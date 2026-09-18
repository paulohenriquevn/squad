"""`sq ci` — why the pipeline is red, including the part the job output never says.

THE MEASUREMENT THAT JUSTIFIES THIS VERB
----------------------------------------
Diagnosing a red CI took roughly eight calls on 2026-09-09. Every job died in three
seconds with zero steps executed; `gh run view --log-failed` returned nothing and the
logs had expired. The reason was in a check-run ANNOTATION and nowhere else:

    "The job was not started because recent account payments have failed or your
     spending limit needs to be increased."

Through the web UI and through the job output, that failure is indistinguishable from
a test failure. So a `sq ci` that reports conclusions and not annotations reproduces
the eight calls instead of replacing them, and fetching them is the whole point.

This is the only verb that reads the network, and it says so in its own output —
`--json` included — because a reader cannot otherwise tell a stale answer from a fresh
one.

Exit codes:
    0 — the most recent run succeeded
    1 — it failed, and the reasons are printed
    2 — could not read: no `gh`, not authenticated, no runs, or not a GitHub remote
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from squad.cli.provenance import describe
from squad.cli.render import emit
from squad.cli.report import FINDING, OK, UNMEASURED, Report

#: Injected so the tests need neither a network nor a token — the shape
#: `check_merge_autonomy.py` already uses for the same reason.
GhRunner = Callable[[list[str]], "tuple[int, str, str]"]


def _default_gh(root: Path) -> GhRunner:
    def run(argv: list[str]) -> tuple[int, str, str]:
        done = subprocess.run(
            ["gh", *argv], capture_output=True, text=True, cwd=root, timeout=60
        , check=False)
        return done.returncode, done.stdout, done.stderr

    return run


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def status(root: Path, *, gh: GhRunner | None = None, limit: int = 1) -> Report:
    runner = gh or _default_gh(root)
    report = Report(verb="ci", observed=describe(root))
    report.not_checked.append(
        "this verb reads the REMOTE over the network, so its answer is as fresh as the "
        "moment it ran and cannot be reproduced from the working tree alone"
    )

    def call(argv: list[str]) -> tuple[int, str, str] | None:
        try:
            return runner(argv)
        except (OSError, subprocess.SubprocessError) as exc:
            report.lines.append(f"gh could not be run: {exc}")
            return None

    listed = call([
        "run", "list", "--limit", str(limit),
        "--json", "databaseId,headSha,conclusion,status,workflowName,headBranch",
    ])
    if listed is None:
        report.exit_code = UNMEASURED
        return report

    code, out, err = listed
    if code != 0:
        report.exit_code = UNMEASURED
        report.lines.append(f"gh refused: {err.strip() or 'no message'}")
        return report

    try:
        runs = json.loads(out or "[]")
    except json.JSONDecodeError:
        report.exit_code = UNMEASURED
        report.lines.append("gh returned output that is not JSON")
        return report

    if not runs:
        # An empty list answers nothing. Reading it as success is the defect this kit
        # finds more than any other.
        report.exit_code = UNMEASURED
        report.lines.append("no workflow runs found — nothing to report, which is not success")
        return report

    # ONE run is reported: the most recent. `--limit` decides how many are FETCHED, and
    # everything after `runs[0]` was discarded — so `--limit 20` read as "consider the
    # last twenty" and reported exactly what `--limit 1` reports. The help text now says
    # which of the two it does, and the count is carried so a reader can see the gap
    # between what was fetched and what was judged.
    run = runs[0]
    if len(runs) > 1:
        report.lines.append(
            f"(fetched {len(runs)} run(s); this reports the most recent only — the "
            f"other {len(runs) - 1} were NOT examined)")
    report.detail["runs_fetched"] = len(runs)
    report.observed.insert(0, f"{run.get('workflowName', '?')} @ {str(run.get('headSha', ''))[:8]}")
    report.detail["run"] = run
    conclusion = run.get("conclusion")
    report.lines.append(
        f"{run.get('headBranch', '?')}: {conclusion or run.get('status', 'unknown')}"
    )

    if conclusion == "success":
        report.exit_code = OK
        return report

    report.exit_code = FINDING
    report.lines.extend(_failure_detail(call, run, report))
    return report


def _failure_detail(call, run: dict, report: Report) -> list[str]:
    """Per-failed-job annotations — the only place a not-started reason appears."""
    lines: list[str] = []
    jobs_response = call(["api", f"repos/{{owner}}/{{repo}}/actions/runs/{run['databaseId']}/jobs"])
    if jobs_response is None or jobs_response[0] != 0:
        report.not_checked.append("the run's jobs could not be listed, so no annotation was read")
        return lines

    try:
        jobs = json.loads(jobs_response[1] or "{}").get("jobs", [])
    except json.JSONDecodeError:
        report.not_checked.append("the jobs response was not JSON, so no annotation was read")
        return lines

    failed = [j for j in jobs if j.get("conclusion") not in (None, "success", "skipped")]
    if not failed:
        lines.append("  no failed job in the run — the failure is at the workflow level")

    seen: set[str] = set()
    for job in failed:
        lines.append(f"  {job.get('name', '?')}: {job.get('conclusion')}")
        annotations = call(["api", f"repos/{{owner}}/{{repo}}/check-runs/{job['id']}/annotations"])
        if annotations is None or annotations[0] != 0:
            lines.append("    (annotations could not be read)")
            continue
        try:
            items = json.loads(annotations[1] or "[]")
        except json.JSONDecodeError:
            items = []
        if not items:
            # Silence here reads as "nothing was wrong". Say it instead.
            lines.append("    no annotation on this job")
            continue
        for item in items:
            message = (item.get("message") or "").strip()
            if not message:
                continue
            if message in seen:
                # Spelling the same paragraph out per job is noise; leaving the job bare
                # reads as "this one had no annotation", which is a different fact.
                lines.append("    (same annotation as above)")
                continue
            seen.add(message)
            lines.append(f"    {item.get('annotation_level', 'note')}: {message}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sq ci", description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--limit", type=int, default=1,
        help="how many runs to FETCH; only the most recent is reported. This said "
             "'consider' until 2026-09-17, and nothing after runs[0] was ever read")
    parser.add_argument("--root", type=Path, default=_repo_root())
    args = parser.parse_args(argv)
    return emit(status(args.root, limit=args.limit), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())

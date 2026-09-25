#!/usr/bin/env python3
"""Flip a milestone checkbox `[ ]` → `[x]` in ROADMAP.md after a green acceptance run.

The `flip` phase of **cycle-acceptance**, which is the only caller. The file lives in
the release slice because that is where the flip used to happen (`cycle-release § 7.5`)
and one implementation of an invariant IS the invariant — moving it would have meant
two. Nothing in `/release` invokes it.

Hard invariant (per `rules/cycle-acceptance.md` § Hard gates): exactly ONE checkbox
flips per accepted milestone. If the diff would produce more than one `[ ]` → `[x]`
transition, the script ABORTS without writing anything.

Idempotent: if the milestone is already `[x]`, exit 0 with INFO. If the
milestone is missing entirely, exit 0 with WARN — the release itself is not
blocked on roadmap metadata.

Side effects (when --commit is passed AND a flip happened):
    - `git add ROADMAP.md && git commit -m "chore(roadmap): mark M<N> done (v<version>)"` on the current branch
    - Append/create `records/roadmap-runs/M<N>-<date>.md` with completion metadata

Usage:
    python3 flip_milestone_checkbox.py \
        --roadmap ROADMAP.md \
        --milestone-id M3 \
        --version 0.4.0 \
        --plan records/plans/foo-plan.md \
        --release-log records/releases/v0.4.0-release.md \
        --commit

Exit codes:
    0 — flipped successfully OR already [x] (no-op) OR milestone missing (WARN, by design)
    1 — single-flip invariant would be violated (multiple [ ] would become [x])
    2 — file not found / parse error
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from datetime import datetime, timezone
from pathlib import Path, Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import
from squad.roadmap import (  # noqa: E402 — post-bootstrap import
    Status,
    find as _find_milestone,
)

#: The only verdicts that may close a milestone. `rules/cycle-acceptance.md` § Hard
#: gates has said so since the flip moved there; until 2026-09-21 this script had never
#: heard the word `verdict` — the gate was honoured by discipline at both ends, and the
#: rule said so in an open regression note rather than pretending otherwise.
GREEN_VERDICTS = ("ACCEPTED", "ACCEPTED_WITH_CAVEATS")


def _header_re(milestone_id: str) -> re.Pattern[str]:
    """Match the literal header for the given milestone, in either [ ] or [x] state."""
    return re.compile(
        rf"^(###\s+{re.escape(milestone_id)}\s+[—\-]{{1,2}}\s+\[)([ x])(\]\s+.+?)$",
        re.MULTILINE,
    )


def flip(roadmap_text: str, milestone_id: str) -> tuple[str, str]:
    """Return (new_text, status) ∈ {flipped, already-x, not-found, cancelled, multi-flip}.

    `cancelled` is separated from `not-found` because they were the same answer and are
    not the same fact. The header pattern cannot match `[-]`, so a cancelled milestone
    reported as absent sent a reader hunting a section that was sitting in the file.
    """
    matches = list(_header_re(milestone_id).finditer(roadmap_text))
    if not matches:
        milestone = _find_milestone(roadmap_text, milestone_id)
        if milestone is not None and milestone.status is Status.CANCELLED:
            return roadmap_text, "cancelled"
        return roadmap_text, "not-found"
    if len(matches) > 1:
        return roadmap_text, "multi-flip"

    match = matches[0]
    current_state = match.group(2)
    if current_state == "x":
        return roadmap_text, "already-x"

    new_text = roadmap_text[: match.start(2)] + "x" + roadmap_text[match.end(2):]

    # The single-flip invariant is enforced ABOVE, by `len(matches) > 1`, and that is
    # the whole of it. What stood here counted occurrences of "] " before and after the
    # replacement — a substring starting at the closing bracket, i.e. AFTER the one
    # character this function rewrites. The two counts were therefore equal for every
    # possible input, and the branch below them was unreachable. A guard that cannot
    # fire reads as a second, independent check and is not one; deleting it leaves the
    # real invariant visible instead of shadowed.
    return new_text, "flipped"


def _git_commit(roadmap_path: Path, milestone_id: str, version: str) -> str | None:
    """Stage and commit ROADMAP.md. Return commit SHA on success, None on failure."""
    repo = roadmap_path.resolve().parent
    msg = f"chore(roadmap): mark {milestone_id} done (v{version})"
    try:
        subprocess.run(["git", "-C", str(repo), "add", str(roadmap_path)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", msg], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        print(f"git commit failed: {exc.stderr.decode(errors='replace')}", file=sys.stderr)
        return None


def _append_roadmap_run(
    roadmap_runs_dir: Path,
    milestone_id: str,
    plan_path: Path | None,
    release_log: Path | None,
    flip_sha: str | None,
) -> Path:
    """Create or append to the roadmap-runs file for this milestone."""
    roadmap_runs_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target = roadmap_runs_dir / f"{milestone_id}-{date_str}.md"

    iso_ts = datetime.now(timezone.utc).isoformat()
    if not target.exists():
        target.write_text(
            "---\n"
            f"milestone_id: {milestone_id}\n"
            f"date: {date_str}\n"
            "status: completed\n"
            f"plan: {plan_path or ''}\n"
            f"release: {release_log or ''}\n"
            f"checkbox_flipped_at: {iso_ts}\n"
            f"flip_commit_sha: {flip_sha or ''}\n"
            "---\n\n"
            f"# Milestone {milestone_id} — completion record\n\n"
            f"Checkbox flipped to [x] by cycle-acceptance on {iso_ts}.\n",
            encoding="utf-8",
        )
    else:
        # Append a completion note rather than overwriting
        target.write_text(
            target.read_text(encoding="utf-8")
            + f"\n## Re-flip / amendment {iso_ts}\n\n"
            + f"- flip_commit_sha: {flip_sha or 'n/a'}\n"
            + f"- release_log: {release_log or 'n/a'}\n",
            encoding="utf-8",
        )
    return target


def _default_runs_dir(project_root: Path) -> Path:
    """Resolve the canonical roadmap-runs directory for this project's layout.

    Defaulting to a CWD-relative `records/roadmap-runs` is what split the
    records in every consumer: the flip wrote its run-file to the project
    ROOT while every other cycle wrote under `.claude/`, so half the audit trail
    landed beside the other half and nobody noticed — an auditor reading one side
    reports absence where the evidence is on the other.

    See rules/records-location.md: `<project>/.squad/` is the one write root, in every
    layout. The branch that used to sit here — plugin install versus standalone kit —
    is gone, and with it the `None` it returned when neither matched.
    """
    return write_records_dir(project_root, "roadmap-runs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roadmap", type=Path, default=Path("ROADMAP.md"))
    parser.add_argument("--milestone-id", required=True, help="Milestone to flip (e.g. M3).")
    parser.add_argument("--version", required=True, help="Semver string without leading 'v'.")
    parser.add_argument(
        "--verdict", required=True,
        help="the verdict compute_acceptance_verdict.py emitted; only "
             f"{' / '.join(GREEN_VERDICTS)} may flip a checkbox")
    parser.add_argument("--plan", type=Path, help="Path to the plan file (recorded in roadmap-runs).")
    parser.add_argument("--release-log", type=Path, help="Path to the release log (recorded in roadmap-runs).")
    parser.add_argument(
        "--roadmap-runs-dir",
        type=Path,
        default=None,
        help=(
            "Directory for the roadmap-runs audit file. Defaults to the canonical "
            "records for this layout (see rules/records-location.md)."
        ),
    )
    parser.add_argument("--commit", action="store_true", help="Stage & commit ROADMAP.md on the current branch.")
    args = parser.parse_args()

    if not args.roadmap.exists():
        print(f"file not found: {args.roadmap}", file=sys.stderr)
        return 2

    if not re.match(r"^M\d+$", args.milestone_id):
        print(f"invalid milestone_id (expected M<N>): {args.milestone_id!r}", file=sys.stderr)
        return 2

    # `[x]` claims a user-visible promise was met and was WATCHED being met. Only the
    # script that computed the verdict can say that, so the token travels here and is
    # checked, rather than the caller being trusted to have looked at it.
    if args.verdict not in GREEN_VERDICTS:
        print(
            f"FAILS roadmap-checkbox: refusing to flip {args.milestone_id} on verdict "
            f"{args.verdict!r}. Only {' / '.join(GREEN_VERDICTS)} may close a "
            f"milestone (rules/cycle-acceptance.md § Hard gates). REJECTED and "
            f"NOT_VALIDATED both leave the checkbox at `[ ]`.",
            file=sys.stderr,
        )
        return 1

    runs_dir = args.roadmap_runs_dir or _default_runs_dir(args.roadmap.resolve().parent)

    text = args.roadmap.read_text(encoding="utf-8")
    new_text, status = flip(text, args.milestone_id)

    if status == "not-found":
        # NOT exit 0. This printed a WARN and returned success until 2026-09-21, so a
        # caller running `flip || exit 1` was told the flip happened. A milestone whose
        # header sits at `##` instead of `###` never closed and never said why — the
        # silence `rules/cycle-acceptance.md` documented and left standing.
        print(
            f"FAILS roadmap-checkbox: {args.milestone_id} not found in {args.roadmap}. "
            f"The header must be `### {args.milestone_id} — [ ] <name>` — a `##` header "
            f"does not match, and neither does a missing em-dash. Nothing was flipped.",
            file=sys.stderr,
        )
        return 1
    if status == "cancelled":
        print(
            f"FAILS roadmap-checkbox: {args.milestone_id} is cancelled (`[-]`). A "
            f"cancelled milestone is not accepted into done; reopen it to `[ ]` first "
            f"if the work resumed.",
            file=sys.stderr,
        )
        return 1
    if status == "already-x":
        print(f"INFO roadmap-checkbox: {args.milestone_id} already [x] — no-op")
        return 0
    if status == "multi-flip":
        print(
            f"ABORT roadmap-checkbox: single-flip invariant would be violated "
            f"({args.milestone_id} matches multiple headers)",
            file=sys.stderr,
        )
        return 1

    args.roadmap.write_text(new_text, encoding="utf-8")
    flip_sha: str | None = None
    commit_failed = False
    if args.commit:
        flip_sha = _git_commit(args.roadmap, args.milestone_id, args.version)
        commit_failed = flip_sha is None

    run_file = _append_roadmap_run(
        runs_dir, args.milestone_id, args.plan, args.release_log, flip_sha
    )
    # Three states, three words. `flip_sha or 'n/a (--commit not passed)'` printed the
    # SAME line whether the caller never asked for a commit or asked and git refused —
    # and it returned 0 either way, so a release script reading the exit code was told
    # the roadmap change had landed when it was sitting unstaged in the working tree.
    if commit_failed:
        detail = "FAILED — the flip is in the working tree and is NOT committed"
    elif flip_sha:
        detail = flip_sha
    else:
        detail = "n/a (--commit not passed)"
    print(
        f"FLIPPED {args.milestone_id} [ ]→[x] in {args.roadmap}; "
        f"audit: {run_file}; commit: {detail}"
    )
    return 1 if commit_failed else 0


if __name__ == "__main__":
    sys.exit(main())

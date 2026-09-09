"""`sq test` — run the suites, and name the ones that did not run.

WHY THIS WRAPS RATHER THAN REIMPLEMENTS
---------------------------------------
`mechanisms/cycle/run_slice_tests.sh` is THE definition of "the suites": `conftest.py`
names it in its refusal, `tests/test_multi_slice_guard.py` asserts that name is
present, and CI invokes it. A `sq test` that discovered suites for itself would be the
second-list defect the ADR forbids, wearing a different filename. So the script runs
the tests; this module selects, invokes, and reports.

THE PROPERTY THAT JUSTIFIES THE COMMAND
---------------------------------------
On 2026-09-09 a session reported `1894 passed` as full coverage. 152 tests collected
nowhere and 22 slice suites had not run, and nothing on screen said the other half
existed. So every report here carries what was NOT run, and it is a field rather than
a printed line — as prose it would have left `--json` handing the same false report to
anything that consumed it.

Exit codes:
    0 — every suite that ran, passed
    1 — a suite failed
    2 — a suite collected nothing, or the selection could not be computed
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mechanisms" / "conventions"))

from touched_slices import Selection, select

from squad.cli.provenance import describe
from squad.cli.render import emit
from squad.cli.report import FINDING, OK, UNMEASURED, Report

#: pytest's own exit code for "no tests were collected". Distinct from 1 on purpose:
#: an empty set is an inability to measure, not a measurement that failed.
_NOTHING_COLLECTED = 5


@dataclass(frozen=True)
class SuiteRow:
    """One line of the runner's machine-readable trailer."""

    path: str
    rc: int
    passed: int | None
    failed: int | None
    collected: int | None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def discover_slices(root: Path) -> set[str]:
    """The slice names, by the same glob the runner uses: `skills/*/tests` that exist."""
    return {p.parent.name for p in sorted(root.glob("skills/*/tests")) if p.is_dir()}


def root_paths(root: Path) -> list[str]:
    """The testpaths the root suite covers, read from the declaration rather than fixed.

    Hard-coding them here is exactly how kit#58 happened: the runner named `tests` and
    the two paths added to close an earlier hole fell back out of it.
    """
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    import re

    match = re.search(r"^testpaths\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if not match:
        return ["tests"]
    return re.findall(r'"([^"]+)"', match.group(1))


def parse_trailer(output: str) -> list[SuiteRow]:
    """The `SUITE\t…` lines the runner prints after the human blocks."""

    def number(token: str) -> int | None:
        # `-` means the runner could not read a count. Zero would be a claim.
        return int(token) if token.isdigit() else None

    rows: list[SuiteRow] = []
    for line in output.splitlines():
        if not line.startswith("SUITE\t"):
            continue
        parts = line.split("\t")
        if len(parts) != 6:
            continue
        rows.append(
            SuiteRow(parts[1], int(parts[2]) if parts[2].isdigit() else 2,
                     number(parts[3]), number(parts[4]), number(parts[5]))
        )
    return rows


def failing_output(output: str, path: str) -> str:
    """The runner's captured pytest block for one suite.

    The runner prints every suite inside `::group::pytest <path>` … `::endgroup::` and
    this command captures all of it — the first version then threw the failing half
    away and printed `FAIL` with no reason, which makes the caller run the suite again
    to learn what this run already knew.

    It cost a real capture to notice. A flaky test fired during a full run, and the
    CHANGELOG's instruction for that very test is "capture the failing output rather
    than re-run until it passes".
    """
    marker = f"::group::pytest {path}"
    start = output.find(marker)
    if start == -1:
        return ""
    end = output.find("::endgroup::", start)
    block = output[start + len(marker):end if end != -1 else None]
    return block.strip("\n")


def build_report(
    root: Path,
    *,
    rows: list[SuiteRow],
    selected: set[str] | None,
    skipped_slices: list[str],
    base: str | None,
    nothing_changed: bool = False,
    raw: str = "",
) -> Report:
    """Turn what ran into a report that also states what did not."""
    report = Report(verb="test", observed=[f"{len(rows)} suite(s)", *describe(root)])

    if nothing_changed:
        # A clean tree means there is nothing to test — which is NOT the same as "test
        # the root suite". The first implementation let an empty slice list fall through
        # to the root, so `--touched` on a clean tree ran 1929 tests for eight minutes
        # to report nothing.
        report.lines.append("no changed files — nothing to run")
        report.not_checked.append(
            f"everything: {len(skipped_slices)} slice suite(s) and the root suite NOT RUN, "
            f"because nothing changed to make them worth running"
        )
        report.not_checked.append("run them anyway with: sq test")
        report.exit_code = OK
        return report

    total = sum(r.passed for r in rows if r.passed is not None)
    for row in sorted(rows, key=lambda r: r.path):
        count = "?" if row.passed is None else str(row.passed)
        verdict = "ok" if row.rc == 0 else ("no tests" if row.rc == _NOTHING_COLLECTED else "FAIL")
        report.lines.append(f"  {verdict:>8}  {count:>5}  {row.path}")
    report.lines.append(f"  {'total':>8}  {total:>5}")
    report.detail["total_passed"] = total
    report.detail["suites"] = [r.__dict__ for r in rows]

    if selected is not None:
        report.observed.insert(0, f"selected {len(selected)} slice(s)")
        if base:
            report.observed.append(f"vs {base}")

    if skipped_slices:
        report.not_checked.append(
            f"{len(skipped_slices)} slice suite(s) NOT RUN: {', '.join(skipped_slices)}"
        )
        report.not_checked.append("run them with: sq test  (no --touched)")
    else:
        report.not_checked.append("nothing — every slice suite and the root suite ran")

    empty = [r for r in rows if r.rc == _NOTHING_COLLECTED]
    failed = [r for r in rows if r.rc not in (0, _NOTHING_COLLECTED)]

    # The reason, beside the verdict. A runner that says FAIL and nothing else makes
    # the caller run it again to learn what this run already captured.
    for row in failed:
        block = failing_output(raw, row.path)
        if block:
            report.lines.append("")
            report.lines.append(f"  --- {row.path} ---")
            report.lines.extend(f"  {ln}" for ln in block.splitlines()[-25:])
            report.detail.setdefault("failures", {})[row.path] = block

    if empty:
        report.exit_code = UNMEASURED
        report.not_checked.append(
            f"{len(empty)} suite(s) collected nothing, which is an empty set rather than "
            f"a passing one: {', '.join(r.path for r in empty)}"
        )
    elif failed:
        report.exit_code = FINDING
    else:
        report.exit_code = OK
    return report


def _changed_paths(root: Path, since: str | None) -> tuple[list[str], str | None, str | None]:
    """Changed files, the base they were compared against, and any reason to widen.

    The DEFAULT is the working tree — staged, unstaged and untracked — because that is
    what "touched" means while working. Comparing against the trunk by default was the
    first implementation and it was wrong in a way only running it showed: this branch
    is 335 commits ahead of `develop`, so every one of the 792 tracked files came back
    as changed and `--touched` degenerated into "run everything, slowly".

    `--since REF` asks the other question — what this branch changed — via merge-base.

    Untracked files are unioned in either way: `git diff` does not list them, so a
    brand-new `skills/foo/tests/test_bar.py` would be invisible and the run would
    report success having never seen it.
    """

    def git(*args: str) -> str | None:
        try:
            done = subprocess.run(  # noqa: PLW1510
                ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout if done.returncode == 0 else None

    status = git("status", "--porcelain")
    if status is None:
        # Not a git repository, or git is absent. Widening is the only safe answer;
        # exit 2 here would tempt a caller to read "could not scope" as "nothing to run".
        return [], None, "git could not be read — cannot scope, so nothing is excluded"

    # `XY path`, and for a rename `XY old -> new`. Take the destination.
    working = [
        line[3:].split(" -> ")[-1].strip().strip('"')
        for line in status.splitlines()
        if line[:2].strip()
    ]

    if since is None:
        return sorted(set(working)), "working tree", None

    merge_base = git("merge-base", "HEAD", since)
    if merge_base is None:
        return [], None, f"no merge-base with {since} — cannot scope, so nothing is excluded"

    sha = merge_base.strip()
    diff = git("diff", "--name-only", sha) or ""
    return sorted(set(diff.split() + working)), f"{since}@{sha[:8]}", None


def _run(root: Path, only: list[str] | None) -> tuple[str, int]:
    """Invoke the runner. `only` restricts it to named suites via one pytest each."""
    if only is None:
        done = subprocess.run(  # noqa: PLW1510
            ["bash", str(root / "mechanisms" / "cycle" / "run_slice_tests.sh")],
            capture_output=True, text=True, cwd=root,
        )
        return done.stdout, done.returncode

    # The SAME wire format the runner emits, so `failing_output` has one shape to read
    # and a filtered run explains a failure exactly as a full run does.
    blocks: list[str] = []
    trailer: list[str] = []
    worst = 0
    for path in only:
        done = subprocess.run(  # noqa: PLW1510
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header",
             *path.split()],
            capture_output=True, text=True, cwd=root,
        )
        out = done.stdout + done.stderr
        blocks.append(f"::group::pytest {path}\n{out}\n::endgroup::")
        passed = _first(out, r"(\d+) passed")
        failed = _first(out, r"(\d+) failed")
        collected = _first(out, r"collected (\d+)")
        trailer.append(
            f"SUITE\t{path}\t{done.returncode}\t{passed}\t{failed}\t{collected}"
        )
        worst = max(worst, done.returncode)
    return "\n".join([*blocks, *trailer]), worst


def _first(text: str, pattern: str) -> str:
    import re

    found = re.findall(pattern, text)
    return found[-1] if found else "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sq test", description=__doc__.split("\n")[0])
    parser.add_argument("--touched", action="store_true",
                        help="only the suites the working tree's changes can affect")
    parser.add_argument("--since", metavar="REF",
                        help="what this branch changed vs REF (merge-base), instead of "
                             "the working tree")
    parser.add_argument("--slice", action="append", default=[], dest="slices",
                        help="one slice by name (repeatable)")
    parser.add_argument("--list", action="store_true", help="the suites, without running them")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=_repo_root())
    args = parser.parse_args(argv)

    root: Path = args.root
    known = discover_slices(root)

    if args.list:
        report = Report(verb="test", observed=[f"{len(known)} slice(s)", *describe(root)])
        report.lines = [f"  root    {' '.join(root_paths(root))}"]
        report.lines += [f"  slice   skills/{name}/tests" for name in sorted(known)]
        report.not_checked.append("nothing — --list is the whole set, and it ran none of it")
        return emit(report, as_json=args.json)

    selected: set[str] | None = None
    base: str | None = None
    only: list[str] | None = None

    if args.slices:
        unknown = sorted(set(args.slices) - known)
        if unknown:
            print(f"sq test: no such slice: {', '.join(unknown)}", file=sys.stderr)
            print("    sq test --list  for the names", file=sys.stderr)
            return UNMEASURED
        selected = set(args.slices)
        only = [f"skills/{name}/tests" for name in sorted(selected)]

    elif args.touched:
        paths, base, widen = _changed_paths(root, args.since)
        if widen:
            print(f"sq test: {widen}", file=sys.stderr)
            selection = Selection(everything=True, root_suite=True, reasons=(widen,))
        else:
            selection = select(paths, frozenset(known))
        if selection.everything:
            only = None  # run the lot
        elif not selection.slices and not selection.root_suite:
            return emit(
                build_report(root, rows=[], selected=set(),
                             skipped_slices=sorted(known), base=base, nothing_changed=True),
                as_json=args.json,
            )
        else:
            selected = set(selection.slices)
            only = [f"skills/{name}/tests" for name in sorted(selected)]
            if selection.root_suite:
                only.insert(0, " ".join(root_paths(root)))

    output, _ = _run(root, only)
    rows = parse_trailer(output)

    if not rows:
        print("sq test: the runner produced no machine-readable trailer", file=sys.stderr)
        print(output[-2000:], file=sys.stderr)
        return UNMEASURED

    ran = {r.path for r in rows}
    skipped = sorted(name for name in known if f"skills/{name}/tests" not in ran)
    return emit(
        build_report(root, rows=rows, selected=selected, skipped_slices=skipped,
                     base=base, raw=output),
        as_json=args.json,
    )


if __name__ == "__main__":
    raise SystemExit(main())

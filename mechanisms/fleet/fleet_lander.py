#!/usr/bin/env python3
"""Land a lane's verified branch on the working branch, or say exactly why not.

WHY THIS EXISTS
---------------

A lane commits on its branch and stops. That is correct — pushing and merging are
not a lane's call. But nothing else did it either: measured 2026-09-03, five
repairs were completed by lanes and all five were pushed and merged by a person.
With `fleet_router.py` handing work out automatically, that end became the
bottleneck — every lane would fill and the sixth unit would have nowhere to go.

WHAT IT REFUSES
---------------

- It never pushes a tree it has not seen pass. A suite that could not be run is
  not a pass, and `pytest` exiting 5 on an empty collection is not a pass either.
- The merge happens in a **scratch worktree cut from `origin/workspace`**, never
  in anybody's working tree. Two individually green branches can merge into a red
  tree; when that happens the scratch tree is thrown away and nothing is pushed.
- It does not close the issue. A merge to the working branch is not availability,
  and the person blocked by a defect is served only by the second one.
- It does not open the PR to `develop`. That promotion is the operator's, and the
  rules this kit ships say so in as many words.
- No `--no-verify`, no `push --force`, no `reset`, no `checkout`, no `revert`. A
  test reads this file and fails if any command built here carries one. The single
  `--force` in this module is `git worktree remove --force`, on a scratch
  directory created three lines earlier — it skips no check and discards nobody's
  work, and a second one cannot be added under cover of it: a test pins that
  there is exactly one and says which.

Usage:
    fleet_lander.py --repo /path/to/kit
    fleet_lander.py --repo /path/to/kit --apply

Exit codes:
    0  ran; every branch either landed or was reported with its reason
    1  at least one branch was refused (the reasons are on stdout)
    2  invocation error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent

#: What a lane's branch looks like. Anything else is somebody's own work and the
#: lander has no standing to touch it.
_LANE_BRANCH = re.compile(r"^fix/kit\d+(?:-|$)")

#: `pytest` prints this when it collected nothing. Exit code alone cannot tell it
#: from a pass, which is how an empty sweep gets published as a clean result.
_EMPTY_SUITE = ("no tests ran", "no tests collected")


@dataclass(frozen=True)
class Ran:
    ok: bool
    stdout: str = ""
    stderr: str = ""

    @property
    def text(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


@dataclass(frozen=True)
class Verdict:
    land: bool
    reason: str


def assess(*, branch: str, suite: Ran | None, merge: Ran | None,
           after: Ran | None, cleanup: list[Ran] | None = None) -> Verdict:
    """Decide whether `branch` may land. Pure — it runs nothing.

    Every gate is a measurement someone took, and `None` means the measurement
    did not happen. `None` never passes: this kit's most-found defect is an
    inability to measure published as a measurement, and a lander that lets an
    unrun suite through would push it straight to the working branch.
    """
    #: The merge is judged FIRST because it is the cheap measurement and the
    #: caller pays for the others in that order. A branch that cannot merge is
    #: refused whether or not its suite is green, so running the suite first
    #: buys an answer nobody can act on. Measured 2026-09-04 (kit#26): three
    #: branches conflicting on CHANGELOG.md cost two suites each per pass, over
    #: three passes — an hour spent proving branches correct that git would not
    #: let land. A conflicting merge with no suite run must say so in the merge's
    #: words: told "the suite was not run", an operator goes hunting a broken
    #: test runner instead of a conflict.
    if merge is not None and not merge.ok:
        return _with_cleanup(Verdict(False, f"{branch}: the merge did not apply — {_tail(merge.text)}"), cleanup)

    if suite is None:
        return _with_cleanup(Verdict(False, f"{branch}: the branch's suite was not run, so it is unverified"), cleanup)
    if not suite.ok:
        return _with_cleanup(Verdict(False, f"{branch}: the branch's suite failed — {_tail(suite.text)}"), cleanup)
    if _looks_empty(suite.text):
        return _with_cleanup(Verdict(False, f"{branch}: the suite reported no tests, which is not a pass"), cleanup)

    if merge is None:
        return _with_cleanup(Verdict(False, f"{branch}: the merge was not attempted"), cleanup)

    if after is None:
        return _with_cleanup(Verdict(False, f"{branch}: the suite was not run after the merge"), cleanup)
    if not after.ok:
        return _with_cleanup(Verdict(False, f"{branch}: the suite failed after the merge — {_tail(after.text)}"), cleanup)
    if _looks_empty(after.text):
        return _with_cleanup(Verdict(
            False, f"{branch}: after the merge the suite reported no tests"), cleanup)
    return _with_cleanup(Verdict(True, f"{branch}: green on its own and green merged"),
                         cleanup)


def _with_cleanup(verdict: Verdict, cleanup: list[Ran] | None) -> Verdict:
    """Append a leaked-worktree note without letting it change the code verdict.

    Whether the branch was good and whether a temporary directory was tidied are
    different questions, and folding one into the other would either hide a leak
    or refuse a good branch over housekeeping. Measured 2026-09-03: a scratch tree
    survived its branch and why could not be answered, because the cleanup call
    discarded its own result.
    """
    failed = [c for c in (cleanup or []) if not c.ok]
    if not failed:
        return verdict
    detail = "; ".join(_tail(c.text, 80) for c in failed)
    return Verdict(verdict.land,
                   f"{verdict.reason} [cleanup leaked {len(failed)} worktree(s): {detail}]")


def _looks_empty(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _EMPTY_SUITE)


def _tail(text: str, limit: int = 200) -> str:
    return " ".join(text.split())[-limit:] or "no output"


# ── running things ────────────────────────────────────────────────────────────

def run(command: list[str], *, cwd: Path, timeout: int = 3000) -> Ran:
    """Run and report. A command that could not start is `ok=False` with the
    reason, never an empty success."""
    try:
        done = subprocess.run(  # noqa: PLW1510 — the returncode is the verdict
            command, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return Ran(False, stderr=f"{command[0]} did not finish within {timeout}s")
    except (OSError, subprocess.SubprocessError) as exc:
        return Ran(False, stderr=f"{command[0]} could not be run: {exc}")
    return Ran(done.returncode == 0, done.stdout or "", done.stderr or "")


def lane_branches(repo: Path) -> list[str] | None:
    """Branches a lane produced that are ahead of the working branch, or None.

    None means the listing FAILED — git missing, a broken repository, a timeout, all of
    which `run()` folds into `Ran(ok=False)`. It used to be `[]`, which `main` renders
    as "swept the repository: no lane branch is ahead of origin/workspace" over a sweep
    that never happened. The comment on that very line states the contract this broke:
    "'nothing to land' and 'I did not look' must not read the same, and on this kit they
    have before." `fleet_router.plan()` refuses on an unreadable branch set for the same
    reason, one file along.
    """
    listed = run(["git", "-C", str(repo), "branch", "-a",
                  "--format=%(refname:short)"], cwd=repo, timeout=60)
    if not listed.ok:
        return None
    names = {ln.strip().removeprefix("origin/") for ln in listed.stdout.splitlines()}
    out = []
    for name in sorted(n for n in names if _LANE_BRANCH.match(n)):
        ahead = run(["git", "-C", str(repo), "rev-list", "--count",
                     f"origin/workspace..{name}"], cwd=repo, timeout=60)
        if ahead.ok and ahead.stdout.strip() not in ("", "0"):
            out.append(name)
    return out


def land(repo: Path, branch: str, *, apply: bool, timeout: int) -> Verdict:
    """Verify `branch`, merge it in a scratch tree, and push only if it holds.

    TWO scratch trees, not one. A single tree that tries a fast-forward and falls
    back to a merge cannot say which state the suite ran against: when the
    fast-forward fails the tree is still the working branch, so "the branch's
    suite" would be the working branch's suite reported under the branch's name.
    Separating them costs one checkout and removes the ambiguity entirely.

    Cleanup runs whatever happens, and its result is READ. A `finally` that calls
    a command and discards the answer is how a leaked worktree became
    unexplainable on this module's first live run.
    """
    # Unique BY CONSTRUCTION. The names were `<branch>-alone-<epoch seconds>` under a
    # machine-global root, so two landers on the same branch within the same second — the
    # supervisor's land loop plus an operator's manual `--apply`, or two supervisors —
    # picked the same paths. `git worktree add` then failed for the second, and the
    # failure reads as a missing worktree rather than as a collision. `mkdtemp` makes the
    # clash impossible instead of unlikely.
    root = Path("/tmp/squad-landing")
    root.mkdir(parents=True, exist_ok=True)
    safe_branch = branch.replace("/", "-")
    session = Path(tempfile.mkdtemp(prefix=f"{safe_branch}-", dir=str(root)))
    alone = session / "alone"
    merged_tree = session / "merged"
    made: list[Path] = []

    def add(tree: Path, ref: str) -> bool:
        ok = run(["git", "-C", str(repo), "worktree", "add", "--detach",
                  str(tree), ref], cwd=repo, timeout=120)
        if ok.ok:
            made.append(tree)
        return ok.ok

    def tidy() -> list[Ran]:
        return [run(["git", "-C", str(repo), "worktree", "remove", "--force",
                     str(tree)], cwd=repo, timeout=120) for tree in made]

    try:
        # Re-fetched per branch, not once per pass. `origin/workspace` moves every
        # time a branch lands, and cutting the next merge tree from a snapshot
        # taken before that makes its push a non-fast-forward — safely refused,
        # but it means only ONE branch could ever land in a pass.
        run(["git", "-C", str(repo), "fetch", "--quiet", "origin"], cwd=repo, timeout=300)
        if not add(alone, branch):
            return _with_cleanup(
                Verdict(False, f"{branch}: no scratch worktree for the branch"), tidy())
        if not add(merged_tree, "origin/workspace"):
            return _with_cleanup(
                Verdict(False, f"{branch}: no scratch worktree for the merge"), tidy())

        # 1. the merge, first, because it is the cheap one. A branch that cannot
        # merge is refused regardless of what its suite says, so the suites are
        # not paid for until the merge is known to apply. Ordering them the other
        # way cost this fleet an hour over three passes (kit#26).
        merged = run(["git", "-C", str(merged_tree), "merge", "--no-ff", "--no-edit",
                      branch], cwd=merged_tree, timeout=120)
        if not merged.ok:
            return _with_cleanup(assess(branch=branch, suite=None, merge=merged,
                                        after=None), tidy())

        # 2. the branch on its own, against its own tree
        suite = run([sys.executable, "-m", "pytest", "-q"], cwd=alone, timeout=timeout)
        # 3. and again against the merged tree
        after = run([sys.executable, "-m", "pytest", "-q"], cwd=merged_tree,
                    timeout=timeout)
        verdict = assess(branch=branch, suite=suite, merge=merged, after=after)
        if verdict.land and apply:
            # Pushed from the tree that was measured, so what lands is what passed.
            pushed = run(["git", "-C", str(merged_tree), "push", "origin",
                          "HEAD:workspace"], cwd=merged_tree, timeout=300)
            if not pushed.ok:
                verdict = Verdict(False, f"{branch}: verified but the push was "
                                         f"refused — {_tail(pushed.text)}")
        return _with_cleanup(verdict, tidy())
    except Exception:
        tidy()
        raise


def report_each(branches: list[str], *,
                assess_branch: Callable[..., Verdict],
                repo: Path, apply: bool,
                timeout: int) -> list[Verdict]:
    """Assess each branch, printing before and after rather than at the end.

    `assess_branch`, not `land`. That parameter shadowed the module-level function
    `land` it is called with, while `verdict.land` inside this body is the boolean
    saying whether the branch may be pushed — so in fifteen lines a reader met `land`
    as a module function, as an injected callable and as a field. It was untyped too,
    so nothing said which of the three a given occurrence was.

    Two full suites per branch is slow on purpose — what it protects is the
    branch every other lane cuts from — and on a five-branch pass that is over an
    hour. Collecting the verdicts and printing them at the close made the whole
    run silent, and a silent process is indistinguishable from a dead one. The
    branch is named on START as well, so a reader twelve minutes in can tell
    which of the five it is waiting on.
    """
    verdicts: list[Verdict] = []
    for index, branch in enumerate(branches, 1):
        print(f"  [{index}/{len(branches)}] {branch}: two suites, this takes a while…",
              flush=True)
        verdict = land(repo, branch, apply=apply, timeout=timeout)
        print(("  landed : " if verdict.land else "  refused: ") + verdict.reason,
              flush=True)
        verdicts.append(verdict)
    return verdicts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="push the verified merge; without it nothing leaves the machine")
    ap.add_argument("--timeout", type=int, default=3000, help="per-suite ceiling in seconds")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    if not (repo / ".git").exists():
        print(f"{repo} is not a git repository", file=sys.stderr)
        return 2

    # The fetch's result was DROPPED, and everything below decides what is landable from
    # `origin/workspace..<branch>` against whatever remote-tracking refs happen to be on
    # disk. With the network down or the remote unauthenticated, the sweep ran on stale
    # refs and printed the line two paragraphs down — the one that insists a sweep and a
    # non-sweep must not read the same.
    fetched = run(["git", "-C", str(repo), "fetch", "--quiet", "origin"],
                  cwd=repo, timeout=300)
    if not fetched.ok:
        print(f"could not fetch origin, so the remote-tracking refs are stale and a "
              f"sweep over them is not a sweep: {(fetched.stderr or '').strip()[:300]}",
              file=sys.stderr)
        return 2

    branches = lane_branches(repo)
    if branches is None:
        print("the repository's branches could not be listed, so whether a lane has "
              "work to land is unknown. Refusing to report a sweep.", file=sys.stderr)
        return 2
    if not branches:
        # Said out loud. "nothing to land" and "I did not look" must not read the
        # same, and on this kit they have before.
        print("swept the repository: no lane branch is ahead of origin/workspace")
    verdicts = ([] if args.json else
                report_each(branches, assess_branch=land, repo=repo, apply=args.apply,
                            timeout=args.timeout))
    if args.json:
        verdicts = [land(repo, b, apply=args.apply, timeout=args.timeout)
                    for b in branches]
        print(json.dumps({"branches": branches, "applied": args.apply,
                          "landed": [v.reason for v in verdicts if v.land],
                          "refused": [v.reason for v in verdicts if not v.land]},
                         indent=2, ensure_ascii=False))
    return 1 if any(not v.land for v in verdicts) else 0


if __name__ == "__main__":
    raise SystemExit(main())

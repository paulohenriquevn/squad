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
    fleet_lander.py --repo /home/paulo/dev/squad
    fleet_lander.py --repo /home/paulo/dev/squad --apply

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
import time
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
           after: Ran | None) -> Verdict:
    """Decide whether `branch` may land. Pure — it runs nothing.

    Every gate is a measurement someone took, and `None` means the measurement
    did not happen. `None` never passes: this kit's most-found defect is an
    inability to measure published as a measurement, and a lander that lets an
    unrun suite through would push it straight to the working branch.
    """
    if suite is None:
        return Verdict(False, f"{branch}: the branch's suite was not run, so it is unverified")
    if not suite.ok:
        return Verdict(False, f"{branch}: the branch's suite failed — {_tail(suite.text)}")
    if _looks_empty(suite.text):
        return Verdict(False, f"{branch}: the suite reported no tests, which is not a pass")

    if merge is None:
        return Verdict(False, f"{branch}: the merge was not attempted")
    if not merge.ok:
        return Verdict(False, f"{branch}: the merge did not apply — {_tail(merge.text)}")

    if after is None:
        return Verdict(False, f"{branch}: the suite was not run after the merge")
    if not after.ok:
        return Verdict(False, f"{branch}: the suite failed after the merge — {_tail(after.text)}")
    if _looks_empty(after.text):
        return Verdict(False, f"{branch}: after the merge the suite reported no tests")
    return Verdict(True, f"{branch}: green on its own and green merged")


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


def lane_branches(repo: Path) -> list[str]:
    """Branches a lane produced that are ahead of the working branch."""
    listed = run(["git", "-C", str(repo), "branch", "-a",
                  "--format=%(refname:short)"], cwd=repo, timeout=60)
    if not listed.ok:
        return []
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
    """
    stamp = int(time.time())
    root = Path("/tmp/squad-landing")
    alone = root / f"{branch.replace('/', '-')}-alone-{stamp}"
    merged_tree = root / f"{branch.replace('/', '-')}-merged-{stamp}"
    made_a = run(["git", "-C", str(repo), "worktree", "add", "--detach",
                  str(alone), branch], cwd=repo, timeout=120)
    if not made_a.ok:
        return Verdict(False, f"{branch}: no scratch worktree — {_tail(made_a.text)}")
    made_b = run(["git", "-C", str(repo), "worktree", "add", "--detach",
                  str(merged_tree), "origin/workspace"], cwd=repo, timeout=120)
    try:
        if not made_b.ok:
            return Verdict(False, f"{branch}: no merge worktree — {_tail(made_b.text)}")
        # 1. the branch on its own, against its own tree
        suite = run([sys.executable, "-m", "pytest", "-q"], cwd=alone, timeout=timeout)
        # 2. the branch merged into the working branch, against a fresh tree
        merged = run(["git", "-C", str(merged_tree), "merge", "--no-ff", "--no-edit",
                      branch], cwd=merged_tree, timeout=120)
        after = run([sys.executable, "-m", "pytest", "-q"], cwd=merged_tree,
                    timeout=timeout) if merged.ok else None
        verdict = assess(branch=branch, suite=suite, merge=merged, after=after)
        if verdict.land and apply:
            # Pushed from the tree that was measured, so what lands is what passed.
            pushed = run(["git", "-C", str(merged_tree), "push", "origin",
                          "HEAD:workspace"], cwd=merged_tree, timeout=300)
            if not pushed.ok:
                return Verdict(False, f"{branch}: verified but the push was refused — "
                                      f"{_tail(pushed.text)}")
        return verdict
    finally:
        for tree in (alone, merged_tree):
            run(["git", "-C", str(repo), "worktree", "remove", "--force", str(tree)],
                cwd=repo, timeout=120)


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

    run(["git", "-C", str(repo), "fetch", "--quiet", "origin"], cwd=repo, timeout=300)
    branches = lane_branches(repo)
    verdicts = [land(repo, b, apply=args.apply, timeout=args.timeout) for b in branches]

    report = {"branches": branches, "applied": args.apply,
              "landed": [v.reason for v in verdicts if v.land],
              "refused": [v.reason for v in verdicts if not v.land]}
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        if not branches:
            # Said out loud. "nothing to land" and "I did not look" must not read
            # the same, and on this kit they have before.
            print("swept the repository: no lane branch is ahead of origin/workspace")
        for verdict in verdicts:
            print(("landed : " if verdict.land else "refused: ") + verdict.reason)
    return 1 if any(not v.land for v in verdicts) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Is this release tag the object the rule says it is, on the branch it says it is?

    python3 mechanisms/gates/check_tag_integrity.py --tag v1.2.0
    python3 mechanisms/gates/check_tag_integrity.py --tag v1.2.0 --trunk main --json

## The gate this replaces, and why it could never have passed

`rules/cycle-release.md` declared the tag-cut gate as "`git tag --verify` resolves AND
tag points at the merge commit". Its own Step 7 cuts the tag with `git tag -a` —
ANNOTATED, not signed. `--verify` checks a GPG signature, so the two clauses contradict
each other. Measured:

    $ git tag -a v1.0.0 -m "release" && git tag --verify v1.0.0
    error: no signature found
    exit=1

Every correctly-cut tag in this kit would have failed its own gate. Nothing caught it
because the gate was never mechanised: the table promised a check that no script ran,
for as long as the table has existed.

Beside it, a second clause carried as declared debt since 2026-09-01 — "Tag must be
annotated (`git tag -a`) and pushed only after merge to `main`", with the note that
"nothing inspects the tag object's type or the branch it was cut from". That is the same
question about the same object, and it is the one worth asking.

## What is actually checked

1. **The tag object is annotated.** `git cat-file -t` answers `tag` for an annotated tag
   and `commit` for a lightweight one — a lightweight tag is a bare ref with no tagger,
   no date and no message, so a release cut that way leaves no record of who cut it or
   when.
2. **The commit it names is contained in the trunk.** `git merge-base --is-ancestor`
   rather than string-matching a branch name, because a tag on an unmerged commit marks
   a release that cannot be checked out of `main` — the artifact is published and the
   history it claims is not there.

Signature is deliberately NOT checked. This kit does not sign tags, and a gate that
demands what the procedure does not produce is the defect above, rebuilt.

## Why a missing tag exits 2

An absent tag is not a passing tag. `2` is this kit's could-not-sweep code (`_contract.py`):
an inability to measure is never reported as a measurement.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _contract import add_root  # noqa: E402 — sibling module, path set above

#: Exit codes, per `_contract.py`.
OK, FOUND, UNMEASURABLE = 0, 1, 2


@dataclass
class TagReport:
    tag: str
    trunk: str
    exists: bool = False
    object_kind: str | None = None
    in_trunk: bool | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def annotated(self) -> bool:
        return self.object_kind == "tag"

    def exit_code(self) -> int:
        if not self.exists or self.in_trunk is None:
            return UNMEASURABLE
        return FOUND if self.problems else OK


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def check_tag_integrity(root: Path, tag: str, trunk: str) -> TagReport:
    report = TagReport(tag=tag, trunk=trunk)

    resolved = _git(root, "rev-parse", "--verify", f"refs/tags/{tag}")
    if resolved.returncode != 0:
        return report
    report.exists = True

    kind = _git(root, "cat-file", "-t", resolved.stdout.strip())
    report.object_kind = kind.stdout.strip() if kind.returncode == 0 else None
    if report.object_kind is None:
        return report
    if not report.annotated:
        report.problems.append(
            f"{tag} is a {report.object_kind} object, not an annotated tag. A lightweight "
            f"tag carries no tagger, no date and no message, so the release has no record "
            f"of who cut it. Cut it with `git tag -a`."
        )

    # `{tag}^{commit}` peels an annotated tag to the commit it names; on a lightweight
    # tag it is the commit itself. One spelling covers both.
    commit = _git(root, "rev-parse", f"{tag}^{{commit}}")
    trunk_ref = _git(root, "rev-parse", "--verify", trunk)
    if commit.returncode != 0 or trunk_ref.returncode != 0:
        # The trunk does not exist here (a bare clone, a fresh worktree, a project whose
        # trunk is named something else). Nothing was measured, and that is reported as
        # such rather than as containment.
        return report

    contained = _git(root, "merge-base", "--is-ancestor",
                     commit.stdout.strip(), trunk_ref.stdout.strip())
    report.in_trunk = contained.returncode == 0
    if not report.in_trunk:
        report.problems.append(
            f"{tag} names a commit that is not contained in `{trunk}`. The release is "
            f"published against history nobody can check out of the trunk. Tag the merge "
            f"commit, after the merge (rules/cycle-release.md § Hard gates)."
        )
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_root(ap)
    ap.add_argument("--tag", required=True, help="the release tag to inspect, e.g. v1.2.0")
    ap.add_argument("--trunk", default="main", help="branch the tag must be contained in")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = check_tag_integrity(args.root, args.tag, args.trunk)
    code = report.exit_code()

    if args.json:
        print(json.dumps({
            "tag": report.tag, "trunk": report.trunk, "exists": report.exists,
            "annotated": report.annotated, "in_trunk": report.in_trunk,
            "problems": report.problems, "exit_code": code,
        }, indent=2))
        return code

    if not report.exists:
        print(f"UNCHECKED: no tag `{report.tag}` in {args.root}. An absent tag is not a "
              f"passing tag.", file=sys.stderr)
        return code
    if report.in_trunk is None:
        print(f"UNCHECKED: cannot resolve `{report.trunk}` in {args.root}, so containment "
              f"was not measured. Pass --trunk with the branch this project releases from.",
              file=sys.stderr)
        return code
    if report.problems:
        print(f"FAILS: {report.tag}")
        for problem in report.problems:
            print(f"  - {problem}")
        return code

    print(f"HOLDS: {report.tag} is an annotated tag contained in `{report.trunk}`.")
    print("  Signature is NOT checked: this kit cuts unsigned annotated tags, and a gate "
          "demanding what the procedure does not produce is unpassable by construction.")
    return code


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Can a rule be cited by something a rename cannot break?

    python3 mechanisms/gates/check_rule_identity.py
    python3 mechanisms/gates/check_rule_identity.py --root . --json

## The defect this exists to keep closed

A rule's only handle was its path. Measured 2026-09-21: **1209 citations** of the form
`rules/<name>.md` inside this kit, and on one consumer's registry 33 of 109 backlog items
citing a path in here — including items about that project's own product, an Error
boundary defect pointing at `rules/error-handling.md`. Of the 6 dead pointers a freshness
check found in that registry, **5 were paths that had moved**.

ESLint settled the shape and names the three reasons: portability across versions,
freedom to reorganise internals without breaking consumers, and one namespace for core
and plugin rules. This kit was the only thing in that consumer's registry asking to be
cited by filename — the independent auditor beside it cites `LCR0101`.

## What is checked

1. **Every rule declares an id.** A rule without one can only be cited by path.
2. **Ids are unique.** Two files claiming one id makes a citation ambiguous.
3. **Ids are never reused.** A retired id that reappears makes an old citation resolve to
   a rule it never meant — worse than not resolving.
4. **A retired rule names its successor.** ESLint's `replacedBy`: a 404 says something is
   wrong and nothing about where the thing went.
5. **Every id a document cites resolves.** The half that makes the index worth keeping.

## What is NOT checked, and why

That prose cites ids rather than paths. A path citation inside the kit is not wrong —
`rules/cycle-plan.md` in a sentence about that file is a file reference, and demanding an
id there would be the `check_prose_tests` defect in another costume. What matters is that
an id EXISTS for anything that needs a durable handle, and that every id written down
still resolves.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "rules.py").is_file():
        sys.path.insert(0, str(_up))
        break
from _contract import add_root  # noqa: E402 — sibling module, path set above

from squad.rules import ID_RE, catalogue  # noqa: E402 — post-bootstrap import

OK, FOUND, UNMEASURABLE = 0, 1, 2

#: An id written anywhere in the kit's own documents or code.
CITED_RE = re.compile(r"\bSQ-[A-Z]{2,4}-\d{2}\b")

#: Where a citation may legitimately appear without resolving: the module that DEFINES
#: the shape, and the tests that exercise it with invented ids.
_SHAPE_OWNERS = ("squad/rules.py", "mechanisms/gates/check_rule_identity.py")


@dataclass
class IdentityReport:
    rules: int = 0
    without_id: list[str] = field(default_factory=list)
    duplicate: list[str] = field(default_factory=list)
    retired_without_successor: list[str] = field(default_factory=list)
    unresolved_citations: list[str] = field(default_factory=list)
    swept: int = 0

    @property
    def problems(self) -> list[str]:
        out = []
        for name in self.without_id:
            out.append(f"{name} declares no rule-id, so it can only be cited by path")
        for line in self.duplicate:
            out.append(f"duplicate id: {line}")
        for rid in self.retired_without_successor:
            out.append(f"{rid} is retired and names no `replaced-by:` successor")
        for line in self.unresolved_citations:
            out.append(f"cites an id that resolves to nothing: {line}")
        return out

    def exit_code(self) -> int:
        if not self.rules:
            return UNMEASURABLE
        return FOUND if self.problems else OK


def _rule_files(root: Path) -> list[Path]:
    rules = root / "rules"
    if not rules.is_dir():
        rules = root / ".claude" / "rules"
    if not rules.is_dir():
        return []
    return sorted(p for p in rules.iterdir()
                  if p.suffix in (".md", ".txt") and p.name != "README.md")


def check_rule_identity(root: Path) -> IdentityReport:
    report = IdentityReport()
    index = catalogue(root)
    report.rules = len(index)
    if not index:
        return report

    known = {r.id for r in index}
    by_id: dict[str, list[str]] = {}
    for rule in index:
        by_id.setdefault(rule.id, []).append(rule.filename)
    report.duplicate = [f"{rid} -> {', '.join(names)}"
                        for rid, names in by_id.items() if len(names) > 1]
    report.retired_without_successor = [r.id for r in index if r.retired and not r.replaced_by]

    declared = {r.filename for r in index}
    report.without_id = [p.name for p in _rule_files(root) if p.name not in declared]

    # Every id written down must still resolve. This is the half that makes the index
    # load-bearing rather than decorative.
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".md", ".txt", ".py", ".sh") or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith((".git/", "node_modules/")) or "__pycache__" in rel:
            continue
        if rel in _SHAPE_OWNERS or "/tests/" in rel or rel.startswith("tests/"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        report.swept += 1
        for cited in sorted(set(CITED_RE.findall(text))):
            if cited not in known and ID_RE.fullmatch(cited):
                report.unresolved_citations.append(f"{rel}: {cited}")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_root(ap)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = check_rule_identity(Path(args.root))
    code = report.exit_code()

    if args.json:
        print(json.dumps({
            "rules": report.rules, "swept": report.swept,
            "problems": report.problems, "exit_code": code}, indent=2))
        return code

    if code == UNMEASURABLE:
        print("UNCHECKED: no rule declares an id, so there was nothing to verify. "
              "An empty index is not a clean one.", file=sys.stderr)
        return code
    if report.problems:
        print(f"FAILS: {len(report.problems)} problem(s) in {report.rules} rule(s)")
        for problem in report.problems:
            print(f"  - {problem}")
        return code

    print(f"HOLDS: {report.rules} rule(s) carry a stable id; every id cited across "
          f"{report.swept} file(s) resolves.")
    print("  A rename moves one line in the index, not the citations.")
    return code


if __name__ == "__main__":
    sys.exit(main())

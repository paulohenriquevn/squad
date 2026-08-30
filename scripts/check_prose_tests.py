#!/usr/bin/env python3
"""Find tests that pin the WORDING of prose the kit ships.

WHY
---
A test that greps a `SKILL.md` fails when someone improves the sentence and
passes when someone breaks the thing the sentence describes. `rules/prompt-text-
is-not-behaviour.md` carries the rule and where it came from; this is the
mechanism, because a rule with no mechanism is a note — a lesson this kit has
now paid for nine times in one day.

PRECISION OVER RECALL, DELIBERATELY
-----------------------------------
A checker that cries wolf is a checker somebody disables, and this kit measured
that outcome on `check_evidence_citations` in the same week. So the target of the
`in` must trace back, inside the SAME function, to text read from a shipped prose
file. Asserts over program output — `result.stdout`, a generated report, a parsed
settings dict — are behaviour and are not reported, even though they are also
string comparisons.

That leaves blind spots. A test that reads prose in a fixture at module scope and
asserts in a function is not seen. Naming that here is the point: the checker
reports what it can prove, and the rule covers the rest.

Usage:
    python3 check_prose_tests.py [root] [--json]

Exit codes:
    0 — nothing to report
    1 — at least one wording-pinning assert
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: A path that names prose the kit SHIPS for a human or an agent to read.
_PROSE_PATH = re.compile(
    r"SKILL\.md|\.prompt|HOW-TO-USE|CONTRIBUTING|golden-rule"
    r"|rules/|/roles/|/reference/"
)

#: `# prose-test: <reason>` on the assert line keeps it, the same shape
#: `english-only` uses. A bare marker with no reason does not count.
_EXEMPT = re.compile(r"#\s*prose-test:\s*\S+")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    function: str
    literal: str
    target: str


def _prose_bindings(fn: ast.FunctionDef) -> set[str]:
    """Names bound, inside this function, to the text of a shipped prose file."""
    names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name) or target.id in names:
                continue
            source = ast.unparse(node.value)
            if ".read_text(" not in source and ".read_bytes(" not in source:
                # Derived from an already-known prose variable (`.lower()`, a slice).
                if not any(re.search(rf"\b{re.escape(v)}\b", source) for v in names):
                    continue
            elif not _PROSE_PATH.search(source):
                continue
            names.add(target.id)
            changed = True
    return names


def check_prose_tests(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted({*root.glob("tests/**/*.py"), *root.glob("skills/*/tests/**/*.py")}):
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        lines = text.splitlines()
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            bound = _prose_bindings(fn)
            if not bound:
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assert):
                    continue
                test = node.test
                if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                    test = test.operand
                if not (isinstance(test, ast.Compare) and len(test.ops) == 1
                        and isinstance(test.ops[0], (ast.In, ast.NotIn))):
                    continue
                left, right = test.left, test.comparators[0]
                if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
                    continue
                if len(left.value) < 6:      # `"id"`, `"##"` — too short to be prose
                    continue
                rendered = ast.unparse(right)
                if not any(re.search(rf"\b{re.escape(v)}\b", rendered) for v in bound):
                    continue
                if node.lineno <= len(lines) and _EXEMPT.search(lines[node.lineno - 1]):
                    continue
                findings.append(Finding(
                    str(path.relative_to(root)), node.lineno, fn.name,
                    left.value[:70], rendered[:44]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings = check_prose_tests(args.root)

    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2, ensure_ascii=False))
        return 1 if findings else 0

    if not findings:
        print("no test pins the wording of shipped prose")
        return 0

    print(f"{len(findings)} assert(s) pin the wording of shipped prose, "
          f"in {len({f.path for f in findings})} file(s):\n")
    for f in findings:
        print(f"  {f.path}:{f.line}  ({f.function})")
        print(f'      "{f.literal}"  in  {f.target}')
    print("\nWording is not behaviour: this fails when the sentence improves and")
    print("passes when the thing it describes breaks. See")
    print("rules/prompt-text-is-not-behaviour.md — and read the section on what a")
    print("grep over a contract is a SYMPTOM of before deleting the assert.")
    print("\nTo keep one, say why on the line:")
    print("    assert \"...\" in text  # prose-test: the contract IS the subject here")
    return 1


if __name__ == "__main__":
    sys.exit(main())

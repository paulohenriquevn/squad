#!/usr/bin/env python3
"""A verdict a skill instructs is a verdict its cycle declares.

    python3 mechanisms/gates/check_emitted_verdicts.py [--root .] [--json]

## The mirror of check_orphan_verdicts.py

That sweep asks *every verdict a contract declares must be reachable by something*, and
was built after finding 15 declared verdicts no code could emit.

This asks the other direction, and the failure is louder. A skill instructing
`--verdict VISION_WRITTEN` against a contract declaring `PRODUCT_ALIGNED`,
`AWAITING_REVIEW`, `NEEDS_REVISION`, `INVALID` does not degrade: `cycle_events.py`
REFUSES, and the phase records nothing at all.

Measured 2026-09-10, closing a live `/brainstorm-vision` session: three of the four
cascade phases instruct an invented verdict. Only `brainstorm-pieces` names the
contract's own. So phases 1-3 of the one cycle a human attends emit no end event —
and `rules/cycle-maintenance.md` already names the cost: work left silent "is
indistinguishable from one nobody touched".

## Two silences, told apart

`declared_verdicts()` returns an empty set both when a rule has no `## Verdicts` section
and when the rule does not exist, and the runtime treats both as permission. That is
right for the first — `implement` and `code-quality` emit real verdicts from rules with
no such section, and refusing them would break honest emitters to catch a dishonest one.

It is wrong for the second. A skill naming `--cycle nosuch` names a contract that does
not exist, which no reader can check and no rule can constrain, so this gate separates
them where the runtime cannot afford to.

Exit codes:
  0  every instructed verdict is declared by its cycle
  1  at least one is not
  2  the tree could not be read; nothing was checked, and that is not a pass
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))

from cycle_events import declared_verdicts  # noqa: E402

CLEAN, UNDECLARED, UNCHECKED = 0, 1, 2

#: Prose an agent executes. Same scope as `check_prose_write_paths.py`, same reason.
SCANNED_DIRS: tuple[str, ...] = ("skills", "commands", "agents", "hooks")

#: `--cycle X ... --verdict Y`, tolerating a line break and the `\` of a wrapped shell
#: command between them — which is how three of the four cascade skills are written.
_CALL = re.compile(
    r"--cycle\s+([a-z][a-z0-9-]*)\b[^\n]*?(?:\\\s*\n[^\n]*?)?--verdict\s+(\{[^}]+\}|[A-Za-z_][A-Za-z0-9_]*)"
)

#: A skill may document an alternation; every branch has to be real.
_PLACEHOLDER = re.compile(r"^\{(.+)\}$")


def _branches(token: str) -> list[str]:
    match = _PLACEHOLDER.match(token)
    if not match:
        return [token]
    return [b.strip() for b in match.group(1).split("|") if b.strip()]


def _rule_exists(root: Path, cycle: str) -> bool:
    return any((root / base / f"cycle-{cycle}.md").is_file()
               for base in ("rules", ".claude/rules"))


def scan(root: Path | str) -> list[dict]:
    """Every instructed verdict its cycle does not declare."""
    base = Path(root)
    findings: list[dict] = []
    for name in SCANNED_DIRS:
        directory = base / name
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in _CALL.finditer(text):
                cycle, token = match.group(1), match.group(2)
                line = text.count("\n", 0, match.start()) + 1
                rel = str(path.relative_to(base))
                if not _rule_exists(base, cycle):
                    findings.append({"file": rel, "line": line, "cycle": cycle,
                                     "verdict": token, "reason": "no such cycle rule"})
                    continue
                declared = declared_verdicts(base, cycle)
                if not declared:
                    # The rule exists and declares none — permission, as at runtime.
                    continue
                for branch in _branches(token):
                    if branch not in declared:
                        findings.append({"file": rel, "line": line, "cycle": cycle,
                                         "verdict": branch,
                                         "reason": "not in the cycle's ## Verdicts",
                                         "declared": sorted(declared)})
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"UNCHECKED  {root} is not a directory", file=sys.stderr)
        return UNCHECKED

    swept = sum(1 for d in SCANNED_DIRS if (root / d).is_dir())
    findings = scan(root)
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings),
                          "dirs_swept": swept}, indent=2))
    elif not swept:
        where = ", ".join(f"{d}/" for d in SCANNED_DIRS)
        print(f"CLEAN  nothing swept: no {where} under {root}")
    elif findings:
        print(f"UNDECLARED  {len(findings)} instructed verdict(s) no cycle declares\n")
        for f in findings:
            print(f"  {f['file']}:{f['line']}  --verdict {f['verdict']}"
                  f"  (cycle-{f['cycle']}.md: {f['reason']})")
            if f.get("declared"):
                print(f"      declared: {', '.join(f['declared'])}")
        print("\n`cycle_events.py` REFUSES these, so the phase records nothing at all.")
    else:
        print(f"CLEAN  {swept} dir(s) swept; every instructed verdict is declared")
    return UNDECLARED if findings else CLEAN


if __name__ == "__main__":
    raise SystemExit(main())

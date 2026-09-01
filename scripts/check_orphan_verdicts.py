#!/usr/bin/env python3
"""Every verdict a contract declares must be reachable by something.

Sibling of `check_gate_mechanisms.py`, asking the complementary question. That sweep
reads `## Hard gates` and asks *does this line say what enforces it?*; this one reads
`## Verdicts` and asks *can anything actually emit this?*

WHY IT EXISTS
-------------
Measured on 2026-08-30 across the cycle rules: **48 verdicts declared, 15 appearing in
no `.py` and no `.js`.** Eight of those are legitimately emitted by an agent following
a skill — judgement, not computation — leaving **6 that appear in no code, no skill and
no command at all**. Four belong to `cycle-maintenance.md`, whose chain, ranking and
verdict table were fully specified and never implemented.

The same defect had just been fixed twice by hand, which is what prompted the sweep:

  `NEEDS_SPLIT`  in plan-alignment's verdict table, in zero code paths. An item
                 describing two subsystems came out as a generic `BLOCKED`, sending the
                 reviewer to close gaps that no rewrite can close.
  `planned`      in the backlog contract's status transitions, in zero items across
                 every install, because nothing wrote to `BACKLOG.md` at all.

Both were found by a person noticing. Neither was findable by any check, and
`cycle-maintenance.md` was invisible even to the gate sweep — that one reads
`## Hard gates`, and this rule has no such section.

WHAT IT PROVES, AND WHAT IT DOES NOT
------------------------------------
It proves the narrow thing a text scan can prove: the name appears somewhere that
could emit it. It does NOT prove the emitter is correct, reachable, or ever runs —
proving that a given `.py` emits a given verdict under the right condition is not
something a grep can do, and claiming otherwise would be the fabricated confidence
this ecosystem caps plans at 49 for.

DECLARING AN EXEMPTION
----------------------
A verdict emitted outside this repository — by a Codex judge, by a human, by a tool
the kit only reads — is not a defect. Say so on its table row:

    | `META_DEFECT_FOUND` | ... | _(emitted externally: the Codex judge writes it)_ |

The exemption must carry a reason, for the same purpose as its sibling's: a reader
deciding whether to trust the sweep needs to see what was set aside and why.

Exit codes: 0 every verdict is reachable or exempt · 1 at least one is orphaned
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: A verdict in a table cell. Four characters minimum keeps `PASS` and `OK` in and
#: single-letter column headers out.
_VERDICT_RE = re.compile(r"`([A-Z][A-Z0-9_]{3,})`")

#: The Verdicts section, ending at the next heading of the SAME level or higher —
#: not at any heading at all.
#:
#: It used to stop at `^#{1,6} `, so a subsection under Verdicts truncated it and the
#: sweep silently covered less. Measured on 2026-08-31: adding a `###` under
#: `cycle-maintenance.md`'s verdict table dropped the swept count from 51 to 49 with
#: no finding, no warning, and nothing in the output to notice. A coverage gate that
#: loses coverage without saying so is the failure it exists to prevent, one level up.
#:
#: `(?P=level)` requires the closing heading to be at least as shallow: `###` no
#: longer ends a `##` section, and `##` still does.
_SECTION_RE = re.compile(
    r"^(?P<level>#{2,})[^\n]*Verdicts?[^\n]*\n(.*?)(?=^(?P=level)(?!#) |\Z)",
    re.MULTILINE | re.DOTALL)

#: `_(emitted externally: reason)_` — the escape hatch, and it must carry a reason.
_EXEMPT_RE = re.compile(r"_\(\s*(?:emitted|verdict)[^:)]*:\s*([^)]+?)\s*\)_", re.IGNORECASE)

#: Words that are not verdicts even when they look like one in a table.
_NOT_VERDICTS = {"NNN", "TODO", "NOTE", "WARN", "JSON", "YAML", "HTTP", "HTML"}

CODE_GLOBS = ("scripts/*.py", "scripts/*.js", "skills/*/scripts/*.py", "skills/*/scripts/*.js")
DOC_GLOBS = ("skills/*/SKILL.md", "skills/*/*.md", "commands/*.md", "agents/*.md")


@dataclass
class VerdictFinding:
    rule: str
    verdict: str
    detail: str


@dataclass
class OrphanReport:
    rules_swept: int = 0
    total: int = 0
    by_code: int = 0
    by_agent: int = 0
    exempt: int = 0
    findings: list[VerdictFinding] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rules_swept": self.rules_swept,
            "total": self.total,
            "emitted_by_code": self.by_code,
            "emitted_by_agent": self.by_agent,
            "exempt": self.exempt,
            "findings": [f.__dict__ for f in self.findings],
        }


def _corpus(repo_root: Path, globs: tuple[str, ...]) -> str:
    """One string of everything that could emit a verdict.

    Concatenated rather than searched file by file because the question is only
    "does this name appear anywhere it could be emitted from", and one pass over
    the corpus answers it for every verdict at once.
    """
    out: list[str] = []
    for pattern in globs:
        for path in sorted(repo_root.glob(pattern)):
            try:
                out.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return "\n".join(out)


def _rows(section_body: str) -> list[str]:
    """Table rows and bullet lines, dropping separators and the header."""
    rows = []
    for line in section_body.splitlines():
        stripped = line.strip()
        if not stripped or set(stripped) <= set("|-: "):
            continue
        if stripped.startswith("|") and "Verdict" in stripped and "Meaning" in stripped:
            continue
        rows.append(stripped)
    return rows


def check_orphan_verdicts(repo_root: Path) -> OrphanReport:
    report = OrphanReport()
    code = _corpus(repo_root, CODE_GLOBS)
    docs = _corpus(repo_root, DOC_GLOBS)

    for rule in sorted((repo_root / "rules").glob("cycle-*.md")):
        body = rule.read_text(encoding="utf-8")
        section = _SECTION_RE.search(body)
        if not section:
            continue
        report.rules_swept += 1

        for row in _rows(section.group(2)):
            names = [n for n in _VERDICT_RE.findall(row) if n not in _NOT_VERDICTS]
            if not names:
                continue
            # The first name on the row is the verdict; later ones are cross-references
            # to other verdicts inside the Meaning column.
            verdict = names[0]
            report.total += 1

            if _EXEMPT_RE.search(row):
                report.exempt += 1
            elif verdict in code:
                report.by_code += 1
            elif verdict in docs:
                report.by_agent += 1
            else:
                report.findings.append(VerdictFinding(
                    rule=rule.name, verdict=verdict,
                    detail="declared here and named in no script, no skill and no command"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = check_orphan_verdicts(args.repo_root)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
        return 1 if report.findings else 0

    print(f"swept {report.rules_swept} cycle rule(s): {report.total} verdict(s) — "
          f"{report.by_code} emitted by code, {report.by_agent} by an agent, "
          f"{report.exempt} declared exempt, {len(report.findings)} orphaned")

    for finding in report.findings:
        print(f"  [orphan] {finding.rule}: {finding.verdict}")
        print(f"      {finding.detail}")

    if report.findings:
        print("\nA verdict nothing can emit is a promise the contract cannot keep. "
              "Implement it, or declare the exemption with a reason: "
              "`_(emitted externally: <reason>)_`.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

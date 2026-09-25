#!/usr/bin/env python3
"""Findings that vanished or were downgraded between two reviews of one slug.

WHY THIS EXISTS
---------------
`consolidate_findings.py` scores from OPEN findings. A re-review that deletes a
finding, or lowers a BLOCKER to MEDIUM, therefore passes — and until now the only
thing standing against either was a sentence in `skills/review/SKILL.md`, guarded
by a test asserting `"delete" in text`.

A grep over a contract is not a guard: a synonym defeats it, an unrelated
occurrence satisfies it. `skills/_kit-rules/prompt-text-is-not-behaviour.md` names that shape
and says what to do about it — mechanise the guarantee, or admit it is prose.
This is the mechanised half.

WHAT IT REFUSES TO DECIDE
-------------------------
An honest re-scope and a quiet deletion look identical on disk. This reports the
disappearance and names the ambiguity; it does not rule on intent. Claiming
otherwise would be the fabricated precision this kit refuses elsewhere.

Usage:
    python3 check_finding_continuity.py <project-root> <slug> [--json]

Exit codes:
    0 — nothing to report, or fewer than two reviews to compare
    1 — a finding vanished or was downgraded
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from dataclasses import dataclass, field
from pathlib import Path, Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import (  # noqa: E402 — post-bootstrap import
    DATA_DIRNAME,
    LEGACY_RECORDS_ROOTS,
)

#: `### F-arch-1: the shard client leaks its cursor`
_FINDING_RE = re.compile(r"^###\s+([A-Za-z][\w-]*-\d+)\s*:?(.*)$", re.MULTILINE)
#: `## BLOCKER findings (1)`
_SECTION_RE = re.compile(r"^##\s+(BLOCKER|HIGH|MEDIUM|LOW|INFO)\b", re.MULTILINE)
_CLOSED_RE = re.compile(r"status:\s*CLOSED", re.IGNORECASE)

_ORDER = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]

#: Both layouts, plus the knowledge-base convention one consumer declares.
_ROOTS = tuple(
    tuple(r.split("/")) for r in (f"{DATA_DIRNAME}/records", *LEGACY_RECORDS_ROOTS)
)


@dataclass(frozen=True)
class ContinuityReport:
    compared: bool
    earlier: str | None = None
    later: str | None = None
    vanished: tuple[str, ...] = ()
    downgraded: tuple[str, ...] = ()
    judgement: tuple[str, ...] = field(default=(
        "whether a disappearance was an honest re-scope or a quiet deletion",
        "whether a lowered severity reflects new evidence or a cheaper verdict",
    ))

    @property
    def is_clean(self) -> bool:
        return not (self.vanished or self.downgraded)


def _reviews(project_root: Path, slug: str) -> list[Path]:
    for parts in _ROOTS:
        d = project_root.joinpath(*parts, "reviews")
        if d.is_dir():
            found = sorted(d.glob(f"{slug}-review-*.md"))
            if found:
                return found
    return []


def _findings(text: str) -> dict[str, tuple[str, bool]]:
    """`id -> (severity, closed)`, severity taken from the section it sits under."""
    out: dict[str, tuple[str, bool]] = {}
    sections = [(m.start(), m.group(1)) for m in _SECTION_RE.finditer(text)]
    for m in _FINDING_RE.finditer(text):
        severity = "INFO"
        for pos, name in sections:
            if pos < m.start():
                severity = name
        out[m.group(1)] = (severity, bool(_CLOSED_RE.search(m.group(0))))
    return out


def check_finding_continuity(project_root: Path, slug: str) -> ContinuityReport:
    reports = _reviews(Path(project_root), slug)
    if len(reports) < 2:
        # One report is not a trend. Saying "clean" would claim a comparison that
        # never happened — the same shape as a gate reporting SKIP as PASS.
        return ContinuityReport(compared=False)

    earlier, later = reports[-2], reports[-1]
    before = _findings(earlier.read_text(encoding="utf-8"))
    after = _findings(later.read_text(encoding="utf-8"))

    vanished, downgraded = [], []
    for fid, (severity, closed) in before.items():
        if closed:
            continue
        if fid not in after:
            vanished.append(fid)
            continue
        new_severity, _ = after[fid]
        if _ORDER.index(new_severity) > _ORDER.index(severity):
            downgraded.append(f"{fid}: {severity} -> {new_severity}")

    return ContinuityReport(
        compared=True, earlier=earlier.name, later=later.name,
        vanished=tuple(sorted(vanished)), downgraded=tuple(sorted(downgraded)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("slug")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = check_finding_continuity(args.project_root, args.slug)

    if args.json:
        print(json.dumps({
            "compared": report.compared, "earlier": report.earlier,
            "later": report.later, "vanished": list(report.vanished),
            "downgraded": list(report.downgraded),
            "judgement_items": list(report.judgement),
        }, indent=2))
        return 0 if report.is_clean else 1

    if not report.compared:
        print(f"only one review for `{args.slug}` — nothing to compare, "
              f"which is not the same as nothing wrong")
        return 0
    print(f"comparing {report.earlier} -> {report.later}")
    if report.is_clean:
        print("  every open finding is still present or explicitly CLOSED")
        return 0
    for fid in report.vanished:
        print(f"  VANISHED    {fid} — open in the earlier review, absent and not CLOSED")
    for d in report.downgraded:
        print(f"  DOWNGRADED  {d}")
    print("\nNot decided here, and yours to judge:")
    for item in report.judgement:
        print(f"  - {item}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The inventory in `mechanisms/README.md`, confronted with the directory.

    python3 mechanisms/gates/check_mechanisms_inventory.py
    python3 mechanisms/gates/check_mechanisms_inventory.py --json

The README this replaces declared, in its own words, *"Every new script in this
directory MUST be added to the inventory above"* — and listed 5 of 36 files. The
rule was real and nothing computed it, so the inventory decayed to a sample while
still reading as a list. That is the shape this kit refuses everywhere else: a
contract asserting what no mechanism checks.

Three things can be wrong, and each is reported separately because the fix
differs:

  `undocumented`  a file on disk with no row. The reader cannot learn what it is.
  `phantom`       a row with no file. The reader is sent to something gone.
  `misfiled`      a file listed under a family it does not live in. Worse than
                  either: the row is present and wrong, so the reader trusts it.

Absence of a README is `INVENTORY_UNREADABLE`, never a pass — a missing contract
does not mean the directory is fine, it means nothing was checked.

Exit codes:
    0 — INVENTORY_MATCHES
    1 — INVENTORY_DRIFTED
    2 — INVENTORY_UNREADABLE
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

MATCHES = "INVENTORY_MATCHES"
DRIFTED = "INVENTORY_DRIFTED"
UNREADABLE = "INVENTORY_UNREADABLE"

#: The families, in the order the README presents them. A directory outside this
#: tuple is reported rather than ignored: a sixth family nobody documented is the
#: same defect as an undocumented file, one level up.
FAMILIES = ("gates", "cycle", "fleet", "dist", "conventions")

#: `### \`gates/\` — measurement`
_SECTION_RE = re.compile(r"^###\s+`([a-z]+)/`", re.MULTILINE)
#: `| \`check_xrefs.py\` | Cross-reference validator … |`
_ROW_RE = re.compile(r"^\|\s*`([A-Za-z0-9_.-]+\.(?:py|sh|js))`\s*\|", re.MULTILINE)


@dataclass
class InventoryReport:
    verdict: str = UNREADABLE
    undocumented: list[str] = field(default_factory=list)
    phantom: list[str] = field(default_factory=list)
    misfiled: list[str] = field(default_factory=list)
    undeclared_families: list[str] = field(default_factory=list)
    documented_count: int = 0
    detail: str = ""


def parse_inventory(readme_text: str) -> dict[str, str]:
    """Map filename -> the family whose section lists it.

    Sections are read by heading, so a row's family comes from where it sits
    rather than from anything the row says. A file listed twice under different
    headings keeps the last, and the disk comparison then reports it misfiled
    against one of them — which is the honest outcome for a duplicated row.
    """
    listed: dict[str, str] = {}
    sections = list(_SECTION_RE.finditer(readme_text))
    for i, match in enumerate(sections):
        family = match.group(1)
        end = sections[i + 1].start() if i + 1 < len(sections) else len(readme_text)
        for row in _ROW_RE.finditer(readme_text[match.end():end]):
            listed[row.group(1)] = family
    return listed


def check(root: Path) -> InventoryReport:
    report = InventoryReport()
    mechanisms = Path(root) / "mechanisms"
    readme = mechanisms / "README.md"
    if not readme.is_file():
        report.detail = f"no {readme} — the inventory that would say what is here is absent"
        return report

    listed = parse_inventory(readme.read_text(encoding="utf-8", errors="replace"))
    if not listed:
        report.detail = ("`mechanisms/README.md` has no inventory rows this parser can read. "
                         "Reporting a match here would be reporting on nothing")
        return report
    report.documented_count = len(listed)

    on_disk: dict[str, str] = {}
    for child in sorted(mechanisms.iterdir()):
        if not child.is_dir() or child.name == "__pycache__":
            continue
        if child.name not in FAMILIES:
            report.undeclared_families.append(child.name)
            continue
        for f in sorted(child.iterdir()):
            if f.is_file() and f.suffix in (".py", ".sh", ".js"):
                on_disk[f.name] = child.name

    report.undocumented = sorted(f"{fam}/{n}" for n, fam in on_disk.items() if n not in listed)
    report.phantom = sorted(f"{fam}/{n}" for n, fam in listed.items() if n not in on_disk)
    report.misfiled = sorted(
        f"{n}: listed under `{listed[n]}/`, lives in `{on_disk[n]}/`"
        for n in on_disk if n in listed and listed[n] != on_disk[n])

    drift = (report.undocumented + report.phantom + report.misfiled
             + report.undeclared_families)
    report.verdict = DRIFTED if drift else MATCHES
    report.detail = (f"{len(on_disk)} file(s) on disk, {len(listed)} documented"
                     if not drift else f"{len(drift)} disagreement(s)")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = check(args.root)
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"mechanisms inventory — {args.root}")
        print(f"  verdict: {report.verdict}")
        for name, rows in (("undocumented", report.undocumented),
                           ("phantom", report.phantom),
                           ("misfiled", report.misfiled),
                           ("undeclared family", report.undeclared_families)):
            for row in rows:
                print(f"  [{name}] {row}")
        print(f"  {report.detail}")

    return {MATCHES: 0, DRIFTED: 1}.get(report.verdict, 2)


if __name__ == "__main__":
    raise SystemExit(main())

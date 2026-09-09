"""The gate that makes `mechanisms/README.md` a computed claim.

The README this directory replaced said, in its own words, *"Every new script in
this directory MUST be added to the inventory above"* — and inventoried 5 of 36
files. The rule was real, nothing computed it, and the list decayed to a sample
while still reading as complete. That is the defect this kit refuses everywhere
else, sitting in the directory that holds the refusing.

The three drift kinds are separate findings because the fix differs: an
undocumented file needs a row, a phantom row needs deleting, and a misfiled row
is the dangerous one — present, and wrong, so the reader trusts it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "gates"))

from check_mechanisms_inventory import (
    DRIFTED,
    MATCHES,
    UNREADABLE,
    check,
    parse_inventory,
)

_REPO = Path(__file__).resolve().parents[1]

_README = """# mechanisms/

### `gates/` — measurement

| File | Purpose |
|---|---|
| `check_thing.py` | does a thing |

### `conventions/` — where things live

| File | Purpose |
|---|---|
| `helper.py` | helps |
"""


def _kit(root: Path, readme: str | None = _README,
         disk: dict[str, list[str]] | None = None) -> Path:
    m = root / "mechanisms"
    m.mkdir(parents=True, exist_ok=True)
    if readme is not None:
        (m / "README.md").write_text(readme, encoding="utf-8")
    for family, files in (disk or {"gates": ["check_thing.py"], "conventions": ["helper.py"]}).items():
        (m / family).mkdir(exist_ok=True)
        for f in files:
            (m / family / f).write_text("# x\n", encoding="utf-8")
    return root


def test_the_kit_own_inventory_matches() -> None:
    """The gate's first duty is to hold for the repository that ships it."""
    report = check(_REPO)
    assert report.verdict == MATCHES, (
        f"undocumented={report.undocumented} phantom={report.phantom} "
        f"misfiled={report.misfiled} families={report.undeclared_families}")
    assert report.documented_count >= 30, "a shrunken inventory would pass vacuously"


def test_a_file_with_no_row_is_named(tmp_path: Path) -> None:
    _kit(tmp_path, disk={"gates": ["check_thing.py", "check_new.py"], "conventions": ["helper.py"]})

    report = check(tmp_path)

    assert report.verdict == DRIFTED
    assert report.undocumented == ["gates/check_new.py"]


def test_a_row_with_no_file_is_named(tmp_path: Path) -> None:
    _kit(tmp_path, disk={"gates": ["check_thing.py"], "conventions": []})

    report = check(tmp_path)

    assert report.verdict == DRIFTED
    assert report.phantom == ["conventions/helper.py"]


def test_a_file_listed_under_the_wrong_family_is_named(tmp_path: Path) -> None:
    """The dangerous one: the row exists, so nothing looks missing."""
    _kit(tmp_path, disk={"gates": ["check_thing.py", "helper.py"], "conventions": []})

    report = check(tmp_path)

    assert report.verdict == DRIFTED
    assert report.misfiled == ["helper.py: listed under `conventions/`, lives in `gates/`"]
    assert report.undocumented == [], "it is documented — just in the wrong place"


def test_an_undeclared_family_is_reported(tmp_path: Path) -> None:
    """A sixth directory nobody documented is an undocumented file one level up."""
    _kit(tmp_path, disk={"gates": ["check_thing.py"], "conventions": ["helper.py"],
                         "experiments": ["x.py"]})

    report = check(tmp_path)

    assert report.verdict == DRIFTED
    assert report.undeclared_families == ["experiments"]


def test_a_missing_readme_is_unreadable_not_a_pass(tmp_path: Path) -> None:
    """Absence of the contract means nothing was checked, not that all is well."""
    _kit(tmp_path, readme=None)

    report = check(tmp_path)

    assert report.verdict == UNREADABLE
    assert report.undocumented == [], "it did not measure, so it reports no findings"


def test_a_readme_with_no_parseable_rows_is_unreadable(tmp_path: Path) -> None:
    """The empty-inventory trap: zero rows vs zero disagreements look identical."""
    _kit(tmp_path, readme="# mechanisms/\n\nNo tables here.\n")

    report = check(tmp_path)

    assert report.verdict == UNREADABLE
    assert "on nothing" in report.detail


def test_a_row_belongs_to_the_heading_above_it() -> None:
    """Family comes from the section, not from anything the row says."""
    listed = parse_inventory(_README)

    assert listed == {"check_thing.py": "gates", "helper.py": "conventions"}

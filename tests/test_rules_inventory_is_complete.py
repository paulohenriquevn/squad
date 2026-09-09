"""The inventory omitted fifteen of the fifty-one files it inventories.

Sibling of `test_check_xrefs_bare_rule_names.py`, guarding the same document against
the opposite failure. That one asks *does every name in the tables exist?* — the
misdirection fixed on 2026-09-07, when four rows named files that had moved or never
existed. This one asks *does every file appear in the tables?*, because a half-correct
inventory is how the first defect was born: the CHANGELOG records a table trimmed while
the prose describing it was not.

Measured 2026-09-07, immediately after the four rows were repaired: 15 of 51 files in
`rules/` appeared in no table. `cycle-brainstorm.md` was among them — a full cycle
contract missing from a table that purports to list the cycle contracts — along with
`squad-map.md`, the 360º view the kit points readers at, and `autonomy-envelope.md`,
which two cycle rules cite as the authority for what runs unattended.

An omission reads differently from a dangling row and is worse in one specific way: a
reader who checks the inventory and does not find `decision-delegation.txt` concludes
the kit has no such rule, rather than that the list is short.

NO EXEMPTIONS, DELIBERATELY
---------------------------
Every file directly under `rules/` is something a reader may have to find, so there is
no category that earns silence. `templates/` is a directory and belongs to the
installer, which the ownership table above the inventory already explains.
"""
from __future__ import annotations

import re
from pathlib import Path

_RULES = Path(__file__).resolve().parent.parent / "rules"
_README = _RULES / "README.md"

#: A filename in a table cell, with or without the `skills/_kit-rules/` prefix that
#: marks a rule living outside this directory.
_LISTED_RE = re.compile(r"`(?:[a-z_/-]+/)?([a-z0-9][a-z0-9._-]*\.(?:md|txt))`")


def _listed() -> set[str]:
    return set(_LISTED_RE.findall(_README.read_text(encoding="utf-8-sig")))


def _on_disk() -> set[str]:
    return {p.name for p in _RULES.iterdir() if p.is_file()} - {"README.md"}


def test_the_directory_is_not_empty() -> None:
    """Vacuity is a failure: an empty directory would make every assertion below pass."""
    assert len(_on_disk()) > 40


def test_every_rule_on_disk_appears_in_the_inventory() -> None:
    missing = sorted(_on_disk() - _listed())
    assert missing == [], (
        f"{len(missing)} file(s) in rules/ appear in no table of rules/README.md, so a "
        f"reader consulting the inventory would conclude they do not exist: {missing}"
    )

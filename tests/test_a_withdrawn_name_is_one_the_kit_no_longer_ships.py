"""An entry in the withdrawals list must name something this kit does not ship.

`mechanisms/distribution/withdrawn.txt` is the only list `install.sh` may remove BY, and it
removes by name. That makes a wrong entry the most expensive line in the kit: naming a
skill that still ships would delete a live skill from every consumer that upgrades with
`--remove-withdrawn`.

So the list is checked against the tree it travels with, on every run. A withdrawal that
gets un-withdrawn — a name reinstated upstream — fails here rather than in someone's
install.

The declared successor is checked too. A successor that does not exist is a withdrawal
pointing nowhere, which is worse than no successor at all: a reader follows it and finds
nothing, and the entry says `none` precisely so that "no replacement" can be stated rather
than implied by an empty field.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_LIST = _ROOT / "mechanisms" / "distribution" / "withdrawn.txt"


def _entries() -> list[tuple[str, str, str, str]]:
    rows = []
    for line in _LIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        assert len(parts) == 4, f"four fields expected, got {len(parts)}: {line}"
        rows.append(tuple(parts))
    return rows


def test_the_list_is_not_empty() -> None:
    """Without this, every test below passes over zero rows and proves nothing."""
    assert _entries(), "withdrawn.txt parsed to no entries; this test lost its subject"


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e[0])
def test_a_withdrawn_path_is_absent_from_this_kit(entry: tuple[str, str, str, str]) -> None:
    """The safety invariant. A live name here deletes a live skill in every consumer."""
    path, _when, _successor, _record = entry
    assert not (_ROOT / path).exists(), (
        f"{path} is declared WITHDRAWN and this kit still ships it. Remove the entry, or "
        f"remove the directory — `install.sh --remove-withdrawn` deletes by this name.")


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e[0])
def test_a_declared_successor_exists(entry: tuple[str, str, str, str]) -> None:
    path, _when, successor, _record = entry
    if successor == "none":
        return
    assert (_ROOT / "skills" / successor).exists(), (
        f"{path} names successor `{successor}`, which this kit does not ship. A withdrawal "
        f"pointing nowhere sends a reader to a dead end; write `none` if there is no "
        f"replacement.")


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e[0])
def test_the_record_that_says_so_exists(entry: tuple[str, str, str, str]) -> None:
    """The fourth field is where a person checks the claim. It must resolve."""
    path, _when, _successor, record = entry
    assert (_ROOT / record).exists(), (
        f"{path} cites `{record}` as the record of its withdrawal, and that file is not "
        f"here. A citation nobody can follow is the defect this kit records as a fabricated "
        f"reference.")

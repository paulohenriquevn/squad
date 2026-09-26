"""An entry in the withdrawals list must name something this kit does not ship.

`mechanisms/distribution/withdrawn.txt` is the only list `install.sh` may remove BY, and it
removes by name. That makes a wrong entry the most expensive line in the kit: naming a
skill that still ships would delete a live skill from every consumer that upgrades with
`--remove-withdrawn`.

So the list is checked against the tree it travels with, on every run. A withdrawal that
gets un-withdrawn — a name reinstated upstream — fails here rather than in someone's
install.

The list is also checked against the kit's HISTORY. It was first written from memory, and
memory named eight skills when `git log` shows the kit shipped and withdrew twenty-seven
skills and eighteen top-level rule files. A consumer holding one of the unlisted ones
was told nothing, and a stale `rules/cycle-auto-plan.md` kept loading into its sessions
beside the `cycle-release.md` that contradicts it. Measured on a consumer 2026-09-23. So
every path the history says was deleted or renamed away, and that the kit does not ship
now, must be on the list or on `_NOT_A_WITHDRAWAL` below with the reason it is not.

The declared successor is checked too. A successor that does not exist is a withdrawal
pointing nowhere, which is worse than no successor at all: a reader follows it and finds
nothing, and the entry says `none` precisely so that "no replacement" can be stated rather
than implied by an empty field.
"""
from __future__ import annotations

import subprocess
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
    """A skill's successor is a skill name; a rule's is the kit path it moved to."""
    path, _when, successor, _record = entry
    if successor == "none":
        return
    target = _ROOT / successor if "/" in successor else _ROOT / "skills" / successor
    assert target.exists(), (
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


#: Paths the history shows leaving the kit that are NOT withdrawals, each with the reason.
#: An entry here is a decision somebody can disagree with; silence would not be.
_NOT_A_WITHDRAWAL: dict[str, str] = {
    # The derived routing table. The kit stopped carrying a placeholder for it in
    # 67ec406, but a consumer's `.claude/rules/domain-routing.txt` is where installs
    # before the write root kept the table the PROJECT derived, and
    # `squad.paths.routing_table` still reads it there (`LEGACY_ROUTING_ROOTS`). Listing
    # it would offer `--remove-withdrawn` the project's own routing.
    "rules/domain-routing.txt": "the project's derived routing table, still read",
    # Renamed to `issue-confidence` in 0214582. `file-issue` is also the name of a
    # personal skill outside this kit, so a project holding one cannot be presumed to
    # hold the kit's; the list removes by name, and a collision would delete the other.
    "skills/file-issue": "name shared with a skill this kit never shipped",
}


def _left_the_kit() -> set[str]:
    """Every `skills/<name>` and top-level `rules/<file>` git saw deleted or renamed
    away, reduced to the ones this kit does not ship now."""
    out = subprocess.run(
        ["git", "-C", str(_ROOT), "log", "--all", "--diff-filter=DR", "--name-status",
         "--format=", "--", "skills/*", "rules/*"],
        capture_output=True, text=True, check=True)
    gone: set[str] = set()
    for line in out.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        parts = fields[1].split("/")
        if parts[0] == "skills" and len(parts) >= 3:
            candidate = f"skills/{parts[1]}"
        elif parts[0] == "rules" and len(parts) == 2:
            candidate = fields[1]
        else:
            continue
        if not (_ROOT / candidate).exists():
            gone.add(candidate)
    return gone


def test_the_history_is_the_floor_the_measurement_stands_on() -> None:
    """Without this, the completeness test below passes over an empty history."""
    assert "rules/cycle-auto-plan.md" in _left_the_kit()


def test_everything_the_kit_withdrew_is_declared() -> None:
    declared = {path for path, *_ in _entries()}

    undeclared = sorted(_left_the_kit() - declared - set(_NOT_A_WITHDRAWAL))

    assert not undeclared, (
        f"{len(undeclared)} path(s) this kit shipped and no longer ships are on neither "
        f"withdrawn.txt nor _NOT_A_WITHDRAWAL: {undeclared}. A consumer holding one is told "
        f"nothing, and the installer calls it the project's.")


def test_an_exception_is_not_also_a_withdrawal() -> None:
    declared = {path for path, *_ in _entries()}

    assert not declared & set(_NOT_A_WITHDRAWAL)

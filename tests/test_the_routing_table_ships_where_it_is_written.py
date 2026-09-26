r"""The kit stops shipping a table to a directory nothing writes to.

`squad.paths.write_routing_table` has resolved the routing table to the project's write
root since 2026-09-11. The installer did not follow: it copied a placeholder to
`rules/domain-routing.txt` and created nothing under the write root, so a fresh consumer
received the table in the one place no writer would ever fill.

The cost is not theoretical, and it was routed here by the consumer that paid it:

  - `install.sh` copies `rules/*` whole, so **every install recreated the legacy file** —
    three weeks after the destination moved;
  - 21 files in this kit still named the old path, four of them documents, so removing
    the copy failed `rules_reference_resolves` four times. The file could not stop
    travelling while the documents demanded it.

`B-198`'s own comment in `install.sh` names the end state this reaches: *"a reinstall
then recreated the legacy path in a project that had already migrated, and while both
files exist the routing is silently correct — `.squad/` is read first — so nothing
reports the copy that will be read the day the newer one is removed."*

WHAT IS NOT CHANGED. `squad.paths.routing_table` still READS the pre-move locations. An
install made before the move keeps its table where it is, and nothing here deletes a
consumer's file. Shipping to a dead path and reading from a former one are different
acts: the first is the kit being wrong, the second is the kit not stranding anyone.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from squad.paths import ROUTING_TABLE, routing_table, write_routing_table  # noqa: E402


@pytest.fixture(scope="module")
def installed(tmp_path_factory) -> Path:
    target = tmp_path_factory.mktemp("consumer")
    subprocess.run(["git", "init", "-q", "."], cwd=target, check=True)
    done = subprocess.run(
        ["bash", str(REPO / "mechanisms" / "distribution" / "install.sh"), str(target)],
        capture_output=True, text=True, timeout=600, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    return target


def test_the_kit_no_longer_carries_a_table_under_rules() -> None:
    """A placeholder in a directory nothing writes to is the copy B-198 named."""
    assert not (REPO / "rules" / ROUTING_TABLE).exists()


def test_a_fresh_install_gets_the_table_where_it_is_written(installed: Path) -> None:
    assert write_routing_table(installed).is_file(), (
        "the consumer received no routing table at the destination its own writer uses"
    )


def test_a_fresh_install_does_not_get_the_legacy_copy(installed: Path) -> None:
    assert not (installed / ".claude" / "rules" / ROUTING_TABLE).exists()


def test_the_reader_still_finds_a_pre_move_table(tmp_path: Path) -> None:
    """Nobody is stranded: an old install keeps its table and it is still read."""
    legacy = tmp_path / ".claude" / "rules"
    legacy.mkdir(parents=True)
    (legacy / ROUTING_TABLE).write_text("# an older install's table\n", encoding="utf-8")

    assert routing_table(tmp_path) == legacy / ROUTING_TABLE


def test_the_write_root_wins_over_a_pre_move_copy(tmp_path: Path) -> None:
    """While both exist the newer one is authoritative — and that is exactly the state
    B-198 called silently correct, which is why the kit must stop creating it."""
    legacy = tmp_path / ".claude" / "rules"
    legacy.mkdir(parents=True)
    (legacy / ROUTING_TABLE).write_text("# old\n", encoding="utf-8")
    current = write_routing_table(tmp_path)
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text("# current\n", encoding="utf-8")

    assert routing_table(tmp_path) == current

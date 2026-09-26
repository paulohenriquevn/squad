"""Reporting the data a project has not moved into `<project>/.squad/` yet.

The companion to `check_write_containment.py`, and it answers the other half:
containment proves no MODULE can spell another root, this proves no DATA is sitting in
one. Both are needed — an owner that is itself wrong passes the first and fails this.

`SPLIT` is the state to be loudest about. Once the write root has content and a legacy
root still does, a reader resolving the first never sees the second: the older copy is
unreachable rather than merely old, and it looks current.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))
sys.path.insert(0, str(_REPO))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_data_root import check_project  # noqa: E402 — post-bootstrap import

from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import


def _states(root: Path) -> dict[str, str]:
    return {r.relative: r.state for r in check_project(root)}


def _file(directory: Path, name: str = "a.md") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("x\n", encoding="utf-8")


def test_an_empty_project_has_nothing_to_migrate(tmp_path: Path) -> None:
    assert _states(tmp_path) == {".squad": "EMPTY"}


def test_a_project_writing_only_to_the_root_is_centralised(tmp_path: Path) -> None:
    _file(write_records_dir(tmp_path, "plans"))

    assert _states(tmp_path) == {".squad": "CENTRALISED"}


def test_a_legacy_root_alone_is_unmigrated(tmp_path: Path) -> None:
    """Readers still fall back to it, and nothing else says so."""
    _file(tmp_path / ".claude" / "records" / "plans")

    assert _states(tmp_path)[".claude/records"] == "UNMIGRATED"


def test_both_roots_holding_data_is_split(tmp_path: Path) -> None:
    """The loudest state: the old copy is unreachable and looks current."""
    _file(write_records_dir(tmp_path, "plans"))
    _file(tmp_path / ".claude" / "records" / "plans")

    report = {r.relative: r for r in check_project(tmp_path)}
    assert report[".claude/records"].state == "SPLIT"
    assert "unreachable" in report[".claude/records"].detail


def test_the_legacy_session_state_is_reported_too(tmp_path: Path) -> None:
    """`session-state/` and `.attestations/` sat beside the installed kit. Policing
    only the trail and the bundle left them outside the guarantee."""
    _file(tmp_path / "session-state", "b-1-progress.md")

    assert _states(tmp_path)["session-state"] == "UNMIGRATED"


def test_a_scaffold_nobody_filled_is_not_data(tmp_path: Path) -> None:
    """An empty directory carrying only `.gitkeep` is a scaffold, and reporting it
    would send somebody to migrate nothing."""
    legacy = tmp_path / "records" / "plans"
    legacy.mkdir(parents=True)
    (legacy / ".gitkeep").write_text("", encoding="utf-8")

    assert _states(tmp_path) == {".squad": "EMPTY"}


def test_the_bundle_counts_as_data(tmp_path: Path) -> None:
    _file(tmp_path / "wiki" / "decisions")

    assert _states(tmp_path)["wiki"] == "UNMIGRATED"


def test_this_repository_follows_the_rule_it_enforces(tmp_path: Path) -> None:
    """A rule the kit does not follow is a rule its consumers read as optional.

    Its own bundle lived at `<repo>/wiki/` and its event stream at
    `.claude/records/`; both moved when the write root was declared.
    """
    stale = [r for r in check_project(_REPO) if r.state in ("UNMIGRATED", "SPLIT")]

    assert not stale, [f"{r.state} {r.relative} ({r.files} files)" for r in stale]


def test_data_written_inside_the_installed_kit_is_seen(tmp_path: Path) -> None:
    """The one path a kit script was actively writing to was the one this gate could not
    see.

    Measured on a consumer 2026-09-16: `convene_panel.py` resolved its project as
    `parents[2]`, which is `.claude/` in a plugin install, and `write_records_dir`
    produced `.claude/.squad/records/panels/` — six files, two of them discover
    assignments no later run regenerates. This gate reported SPLIT for two other paths and
    said nothing about that one.

    It gets its own state because it is worse than SPLIT: `.claude/` is gitignored AND
    replaced wholesale by the installer, so the records reach nobody and are scheduled for
    deletion, while a reader resolving the write root reports absence.
    """
    (tmp_path / ".squad" / "records").mkdir(parents=True)
    (tmp_path / ".squad" / "records" / "live.md").write_text("here\n", encoding="utf-8")
    stranded = tmp_path / ".claude" / ".squad" / "records" / "panels"
    stranded.mkdir(parents=True)
    (stranded / "B-001-plan.md").write_text("stranded\n", encoding="utf-8")

    states = {r.relative: r.state for r in check_project(tmp_path)}
    assert states.get(".claude/.squad") == "INSIDE_KIT", states



def test_a_write_root_nested_inside_the_write_root_is_seen(tmp_path: Path) -> None:
    """No migration produces `.squad/.squad/`; only a writer that took the write root for
    a project does. SPLIT compares the write root with roots BESIDE it, so a copy INSIDE
    it was invisible here — measured on a consumer 2026-09-25 with 39 events in the
    nested stream and nothing reporting them.
    """
    _file(write_records_dir(tmp_path, "plans"))
    _file(tmp_path / ".squad" / ".squad" / "records", "cycle-events.jsonl")

    assert _states(tmp_path).get(".squad/.squad") == "NESTED"


def test_a_clean_project_does_not_gain_the_new_state(tmp_path: Path) -> None:
    """Widening a scan must not invent findings. A kit tree with no data under it is the
    normal case and stays silent."""
    (tmp_path / ".squad" / "records").mkdir(parents=True)
    (tmp_path / ".squad" / "records" / "live.md").write_text("here\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "x.md").write_text("a skill\n", encoding="utf-8")

    assert not any(r.state == "INSIDE_KIT" for r in check_project(tmp_path))


@pytest.mark.parametrize("state_maker", ["nested", "unmigrated"])
def test_the_ecosystem_verifier_fails_on_every_state_the_gate_fails_on(
    tmp_path: Path, state_maker: str,
) -> None:
    """`verify_ecosystem` kept its own list of failing states, `UNMIGRATED` and `SPLIT`,
    and every state added to this gate since — `INSIDE_KIT`, `NESTED`, `SHARED`,
    `COMMITTABLE` — passed the ecosystem check while the gate itself exited 1. One
    question, two lists, and the second one never heard about the additions."""
    sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))
    from verify_ecosystem import check_data_root as verify

    if state_maker == "nested":
        _file(write_records_dir(tmp_path, "plans"))
        _file(tmp_path / ".squad" / ".squad" / "records", "cycle-events.jsonl")
    else:
        _file(tmp_path / ".claude" / "records" / "plans")

    ok, detail = verify(tmp_path)

    assert not ok, detail

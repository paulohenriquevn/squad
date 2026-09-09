"""The boss attacks the cause of a halt; it never decides the halt.

Every test here is about that line. The mechanism is small on purpose — what makes it
safe is not cleverness, it is the set of things it declines to do.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from backlog_fixtures import item_block
from squad_boss import (
    HALT_DIRS,
    attack_plan,
    causes_named,
    halt_reports,
    unblocking_ids,
)


def _project(tmp_path: Path, *blocks: str) -> Path:
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n\n" + "".join(blocks),
                                         encoding="utf-8")
    (tmp_path / ".claude" / "records" / "implementations").mkdir(parents=True,
                                                                exist_ok=True)
    return tmp_path


def _report(project: Path, slug: str, body: str) -> Path:
    path = project / ".claude" / "records" / "implementations" / f"{slug}-BLOCKED.md"
    path.write_text(body, encoding="utf-8")
    return path


# ── finding the halts ─────────────────────────────────────────────────────────


def test_a_blocked_report_is_found_by_the_item_in_its_slug(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-033"))
    _report(project, "b033-prometheus-url-dev-public", "# BLOCKED\n")
    assert list(halt_reports(project)) == ["B-033"]


def test_a_project_with_no_halt_reports_nothing(tmp_path: Path) -> None:
    assert halt_reports(_project(tmp_path, item_block("B-001"))) == {}


def test_a_report_with_a_suffix_after_BLOCKED_is_still_found(tmp_path: Path) -> None:
    """kit#29 — a lane writing a second halt report for one item naturally adds a
    descriptive suffix (`B-079-2026-09-04-BLOCKED-implement-preflight.md`), and the
    old glob `*-BLOCKED.md` anchored BLOCKED to the end of the name and dropped
    every such file silently. The item then kept being re-offered by the selector
    forever while every surface reported normal operation — measured in the
    consumer on 2026-09-04, B-079 had two halt reports on disk and neither was
    returned.

    The fix (glob → `*BLOCKED*.md`) IS in place. This test locks it: reverting
    the glob to `*-BLOCKED.md` fails this test for the right reason (the
    suffixed report is silently excluded from the result), which is exactly
    what the loop failure looked like from outside.
    """
    project = _project(tmp_path, item_block("B-079"))
    project_records = project / ".claude" / "records" / "implementations"
    # Name shape a lane naturally chooses when writing a second report for one
    # item — the exact form measured on B-079 in the consumer.
    (project_records / "B-079-2026-09-04-BLOCKED-implement-preflight.md").write_text(
        "# BLOCKED\n\nDirty tree from fleet concurrency.\n", encoding="utf-8")

    found = halt_reports(project)

    assert "B-079" in found, (
        "a halt report whose filename carries anything after `BLOCKED` must still "
        "hold its item — the suffix is descriptive prose the lane chose, not a "
        "signal that the file is not a halt.")


def test_a_RESOLVED_rename_no_longer_holds_the_item(tmp_path: Path) -> None:
    """The `-RESOLVED.md` rename is how a halt is retired: the file is renamed out
    of the glob scope so the selector stops holding the item. The new glob
    (`*BLOCKED*.md`) must still exclude these — a report renamed to
    `-RESOLVED.md` no longer contains `BLOCKED` in the filename, so it drops
    out cleanly. Locking that keeps the retire mechanism whole."""
    project = _project(tmp_path, item_block("B-001"))
    project_records = project / ".claude" / "records" / "implementations"
    (project_records / "B-001-2026-09-04-RESOLVED.md").write_text(
        "# RESOLVED\n\nWall cleared by 7565db99c.\n", encoding="utf-8")

    assert halt_reports(project) == {}, (
        "a `-RESOLVED.md` file MUST NOT hold an item — that is precisely how "
        "the retire path works, and if it were included the item would be "
        "re-offered after its halt was retired.")


# ── reading the cause out of the report ──────────────────────────────────────


def test_the_causes_are_the_items_the_report_cites(tmp_path: Path) -> None:
    """Prose, read with a regex, because that is what the reports are: `/implement`
    writes them for a person."""
    project = _project(tmp_path, item_block("B-033"))
    report = _report(project, "b033-x",
                     "# BLOCKED\n\nRegistered B-168, B-169 and B-170 for the "
                     "pre-existing failures.\n")
    assert causes_named(report, "B-033") == ["B-168", "B-169", "B-170"]


def test_the_halted_item_is_not_its_own_cause(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-033"))
    report = _report(project, "b033-x", "# BLOCKED report for B-033\n\nSee B-168.\n")
    assert causes_named(report, "B-033") == ["B-168"]


def test_a_cause_is_named_once_however_often_it_appears(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-033"))
    report = _report(project, "b033-x", "B-168 here, B-168 again, and B-168 once more")
    assert causes_named(report, "B-033") == ["B-168"]


# ── which causes count ───────────────────────────────────────────────────────


def test_a_finished_cause_does_not_hold_anything(tmp_path: Path) -> None:
    """A shipped item cannot be what holds another, however the prose around it reads.
    This is the whole answer to "which of these ids is really the cause?" — measured,
    not judged."""
    project = _project(tmp_path, item_block("B-033"),
                       item_block("B-168", status="shipped"),
                       item_block("B-169", status="triaged"))
    _report(project, "b033-x", "Registered B-168 and B-169.\n")
    statuses = {"B-033": "triaged", "B-168": "shipped", "B-169": "triaged"}
    assert attack_plan(project, statuses) == {"B-033": ["B-169"]}


def test_a_halt_whose_causes_all_shipped_leaves_the_plan(tmp_path: Path) -> None:
    """Not something to attack — something to re-run, and deciding that is a
    person's."""
    project = _project(tmp_path, item_block("B-033"), item_block("B-168"))
    _report(project, "b033-x", "Registered B-168.\n")
    assert attack_plan(project, {"B-033": "triaged", "B-168": "shipped"}) == {}


def test_a_report_naming_no_open_item_is_reported_as_such(tmp_path: Path) -> None:
    """The case a person must still resolve, and the one most easily read as handled."""
    project = _project(tmp_path, item_block("B-033"))
    _report(project, "b033-x", "Blocked on a sponsor decision. No item to point at.\n")
    assert halt_reports(project)                       # the halt is seen
    assert attack_plan(project, {"B-033": "triaged"}) == {}   # and nothing to attack


def test_unblocking_ids_is_the_union_across_every_halt(tmp_path: Path) -> None:
    project = _project(tmp_path, item_block("B-033"), item_block("B-044"))
    _report(project, "b033-x", "See B-168.\n")
    _report(project, "b044-y", "See B-169 and B-168.\n")
    statuses = {"B-033": "triaged", "B-044": "triaged",
                "B-168": "triaged", "B-169": "raw"}
    assert unblocking_ids(project, statuses) == {"B-168", "B-169"}


def test_a_blocked_report_from_the_maintenance_cycle_is_seen(tmp_path: Path) -> None:
    """`cycle-maintenance` declares ITEM_BLOCKED and writes under `maintenance-runs/`.

    That directory was missing from `HALT_DIRS`, so a BLOCKED report from the cycle
    that ORCHESTRATES the queue was invisible to the reader of that queue. A
    consumer measured it from the inside on 2026-08-31 and filed the gap as its own
    blocker — an item waiting on a kit fix nobody upstream knew was needed.
    """
    (tmp_path / ".claude" / "records" / "maintenance-runs").mkdir(parents=True)
    (tmp_path / ".claude" / "records" / "maintenance-runs" / "b-042-BLOCKED.md").write_text(
        "# BLOCKED\n\nB-042 cannot proceed: it waits on B-077.\n", encoding="utf-8")

    halts = halt_reports(tmp_path)

    assert "B-042" in halts, f"the maintenance cycle's halt was not seen: {sorted(halts)}"


@pytest.mark.parametrize("directory", sorted(HALT_DIRS))
def test_every_halt_dir_is_one_the_installer_creates(directory: str) -> None:
    """A directory in this map that the installer never scaffolds is a phase whose
    halts can only be found by accident."""
    install = (Path(__file__).resolve().parents[3]
               / "mechanisms" / "distribution" / "install.sh").read_text(encoding="utf-8")

    assert f'"{directory}"' in install, f"{directory} is watched but never created"

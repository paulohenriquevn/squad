"""A convention a tool does not know is a convention that does nothing.

A lane on a consumer renamed `B-069-BLOCKED.md` to `B-069-BLOCKED.withdrawn.md` to
record that the halt no longer stood. Nothing in this kit read the marker: the
`*BLOCKED*.md` glob matched it anyway, so the item stayed halted on every board and in
every selection — and the person who renamed it had no way to tell.

The FILENAME rather than a line inside the file, deliberately. It shows in `ls`, survives
a grep, needs no parse, and cannot disagree with itself. A marker in the body would be a
second mechanism for one fact, which is the shape this kit keeps removing — so a report
declaring its own withdrawal in prose is still a live halt, and the fix is to rename the
file.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from squad_boss import WITHDRAWN_MARKER, halt_reports  # noqa: E402


def _with_reports(tmp_path: Path, *names: str) -> Path:
    directory = tmp_path / ".squad" / "records" / "implementations"
    directory.mkdir(parents=True)
    for name in names:
        (directory / name).write_text("# BLOCKED\n", encoding="utf-8")
    return tmp_path


def test_a_withdrawn_report_is_not_a_live_halt(tmp_path: Path) -> None:
    root = _with_reports(tmp_path, f"B-069-BLOCKED{WITHDRAWN_MARKER}.md")
    assert halt_reports(root) == {}, \
        "a halt marked withdrawn in its filename was still counted"


def test_a_live_report_beside_a_withdrawn_one_still_counts(tmp_path: Path) -> None:
    """The marker must not become a way to hide every halt in the directory."""
    root = _with_reports(tmp_path,
                         f"B-069-BLOCKED{WITHDRAWN_MARKER}.md",
                         "B-022-BLOCKED.md")
    assert sorted(halt_reports(root)) == ["B-022"]


def test_a_second_report_for_one_item_is_still_found(tmp_path: Path) -> None:
    """`*BLOCKED*.md` rather than `*-BLOCKED.md` exists because lanes add descriptive
    suffixes, and anchoring dropped those files silently. The withdrawal skip must not
    reintroduce that."""
    root = _with_reports(tmp_path, "B-079-BLOCKED-second-lane.md")
    assert sorted(halt_reports(root)) == ["B-079"]


def test_prose_is_not_the_marker(tmp_path: Path) -> None:
    """A report saying it was withdrawn IN ITS BODY stays a live halt. One fact, one
    mechanism — and this one is visible in `ls`."""
    directory = tmp_path / ".squad" / "records" / "implementations"
    directory.mkdir(parents=True)
    (directory / "B-022-BLOCKED.md").write_text(
        "> **WITHDRAWN 2026-09-14 by the coordinator.**\n", encoding="utf-8")
    assert sorted(halt_reports(tmp_path)) == ["B-022"]

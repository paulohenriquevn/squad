"""B-103 — a fix that lands in one tree and not the other must be visible before it is archaeology.

Twenty-two fixes to this kit lived for weeks in a consumer's gitignored `.claude/` install and
nowhere else. Nobody hid them; nothing looked. `sync_consumers.py` propagates kit -> consumer and
answers "is the consumer behind"; this answers the question that went unasked, "have the two
drifted, and which way".

The classification is deliberately line-set based rather than a diff: the question is not "are
these byte-identical" (they never are, once a comment is reworded) but "does one side hold work the
other lacks". A file where BOTH sides hold unique lines is the only case needing a human, and it is
the case a blind copy destroys — measured on `run_code_quality.py`, where copying the install over
the kit would have deleted B-092's zero-detector check.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_install_drift import Drift, classify_file, scan


def _write(p: Path, body: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_identical_files_are_not_drift(tmp_path: Path) -> None:
    a = _write(tmp_path / "a" / "f.py", "x = 1\ny = 2\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\ny = 2\n")
    assert classify_file(a, b) is Drift.IDENTICAL


def test_whitespace_only_difference_is_not_drift(tmp_path: Path) -> None:
    """Blank lines are not work. Reporting them would train people to ignore the report."""
    a = _write(tmp_path / "a" / "f.py", "x = 1\n\n\ny = 2\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\ny = 2\n")
    assert classify_file(a, b) is Drift.IDENTICAL


def test_install_holding_extra_lines_is_install_ahead(tmp_path: Path) -> None:
    a = _write(tmp_path / "a" / "f.py", "x = 1\ny = 2\nz = 3\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\ny = 2\n")
    assert classify_file(a, b) is Drift.INSTALL_AHEAD


def test_kit_holding_extra_lines_is_kit_ahead(tmp_path: Path) -> None:
    a = _write(tmp_path / "a" / "f.py", "x = 1\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\ny = 2\n")
    assert classify_file(a, b) is Drift.KIT_AHEAD


def test_unique_lines_on_both_sides_is_diverged(tmp_path: Path) -> None:
    """The only class that needs a human — and the one a blind copy destroys."""
    a = _write(tmp_path / "a" / "f.py", "x = 1\nonly_install = True\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\nonly_kit = True\n")
    assert classify_file(a, b) is Drift.DIVERGED


def test_scan_reports_each_class_and_exits_nonzero_only_on_real_drift(tmp_path: Path) -> None:
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "same.py", "a\n")
    _write(kit / "same.py", "a\n")
    _write(install / "ahead.py", "a\nb\n")
    _write(kit / "ahead.py", "a\n")
    _write(install / "only-here.py", "a\n")

    report = scan(install, kit)

    assert report.counts[Drift.IDENTICAL] == 1
    assert report.counts[Drift.INSTALL_AHEAD] == 1
    assert report.only_in_install == ["only-here.py"]
    assert report.needs_attention is True   # INSTALL_AHEAD is unharvested work


def test_a_tree_that_matches_exactly_needs_no_attention(tmp_path: Path) -> None:
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "same.py", "a\n")
    _write(kit / "same.py", "a\n")

    assert scan(install, kit).needs_attention is False


def test_only_in_kit_is_reported_but_is_not_drift(tmp_path: Path) -> None:
    """A consumer that has not reinstalled is behind, which is sync_consumers' question, not this one."""
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "same.py", "a\n")
    _write(kit / "same.py", "a\n")
    _write(kit / "new-in-kit.py", "a\n")

    report = scan(install, kit)
    assert report.only_in_kit == ["new-in-kit.py"]
    assert report.needs_attention is False


def test_a_file_added_under_a_directory_the_kit_HAS_is_unharvested_work(tmp_path: Path) -> None:
    """B-103's `_layout.py` case: a whole file that existed in one tree only, and mattered."""
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "implement" / "scripts" / "known.py", "a\n")
    _write(kit / "implement" / "scripts" / "known.py", "a\n")
    _write(install / "implement" / "scripts" / "_layout.py", "a\n")

    report = scan(install, kit)
    assert report.unharvested_files == ["implement/scripts/_layout.py"]
    assert report.needs_attention is True


def test_a_directory_the_kit_does_not_have_at_all_is_a_consumer_artifact(tmp_path: Path) -> None:
    """`review-b052-…-knowledge/` is generated per review by the consumer. Thirty-eight of them.

    Failing on those would make the check red forever on any project that runs /review, which is
    every project — and a check that is always red is a check nobody reads.
    """
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "review" / "scripts" / "known.py", "a\n")
    _write(kit / "review" / "scripts" / "known.py", "a\n")
    _write(install / "review-b052-tests-knowledge" / "SKILL.md", "generated\n")

    report = scan(install, kit)
    assert report.unharvested_files == []
    assert report.only_in_install == ["review-b052-tests-knowledge/SKILL.md"]
    assert report.needs_attention is False

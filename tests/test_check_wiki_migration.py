"""The sweep that keeps the two-root tolerance from becoming the shape of the system.

`test_wiki_fallback.py` promised this script by name — *"`check_wiki_migration.py`
reports a project still reading from the old root"* — and for four days the
sentence was the only thing that existed. These tests pin the four states it
distinguishes, because the interesting one is not the failure but `SPLIT`: once
both roots hold documents the fallback returns the bundle's copy and the old
root's becomes unreachable, so it can never be seen to be stale.

The first case verified against a real consumer rather than a fixture: ten
opportunity documents under `records/discoveries/opportunities/`, a bundle
directory scaffolded and empty beside them, and nothing anywhere reporting it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "gates"))

from check_wiki_migration import (
    EMPTY,
    MIGRATED,
    SPLIT,
    UNMIGRATED,
    check_leaf,
    check_project,
    main,
)


def _write(root: Path, relative: str, name: str = "doc.md") -> Path:
    target = root / relative
    target.mkdir(parents=True, exist_ok=True)
    path = target / name
    path.write_text("# a document\n", encoding="utf-8")
    return path


def test_empty_when_neither_root_holds_a_document(tmp_path: Path) -> None:
    (tmp_path / "wiki" / "sops").mkdir(parents=True)
    (tmp_path / "records" / "sops").mkdir(parents=True)

    report = check_leaf(tmp_path, "sops", "sops")

    assert report.state == EMPTY
    assert report.in_bundle == 0 and report.in_records == 0


def test_scaffold_only_is_not_migrated(tmp_path: Path) -> None:
    """A fresh install has the directories and no knowledge. It is not done."""
    (tmp_path / "wiki" / "sops").mkdir(parents=True)
    (tmp_path / "wiki" / "sops" / ".gitkeep").write_text("", encoding="utf-8")
    _write(tmp_path, "wiki/sops", "index.md")

    assert check_leaf(tmp_path, "sops", "sops").state == EMPTY


def test_unmigrated_when_only_the_old_root_holds_documents(tmp_path: Path) -> None:
    _write(tmp_path, "records/discoveries/opportunities", "found-something.md")

    report = check_leaf(tmp_path, "opportunities", "discoveries/opportunities")

    assert report.state == UNMIGRATED
    assert report.in_records == 1
    assert "fall back" in report.detail


def test_migrated_when_only_the_bundle_holds_documents(tmp_path: Path) -> None:
    _write(tmp_path, "wiki/decisions", "where-knowledge-lives.md")

    assert check_leaf(tmp_path, "decisions", "adrs").state == MIGRATED


def test_split_is_reported_when_both_roots_hold_documents(tmp_path: Path) -> None:
    """The worst state: the old copy is unreachable, so it cannot be seen to rot."""
    _write(tmp_path, "wiki/decisions", "a.md")
    _write(tmp_path, "records/adrs", "a.md")

    report = check_leaf(tmp_path, "decisions", "adrs")

    assert report.state == SPLIT
    assert "unreachable" in report.detail


def test_the_legacy_rename_is_honoured(tmp_path: Path) -> None:
    """`decisions/` was `adrs/`. Looking for the new name under the old root
    would find nothing, and would fail for exactly the consumers that most need
    the report — the ones whose files still sit under the old names."""
    _write(tmp_path, "records/adrs", "old-decision.md")

    assert check_leaf(tmp_path, "decisions", "adrs").state == UNMIGRATED
    # the same documents under the NEW name in the old root are not the case
    # this sweep is about, and must not be counted as one
    other = tmp_path / "other"
    _write(other, "records/decisions", "old-decision.md")
    assert check_leaf(other, "decisions", "adrs").state == EMPTY


def test_the_plugin_layout_is_found(tmp_path: Path) -> None:
    """A consumer keeps both roots under `.claude/`."""
    _write(tmp_path, ".claude/records/discoveries/opportunities", "one.md")

    assert check_leaf(tmp_path, "opportunities",
                      "discoveries/opportunities").state == UNMIGRATED


def test_every_durable_leaf_is_reported(tmp_path: Path) -> None:
    reports = check_project(tmp_path)

    assert {r.leaf for r in reports} == {"sops", "decisions",
                                         "references", "opportunities"}


def test_exit_code_is_one_when_a_leaf_still_reads_the_old_root(tmp_path: Path) -> None:
    _write(tmp_path, "records/sops", "a-procedure.md")

    assert main(["--root", str(tmp_path)]) == 1


def test_exit_code_is_zero_when_nothing_reads_the_old_root(tmp_path: Path) -> None:
    _write(tmp_path, "wiki/sops", "a-procedure.md")

    assert main(["--root", str(tmp_path)]) == 0


def test_a_missing_root_is_a_refusal_not_a_pass(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path / "absent")]) == 2


def test_json_carries_the_verdict(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    import json

    _write(tmp_path, "records/references", "absorbed.md")
    main(["--root", str(tmp_path), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "UNMIGRATED"
    assert any(leaf["state"] == UNMIGRATED for leaf in payload["leaves"])

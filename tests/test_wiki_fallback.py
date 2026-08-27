"""Readers try the OKF bundle first and the records second.

WHY THE FALLBACK EXISTS
-----------------------
42 consumers already have `records/` on disk. A hard cut would break
every one of them that updates the kit without running a migration, and the kit
cannot run anything inside another project's repository.

So: `wiki/` first, `records/` second, and writers only ever write the
new one. Each consumer migrates as it runs, and nothing is deleted from under
anyone.

WHAT THE FALLBACK IS NOT
------------------------
It is not permanent tolerance for two layouts. `check_wiki_migration.py`
reports a project still reading from the old root, so the transition stays
visible instead of becoming the shape of the system.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sop_format import knowledge_base_dir, resolve_knowledge_dir  # noqa: E402


def test_the_bundle_wins_when_both_exist(tmp_path: Path) -> None:
    """The whole point of writing only to the new root: once a project has both,
    the new one is the answer."""
    (tmp_path / "wiki" / "sops").mkdir(parents=True)
    (tmp_path / "records" / "sops").mkdir(parents=True)

    assert resolve_knowledge_dir(tmp_path, "sops") == tmp_path / "wiki" / "sops"


def test_the_old_root_still_answers_when_it_is_all_there_is(tmp_path: Path) -> None:
    """An unmigrated consumer keeps working, unchanged."""
    (tmp_path / "records" / "sops").mkdir(parents=True)

    assert resolve_knowledge_dir(tmp_path, "sops") == tmp_path / "records" / "sops"


def test_the_plugin_layout_is_served_on_both_roots(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "wiki" / "sops").mkdir(parents=True)

    assert resolve_knowledge_dir(tmp_path, "sops") == tmp_path / ".claude" / "wiki" / "sops"


def test_a_project_with_neither_gets_none(tmp_path: Path) -> None:
    """None and an empty directory mean different things: nothing to read is not
    the same as a directory that happens to be empty."""
    assert resolve_knowledge_dir(tmp_path, "sops") is None


def test_the_trail_never_moves_to_the_bundle(tmp_path: Path) -> None:
    """`sop-runs/` is dated evidence, and the decision was explicit that it stays.

    A reader that silently accepted `wiki/sop-runs/` would invite exactly the
    mixing the split exists to prevent.
    """
    (tmp_path / "wiki" / "sop-runs").mkdir(parents=True)
    (tmp_path / "records" / "sop-runs").mkdir(parents=True)

    assert knowledge_base_dir(tmp_path, "sop-runs") == tmp_path / "records" / "sop-runs"


def test_the_sop_checker_reads_the_bundle(tmp_path: Path) -> None:
    """End to end: a SOP living in the bundle is swept."""
    from check_sop_structure import check_sop_structure

    sops = tmp_path / "wiki" / "sops"
    sops.mkdir(parents=True)
    (sops / "demo.md").write_text(
        "---\ntype: SOP\nsop: demo\nversion: 1.0.0\nowner: someone\n"
        "last_reviewed: 2026-08-20\n---\n\n"
        "## Steps\n1. **Run** the thing.\n\n"
        "## Escalation\n- **It breaks** → stop and ask.\n",
        encoding="utf-8",
    )

    report = check_sop_structure(tmp_path, today="2026-08-27")

    assert report.sops_read == 1
    assert report.findings == []


def test_the_sop_checker_still_reads_the_old_root(tmp_path: Path) -> None:
    from check_sop_structure import check_sop_structure

    sops = tmp_path / "records" / "sops"
    sops.mkdir(parents=True)
    (sops / "demo.md").write_text(
        "---\ntype: SOP\nsop: demo\nversion: 1.0.0\nowner: someone\n"
        "last_reviewed: 2026-08-20\n---\n\n"
        "## Steps\n1. **Run** the thing.\n\n"
        "## Escalation\n- **It breaks** → stop and ask.\n",
        encoding="utf-8",
    )

    assert check_sop_structure(tmp_path, today="2026-08-27").sops_read == 1


@pytest.mark.parametrize("leaf", ["sops", "decisions", "references", "opportunities"])
def test_every_durable_leaf_resolves_to_the_bundle(tmp_path: Path, leaf: str) -> None:
    (tmp_path / "wiki" / leaf).mkdir(parents=True)
    assert resolve_knowledge_dir(tmp_path, leaf) == tmp_path / "wiki" / leaf


@pytest.mark.parametrize(
    ("leaf", "legacy"),
    [
        ("sops", "sops"),
        ("decisions", "adrs"),                              # renamed by the migration
        ("references", "references"),
        ("opportunities", "discoveries/opportunities"),     # nested, and never at the leaf's own name
    ],
)
def test_the_fallback_knows_where_the_old_root_actually_kept_it(
    tmp_path: Path, leaf: str, legacy: str
) -> None:
    """A fallback that looks for the NEW name under the OLD root finds nothing.

    Two of the four moved as part of this migration: `adrs/` became `decisions/`
    and `discoveries/opportunities/` flattened to `opportunities/`. Resolving
    `records/<new-name>` would miss both — the consumers that most need
    the fallback are precisely the ones whose files sit under the old names.
    """
    (tmp_path / "records" / legacy).mkdir(parents=True)

    assert resolve_knowledge_dir(tmp_path, leaf) == tmp_path / "records" / legacy


def test_the_bundle_still_wins_over_a_legacy_path(tmp_path: Path) -> None:
    (tmp_path / "wiki" / "decisions").mkdir(parents=True)
    (tmp_path / "records" / "adrs").mkdir(parents=True)

    assert resolve_knowledge_dir(tmp_path, "decisions") == tmp_path / "wiki" / "decisions"


def test_this_repository_resolves_its_sops_to_the_bundle() -> None:
    """The kit itself migrated, so its own SOPs must come from `wiki/`."""
    resolved = resolve_knowledge_dir(REPO_ROOT, "sops")

    assert resolved is not None
    assert resolved.parent.name == "wiki", f"resolved to {resolved}"


def test_the_old_records_root_still_answers(tmp_path: Path) -> None:
    """`knowledge-base/` was renamed to `records/`; consumers still have the old
    one, and the kit cannot run a migration inside another project's repo."""
    (tmp_path / "knowledge-base" / "sop-runs").mkdir(parents=True)

    assert knowledge_base_dir(tmp_path, "sop-runs") == tmp_path / "knowledge-base" / "sop-runs"


def test_the_new_records_root_wins_over_the_old(tmp_path: Path) -> None:
    (tmp_path / "records" / "sop-runs").mkdir(parents=True)
    (tmp_path / "knowledge-base" / "sop-runs").mkdir(parents=True)

    assert knowledge_base_dir(tmp_path, "sop-runs") == tmp_path / "records" / "sop-runs"

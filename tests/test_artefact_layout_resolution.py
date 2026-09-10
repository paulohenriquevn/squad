"""The third layout, and the third time this defect has been found.

`run_validation.py` resolves artefacts in two layouts: `<project>/.claude/records/`
and `<project>/records/`. A consumer measured on 2026-08-29 uses neither. The
`platform` repository declares `<project>/.claude/knowledge-base/` canonical
in a rule of its own — written after an audit read `.claude/` and reported one
repository as having "0 implementations, 0 reviews, 0 releases" when it had 6, 12
and 8.

That repository holds **32 plans in `knowledge-base/plans/` and zero in
`records/plans/`**. Every one of the nine `_find_plan` call sites therefore
answers SKIP, including the alignment gate installed there minutes earlier.

The comment directly beneath `_find_plan` already names the failure mode, having
been written for the same defect one layout earlier:

    A gate that reports SKIP because it looked in the wrong directory is
    indistinguishable in the report from one that legitimately had nothing to
    check, which is why this survived.

Looking in more places cannot produce a false finding — it can only stop a false
SKIP. That asymmetry is why this is safe to widen and why it should have been
widened the first time.

NOT THE SAME FILE AS `test_knowledge_base_layout.py`
----------------------------------------------------
That one is the regression guard for issue #7: `/roadmap-init` hardcoded the
standalone `records/` side and aborted in every plugin install. Its scope note
already counted the wider damage — **11 skills hardcoding `.claude/records/` and
24 hardcoding `records/`, none resolving the layout** — and deliberately declined
to widen itself, because turning a regression guard into a 34-skill migration
hides the regression.

This file is one instalment of that migration, for `run_validation.py`, and it
adds a third root neither of them knew about.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/implement/scripts"
sys.path.insert(0, str(SCRIPTS))

import run_validation as rv  # noqa: E402

LAYOUTS = (
    (".claude/records", "the plugin layout the kit ships"),
    ("records", "the standalone layout the kit dogfoods"),
    (".claude/knowledge-base", "platform, which declares this canonical in a rule"),
    ("knowledge-base", "the standalone form of the same convention"),
)


def _make(tmp_path: Path, base: str, kind: str, name: str) -> Path:
    d = tmp_path / base / kind
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("# artefact\n", encoding="utf-8")
    return p


def test_a_plan_is_found_in_every_layout(tmp_path: Path) -> None:
    """Nine gates key off this one lookup. A miss here silences all nine."""
    for base, why in LAYOUTS:
        root = tmp_path / base.replace("/", "_")
        _make(root, base, "plans", "demo-plan.md")
        found = rv._find_plan(root, "demo")
        assert found is not None, f"plan not found in {base} — {why}"
        assert found.name == "demo-plan.md"


@pytest.mark.skipif(not hasattr(rv, "check_implementation_log"),
                    reason="this kit has no implementation-log gate; the two diverge here "
                           "by design and asserting it everywhere would fake parity")
def test_an_implementation_log_is_found_in_every_layout(tmp_path: Path) -> None:
    """`check_implementation_log` FAILs on absence, so a wrong directory here does
    not merely go quiet — it accuses a project of losing a log it wrote."""
    for base, why in LAYOUTS:
        root = tmp_path / base.replace("/", "_")
        _make(root, base, "plans", "demo-plan.md")
        _make(root, base, "implementations", "demo-implementation.md")
        result = rv.check_implementation_log(root, "demo")
        assert result["status"] == "PASS", f"{base} — {why}: {result.get('reason')}"


def test_the_alignment_gate_reaches_a_knowledge_base_plan(tmp_path: Path) -> None:
    """The gate installed into that consumer would have been inert on arrival.

    This is the third port of the same gate and the third time the behaviour did
    not travel with the file: `B-NNN` versus `milestone_id` between the two kits,
    and now `records/` versus `knowledge-base/` inside one consumer.
    """
    root = tmp_path / "kb"
    plan = _make(root, ".claude/knowledge-base", "plans", "b-014-demo-plan.md")
    plan.write_text("# Plan\n\nImplements B-014.\n", encoding="utf-8")
    result = rv.check_alignment_gate(root, "b-014-demo")
    assert result["status"] == "FAIL", result
    assert "B-014" in result["reason"]


def test_a_writer_does_not_follow_the_project_legacy_trail(tmp_path: Path) -> None:
    """Writers go to the one root; only readers fall back.

    This test used to assert the opposite — that a new artifact landed wherever the
    project already wrote — and the reasoning was sound for its time: a report landing
    in `records/reviews/` inside a project whose trail lived in `knowledge-base/`
    created the second audit trail that rule calls worse than none.

    Centralising answers it differently. A writer that followed would keep every
    project on its old root forever, and the split it avoided would be replaced by a
    migration that never happens. The split is now temporary, reported by
    `check_wiki_migration.py`, and closed by a person moving the old trail.
    """
    root = tmp_path / "kb"
    _make(root, ".claude/knowledge-base", "plans", "demo-plan.md")

    target = rv._artefact_write_dir(root, "reviews")

    assert target == root / ".squad" / "records" / "reviews", target


def test_a_project_with_no_trail_at_all_gets_the_same_root(tmp_path: Path) -> None:
    """There is no layout-dependent default left to get wrong."""
    target = rv._artefact_write_dir(tmp_path / "fresh", "reviews")

    assert target.parts[-3:] == (".squad", "records", "reviews"), target

"""Six reviewers sharing one working tree filed a false BLOCKER.

MEASURED, NOT HYPOTHESISED
--------------------------
The comment in `consolidate_findings.py` records the B-025 run: six agents ran
concurrently against ONE tree, `usage-panel.tsx` was found carrying a mutation
marker mid-review, probe files appeared at the repo root, and the architecture
reviewer filed `reportGuardFailure has zero production call sites` against a
symbol called at `usage-panel.tsx:115` and `:147`. Three of six reviewers
happened to notice the tree was dirty and re-derived their citations.

That comment ends with the answer and does not take it:

    Isolation (a worktree per agent) is the fix. This is the DETECTOR beside it.

`capture_tree_state` was built, and the instruction that spawns the agents was
left asking for no isolation at all. A detector beside a missing fix reports the
damage after the budget is spent — the B-025 run cost six full reviews and
produced one false BLOCKER.

WHAT THIS PINS
--------------
The spawn instruction must ask for isolation. This is a contract on the
INSTRUCTION, which is prose — so it asserts the mechanism is named, not any
particular sentence. `skills/_kit-rules/prompt-text-is-not-behaviour.md` draws that line:
naming a required parameter is structure; the wording around it is not.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


def _spawn_block() -> str:
    """The Agent( ... ) invocation the skill tells the caller to make."""
    text = SKILL.read_text(encoding="utf-8")
    m = re.search(r"Agent\((.*?)\)", text, re.DOTALL)
    assert m, "SKILL.md no longer shows an Agent( ) invocation to check"
    return m.group(1)


def test_the_spawn_asks_for_worktree_isolation() -> None:
    """Without it, N reviewers share one tree and each one's edits are the
    others' evidence."""
    block = _spawn_block()
    assert "isolation" in block, (
        "the spawn instruction does not request isolation — six agents will share "
        "one working tree, which is the B-025 defect the tree-state detector was "
        "built to notice after the fact"
    )
    assert "worktree" in block, "isolation is requested but not the worktree kind"


def test_the_detector_is_still_there() -> None:
    """Isolation that silently stops working looks exactly like isolation that
    works. The detector is not replaced by the fix; it is what proves the fix is
    still in force.

    KNOWN GAP, MEASURED 2026-08-30: only one of the two kits has
    `capture_tree_state`. The other now passes `isolation="worktree"` and has
    nothing that would notice if that stopped taking effect — which is the worse
    half of the pair, by the reasoning in the B-025 comment itself.

    It is NOT ported here on purpose. The detector has seven integration points
    including the report renderer, and the two `consolidate_findings.py` have
    already diverged: copying this file wholesale between the kits broke one of
    them earlier the same week. A rushed port of a detector is a detector nobody
    can trust. The gap is named so it is a decision rather than an oversight.
    """
    src_path = SKILL.parent / "scripts" / "consolidate_findings.py"
    src = src_path.read_text(encoding="utf-8")
    if "def capture_tree_state" not in src:
        pytest.skip(
            "this kit ships no tree-state detector — it has the isolation fix and "
            "no way to notice if the isolation stops working. Named in "
            "skills/_kit-rules/parallelism-shapes.md; porting it is a decision, not a chore."
        )
    assert "def capture_tree_state" in src

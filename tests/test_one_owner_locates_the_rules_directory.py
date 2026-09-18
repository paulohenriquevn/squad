"""Nine sites located `rules/` by hand, and they disagreed about which one wins.

Six tried `("rules", ".claude/rules")` — `check_phase_drift` (three times),
`cycle_events`, `check_emitted_verdicts`, `squad_lead`, `board_state` — and three tried
`(".claude/rules", "rules")` — `check_chain_preconditions`, `select_auditors`,
`squad/paths.LEGACY_ROUTING_ROOTS`.

In a plugin install BOTH directories exist: `.claude/rules/` is the installed kit's and
`rules/` may be the project's own. So the same question got two answers depending on
which module asked it, and a table edited in one was invisible to half its readers.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

#: The literal pair, in either order. A site spelling it again is a site that can drift.
_HAND_ROLLED = re.compile(
    r'\(\s*"(?:\.claude/)?rules"\s*,\s*"(?:\.claude/)?rules"\s*\)'
    r'|\(\s*project\s*/\s*"\.claude"\s*/\s*"rules"\s*,')


def test_the_order_is_declared_in_exactly_one_place() -> None:
    from squad.paths import rules_dir

    assert rules_dir.__doc__ and ".claude/rules" in rules_dir.__doc__, (
        "the owner does not say which order it uses")


def test_no_module_rolls_the_pair_by_hand_again() -> None:
    offenders = []
    for base in ("mechanisms", "skills", "hooks", "squad"):
        for path in (_ROOT / base).rglob("*.py"):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if _HAND_ROLLED.search(line):
                    offenders.append(f"{path.relative_to(_ROOT)}:{number}")

    # `squad/paths.py` is the owner and `_RULE_BASES` constants name the same order once
    # per module that iterates BASES rather than asking for a directory.
    allowed = {"squad/paths.py"}
    unexpected = [o for o in offenders if o.rsplit(":", 1)[0] not in allowed]

    assert not unexpected, (
        f"these resolve the rules directory by hand again: {unexpected}. "
        f"Import `squad.paths.rules_dir` — the order is declared there, once.")


def test_the_owner_prefers_the_installed_kit_when_both_exist(tmp_path: Path) -> None:
    """The case where the disagreement was observable, pinned."""
    from squad.paths import rules_dir

    (tmp_path / "rules").mkdir()
    (tmp_path / ".claude" / "rules").mkdir(parents=True)

    assert rules_dir(tmp_path) == tmp_path / ".claude" / "rules"


def test_the_owner_finds_a_bare_rules_tree(tmp_path: Path) -> None:
    """The kit's own checkout: only `rules/` exists and the order never comes up."""
    from squad.paths import rules_dir

    (tmp_path / "rules").mkdir()

    assert rules_dir(tmp_path) == tmp_path / "rules"


def test_a_tree_with_neither_answers_none(tmp_path: Path) -> None:
    from squad.paths import rules_dir

    assert rules_dir(tmp_path) is None

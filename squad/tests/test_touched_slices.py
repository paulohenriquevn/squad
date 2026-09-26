"""The file-to-slice map behind `sq test --touched`.

The dangerous failure here is NARROWING, not widening: a map that misses an edge
runs fewer tests and still reports success. So every rule that cannot resolve a path
widens to everything, and the reason is carried out with the selection rather than
inferred by the caller.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mechanisms" / "conventions"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import touched_slices  # noqa: E402 — post-bootstrap import

KNOWN = frozenset({"backlog-review", "plan-confidence", "review", "implement"})


def test_a_skill_file_selects_exactly_its_own_slice() -> None:
    sel = touched_slices.select(["skills/review/scripts/spawn_reviewers.py"], KNOWN)
    assert sel.slices == {"review"}
    assert sel.everything is False


def test_two_skill_files_select_both_slices() -> None:
    sel = touched_slices.select(
        ["skills/review/scripts/a.py", "skills/implement/tests/test_b.py"], KNOWN
    )
    assert sel.slices == {"review", "implement"}
    assert sel.everything is False


def test_a_skill_that_is_not_a_known_slice_widens() -> None:
    """A skill with no `tests/` dir is not a slice, and guessing would under-run."""
    sel = touched_slices.select(["skills/pipeline/SKILL.md"], KNOWN)
    assert sel.everything is True


def test_a_mechanisms_file_widens_to_everything() -> None:
    """Shared code. `skills/plan-confidence/tests/conftest.py` reaches into it."""
    sel = touched_slices.select(["mechanisms/conventions/ecosystem_utils.py"], KNOWN)
    assert sel.everything is True
    assert any("mechanisms" in r for r in sel.reasons)


def test_a_rules_file_widens_to_everything() -> None:
    """`rules/*.txt` are read by gates the slices exercise."""
    assert touched_slices.select(["rules/verdict-bands.txt"], KNOWN).everything is True


def test_root_owned_trees_select_the_root_suite_only() -> None:
    for path in ("tests/test_x.py", "hooks/validate-command.py", "squad/layout.py"):
        sel = touched_slices.select([path], KNOWN)
        assert sel.root_suite is True, path
        assert sel.everything is False, path
        assert sel.slices == frozenset(), path


def test_an_unrecognised_path_widens_and_names_itself() -> None:
    """No match is not 'no impact'. The path appears in the reason so it can be mapped."""
    sel = touched_slices.select(["some/new/tree/thing.py"], KNOWN)
    assert sel.everything is True
    assert any("some/new/tree/thing.py" in r for r in sel.reasons)


def test_an_empty_change_set_selects_nothing_and_says_so() -> None:
    """Nothing changed is a real answer, and it is not the same as 'run everything'."""
    sel = touched_slices.select([], KNOWN)
    assert sel.everything is False
    assert sel.slices == frozenset()
    assert sel.root_suite is False
    assert sel.reasons


def test_widening_beats_narrowing_when_both_apply() -> None:
    """One unmappable path in a set of skill files still widens the whole run."""
    sel = touched_slices.select(
        ["skills/review/scripts/a.py", "mechanisms/gates/check_xrefs.py"], KNOWN
    )
    assert sel.everything is True


def test_the_selection_is_deterministic_regardless_of_input_order() -> None:
    a = touched_slices.select(["skills/review/a.py", "skills/implement/b.py"], KNOWN)
    b = touched_slices.select(["skills/implement/b.py", "skills/review/a.py"], KNOWN)
    assert a.slices == b.slices
    assert sorted(a.reasons) == sorted(b.reasons)


def test_a_dotted_path_is_not_eaten_by_the_prefix_strip() -> None:
    """`lstrip("./")` removes any leading `.` or `/`, not the prefix `./`.

    Found by running the real thing: `.claude-plugin/plugin.json` arrived as
    `claude-plugin/plugin.json` and `.gitattributes` as `gitattributes`. Both still
    widened, so the selection stayed SAFE — but the reason named a path that does not
    exist, and a reason nobody can look up is a reason nobody can act on.
    """
    sel = touched_slices.select([".claude-plugin/plugin.json"], KNOWN)
    assert sel.everything is True
    assert any(".claude-plugin/plugin.json" in r for r in sel.reasons), sel.reasons


def test_an_explicit_dot_slash_prefix_is_removed() -> None:
    """`./skills/review/x.py` and `skills/review/x.py` are the same file."""
    sel = touched_slices.select(["./skills/review/scripts/a.py"], KNOWN)
    assert sel.slices == {"review"}

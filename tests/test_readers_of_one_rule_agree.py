"""Two readers of one rule file, and nothing asserts they answer the same.

`rules/blocking-verdicts.txt` is read by `board_state.blocking_verdicts` and by
`squad_lead._blocking_verdicts`. The two parses are character-for-character equivalent
today — same search order, same `#` split, same upper-casing, same discard of the empty
string. Nothing makes them stay that way.

That file exists BECAUSE this already happened: `check_verdict_bands` records "16 in a
frozenset hardcoded inside check_phase_drift" against the list in the rule, and
`squad_boss.halt_reports` cites "two copies of a blocking-verdict list" as the reason it
refuses to be a second reader of anything.

A sweep finds the readers that exist now. An AGREEMENT test fails when the next one
disagrees — which is the reader nobody has written yet, and the only kind a sweep
cannot reach. Three readers of "does this item have a record" disagreed for months on
2026-09-16 with no red test anywhere, because each passed against the fixture its own
author wrote.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "skills" / "backlog-review" / "scripts"))
sys.path.insert(0, str(_ROOT / "mechanisms" / "fleet"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from board_state import blocking_verdicts  # noqa: E402 — post-bootstrap import
from squad_lead import Lead  # noqa: E402 — post-bootstrap import

_RULE = """\
# A comment line, discarded entirely
FAIL_HARD
  invalid  # trailing comment, and lowercase, and padded
BLOCKED

AWAITING_HUMAN
"""


def _project(tmp_path: Path, body: str) -> Path:
    rules = tmp_path / "rules"
    rules.mkdir(parents=True)
    (rules / "blocking-verdicts.txt").write_text(body, encoding="utf-8")
    return tmp_path


def _both(root: Path) -> tuple[frozenset, frozenset]:
    return blocking_verdicts(root), Lead(session="t", project=root)._blocking_verdicts()


def test_the_two_readers_answer_the_same(tmp_path: Path) -> None:
    board, lead = _both(_project(tmp_path, _RULE))
    assert board == lead, (
        "one rule file, two answers — a comment, a case or a padded line is parsed "
        f"differently: board={sorted(board)} lead={sorted(lead)}")
    assert "INVALID" in board, "the shared parse stopped upper-casing"


def test_they_agree_on_an_absent_file(tmp_path: Path) -> None:
    """The case where one could plausibly return everything and the other nothing.

    Both say None — "I could not read the rule" — and neither says `frozenset()`, which
    would make every verdict non-blocking and let a held item start.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    board, lead = _both(tmp_path)
    assert board is None and lead is None, f"board={board} lead={lead}"


def test_they_agree_on_the_claude_rules_location(tmp_path: Path) -> None:
    """A consumer keeps the kit under `.claude/`. A reader that searched only one of the
    two locations would answer empty where the other answered the list."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "blocking-verdicts.txt").write_text("FAIL\n", encoding="utf-8")
    board, lead = _both(tmp_path)
    assert board == lead == frozenset({"FAIL"})


def test_they_agree_on_a_file_that_is_only_comments(tmp_path: Path) -> None:
    """Empty-after-parsing and absent are different states upstream, and both readers
    must reach the same one."""
    board, lead = _both(_project(tmp_path, "# nothing but a comment\n\n"))
    assert board == lead == frozenset()

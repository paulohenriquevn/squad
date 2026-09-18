"""A plan waiting on its panel exited with the code reserved for a broken invocation.

`_exit_code` fell through to `return 2` for AWAITING_REVIEW, NEEDS_REVISION and
ITEM_IN_FLIGHT, and SKILL.md maps 2 to "Error (plan not found, malformed rubric)". To
any caller reading exit codes, a structurally perfect plan that nobody has reviewed yet
was indistinguishable from a command typed wrong — and the two take opposite actions:
one convenes a panel, the other fixes the command.

4 is the panel's code. It is not a failure of the plan; it says the SCORE stands and
the VERDICT is held pending a human.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))
sys.path.insert(0, str(_ROOT))

import run_structural  # noqa: E402 — post-bootstrap import


def test_each_panel_verdict_has_its_own_code() -> None:
    for verdict in ("AWAITING_REVIEW", "NEEDS_REVISION", "ITEM_IN_FLIGHT"):
        assert run_structural._exit_code(verdict) == 4, (
            f"{verdict} exits {run_structural._exit_code(verdict)}, which SKILL.md "
            f"reads as an invocation error")


def test_the_scored_verdicts_keep_their_codes() -> None:
    assert run_structural._exit_code("SHIPPABLE") == 0
    assert run_structural._exit_code("SHIPPABLE_WITH_CAVEATS") == 0
    assert run_structural._exit_code("INVALID") == 1
    assert run_structural._exit_code("NON_SHIPPABLE") == 3


def test_two_remains_the_code_for_a_broken_invocation() -> None:
    """Whatever else 2 means, it must not also mean "a person has not looked yet"."""
    assert run_structural._exit_code("something-unrecognised") == 2


def test_the_skill_documents_the_panel_code() -> None:
    text = (_ROOT / "skills" / "plan-confidence" / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("## Exit Codes", 1)[1].split("\n## ", 1)[0]

    assert re.search(r"^- `4`", section, re.MULTILINE), section

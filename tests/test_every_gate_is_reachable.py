"""A gate nobody runs reports its first real failure to nobody.

Measured on 2026-09-02: of eighteen gates, two were executed by nothing at all —
not the CI, not a hook, not `verify_ecosystem`, not any script.
`check_orphan_verdicts` appeared exactly once outside its own tests, inside a
COMMENT in a sibling gate. Both passed clean when finally run, so nothing was
hiding behind them; that is luck, and luck is not a property you can rely on
twice.

The two they check are not minor. One asks whether every verdict a cycle rule
declares can actually be emitted by something; the other asks whether every
declared phase has an emitter at all. A verdict named in a rule and produced by
nothing is a state the chain can never enter, and a reader planning around it is
planning around a state that does not exist — `NEEDS_SPLIT` lived exactly that
way, documented and unimplemented, and briefs needing a split were squeezed into
BLOCKED.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_GATES = _REPO / "mechanisms" / "gates"

#: Gates that legitimately have no automatic trigger, each with the reason.
#: Empty on purpose — an entry here is a claim that a gate should never fire on
#: its own, and that claim should be hard to make.
MANUAL_ONLY: dict[str, str] = {}


def _gate_names() -> list[str]:
    return sorted({p.stem for p in _GATES.glob("check_*.py")}
                  | {"validate_skill_frontmatter"})


def _invokes(text: str, gate: str) -> bool:
    """A real invocation, not a mention.

    `check_orphan_verdicts` was named in a COMMENT in a sibling gate, and that
    read as coverage until someone looked — so a bare occurrence of the name does
    not count. What counts is the filename, an import, or the name passed as an
    argument to a runner (`_run_gate(dir, "check_x")`), which is how a dispatcher
    invokes a gate whose path it builds itself.
    """
    return bool(re.search(
        rf"{gate}\.py|from {gate} import|import {gate}\b|_run_gate\([^)]*[\"']{gate}[\"']",
        text))


def _triggers_for(gate: str) -> list[str]:
    sources: list[tuple[str, str]] = []
    workflows = _REPO / ".github" / "workflows"
    if workflows.is_dir():
        for path in workflows.glob("*.yml"):
            sources.append((f"CI:{path.name}", path.read_text(encoding="utf-8")))
    for path in (list((_REPO / "hooks").glob("*.py"))
                 + list((_REPO / "mechanisms").rglob("*.py"))
                 + list((_REPO / "mechanisms").rglob("*.sh"))
                 + list((_REPO / "skills").rglob("scripts/*.py"))):
        if path.stem == gate or "/tests/" in str(path):
            continue
        try:
            sources.append((str(path.relative_to(_REPO)), path.read_text(encoding="utf-8")))
        except OSError:
            continue
    return [name for name, text in sources if _invokes(text, gate)]


@pytest.mark.parametrize("gate", _gate_names())
def test_something_runs_this_gate(gate: str) -> None:
    """Being correct is not the same as being consulted."""
    if gate in MANUAL_ONLY:
        pytest.skip(f"declared manual-only: {MANUAL_ONLY[gate]}")

    triggers = _triggers_for(gate)

    assert triggers, (
        f"{gate} is executed by nothing — not the CI, not a hook, not "
        f"verify_ecosystem, not any script. Wire it, or add it to MANUAL_ONLY "
        f"with the reason it should never fire on its own.")


def test_the_two_phase_gates_are_wired_into_the_verifier() -> None:
    """Named specifically because they were the two found orphaned, and because
    a general assertion is satisfied by any caller — including a weak one."""
    verifier = (_GATES / "verify_ecosystem.py").read_text(encoding="utf-8")

    for gate in ("check_orphan_verdicts", "check_phase_emitters"):
        assert _invokes(verifier, gate), f"{gate} left the verifier again"
    assert '("Orphan verdicts"' in verifier and '("Phase emitters"' in verifier, \
        "wired but not registered in the check list is the same as not wired"

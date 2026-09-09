"""A preserved lane is the one most likely to be stuck, and it was the one skipped.

`start_fleet.sh` leaves an already-running session alone — correct, since killing
a lane mid-turn loses its work. The readiness check added on 2026-09-02 then
looked only at sessions the script had just created.

That is backwards. A session this script watched start is the case already
observed to succeed; a preserved one is the case nobody watched, and it is
exactly how three lanes spent forty minutes in a first-run dialog while
`fleet_status.sh` reported them idle and the lead read three free lanes.

Found by the kit's own self-audit, in the lens for absence reported as an answer,
against a fix written earlier the same day.
"""
from __future__ import annotations

import re
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parent.parent / "mechanisms" / "fleet"
           / "start_fleet.sh")


def _code() -> str:
    return "\n".join(line for line in _SCRIPT.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def test_a_preserved_session_joins_the_readiness_check() -> None:
    """Both branches of the create-or-keep decision must feed the same list."""
    code = _code()

    appends = re.findall(r'checked\+=\("\$name"\)', code)
    assert len(appends) == 2, (
        f"expected the preserved branch and the created branch to both register "
        f"the session; found {len(appends)} registration(s)")


def test_the_preserved_branch_registers_before_it_continues() -> None:
    """`continue` above the append would skip it silently — the original shape."""
    code = _code()
    branch = code[code.index("already running"):]
    append_at = branch.index('checked+=("$name")')
    continue_at = branch.index("continue")

    assert append_at < continue_at, "the preserved branch continues before registering"


def test_the_list_is_named_for_what_it_holds() -> None:
    """It was called `started` while holding sessions that were not started here.
    A name that lies is where the next reader's wrong assumption comes from."""
    code = _code()

    assert "checked=()" in code
    assert "started+=" not in code


def test_the_fleet_does_not_open_when_a_lane_is_not_at_a_prompt() -> None:
    """The point of checking. A fleet whose lanes are stuck reports them idle, and
    the lead hands work to sessions that cannot take it."""
    code = _code()

    assert "session_ready.py" in code
    assert re.search(r"exit 1", code), "a stuck lane must stop the fleet from opening"

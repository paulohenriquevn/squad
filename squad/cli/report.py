"""What every `sq` command returns, and the field that makes it honest.

`not_checked` is REQUIRED, not optional, and it is the reason this dataclass exists
rather than each command printing as it goes.

The kit's governing sentence is that an inability to measure must never become a
passing measurement (`tests/test_gates_say_what_they_examined.py`). The tooling used
to measure did not have that property: on 2026-09-09 a session reported "1894 passed"
while 152 tests collected nowhere and 22 slice suites had not run, and nothing on
screen said the other half existed.

Making it a printed line would have fixed the human channel and left `--json` saying
`{"passed": 1894}` — so every programmatic consumer would get exactly the
false-coverage report this field exists to prevent. It is a field, and a test asserts
that every verb populates it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: What the caller should conclude. `0` the thing held · `1` a finding or a refusal ·
#: `2` could not measure, or bad invocation. The third is the load-bearing one and is
#: the house convention: `check_mechanisms_inventory.py` states it as "Absence of a
#: README is INVENTORY_UNREADABLE, never a pass".
OK = 0
FINDING = 1
UNMEASURED = 2


@dataclass
class Report:
    """One command's answer, including the shape of its own ignorance."""

    verb: str
    #: What the command looked at, in its own units ("23 gates", "22 slices").
    observed: list[str] = field(default_factory=list)
    #: What it did NOT look at, each with the reason. Never empty for convenience:
    #: an empty list is a claim that nothing was missed, and it must be true.
    not_checked: list[str] = field(default_factory=list)
    #: Human-facing lines, in order.
    lines: list[str] = field(default_factory=list)
    #: Anything the verb wants in `--json` beyond the fields above.
    detail: dict[str, Any] = field(default_factory=dict)
    exit_code: int = OK

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

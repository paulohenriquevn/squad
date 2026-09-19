"""How much the kit says into a session on its own initiative.

The kit speaks three times per turn without being asked. Measured on a consumer
2026-09-18: 1249 bytes in front of every prompt, 1835 once at session start, and
602 of advisory warnings at the end of a turn.

The ladder's docstring gives the reason it is unconditional, and the reason is
good — "a rule read at session start is a rule forgotten by the fortieth prompt".
It is good for a session writing code. It is false for one that is not: asking
what time it is gets the parsimony ladder in front of it, and a reader who sees
doctrine attached to every question learns to skip doctrine. A rule injected into
a turn it has nothing to do with is not a rule being remembered, it is a rule
being spent.

WHAT THIS DOES NOT TURN OFF, and the distinction is the whole design:

  * `PreToolUse` — `boundary-check` and `validate-command` still refuse. A guard
    a config can silence is a guard that gets silenced on the day it would have
    mattered, by somebody who only wanted less text.
  * `Stop`'s BLOCKERS — a secret in the diff, production source with no changelog
    entry. Only the WARN half is advisory, and only the advisory half is noise.
  * `PostToolUse` lints, which are already silent when there is nothing to say.

So this is a volume control and never a kill switch, and the two are worth keeping
apart by construction rather than by documentation.

`STOP_VALIDATION_WARN_ONLY=1` is the opposite axis: it downgrades blockers to
warnings, where this suppresses warnings and never reaches blockers. Neither is a
route to the other.

ONE OWNER. Three hooks need this answer and each could compute it. Two files that
answer the same question is the shape this kit has paid for in `squad/plan.py`, in
`_credential_globs`, in `_is_auto_generated` and in `default_panel_path` — every
time the same way: one copy gets fixed and the other keeps running.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Overrides the project's setting for ONE session, in BOTH directions. Turning it
#: back on matters as much as turning it off: a project that is quiet by default is
#: one where somebody eventually needs the doctrine back, and editing a versioned
#: file to get it for an afternoon is a change that gets committed by accident.
QUIET_ENV = "SQUAD_QUIET"

#: Project-owned, under `rules/`, preserved across installs by the same mechanism
#: that preserves `notifications.txt` and `contribution-overrides.txt`. It belongs
#: to the project because how loud a dependency should be is the project's call.
SETTING_FILE = "rules/session-injection.txt"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _read(value: str) -> bool | None:
    """`True`, `False`, or `None` when the text decides nothing."""
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    return None


def is_quiet(kit_dir: Path | str | None) -> bool:
    """Should the kit hold its unprompted injections for this session?

    Precedence: the variable, then the file, then speaking. Anything unreadable at
    either level falls through to the next rather than deciding — silence is never
    the answer to a question that could not be read. A parse failure that quiets
    the kit would remove the doctrine AND the report that something is wrong, which
    is this repository's most-repeated defect wearing its quietest face.
    """
    override = _read(os.environ.get(QUIET_ENV, ""))
    if override is not None:
        return override
    if kit_dir is None:
        return False
    setting = Path(kit_dir) / SETTING_FILE
    try:
        text = setting.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip().lower() == "quiet":
            decided = _read(value)
            if decided is not None:
                return decided
    return False

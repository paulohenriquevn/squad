"""The active block of work: a goal, what it admitted, and what closing it decided.

## What this is, and the three things it deliberately does not do

The chain runs one item per phase and the fleet runs many items at once. Neither of them
answers *why this work and not other work* — `select_backlog_item.rank()` orders by
obligation, then by what unblocks a halt, then by status, then by AGE. Age is the only
signal that cannot be inflated by whoever wants to move on, which is why it is there and
why it stays. But a queue ordered by age alone is a task list: every item individually
justified, the set as a whole answering to nothing.

A sprint is the missing answer. It is a declared goal, the items admitted to it, and a
close that records what each admitted item came to.

It does NOT schedule work. `mechanisms/fleet/pipeline_orchestrator.py` already puts N
items through the stages at once, with the lane budget DERIVED — an earlier draft asserted
`8` and deadlocked against the agent cap it cited in the same sentence.

It does NOT decide what happens to a blocked item. `mechanisms/cycle/halt_disposition.py`
already does, with two answers: `RETURN_TO_QUEUE` when the halt is work, and
`RETAIN_FOR_PERSON` when it is a material impediment. Both move the item out of the phase
and neither holds the session, so the block refills by the mechanism that already exists.

It does NOT gate release. Releasing per item is a measured strength of this chain, and the
process model that motivated the sprint names *releasing a whole sprint as one technical
package* as an antipattern in the same document that recommends sprints.

## Why a person opens and closes it

`opened_by` and `closed_by` take `human/<name>` and nothing else. The argument is the one
`approved_by` rests on: a commitment with no attribution is not evidence that anybody
decided. A sprint opened by `system/` would be focus declared by whoever wanted to move
on, which is the same shape as an agent assigning itself a low uncertainty level — the
kit refuses that one by requiring evidence, and refuses this one by requiring a signature.

## Why closing needs a verdict per admitted item

Because otherwise the block is a label. A sprint that closes while an admitted item is
still open says the focus ended and leaves no record of what happened to the work — and
an item that quietly leaves a sprint is indistinguishable from one that was never in it.
The close reads the registry's own terminal statuses; it does not invent a vocabulary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from squad.paths import sprint_record

#: Statuses that mean the registry is finished with an item. Read from the contract's
#: vocabulary rather than restated as a threshold: a sprint must not have its own opinion
#: about what "done" means.
TERMINAL_STATUSES = ("shipped", "killed")

#: Who may open or close one. See the module docstring.
_SIGNATURE_RE = re.compile(r"^human/\S+")

_FIELD_RE = re.compile(r"^([a-z_]+):\s*(.*)$", re.MULTILINE)


class SprintInvalid(Exception):
    """The sprint was not opened or closed validly. NOT a judgement on the work."""


@dataclass(frozen=True)
class Sprint:
    sprint_id: str
    goal: str
    admitted: tuple[str, ...]
    opened_by: str
    traces_to: tuple[str, ...] = ()
    closed_by: str = ""
    verdicts: dict[str, str] | None = None

    @property
    def is_open(self) -> bool:
        return not self.closed_by


def _ids(raw: str) -> tuple[str, ...]:
    """Distinct ids, in the order written.

    Distinct on purpose. `parse_blocked_by` returns one entry per OCCURRENCE of an id in
    prose, so a registry printed `blocks B-229, B-229, B-229` for one impediment named
    three times in one sentence. Filed as a defect elsewhere; not repeated here.
    """
    return tuple(dict.fromkeys(i.strip() for i in raw.split(",") if i.strip()))


def load(project_root: Path | str) -> Sprint | None:
    """The sprint on disk, or None. None means no focus is declared, never a default one."""
    path = sprint_record(project_root)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    fields = {k: v.strip() for k, v in _FIELD_RE.findall(text)}
    if not fields.get("sprint"):
        return None
    verdicts = {}
    for line in text.splitlines():
        m = re.match(r"^\s*-\s+(B-\d+)\s*:\s*(\S+)", line)
        if m:
            verdicts[m.group(1)] = m.group(2)
    return Sprint(
        sprint_id=fields["sprint"],
        goal=fields.get("goal", ""),
        admitted=_ids(fields.get("admitted", "")),
        opened_by=fields.get("opened_by", ""),
        traces_to=_ids(fields.get("traces_to", "")),
        closed_by=fields.get("closed_by", ""),
        verdicts=verdicts or None,
    )


def open_sprint(project_root: Path | str, *, sprint_id: str, goal: str,
                admitted: list[str], opened_by: str,
                traces_to: list[str] | None = None) -> Sprint:
    """Declare the block. Refuses the three shapes that would make it decorative."""
    if not goal.strip():
        raise SprintInvalid(
            "a sprint needs a goal. A block of work with no goal is the task list this "
            "exists to stop being — every item justified, the set answering to nothing")
    if not admitted:
        raise SprintInvalid(
            "a sprint must admit at least one item. An empty block declares focus on "
            "nothing, and the band it feeds would order an empty set")
    if not _SIGNATURE_RE.match(opened_by.strip()):
        raise SprintInvalid(
            f"`opened_by` must be `human/<name>`, not {opened_by!r}. Focus declared by "
            "whoever wants to move on is not focus — the same argument `approved_by` "
            "rests on")
    existing = load(project_root)
    if existing is not None and existing.is_open:
        raise SprintInvalid(
            f"`{existing.sprint_id}` is still open. Two blocks of focus are no focus; "
            "close it, naming what each admitted item came to")
    if existing is not None:
        _archive(project_root, existing)

    s = Sprint(sprint_id=sprint_id, goal=goal.strip(), admitted=_ids(",".join(admitted)),
               opened_by=opened_by.strip(), traces_to=_ids(",".join(traces_to or [])))
    _write(project_root, s)
    return s


def admit(project_root: Path | str, item_id: str) -> Sprint:
    """Add an item to the open block — the refill, once something leaves.

    What DECIDED that something left is `halt_disposition`, and what picks the next
    candidate is `select_backlog_item.rank()`. This only records the admission, so the
    block's membership is a fact somebody can read rather than a side effect of a lane
    having started something.
    """
    s = load(project_root)
    if s is None or not s.is_open:
        raise SprintInvalid("no sprint is open, so nothing can be admitted to one")
    if item_id in s.admitted:
        return s
    grown = Sprint(sprint_id=s.sprint_id, goal=s.goal,
                   admitted=s.admitted + (item_id,), opened_by=s.opened_by,
                   traces_to=s.traces_to)
    _write(project_root, grown)
    return grown


def close(project_root: Path | str, *, closed_by: str,
          terminal: dict[str, str]) -> Sprint:
    """Close the block, refusing while any admitted item can still move.

    `terminal` maps admitted id to the registry's own terminal status. The caller reads it
    from the registry; this function does not parse the backlog, because a second reader of
    `status` is a second answer to what an item's state is.
    """
    s = load(project_root)
    if s is None or not s.is_open:
        raise SprintInvalid("no sprint is open")
    if not _SIGNATURE_RE.match(closed_by.strip()):
        raise SprintInvalid(
            f"`closed_by` must be `human/<name>`, not {closed_by!r}")

    unresolved = [i for i in s.admitted
                  if terminal.get(i) not in TERMINAL_STATUSES]
    if unresolved:
        raise SprintInvalid(
            "these admitted items carry no terminal status, so the block is not finished: "
            + ", ".join(unresolved)
            + ". An item that quietly leaves a sprint is indistinguishable from one that "
              "was never in it")

    closed = Sprint(sprint_id=s.sprint_id, goal=s.goal, admitted=s.admitted,
                    opened_by=s.opened_by, traces_to=s.traces_to,
                    closed_by=closed_by.strip(),
                    verdicts={i: terminal[i] for i in s.admitted})
    _write(project_root, closed)
    return closed


def rank_band(project_root: Path | str, item_id: str) -> int:
    """`0` when the open sprint admitted this item, `1` otherwise.

    A BAND, not a score. It sorts before status and after the two things that already
    outrank everything — an obligation, which costs while it waits, and an item some halt
    names as its cause. Focus does not outrank a live incident.

    With no open sprint every item returns the same value, so the order is exactly what it
    was. No sprint means no focus to honour, not a fabricated one.
    """
    s = load(project_root)
    if s is None or not s.is_open:
        return 0
    return 0 if item_id in s.admitted else 1


def _archive(project_root: Path | str, s: Sprint) -> Path:
    """Move a CLOSED sprint into the records tree before its slot is reused.

    The closed record is the only durable output a sprint has — the per-item verdicts are
    what `sprint_record`'s docstring calls the reason it is worth keeping. Opening the next
    one used to overwrite them, which was found by running the commands end to end and not
    by any unit test: every assertion about closing passed, and the file it wrote was gone
    one command later.

    Records, not state: once closed it is a dated artifact rather than something one
    session leaves for the next, which is the line `write_state_dir` draws.
    """
    from squad.paths import write_records_dir

    out = write_records_dir(project_root, "sprints") / f"{s.sprint_id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sprint_record(project_root).read_text(encoding="utf-8"),
                   encoding="utf-8")
    return out


def _write(project_root: Path | str, s: Sprint) -> None:
    path = sprint_record(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Sprint {s.sprint_id}",
        "",
        f"sprint: {s.sprint_id}",
        f"goal: {s.goal}",
        f"opened_by: {s.opened_by}",
        f"admitted: {', '.join(s.admitted)}",
    ]
    if s.traces_to:
        lines.append(f"traces_to: {', '.join(s.traces_to)}")
    if s.closed_by:
        lines += [f"closed_by: {s.closed_by}", "", "## Verdicts", ""]
        lines += [f"- {i}: {(s.verdicts or {}).get(i, '?')}" for i in s.admitted]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

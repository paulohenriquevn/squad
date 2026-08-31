#!/usr/bin/env python3
"""The declared phase plan, confronted with what actually ran.

WHY THIS IS THE PIECE THAT MATTERS
-----------------------------------
Emitting phase events buys a better record. It does not, by itself, buy a gate:
a stream can carry a published plan and an execution that contradicts it, with
nobody comparing the two.

Measured 2026-08-27 in `deer-workflow` (studied, never adopted), which has the
event stream and not the comparison: a Workflow declaring
`meta.phases = [Plan, Execute]`, running `Plan` and `Undeclared`, and never
entering `Execute`, exits 0. Its generator SKILL asks the agent to check the
match — item 3 of a 15-item list — which is the delegation this repository has
spent its history removing from its own gates.

So: `rules/cycle-phases.txt` declares the chain, `cycle_events.py` records what
ran, and this script is the half neither system had.

THE FOUR FINDINGS
-----------------
| Finding | Question it answers |
|---|---|
| `phase_ran_undeclared` | a phase emitted that the chain does not know |
| `phase_out_of_order` | a phase emitted before one it depends on, with no failed gate to send it back |
| `phase_advanced_over_blocking_verdict` | work continued past a FAIL |
| `phase_declared_never_ran` | a `required` phase left no event (`--expect-complete` only) |

The third is the one worth the movement. `check_upstream_gate.py` already
refuses `/review` when the `/code-quality` audit is FAIL_HARD — but it reads the
audit FILE, so it can only speak for the run that produced that file. The stream
records ORDER, which is what makes "review ran anyway, afterwards" answerable at
all.

WHAT IT REFUSES TO CONCLUDE
---------------------------
A missing `conditional` phase is never a finding. An item killed in DISCOVER
never reaches PLAN, and `cycle-discover.md` calls killing an item a SUCCESSFUL
outcome. A report that files those absences as debt earns the habit of being
ignored — the failure mode this repository has recorded more than once.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

_PHASES_RULE = "cycle-phases.txt"

#: Verdicts that forbid the chain from advancing. Drawn from the golden rules
#: rather than invented here: `code-quality-golden-rule.md § 1` blocks
#: downstream on FAIL_HARD / INVALID and admits FAIL_SOFT against an ADR, and
#: `cycle-review.md` blocks on NEEDS_FIXES. FAIL_SOFT is deliberately absent —
#: `check_upstream_gate.py` judges it with the ADRs in hand, which is more
#: information than a stream has.
#: Verdicts that mean a phase approved cleanly. Anything else — including a soft cap —
#: is a reason to work the phase again, which is why "sends work back" is a DIFFERENT
#: set from "forbids advancing".
#:
#: `FAIL_SOFT` is the case that made the distinction necessary. It does not forbid
#: advancing, so it is absent from `rules/blocking-verdicts.txt` and rightly so — but a session
#: that sees it and goes back to implement is doing the correct thing, and calling that
#: a defect punishes the chain for working.
#:
#: Defined by what passes rather than by listing every failure, because the failures
#: are open-ended and the approvals are not: a verdict nobody has enumerated should
#: count as a reason to redo, not as a clean pass.
_CLEAN_VERDICTS = frozenset({
    "PASS", "SHIPPABLE", "SHIPPABLE_WITH_CAVEATS", "PASS_WITH_CAVEATS",
    "READY_TO_MERGE", "READY_TO_MERGE_WITH_FOLLOWUPS", "RELEASED", "ACCEPTED",
    "ACCEPTED_WITH_CAVEATS", "VALIDATED", "ITEM_REGISTERED", "ITEM_SHIPPED",
    "OPPORTUNITY_COMPLETE", "PLAN_WRITTEN", "MILESTONE_RELEASED",
    # The Step 4 milestone. Absent from this set, a return after it read as rework
    # rather than disorder — the conservative error, but by omission rather than by
    # decision. It appeared in the stream on 2026-08-31 and in twelve rule files.
    "IMPLEMENTATION_COMPLETE",
})

_VERDICTS_RULE = "blocking-verdicts.txt"


def load_blocking_verdicts(project_root: Path) -> frozenset[str]:
    """Read `rules/blocking-verdicts.txt`.

    Read rather than hard-coded because the board holds the same list, and the two
    copies had already drifted: this checker called `implement FAIL` a verdict that
    forbids advancing while the board's panel called the same event unblocked.
    """
    project_root = Path(project_root)
    for relative in ("rules", ".claude/rules"):
        candidate = project_root / relative / _VERDICTS_RULE
        if candidate.is_file():
            path = candidate
            break
    else:
        raise FileNotFoundError(
            f"{_VERDICTS_RULE} not found under {project_root}. An absent list is not "
            "an empty one: nothing would ever be found to block, and the gate would "
            "pass every stream while checking nothing."
        )
    verdicts = {
        line.split("#", 1)[0].strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
    }
    verdicts.discard("")
    if not verdicts:
        raise ValueError(f"{_VERDICTS_RULE} names no verdict at all")
    return frozenset(verdicts)

_ANONYMOUS = "(no slug)"


@dataclass(frozen=True)
class DeclaredPhase:
    """One row of the declared chain."""

    name: str
    required: bool
    note: str
    position: int


@dataclass(frozen=True)
class DriftFinding:
    """One divergence between the declared chain and the stream."""

    kind: str
    slug: str
    detail: str


@dataclass
class DriftReport:
    """What the comparison saw. Counts print whether or not anything failed."""

    events_read: int = 0
    slugs_seen: list[str] = field(default_factory=list)
    findings: list[DriftFinding] = field(default_factory=list)


def load_declared_phases(project_root: Path) -> list[DeclaredPhase]:
    """Read `rules/cycle-phases.txt` in file order.

    Order is positional and stays that way: a phase list whose order came from a
    mapping would reorder between runs and make `phase_out_of_order` a coin flip.
    """
    project_root = Path(project_root)
    for relative in ("rules", ".claude/rules"):
        candidate = project_root / relative / _PHASES_RULE
        if candidate.is_file():
            path = candidate
            break
    else:
        raise FileNotFoundError(
            f"{_PHASES_RULE} not found under {project_root}. An absent declaration "
            "is not an empty plan: every stream would conform to it, and the gate "
            "would pass everything while checking nothing."
        )

    phases: list[DeclaredPhase] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [cell.strip() for cell in line.split("|")]
        if len(parts) < 2:
            raise ValueError(f"{_PHASES_RULE}: malformed line {raw!r}")
        name, requirement = parts[0], parts[1].lower()
        note = parts[2] if len(parts) > 2 else ""
        if requirement not in ("required", "conditional"):
            raise ValueError(
                f"{_PHASES_RULE}: unknown requirement {requirement!r} for {name!r}. "
                "Use `required` or `conditional` — a word nobody recognises would "
                "silently downgrade the phase it labels."
            )
        phases.append(DeclaredPhase(name, requirement == "required", note, len(phases)))

    if not phases:
        raise ValueError(f"{_PHASES_RULE} declares no phase at all")
    return phases


def _events_for(project_root: Path) -> list[dict]:
    tooling = Path(__file__).resolve().parent
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    from cycle_events import read_events

    return read_events(project_root)


def check_phase_drift(project_root: Path, *, expect_complete: bool = False) -> DriftReport:
    """Compare the declared chain with the emitted stream, per item."""
    project_root = Path(project_root)
    declared = load_declared_phases(project_root)
    blocking_verdicts = load_blocking_verdicts(project_root)
    by_name = {phase.name: phase for phase in declared}

    events = _events_for(project_root)
    report = DriftReport(events_read=len(events))

    # One stream carries every item's phases interleaved. Judging them as a
    # single sequence would report order violations that never happened.
    per_slug: dict[str, list[dict]] = {}
    for event in events:
        if event.get("type") != "cycle:phase:end":
            continue
        slug = (event.get("slug") or "").strip() or _ANONYMOUS
        per_slug.setdefault(slug, []).append(event)

    report.slugs_seen = sorted(per_slug)

    for slug, slug_events in per_slug.items():
        report.findings.extend(_judge_one(slug, slug_events, declared, blocking_verdicts, by_name, expect_complete))
    return report


def _judge_one(
    slug: str,
    events: list[dict],
    declared: list[DeclaredPhase],
    blocking_verdicts: frozenset[str],
    by_name: dict[str, DeclaredPhase],
    expect_complete: bool,
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    highest_position = -1
    #: Whether the phase before this one approved cleanly. A return after anything else
    #: is rework, not disorder.
    last_verdict_was_clean = True
    blocking: tuple[str, str] | None = None
    ran: set[str] = set()

    for event in events:
        cycle = (event.get("cycle") or "").strip()
        verdict = event.get("verdict")
        phase = by_name.get(cycle)

        if phase is None:
            findings.append(DriftFinding(
                "phase_ran_undeclared", slug,
                f"`{cycle}` emitted an event and {_PHASES_RULE} does not declare it. "
                "Either the chain gained a phase nobody wrote down, or a caller is "
                "naming its cycle something the pipeline does not recognise.",
            ))
            continue

        ran.add(cycle)

        if blocking is not None and phase.position > by_name[blocking[0]].position:
            findings.append(DriftFinding(
                "phase_advanced_over_blocking_verdict", slug,
                f"`{cycle}` ran after `{blocking[0]}` ended with `{blocking[1]}`. "
                "The chain advanced past a verdict that forbids advancing — the "
                "gate either did not run or its answer was overridden.",
            ))

        # Going BACK is not the same as going out of order, and treating them alike
        # reports the cycle working correctly as a defect.
        #
        # A gate that fails sends the work back: `code-quality` returns FAIL_SOFT and
        # `implement` runs again. That is the chain doing its job. What this check
        # exists for is the other shape — `review` running before anything was ever
        # implemented, a step skipped rather than repeated.
        #
        # The two are told apart by what came before the return: a blocking verdict
        # makes it rework, its absence makes it disorder. Measured on 2026-08-31, an
        # item went code-quality(FAIL_SOFT) -> implement, and the earlier rule would
        # have called that a defect.
        if phase.position < highest_position and last_verdict_was_clean:
            earlier = next(p.name for p in declared if p.position == highest_position)
            findings.append(DriftFinding(
                "phase_out_of_order", slug,
                f"`{cycle}` ran after `{earlier}`, which comes later in the chain, "
                "and no gate had failed — so this is a step out of sequence rather "
                "than work sent back to be redone.",
            ))
        highest_position = max(highest_position, phase.position)

        last_verdict_was_clean = (
            not isinstance(verdict, str) or verdict.upper() in _CLEAN_VERDICTS)

        if isinstance(verdict, str) and verdict.upper() in blocking_verdicts:
            blocking = (cycle, verdict.upper())

    if expect_complete:
        for phase in declared:
            if phase.required and phase.name not in ran:
                findings.append(DriftFinding(
                    "phase_declared_never_ran", slug,
                    f"`{phase.name}` is declared `required` and left no event. "
                    f"({phase.note})" if phase.note else
                    f"`{phase.name}` is declared `required` and left no event.",
                ))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Confront the declared phase chain with the emitted stream.",
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--expect-complete", action="store_true",
        help="the caller states this run is finished, which is the only context "
             "where a missing required phase means anything; mid-run it is just "
             "a run in progress",
    )
    args = parser.parse_args(argv)

    try:
        report = check_phase_drift(args.project_root, expect_complete=args.expect_complete)
    except (FileNotFoundError, ValueError) as error:
        print(f"phase-drift: {error}", file=sys.stderr)
        return 2

    plural = "" if report.events_read == 1 else "s"
    print(
        f"read {report.events_read} event{plural} across "
        f"{len(report.slugs_seen)} item(s): {len(report.findings)} divergence(s) "
        "between the declared chain and what ran"
    )
    for finding in report.findings:
        print(f"  [{finding.kind}] {finding.slug}: {finding.detail}")

    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())

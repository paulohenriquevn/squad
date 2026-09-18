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
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
from squad.paths import rules_dir  # noqa: E402 — post-bootstrap import

_PHASES_RULE = "cycle-phases.txt"

#: Verdicts that forbid the chain from advancing. Drawn from the golden rules
#: rather than invented here: `code-quality-golden-rule.md § 1` blocks
#: downstream on FAIL_HARD / INVALID and admits FAIL_SOFT against an ADR, and
#: `cycle-review.md` blocks on NEEDS_FIXES. FAIL_SOFT is deliberately absent —
#: `check_upstream_gate.py` judges it with the ADRs in hand, which is more
#: information than a stream has.
#: What "a phase approved cleanly" means is read from `rules/verdict-bands.txt`, not
#: held here.
#:
#: This WAS a frozenset in this file — a second list with no owner, which is exactly
#: the shape `blocking-verdicts.txt` exists to prevent, one file along. Measured
#: 2026-09-08: of 47 verdicts reachable in the stream, 14 were in the blocking list,
#: 16 in that frozenset, and 23 in neither. Since an unclassified verdict fell to the
#: not-clean default, the disorder check below switched itself off for half the
#: vocabulary with nothing in the output to notice — including three SUCCESS verdicts
#: (`PRE_RELEASED`, `ITEM_VERIFIED_LOCAL`, `PRODUCT_ALIGNED`).
#:
#: `FAIL_SOFT` remains the case that makes the distinction necessary. It does not
#: forbid advancing, so it is absent from `blocking-verdicts.txt` and rightly so — but
#: a session that sees it and goes back to implement is doing the correct thing, and
#: calling that a defect punishes the chain for working. It is `redo` in the registry
#: and blocks nothing: two axes, kept separate on purpose.
_BANDS_RULE = "verdict-bands.txt"


def load_clean_verdicts(project_root: Path) -> frozenset[str]:
    """Read the clean band from `rules/verdict-bands.txt`.

    An absent registry raises, on the same grounds as an absent blocking list: an
    empty set would make every verdict read as not-clean, and the disorder check
    would pass every stream while checking nothing.
    """
    project_root = Path(project_root)
    # `squad.paths.rules_dir` owns the order. Nine sites resolved this pair by hand
    # and they disagreed; see that function for which order wins and why.
    directory = rules_dir(project_root)
    candidate = directory / _BANDS_RULE if directory else None
    if candidate is not None and candidate.is_file():
        path = candidate
    else:
        raise FileNotFoundError(
            f"{_BANDS_RULE} not found under {project_root}. An absent registry is not "
            "an empty one: every verdict would read as not-clean and the out-of-order "
            "check would report nothing while appearing to run."
        )

    tooling = Path(__file__).resolve().parent.parent / "cycle"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    from verdict_bands import clean_verdicts

    return clean_verdicts(path)


_VERDICTS_RULE = "blocking-verdicts.txt"


def load_blocking_verdicts(project_root: Path) -> frozenset[str]:
    """Read `rules/blocking-verdicts.txt`.

    Read rather than hard-coded because the board holds the same list, and the two
    copies had already drifted: this checker called `implement FAIL` a verdict that
    forbids advancing while the board's panel called the same event unblocked.
    """
    project_root = Path(project_root)
    # `squad.paths.rules_dir` owns the order. Nine sites resolved this pair by hand
    # and they disagreed; see that function for which order wins and why.
    directory = rules_dir(project_root)
    candidate = directory / _VERDICTS_RULE if directory else None
    if candidate is not None and candidate.is_file():
        path = candidate
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
    #: The phase this one runs INSIDE, when it is not a sequential step of the chain.
    #: `code-quality` is invoked by `run_validation.py` during `implement`, which the
    #: declaration has always said in prose — and this gate, reading that same file,
    #: judged it by position anyway.
    nested_in: str = ""


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


#: `nested-in: implement` in the note column. A structured marker rather than a new
#: value in the requirement column, because four other readers assume that column holds
#: exactly `required` or `conditional` and a third word would change what they mean.
_NESTED_IN_RE = re.compile(r"\bnested-in:\s*([\w-]+)")


def load_declared_phases(project_root: Path) -> list[DeclaredPhase]:
    """Read `rules/cycle-phases.txt` in file order.

    Order is positional and stays that way: a phase list whose order came from a
    mapping would reorder between runs and make `phase_out_of_order` a coin flip.
    """
    project_root = Path(project_root)
    # `squad.paths.rules_dir` owns the order. Nine sites resolved this pair by hand
    # and they disagreed; see that function for which order wins and why.
    directory = rules_dir(project_root)
    candidate = directory / _PHASES_RULE if directory else None
    if candidate is not None and candidate.is_file():
        path = candidate
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
        nested = _NESTED_IN_RE.search(note)
        phases.append(DeclaredPhase(
            name, requirement == "required", note, len(phases),
            nested_in=nested.group(1) if nested else ""))

    if not phases:
        raise ValueError(f"{_PHASES_RULE} declares no phase at all")
    return phases


def _events_for(project_root: Path) -> list[dict]:
    tooling = Path(__file__).resolve().parent.parent / "cycle"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    from cycle_events import read_events

    return read_events(project_root)


def check_phase_drift(project_root: Path, *, expect_complete: bool = False) -> DriftReport:
    """Compare the declared chain with the emitted stream, per item."""
    project_root = Path(project_root)
    declared = load_declared_phases(project_root)
    blocking_verdicts = load_blocking_verdicts(project_root)
    clean = load_clean_verdicts(project_root)
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
        report.findings.extend(_judge_one(slug, slug_events, declared, blocking_verdicts, clean, by_name, expect_complete))
    return report


def _judge_one(
    slug: str,
    events: list[dict],
    declared: list[DeclaredPhase],
    blocking_verdicts: frozenset[str],
    clean_verdicts: frozenset[str],
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

        # A nested phase is not a step in the sequence, so neither ordering rule applies
        # to it. Measured on a consumer 2026-09-15: `code-quality` fires many times per
        # item around `implement`, which is `run_validation.py` invoking it exactly as
        # the declaration describes — and produced all 19 of that run's divergences,
        # 5 `phase_out_of_order` and 4 `phase_advanced_over_blocking_verdict`, none of
        # them real. A gate reporting the chain working correctly as a defect is worse
        # than no gate: it teaches its reader to skip the output.
        # `by_name.get(cycle, phase)` was the second half of this test and could only
        # ever return `phase`: it is bound eight lines up as `by_name.get(cycle)`, and
        # the branch is reached only after `if phase is None: continue`. The disjunct
        # asked the same question twice and read as though it covered a second case.
        if phase.nested_in:
            continue

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
            not isinstance(verdict, str) or verdict.upper() in clean_verdicts)

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
    parser.add_argument(
        "--root", "--project-root", dest="root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--expect-complete", action="store_true",
        help="the caller states this run is finished, which is the only context "
             "where a missing required phase means anything; mid-run it is just "
             "a run in progress",
    )
    args = parser.parse_args(argv)

    try:
        report = check_phase_drift(args.root, expect_complete=args.expect_complete)
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

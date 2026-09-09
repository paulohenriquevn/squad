#!/usr/bin/env python3
"""Where an item goes when a phase stops, now that no phase may address a person.

    python3 mechanisms/cycle/halt_disposition.py \\
        --phase implement --verdict FAIL_HARD --cause "the coverage gate rejects the slice"

## The signal this exists for

Ten places between DISCOVER and ACCEPTANCE were written as *escalate to the human*,
*surface to human*, *ask the human*. Each one is correct while somebody is coming, and
each one is a queue that stops for as long as nobody happens to look — the failure
`rules/autonomy-envelope.md` names in its own opening, distributed across ten phases
instead of one.

`rules/autonomy-envelope.md § The autonomous span` (2026-09-08) removed all ten. Removing
them is half a policy. A loop that cannot finish must still stop, a gate that fails must
still hold, and the item still has to go somewhere. This module decides where, so that
the same halt gets the same disposition in every phase that can produce one.

## The two dispositions, and why neither one waits

Both move the item OUT of the phase. Neither holds the session:

    RETURN_TO_QUEUE      the halt is work. The item goes back to the registry with the
                         cause named on it, and the queue works the cause — it puts a
                         named cause at the FRONT precisely because something is blocked
                         on it. This is the default.

    RETAIN_FOR_PERSON    the halt is a material impediment. The item goes back to the
                         registry behind a wall, and the queue takes the next item. The
                         person is reached through the registry, never by a session
                         standing still in front of them.

## The asymmetry with `delegated_decision.py`, which is deliberate

That module classifies a `blocked_by` line — prose a PERSON wrote in the registry — and
an unmatched one is RETAINED, because no match is not consent.

This module classifies a halt the SYSTEM emitted, with a verdict from a closed set. Here
an unmatched one is the queue's own work. Applying the registry's fail-safe would send
every ordinary rework loop to a person and rebuild, one layer down, exactly the halt this
policy exists to remove.

The two are not in conflict: they read different inputs, written by different authors,
and each one fails toward the answer that is safe for ITS input.

## What protects the default from being wrong

Nothing here has to classify free prose correctly on the first pass, and it must not
pretend to — a predecessor matched the substring "config" inside an item asking an
operator to provision a host and reported it resolvable.

So the default is backed by a MEASUREMENT rather than a match: an item the queue has
already returned twice for the same cause has demonstrated an impediment the queue cannot
move, and it is retained on that evidence. A wrong guess costs two passes and then
corrects itself; it does not cost a stopped queue.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from delegated_decision import DecisionClass, is_retained

#: The phases this mechanism speaks for. BRAINSTORM is the phase a person attends and
#: BACKLOG intake is the human's own judgement — for both, waiting for a person IS the
#: correct behaviour, so there is no autonomous disposition to compute and asking for one
#: is a category error at the call site.
SPAN = (
    "discover",
    "plan",
    "plan-alignment",
    "plan-confidence",
    "implement",
    "code-quality",
    "review",
    "release",
    "acceptance",
)

#: How many times the queue may return an item for the SAME cause before the impediment
#: is treated as demonstrated. Two is the smallest number that distinguishes "the fix did
#: not work" from "nothing the queue does will work": one return proves nothing, and a
#: third attempt would only produce the second identical failure again.
RETURN_LIMIT = 2

#: Material impediments, in the vocabulary a PHASE emits — English, and about tools,
#: targets and credentials rather than about registry prose. `delegated_decision.py` holds
#: the patterns for the other author.
#:
#: Ordered by class so a reader can see the whole of one class at once.
_IMPEDIMENT_PATTERNS: list[tuple[DecisionClass, str]] = [
    # ACCESS — a machine, credential or repository the process lacks.
    (DecisionClass.ACCESS, r"\bcredentials?\b[^.]{0,60}\b(absent|missing|unavailable|not\s+(?:held|available|set))"),
    (DecisionClass.ACCESS, r"\b(no|without|lacks?|missing|needs?)\b[^.]{0,40}\bcredentials?\b"),
    (DecisionClass.ACCESS, r"\bprovision(?:ed|ing)?\b[^.]{0,60}\b(host|vm|machine|instance|server)\b"),
    (DecisionClass.ACCESS, r"\b(another|a\s+new|an\s+additional)\s+(vm|host|machine|instance)\b"),
    (DecisionClass.ACCESS, r"\bno\s+host\s+is\s+provisioned\b"),
    (DecisionClass.ACCESS, r"\btarget\s+unreachable\b"),
    (DecisionClass.ACCESS, r"\b(repository|repo)\b[^.]{0,40}\b(cannot\s+reach|not\s+reachable|no\s+access)\b"),
    (DecisionClass.ACCESS, r"\brequires?\s+a\s+(repository|repo|machine|host)\b"),
    # ELAPSED — time must pass.
    (DecisionClass.ELAPSED, r"\b\d+\s+days?\b[^.]{0,40}\b(of\s+)?(data|series|accumulat|soak)"),
    (DecisionClass.ELAPSED, r"\b(needs?|requires?)\b[^.]{0,40}\b(time\s+to\s+pass|a\s+soak|a\s+deadline)\b"),
    (DecisionClass.ELAPSED, r"\baccumulated?\s+data\b"),
    # LIVENESS — a system must be standing, and is not.
    (DecisionClass.LIVENESS, r"\b(environment|system|service|target|api)\b[^.]{0,30}\b(is\s+)?down\b"),
    (DecisionClass.LIVENESS, r"\bnothing\s+is\s+standing\b"),
    (DecisionClass.LIVENESS, r"\bnot\s+(?:currently\s+)?running\b[^.]{0,40}\bcannot\s+be\s+started\b"),
    # GOVERNANCE — the item names autonomy itself as the bypass.
    (DecisionClass.GOVERNANCE, r"autonomous\s+execution[^.]{0,80}bypass"),
    (DecisionClass.GOVERNANCE, r"bypass[^.]{0,60}governance"),
]


class Disposition(Enum):
    """Where the item goes. Neither value leaves it inside the phase."""

    RETURN_TO_QUEUE = "return_to_queue"
    RETAIN_FOR_PERSON = "retain_for_person"


@dataclass(frozen=True)
class HaltDisposition:
    """What to do with an item whose phase stopped, and the reason a reader can check."""

    disposition: Disposition
    decision_class: str
    reason: str

    @property
    def awaits_person(self) -> bool:
        """Is a person the only one who can clear this?"""
        return self.disposition is Disposition.RETAIN_FOR_PERSON

    @property
    def returns_item_to_registry(self) -> bool:
        """Always true, and asserted rather than assumed.

        The span's promise is that a phase may stop but may not hold the session. Both
        dispositions write the item back to the registry; they differ only in whether a
        wall goes with it.
        """
        return True


def _match_impediment(cause: str) -> tuple[DecisionClass, str] | None:
    for klass, pattern in _IMPEDIMENT_PATTERNS:
        found = re.search(pattern, cause, re.IGNORECASE)
        if found:
            return klass, found.group(0)
    return None


def disposition_for(
    *,
    phase: str,
    verdict: str,
    cause: str,
    prior_returns: int = 0,
) -> HaltDisposition:
    """Decide where an item goes when `phase` stopped with `verdict` because of `cause`.

    `prior_returns` is how many times the queue has already returned THIS item for THIS
    cause. It is the backstop that keeps the default from being a guess — see the module
    docstring.
    """
    if phase.strip().lower() not in SPAN:
        raise ValueError(
            f"{phase!r} is outside the autonomous span {SPAN}. BRAINSTORM and BACKLOG "
            "intake belong to a person by design, so there is no disposition to compute."
        )
    if not cause or not cause.strip():
        raise ValueError(
            "a halt must state its cause — the phase knows why it stopped, and an item "
            "filed with a blank cause carries no evidence to work from"
        )

    # Impediments are tested FIRST and win outright, exactly as in the registry
    # classifier. A halt that is both a failing gate and a missing machine is a missing
    # machine: the gate can be fixed and the item still cannot move.
    matched = _match_impediment(cause)
    if matched is not None:
        klass, evidence = matched
        assert is_retained(klass), f"{klass} matched an impediment pattern but is delegable"
        return HaltDisposition(
            disposition=Disposition.RETAIN_FOR_PERSON,
            decision_class=klass.value,
            reason=(
                f"{klass.value}: the halt names something authority does not supply "
                f"({evidence!r}). Retained per rules/decision-delegation.txt."
            ),
        )

    if prior_returns >= RETURN_LIMIT:
        # Demonstrated rather than matched. The queue has now failed at this cause twice,
        # which is evidence of an impediment the patterns above did not name.
        return HaltDisposition(
            disposition=Disposition.RETAIN_FOR_PERSON,
            decision_class=DecisionClass.UNCLASSIFIED.value,
            reason=(
                f"the queue returned this item {prior_returns} times for the same cause "
                f"and it did not move — twice is the point at which an unnamed impediment "
                f"is demonstrated rather than guessed at ({verdict})"
            ),
        )

    return HaltDisposition(
        disposition=Disposition.RETURN_TO_QUEUE,
        decision_class="work",
        reason=(
            f"{verdict} in {phase} is a named cause, not an impediment: the queue works "
            "named causes first (rules/autonomy-envelope.md § A loop ran out of attempts)"
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decide where an item goes when a phase halts.",
    )
    parser.add_argument("--phase", required=True, help=f"one of {', '.join(SPAN)}")
    parser.add_argument("--verdict", required=True, help="the verdict the phase ended on")
    parser.add_argument("--cause", required=True, help="why the phase stopped, in prose")
    parser.add_argument(
        "--prior-returns",
        type=int,
        default=0,
        help="how many times the queue already returned this item for this cause",
    )
    parser.add_argument("--json", action="store_true", help="emit the verdict as JSON")
    args = parser.parse_args(argv)

    try:
        result = disposition_for(
            phase=args.phase,
            verdict=args.verdict,
            cause=args.cause,
            prior_returns=args.prior_returns,
        )
    except ValueError as exc:
        print(f"halt_disposition: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "disposition": result.disposition.value,
            "decision_class": result.decision_class,
            "awaits_person": result.awaits_person,
            "reason": result.reason,
        }, indent=2))
    else:
        print(f"{result.disposition.value} ({result.decision_class})")
        print(result.reason)

    # 0 = the queue continues on its own; 1 = a person is needed, through the registry.
    return 1 if result.awaits_person else 0


if __name__ == "__main__":
    sys.exit(main())

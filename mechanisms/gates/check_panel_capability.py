#!/usr/bin/env python3
"""Can a valid review panel be formed at all? Asked at intake, not per item.

    python3 mechanisms/gates/check_panel_capability.py
    python3 mechanisms/gates/check_panel_capability.py --panel rules/review-panel.txt --json

## The premise

`rules/review-panel.txt` declares who judges a DISCOVER opportunity and a PLAN
plan. This gate asks whether that declaration can actually produce a panel:

    - three reviewers, because the majority is 2 of 3 over a FULL panel;
    - at least one from a recognised family outside the kit's own, because
      correlated models share failure modes and a plausible fabrication that
      survives one tends to survive its siblings;
    - every non-`builtin` reviewer reachable on PATH, because declared and
      available are different claims.

## Why at intake

The failure this prevents is the one `check_merge_autonomy.py` prevents at the
other end of the chain: every item measured, planned, and then stopped at a panel
that was never formable. `review_panel.py` correctly refuses to tally an
incomplete panel, and under the autonomous span that refusal returns each item to
the registry as an `access` impediment — item by item, for a cause that was
knowable before the first one was selected. Announcing it here costs one read of
one file.

## Why an absent declaration is VIOLATED and a broken one is UNCHECKED

Absence is determinable from disk: a project that never configured a panel cannot
form one, and that is a fact. A file that exists and does not parse tested
nothing — reporting it as a pass would be the defect this repository's own CI
notes record about `check_xrefs.py` without `--strict`: a gate that looks, sees
nothing and approves produces confidence where there was no verification.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from enum import Enum
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cycle"))
from convene_panel import agents_dir, repo_root, resolve_seat, seat_family
from review_panel import (
    HOME_FAMILY,
    PANEL_SIZE,
    Seat,
    panel_size_for,
    parse_panel_phases,
    parse_roster,
    seats_for,
    single_family_waived,
)

#: Resolve an executable name to a path, or None. Injected so the gate is testable
#: without depending on what happens to be installed on the machine running it.
WhichFn = Callable[[str], "str | None"]

class PanelCapability(Enum):
    """Four facts with different audiences, deliberately not collapsed.

    `VIOLATED` and `UNREACHABLE` were one value until 2026-09-08, and the conflation
    had a measured cost: with a PATH holding no `codex`, the gate reported VIOLATED,
    so `verify_ecosystem` — which the CI runs — would have gone red on a GitHub runner
    for a repository with nothing wrong with it. A declaration that cannot form a panel
    on ANY machine is the repository's defect; a reviewer missing on THIS machine is not.
    """

    HOLDS = "holds"
    #: The declaration itself cannot form a panel — a gated phase without exactly
    #: three seats, or three seats from one family. Fails everywhere, CI included.
    VIOLATED = "violated"
    #: The registry does not parse. Nothing was tested, and that is not a pass.
    UNCHECKED = "unchecked"
    #: The declaration is valid and a declared reviewer cannot be reached HERE — no
    #: such agent in this project, or no such binary on PATH. The operator about to
    #: run the chain needs this; the CI checking the repository does not.
    UNREACHABLE = "unreachable"

    @property
    def exit_code(self) -> int:
        return {"holds": 0, "violated": 1, "unchecked": 2, "unreachable": 3}[self.value]


def default_panel_path() -> Path:
    return Path(__file__).resolve().parents[2] / "rules" / "review-panel.txt"


#: Why each seat could not be filled on the LAST run: `(phase, agent, reason)`. A
#: module-level record rather than a changed return type — `PanelCapability` is what six
#: readers compute from, and widening it to a tuple would rewrite all of them to carry a
#: detail only `main` prints. `unfillable_seats()` is the addition.
unfillable: list[tuple[str, str, str]] = []


def unfillable_seats() -> list[tuple[str, str, str]]:
    """`(phase, agent, reason)` for every seat the last check could not fill."""
    return list(unfillable)


#: CLIs that put a non-Anthropic family within reach. Deliberately short: each entry
#: is a binary whose presence REFUTES "no provider is configured", so a wrong one turns
#: an honest waiver into a false alarm — and a gate that cries wolf gets deleted.
PROVIDER_BINARIES = ("codex", "gemini", "ollama")

#: The one waiver reason that is a checkable claim about THIS MACHINE. Anything else —
#: a broken CLI, an expired key, a model the account refuses — is a claim about the
#: provider's BEHAVIOUR, and probing that costs a live call on every gate run.
_CLAIMS_NO_PROVIDER = re.compile(r"\bno\s+(?:\S+\s+){0,3}provider\b", re.IGNORECASE)


def waiver_contradicted(reason: str, *, which=shutil.which) -> str:
    """The binary that refutes this waiver reason, or "" when nothing refutes it.

    A waiver carries a reason so a reader can weigh it. Nothing re-read that reason, so
    it outlived the fact it named: it said no non-Anthropic provider was configured for
    nine days while `codex` sat on PATH, authenticated, with `judge-codex` installed
    (measured 2026-09-21). The panel was single-family for a real reason the whole time
    — the CLI is too old for every model the account exposes — and the file named the
    wrong one, which is the difference between a cost somebody chose and one nobody saw.

    Only the "no provider" class is decided here. A reason naming a broken CLI is not
    refuted by that CLI being present: its presence is the reason's own premise.
    """
    if not _CLAIMS_NO_PROVIDER.search(reason or ""):
        return ""
    for binary in PROVIDER_BINARIES:
        if which(binary):
            return binary
    return ""


def check_panel_capability(
    panel_path: Path | None = None,
    *,
    which: WhichFn | None = None,
    project: Path | None = None,
    config_dir: Path | None = None,
) -> PanelCapability:
    """Can a panel be convened for EVERY phase a panel gates?

    Per phase, not over the whole file. A roster holding six valid seats can still
    leave one gated phase with two, and a global count would call that formable —
    then every item in that phase would halt on an `access` impediment for a cause
    knowable before the first was selected, which is the entire point of asking here.
    """
    named_by_caller = panel_path is not None
    path = panel_path or default_panel_path()
    resolve = which or shutil.which
    agents = agents_dir(project or repo_root())

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        # A project with no panel declaration cannot form a panel. Determinable,
        # therefore a fact rather than a failure to look.
        #
        # That argument holds for the DEFAULT path and only there. When the CALLER
        # named the roster, an unreadable file says nothing about the project's panel
        # — it says the gate was pointed somewhere else, and the two were collapsed
        # until 2026-09-21. Measured that day: `--panel discover` (a phase name where a
        # path belongs) printed PREMISE VIOLATED, naming `rules/review-panel.txt` as
        # the file that cannot form a panel while never having opened it. The roster
        # it accused HOLDS. `check_auditor_coverage.py` already refuses this shape on
        # its own side — "the gate was pointed at the wrong tree — it has NOT
        # established that no audit is required" — and the sentence governs both: an
        # inability to measure must not become a passing measurement, and it must not
        # become a failing one either.
        return PanelCapability.UNCHECKED if named_by_caller else PanelCapability.VIOLATED

    try:
        gated = parse_panel_phases(text)
        by_phase = {ph: seats_for(text, ph) for ph in gated}
    except ValueError:
        return PanelCapability.UNCHECKED

    if not gated:
        return PanelCapability.VIOLATED

    # A project may declare, in the roster the installer preserves, that it runs a
    # one-family panel and what that costs it. The kit's rule does not move: which
    # models a project can reach is not the kit's business, and a project with no
    # second provider chooses between running no panel and running one that says what
    # it is worth. DECLARED, never inferred — a roster that happens to be one family
    # and one that was meant to be read the same on disk, and only one is a decision.
    waived, _reason = single_family_waived(text)

    for _phase, seats in by_phase.items():
        if len(seats) != panel_size_for(_phase):
            return PanelCapability.VIOLATED
        # The family rule guards a MAJORITY, and a single seat has none.
        #
        # Its reason is that correlated models are fooled together: "a plausible fabrication that
        # survives one tends to survive its siblings". That is an argument about two of three
        # agreeing, and it does not reach a phase with one reviewer, where the guarantee that
        # matters is a different one — NOT THE AUTHOR — and is enforced immediately above.
        #
        # Measured 2026-09-23, because the opposite claim was available and had to be tested: two
        # same-family sessions reviewing each other's work that day refuted three claims between
        # them, and one of those refutations found a root cause neither had seen. Same-family
        # review is not empty review; it is correlated VOTING that the rule exists to prevent.
        #
        # A single-seat phase that COULD be filled from another family still should be, and the
        # signature vocabulary keeps the distinction visible either way: `judge/…` and `human/…`
        # are different claims to any reader, and `score_alignment` reports the weakest of a set.
        # The family a seat WILL RUN, not the one its roster row names. For a `builtin`
        # seat the roster's model is a claim about a Claude sub-agent, and the agent's
        # own frontmatter is what selects the model — see `seat_family`. This gate
        # asserted diversity on the unread string for as long as it existed.
        families = {seat_family(s, config_dir=config_dir)[0] for s in seats}
        if not (families - {HOME_FAMILY, "unknown"}) and not waived and len(seats) > 1:
            return PanelCapability.VIOLATED

    # Reachability is checked LAST and reported separately, because it is the only
    # question here whose answer depends on the machine rather than on the repository.
    #
    # EVERY unfillable seat, with the reason `resolve_seat` gave. This returned on the
    # first one and discarded the string it had just been handed — `no agent \`X\` in
    # <dir>`, `plugin \`X\` is not installed`, `\`X\` is not on PATH` — so the operator
    # read "no such agent, or no such binary on PATH" and had to go find out which, for
    # a seat the gate had already identified.
    unfillable.clear()
    for phase, seats in by_phase.items():
        for seat in seats:
            reason = resolve_seat(seat, agents=agents, which=resolve,
                                  config_dir=config_dir)
            if reason:
                # The panel is short a member here. When it is the orthogonal one, this
                # also removes the only thing the diversity rule was protecting — so it
                # still stops a real run, it just is not the repository's fault.
                unfillable.append((phase, seat.agent, reason))
    if unfillable:
        return PanelCapability.UNREACHABLE

    return PanelCapability.HOLDS


_MESSAGES = {
    PanelCapability.HOLDS: (
        "A panel is DECLARED for {phases}: {n} seats across {fams}, every non-builtin "
        "binary present on PATH.\n"
        "  This checks the BINARY, not the model behind it. `shutil.which` was the only "
        "probe — this gate runs nothing — so a seat whose CLI resolves and whose model "
        "is unavailable reads as reachable here and terminates when dispatched.\n"
        "  Measured on a consumer 2026-09-16: this line printed `all reachable` in the "
        "same minute a `gpt-5-codex` seat terminated with \"the selected model may not "
        "exist or you may not have access\" — after two sibling seats had already been "
        "dispatched and spent. Every gated phase in that project routes an orthogonal "
        "seat to that model, so no panel could reach 2-of-3, and it was announced as "
        "HOLDS.\n"
        "  This is the PREMISE gate. `cycle-plan.md` gives its purpose as \"a violated "
        "premise, reported before the first item is selected\" — so an overclaim here "
        "costs the whole run, not one seat."
    ),
    PanelCapability.VIOLATED: (
        "PREMISE VIOLATED — no valid review panel can be formed from "
        "rules/review-panel.txt.\n"
        "\n"
        "Each gated phase needs exactly {size} seats with at least one from a "
        "recognised family outside `{home}`. A `builtin` seat must name an agent "
        "this project has; any other must be on PATH.\n"
        "\n"
        "  Without it every item would be measured, planned, and returned to the\n"
        "  registry at a panel that was never formable — one `access` impediment per\n"
        "  item, for a cause knowable before the first was selected.\n"
        "\n"
        "rules/review-panel.txt records why the panel must not be one family."
    ),
    PanelCapability.UNREACHABLE: (
        "NOT FORMABLE HERE — the declaration is valid and a declared reviewer is not on "
        "reachable from this project — no such agent, or no such binary on PATH.\n"
        "\n"
        "  The panel would be short a member, and if the missing one is the orthogonal\n"
        "  reviewer, the diversity rule has nothing left to protect. A run started now\n"
        "  would return every item to the registry with an `access` impediment.\n"
        "\n"
        "This is NOT a repository defect, which is why it is reported apart from "
        "VIOLATED: `rules/review-panel.txt` is fine and this machine is missing a tool."
    ),
    PanelCapability.UNCHECKED: (
        "NOT CHECKED — the roster could not be read: it does not parse, or the "
        "path this gate was given is not there.\n"
        "\n"
        "This is not a pass, and it is not a VIOLATED either. A reviewer row that "
        "announces a reviewer without describing one would silently shrink the "
        "panel, so it is refused rather than skipped — and a roster the caller "
        "named and that is absent establishes nothing about the project's panel, "
        "so it must not be reported as one that cannot be formed."
    ),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check that a review panel can be formed.")
    ap.add_argument("--panel", type=Path, default=None,
                    help="PATH to the roster file, not a phase name "
                         "(default: rules/review-panel.txt)")
    # `--root`, per the contract in `_contract.py`: a caller that does not know
    # which gate it is talking to passes this and it works. This gate resolved the
    # tree implicitly from the working directory, so it could not be pointed at one.
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    path = args.panel or default_panel_path()
    result = check_panel_capability(path)

    seats: list[Seat] = []
    gated: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
        seats = parse_roster(text)
        gated = parse_panel_phases(text)
    except (OSError, ValueError):
        pass

    message = _MESSAGES[result].format(
        n=len(seats),
        phases=", ".join(gated) or "no phase",
        fams=", ".join(sorted({s.family for s in seats})) or "nothing",
        size=PANEL_SIZE,
        home=HOME_FAMILY,
    )

    # The waiver never passes silently. A panel of one family HOLDS only because this
    # project declared it does, and the line that reports HOLDS has to carry that or a
    # reader takes it for a panel that spans families.
    _waived, _reason = (False, "")
    try:
        _waived, _reason = single_family_waived(text)
    except (OSError, ValueError, NameError):  # pragma: no cover - text may be unread
        pass
    if _waived and result is PanelCapability.HOLDS:
        message += (
            "\n\n  SINGLE FAMILY, BY DECLARATION. `rules/review-panel.txt` waives the "
            f"cross-family requirement: {_reason}.\n"
            "  Correlated reviewers share failure modes — a plausible fabrication that "
            "survives one tends to survive its siblings — so an APPROVED from this panel "
            "is a weaker claim than one spanning two families, and `review_panel.tally()` "
            "carries the same note into every outcome. Remove both keys from the roster "
            "the day a second provider is reachable."
        )
        _refuted_by = waiver_contradicted(_reason)
        if _refuted_by:
            message += (
                f"\n\n  THE DECLARED REASON IS REFUTED HERE: it claims no provider is "
                f"configured, and `{_refuted_by}` is on PATH. The panel may still be "
                "single-family for a real reason — but this file no longer names it, so "
                "nobody can weigh what the waiver costs. Re-measure and rewrite the "
                "reason, or fill the seat."
            )

    if result is PanelCapability.UNREACHABLE and unfillable_seats():
        message += "\n\nWhich seats, and why:\n" + "\n".join(
            f"  {phase}/{agent}: {reason}" for phase, agent, reason in unfillable_seats())

    # Resolved once per seat, here, because `main` has no `config_dir` of its own:
    # the check takes one for testability and defaults to this machine's. Calling
    # `seat_family` inline in the payload read a name that does not exist in this
    # scope, and the gate died with a NameError under `--json` — the shape the
    # report is meant to prevent, in the reporter.
    verified = {id(s): seat_family(s) for s in seats}

    if args.json:
        print(json.dumps({
            "result": result.value,
            "unfillable_seats": [{"phase": p, "agent": a, "reason": r}
                                 for p, a, r in unfillable_seats()],
            "panel_phases": gated,
            "seats": [{"phase": s.phase, "agent": s.agent, "model": s.model,
                       # The verified family and where it was established — the same
                       # answer the verdict above was computed from. Reporting the
                       # roster's string beside a verdict derived from the frontmatter
                       # is two readers of one table, which is the defect this gate
                       # was built to stop happening elsewhere.
                       "family": verified[id(s)][0],
                       "family_source": verified[id(s)][1],
                       "via": s.invocation} for s in seats],
            "families": sorted({fam for fam, _src in verified.values()}),
            "message": message,
        }, indent=2))
    else:
        print(f"review panel: {result.value.upper()}")
        print(message)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())

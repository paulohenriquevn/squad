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
import shutil
import sys
from enum import Enum
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cycle"))
from convene_panel import agents_dir, repo_root, resolve_seat
from review_panel import (
    HOME_FAMILY,
    PANEL_SIZE,
    Seat,
    parse_panel_phases,
    parse_roster,
    seats_for,
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


def check_panel_capability(
    panel_path: Path | None = None,
    *,
    which: WhichFn | None = None,
    project: Path | None = None,
) -> PanelCapability:
    """Can a panel be convened for EVERY phase a panel gates?

    Per phase, not over the whole file. A roster holding six valid seats can still
    leave one gated phase with two, and a global count would call that formable —
    then every item in that phase would halt on an `access` impediment for a cause
    knowable before the first was selected, which is the entire point of asking here.
    """
    path = panel_path or default_panel_path()
    resolve = which or shutil.which
    agents = agents_dir(project or repo_root())

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        # A project with no panel declaration cannot form a panel. Determinable,
        # therefore a fact rather than a failure to look.
        return PanelCapability.VIOLATED

    try:
        gated = parse_panel_phases(text)
        by_phase = {ph: seats_for(text, ph) for ph in gated}
    except ValueError:
        return PanelCapability.UNCHECKED

    if not gated:
        return PanelCapability.VIOLATED

    for seats in by_phase.values():
        if len(seats) != PANEL_SIZE:
            return PanelCapability.VIOLATED
        families = {s.family for s in seats}
        if not (families - {HOME_FAMILY, "unknown"}):
            return PanelCapability.VIOLATED

    # Reachability is checked LAST and reported separately, because it is the only
    # question here whose answer depends on the machine rather than on the repository.
    for seats in by_phase.values():
        for seat in seats:
            # The panel is short a member here. When it is the orthogonal one, this
            # also removes the only thing the diversity rule was protecting — so it
            # still stops a real run, it just is not the repository's fault.
            if resolve_seat(seat, agents=agents, which=resolve):
                return PanelCapability.UNREACHABLE

    return PanelCapability.HOLDS


_MESSAGES = {
    PanelCapability.HOLDS: (
        "A panel can be formed for {phases}: {n} seats across {fams}, all reachable."
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
        "NOT CHECKED — rules/review-panel.txt exists and does not parse.\n"
        "\n"
        "This is not a pass. A reviewer row that announces a reviewer without "
        "describing one would silently shrink the panel, so it is refused rather "
        "than skipped."
    ),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check that a review panel can be formed.")
    ap.add_argument("--panel", type=Path, default=None)
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

    if args.json:
        print(json.dumps({
            "result": result.value,
            "panel_phases": gated,
            "seats": [{"phase": s.phase, "agent": s.agent, "model": s.model,
                       "family": s.family, "via": s.invocation} for s in seats],
            "families": sorted({s.family for s in seats}),
            "message": message,
        }, indent=2))
    else:
        print(f"review panel: {result.value.upper()}")
        print(message)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())

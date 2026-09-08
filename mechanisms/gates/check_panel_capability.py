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
from review_panel import HOME_FAMILY, PANEL_SIZE, family_of

#: Resolve an executable name to a path, or None. Injected so the gate is testable
#: without depending on what happens to be installed on the machine running it.
WhichFn = Callable[[str], "str | None"]

#: A reviewer that runs as a sub-agent in this session needs no binary. Requiring
#: one would fail every panel on a machine that has everything it needs.
BUILTIN = "builtin"


class PanelCapability(Enum):
    HOLDS = "holds"
    VIOLATED = "violated"
    UNCHECKED = "unchecked"

    @property
    def exit_code(self) -> int:
        return {"holds": 0, "violated": 1, "unchecked": 2}[self.value]


def default_panel_path() -> Path:
    return Path(__file__).resolve().parents[2] / "rules" / "review-panel.txt"


def parse_reviewers(text: str) -> list[tuple[str, str, str]]:
    """(id, model, invocation) for every declared reviewer.

    Raises ValueError on a line that announces a reviewer and does not describe
    one — a half-written row must not silently shrink the panel.
    """
    rows: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or not line.startswith("reviewer"):
            continue
        _, _, value = line.partition("=")
        parts = [p.strip() for p in value.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"malformed reviewer row: {raw.strip()!r}")
        rows.append((parts[0], parts[1], parts[2]))
    return rows


def check_panel_capability(
    panel_path: Path | None = None,
    *,
    which: WhichFn | None = None,
) -> PanelCapability:
    """Can the declared panel be convened?"""
    path = panel_path or default_panel_path()
    resolve = which or shutil.which

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        # A project with no panel declaration cannot form a panel. Determinable,
        # therefore a fact rather than a failure to look.
        return PanelCapability.VIOLATED

    try:
        reviewers = parse_reviewers(text)
    except ValueError:
        return PanelCapability.UNCHECKED

    if len(reviewers) < PANEL_SIZE:
        return PanelCapability.VIOLATED

    families = {family_of(model) for _, model, _ in reviewers}
    if not (families - {HOME_FAMILY, "unknown"}):
        return PanelCapability.VIOLATED

    for _, model, invocation in reviewers:
        if invocation == BUILTIN:
            continue
        if resolve(invocation) is None:
            # An unreachable reviewer shrinks the panel below its size. When it is
            # the orthogonal one, it also removes the only thing the diversity rule
            # was protecting.
            return PanelCapability.VIOLATED

    return PanelCapability.HOLDS


_MESSAGES = {
    PanelCapability.HOLDS: (
        "A panel can be formed: {n} reviewers across {fams}, all reachable."
    ),
    PanelCapability.VIOLATED: (
        "PREMISE VIOLATED — no valid review panel can be formed from "
        "rules/review-panel.txt.\n"
        "\n"
        "DISCOVER and PLAN each need {size} reviewers with at least one from a "
        "recognised family outside `{home}`, and every non-builtin reviewer must be on "
        "PATH.\n"
        "\n"
        "  Without it every item would be measured, planned, and returned to the\n"
        "  registry at a panel that was never formable — one `access` impediment per\n"
        "  item, for a cause knowable before the first was selected.\n"
        "\n"
        "rules/review-panel.txt records why the panel must not be one family."
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

    reviewers: list[tuple[str, str, str]] = []
    try:
        reviewers = parse_reviewers(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass

    message = _MESSAGES[result].format(
        n=len(reviewers),
        fams=", ".join(sorted({family_of(m) for _, m, _ in reviewers})) or "nothing",
        size=PANEL_SIZE,
        home=HOME_FAMILY,
    )

    if args.json:
        print(json.dumps({
            "result": result.value,
            "reviewers": [{"id": i, "model": m, "via": v} for i, m, v in reviewers],
            "families": sorted({family_of(m) for _, m, _ in reviewers}),
            "message": message,
        }, indent=2))
    else:
        print(f"review panel: {result.value.upper()}")
        print(message)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())

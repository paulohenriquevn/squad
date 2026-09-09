"""A contract may attribute a verdict to a sibling cycle that never emits it.

Measured 2026-09-07: `cycle-idea-to-release.md` stated that *"`cycle-maintenance`
emits `ROADMAP_BLOCKED`"*. `ROADMAP_BLOCKED` appears zero times in
`cycle-maintenance.md`; the token that cycle actually emits is `BACKLOG_BLOCKED`,
declared in three places with a table row explaining why it is not `BACKLOG_EMPTY`.
`ROADMAP_BLOCKED` is residue from the rename of `cycle-roadmap` to
`cycle-maintenance` — the same rename that `check_xrefs.py` Check 8 exists because
of, surviving one layer deeper: Check 8 validates that the CYCLE named exists, and
never asks whether the TOKEN attributed to it does.

This is worse than a dangling reference. A reader wiring an orchestrator against
`ROADMAP_BLOCKED` gets a branch that is structurally correct, passes every existing
gate, and can never fire — the upstream cycle has no path that emits that string.

WHAT THIS PROVES, AND WHAT IT DOES NOT
--------------------------------------
It proves the token a contract attributes to a named cycle appears in that cycle's
own contract. It does not prove the cycle can reach it at runtime — that is
`check_orphan_verdicts.py`'s question, and a grep cannot answer it either.
"""
from __future__ import annotations

import re
from pathlib import Path

_RULES = Path(__file__).resolve().parent.parent / "rules"

#: "`cycle-x` emits `TOKEN`", "`cycle-x` returns `TOKEN`", and the reversed
#: "`TOKEN` ... emitted by `cycle-x`". The window is deliberately short: a token and
#: a cycle name in the same sentence is an attribution, in the same paragraph is not.
_ATTRIBUTION_RE = re.compile(
    r"`cycle-([a-z][a-z0-9-]*)`[^.`\n]{0,40}?\b(?:emits|returns|reports)\b[^.`\n]{0,40}?"
    r"`([A-Z][A-Z0-9_]{3,})`"
)


def _attributions() -> list[tuple[Path, str, str]]:
    out: list[tuple[Path, str, str]] = []
    for rule in sorted(_RULES.glob("*.md")):
        for cycle, token in _ATTRIBUTION_RE.findall(rule.read_text(encoding="utf-8-sig")):
            out.append((rule, cycle, token))
    return out


def test_the_sweep_finds_attributions_to_check() -> None:
    """Vacuity is a failure. A regex that matches nothing reports green forever."""
    assert _attributions(), "no verdict attributions matched — the pattern has rotted"


def test_every_attributed_verdict_appears_in_the_cycle_it_is_attributed_to() -> None:
    offenders = []
    for rule, cycle, token in _attributions():
        target = _RULES / f"cycle-{cycle}.md"
        if not target.is_file():
            continue  # Check 8 in check_xrefs.py owns the missing-cycle case
        if f"`{token}`" not in target.read_text(encoding="utf-8-sig"):
            offenders.append(f"{rule.name} attributes `{token}` to `cycle-{cycle}`, "
                             f"which never names it")
    assert offenders == [], offenders

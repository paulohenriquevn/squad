"""A cap the golden rule declares must be one the scorer can actually emit.

`rules/plan-confidence-golden-rule.md` is the authority on which caps exist: its
table is where a threshold is declared, and `check_adr_completeness.py` points at
it to explain why a reported field is not a gate. Nothing read that table back.

The existing guard, `test_documented_identifiers_are_the_emitted_ones`, reads
`SKILL.md § Hard Caps` — which names two of the eight ids the rule declares. The
six others were declared and unchecked, and a declared cap nobody can emit is the
defect class this kit has now hit repeatedly: the rule reads as enforced, the
report never carries the id, and an empty match reads as "the cap never fired".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RULE = _ROOT / "rules" / "plan-confidence-golden-rule.md"

sys.path.insert(0, str(_ROOT / "tests"))
from test_documented_identifiers_are_the_emitted_ones import (  # noqa: E402
    _emitted_identifiers,
)

_DECLARED_RE = re.compile(r"[Ss]table id(?:entifier)?:\s*`([a-z0-9_]+)`")


def _declared_in_the_rule() -> set[str]:
    return set(_DECLARED_RE.findall(_RULE.read_text(encoding="utf-8")))


def test_the_rule_declares_at_least_the_caps_it_used_to() -> None:
    """A row losing its `Stable id:` would empty the set and pass vacuously."""
    assert len(_declared_in_the_rule()) >= 8


def test_every_declared_cap_is_emittable() -> None:
    orphans = sorted(_declared_in_the_rule() - _emitted_identifiers())
    assert not orphans, (
        "declared in rules/plan-confidence-golden-rule.md, emitted by nothing: "
        + ", ".join(orphans)
        + " — the rule reads as enforced and the id never reaches hard_caps_triggered"
    )

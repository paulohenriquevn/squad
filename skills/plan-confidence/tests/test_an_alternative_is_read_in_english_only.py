"""`rules/english-only.md` says this checker reads English only, and it still accepted
six Portuguese phrases as evidence an ADR had weighed an alternative. A rationale
written in Portuguese satisfied the alternatives check while breaking the rule that
governs the plan it sits in (#216).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))

from check_adr_completeness import check_adr_completeness  # noqa: E402 — post-bootstrap import

_PLAN = """# Plan

## ADRs

### D1 — Use a context rather than a module variable

**Decision** — a React context.

**Rationale** — {rationale}

**Consequences** — one extra element in the SSR tree.
"""


def _ratio(tmp_path: Path, rationale: str) -> float:
    plan = tmp_path / "plan.md"
    plan.write_text(_PLAN.format(rationale=rationale), encoding="utf-8")
    return check_adr_completeness(plan).completeness_ratio


@pytest.mark.parametrize("rationale", [
    "Rejeitada a alternativa de variável de módulo.",  # english-only: the phrase under test
    "Usamos contexto em vez de variável de módulo.",  # english-only: the phrase under test
    "Contexto ao invés de variável global.",  # english-only: the phrase under test
])
def test_a_portuguese_alternative_is_not_evidence(tmp_path: Path, rationale: str) -> None:
    assert _ratio(tmp_path, rationale) < 1.0


def test_an_english_alternative_still_is(tmp_path: Path) -> None:
    assert _ratio(tmp_path, "A module variable was rejected: it leaks across requests.") == 1.0

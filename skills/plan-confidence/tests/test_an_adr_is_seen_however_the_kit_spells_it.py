"""`check_adr_completeness` saw no ADR, so the cap that guards them had no subject.

`ADR_HEADER_RE` matched `^###\\s+(D\\d+)`, and the plan template does prescribe `D1, D2, …`.
But the rest of the kit writes `ADR-N` — `rules/cycle-code-quality.md`,
`rules/cycle-rule-schema.md`, `docs/ADR/0025-…` — and authors followed the majority. Measured
across one consumer's plans: **`### ADR-N` 96 times against `### D1` five**. So the kit taught one
spelling everywhere and matched the other.

The consequence, proven rather than argued. `plan-confidence-golden-rule.md:42` declares:

    | ADR without alternatives in Rationale → score ≤ 70 | M2 — check_adr_completeness.py |

Build the worst case — one ADR, zero rejected alternatives — and it reports
`total_adrs=0, completeness_ratio=1.0`. **A plan whose ADRs reject nothing passes that gate in
silence, with a perfect ratio.** A gate reporting itself applied while applying nothing is the
class this kit exists to catch, pointed inward, and the second instance in one day: the first was
the template prescribing DoD headings the criteria checker could not match (#186).

Found by the ORTHOGONAL seat of a plan panel — the reviewer from outside the kit's model family
approved the artifact and brought back a defect of the kit that neither same-family seat saw.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))

from check_adr_completeness import ADR_HEADER_RE, check_adr_completeness  # noqa: E402

_ONE_ADR_NO_ALTERNATIVE = """# Plan

## ADRs

### {header} — Use a context rather than a module variable

**Decision** — a React context.

**Rationale** — it is the mechanism React has for this.

**Consequences** — one extra element in the SSR tree.
"""


@pytest.mark.parametrize("header", ["D1", "ADR-1", "ADR-12", "D12"])
def test_both_spellings_are_seen(header: str) -> None:
    assert ADR_HEADER_RE.search(f"### {header} — Something"), (
        f"`### {header} —` is a form this kit's own documents write and the pattern misses it")


@pytest.mark.parametrize("header", ["D1", "ADR-1"])
def test_an_adr_with_no_alternative_is_counted_and_capped(tmp_path: Path, header: str) -> None:
    """The subject the cap needs. With `total_adrs=0` the cap cannot fire at all."""
    plan = tmp_path / f"{header}-plan.md"
    plan.write_text(_ONE_ADR_NO_ALTERNATIVE.format(header=header), encoding="utf-8")

    report = check_adr_completeness(plan)

    assert report.total_adrs == 1, (
        f"an ADR headed `{header}` was not counted, so `adr_without_alternatives` has no "
        f"subject and a plan whose ADRs reject nothing passes with a perfect ratio")
    assert report.completeness_ratio < 1.0, (
        "the ADR names no rejected alternative and the ratio says it is complete")


def test_prose_that_is_not_an_adr_heading_is_not_counted(tmp_path: Path) -> None:
    """The control. A pattern widened until it matches anything measures nothing."""
    plan = tmp_path / "p.md"
    plan.write_text("# Plan\n\n## ADRs\n\n### Decisions we made — narrative\n\n- a thing\n",
                    encoding="utf-8")

    assert check_adr_completeness(plan).total_adrs == 0

"""The alignment score, which decides whether an item may be built at all.

WHY THESE TESTS MATTER MORE THAN MOST
-------------------------------------
This score is a gate on starting work. A scorer that is too lenient waves through
items nobody understands — the failure it exists to prevent. One that is too
strict gets switched off, which is the same outcome by a slower route.

So the fixtures below are two real shapes: a brief that genuinely says everything,
and one that looks complete to a skim and says nothing checkable. The second is
the one that matters — vague briefs are not empty, they are full of words.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from score_alignment import THRESHOLD, score_alignment  # noqa: E402

COMPLETE = """
# Alignment: B-014 — trace explorer p95

## Problem
The trace explorer takes 4.1s at p95 for a 24h window, measured on 2026-08-20 across
2,300 requests in production. Support gets three tickets a week about it and the team
has been closing them as "expected". Nobody has profiled the query path.

## Functional Requirements
- A 24h window returns within the latency budget below.
- Windows longer than 24h return a partial result plus an explicit truncation marker.

## Non-Functional Requirements
- p95 under 800ms at 50 rps for a 24h window.
- Memory under 512MB per query.

## Flows
### Query a 24h window
1. The UI posts the range to /api/traces.
2. The gateway fans out to three shards.
3. Results merge and stream back.

## System design
```mermaid
flowchart LR
  UI -->|POST /api/traces| GW[Gateway]
  GW --> S1[(shard 1)]
  GW --> S2[(shard 2)]
```

## Interaction
```mermaid
sequenceDiagram
  participant UI
  participant GW as Gateway
  participant S as Shard
  UI->>GW: POST /api/traces
  GW->>S: scan(range)
  S-->>GW: rows
```

## Acceptance Criteria
- `npm run bench:traces -- --window 24h` reports p95 under 800ms.
- `pytest tests/test_truncation.py` exits 0.

## Dependencies
- The shard client must expose a streaming cursor (owned by data-plane).

## Out of scope
- Windows beyond 7 days; those go through the export path.

## Questions answered
- Which shard is slowest? Shard 2, 3.4s of the 4.1s.
- Is the merge the bottleneck? No, measured at 90ms.

## Demonstration
- Run the bench command above in front of the team and show the p95 line.

## Walkthrough
See `alignment-b-014.html` for the animated flow.
"""

VAGUE = """
# Alignment: B-099 — improve the dashboard

## Problem
The dashboard is slow and users complain.

## Functional Requirements
- Make the dashboard faster.

## Non-Functional Requirements
- Should feel responsive.

## Flows
### Loading the dashboard

## Acceptance Criteria
- The dashboard is faster.

## Dependencies

## Questions answered
- Which query is slow? UNKNOWN
"""


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "brief.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_a_complete_brief_clears_the_threshold(tmp_path: Path) -> None:
    """The bar has to be reachable, or the gate is theatre.

    If a brief this thorough could not pass, nobody would ever pass, and the gate
    would be switched off within a week — which is the same as not having it.
    """
    report = score_alignment(_write(tmp_path, COMPLETE))
    assert report.meets_threshold, (
        f"a complete brief scored {report.ratio:.0%}; gaps: "
        f"{[(c.key, c.why) for c in report.gaps]}"
    )


def test_a_vague_brief_is_refused(tmp_path: Path) -> None:
    """The one that matters: it LOOKS complete and says nothing checkable.

    Every section is present. "Make the dashboard faster" is a functional
    requirement in shape only, "should feel responsive" has no number, the
    acceptance criterion cannot fail, and one question is still UNKNOWN.

    An empty brief is obviously not ready. This one is the failure mode that
    reaches implementation.
    """
    report = score_alignment(_write(tmp_path, VAGUE))
    assert not report.meets_threshold
    assert report.ratio < 0.6, f"scored {report.ratio:.0%} — far too generous"


def test_an_unanswered_question_costs_the_point(tmp_path: Path) -> None:
    """`UNKNOWN` in the answers is an open question wearing a closed coat."""
    with_unknown = COMPLETE.replace("Shard 2, 3.4s of the 4.1s.", "UNKNOWN")
    report = score_alignment(_write(tmp_path, with_unknown))
    questions = next(c for c in report.criteria if c.key == "questions_closed")
    assert questions.score < 2
    assert "open" in questions.why


def test_a_requirement_without_a_number_is_not_measurable(tmp_path: Path) -> None:
    """"Fast" is a wish. The rubric scores the difference.

    This is the single most common way a brief passes review and fails delivery:
    everyone nods at "responsive", and nobody can say afterwards whether it was
    achieved.
    """
    no_numbers = COMPLETE.replace(
        "- p95 under 800ms at 50 rps for a 24h window.\n- Memory under 512MB per query.",
        "- Should feel fast.\n- Should not use much memory.")
    report = score_alignment(_write(tmp_path, no_numbers))
    nfr = next(c for c in report.criteria if c.key == "nfr_measurable")
    assert nfr.score < 2
    assert "0/2" in nfr.why


def test_an_acceptance_criterion_that_cannot_fail_is_not_executable(tmp_path: Path) -> None:
    """A criterion nobody can run is a criterion that closes by opinion."""
    soft = COMPLETE.replace(
        "- `npm run bench:traces -- --window 24h` reports p95 under 800ms.",
        "- The team agrees performance is acceptable.")
    report = score_alignment(_write(tmp_path, soft))
    ac = next(c for c in report.criteria if c.key == "acceptance_executable")
    assert ac.score < 2


def test_missing_out_of_scope_is_penalised(tmp_path: Path) -> None:
    """The boundary nobody writes is the boundary everybody assumes differently.

    Two people can agree completely on what a thing does and disagree completely
    on what it does not, and that disagreement only surfaces at review.
    """
    without = COMPLETE.replace(
        "## Out of scope\n- Windows beyond 7 days; those go through the export path.\n", "")
    report = score_alignment(_write(tmp_path, without))
    scope = next(c for c in report.criteria if c.key == "out_of_scope")
    assert scope.score == 0


def test_judgement_items_are_named_and_not_scored(tmp_path: Path) -> None:
    """What the script cannot decide is said out loud, not counted as passing.

    Structure is checkable; whether the stated problem is the REAL problem is
    not. Scoring it silently would make the number claim more than it measured.
    """
    report = score_alignment(_write(tmp_path, COMPLETE))
    assert len(report.judgement_items) >= 3
    assert report.maximum == 2 * len(report.criteria)


def test_the_threshold_is_ninety_percent(tmp_path: Path) -> None:
    """Pinned because it is a decision, not an implementation detail.

    It matches the Definition-of-Ready convention (score 0/1/2 per criterion,
    require >=90%), and changing it changes what the kit refuses to build.
    """
    assert THRESHOLD == 0.90

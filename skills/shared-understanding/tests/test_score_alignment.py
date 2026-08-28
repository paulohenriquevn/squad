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

    It scores `COMPLETE_V2`, not `COMPLETE`: the v1 fixture carries no stable
    ids, no scenario classes and no traceability, so under the v2 rubric it is
    correctly refused. `COMPLETE` survives below as the control that shows each
    new criterion actually fires.
    """
    report = score_alignment(_write(tmp_path, COMPLETE_V2))
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


# ── v2: what the five reference implementations do that this one did not ──────
#
# Sources read on 2026-08-28, in full:
#   github/spec-kit                 /clarify, /analyze, /checklist + templates
#   obra/superpowers                skills/brainstorming
#   jeffallan/claude-skills         skills/feature-forge
#   FredAntB/Spec-Driven-Development SKILL.md (generation gate, SDD health metrics)
#   melodic-software/claude-code-plugins  discovery/blindspot
#
# The tests below pin the mechanisms taken from them. Each names its source,
# because a criterion whose provenance is lost is a criterion nobody can argue
# with later.

COMPLETE_V2 = COMPLETE.replace(
    "## Functional Requirements\n"
    "- A 24h window returns within the latency budget below.\n"
    "- Windows longer than 24h return a partial result plus an explicit truncation marker.",
    "## Functional Requirements\n"
    "- FR-001: The explorer shall return a 24h window within the NFR-001 budget.\n"
    "- FR-002: When the window exceeds 24h, the explorer shall return a partial\n"
    "  result plus an explicit truncation marker.",
).replace(
    "- p95 under 800ms at 50 rps for a 24h window.\n- Memory under 512MB per query.",
    "- NFR-001: p95 under 800ms at 50 rps for a 24h window.\n"
    "- NFR-002: Memory under 512MB per query.",
).replace(
    "- `npm run bench:traces -- --window 24h` reports p95 under 800ms.\n"
    "- `pytest tests/test_truncation.py` exits 0.",
    "- AC-001 (NFR-001): `npm run bench:traces -- --window 24h` reports p95 under 800ms.\n"
    "- AC-002 (FR-002): `pytest tests/test_truncation.py` exits 0.",
).replace(
    "## Flows\n### Query a 24h window\n",
    "## Flows\n### Query a 24h window [primary]\n",
).replace(
    "## System design",
    "### Shard returns no rows [alternate]\n"
    "1. The gateway records an empty shard.\n"
    "2. The merge proceeds with the shards that answered.\n\n"
    "### Shard times out at 2s [exception]\n"
    "1. The gateway cancels the scan.\n"
    "2. The response carries a partial marker naming the shard.\n\n"
    "### Gateway restarts mid-query [recovery]\n"
    "1. The client re-issues with the same cursor.\n"
    "2. The scan resumes rather than restarting.\n\n"
    "## System design",
)


def test_stable_ids_are_required(tmp_path: Path) -> None:
    """Without `FR-001`, nothing can point at anything.

    Every reference implementation converged on this independently — spec-kit's
    `FR-###`/`SC-###` inventory, feature-forge's EARS ids, FredAntB's sequential
    `REQ-xxx`. A requirement with no id cannot be cited by an acceptance
    criterion, a task, a test, or a review comment; the whole traceability chain
    starts here or it does not start.
    """
    report = score_alignment(_write(tmp_path, COMPLETE_V2))
    ids = next(c for c in report.criteria if c.key == "stable_ids")
    assert ids.score == 2, ids.why

    without = score_alignment(_write(tmp_path, COMPLETE))
    assert next(c for c in without.criteria if c.key == "stable_ids").score == 0


def test_an_acceptance_criterion_must_cite_the_requirement_it_closes(tmp_path: Path) -> None:
    """spec-kit's coverage pass: a requirement with zero coverage is CRITICAL.

    An acceptance criterion that names no requirement proves nothing in
    particular, and a requirement no criterion cites is a requirement that will
    ship unverified. Both directions are checked because both happen.
    """
    report = score_alignment(_write(tmp_path, COMPLETE_V2))
    trace = next(c for c in report.criteria if c.key == "traceability")
    assert trace.score == 2, trace.why

    orphaned = COMPLETE_V2.replace("- AC-001 (NFR-001):", "- AC-001:")
    report = score_alignment(_write(tmp_path, orphaned))
    assert next(c for c in report.criteria if c.key == "traceability").score < 2


def test_the_four_scenario_classes_must_be_covered(tmp_path: Path) -> None:
    """"Happy path only" was an anti-pattern in prose; now it is a measurement.

    spec-kit's scenario classification — Primary / Alternate / Exception /
    Recovery — turns "did you think about failure?" from a question somebody
    remembers to ask into a check that fires. The bugs live in the three classes
    nobody drew.
    """
    report = score_alignment(_write(tmp_path, COMPLETE_V2))
    classes = next(c for c in report.criteria if c.key == "scenario_classes")
    assert classes.score == 2, classes.why

    happy_only = score_alignment(_write(tmp_path, COMPLETE))
    assert next(c for c in happy_only.criteria if c.key == "scenario_classes").score < 2


def test_vague_adjectives_are_caught_wherever_they_appear(tmp_path: Path) -> None:
    """`nfr_measurable` only ever looked at one section.

    spec-kit's ambiguity pass flags "fast, scalable, secure, intuitive, robust"
    ANYWHERE they carry weight without a number. A functional requirement saying
    the explorer "shall be responsive" passed every previous check, because the
    old rubric only demanded numbers from the NFR section.
    """
    report = score_alignment(_write(tmp_path, COMPLETE_V2))
    assert next(c for c in report.criteria if c.key == "no_vague_terms").score == 2

    vague = COMPLETE_V2.replace(
        "- FR-001: The explorer shall return a 24h window within the NFR-001 budget.",
        "- FR-001: The explorer shall be fast and provide a seamless experience.")
    report = score_alignment(_write(tmp_path, vague))
    term = next(c for c in report.criteria if c.key == "no_vague_terms")
    assert term.score < 2
    assert "fast" in term.why


def test_placeholders_are_scanned_across_the_whole_brief(tmp_path: Path) -> None:
    """`UNKNOWN` cost a point only inside `## Questions answered`.

    A `TODO` in the data model or a `TBD` in the acceptance criteria is the same
    unresolved decision, and it was invisible. superpowers' spec self-review
    scans the whole document for exactly this reason.
    """
    with_todo = COMPLETE_V2.replace("- NFR-002: Memory under 512MB per query.",
                                    "- NFR-002: Memory ceiling TBD.")
    report = score_alignment(_write(tmp_path, with_todo))
    ph = next(c for c in report.criteria if c.key == "no_placeholders")
    assert ph.score == 0
    assert "TBD" in ph.why


def test_the_machine_score_alone_never_yields_ALIGNED(tmp_path: Path) -> None:
    """The finding that matters most: the gate was self-assessed.

    The same agent wrote the brief and ran the scorer that approved it. spec-kit
    separates the two — its checklist is reviewer-owned, generated unchecked, and
    `/implement` reads the boxes as a gate and MAY NOT touch them.

    So `ALIGNED` now needs two independent things: a machine score the agent CAN
    reach, and a sign-off only a human can give. A perfect brief with no reviewer
    is `AWAITING_REVIEW`, never `ALIGNED`.
    """
    report = score_alignment(_write(tmp_path, COMPLETE_V2))
    assert report.meets_machine_threshold, f"{report.machine_ratio:.0%}"
    assert not report.reviewer_signed_off
    assert not report.aligned
    assert report.verdict == "AWAITING_REVIEW"


def test_a_reviewer_signs_off_by_checking_every_box(tmp_path: Path) -> None:
    """And the sign-off is a real artefact, not a claim in prose."""
    signed = COMPLETE_V2 + """
## Reviewer sign-off
- [x] CHK001 The stated problem is the one we actually have. [Judgement]
- [x] CHK002 The flows drawn are the flows that matter. [Judgement]
- [x] CHK003 The numbers in the NFRs are the right numbers. [Judgement]
"""
    report = score_alignment(_write(tmp_path, signed))
    assert report.reviewer_signed_off
    assert report.aligned
    assert report.verdict == "ALIGNED"


def test_one_unchecked_box_withholds_the_sign_off(tmp_path: Path) -> None:
    """A partially reviewed brief is an unreviewed brief.

    This is the case the mechanism exists for: three boxes, two ticked, and the
    untouched one is the judgement nobody made.
    """
    partial = COMPLETE_V2 + """
## Reviewer sign-off
- [x] CHK001 The stated problem is the one we actually have. [Judgement]
- [x] CHK002 The flows drawn are the flows that matter. [Judgement]
- [ ] CHK003 The numbers in the NFRs are the right numbers. [Judgement]
"""
    report = score_alignment(_write(tmp_path, partial))
    assert not report.reviewer_signed_off
    assert report.verdict == "AWAITING_REVIEW"
    assert "CHK003" in report.pending_review[0]


def test_a_section_keeps_its_own_subsections(tmp_path: Path) -> None:
    """Pinned because the first version of `_section` silently truncated.

    It stopped at `^##+`, so `## Flows` ended at its own `### Query a 24h window`
    and the criterion scored 0 over a brief containing four flows. The fixture
    still cleared 90% — two lost points fit inside the tolerance — so nothing
    failed and the gate reported "no named flow" about a document full of them.
    A gate reading an empty string still produces a verdict, which is why this
    is worse than having no gate.
    """
    report = score_alignment(_write(tmp_path, COMPLETE_V2))
    flows = next(c for c in report.criteria if c.key == "flows")
    assert flows.score == 2, flows.why
    assert "4 flow(s)" in flows.why

"""The plan template stopped charging for sections that restate or decide nothing.

Measured on a consumer 2026-09-16 across 35 plans: `## ADRs` in 35 of 35 at 149 lines
median (5,752 total) with `adr_without_alternatives` firing on 8 of them, and
`## Baseline Context` at 135 lines median (4,794 total) against 503 in the opportunity
document that precedes it and already holds the same state.

Together 10,546 lines — 22% of all plan content — either deciding nothing or written
twice. Half the defects found across two days of running this chain were two documents of
one item contradicting each other, and a section that re-derives what another already
holds is where that class is manufactured.

Neither section is removed. The ADR is required where a decision was made, and the
baseline is required where the discovery did not establish it.
"""
from __future__ import annotations

from pathlib import Path

TEMPLATE = (Path(__file__).resolve().parents[1] / "skills" / "plan-write"
            / "templates" / "plan-template.md")


def _section(title: str) -> str:
    """The section, found by its HEADING — a line that starts with `## `.

    `body.index("## ADRs")` matched the words inside a Prior Art sentence that tells the
    author to "list it in `## ADRs` with rationale", and returned that paragraph as the
    section. A region chosen by a delimiter the content also uses is not a region, and
    this is the third time in two days that sentence has been the finding.
    """
    lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"## {title}")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def test_an_adr_is_asked_for_only_where_a_decision_was_made() -> None:
    """`check_adr_completeness` already returns complete for ZERO ADRs — deliberately.
    What it caps is an ADR naming no rejected alternative, which is the shape an
    obligatory-section habit produces. The template read as mandatory and the habit
    followed."""
    # Flattened: the prose is wrapped, and a phrase that crosses a wrap point tests the
    # line width rather than the content.
    section = " ".join(_section("ADRs").split())
    assert "Only when a decision was actually made" in section
    assert "NO `## ADRs` section" in section, \
        "the template does not say an absent section is accepted"


def test_the_baseline_is_cited_rather_than_restated() -> None:
    """A restatement is not more rigorous than a citation. It is one more thing that can
    drift."""
    section = " ".join(_section("Baseline Context").split())
    assert "Cite the discovery, do not restate it" in section
    assert "opportunity.md" in section, \
        "the template does not name the document that already holds the baseline"


def test_the_template_says_where_a_criterion_writes_its_evidence() -> None:
    """16 of 35 plans on a consumer wrote evidence to a fixed `/tmp/<item>-*.txt`, and one
    of them collided: two lanes of the same item derive the SAME name, both files ended
    zero bytes, and the `comm -13` over them printed 0 and PASSED while proving nothing.

    The convention was invented in the absence of one. The kit never taught it and never
    warned against it, and its own pipeline SKILL modelled the shape with a fixed
    `/tmp/queue.json`.

    A criterion that cannot fail is indistinguishable from one that is satisfied.
    """
    section = " ".join(_section("Where a criterion writes its evidence").split())
    assert "Never a fixed path under `/tmp`" in section
    assert "mktemp" in section, "the template names no working alternative"
    assert "$$" in section, \
        "the template does not credit the form the review templates already use"


def test_the_pipeline_skill_does_not_model_the_shape_it_warns_about() -> None:
    skill = (Path(__file__).resolve().parents[1] / "skills" / "pipeline"
             / "SKILL.md").read_text(encoding="utf-8")
    assert "/tmp/queue.json" not in skill, (  # prose-test: a ban on a literal a reader would copy — weak against synonyms, kept for the regression it names
        "the dispatch still writes a fixed path two concurrent runs would share")

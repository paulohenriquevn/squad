"""The kit's plan template ships headings the kit's own checkers cannot find.

Measured 2026-09-23 against `check_criterion_executability.SECTION_HEADER_RE`:

    MATCH   #### Acceptance Criteria          plan-template.md:260
    NO      #### DoD (Definition of Done)     plan-template.md:269
    NO      ## Global Definition of Done      plan-template.md:339
    NO      ## Global DoD                     the alternative the regex itself LISTS
    MATCH   ### Global DoD                    the only level at which it matched

Two independent defects. **The template prescribes two headings nothing matches**, so every DoD
bullet in a plan written from the template is invisible to the checker. And **`Global DoD` is
unreachable at its natural level**: the pattern is `####?` — three or four `#` — while a
document section is `##`, so the listed alternative can only match as `### Global DoD`, which no
author would write for a top-level section.

The consequence is worse than a miss. A consumer measured:

    criterion_executability: total_criteria 0
    hard_caps_triggered: [… 'vague_acceptance_criteria' …]
    verdict: INVALID

The cap is named `vague_acceptance_criteria` and the cause is ZERO criteria found, so the
message sends an author to rewrite criteria that are perfectly precise. **A diagnosis pointing
the wrong way is worse than no diagnosis**, and the same consumer reported discovering SIX exact
literals by trial and error in one day, across three checkers.

WHY THIS TEST AND NOT A LINT TOOL. The parsimony ladder says stop at the highest rung that
resolves it, and a lint tool is rung six while the two files agreeing is rung one. This is the
rung-one mechanism: the template is fed to its own checkers, so a heading either side changes
without the other fails here rather than in somebody's plan. It closes the cases nobody has
found yet, which is the half a table of known literals cannot.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))

TEMPLATE = _ROOT / "skills" / "plan-write" / "templates" / "plan-template.md"

#: Placeholder shapes the template carries for an author to replace. Filled with something
#: trivially valid so the checkers see a document rather than a form.
_PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_ .|/-]{1,60}\}|<[A-Za-z0-9_ .|/-]{1,60}>")


@pytest.fixture(scope="module")
def filled(tmp_path_factory) -> Path:
    """The template with its placeholders replaced — a document, not a form."""
    assert TEMPLATE.is_file(), f"{TEMPLATE} is not here; this test lost its subject"
    body = TEMPLATE.read_text(encoding="utf-8")
    # The template shows its prescribed forms inside ```markdown fences, correctly — a template
    # is a form and its examples must not be read as content. The checkers strip fenced code, so
    # the fences are removed here to model AN AUTHOR WHO FOLLOWED THE TEMPLATE rather than the
    # template as a document. Without this the citation example is invisible and the test
    # asserts something about fences instead of about the contract.
    body = re.sub(r"^```markdown\s*$|^```\s*$", "", body, flags=re.MULTILINE)
    body = _PLACEHOLDER.sub("x", body)
    path = tmp_path_factory.mktemp("plan") / "a-plan.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_the_template_is_not_empty(filled: Path) -> None:
    """Without this, every assertion below runs over a blank file and passes."""
    assert len(filled.read_text(encoding="utf-8")) > 2000


def test_the_criteria_checker_finds_criteria_in_the_template(filled: Path) -> None:
    from check_criterion_executability import check_criterion_executability

    report = check_criterion_executability(filled)

    assert report.total_criteria > 0, (
        "the kit's own template yields ZERO acceptance criteria to the kit's own checker, so "
        "every plan written from it fires `vague_acceptance_criteria` for having none. "
        f"Headings present: {_headings(filled)}")


def test_every_dod_heading_the_template_writes_is_matched(filled: Path) -> None:
    """The narrow half, so a fix that only helps `Acceptance Criteria` still fails."""
    from check_criterion_executability import SECTION_HEADER_RE

    dod = [h for h in _headings(filled) if "dod" in h.lower() or "definition of done" in h.lower()]
    assert dod, "the template writes no DoD heading at all; re-point this test"
    unmatched = [h for h in dod if not SECTION_HEADER_RE.search(h)]
    assert unmatched == [], (
        f"the template prescribes these and the checker matches none of them: {unmatched}")


def test_the_baseline_checker_finds_its_subsections(filled: Path) -> None:
    from check_baseline_context import check_baseline_context

    report = check_baseline_context(filled)
    missing = getattr(report, "missing_subsections", None) or getattr(report, "missing", ())
    assert not missing, (
        f"the template does not satisfy the baseline checker's required subsections: {missing}")


def test_the_drawbacks_checker_accepts_the_templates_bullets(filled: Path) -> None:
    from check_drawbacks_section import check_drawbacks_section

    report = check_drawbacks_section(filled)
    assert getattr(report, "present", True), (
        "the drawbacks checker does not recognise the section the template prescribes")


def _headings(path: Path) -> list[str]:
    return [ln.rstrip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.startswith("#")]

# ── every checker is exercised here, or declared as not being ────────────────
#
# This file named THREE checkers and the skill ships SEVENTEEN. Naming three is the same shape as
# the frozen parenthetical that named six signals while the matcher held thirty-nine (#175): the
# list looks like coverage and is a sample.
#
# It cost an instance the same day. `check_adr_completeness` matched `### D1` while every plan
# writes `### ADR-N`, so the cap guarding ADRs had no subject — a gate reporting itself applied
# while applying nothing. Had this file enumerated the directory, that would have surfaced in the
# run that found the two DoD headings.
#
# So the list below is DERIVED from disk, and a checker that this file does not exercise must be
# named in `_NOT_EXERCISED` with the reason. Adding a checker forces the decision rather than
# inheriting silence — the `test_every_gate_is_reachable` idiom, pointed at this file.
_SCRIPTS = _ROOT / "skills" / "plan-confidence" / "scripts"

#: Checkers this file does not run against the template, each with why. A template is a form:
#: some checkers need an artifact the form cannot contain.
_NOT_EXERCISED = {
    "check_alignment_gate": "reads the alignment brief, not the plan",
    "check_architecture_compliance": "reads the repository's modules, not a document",
    "check_coverage_matrix": "needs task ids that only a written plan has",
    "check_deps_audit": "needs a dependency audit record",
    "check_evidence_citations": "resolves file:line against a real tree",
    "check_failure_scenarios": "fires only when the plan declares external I/O",
    "check_impediment_agrees": "reads the backlog item, not the plan",
    "check_patterns_consumption": "needs the project's *-patterns skills on disk",
    "check_spec_smells": "reads a spec, not a plan template",
    "check_symbol_naming": "reads code identifiers",
    "check_task_interfaces": "needs task blocks a form does not carry",
    "check_tdd_in_bugfix": "fires only on a bugfix task",
    "check_concurrency_tests": "fires only when the plan text signals concurrency",
    "check_adr_completeness": "the template's ADR section is illustrative prose, "
                              "and `test_an_adr_is_seen_however_the_kit_spells_it` "
                              "covers the pattern directly",
}


def test_every_checker_is_exercised_or_declared() -> None:
    on_disk = {p.stem for p in _SCRIPTS.glob("check_*.py")}
    assert len(on_disk) > 3, f"only {len(on_disk)} checkers found; this test lost its subject"

    source = Path(__file__).read_text(encoding="utf-8")
    exercised = {name for name in on_disk if f"from {name} import" in source}
    unaccounted = on_disk - exercised - set(_NOT_EXERCISED)

    assert unaccounted == set(), (
        f"these checkers are neither exercised against the template nor declared in "
        f"`_NOT_EXERCISED` with a reason: {sorted(unaccounted)}. A list that names some is a "
        f"sample wearing coverage.")


def test_no_declared_exclusion_names_a_checker_that_left() -> None:
    """The other direction: an exclusion for a deleted checker is a rule that stopped applying."""
    on_disk = {p.stem for p in _SCRIPTS.glob("check_*.py")}
    stale = set(_NOT_EXERCISED) - on_disk

    assert stale == set(), f"declared as not exercised and no longer on disk: {sorted(stale)}"


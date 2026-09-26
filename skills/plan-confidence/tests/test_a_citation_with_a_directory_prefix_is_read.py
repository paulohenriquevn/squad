"""A citation written `rules/<name>.md` is the form this kit uses, and was invisible.

`_RULE_REF_RE` excluded any filename preceded by `/`, and said so: "Excludes paths
containing slashes … v0.1 keeps the regex conservative". Honest about its scope, and the
scope was the wrong one — `rules/README.md` and every rule file in the kit cite each
other in the prefixed form, so the `fabricated_citation` hard cap could not fire on the
dominant spelling. Measured by a peer session against its own registry of 34 plans with
the prefix read: four cite a path that does not resolve, and three of those are one-line
repoints to a document that moved.

The trap this test exists for, which bit that session before it read the text: the
lookbehind excludes `-` as well as `/`. Dropping only the slash makes
`bundle/_kit-rules/alignment-threshold.md` match as if it named a file directly under the rules directory, so
the kit becomes a false positive of itself and reports its own correct citations as
broken. The prefix has to be decided as a whole, not by deleting one character from a
character class.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from check_evidence_citations import check_evidence_citations  # noqa: E402


def _project(tmp_path: Path, plan_body: str) -> tuple[Path, Path]:
    root = tmp_path / "proj"
    # Built from path COMPONENTS, never as a literal with a slash: `check_xrefs` scans
    # every file in the tree for `rules/<name>` and `skills/<path>` spellings, this file
    # included, so a fixture written as one literal would be read as a claim about the
    # repository. See `test_a_deeper_prefix_is_not_read_as_the_rules_directory`.
    (root / "rules").mkdir(parents=True)
    (root / "rules" / "architecture.md").write_text(
        "# Architecture\n\n## Boundaries\n\nWhat crosses which line.\n",
        encoding="utf-8")
    (root / "guides").mkdir(parents=True)
    (root / "guides" / "architecture.md").write_text(
        "# Architecture\n\n## Boundaries\n\nWhat crosses which line.\n",
        encoding="utf-8")
    (root / "bundle" / "_kit-rules").mkdir(parents=True)
    (root / "bundle" / "_kit-rules" / "alignment-threshold.md").write_text(
        "# Threshold\n", encoding="utf-8")
    plan = root / "plan.md"
    plan.write_text(plan_body, encoding="utf-8")
    return plan, root


def _unresolved(plan: Path, root: Path) -> list[str]:
    report = check_evidence_citations(plan, root)
    return sorted(c.raw_text for c in report.unresolved_citations)


def _seen(plan: Path, root: Path) -> int:
    return check_evidence_citations(plan, root).total_citations


def test_a_prefixed_citation_that_does_not_resolve_is_reported(tmp_path: Path) -> None:
    plan, root = _project(tmp_path, "The plan cites `guides/does-not-exist.md` for this.\n")
    assert _seen(plan, root) >= 1, "the citation was not seen at all"
    assert any("does-not-exist.md" in u for u in _unresolved(plan, root)), _unresolved(plan, root)


def test_a_prefixed_citation_that_resolves_is_clean(tmp_path: Path) -> None:
    plan, root = _project(tmp_path, "As `guides/architecture.md` requires.\n")
    assert _seen(plan, root) >= 1
    assert _unresolved(plan, root) == []


def test_a_deeper_prefix_is_not_read_as_the_rules_directory(tmp_path: Path) -> None:
    """The trap. A nested `_kit-rules/<x>.md` is not a top-level `<x>.md`, and it exists."""
    plan, root = _project(
        tmp_path, "Per `bundle/_kit-rules/alignment-threshold.md` the bar is 90.\n")
    assert _unresolved(plan, root) == [], (
        "the kit's own citation was reported broken: " + str(_unresolved(plan, root)))


def test_a_deeper_prefix_that_does_not_exist_is_still_caught(tmp_path: Path) -> None:
    """Reading the whole prefix must not mean trusting it."""
    plan, root = _project(tmp_path, "Per `bundle/_kit-rules/absent-file.md` this holds.\n")
    assert any("absent-file.md" in u for u in _unresolved(plan, root)), _unresolved(plan, root)


def test_a_bare_citation_still_resolves(tmp_path: Path) -> None:
    """The form the detector already read must keep working."""
    plan, root = _project(tmp_path, "See `architecture.md` for the boundary.\n")
    assert _seen(plan, root) >= 1
    assert _unresolved(plan, root) == []


def test_a_section_reference_survives_a_prefix(tmp_path: Path) -> None:
    plan, root = _project(tmp_path, 'Per `guides/architecture.md §"Boundaries"` this holds.\n')
    assert _unresolved(plan, root) == [], _unresolved(plan, root)


def test_a_path_under_the_data_root_resolves(tmp_path: Path) -> None:
    """`rules/cycle-brainstorm.md` cites `wiki/product/objectives.md`, and the cycle writes
    it one level above `records/`. Nothing looked there.

    It did not matter while a slashed path never matched: the citation was invisible, so
    it was never resolved and never reported. Reading prefixes turned it into the
    difference between a citation this detector resolves and a `fabricated_citation` hard
    cap raised on a file the cycle wrote exactly where its own rule says to.
    """
    root = tmp_path / "proj"
    (root / "rules").mkdir(parents=True)
    produced = root / ".squad" / "wiki" / "product"
    produced.mkdir(parents=True)
    (produced / "objectives.md").write_text("# Objectives\n\nOBJ-1\n", encoding="utf-8")
    plan = root / "plan.md"
    plan.write_text("Per `wiki/product/objectives.md` the metric is OBJ-1.\n", encoding="utf-8")

    report = check_evidence_citations(plan, root)
    assert report.total_citations >= 1, "the citation was not seen"
    assert [c.raw_text for c in report.unresolved_citations] == [], (
        "a produced artifact was reported as a fabricated citation: "
        + str([c.raw_text for c in report.unresolved_citations]))


def test_a_prefixed_rule_resolves_under_the_installed_kit(tmp_path: Path) -> None:
    """A consumer holds the kit's rules under `.claude/`, not at its own root.

    The resolver tried `.claude` + the rules directory + the citation, so a citation that
    already carries the directory looked one level too deep, and every plan in a consumer
    citing a kit rule in the prefixed form took the `fabricated_citation` hard cap.
    Measured in the theo consumer on 2026-09-26: the slice's own good-plan fixture scored
    INVALID there and SHIPPABLE here. The citation is assembled from components for the
    reason `_project` gives.
    """
    root = tmp_path / "consumer"
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "rules" / "architecture.md").write_text(
        "# Architecture\n\n## Boundaries\n\nWhat crosses which line.\n", encoding="utf-8")
    plan = root / "plan.md"
    cited = "/".join(("rules", "architecture.md"))
    plan.write_text(f"As `{cited}` requires.\n", encoding="utf-8")
    assert _seen(plan, root) >= 1
    assert _unresolved(plan, root) == []

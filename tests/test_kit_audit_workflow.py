"""The kit auditing itself: what the script must keep doing.

Every defect this kit found on 2026-09-02 was found by an agent doing OTHER work
— running the pipeline over a consumer's backlog and noticing something wrong in
the tooling underneath. Seven issues arrived that way, all real. A good source,
and a slow one: it finds only what happens to lie in the path.

A gate cannot replace it either. These patterns are about MEANING, and the suite
already holds 1180 assertions that see shape. The measured evidence for that gap
came from an ALIGN agent: one brief scored 31/34 unchanged across five content
defects and their fixes, and what caught them was a reviewer reading the
repository rather than the rubric.

So this script asks agents to look on purpose. These assertions pin the two
things that make its output worth reading — the lenses carry measurements, and
nothing is reported until something tried to kill it.
"""
from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = (Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
            / "kit_audit_workflow.js")

_BLOCK = re.compile(r"/\*.*?\*/", re.S)


def _code() -> str:
    body = _BLOCK.sub("", WORKFLOW.read_text(encoding="utf-8"))
    return "\n".join(line for line in body.splitlines()
                     if not line.lstrip().startswith("//"))


def test_no_finding_is_reported_without_something_trying_to_kill_it() -> None:
    """A finding that survives only because nobody looked is worse than none: it
    spends a maintainer's attention and teaches them to distrust the next one."""
    code = _code()

    assert "phase: 'Refute'" in code, "there is no refutation stage"
    assert "refuted" in code, "the verdict does not carry a refutation"
    assert re.search(r"filter\(\(f\)\s*=>\s*f\.verdict\s*&&\s*!f\.verdict\.refuted\)", code), \
        "survivors must be selected by a verdict, not by having been found"


def test_the_refuter_defaults_to_refuting() -> None:
    """An audit whose verifier defaults to confirming is an audit that confirms."""
    prose = WORKFLOW.read_text(encoding="utf-8")

    assert "Default to refuted=true" in prose


def test_every_lens_carries_a_measurement_rather_than_an_adjective() -> None:
    """An agent told "look for silent failures" finds prose. One told "a matcher
    reported a complete delta of 5 against a true 11" finds matchers. Every lens
    here quotes a defect this kit actually shipped, with its number."""
    prose = WORKFLOW.read_text(encoding="utf-8")
    lenses = re.findall(r"key:\s*'([a-z-]+)',\s*\n\s*prompt:\s*`(.*?)`,", prose, re.S)

    assert len(lenses) >= 5, f"only {len(lenses)} lenses parsed"
    for key, prompt in lenses:
        assert re.search(r"\d", prompt), f"lens {key} cites no measurement"
        assert "Measured" in prompt, f"lens {key} does not say what was measured"


def test_the_audit_never_writes_to_the_kit_it_audits() -> None:
    """A hunter that can edit is a hunter that can make its own finding true."""
    prose = WORKFLOW.read_text(encoding="utf-8")

    assert "Read it; do not change it" in prose


def test_an_empty_result_is_named_as_a_real_answer() -> None:
    """Otherwise the incentive is to pad, and a padded audit is noise with a
    verification stage bolted to it."""
    prose = WORKFLOW.read_text(encoding="utf-8")

    assert "An empty list is a real answer" in prose
    assert "report FEWER rather than padding" in prose


def test_there_is_no_barrier_between_hunting_and_refuting() -> None:
    """A lens that finishes first should have its findings refuted while the
    slower lenses are still hunting."""
    code = _code()

    assert "await pipeline(" in code
    assert "await parallel(\n  LENSES" not in code

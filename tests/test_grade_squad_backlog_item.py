"""Tests for the backlog-item eval grader.

A grader is a validator, and an untested validator is the defect this project has already
hit three times: check_xrefs auditing the wrong project, the thresholds resolver silently
using the wrong bands, the routing check that could never run. Each printed a confident
result. A grader with a wrong regex does the same — it reports a pass rate that reads like
a measurement.

The load-bearing test here is `test_needs_review_never_auto_passes`: an assertion that
requires judgement must NOT count as passed. Defaulting it to true would inflate every run
in the battery, and the inflation would be invisible.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "skill-creator" / "scripts"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from grade_squad_backlog_item import (  # noqa: E402 — post-bootstrap import
    BASE_IDS,
    _blocks,
    _field,
    grade,
)

BASE_BACKLOG = """# Backlog

## Itens

## B-007 — Suspected N+1 in the ingest path   [ ]

domain: data-plane-ts
repo: search-api
status: killed
kill_reason: measured, it is a single batched query

## B-014 — Reduce round-trips in the trace listing   [ ]

domain: data-plane-ts
repo: web-console
suggested_mode: review
source: human
evidence: none-yet
why_now: the dashboard started loading 30d by default
status: raw
dod:
  - the listing issues a number of queries independent of the span count
"""


def _run(tmp_path: Path, backlog: str, transcript: str = "") -> Path:
    run = tmp_path / "with_skill"
    (run / "outputs").mkdir(parents=True)
    (run / "outputs" / "BACKLOG.md").write_text(backlog, encoding="utf-8")
    (run / "outputs" / "transcript.md").write_text(transcript, encoding="utf-8")
    return run


def _by_text(exps: list[dict], fragment: str) -> dict:
    return next(e for e in exps if fragment.lower() in e["text"].lower())


def test_blocks_parses_every_item() -> None:
    blocks = _blocks(BASE_BACKLOG)
    assert set(blocks) == {"B-007", "B-014"}
    assert "web-console" in blocks["B-014"]
    assert "web-console" not in blocks["B-007"], "block boundaries leaked into the neighbour"


def test_field_extracts_only_its_own_field() -> None:
    block = _blocks(BASE_BACKLOG)["B-014"]
    assert _field(block, "repo") == "web-console"
    assert _field(block, "status") == "raw"
    assert _field(block, "evidence") == "none-yet"
    assert _field(block, "nonexistent") == ""


def test_needs_review_never_auto_passes(tmp_path: Path) -> None:
    """The most important guard in this file.

    Assertions that need a human read are emitted with passed=False and an evidence string
    marked NEEDS REVIEW. If they defaulted to passed=True, every run in the battery would
    be inflated by exactly the assertions nobody checked — and the inflation would look
    like a good result.
    """
    run = _run(tmp_path, BASE_BACKLOG + _new_item())
    exps = grade(run, 0)
    needs = [e for e in exps if e["evidence"].startswith("NEEDS REVIEW")]
    assert needs, "eval-0 is expected to have at least one judgement assertion"
    assert all(e["passed"] is False for e in needs)


def _new_item(evidence: str = "none-yet", status: str = "raw",
              domain: str = "data-plane-ts", repo: str = "promptly") -> str:
    return f"""
## B-032 — Resolving a new revision takes a few seconds   [ ]

domain: {domain}
repo: {repo}
suggested_mode: review
source: human
evidence: {evidence}
why_now: noticed while editing prompts; no trigger declared by the reporter
status: {status}
dod:
  - the new revision resolves in the API in under 1s after the save
"""


def test_eval0_passes_on_a_correct_hunch(tmp_path: Path) -> None:
    run = _run(tmp_path, BASE_BACKLOG + _new_item())
    exps = grade(run, 0)
    assert _by_text(exps, "new B-NNN block was appended")["passed"]
    assert _by_text(exps, "evidence: none-yet")["passed"]
    assert _by_text(exps, "status: raw")["passed"]
    assert _by_text(exps, "repo is promptly")["passed"]


def test_eval0_fails_when_evidence_was_demanded(tmp_path: Path) -> None:
    """Intake has no evidence gate; an item arriving WITH evidence means one was demanded."""
    run = _run(tmp_path, BASE_BACKLOG + _new_item(evidence="src/traces.ts:42"))
    exps = grade(run, 0)
    assert not _by_text(exps, "evidence: none-yet")["passed"]


def test_eval0_fails_when_nothing_was_registered(tmp_path: Path) -> None:
    run = _run(tmp_path, BASE_BACKLOG)
    exps = grade(run, 0)
    assert not _by_text(exps, "new B-NNN block was appended")["passed"]


def test_eval0_fails_on_wrong_domain(tmp_path: Path) -> None:
    run = _run(tmp_path, BASE_BACKLOG + _new_item(domain="control-plane", repo="control-plane"))
    exps = grade(run, 0)
    assert not _by_text(exps, "repo is promptly")["passed"]


def test_eval1_fails_when_prior_art_reached_the_registry(tmp_path: Path) -> None:
    """G5's whole point: the LangSmith comparison must never become a why_now."""
    leaked = BASE_BACKLOG + """
## B-032 — Waterfall de traces   [ ]

domain: data-plane-ts
repo: web-console
evidence: none-yet
why_now: LangSmith has a nice waterfall and we should have one too
status: raw
"""
    run = _run(tmp_path, leaked, transcript="Registrei o item.")
    exps = grade(run, 1)
    assert not _by_text(exps, "No B-NNN block carries the LangSmith")["passed"]


def test_eval1_passes_when_the_gate_fired(tmp_path: Path) -> None:
    transcript = (
        "Gate G5 disparou: a justificativa se apoia no LangSmith, outro projeto. "
        "Would ask the user: rephrase with a local reason / false positive / cancel."
    )
    run = _run(tmp_path, BASE_BACKLOG, transcript=transcript)
    exps = grade(run, 1)
    assert _by_text(exps, "No B-NNN block carries the LangSmith")["passed"]
    assert _by_text(exps, "flagged that the justification")["passed"]
    assert _by_text(exps, "offered a choice")["passed"]


def test_eval3_fails_when_a_duplicate_id_was_allocated(tmp_path: Path) -> None:
    """B-014 already covers the request; allocating a new id is the failure."""
    run = _run(tmp_path, BASE_BACKLOG + _new_item(), transcript="Criei o item B-032.")
    exps = grade(run, 3)
    assert not _by_text(exps, "No new B-NNN id was allocated")["passed"]


def test_eval3_passes_when_the_existing_item_absorbed_it(tmp_path: Path) -> None:
    transcript = "Searched BACKLOG.md and found B-014, which already covers exactly this. ITEM_MERGED."
    run = _run(tmp_path, BASE_BACKLOG, transcript=transcript)
    exps = grade(run, 3)
    assert _by_text(exps, "No new B-NNN id was allocated")["passed"]
    assert _by_text(exps, "searched BACKLOG.md")["passed"]
    assert _by_text(exps, "existing open item")["passed"]


def test_eval2_requires_two_items_in_the_right_domains(tmp_path: Path) -> None:
    split = BASE_BACKLOG + """
## B-032 — Blank screen when the token expires   [ ]

domain: frontend-dashboard
repo: control-plane/dashboard
evidence: none-yet
status: raw

## B-033 — API returns 500 em vez de 401   [ ]

domain: control-plane
repo: control-plane
evidence: none-yet
status: raw
"""
    run = _run(tmp_path, split, transcript="This spans two domains (G3), so I split it into two items.")
    exps = grade(run, 2)
    assert _by_text(exps, "split was proposed as two items")["passed"]
    assert _by_text(exps, "UI half routes to frontend-dashboard")["passed"]
    assert _by_text(exps, "API half routes to control-plane")["passed"]


def test_eval2_fails_when_registered_as_one_item(tmp_path: Path) -> None:
    run = _run(tmp_path, BASE_BACKLOG + _new_item(domain="control-plane", repo="control-plane"))
    exps = grade(run, 2)
    assert not _by_text(exps, "split was proposed as two items")["passed"]


def test_base_ids_match_the_shipped_fixture() -> None:
    """The grader's baseline must match the fixture, or every new-id count is wrong.

    If the fixture gains an item and BASE_IDS does not, that item reads as 'newly created'
    in every run — inverting the dedup verdict without touching the grader's logic.
    """
    fixture = PROJECT_ROOT / "skills" / "backlog-item" / "evals" / "fixtures" / "BACKLOG.md"
    if not fixture.is_file():
        pytest.skip("fixture not present")
    assert set(_blocks(fixture.read_text(encoding="utf-8"))) == BASE_IDS

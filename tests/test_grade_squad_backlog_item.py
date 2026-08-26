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

from grade_squad_backlog_item import BASE_IDS, _blocks, _field, grade  # noqa: E402

BASE_BACKLOG = """# Backlog

## Itens

## B-007 — Suspeita de N+1 no ingest   [ ]

domain: data-plane-ts
repo: theo-rag
status: killed
kill_reason: medido, uma query em lote

## B-014 — Reduzir round-trips do listing de traces   [ ]

domain: data-plane-ts
repo: theo-lens
suggested_mode: review
source: human
evidence: none-yet
why_now: o dashboard passou a carregar 30d por padrão
status: raw
dod:
  - a listagem faz um número de queries independente da contagem de spans
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
    assert "theo-lens" in blocks["B-014"]
    assert "theo-lens" not in blocks["B-007"], "block boundaries leaked into the neighbour"


def test_field_extracts_only_its_own_field() -> None:
    block = _blocks(BASE_BACKLOG)["B-014"]
    assert _field(block, "repo") == "theo-lens"
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
              domain: str = "data-plane-ts", repo: str = "theo-promptly") -> str:
    return f"""
## B-032 — Resolução de revisão nova demora alguns segundos   [ ]

domain: {domain}
repo: {repo}
suggested_mode: review
source: human
evidence: {evidence}
why_now: percebido ao editar prompts; sem gatilho declarado pelo relator
status: {status}
dod:
  - a revisão nova resolve na API em menos de 1s após o save
"""


def test_eval0_passes_on_a_correct_hunch(tmp_path: Path) -> None:
    run = _run(tmp_path, BASE_BACKLOG + _new_item())
    exps = grade(run, 0)
    assert _by_text(exps, "new B-NNN block was appended")["passed"]
    assert _by_text(exps, "evidence: none-yet")["passed"]
    assert _by_text(exps, "status: raw")["passed"]
    assert _by_text(exps, "repo is theo-promptly")["passed"]


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
    run = _run(tmp_path, BASE_BACKLOG + _new_item(domain="control-plane", repo="theo-cloud"))
    exps = grade(run, 0)
    assert not _by_text(exps, "repo is theo-promptly")["passed"]


def test_eval1_fails_when_prior_art_reached_the_registry(tmp_path: Path) -> None:
    """G5's whole point: the LangSmith comparison must never become a why_now."""
    leaked = BASE_BACKLOG + """
## B-032 — Waterfall de traces   [ ]

domain: data-plane-ts
repo: theo-lens
evidence: none-yet
why_now: o LangSmith tem um waterfall bonito e a gente devia ter também
status: raw
"""
    run = _run(tmp_path, leaked, transcript="Registrei o item.")
    exps = grade(run, 1)
    assert not _by_text(exps, "No B-NNN block carries the LangSmith")["passed"]


def test_eval1_passes_when_the_gate_fired(tmp_path: Path) -> None:
    transcript = (
        "Gate G5 disparou: a justificativa se apoia no LangSmith, outro projeto. "
        "Perguntaria ao usuário: reformular com um motivo local / falso positivo / cancelar."
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
    transcript = "Busquei no BACKLOG.md e achei o B-014, que já cobre exatamente isso. ITEM_MERGED."
    run = _run(tmp_path, BASE_BACKLOG, transcript=transcript)
    exps = grade(run, 3)
    assert _by_text(exps, "No new B-NNN id was allocated")["passed"]
    assert _by_text(exps, "searched BACKLOG.md")["passed"]
    assert _by_text(exps, "existing open item")["passed"]


def test_eval2_requires_two_items_in_the_right_domains(tmp_path: Path) -> None:
    split = BASE_BACKLOG + """
## B-032 — Tela branca quando o token expira   [ ]

domain: frontend-dashboard
repo: theo-cloud/dashboard
evidence: none-yet
status: raw

## B-033 — API devolve 500 em vez de 401   [ ]

domain: control-plane
repo: theo-cloud
evidence: none-yet
status: raw
"""
    run = _run(tmp_path, split, transcript="Isso abrange dois domínios (G3), então dividi em dois itens.")
    exps = grade(run, 2)
    assert _by_text(exps, "split was proposed as two items")["passed"]
    assert _by_text(exps, "UI half routes to frontend-dashboard")["passed"]
    assert _by_text(exps, "API half routes to control-plane")["passed"]


def test_eval2_fails_when_registered_as_one_item(tmp_path: Path) -> None:
    run = _run(tmp_path, BASE_BACKLOG + _new_item(domain="control-plane", repo="theo-cloud"))
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

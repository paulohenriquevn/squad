"""The lead decides flow, never content.

The fixture below is the real menu the first autonomous run stopped at, on
2026-08-31. It had measured its item, concluded correctly, labelled the right answer
`(Recommended)` — and waited anyway. That is the failure this watchdog exists for: a
session that is RIGHT and stops for permission, which is different from the four
failures `squad-lead`'s README records, all of which are a session being wrong.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from squad_lead import Lead, watch

# The menu, as captured. Option 1 moves the registry; option 2 asks for a decision
# only the sponsor holds.
REAL_MENU = """\
 B-022 é um T3 governance-blocked (decisão de fronteira de autenticação). Como quer proceder?
❯ 1. Adicionar blocked_by em B-022 e re-selecionar (Recommended)
     Escrevo `blocked_by:` no bloco de B-022, re-rodo o SELECT e trabalho o próximo item.
  2. Você toma a decisão T3 agora
  3. Parar aqui e relatar
"""

WORKING = "● Bash(python3 select_backlog_item.py BACKLOG.md)\n  ⎿ ITEM_SELECTED: B-022\n"


def _lead() -> Lead:
    return Lead(session="test")


# ── the distinction the whole thing rests on ──────────────────────────────────


def test_the_recommended_flow_option_is_confirmed() -> None:
    decision = _lead().decide(REAL_MENU)
    assert decision.action == "confirm"
    assert decision.item == "B-022"


def test_a_decision_only_a_person_holds_is_escalated() -> None:
    menu = REAL_MENU.replace("❯ 1.", "  1.").replace("  2. Você toma", "❯ 2. Você toma")
    assert _lead().decide(menu).action == "escalate"


@pytest.mark.parametrize("option", [
    "Aprovar o merge do PR",
    "Fazer o release da versão",
    "Você decide se mantemos a dependência",
    "Deletar o registro antigo",
    "Revogar a credencial no painel",
])
def test_content_options_are_never_confirmed(option: str) -> None:
    assert _lead().classify(option) == "content"


@pytest.mark.parametrize("option", [
    "Adicionar blocked_by em B-022 e re-selecionar",
    "Registrar o impedimento e seguir para o próximo item",
    "Re-run the SELECT and continue",
])
def test_flow_options_are_recognised(option: str) -> None:
    assert _lead().classify(option) == "flow"


def test_content_wins_over_flow_in_the_same_option() -> None:
    """A sponsor decision wrapped in a flow-sounding sentence is still a decision."""
    mixed = "Registrar o impedimento e você toma a decisão T3 agora"
    assert _lead().classify(mixed) == "content"


def test_an_unrecognised_option_is_escalated_not_guessed() -> None:
    menu = "❯ 1. Reticulate the splines\n  2. Something else\n"
    decision = _lead().decide(menu)
    assert decision.action == "escalate"


def test_a_flow_option_the_session_did_not_recommend_is_escalated() -> None:
    """`(Recommended)` is the session stating its own answer. Without it there is none."""
    menu = "❯ 1. Adicionar blocked_by e re-selecionar\n  2. Outra coisa\n"
    assert _lead().decide(menu).action == "escalate"


def test_a_sole_flow_option_needs_no_recommendation() -> None:
    """With one option there is nothing to choose between."""
    assert _lead().decide("❯ 1. Re-run the SELECT and continue\n").action == "confirm"


def test_a_working_session_is_left_alone() -> None:
    assert _lead().decide(WORKING).action == "wait"


# ── its own stopping criteria ─────────────────────────────────────────────────


def test_the_same_question_twice_is_a_loop_not_progress() -> None:
    lead = _lead()
    first = lead.decide(REAL_MENU)
    lead.answered.add(f"{first.item}|{first.option}")
    assert lead.decide(REAL_MENU).action == "exhausted"


def test_an_item_unblocked_too_often_is_abandoned() -> None:
    lead = Lead(session="test", max_per_item=2)
    lead.interventions["B-022"] = 2
    assert lead.decide(REAL_MENU).action == "exhausted"


def test_the_ceiling_is_per_item_not_global() -> None:
    lead = Lead(session="test", max_per_item=1)
    lead.interventions["B-022"] = 1
    other = REAL_MENU.replace("B-022", "B-033")
    assert lead.decide(other).action == "confirm"


# ── the loop ──────────────────────────────────────────────────────────────────


def test_a_busy_session_is_never_interrupted(tmp_path: Path, monkeypatch) -> None:
    """Answering a menu the session was about to move past is worse than not helping."""
    lead = _lead()
    monkeypatch.setattr(lead, "capture", lambda: REAL_MENU)
    monkeypatch.setattr(lead, "confirm", lambda d: pytest.fail("interrupted a busy session"))
    marker = tmp_path / "log"
    marker.write_text("x", encoding="utf-8")          # mtime = now, so it is working
    monkeypatch.setattr("squad_lead.time.sleep", lambda s: None)
    assert watch(lead, marker, None, poll=0, rounds=1) == 0


def test_a_vanished_session_ends_the_watch(monkeypatch) -> None:
    lead = _lead()
    monkeypatch.setattr(lead, "capture", lambda: None)
    assert watch(lead, None, None, poll=0, rounds=1) == 1


def test_every_decision_is_logged(tmp_path: Path, monkeypatch) -> None:
    """A lead nobody can audit is a lead nobody should trust."""
    import json

    lead = _lead()
    monkeypatch.setattr(lead, "capture", lambda: REAL_MENU)
    monkeypatch.setattr(lead, "confirm", lambda d: True)
    monkeypatch.setattr("squad_lead.time.sleep", lambda s: None)
    log = tmp_path / "lead.jsonl"
    watch(lead, None, log, poll=0, rounds=1)
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert entry["event"] == "confirm" and entry["item"] == "B-022"


# ── both found by watching it run, minutes after it started ───────────────────


def test_a_slash_command_is_not_the_act_it_names() -> None:
    """`/idea-to-release` contains "release"; the cycle it names stops before one.

    Without the strip, the lead escalated on the most common option there is — "run
    the cycle" — which is the difference between a useful watchdog and a silent one.
    """
    assert _lead().classify("Rodar /idea-to-release B-033 no que é autônomo (Recommended)") == "flow"


def test_a_real_release_request_is_still_content() -> None:
    """Stripping commands must not blind it to the act itself."""
    assert _lead().classify("Fazer o release da v2.1 agora") == "content"
    assert _lead().classify("Aprovar o merge do PR") == "content"


def test_the_item_comes_from_the_option_not_the_scrollback() -> None:
    screen = (
        "  contexto antigo sobre B-022 rolando na tela\n"
        "❯ 1. Rodar /idea-to-release B-033 no que é autônomo (Recommended)\n"
        "  2. Outra coisa\n"
    )
    assert _lead().decide(screen).item == "B-033"


def test_the_screen_is_the_fallback_when_the_option_names_no_item() -> None:
    screen = "  trabalhando em B-022\n❯ 1. Re-run the SELECT and continue (Recommended)\n  2. Parar\n"
    assert _lead().decide(screen).item == "B-022"

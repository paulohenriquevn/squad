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

from squad_lead import Lead, watch, Decision

# The menu, as captured. Option 1 moves the registry; option 2 asks for a decision
# only the sponsor holds.
# english-only: captured verbatim from the live session; translating the fixture
# would test a menu that never appeared and stop testing the one that did.
REAL_MENU = """\
 B-022 é um T3 governance-blocked (decisão de fronteira de autenticação). Como quer proceder?  # english-only: captured verbatim from the live session
❯ 1. Adicionar blocked_by em B-022 e re-selecionar (Recommended)
     Escrevo `blocked_by:` no bloco de B-022, re-rodo o SELECT e trabalho o próximo item.
  2. Você toma a decisão T3 agora  # english-only: captured verbatim from the live session
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
    # english-only: moving the cursor within the verbatim fixture above.
    menu = REAL_MENU.replace("❯ 1.", "  1.").replace("  2. Você toma", "❯ 2. Você toma")  # english-only: captured verbatim from the live session
    assert _lead().decide(menu).action == "escalate"


@pytest.mark.parametrize("option", [
    "Aprovar o merge do PR",
    "Fazer o release da versão",
    "Você decide se mantemos a dependência",  # english-only: captured verbatim from the live session
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
    mixed = "Registrar o impedimento e você toma a decisão T3 agora"  # english-only: captured verbatim from the live session
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
    assert _lead().classify("Rodar /idea-to-release B-033 no que é autônomo (Recommended)") == "flow"  # english-only: the live option, verbatim


def test_a_real_release_request_is_still_content() -> None:
    """Stripping commands must not blind it to the act itself."""
    assert _lead().classify("Fazer o release da v2.1 agora") == "content"
    assert _lead().classify("Aprovar o merge do PR") == "content"


def test_the_item_comes_from_the_option_not_the_scrollback() -> None:
    screen = (
        "  contexto antigo sobre B-022 rolando na tela\n"
        "❯ 1. Rodar /idea-to-release B-033 no que é autônomo (Recommended)\n"  # english-only: the live option, verbatim
        "  2. Outra coisa\n"
    )
    assert _lead().decide(screen).item == "B-033"


def test_the_screen_is_the_fallback_when_the_option_names_no_item() -> None:
    screen = "  trabalhando em B-022\n❯ 1. Re-run the SELECT and continue (Recommended)\n  2. Parar\n"
    assert _lead().decide(screen).item == "B-022"


# ── a turn handed back, with no menu to read ──────────────────────────────────
#
# Measured on 2026-08-31: the executing session ended its turn and stopped for TWO
# HOURS, reporting that five reviewer sign-off checkboxes were waiting and a language
# gate was blocked. The lead sat silent the whole time because it only reads menus, and
# the user found it by looking at an empty pane. Silence from a watchdog is supposed to
# mean "nothing to report", not "I cannot see this".


IDLE_PROMPT = "  ⎿ report written\n\n❯ \n────────\n  workspace*\n"


def test_a_handed_back_turn_is_reported_once_it_goes_quiet() -> None:
    lead = Lead(session="test", stalled_seconds=900)
    assert lead.decide(IDLE_PROMPT, idle=1200).action == "stalled"


def test_a_brief_pause_is_not_a_handed_back_turn() -> None:
    """A session thinking hard also looks idle; the threshold is well above that."""
    lead = Lead(session="test", stalled_seconds=900)
    assert lead.decide(IDLE_PROMPT, idle=200).action == "wait"


def test_a_waiting_menu_is_still_answered_not_called_stalled() -> None:
    """The menu path must win: that one the lead can actually move."""
    lead = Lead(session="test", stalled_seconds=900)
    assert lead.decide(REAL_MENU, idle=5000).action == "confirm"


def test_stalled_is_reported_and_never_acted_on(monkeypatch, tmp_path: Path) -> None:
    """A session that ended its turn is not stuck mid-thought; typing into it would be
    the lead inventing work rather than unblocking it."""
    import os
    import time as _time

    lead = Lead(session="test", stalled_seconds=10)
    monkeypatch.setattr(lead, "capture", lambda: IDLE_PROMPT)
    monkeypatch.setattr(lead, "confirm", lambda d: pytest.fail("acted on a stalled session"))
    monkeypatch.setattr("squad_lead.time.sleep", lambda s: None)
    marker = tmp_path / "log"
    marker.write_text("x", encoding="utf-8")
    old = _time.time() - 600
    os.utime(marker, (old, old))
    assert watch(lead, marker, None, poll=0, rounds=1) == 0


def test_an_unmeasured_idle_is_never_called_stalled() -> None:
    """No activity marker means "not measured"; asserting a duration from that would be
    the lead reporting something it never observed."""
    lead = Lead(session="test", stalled_seconds=10)
    assert lead.decide(IDLE_PROMPT, idle=float("inf")).action == "wait"


def test_the_stall_says_how_long(monkeypatch, tmp_path: Path) -> None:
    import json
    import os
    import time as _time

    lead = Lead(session="test", stalled_seconds=10)
    monkeypatch.setattr(lead, "capture", lambda: IDLE_PROMPT)
    monkeypatch.setattr("squad_lead.time.sleep", lambda s: None)
    marker = tmp_path / "log"
    marker.write_text("x", encoding="utf-8")
    old = _time.time() - 600
    os.utime(marker, (old, old))
    log = tmp_path / "lead.jsonl"
    watch(lead, marker, log, poll=0, rounds=1)
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert entry["event"] == "stalled"


def test_the_watch_continues_after_reporting_a_stall(monkeypatch, tmp_path: Path) -> None:
    """Exiting would leave the session unwatched from the first stall onward, and the
    next thing that happens is often a menu the lead could have answered.

    Found by shipping the exit: the lead reported a 128-minute stall correctly and then
    died, so a restart was needed before it could see anything again.
    """
    import os
    import time as _time

    lead = Lead(session="test", stalled_seconds=10)
    monkeypatch.setattr(lead, "capture", lambda: IDLE_PROMPT)
    monkeypatch.setattr("squad_lead.time.sleep", lambda s: None)
    marker = tmp_path / "log"
    marker.write_text("x", encoding="utf-8")
    old = _time.time() - 600
    os.utime(marker, (old, old))

    watch(lead, marker, None, poll=0, rounds=3)
    assert lead.reported_stall is True


def test_the_same_stall_is_not_reported_twice(monkeypatch, tmp_path: Path) -> None:
    """Repeating it every poll buries the line in a log nobody reads."""
    import json
    import os
    import time as _time

    lead = Lead(session="test", stalled_seconds=10)
    monkeypatch.setattr(lead, "capture", lambda: IDLE_PROMPT)
    monkeypatch.setattr("squad_lead.time.sleep", lambda s: None)
    marker = tmp_path / "log"
    marker.write_text("x", encoding="utf-8")
    old = _time.time() - 600
    os.utime(marker, (old, old))
    log = tmp_path / "lead.jsonl"

    watch(lead, marker, log, poll=0, rounds=4)
    stalls = [l for l in log.read_text(encoding="utf-8").splitlines()
              if json.loads(l)["event"] == "stalled"]
    assert len(stalls) == 1, stalls


def test_a_session_that_moves_again_can_stall_again(monkeypatch, tmp_path: Path) -> None:
    """The next stall is a new fact, not a repeat of the old one."""
    lead = Lead(session="test", stalled_seconds=10)
    lead.reported_stall = True
    monkeypatch.setattr(lead, "capture", lambda: IDLE_PROMPT)
    monkeypatch.setattr("squad_lead.time.sleep", lambda s: None)
    marker = tmp_path / "log"
    marker.write_text("x", encoding="utf-8")     # mtime = now, so it is working
    watch(lead, marker, None, poll=0, rounds=1)
    assert lead.reported_stall is False


# ── a handed-back turn stops the item, not the queue ─────────────────────────


def _lead_with_select(tmp_path, answer: dict):
    """A Lead whose SELECT is a stub returning `answer`. The subprocess call is what
    is being replaced, not the decision — the point is what the lead does with an
    answer, not that Python can run a script."""
    lead = Lead(session="s", project=tmp_path, stalled_seconds=900)
    lead.next_item = lambda: (answer.get("item"), answer.get("why", ""))
    return lead


def test_a_handed_back_turn_starts_the_next_item(tmp_path: Path) -> None:
    """Reporting the stall was right about the item and wrong about the backlog.
    Measured on 2026-08-31: /implement halted on B-033 needing a sponsor decision and
    the queue sat still for 85 minutes with 25 other selectable items waiting."""
    lead = _lead_with_select(tmp_path, {"item": "B-057", "why": "oldest unblocked"})
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "start"
    assert decision.item == "B-057"
    assert decision.option == "/idea-to-release B-057"


def test_the_lead_does_not_start_the_same_item_twice(tmp_path: Path) -> None:
    """Starting one item over and over is the loop the per-item ceiling exists to
    stop, one level up."""
    lead = _lead_with_select(tmp_path, {"item": "B-057", "why": "oldest unblocked"})
    lead.started.add("B-057")
    assert lead.decide("no menu here", idle=1000).action == "stalled"


def test_a_blocked_backlog_is_reported_not_forced(tmp_path: Path) -> None:
    """A queue where everything is held is exactly the case only a person clears."""
    lead = _lead_with_select(
        tmp_path, {"item": None, "why": "BACKLOG_BLOCKED: every item is held"})
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "stalled"
    assert "BACKLOG_BLOCKED" in decision.reason


def test_without_a_project_the_lead_starts_nothing(tmp_path: Path) -> None:
    """No registry to read means no answer to relay. It reports, as it always did."""
    lead = Lead(session="s", stalled_seconds=900)
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "stalled"
    assert "cannot ask SELECT" in decision.reason


def test_the_lead_never_types_anything_but_the_template(tmp_path: Path) -> None:
    """The one thing it types unprompted is built from a template with a validated id.
    An id that does not match is refused at the point of typing, not only where it was
    chosen — that is where it becomes keystrokes in a session with no prompts."""
    lead = Lead(session="s", project=tmp_path)
    assert lead.start(Decision("start", "x", "whatever", "B-057; rm -rf /")) is False
    assert lead.start(Decision("start", "x", "whatever", "")) is False
    assert lead.started == set()


def test_a_still_quiet_session_waits(tmp_path: Path) -> None:
    """Below the stall horizon nothing happens — a session thinking hard looks idle."""
    lead = _lead_with_select(tmp_path, {"item": "B-057"})
    assert lead.decide("no menu here", idle=10).action == "wait"


def test_an_unmeasured_idle_never_starts_anything(tmp_path: Path) -> None:
    """Without an activity marker `idle` is infinite, which means NOT MEASURED. Acting
    on it would be the lead asserting a duration it never observed."""
    lead = _lead_with_select(tmp_path, {"item": "B-057"})
    assert lead.decide("no menu here", idle=float("inf")).action == "wait"

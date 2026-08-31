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
    # The message invokes the cycle AND carries what the lead read. A handoff with no
    # state is not a handoff, it is an order — and on 2026-08-31 the session refused
    # one, correctly, after ten minutes of work the bare command ignored.
    assert "/idea-to-release B-057" in decision.option
    assert "oldest unblocked" in decision.option
    assert "não escolha por mim" in decision.option  # english-only: the session's language


def test_an_attempt_that_just_happened_is_not_repeated(tmp_path: Path) -> None:
    """Immediately after typing, nothing has had time to move. Retrying here would be
    the loop the ceiling exists to stop — and moving on would abandon work in progress,
    so the answer is to wait for this one."""
    import time
    lead = _lead_with_select(tmp_path, {"item": "B-057", "why": "oldest unblocked"})
    lead.attempts["B-057"] = (time.time(), 0)
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "wait"
    assert "under way" in decision.reason


def test_an_attempt_that_never_landed_is_retried(tmp_path: Path) -> None:
    """Measured on 2026-08-31: the lead typed `/idea-to-release B-169`, the operator
    stopped the run, the stream recorded nothing, and every poll after that answered
    "already started once by this lead". One attempt was final, forever."""
    import time
    lead = _lead_with_select(tmp_path, {"item": "B-169", "why": "cause of a halt"})
    lead.attempts["B-169"] = (time.time() - 400, 0)     # tried, produced nothing
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "start"
    assert "did not land" in decision.reason


def test_an_item_that_moved_and_came_back_may_run_again(tmp_path: Path) -> None:
    """Something sent the work back. That is the chain working, not a loop — the same
    distinction the drift checker draws between rework and disorder."""
    import time
    lead = _lead_with_select(tmp_path, {"item": "B-057", "why": "back in the queue"})
    lead.attempts["B-057"] = (time.time(), 0)
    lead._event_count = lambda item: 3                  # the stream grew since
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "start"
    assert "moved since the last attempt" in decision.reason


def test_the_ceiling_still_stops_a_real_loop(tmp_path: Path) -> None:
    """Retrying is allowed; retrying forever is not. `max_per_item` was always the
    right freio and is now the only one."""
    import time
    lead = _lead_with_select(tmp_path, {"item": "B-057", "why": "oldest"})
    lead.interventions["B-057"] = lead.max_per_item
    lead.attempts["B-057"] = (time.time() - 9999, 0)
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
    assert lead.attempts == {}


def test_a_still_quiet_session_waits(tmp_path: Path) -> None:
    """Below the stall horizon nothing happens — a session thinking hard looks idle."""
    lead = _lead_with_select(tmp_path, {"item": "B-057"})
    assert lead.decide("no menu here", idle=10).action == "wait"


def test_an_unmeasured_idle_never_starts_anything(tmp_path: Path) -> None:
    """Without an activity marker `idle` is infinite, which means NOT MEASURED. Acting
    on it would be the lead asserting a duration it never observed."""
    lead = _lead_with_select(tmp_path, {"item": "B-057"})
    assert lead.decide("no menu here", idle=float("inf")).action == "wait"


# ── a flag that switches off a gate is never flow ────────────────────────────


def test_an_option_with_a_relaxing_flag_is_escalated(tmp_path: Path) -> None:
    """Measured on 2026-08-31, minutes after the lead gained the power to start items:
    the session offered "Rodar /idea-to-release B-057 --allow-dirty-tree até halt  # english-only: the menu quoted verbatim
    natural (Recommended)" and the lead confirmed it. The classifier read "Rodar",
    matched a flow marker, and never looked at the flag.

    Running the cycle is flow. Running it with a precondition switched off is a
    decision to accept the risk that precondition exists to prevent."""
    lead = Lead(session="s")
    assert lead.classify("Rodar /idea-to-release B-057 --allow-dirty-tree (Recommended)") == "content"
    assert lead.classify("continuar com --no-verify") == "content"
    assert lead.classify("prosseguir --skip-tests") == "content"
    assert lead.classify("continue --force") == "content"


def test_the_same_option_without_the_flag_stays_flow(tmp_path: Path) -> None:
    """The flag is what decides, not the command. Escalating every cycle invocation
    would put the lead back to answering nothing."""
    lead = Lead(session="s")
    assert lead.classify("Rodar /idea-to-release B-057 (Recommended)") == "flow"


def test_the_escalation_names_the_flag_it_refused(tmp_path: Path) -> None:
    """A lead nobody can contest is a lead nobody should trust — so the log says
    which precondition it declined to switch off."""
    lead = Lead(session="s")
    screen = "❯ 1. Rodar /idea-to-release B-057 --allow-dirty-tree (Recommended)\n"
    decision = lead.decide(screen, idle=200)
    assert decision.action == "escalate"
    assert "--allow" in decision.reason


# ── the horizon, and the check that lets it be short ─────────────────────────


def test_the_stall_horizon_is_the_measured_one(tmp_path: Path) -> None:
    """900s came from a belief — "a session thinking hard also looks idle briefly" —
    that was never measured and is wrong. Measured on 2026-08-31: mid-task the marker
    read 0s and 3s idle; with the turn handed back it went untouched across 127
    consecutive samples. The two states are far apart, not close."""
    assert Lead(session="s").stalled_seconds == 120


def test_the_lead_re_reads_the_marker_before_typing(tmp_path: Path) -> None:
    """Between deciding and typing there is a poll interval. A session that woke up in
    it would get a command pasted into whatever it was composing."""
    marker = tmp_path / "run.log"
    marker.write_text("x", encoding="utf-8")          # just touched: not quiet
    assert Lead(session="s").still_quiet(marker) is False


def test_a_long_quiet_marker_passes_the_second_check(tmp_path: Path) -> None:
    import os
    import time
    marker = tmp_path / "run.log"
    marker.write_text("x", encoding="utf-8")
    old = time.time() - 600
    os.utime(marker, (old, old))
    assert Lead(session="s").still_quiet(marker) is True


def test_no_marker_means_the_lead_does_not_type(tmp_path: Path) -> None:
    """No marker is NOT MEASURED, and the lead does not type on an unmeasured
    session — the same rule that keeps an infinite idle from reporting a stall."""
    assert Lead(session="s").still_quiet(None) is False


def test_a_session_that_woke_up_is_not_typed_into(tmp_path: Path) -> None:
    """End to end through `watch`: the decision was `start`, the marker is fresh, and
    nothing is sent."""
    import squad_lead
    marker = tmp_path / "run.log"
    marker.write_text("x", encoding="utf-8")
    log = tmp_path / "lead.jsonl"
    lead = Lead(session="s", project=tmp_path, stalled_seconds=120)
    lead.next_item = lambda: ("B-057", "oldest unblocked")
    lead.capture = lambda: "no menu here"
    typed: list[str] = []
    lead.start = lambda d: typed.append(d.item) or True   # never reached
    watch(lead, marker, log, poll=0, rounds=1)
    assert typed == []


# ── asking an agent, from outside the session ────────────────────────────────


def test_agents_are_off_unless_asked_for(tmp_path: Path) -> None:
    """A daemon that calls a model unattended is a different thing from a daemon that
    reads a screen, and the difference should be chosen, not inherited."""
    lead = Lead(session="s", project=tmp_path)
    answer, why = lead.ask_agent("squad-lead", "anything")
    assert answer is None
    assert "--agents-when-stuck" in why


def test_the_same_agent_is_not_asked_twice_in_a_row(tmp_path: Path) -> None:
    """Being stuck is a STATE, not an event. Without a cooldown the lead would re-ask
    on every poll and bill for the same question all night."""
    import time
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True,
                agent_cooldown=1800)
    lead.agent_asked["squad-lead"] = time.time()
    answer, why = lead.ask_agent("squad-lead", "anything")
    assert answer is None
    assert "cooldown" in why


def test_an_agent_answer_is_logged_not_acted_on(tmp_path: Path) -> None:
    """The lead pays for a judgement and records it. Acting on it would be the lead
    deciding the very thing it just paid someone else to think about."""
    lead = _lead_with_select(tmp_path, {"item": None, "why": "BACKLOG_BLOCKED: all held"})
    lead.agents_when_stuck = True
    lead.ask_agent = lambda agent, q: ("NEXT: register the cause named in the report", "answered")
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "asked"
    assert "register the cause" in decision.reason
    assert decision.option == ""          # nothing to type


def test_a_silent_agent_falls_back_to_reporting_the_stall(tmp_path: Path) -> None:
    """No answer is not an excuse to invent one. The stall is reported as it always
    was, with the reason the agent could not help."""
    lead = _lead_with_select(tmp_path, {"item": None, "why": "BACKLOG_BLOCKED: all held"})
    lead.agents_when_stuck = True
    lead.ask_agent = lambda agent, q: (None, "squad-lead did not answer in 300s")
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "stalled"
    assert "did not answer" in decision.reason


def test_the_prompt_carries_the_constraint_the_agent_inherits(tmp_path: Path) -> None:
    """The agent file states the rule and so does the prompt. A prompt that
    contradicted it would be the one place the rule could be lost."""
    import squad_lead
    prompt = squad_lead._STUCK_PROMPT
    assert "flow" in prompt
    assert "do not relax any gate" in prompt.lower()
    assert "only a person" in prompt


# ── a phase that stopped at a human gate leaves a trace, and the lead reads it ──


def _project_with(tmp_path: Path, *events, blocking: str = "AWAITING_HUMAN\nFAIL\n") -> Path:
    import json
    (tmp_path / "rules").mkdir(exist_ok=True)
    (tmp_path / "rules" / "blocking-verdicts.txt").write_text(blocking, encoding="utf-8")
    (tmp_path / "records").mkdir(exist_ok=True)
    (tmp_path / "records" / "cycle-events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    return tmp_path


def _end(cycle: str, slug: str, verdict: str) -> dict:
    return {"type": "cycle:phase:end", "cycle": cycle, "slug": slug,
            "verdict": verdict, "timestamp": "2026-08-31T20:00:00Z"}


def test_an_item_awaiting_a_human_is_not_restarted(tmp_path: Path) -> None:
    """Measured on 2026-08-31: B-058 and B-059 were worked, halted at a gate only a
    person opens, and emitted NOTHING. The lead saw no event, concluded the attempt had
    not landed, and restarted B-059 — the only conclusion available to it.

    `AWAITING_HUMAN` exists so this branch has something to read."""
    import time
    project = _project_with(tmp_path, _end("plan", "B-059", "AWAITING_HUMAN"))
    lead = Lead(session="s", project=project)
    lead.attempts["B-059"] = (time.time() - 9999, 0)     # old enough to retry
    allowed, why = lead.may_start("B-059", time.time())
    assert allowed is False
    assert "only a person moves this" in why


def test_an_item_whose_last_verdict_passed_may_be_started(tmp_path: Path) -> None:
    """The rule is about verdicts that HOLD, not about having run before."""
    import time
    project = _project_with(tmp_path, _end("plan", "B-059", "SHIPPABLE"))
    lead = Lead(session="s", project=project)
    lead.attempts["B-059"] = (time.time() - 9999, 0)
    assert lead.may_start("B-059", time.time())[0] is True


def test_an_unreadable_rule_file_costs_a_retry_never_a_false_stop(tmp_path: Path) -> None:
    """Empty is NOT MEASURED. Treating it as "everything blocks" would let a missing
    file stop the queue, which is the worse direction."""
    import time
    project = _project_with(tmp_path, _end("plan", "B-059", "AWAITING_HUMAN"))
    (project / "rules" / "blocking-verdicts.txt").unlink()
    lead = Lead(session="s", project=project)
    lead.attempts["B-059"] = (time.time() - 9999, 0)
    assert lead.may_start("B-059", time.time())[0] is True


def test_the_lead_reads_the_same_list_the_board_and_the_checker_read(tmp_path: Path) -> None:
    """Three readers, one file. The fourth copy is where they start disagreeing."""
    kit = Path(__file__).resolve().parents[1]
    lead = Lead(session="s", project=kit)
    names = lead._blocking_verdicts()
    assert "AWAITING_HUMAN" in names
    assert "FAIL" in names


# ── the menu says which item, the scrollback does not ────────────────────────


def test_the_item_comes_from_the_option(tmp_path: Path) -> None:
    lead = Lead(session="s")
    assert lead._item_of("Rodar /idea-to-release B-057 (Recommended)", "") == "B-057"


def test_the_item_comes_from_the_menu_heading_when_the_option_has_none(tmp_path: Path) -> None:
    """The heading is where a session states what it is asking about."""
    screen = ("B-059 registrou 'adicionar gate'. Qual escopo o chain deve implementar?\n"  # english-only: a captured screen, quoted verbatim
              "\n"
              "❯ 1. Gate + fix nas 8 rotas (Recommended)\n"
              "  2. Gate-only\n")
    assert Lead(session="s")._item_of("Gate + fix nas 8 rotas (Recommended)", screen) == "B-059"


def test_an_id_from_the_scrollback_is_never_used(tmp_path: Path) -> None:
    """Measured twice on 2026-08-31. The second time the lead logged `escalate B-033`
    for a menu titled "B-059 scope", because the option carried no id and the fallback
    found `B-033/B-057` in a paragraph twenty lines up that mentioned them in passing.

    An id that did not come from the menu is a guess, and this lead is built on not
    guessing. Empty is the honest answer."""
    screen = ("o handoff de B-033/B-057 que está pendente, e o escopo excede o que\n"  # english-only: a captured screen, quoted verbatim
              + "\n" * 20 +
              "Qual escopo o chain deve implementar?\n"  # english-only: a captured screen, quoted verbatim
              "\n"
              "❯ 1. Gate + fix nas 8 rotas (Recommended)\n")
    assert Lead(session="s")._item_of("Gate + fix nas 8 rotas (Recommended)", screen) == ""


# ── escalating does not kill the watch ───────────────────────────────────────


def test_a_question_already_with_a_person_is_not_raised_again(tmp_path: Path) -> None:
    """Raised once. Repeating it every poll buries the log this lead exists to keep
    readable — which is what exiting used to buy, at the price of no lead at all."""
    lead = Lead(session="s")
    screen = "❯ 1. You take the T3 decision now\n"
    first = lead.decide(screen, idle=200)
    assert first.action == "escalate"
    lead.surfaced.add(f"{first.item}|{first.option}")
    assert lead.decide(screen, idle=200).action == "wait"


def test_the_watch_survives_an_escalation(tmp_path: Path) -> None:
    """Measured on 2026-08-31 at 20:39: the lead correctly refused a scope decision —
    the best call it made all day — and then exited, leaving the session unwatched from
    that moment on."""
    log = tmp_path / "lead.jsonl"
    lead = Lead(session="s")
    lead.capture = lambda: "❯ 1. You take the T3 decision now\n"
    assert watch(lead, None, log, poll=0, rounds=3) == 0
    entries = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(entries) == 1, "the same question was raised more than once"
    assert lead.surfaced, "the lead did not remember what it surfaced"


# ── content reaches the doctrine before it reaches a person ──────────────────


_MENU = ("Qual escopo o chain deve implementar?\n"  # english-only: a captured screen, quoted verbatim
         "\n"
         "❯ 1. Gate + fix nas 8 rotas (Recommended)\n"  # english-only: idem
         "  2. Gate-only, itens separados\n")           # english-only: idem


def test_a_doctrine_answer_selects_the_option(tmp_path: Path) -> None:
    """The watchdog still refuses — a scope call is not flow. What changed is where the
    refusal goes: to the file that decides it, instead of to a person who said they
    enter at the initial backlog and nowhere else."""
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: ("OPTION: 2\nRULE APPLIED: Scope grew during measurement",
                                   "answered")
    decision = lead.decide(_MENU, idle=200)
    assert decision.action == "choose"
    assert decision.option_number == "2"
    assert "Scope grew during measurement" in decision.reason


def test_a_number_without_a_rule_is_not_an_answer(tmp_path: Path) -> None:
    """A choice with no rule named is the agent improvising, which is precisely what
    the envelope replaced."""
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: ("OPTION: 2", "answered")
    assert lead.decide(_MENU, idle=200).action == "escalate"


def test_no_rule_falls_back_to_a_person(tmp_path: Path) -> None:
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: ("NO RULE: nothing here covers a licence question",
                                   "answered")
    assert lead.decide(_MENU, idle=200).action == "escalate"


def test_an_option_number_the_menu_does_not_have_is_refused(tmp_path: Path) -> None:
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: ("OPTION: 9\nRULE APPLIED: Scope grew", "answered")
    assert lead.decide(_MENU, idle=200).action == "escalate"


def test_the_floor_is_never_reached_by_doctrine(tmp_path: Path) -> None:
    """A relaxing flag is refused before the agent is asked, and refused again if the
    agent somehow picks one. The floor is not a decision anyone delegates."""
    menu = ("❯ 1. Rodar com --allow-dirty-tree (Recommended)\n"  # english-only: a captured screen
            "  2. Parar\n")                                      # english-only: idem
    asked = []
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: asked.append(q) or ("OPTION: 1\nRULE APPLIED: x", "answered")
    decision = lead.decide(menu, idle=200)
    assert decision.action == "escalate"
    assert asked == [], "the agent was asked about something on the floor"


def test_the_cursor_is_re_read_before_enter(tmp_path: Path) -> None:
    """Arrow keys, then a re-read. If the cursor is not where the arrows should have put
    it, something else moved the menu and Enter would take the wrong option."""
    lead = Lead(session="s")
    lead.capture = lambda: "❯ 1. still on one\n  2. the target\n"   # never moved
    sent = []
    import subprocess as sp
    original = sp.run
    sp.run = lambda *a, **k: sent.append(a[0][-1]) or original(["true"], **{k2: v for k2, v in k.items() if k2 != "check"})
    try:
        ok = lead.choose("❯ 1. still on one\n  2. the target\n",
                         Decision("choose", "x", "the target", "B-001", option_number="2"))
    finally:
        sp.run = original
    assert ok is False
    assert "Enter" not in sent, "Enter was pressed although the cursor had not moved"


# ── a failure to ask is not an answer ────────────────────────────────────────


def test_an_error_on_stdout_is_not_an_answer(tmp_path: Path) -> None:
    """`claude -p` reports a blown budget on STDOUT and exits 0. Measured: a one-word
    question exceeded a 0.50 cap, the lead read `Error: Exceeded USD budget` as the
    agent's reply, found no rule in it, and escalated saying no rule covered the case.
    It had never been asked."""
    import subprocess
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    completed = subprocess.CompletedProcess([], 0, "Error: Exceeded USD budget (0.5)", "")
    lead_run = subprocess.run
    try:
        subprocess.run = lambda *a, **k: completed
        answer, note = lead.ask_agent("squad-lead", "anything")
    finally:
        subprocess.run = lead_run
    assert answer is None
    assert "could not answer" in note


def test_why_the_doctrine_did_not_decide_reaches_the_log(tmp_path: Path) -> None:
    """"The doctrine has no rule for this" and "nobody was asked" are opposite facts.
    A log that renders them identically reports a gap in the envelope that is not
    there — and the gap is the one thing meant to go back to the human."""
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: (None, "squad-lead could not answer: Error: budget")
    decision = lead.decide(_MENU, idle=200)
    assert decision.action == "escalate"
    assert "could not answer" in decision.reason


def test_a_real_no_rule_says_so(tmp_path: Path) -> None:
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: ("NO RULE: licence questions are not covered", "answered")
    decision = lead.decide(_MENU, idle=200)
    assert "found no rule" in decision.reason


def test_the_budget_clears_the_measured_cost(tmp_path: Path) -> None:
    """Guessed twice, measured once. 0.50 and 3.00 both blocked every consultation
    silently; the real menu consultation — read the envelope, the registry and the
    stream, then answer — cost USD 3.67 over two minutes."""
    assert Lead(session="s").agent_budget_usd >= 3.67


# ── a numbered paragraph is not a menu ───────────────────────────────────────


_PROSE_THEN_MENU = (
    "  Recomendação\n"                                       # english-only: a captured screen
    "\n"
    "  1. Atualizar registro no BACKLOG com a descoberta\n"   # english-only: idem
    "  2. Halt aqui — não estou expandindo escopo\n"          # english-only: idem
    "\n"
    "Qual escopo o chain deve implementar?\n"                 # english-only: idem
    "\n"
    "  1. Gate + fix nas 8 rotas (Recommended)\n"             # english-only: idem
    "❯ 2. Gate-only, itens separados\n"                       # english-only: idem
    "  3. Só a gate, aceitar caveat\n"                        # english-only: idem
)


def test_a_written_recommendation_is_not_read_as_the_menu(tmp_path: Path) -> None:
    """`1. do this` is also how a session writes a recommendation in prose, and both
    shapes sit on the same screen.

    Measured: the lead recorded a sentence from a paragraph as the option it had
    chosen, and handed the agent two lists spliced together. The cursor is what tells
    them apart — exactly one line carries it, and it is in the real menu."""
    options = Lead(session="s")._menu_options(_PROSE_THEN_MENU)
    texts = [t for _, t in options]
    assert len(options) == 3, texts
    assert not any("Atualizar registro" in t for t in texts)
    assert any("Gate-only" in t for t in texts)


def test_the_option_chosen_is_the_menu_one_not_the_paragraph_one(tmp_path: Path) -> None:
    """Both lists have a "2". Picking the wrong one meant recording — and fingerprinting
    — a decision about a sentence nobody was offered."""
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: ("OPTION: 2\nRULE APPLIED: Scope grew during measurement",
                                   "answered")
    decision = lead.decide(_PROSE_THEN_MENU, idle=200)
    assert decision.action == "choose"
    assert "Gate-only" in decision.option
    assert "Halt aqui" not in decision.option  # english-only: quoting the screen


def test_no_cursor_means_no_menu(tmp_path: Path) -> None:
    """Numbered lines with nothing selected are a list, not a menu."""
    assert Lead(session="s")._menu_options("  1. first\n  2. second\n") == []


# ── the same case gets the same answer ───────────────────────────────────────


_ESCAPE_MENU = ("Qual escopo?\n\n"                      # english-only: a captured screen
                "❯ 1. Gate-only, itens separados\n"     # english-only: idem
                "  2. Type something.\n")


def test_an_escape_with_no_instruction_is_refused(tmp_path: Path) -> None:
    """"Type something." opens a field. On its own that answers nothing — the agent
    picked it once and cited a rule for it, having said nothing to type."""
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: ("OPTION: 2\nRULE APPLIED: Scope grew", "answered")
    decision = lead.decide(_ESCAPE_MENU, idle=200)
    assert decision.action == "escalate"
    assert "without saying what to type" in decision.reason


def test_an_escape_with_an_instruction_is_taken(tmp_path: Path) -> None:
    """The door out of a menu that offers nothing the doctrine prescribes. Observed:
    an agent correctly diagnosed that the real cause was not among the options and had
    no way to act on its own diagnosis — the diagnosis was right and worth nothing."""
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: (
        "OPTION: 2\nRULE APPLIED: The menu does not offer what the doctrine prescribes\n"
        "TYPE: Register the impediment and move to the next item", "answered")
    decision = lead.decide(_ESCAPE_MENU, idle=200)
    assert decision.action == "choose"
    assert decision.typed == "Register the impediment and move to the next item"


def test_an_instruction_that_switches_off_a_gate_is_refused(tmp_path: Path) -> None:
    """The floor holds through the text field too. It would be a poor door that let in
    what the option check keeps out."""
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: (
        "OPTION: 2\nRULE APPLIED: x\nTYPE: rode com --allow-dirty-tree", "answered")
    decision = lead.decide(_ESCAPE_MENU, idle=200)
    assert decision.action == "escalate"
    assert "switches off a gate" in decision.reason


def test_a_runaway_instruction_is_refused(tmp_path: Path) -> None:
    """Bounded, so a runaway answer cannot paste an essay into a prompt nobody is
    watching."""
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    lead.ask_agent = lambda a, q: (
        "OPTION: 2\nRULE APPLIED: x\nTYPE: " + "a" * 500, "answered")
    assert lead.decide(_ESCAPE_MENU, idle=200).action == "escalate"


def test_prior_rulings_reach_the_prompt(tmp_path: Path) -> None:
    """Every consultation is a fresh process with no memory of the last. Measured: the
    same menu answered twice, five minutes apart, with different options AND different
    rules — the incoherence the envelope exists to prevent, produced by the mechanism
    meant to enforce it."""
    import json
    log = tmp_path / "lead.jsonl"
    log.write_text(json.dumps({
        "event": "choose", "item": "B-059", "option_number": "2",
        "reason": "envelope decides it — Scope grew during measurement"}) + "\n",
        encoding="utf-8")
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True, log_path=log)
    seen = []
    lead.ask_agent = lambda a, q: seen.append(q) or (None, "stub")
    # The heading names the item; without it there is no item to look rulings up by.
    lead.decide("B-059 scope: qual escopo?\n\n❯ 1. um\n  2. dois\n", idle=200)  # english-only: a screen
    assert seen, "the agent was not asked"
    assert "ruled on before" in seen[0]
    assert "Scope grew during measurement" in seen[0]
    assert "the SAME answer" in seen[0]


def test_no_prior_ruling_adds_nothing_to_the_prompt(tmp_path: Path) -> None:
    lead = Lead(session="s", project=tmp_path, log_path=tmp_path / "absent.jsonl")
    assert lead._prior_rulings("B-059") == ""


def test_a_failed_move_puts_the_cursor_back(tmp_path: Path) -> None:
    """A move that is not confirmed must leave nothing behind. Measured: two failed
    attempts walked the cursor down to "Type something." and left it there, so the next
    reader saw a menu pointing at something nobody chose."""
    import subprocess as sp
    lead = Lead(session="s")
    lead.capture = lambda: "❯ 1. still here\n  2. target\n  3. other\n"   # never moves
    keys = []
    original = sp.run
    sp.run = lambda *a, **k: keys.append(a[0][-1]) or original(["true"])
    try:
        ok = lead.choose("❯ 1. still here\n  2. target\n  3. other\n",
                         Decision("choose", "x", "target", "B-001", option_number="3"))
    finally:
        sp.run = original
    assert ok is False
    assert keys.count("Down") == keys.count("Up"), f"cursor left displaced: {keys}"
    assert "Enter" not in keys


def test_a_failure_is_reported_from_stdout_when_stderr_is_empty(tmp_path: Path) -> None:
    """`claude -p` reports its own failures on stdout. Reading only stderr produced a
    log line that ended in a colon and said nothing — the same silence this path exists
    to remove."""
    import subprocess
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    completed = subprocess.CompletedProcess([], 1, "Error: something specific", "")
    original = subprocess.run
    try:
        subprocess.run = lambda *a, **k: completed
        answer, note = lead.ask_agent("squad-lead", "x")
    finally:
        subprocess.run = original
    assert answer is None
    assert "something specific" in note


def test_the_agent_is_called_with_stdin_closed(tmp_path: Path) -> None:
    """Under tmux the daemon's stdin is an open pipe that never delivers, and `claude
    -p` waits on it. By hand over ssh it answered in 27 seconds; from the daemon it
    exited 1 with nothing on either stream."""
    import subprocess
    seen = {}
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True)
    original = subprocess.run

    def capture(*a, **k):
        seen.update(k)
        return subprocess.CompletedProcess([], 0, "OK", "")
    try:
        subprocess.run = capture
        lead.ask_agent("squad-lead", "x")
    finally:
        subprocess.run = original
    assert seen.get("stdin") is subprocess.DEVNULL


def test_the_cursor_check_waits_for_the_redraw(tmp_path: Path) -> None:
    """Sending a key and reading the result are separate events, and a terminal owes no
    ordering between them.

    The first version captured immediately after send-keys and always saw the screen as
    it was BEFORE the redraw. Three consultations reached the right option, by the right
    rule, and none of them ever pressed Enter — the guard refused every move the arrows
    had actually made."""
    lead = Lead(session="s")
    frames = iter(["❯ 1. before the redraw\n  2. target\n",     # english-only: a screen
                   "❯ 1. before the redraw\n  2. target\n",     # english-only: idem
                   "  1. before the redraw\n❯ 2. target\n"])    # english-only: idem
    lead.capture = lambda: next(frames, "  1. x\n❯ 2. target\n")
    assert lead._cursor_reached("2") is True


def test_the_cursor_check_fails_closed(tmp_path: Path) -> None:
    """If the cursor never lands within the window, the answer is no. A guard that
    times out into a yes is not a guard."""
    import squad_lead
    lead = Lead(session="s")
    lead.capture = lambda: "❯ 1. never moves\n  2. target\n"   # english-only: a screen
    original = squad_lead._REDRAW_SECONDS
    try:
        squad_lead._REDRAW_SECONDS = 0.4
        assert lead._cursor_reached("2") is False
    finally:
        squad_lead._REDRAW_SECONDS = original


# ── one hard item does not stop the queue ────────────────────────────────────


def test_the_lead_moves_down_the_queue_when_the_head_is_held(tmp_path: Path) -> None:
    """The envelope says it in its own words: a queue that halts because ONE item is
    hard has turned a local problem into a global one.

    Measured: an item hit its per-item ceiling, `may_start` refused it, and the
    watchdog reported "the backlog offers nothing to start" with 25 items waiting. It
    only ever looked at the head."""
    import time
    lead = _lead_with_select(tmp_path, {"item": "B-059", "why": "oldest unblocked"})
    lead.queue = ["B-059", "B-060", "B-067"]
    lead.interventions["B-059"] = lead.max_per_item          # head is spent
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "start"
    assert decision.item == "B-060"
    assert "B-059 is held" in decision.reason


def test_the_head_still_wins_when_it_can_start(tmp_path: Path) -> None:
    """Walking the queue must not reorder it. The ranking is the selector's."""
    lead = _lead_with_select(tmp_path, {"item": "B-059", "why": "oldest unblocked"})
    lead.queue = ["B-059", "B-060"]
    assert lead.decide("no menu here", idle=1000).item == "B-059"


def test_a_queue_entirely_held_is_reported_with_the_reasons(tmp_path: Path) -> None:
    """Then it really is stalled — and the log says what held each one, so the report
    can be checked instead of believed."""
    import time
    lead = _lead_with_select(tmp_path, {"item": "B-059", "why": "oldest"})
    lead.queue = ["B-059", "B-060"]
    for item in ("B-059", "B-060"):
        lead.interventions[item] = lead.max_per_item
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "stalled"
    assert "every item in the queue is held" in decision.reason
    assert "B-059" in decision.reason and "B-060" in decision.reason


def test_work_in_progress_is_waited_for_not_walked_past(tmp_path: Path) -> None:
    """HELD and NOT STARTABLE are different, and conflating them cost real work.

    Measured with one session: the lead started an item, waited out `retry_after`,
    started the next, then came back — three items, zero events between them, and the
    session analysing something else by the end. Walking past work in progress is not
    parallelism when there is one session; it is a change of subject."""
    import time
    lead = _lead_with_select(tmp_path, {"item": "B-060", "why": "oldest"})
    lead.queue = ["B-060", "B-067"]
    lead.attempts["B-060"] = (time.time(), 0)      # started moments ago, no event yet
    decision = lead.decide("no menu here", idle=1000)
    assert decision.action == "wait"
    assert "under way" in decision.reason


def test_a_held_head_is_still_walked_past(tmp_path: Path) -> None:
    """The earlier fix stands: a ceiling reached is held, and the queue moves on."""
    lead = _lead_with_select(tmp_path, {"item": "B-060", "why": "oldest"})
    lead.queue = ["B-060", "B-067"]
    lead.interventions["B-060"] = lead.max_per_item
    assert lead.decide("no menu here", idle=1000).item == "B-067"


def test_held_reason_names_only_what_cannot_change_by_waiting(tmp_path: Path) -> None:
    import time
    lead = Lead(session="s", project=tmp_path)
    lead.attempts["B-060"] = (time.time(), 0)
    assert lead.held_reason("B-060") is None       # waiting fixes this
    lead.interventions["B-061"] = lead.max_per_item
    assert lead.held_reason("B-061") is not None   # waiting does not


# ── a fleet: several sessions, one claim on the work ─────────────────────────


def test_two_sessions_are_never_handed_the_same_item(tmp_path: Path) -> None:
    """One session works one item at a time — that is what a session IS — so a fleet
    is the only way to work several. And the only harm two members can do each other is
    to take the same work twice: the same commits attempted from two directions, the
    same registry line written twice."""
    from squad_lead import Fleet
    fleet = Fleet()
    first = _lead_with_select(tmp_path, {"item": "B-060", "why": "oldest"})
    first.session, first.fleet, first.queue = "squad1", fleet, ["B-060", "B-067"]
    second = _lead_with_select(tmp_path, {"item": "B-060", "why": "oldest"})
    second.session, second.fleet, second.queue = "squad2", fleet, ["B-060", "B-067"]

    fleet.claim("squad1", "B-060")
    decision = second.decide("no menu here", idle=1000)
    assert decision.action == "start"
    assert decision.item == "B-067", "the second session took the first one's item"


def test_a_released_item_returns_to_the_fleet(tmp_path: Path) -> None:
    from squad_lead import Fleet
    fleet = Fleet()
    fleet.claim("squad1", "B-060")
    assert fleet.holder("B-060") == "squad1"
    fleet.release("squad1")
    assert fleet.holder("B-060") is None


def test_a_lone_lead_has_no_fleet_and_behaves_as_before(tmp_path: Path) -> None:
    """A fleet of one is a lead. Nothing about the single-session path changes."""
    lead = _lead_with_select(tmp_path, {"item": "B-060", "why": "oldest"})
    assert lead.fleet is None
    assert lead.taken_by_another("B-060") is None

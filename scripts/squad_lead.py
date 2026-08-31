#!/usr/bin/env python3
"""Keep an executing session moving, without deciding anything for it.

    python3 scripts/squad_lead.py --session squad --project ~/dev/theo

## The signal this exists for

Measured on 2026-08-31, forty minutes into the first autonomous run. The session
measured its item correctly, concluded it was governance-blocked, and stopped at a
menu it had already answered:

    1. Add blocked_by to B-022 and re-select   (Recommended)
    2. You take the T3 decision now
    3. Stop here and report

It did not stop because it was stuck. It stopped out of deference — it knew the
answer, labelled it *(Recommended)*, and waited anyway. The backlog then sat still
for as long as nobody happened to look.

That is a different failure from the four in `squad-lead`'s own README, which are all
about a session being WRONG: a capability declared absent, a large expense as a
workaround, a verdict that refuses without naming its cause, a cause inferred rather
than measured. This one is about a session being RIGHT and waiting for permission,
and it is both the cheapest to detect and, on the evidence so far, the most frequent.

## The rule: the lead decides flow, never content

A menu option that moves the REGISTRY forward is flow — recording an impediment,
re-running SELECT, continuing to the next item. An option that asks for a judgement
only a person holds is content — a sponsor decision, a T3 boundary call, an approval
to merge.

    "record the impediment and move on?"   -> flow, confirm it
    "do you take the T3 decision now?"     -> content, escalate and say nothing

Confirming flow keeps the backlog moving without ever deciding anything on the human's
behalf. The distinction is not a heuristic about wording; it is about whether the
option's effect is a registry write the contract already prescribes.

## Starting the next item is flow too

Reporting a handed-back turn and stopping there was correct about the ITEM and wrong
about the BACKLOG. Measured on 2026-08-31: `/implement` halted on B-033 needing a
sponsor decision between three paths, wrote a BLOCKED report saying so, and the whole
queue then sat still for 85 minutes — 25 other selectable items, none of them waiting
on anything.

The decision B-033 needs is content and stays with a person. Choosing WHICH ITEM RUNS
NEXT is not: `select_backlog_item.py` computes it from the registry, deterministically,
and the lead only relays the answer. So on a handed-back turn the lead now asks SELECT
and starts what it names.

It cannot restart the item that halted: SELECT holds out anything with a BLOCKED report
on disk, which is a measurement of a file's existence, not a judgement about the halt.
And when SELECT answers BACKLOG_BLOCKED or BACKLOG_EMPTY, the lead reports and waits —
a queue where everything is held is exactly the case only a person can clear.

What the lead types is built from a template with a validated `B-NNN`; it never
composes free text, so the worst it can do is start an item the registry says is ready.

## Why a watchdog and not a second agent

Detecting this needs no judgement — it needs to read a screen and apply two rules.
Spending an agent on it costs tokens and, worse, adds a second place where mistakes
are made. `squad-lead`'s own README records that the supervisor shipped a NameError
and a test that passed for the wrong reason on the same day it supervised; the fewer
decisions this thing makes, the less of that it can do.

## Its own stopping criteria

The README names these as missing, and they are the difference between a lead and a
loop:

  - a per-item ceiling: after N interventions on one B-NNN it stops trying
  - never the same question twice: a repeat means a loop, not progress
  - every intervention is logged, or the lead is a black box nobody can contest

Exit codes: 0 stopped cleanly · 1 the session or tmux is gone
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: A menu option the lead may confirm: its effect is a registry write the contract
#: already prescribes. Matched against the option's own text, which the session wrote.
FLOW_MARKERS = (
    "blocked_by", "re-select", "re-run the select", "re-rodo o select", "reselect",
    "next item", "próximo item", "proximo item",
    "record the impediment", "registrar o impedimento", "adicionar blocked_by",
    "continue", "continuar", "prosseguir", "skip", "pular",
    # Invoking a cycle command is flow, because the human gates live INSIDE the
    # skills — `/release` waits at its own Step 6, `/idea-to-release` stops at
    # PR_OPEN_AWAITING_APPROVAL. The lead does not need to re-implement those gates;
    # it needs to not answer them when they fire. So "run the cycle" is a decision
    # about flow, and the approval it eventually reaches is content the lead escalates.
    "rodar", "run ", "executar", "seguir",
)

#: A menu option only a person can answer, whatever else it says. Checked FIRST, so an
#: option that mentions both loses — a sponsor decision wrapped in a flow-sounding
#: sentence is still a sponsor decision.
#: Flags whose whole purpose is to proceed DESPITE a gate. An option carrying one is
#: never flow, whatever verb it starts with.
#:
#: Measured on 2026-08-31, minutes after the lead gained the power to start items: the
#: session offered "Rodar /idea-to-release B-057 --allow-dirty-tree até halt natural  # english-only: the session's menu, quoted verbatim
#: (Recommended)" and the lead confirmed it. The classifier read "Rodar", matched a
#: flow marker, and never looked at the flag. Running the cycle IS flow; running it
#: with a precondition switched off is a decision to accept the risk that precondition
#: exists to prevent, and that decision is not a watchdog's.
#:
#: Matched as a prefix on a token, so `--allow-dirty-tree` and `--allow-existing-
#: failures` are both caught without listing either.
_RELAXING_FLAGS = ("--allow", "--no-", "--skip", "--force", "--ignore", "--unsafe",
                   "--bypass", "--disable")

CONTENT_MARKERS = (
    # english-only: the session writes its menus in the operator's language, so the
    # markers must match what it actually prints — a marker list in English alone
    # would classify every Portuguese question as `unknown` and escalate all of them.
    "you take", "você toma", "voce toma", "you decide", "você decide", "voce decide",  # english-only: the session prints its menus in the operator's language; the markers must match
    "sponsor", "t3", "approve", "aprovar", "aprovação", "aprovacao",
    "merge", "release", "deploy", "tag", "publish", "publicar",
    "delete", "deletar", "remover", "drop", "revoke", "revogar",
)

#: The line a Claude Code menu draws for the highlighted option.
_SELECTED_RE = re.compile(r"^\s*❯\s*(\d+)\.\s*(.+?)\s*$", re.MULTILINE)
_OPTION_RE = re.compile(r"^\s*❯?\s*(\d+)\.\s*(.+?)\s*$", re.MULTILINE)
_RECOMMENDED_RE = re.compile(r"\(recommended\)", re.IGNORECASE)
_ITEM_RE = re.compile(r"\bB-\d{3,}\b")

#: Slash commands are stripped before classification. `/idea-to-release` contains
#: "release", and without this the lead escalated on the single most common option
#: there is — "run the cycle" — which would have made it useless. Observed on the
#: live run within minutes of starting it. The command is not the act: the cycle it
#: names stops by itself at PR_OPEN_AWAITING_APPROVAL, which is where the human gate
#: already lives.
_SLASH_COMMAND_RE = re.compile(r"/[a-z][a-z0-9-]*")


#: The only shape the lead ever types unprompted. A template with one slot, filled by
#: an id SELECT returned and this regex re-validates — never free text, so the worst
#: outcome is starting an item the registry already called ready.
_START_TEMPLATE = "/idea-to-release {item}"
_VALID_ITEM_RE = re.compile(r"^B-\d{3,}$")

#: An item id anywhere in a slug, with or without the hyphen and in either case.
#: The stream carries BOTH forms — `B-033` from the registry phases and
#: `b033-prometheus-url-dev-public` from the phases that produce artefacts — and
#: matching only the first would have read every plan-slug event as belonging to no
#: item, which is exactly how the board once lost half of its own execution.
_SLUG_ITEM_RE = re.compile(r"\bb-?(\d{3,})\b", re.IGNORECASE)

#: What the lead asks when the selector has computed everything and the queue is
#: still stopped. Deliberately states the constraint the agent inherits, because the
#: agent file states it too and a prompt that contradicts it would be the one place
#: the rule could be lost.
_STUCK_PROMPT = """The maintenance queue is stopped and the mechanical selector has no
actionable answer. Its verdict was: {why}

Read the registry, the event stream, the selector's JSON output and any BLOCKED
reports on disk, then name ONE next move that is flow — a registry write the contract
already prescribes. Do not decide anything a person owns, do not relax any gate, and
do not recommend an option carrying a flag that switches off a precondition. If the
honest answer is that only a person can move this, say exactly which decision and on
which item."""


@dataclass
class Decision:
    action: str          # confirm · escalate · wait · exhausted · stalled · start · asked
    reason: str
    option: str = ""
    item: str = ""


@dataclass
class Lead:
    session: str
    #: The project whose registry SELECT reads. Absent means the lead reports a
    #: handed-back turn and stops there, exactly as it did before.
    project: Path | None = None
    max_per_item: int = 3
    idle_seconds: int = 90
    #: Silence beyond this, with no menu, is a handed-back turn.
    #:
    #: It was 900 on the belief that "a session thinking hard also looks idle briefly".
    #: That was never measured, and it is wrong. The marker is the session's terminal
    #: output, and Claude Code redraws a running counter every second while it works,
    #: so the two states are not close together — they are far apart:
    #:
    #:   working  — measured twice on 2026-08-31, mid-task: idle 0s and 3s
    #:   returned — measured the same day, marker untouched, gap growing monotonically
    #:              (259s, 380s, …) across 127 consecutive samples
    #:
    #: The cost of the wrong number is in the same log: five handed-back turns, three
    #: of them waiting out the full 900s, and two — from before the lead could act at
    #: all — sitting at 7713s and 7905s. Over two hours each.
    #:
    #: 120s is 40x the largest silence ever observed under load, and the same number
    #: `idle_seconds` already uses to answer menus without once interrupting work.
    #: `_still_quiet` re-reads the marker before typing, so the horizon does not have
    #: to carry the whole safety margin by itself.
    stalled_seconds: int = 120
    #: How long an attempt that produced no event at all is given before another is
    #: allowed. Long enough that a session starting a cycle is not interrupted;
    #: short enough that a command that never landed is not final.
    retry_after: int = 300
    #: Whether the lead may spend money on an agent when the mechanical path has no
    #: answer. Off by default: a daemon that calls a model unattended is a different
    #: thing from a daemon that reads a screen, and the difference should be chosen.
    agents_when_stuck: bool = False
    agent_budget_usd: float = 0.50
    agent_timeout: int = 300
    #: One ask per agent per this many seconds. The queue being stuck is a state, not
    #: an event: without this the lead would re-ask on every poll.
    agent_cooldown: int = 1800
    agent_asked: dict[str, float] = field(default_factory=dict)
    #: True once a handed-back turn has been reported, so it is not repeated every
    #: poll. Cleared when the session moves again.
    reported_stall: bool = False
    #: How many times each item has been unblocked, and every question already
    #: answered. Both are stopping criteria, not statistics.
    interventions: dict[str, int] = field(default_factory=dict)
    answered: set[str] = field(default_factory=set)
    #: What this lead tried, and what the stream held at that moment:
    #: item -> (when it typed, how many events the item had then).
    #:
    #: It used to be a set of "already started", checked forever. That made ONE
    #: attempt final: an item whose command never took — the session busy at the
    #: instant of the keystroke, a person cancelling the run, anything — was never
    #: offered again, and the queue died on it.
    #:
    #: Measured on 2026-08-31: the lead typed `/idea-to-release B-169` at 19:30:59,
    #: the operator stopped the run to show the behaviour, the stream recorded nothing
    #: for B-169, and every poll after that answered "already started once by this
    #: lead". Ten minutes, then indefinitely.
    #:
    #: Repeating is legitimate when something sent the work back, or when the attempt
    #: never landed; it is a loop only when nothing changed and no time passed. The
    #: stream answers the first question and the clock answers the second — and
    #: `max_per_item`, which already existed, is the ceiling over both.
    attempts: dict[str, tuple[float, int]] = field(default_factory=dict)

    # ── may this item be started again? ────────────────────────────────────
    def _event_count(self, item: str) -> int:
        """How many phase events the stream holds for this item.

        Zero when the stream cannot be read: an unreadable stream is NOT MEASURED,
        and treating it as "nothing moved" is the safe direction — it only ever
        delays a retry, never fabricates progress.
        """
        if self.project is None:
            return 0
        tooling = Path(__file__).resolve().parent
        if str(tooling) not in sys.path:
            sys.path.insert(0, str(tooling))
        try:
            from cycle_events import read_events
        except ImportError:
            return 0
        try:
            events = read_events(self.project)
        except (OSError, ValueError):
            return 0
        wanted = item.upper()
        seen = 0
        for event in events:
            match = _SLUG_ITEM_RE.search(str(event.get("slug") or ""))
            if match and f"B-{match.group(1)}" == wanted:
                seen += 1
        return seen

    # ── asking an agent, from outside the session ─────────────────────────
    def ask_agent(self, agent: str, question: str) -> tuple[str | None, str]:
        """Run one headless session so an agent can answer what this cannot compute.

        A subagent cannot help here: it lives inside a session, and the whole reason
        this watchdog exists is that the session is the thing that stopped. So the
        judgement runs in a NEW process — `claude -p` — with the project as its
        working directory, where `.claude/agents/{agent}.md` is on disk.

        Three limits, because a daemon that spends money unattended needs them:
        `--max-budget-usd` caps one call, `agent_cooldown` caps the rate, and the
        whole path is off unless `--agents-when-stuck` turned it on. Returns
        (answer, why) — `None` and a reason whenever it did not run.
        """
        if not self.agents_when_stuck:
            return None, "agents are off (pass --agents-when-stuck)"
        if self.project is None:
            return None, "no project to run the agent in"
        now = time.time()
        last = self.agent_asked.get(agent, 0.0)
        if now - last < self.agent_cooldown:
            return None, (f"{agent} was asked {int(now - last)}s ago; "
                          f"waiting out the {self.agent_cooldown}s cooldown")
        self.agent_asked[agent] = now
        prompt = (f"Use the `{agent}` subagent for this, and report its answer "
                  f"verbatim without adding to it.\n\n{question}")
        try:
            out = subprocess.run(
                ["claude", "-p", prompt,
                 "--max-budget-usd", str(self.agent_budget_usd),
                 "--no-session-persistence"],
                capture_output=True, text=True, timeout=self.agent_timeout,
                cwd=str(self.project))
        except subprocess.TimeoutExpired:
            return None, f"{agent} did not answer in {self.agent_timeout}s"
        except (OSError, subprocess.SubprocessError) as error:
            return None, f"{agent} could not be run ({error})"
        if out.returncode != 0:
            return None, f"{agent} exited {out.returncode}: {out.stderr.strip()[:200]}"
        answer = out.stdout.strip()
        return (answer, "answered") if answer else (None, f"{agent} answered nothing")

    def may_start(self, item: str, now: float) -> tuple[bool, str]:
        """Whether to type this item's command, and the reason either way."""
        if self.interventions.get(item, 0) >= self.max_per_item:
            return False, f"{item} already started {self.max_per_item} times"
        previous = self.attempts.get(item)
        if previous is None:
            return True, "not tried yet"
        when, count_then = previous
        if self._event_count(item) > count_then:
            # A phase ran since the attempt. If SELECT is naming the item again, the
            # work came back — which is the chain working, not a loop.
            return True, "the item moved since the last attempt, and is back in the queue"
        if now - when >= self.retry_after:
            return True, (f"the last attempt produced no event in "
                          f"{int((now - when) // 60)} minute(s); it did not land")
        return False, f"{item} was started {int(now - when)}s ago and has not moved yet"

    # ── choosing what runs next ────────────────────────────────────────────
    def next_item(self) -> tuple[str | None, str]:
        """Ask SELECT what may start. Returns (item or None, the answer's own words).

        Shelled out rather than imported: the selector lives in the installed kit
        beside the project, and importing it would bind the lead to one layout. Its
        stdout is the contract either way.
        """
        if self.project is None:
            return None, "no project given; the lead cannot ask SELECT"
        selector = self.project / ".claude/skills/backlog-review/scripts/select_backlog_item.py"
        if not selector.is_file():
            return None, f"SELECT is not installed at {selector}"
        try:
            out = subprocess.run(
                [sys.executable, str(selector), str(self.project / "BACKLOG.md"), "--json"],
                capture_output=True, text=True, timeout=60, cwd=str(self.project))
        except (OSError, subprocess.SubprocessError) as error:
            return None, f"SELECT could not be run ({error})"
        if out.returncode != 0:
            return None, f"SELECT exited {out.returncode}: {out.stderr.strip()[:200]}"
        try:
            answer = json.loads(out.stdout)
        except json.JSONDecodeError as error:
            return None, f"SELECT returned no usable answer ({error})"
        verdict = answer.get("verdict", "")
        if verdict != "ITEM_SELECTED":
            # BACKLOG_BLOCKED and BACKLOG_EMPTY are both cases only a person clears.
            return None, f"{verdict}: {answer.get('reason', '')}"
        item = answer.get("item_id") or ""
        if not _VALID_ITEM_RE.match(item):
            return None, f"SELECT named {item!r}, which is not an item id"
        return item, answer.get("reason", "")

    # ── reading the session ────────────────────────────────────────────────
    def capture(self) -> str | None:
        try:
            out = subprocess.run(
                ["tmux", "capture-pane", "-t", self.session, "-p"],
                capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout if out.returncode == 0 else None

    # ── the judgement, such as it is ───────────────────────────────────────
    def classify(self, option_text: str) -> str:
        """`content` when only a person may answer, else `flow`.

        Content is checked first and wins ties: an option that offers to record an
        impediment AND to take the sponsor's decision is a sponsor decision with a
        friendly preamble.
        """
        low = _SLASH_COMMAND_RE.sub(" ", option_text.lower())
        # Checked BEFORE the content markers and before the flow ones: a relaxing flag
        # is decisive on its own, and reaching either list first would let the verb
        # decide what the flag already settled.
        if any(flag in low for flag in _RELAXING_FLAGS):
            return "content"
        if any(m in low for m in CONTENT_MARKERS):
            return "content"
        if any(m in low for m in FLOW_MARKERS):
            return "flow"
        return "unknown"

    def decide(self, screen: str, idle: float = 0.0) -> Decision:
        selected = _SELECTED_RE.search(screen)
        if not selected:
            # No menu, and the session has gone quiet: it ended its turn and handed
            # control back. Nothing here can answer that — the next move is a person's
            # — but nobody learns of it unless the lead says so.
            #
            # Measured on 2026-08-31: the executing session stopped for TWO HOURS this
            # way, reporting that five reviewer sign-off checkboxes were waiting and
            # that a language gate was blocked, and the lead sat silent because there
            # was no menu to read. The user found it by looking at an empty pane.
            #
            # `stalled` is reported and never acted on. A session that ended its turn
            # is not a session stuck mid-thought, and typing into it would be the lead
            # inventing work rather than unblocking it.
            # A finite measurement only. Without an activity marker `idle` is
            # infinite, which means "not measured" — and reporting a stall from that
            # would be the lead asserting a duration it never observed.
            if idle == float("inf") or idle < self.stalled_seconds:
                return Decision("wait", "no menu is waiting")

            # The turn is back and nothing is on screen to answer. The ITEM may well
            # need a person; the QUEUE does not. Ask SELECT.
            item, why = self.next_item()
            if item:
                allowed, verdict = self.may_start(item, time.time())
                if allowed:
                    return Decision(
                        "start", f"the session handed the turn back after "
                                 f"{int(idle // 60)} minute(s); SELECT names {item} as next "
                                 f"({why}); {verdict}",
                        _START_TEMPLATE.format(item=item), item)
                why = f"{verdict}. SELECT still names it: {why}"

            if self.reported_stall:
                return Decision("wait", "no menu is waiting")
            # Either SELECT has nothing to hand out, or it keeps naming one this lead
            # already started. Both are a person's to clear, and both are reported with
            # SELECT's own words rather than a summary of them.
            # Nothing mechanical answers. This is the one place judgement is worth
            # paying for: the selector computed everything it could and the queue is
            # still stopped.
            answer, note = self.ask_agent("squad-lead", _STUCK_PROMPT.format(why=why))
            if answer:
                return Decision("asked", f"the queue is stopped ({why}); squad-lead says:"
                                         f" {answer[:900]}")
            return Decision("stalled",
                            f"the session ended its turn and has been idle for "
                            f"{int(idle // 60)} minute(s); no menu is waiting and the "
                            f"backlog offers nothing to start — {why} [{note}]")

        option_text = selected.group(2)
        options = _OPTION_RE.findall(screen)

        # The item comes from the OPTION first. Taking the screen's first `B-NNN` read
        # an id out of scrollback — observed live, reporting B-022 for an option about
        # B-033 — which would have charged the per-item ceiling to the wrong item and
        # let a real loop run past it.
        in_option = _ITEM_RE.search(option_text)
        on_screen = _ITEM_RE.search(screen)
        item = in_option.group(0) if in_option else (on_screen.group(0) if on_screen else "")

        # The same question twice is a loop, not progress. Keyed by the option text
        # rather than the item, because a session can loop on one item's one question.
        fingerprint = f"{item}|{option_text}"
        if fingerprint in self.answered:
            return Decision("exhausted", "this exact question was already answered once",
                            option_text, item)

        if item and self.interventions.get(item, 0) >= self.max_per_item:
            return Decision("exhausted",
                            f"{item} already unblocked {self.max_per_item} times",
                            option_text, item)

        kind = self.classify(option_text)
        if kind == "content":
            flag = next((f for f in _RELAXING_FLAGS if f in option_text.lower()), "")
            reason = (f"the option switches off a precondition ({flag}…); accepting that "
                      f"risk is a person's call" if flag else "only a person can answer this")
            return Decision("escalate", reason, option_text, item)
        if kind == "unknown":
            return Decision("escalate", "the option does not read as flow; not guessing",
                            option_text, item)

        # `(Recommended)` is the session stating what it would do. Confirming that is
        # not the lead having an opinion — it is the lead removing a wait.
        if not _RECOMMENDED_RE.search(option_text) and len(options) > 1:
            return Decision("escalate",
                            "flow option, but the session did not recommend it",
                            option_text, item)

        return Decision("confirm", "flow the session already recommended", option_text, item)

    # ── acting ─────────────────────────────────────────────────────────────
    def confirm(self, decision: Decision) -> bool:
        try:
            subprocess.run(["tmux", "send-keys", "-t", self.session, "Enter"],
                           check=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return False
        if decision.item:
            self.interventions[decision.item] = self.interventions.get(decision.item, 0) + 1
        self.answered.add(f"{decision.item}|{decision.option}")
        return True

    def still_quiet(self, marker: Path | None) -> bool:
        """Re-read the marker at the moment of typing.

        The horizon says the session HAD been quiet; this says it still is. Between
        deciding and typing there is a poll interval, and a session that woke up in
        it would get a command pasted into whatever it was composing.

        Cheap enough to do every time, and it is what lets the horizon be 120s rather
        than a number chosen to cover the gap by itself. No marker means nothing was
        measured, and the lead does not type on an unmeasured session.
        """
        if marker is None:
            return False
        return _idle_seconds(marker) >= self.stalled_seconds

    def start(self, decision: Decision) -> bool:
        """Type the start command and send it.

        Re-validates the id at the point of typing rather than trusting the Decision.
        The check upstream is where the id is chosen; this one is where it becomes
        keystrokes in a session with no permission prompts, and the two places that
        matter are the one that decides and the one that acts.
        """
        if not _VALID_ITEM_RE.match(decision.item):
            return False
        command = _START_TEMPLATE.format(item=decision.item)
        try:
            # Text and Enter as separate calls: a single send-keys with the command in
            # it would submit whatever the composer already held, appended to ours.
            subprocess.run(["tmux", "send-keys", "-t", self.session, command],
                           check=True, timeout=15)
            subprocess.run(["tmux", "send-keys", "-t", self.session, "Enter"],
                           check=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return False
        # Recorded WITH the stream depth at this moment, so the next decision can ask
        # whether anything happened rather than whether anything was typed.
        self.attempts[decision.item] = (time.time(), self._event_count(decision.item))
        self.interventions[decision.item] = self.interventions.get(decision.item, 0) + 1
        return True


def _log(path: Path | None, payload: dict) -> None:
    """Append one line. A lead nobody can audit is a lead nobody should trust.

    The timestamp is stamped here rather than by the caller, so no decision can reach
    the log without one. It was missing at first, and a log of decisions with no time
    on them cannot answer the question anyone actually asks — *when did it stop?*
    """
    payload = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
    line = json.dumps(payload, ensure_ascii=False)
    print(line, flush=True)
    if path:
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass


def _idle_seconds(marker: Path | None) -> float:
    if marker is None or not marker.exists():
        return float("inf")
    return time.time() - marker.stat().st_mtime


def watch(lead: Lead, marker: Path | None, log: Path | None,
          poll: int, rounds: int | None = None) -> int:
    served = 0
    while rounds is None or served < rounds:
        served += 1
        screen = lead.capture()
        if screen is None:
            _log(log, {"event": "gone", "session": lead.session})
            return 1

        idle = _idle_seconds(marker)
        if idle < lead.idle_seconds:
            # The session moved. Whatever stall was reported is over, and the next one
            # is a new fact worth reporting.
            lead.reported_stall = False
            # Working. A lead that interrupts a session mid-thought is worse than no
            # lead: it answers a menu the session was about to move past on its own.
            time.sleep(poll)
            continue

        decision = lead.decide(screen, idle)
        if decision.action == "wait":
            time.sleep(poll)
            continue

        entry = {"event": decision.action, "item": decision.item,
                 "reason": decision.reason, "option": decision.option[:160],
                 "idle_seconds": None if idle == float("inf") else round(idle)}
        if decision.action == "confirm":
            entry["sent"] = lead.confirm(decision)
        elif decision.action == "start":
            # Checked here, not in `decide`: this is the last moment before keystrokes,
            # and it is the only one where "is it still quiet?" has the right answer.
            if lead.still_quiet(marker):
                entry["sent"] = lead.start(decision)
            else:
                entry["sent"] = False
                entry["reason"] = ("the session moved between the decision and the "
                                   "keystrokes; not typing into a working session")
        _log(log, entry)

        if decision.action == "asked":
            # An answer is not an action. It goes in the log for a person to read, and
            # the lead keeps watching — acting on it would be the lead deciding what
            # it just paid an agent to think about.
            lead.reported_stall = True
            time.sleep(poll)
            continue

        if decision.action == "start":
            # The session has work again. The next stall is a new fact.
            lead.reported_stall = False
            time.sleep(poll)
            continue

        if decision.action == "stalled":
            # Reported once, and the watch CONTINUES. Repeating it every poll would
            # bury the line in a log nobody reads; exiting would leave the session
            # unwatched from the first stall onward, which is worse — the next thing
            # that happens is a menu the lead could have answered.
            #
            # Found by shipping the exit: the lead reported a 128-minute stall
            # correctly and then died, so a restart was needed before it could see
            # anything again.
            lead.reported_stall = True
            time.sleep(poll)
            continue

        if decision.action in ("escalate", "exhausted"):
            # Escalation is terminal by design. Looping here would turn "a person must
            # answer" into a message repeated every poll into a log nobody reads.
            return 0
        time.sleep(poll)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", default="squad", help="tmux session to watch")
    parser.add_argument("--marker", type=Path,
                        help="file whose mtime marks activity (the session's log)")
    parser.add_argument("--log", type=Path, help="append decisions here as JSONL")
    parser.add_argument("--idle", type=int, default=90,
                        help="seconds of silence before the lead may act")
    parser.add_argument("--poll", type=int, default=20)
    parser.add_argument("--max-per-item", type=int, default=3)
    parser.add_argument("--agents-when-stuck", action="store_true",
                        help="when the selector has no actionable answer, spend one "
                             "headless `claude -p` call asking the squad-lead agent "
                             "what to do. Off by default")
    parser.add_argument("--agent-budget-usd", type=float, default=0.50,
                        help="cap for one agent call (default 0.50)")
    parser.add_argument("--agent-cooldown", type=int, default=1800,
                        help="minimum seconds between asks of the same agent")
    parser.add_argument("--project", type=Path,
                        help="project whose BACKLOG.md SELECT reads. Without it the "
                             "lead reports a handed-back turn and starts nothing")
    parser.add_argument("--stalled", type=int, default=120,
                        help="seconds of silence with no menu before treating the turn "
                             "as handed back (default 120; measured, see the field)")
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    args = parser.parse_args(argv)

    project = args.project.expanduser().resolve() if args.project else None
    if project is not None and not (project / "BACKLOG.md").is_file():
        print(f"FATAL: no BACKLOG.md under {project}", file=sys.stderr)
        return 1
    lead = Lead(session=args.session, project=project, max_per_item=args.max_per_item,
                idle_seconds=args.idle, stalled_seconds=args.stalled,
                agents_when_stuck=args.agents_when_stuck,
                agent_budget_usd=args.agent_budget_usd,
                agent_cooldown=args.agent_cooldown)
    return watch(lead, args.marker, args.log, args.poll, rounds=1 if args.once else None)


if __name__ == "__main__":
    raise SystemExit(main())

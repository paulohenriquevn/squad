#!/usr/bin/env python3
"""Keep an executing session moving, without deciding anything for it.

    python3 mechanisms/fleet/squad_lead.py --session squad --project ~/dev/theo

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

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from pathlib import Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import records_dir  # noqa: E402

def _halted_items(project: Path) -> set[str]:
    """Items a phase stopped on, from the ONE reader of those files.

    This globbed `*{item[2:]}*-BLOCKED.md` itself, and that glob is the one
    `squad_boss.halt_reports` documents as wrong: "anchoring BLOCKED to the end of the
    name dropped those files silently, and a dropped halt is re-offered forever —
    measured 2026-09-04, B-079 had two halt reports on disk and this function returned
    neither." A lane writing a second report for one item adds a descriptive suffix, and
    the end-anchor misses it.

    So this told a lane "not blocked" for an item whose halt report was the second one,
    while the board and the selector said blocked — the same registry answering two ways
    depending on which mechanism asked.

    `halt_reports` also called itself "the single reader of these files", which was true
    of the two it named and false of this one. A claim of singleness is a claim nothing
    checks; calling through is what makes it true.

    Empty on ImportError rather than falling back to a glob: a second implementation
    appearing whenever an import fails is how the two diverged in the first place, and a
    missing "blocked" note costs a redundant sentence in a prompt.
    """
    here = _Path_bootstrap(__file__).resolve()
    for up in here.parents:
        scripts = up / "skills" / "backlog-review" / "scripts"
        if (scripts / "squad_boss.py").is_file():
            if str(scripts) not in _sys_bootstrap.path:
                _sys_bootstrap.path.insert(0, str(scripts))
            break
    try:
        from squad_boss import halt_reports  # noqa: PLC0415
    except ImportError:
        return set()
    return set(halt_reports(project))


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


#: How long to wait for a terminal to redraw after a keystroke. Sending a key and
#: reading the result are separate events, and nothing orders them; the first version
#: read immediately and always saw the screen from before the move.
_REDRAW_SECONDS = 3.0

#: Menu entries that are not decisions. They open a text field, a conversation or a
#: way out — choosing one answers nothing and changes the screen into a shape the lead
#: cannot read. Measured: an agent picked "Type something." and cited a rule for it.
#:
#: Matched on the option TEXT, lower-cased, as a substring. Short and explicit rather
#: than clever: a menu entry that genuinely decides something never reads like these.
_ESCAPE_OPTIONS = ("type something", "chat about", "cancel", "go back", "none of these",
                   "escrever", "conversar", "voltar", "cancelar")

#: The only shape the lead ever types unprompted. Two slots, both filled from things
#: the lead READ — an id SELECT returned and re-validates, and facts from the registry
#: and the stream. Never free prose: the worst it can compose is a true sentence about
#: an item the registry already called ready.
#:
#: It used to be the bare command, and on 2026-08-31 that produced the failure this
#: template exists for. The session had just spent ten minutes measuring B-059, found
#: that the item's recorded scope was wrong, and ended with "aguardando decisão". The
#: lead typed `/idea-to-release B-059` over it. The session refused — correctly — and
#: reopened the same question, so a whole turn bought nothing.
#:
#: A handoff that carries no state is not a handoff, it is an order. The last sentence
#: matters most: it says out loud that refusing is allowed, which is exactly what the
#: bare command denied.
#:
#: The pointer to the envelope is not decoration. A session carries the rules it read
#: when it started, and a clause added afterwards reaches nobody already running.
#: Measured: the envelope was widened to cover the exact case three sessions were
#: refusing, it was on disk within minutes, and none of the three mentioned it — they
#: had read the narrower version and no reason to look again.
#:
#: The handoff is the one moment the lead speaks to a session, so it is where the
#: current policy has to be pointed at.
#:
#: One line, because a newline in `tmux send-keys` submits.
#: What the lead types INTO THE SESSION, in the language that session is speaking.
#:
#: Reading and writing are not symmetric here, and conflating them was the defect.
#: `FLOW_MARKERS` above matches BOTH languages because matching is reading, and the
#: lead does not get to choose what the session prints. Writing is the opposite: a
#: fixed language makes the lead the one participant in the conversation that ignores
#: the conversation. So the language is OBSERVED from the screen and mirrored.
#:
#: English is the default rather than a guess: this repository is English by policy,
#: and a session that has printed nothing recognisable has given no reason to switch.
_START_TEMPLATES = {
    "en": (
        "[hermes] The turn came back and the queue has work: run "
        "/idea-to-release {item}. Why this item: {why}. {history} "
        "Before deciding that something needs a person, re-read "
        "rules/autonomy-envelope.md on disk: it says what the system decides on its "
        "own, and it changes without telling whoever is already running. If this "
        "contradicts what you just reported, or if the item needs a decision the "
        "envelope does not cover, say so instead of executing — do not choose for me."
    ),
    "pt": (
        "[hermes] O turno voltou e a fila tem trabalho: rode /idea-to-release {item}. "  # english-only: mirrors the session's language
        "Por que este item: {why}. {history} "  # english-only: mirrors the session's language
        "Antes de decidir que algo precisa de uma pessoa, releia rules/autonomy-envelope.md "  # english-only: mirrors the session's language
        "em disco: ele diz o que o sistema decide sozinho, e muda sem avisar quem já roda. "  # english-only: mirrors the session's language
        "Se isto contradiz o que você acabou de reportar, ou se o item precisa de uma "  # english-only: mirrors the session's language
        "decisão que nem o envelope cobre, diga isso em vez de executar — não escolha por mim."  # english-only: mirrors the session's language
    ),
}

#: The same clause set, per language. Kept beside the template so adding a language is
#: one dictionary entry in each, rather than a branch somewhere in `handoff`.
_HISTORY = {
    "en": {
        "none": "The stream records no event for {item} yet.",
        "some": "The stream already records {count} event(s) for {item}{ended}.",
        "ended": ", last verdict `{verdict}`",
        "blocked": " There is a BLOCKED report on disk for it — read it first.",
    },
    "pt": {
        "none": "O stream não registra nenhum evento para {item} ainda.",  # english-only: mirrors the session's language
        "some": "O stream já registra {count} evento(s) para {item}{ended}.",  # english-only: mirrors the session's language
        "ended": ", último veredito `{verdict}`",  # english-only: mirrors the session's language
        "blocked": " Há um laudo BLOCKED em disco para ele — leia antes.",  # english-only: mirrors the session's language
    },
}

DEFAULT_LANGUAGE = "en"

#: How many distinct Portuguese markers a screen must carry before the lead switches.
#:
#: Two, not one. A single word decides nothing — `implementação` inside an item title,
#: or a path — and the cost of switching wrongly is every subsequent message written
#: to a session that is not speaking that language. Two independent markers is the
#: cheapest evidence that the SESSION is speaking it, not that one string contains it.
_LANGUAGE_EVIDENCE = 2


def detect_language(text: str) -> str:
    """The language the session is speaking, read from what it printed.

    Reuses `check_english_only.find_markers` rather than carrying a second list of
    what Portuguese looks like. The two uses point opposite ways — that script REFUSES
    what this one MIRRORS — but the question underneath is the same one, and a second
    copy of the answer is how the two drift.
    """
    if not text:
        return DEFAULT_LANGUAGE
    try:
        from check_english_only import find_markers
    except ImportError:
        return DEFAULT_LANGUAGE
    seen: set[str] = set()
    for line in text.splitlines():
        seen.update(find_markers(line))
        if len(seen) >= _LANGUAGE_EVIDENCE:
            return "pt"
    return DEFAULT_LANGUAGE

#: The bare command, for when the lead has nothing to add. Kept so a caller that wants
#: determinism over context can have it.
_BARE_TEMPLATE = "/idea-to-release {item}"
_VALID_ITEM_RE = re.compile(r"^B-\d{3,}$")

#: How far above the first option a menu's own heading reaches. Five lines covers the
#: question and its preamble; beyond that is the conversation the menu interrupted,
#: and reading an id from there is how the lead reported an item it was not asked
#: about — twice.
_HEADING_LINES = 5

#: An item id anywhere in a slug, with or without the hyphen and in either case.
#: The stream carries BOTH forms — `B-033` from the registry phases and
#: `b033-prometheus-url-dev-public` from the phases that produce artefacts — and
#: matching only the first would have read every plan-slug event as belonging to no
#: item, which is exactly how the board once lost half of its own execution.
_SLUG_ITEM_RE = re.compile(r"\bb-?(\d{3,})\b", re.IGNORECASE)

#: What the lead asks when a menu is a decision the doctrine may already cover.
#:
#: The watchdog itself still refuses: it classifies, and a scope call is not flow. What
#: changed is where the refusal goes. It used to end at a person who had said they
#: enter at the initial backlog and nowhere else, which turned every such menu into a
#: permanent stop. Now it goes to the agent that holds `rules/autonomy-envelope.md`,
#: and comes back either as a rule applied or as a gap in that file.
#:
#: The answer must name BOTH an option number and the rule that produced it. A number
#: without a rule is the agent improvising, which is the thing the envelope exists to
#: replace — so the lead refuses it and escalates instead.
_MENU_PROMPT = """A session stopped at a menu and the watchdog will not answer it: the
option is not flow.

The menu:
{menu}

Does the doctrine in `rules/autonomy-envelope.md` decide this? Read the file, and read
the registry and the stream for whatever item the menu is about.

{history}If a rule covers it, answer with exactly two lines:
OPTION: <the number to choose>
RULE APPLIED: <the section of the envelope, by name>

If the action the doctrine prescribes is NOT among the options — the menu offers three
ways to do something the rule says to do differently — choose the option that opens a
text field and add a third line saying what to type:
OPTION: <the number of the field-opening option>
RULE APPLIED: <the section, by name>
TYPE: <one line, what to instruct the session to do>

That third form is also how nothing stays stuck. If no option and no instruction can
carry out the doctrine, the envelope's last clause applies: say to record the
impediment and move to the next item, and TYPE exactly that. An item waiting is not
the queue waiting.

Answer NO RULE only when the case itself is missing from the envelope AND you cannot
say what should happen:
NO RULE: <what the case is, stated so it can be added to the envelope>

Never choose an option that switches off a gate, that merges, or that widens an item
already executing — those are the envelope's floor and no rule overrides them."""

#: The agent's answer, parsed strictly. Anything that does not match is not an answer.
_OPTION_RE_ANSWER = re.compile(r"^OPTION:\s*(\d+)\s*$", re.MULTILINE)
_RULE_RE_ANSWER = re.compile(r"^RULE APPLIED:\s*(\S.*?)\s*$", re.MULTILINE)
#: The text to type, when the option chosen is one that opens a field.
_TYPE_RE_ANSWER = re.compile(r"^TYPE:\s*(\S.*?)\s*$", re.MULTILINE)

#: Longest instruction the lead will type into a session. Long enough for a sentence
#: naming an action and its reason; short enough that a runaway answer cannot paste an
#: essay into a prompt nobody is watching.
_MAX_TYPED = 400

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


#: The squad agent this watchdog escalates to. It is the facilitator role —
#: flow and impediments — and the name must match a file `install.sh` copies,
#: because `claude -p` resolves it from `.claude/agents/{name}.md` on disk.
SQUAD_FACILITATOR = "hermes-scrum-master"


@dataclass
class Decision:
    action: str          # confirm · escalate · wait · exhausted · stalled · start
                         # · asked · choose · still_stalled
    reason: str
    option: str = ""
    item: str = ""
    #: For `choose`: which numbered option the doctrine selected.
    option_number: str = ""
    #: For `choose` on an option that opens a field: what to type into it.
    typed: str = ""


@dataclass
class Lead:
    session: str
    #: The project whose registry SELECT reads. Absent means the lead reports a
    #: handed-back turn and stops there, exactly as it did before.
    project: Path | None = None
    #: The language the session is speaking, re-read from every screen. Held on the
    #: lead rather than passed down so a caller that composes a message outside
    #: `decide()` still writes in the language the session last used.
    language: str = DEFAULT_LANGUAGE
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
    #: Measured three times, each one correcting the last guess. A one-word question
    #: in a real project exceeded 0.50 and answered at 2.00; the actual menu
    #: consultation — read the envelope, the registry and the stream, then answer —
    #: cost USD 3.67 over two minutes, and blew a 3.00 cap. The cap counts the whole
    #: call, and the project's own context dominates it long before the question does.
    #:
    #: 6.00 is that measurement with room for a larger project. It is a CEILING, not a
    #: price: the call stops there rather than spending it.
    #:
    #: The rate matters more than the cap. At `agent_cooldown` = 1800s this is at most
    #: two consultations an hour, and the cooldown is the knob to turn if that is too
    #: much — not the cap, which only decides whether an answer arrives at all.
    #: A ceiling, not a price: the call stops there rather than spending it. Raised
    #: from 6.00 on 2026-09-02 after a consumer's lead exited 1 on it and took the
    #: whole fleet down with it — the queue was not stuck on the work, it was stuck
    #: on a number. The measured cost of one consultation in a large project is
    #: ~$1.30, so this is roughly thirty of them; `agent_cooldown` is what limits
    #: the RATE, and the rate is what actually controls spend.
    agent_budget_usd: float = 40.00
    agent_timeout: int = 300
    #: One ask per agent per this many seconds. The queue being stuck is a state, not
    #: an event: without this the lead would re-ask on every poll.
    agent_cooldown: int = 1800
    agent_asked: dict[str, float] = field(default_factory=dict)
    #: Where decisions are written. Read back to the agent so consecutive consultations
    #: about one item cannot contradict each other.
    log_path: Path | None = None
    #: The ranked order SELECT last returned, so a head that cannot start does not end
    #: the search.
    queue: list[str] = field(default_factory=list)
    #: Shared with the other leads of a fleet. None when this lead watches alone.
    fleet: "Fleet | None" = None
    #: True once a handed-back turn has been reported, so it is not repeated every
    #: poll. Cleared when the session moves again.
    reported_stall: bool = False
    #: When that report went out, so the stall can be RE-reported on a heartbeat
    #: rather than never. Silencing every later poll was measured on 2026-09-03:
    #: the lead was alive and sleeping while its log had been still for 9h11m, and
    #: from outside a silent lead is indistinguishable from a dead one.
    stall_reported_at: float = 0.0
    #: How long a stall may go unmentioned. Long enough that the log stays
    #: readable, short enough that a person checking it learns the watch is alive.
    heartbeat_seconds: int = 1800
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
    #: Questions already raised for a person. Raised once, then the watch goes on
    #: watching — the alternative was exiting, which kept the log quiet by having no
    #: lead left to write to it.
    surfaced: set[str] = field(default_factory=set)

    # ── may this item be started again? ────────────────────────────────────
    def _event_count(self, item: str) -> int:
        """How many phase events the stream holds for this item.

        Zero when the stream cannot be read: an unreadable stream is NOT MEASURED,
        and treating it as "nothing moved" is the safe direction — it only ever
        delays a retry, never fabricates progress.
        """
        if self.project is None:
            return 0
        tooling = Path(__file__).resolve().parent.parent / "cycle"
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
    def _decide_by_doctrine(self, screen: str, options: list,
                           item: str) -> tuple[Decision | None, str]:
        """Ask the agent whether the envelope decides this menu, and how.

        Returns a `choose` decision when it does, and None when it does not — so the
        caller escalates exactly as before. The refusal moved; it did not disappear.
        """
        menu = "\n".join(f"{n}. {text}" for n, text in options)
        answer, note = self.ask_agent(
            SQUAD_FACILITATOR, _MENU_PROMPT.format(menu=menu, history=self._prior_rulings(item)))
        if not answer:
            # Never conflated with "no rule covers it". One is the doctrine speaking and
            # the other is nobody speaking, and a log that renders them identically
            # reports a gap in the envelope that does not exist.
            return None, note
        picked = _OPTION_RE_ANSWER.search(answer)
        rule = _RULE_RE_ANSWER.search(answer)
        if not picked or not rule:
            if answer.lstrip().upper().startswith("NO RULE"):
                return None, f"the agent found no rule: {answer.splitlines()[0][:120]}"
            # A number with no rule is the agent improvising, which is what the
            # envelope replaced. No rule named, no answer taken.
            return None, "the agent answered without naming a rule; not acted on"
        number = picked.group(1)
        if number not in {n for n, _ in options}:
            return None, f"the agent chose option {number}, which this menu does not have"
        text = next(t for n, t in options if n == number)
        lowered = text.lower()
        if any(f in lowered for f in _RELAXING_FLAGS):
            # The floor again, reached from the other side: the agent may not pick what
            # the classifier would have refused.
            return None, "the agent chose an option that switches off a gate; refused"
        if any(e in lowered for e in _ESCAPE_OPTIONS):
            # An escape opens a field rather than deciding. That is useless on its own
            # and necessary when the menu contains no option for the action the
            # doctrine prescribes — which is a real case: an agent correctly reported
            # "the actual cause is not among the choices offered" and had no way to act
            # on its own diagnosis, because this branch refused the only door out.
            #
            # So it is allowed WITH the text to type, and only then. The instruction is
            # validated the same way the option is: no relaxing flag, one line, bounded.
            typed = _TYPE_RE_ANSWER.search(answer)
            if not typed:
                return None, (f"the agent chose {number!r} ({text[:40]}), which opens a "
                              f"field, without saying what to type into it")
            instruction = typed.group(1).strip()
            if len(instruction) > _MAX_TYPED:
                return None, f"the instruction is {len(instruction)} characters; cap is {_MAX_TYPED}"
            if any(f in instruction.lower() for f in _RELAXING_FLAGS):
                return None, "the instruction switches off a gate; refused"
            return (Decision("choose", f"envelope decides it — {rule.group(1)}", text,
                             item, option_number=number, typed=instruction), "answered")
        return (Decision("choose", f"envelope decides it — {rule.group(1)}", text, item,
                         option_number=number), "answered")

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
        # The fleet's clock when there is a fleet: one cooldown per agent, not one
        # per agent per session. Falls back to this lead's own dict for a single
        # session, where the two are the same thing.
        clock = self.fleet.asked_at if self.fleet is not None else self.agent_asked
        now = time.time()
        last = clock.get(agent, 0.0)
        if now - last < self.agent_cooldown:
            return None, (f"{agent} was asked {int(now - last)}s ago; "
                          f"waiting out the {self.agent_cooldown}s cooldown")
        clock[agent] = now
        prompt = (f"Use the `{agent}` subagent for this, and report its answer "
                  f"verbatim without adding to it.\n\n{question}")
        try:
            out = subprocess.run(  # noqa: PLW1510 — returncode is read below
                ["claude", "-p", prompt,
                 "--max-budget-usd", str(self.agent_budget_usd),
                 "--no-session-persistence"],
                capture_output=True, text=True, timeout=self.agent_timeout,
                cwd=str(self.project),
                # Closed, not inherited. `claude -p` reads stdin for piped input and
                # waits when it is an open pipe that never delivers — which is exactly
                # what this lead's stdin is, running under tmux through `tee`. Called
                # by hand over ssh it answered in 27s; called from the daemon it exited
                # 1 with nothing on either stream. The tool's own warning names the
                # fix: redirect stdin explicitly.
                stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return None, f"{agent} did not answer in {self.agent_timeout}s"
        except (OSError, subprocess.SubprocessError) as error:
            return None, f"{agent} could not be run ({error})"
        if out.returncode != 0:
            # stdout first: `claude -p` reports its own failures there, and reading only
            # stderr produced a log line that ended in a colon and said nothing — the
            # same silence this whole path exists to remove.
            detail = (out.stdout or "").strip() or (out.stderr or "").strip()
            return None, f"{agent} exited {out.returncode}: {detail[:200] or 'no output'}"
        answer = out.stdout.strip()
        if not answer:
            return None, f"{agent} answered nothing"
        # `claude -p` reports a blown budget on STDOUT and exits 0, so the returncode
        # check above passes and the error text arrives shaped like an answer. Measured:
        # a one-word question exceeded a 0.50 cap, the lead read `Error: Exceeded USD
        # budget` as the agent's reply, found no rule in it, and escalated saying no
        # rule covered the case. It had never been asked.
        first = answer.splitlines()[0].strip()
        if first.lower().startswith("error:"):
            return None, f"{agent} could not answer: {first[:120]}"
        return answer, "answered"

    def _last_verdict(self, item: str) -> str | None:
        """The verdict of the last phase this item ended, or None."""
        if self.project is None:
            return None
        tooling = Path(__file__).resolve().parent.parent / "cycle"
        if str(tooling) not in sys.path:
            sys.path.insert(0, str(tooling))
        try:
            from cycle_events import read_events
        except ImportError:
            return None
        try:
            events = read_events(self.project)
        except (OSError, ValueError):
            return None
        for event in reversed(events):
            if event.get("type") != "cycle:phase:end":
                continue
            match = _SLUG_ITEM_RE.search(str(event.get("slug") or ""))
            if match and f"B-{match.group(1)}" == item.upper():
                verdict = event.get("verdict")
                return str(verdict) if verdict else None
        return None

    def handoff(self, item: str, why: str) -> str:
        """The message the lead types when it starts an item.

        Every clause is read, never inferred: the selector's own reason, the stream's
        count and last verdict, and whether a phase left a BLOCKED report. The lead
        states what it knows and stops — telling the session what to conclude would be
        it deciding content through a sentence instead of through a menu.
        """
        phrases = _HISTORY.get(self.language, _HISTORY[DEFAULT_LANGUAGE])
        count = self._event_count(item)
        verdict = self._last_verdict(item)
        if count == 0:
            history = phrases["none"].format(item=item)
        else:
            ended = phrases["ended"].format(verdict=verdict) if verdict else ""
            history = phrases["some"].format(count=count, item=item, ended=ended)
        if self.project is not None and item in _halted_items(self.project):
            history += phrases["blocked"]
        template = _START_TEMPLATES.get(self.language, _START_TEMPLATES[DEFAULT_LANGUAGE])
        return template.format(item=item, why=why.rstrip(". "), history=history)

    def _blocking_verdicts(self) -> frozenset[str]:
        """The shared list, read from `rules/blocking-verdicts.txt`.

        Empty when unreadable — which only ever costs a retry, never fabricates a
        reason to stop.
        """
        if self.project is None:
            return frozenset()
        for relative in ("rules", ".claude/rules"):
            path = self.project / relative / "blocking-verdicts.txt"
            if path.is_file():
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                names = {line.split("#", 1)[0].strip().upper() for line in lines}
                names.discard("")
                return frozenset(names)
        return frozenset()

    def taken_by_another(self, item: str) -> str | None:
        """The other session working this item, if any.

        Two sessions on one item is the only way members of a fleet can damage each
        other: the same commits attempted twice, the same registry line written from
        two directions. It is also the easiest thing to prevent, which is why it is the
        only thing the coordinator knows.
        """
        if self.fleet is None:
            return None
        holder = self.fleet.holder(item)
        return holder if holder and holder != self.session else None

    def held_reason(self, item: str) -> str | None:
        """Why nothing can be done with this item until something changes, or None.

        HELD is not the same as NOT STARTABLE, and conflating them cost real work.
        A ceiling reached and a verdict that blocks are held: no amount of waiting
        changes them, so the queue should move past. An attempt made four minutes ago
        that has not produced an event yet is the opposite — it is work in progress,
        and moving past it throws away the context the session just built.

        Measured: with one session, the lead started B-060, waited out `retry_after`,
        started another item, then came back — three items, zero events between them,
        and the session analysing something else entirely by the end.
        """
        other = self.taken_by_another(item)
        if other:
            # Held for THIS lead, and the clearest case of it: waiting will not free an
            # item another session is working, and there is nothing here to wait for.
            return f"{item} is already with session {other}"
        if self.interventions.get(item, 0) >= self.max_per_item:
            return f"{item} already started {self.max_per_item} times"
        verdict = self._last_verdict(item)
        if verdict and verdict.upper() in self._blocking_verdicts():
            return (f"{item} last ended `{verdict}`, which holds it; only a "
                    f"person moves this")
        return None

    def may_start(self, item: str, now: float) -> tuple[bool, str]:
        """Whether to type this item's command, and the reason either way."""
        held = self.held_reason(item)
        if held:
            return False, held

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
            out = subprocess.run(  # noqa: PLW1510 — returncode is read below
                [sys.executable, str(selector), str(self.project / "BACKLOG.md"), "--json"],
                capture_output=True, text=True, timeout=60, cwd=str(self.project))
        except (OSError, subprocess.SubprocessError) as error:
            return None, f"SELECT could not be run ({error})"
        # The exit code is read AFTER stdout, not before. SELECT ends on
        # `return 0 if verdict == "ITEM_SELECTED" else 1`, so a held backlog always
        # exits 1 with an empty stderr while the reason sits on stdout. Checking the
        # code first made the branch below unreachable and the lead logged
        # `SELECT exited 1: ` — an inability to act published as a blank. Measured on
        # the runner 2026-09-03: three lanes idle 10h33m behind that empty string.
        try:
            answer = json.loads(out.stdout)
        except json.JSONDecodeError as error:
            if out.returncode != 0:
                detail = out.stderr.strip() or out.stdout.strip()
                return None, f"SELECT exited {out.returncode}: {detail[:200] or 'no output'}"
            return None, f"SELECT returned no usable answer ({error})"
        verdict = answer.get("verdict", "")
        if verdict != "ITEM_SELECTED":
            # BACKLOG_BLOCKED and BACKLOG_EMPTY are both cases only a person clears.
            return None, f"{verdict}: {answer.get('reason', '')}"
        item = answer.get("item_id") or ""
        if not _VALID_ITEM_RE.match(item):
            return None, f"SELECT named {item!r}, which is not an item id"
        # The rest of the order comes back too. The lead used to take only the head and
        # stop when it could not be started, which is the failure the envelope names in
        # its own words: a queue that halts because ONE item is hard has turned a local
        # problem into a global one. Measured: an item hit its per-item ceiling and the
        # watchdog reported "the backlog offers nothing to start" with 25 items waiting.
        self.queue = [i for i in (answer.get("queue") or []) if _VALID_ITEM_RE.match(i)]
        return item, answer.get("reason", "")

    # ── reading the session ────────────────────────────────────────────────
    def capture(self) -> str | None:
        try:
            out = subprocess.run(  # noqa: PLW1510 — returncode is read below
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
        # Observed before anything is composed: every message this call may produce
        # should be in the language of the screen that prompted it.
        self.language = detect_language(screen)
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
                now = time.time()
                # Down the order, not just its head. `queue` is already ranked — what
                # unblocks a halt first, then triaged before raw, then oldest — so the
                # first candidate that may start is the right one to start.
                held = []
                for candidate in [item] + [q for q in self.queue if q != item]:
                    allowed, verdict = self.may_start(candidate, now)
                    if allowed:
                        reason = (why if candidate == item
                                  else f"{item} is held ({held[0] if held else 'unavailable'}), "
                                       f"so the next in the ranked queue")
                        return Decision(
                            "start", f"the session handed the turn back after "
                                     f"{int(idle // 60)} minute(s); SELECT names "
                                     f"{candidate} ({reason}); {verdict}",
                            self.handoff(candidate, reason), candidate)
                    if self.held_reason(candidate) is None:
                        # Not held — started recently and still working. Walking past
                        # it would abandon work in progress for the next item, and with
                        # one session that is not parallelism, it is a change of
                        # subject. Wait for THIS one.
                        return Decision("wait", f"{candidate} is under way: {verdict}",
                                        "", candidate)
                    held.append(f"{candidate}: {verdict}")
                why = ("every item in the queue is held — " + "; ".join(held[:3]))

            if self.reported_stall:
                # Quiet, but not mute. Past the heartbeat the same stall is stated
                # again — with its real reason, which is never "no menu is waiting":
                # the menu is absent because the backlog is walled.
                if time.time() - self.stall_reported_at < self.heartbeat_seconds:
                    return Decision("wait", "no menu is waiting")
                return Decision(
                    "still_stalled",
                    f"unchanged after {int(idle // 60)} minute(s) idle: {why}")
            # Either SELECT has nothing to hand out, or it keeps naming one this lead
            # already started. Both are a person's to clear, and both are reported with
            # SELECT's own words rather than a summary of them.
            # Nothing mechanical answers. This is the one place judgement is worth
            # paying for: the selector computed everything it could and the queue is
            # still stopped.
            answer, note = self.ask_agent(SQUAD_FACILITATOR, _STUCK_PROMPT.format(why=why))
            if answer:
                return Decision("asked", f"the queue is stopped ({why}); hermes-scrum-master says:"
                                         f" {answer[:900]}")
            return Decision("stalled",
                            f"the session ended its turn and has been idle for "
                            f"{int(idle // 60)} minute(s); no menu is waiting and the "
                            f"backlog offers nothing to start — {why} [{note}]")

        option_text = selected.group(2)
        options = self._menu_options(screen)

        # The item comes from the OPTION first. Taking the screen's first `B-NNN` read
        # an id out of scrollback — observed live, reporting B-022 for an option about
        # B-033 — which would have charged the per-item ceiling to the wrong item and
        # let a real loop run past it.
        item = self._item_of(option_text, screen)

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

        if f"{item}|{option_text}" in self.surfaced:
            # Already put to a person, and they have not answered. Saying it again adds
            # nothing except noise to the log this lead exists to keep readable.
            return Decision("wait", "this question is already with a person",
                            option_text, item)

        kind = self.classify(option_text)
        if kind in ("content", "unknown"):
            flag = next((f for f in _RELAXING_FLAGS if f in option_text.lower()), "")
            if flag:
                # The floor. No doctrine reaches it, so there is nothing to ask.
                return Decision("escalate",
                                f"the option switches off a precondition ({flag}…); "
                                f"accepting that risk is nobody's to delegate",
                                option_text, item)
            # `unknown` comes here too, and it is the more common case: the markers are
            # a small vocabulary and a real menu rarely speaks it. "I cannot classify
            # this" is exactly where a rule that classifies it is worth reading — and
            # the observed refusal that stopped a queue for forty minutes was an
            # `unknown`, not a `content`.
            chosen, why = self._decide_by_doctrine(screen, options, item)
            if chosen is not None:
                return chosen
            base = ("only a person can answer this" if kind == "content"
                    else "the option does not read as flow")
            return Decision("escalate", f"{base} — {why}", option_text, item)

        # `(Recommended)` is the session stating what it would do. Confirming that is
        # not the lead having an opinion — it is the lead removing a wait.
        if not _RECOMMENDED_RE.search(option_text) and len(options) > 1:
            return Decision("escalate",
                            "flow option, but the session did not recommend it",
                            option_text, item)

        return Decision("confirm", "flow the session already recommended", option_text, item)

    # ── acting ─────────────────────────────────────────────────────────────
    def _prior_rulings(self, item: str) -> str:
        """What the doctrine already decided about this item, for the prompt.

        Every consultation is a fresh process with no memory of the last one. Measured:
        the same menu was answered twice, five minutes apart, with different options
        AND different rules — which is the incoherence the envelope was written to
        prevent, produced by the mechanism meant to enforce it.

        The envelope's own clause says a case resembling one already decided gets the
        same answer. An agent cannot honour that without being told what was decided,
        so the log is read back to it. Read from disk, not from memory, so a restarted
        lead does not forget what it already ruled.
        """
        if not item or self.log_path is None or not self.log_path.is_file():
            return ""
        past = []
        try:
            for line in self.log_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("event") == "choose" and entry.get("item") == item:
                    past.append(f"- option {entry.get('option_number')} — "
                                f"{entry.get('reason', '')}")
        except OSError:
            return ""
        if not past:
            return ""
        recent = "\n".join(past[-3:])
        return (f"This item has been ruled on before:\n{recent}\n\n"
                f"The envelope says a case resembling one already decided gets the SAME "
                f"answer, and a divergence needs its reason written beside it. If you "
                f"depart from the above, say why on the RULE APPLIED line.\n\n")

    def _menu_options(self, screen: str) -> list[tuple[str, str]]:
        """The options of the MENU, not every numbered line on screen.

        `1. do this` is also how a session writes a recommendation in prose, and both
        shapes sit on the same screen. Measured: a session's written recommendation —
        "1. Atualizar registro…", "2. Halt aqui…" — was read as the menu, so the option
        the lead recorded was a sentence from a paragraph and the menu passed to the
        agent was two lists spliced together.

        The cursor is what distinguishes them: exactly one line carries `❯`, and it is
        in the real menu. From there the block extends while lines are options or their
        indented descriptions, and stops at the first line that is neither.
        """
        lines = screen.splitlines()
        cursor = next((i for i, line in enumerate(lines) if _SELECTED_RE.match(line)), None)
        if cursor is None:
            return []

        def belongs(index: int) -> bool:
            if not 0 <= index < len(lines):
                return False
            line = lines[index]
            return bool(_OPTION_RE.match(line) or (line.strip() and line.startswith("  ")))

        start = cursor
        while belongs(start - 1):
            start -= 1
        end = cursor
        while belongs(end + 1):
            end += 1
        return _OPTION_RE.findall("\n".join(lines[start:end + 1]))

    def _item_of(self, option_text: str, screen: str) -> str:
        """The item this menu is about — from the MENU, never from the scrollback.

        The option first: it is the thing being answered. Failing that, the menu's own
        heading, which is the few lines above the first option and is where a session
        states what it is asking about.

        Never the whole screen. Measured twice on 2026-08-31: first reporting B-022 for
        an option about B-033, and then — after "read the option first" was supposed to
        fix it — reporting `escalate B-033` for a menu titled "B-059 scope", because the
        option carried no id and the fallback found `B-033/B-057` in a paragraph twenty
        lines up that mentioned them in passing.

        An id that did not come from the menu is a guess, and this lead is built on not
        guessing. Returning "" is the honest answer: the per-item ceiling then does not
        apply, and the option fingerprint still stops a real loop.
        """
        match = _ITEM_RE.search(option_text)
        if match:
            return match.group(0)
        lines = screen.splitlines()
        first_option = next((i for i, line in enumerate(lines) if _OPTION_RE.match(line)), None)
        if first_option is None:
            return ""
        heading = "\n".join(lines[max(0, first_option - _HEADING_LINES):first_option])
        match = _ITEM_RE.search(heading)
        return match.group(0) if match else ""

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

    def choose(self, screen: str, decision: Decision) -> bool:
        """Move the menu cursor to the chosen option and press Enter.

        Arrow keys rather than typing the number: the number is what the menu SHOWS,
        and a menu that renumbers between the read and the keystroke would take a
        different option under the same digit. Moving from where the cursor actually
        is has no such gap.
        """
        selected = _SELECTED_RE.search(screen)
        if not selected or not decision.option_number:
            return False
        try:
            steps = int(decision.option_number) - int(selected.group(1))
        except ValueError:
            return False
        key = "Down" if steps > 0 else "Up"
        back = "Up" if steps > 0 else "Down"
        moved = 0
        try:
            for _ in range(abs(steps)):
                subprocess.run(["tmux", "send-keys", "-t", self.session, key],
                               check=True, timeout=15)
                moved += 1
            # Re-read before committing: if the cursor is not where the arrows should
            # have put it, something else moved the menu and Enter would take the wrong
            # option.
            #
            # Polled rather than read once. The first version captured immediately after
            # send-keys and always saw the screen as it was BEFORE the redraw, so the
            # guard refused every move the arrows had actually made — three
            # consultations reached the right option, by the right rule, and none of
            # them ever pressed Enter. Sending a key and reading the result are separate
            # events, and a terminal owes you no ordering between them.
            if not self._cursor_reached(decision.option_number):
                self._rewind_cursor(back, moved)
                return False
            subprocess.run(["tmux", "send-keys", "-t", self.session, "Enter"],
                           check=True, timeout=15)
            if decision.typed:
                # The option opened a field. Typing and submitting are separate calls:
                # one send-keys carrying the text would submit whatever the field
                # already held, appended to ours.
                time.sleep(0.4)
                subprocess.run(["tmux", "send-keys", "-t", self.session, decision.typed],
                               check=True, timeout=15)
                subprocess.run(["tmux", "send-keys", "-t", self.session, "Enter"],
                               check=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            self._rewind_cursor(back, moved)
            return False
        if decision.item:
            self.interventions[decision.item] = self.interventions.get(decision.item, 0) + 1
        self.answered.add(f"{decision.item}|{decision.option}")
        return True

    def _cursor_reached(self, number: str) -> bool:
        """Wait for the terminal to redraw, then confirm the cursor landed.

        Bounded, and it fails closed: if the cursor is not there within the window, the
        answer is no. The window only has to cover a redraw, so it is short — long
        enough for a terminal, far too short to sit through anything the session does.
        """
        deadline = time.monotonic() + _REDRAW_SECONDS
        while time.monotonic() < deadline:
            landed = _SELECTED_RE.search(self.capture() or "")
            if landed and landed.group(1) == number:
                return True
            time.sleep(0.2)
        return False

    def _rewind_cursor(self, key: str, steps: int) -> None:
        """Put the cursor back where the session left it.

        A move that is not confirmed must leave nothing behind. Measured: two failed
        attempts walked the cursor from the option the session had highlighted down to
        "Type something.", and left it there — so the next reader, human or agent, saw
        a menu pointing at something nobody chose.
        """
        for _ in range(steps):
            try:
                subprocess.run(["tmux", "send-keys", "-t", self.session, key],
                               check=True, timeout=15)
                time.sleep(0.15)
            except (OSError, subprocess.SubprocessError):
                return

    def start(self, decision: Decision) -> bool:
        """Type the start command and send it.

        Re-validates the id at the point of typing rather than trusting the Decision.
        The check upstream is where the id is chosen; this one is where it becomes
        keystrokes in a session with no permission prompts, and the two places that
        matter are the one that decides and the one that acts.
        """
        if not _VALID_ITEM_RE.match(decision.item):
            return False
        command = decision.option or _BARE_TEMPLATE.format(item=decision.item)
        if f"/idea-to-release {decision.item}" not in command:
            # The one invariant of what gets typed: it invokes the cycle for the item
            # the decision names. Checked here because this is where it becomes
            # keystrokes, not where it was composed.
            return False
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


@dataclass
class Fleet:
    """The sessions a lead watches, and the items they already hold.

    One session is one item at a time — that is what a session IS — so the only way to
    work more than one item at once is to have more than one session. Measured with a
    single session: the watchdog started three items in nine minutes, none of them
    produced an event, and by the end the session was analysing something none of the
    three had asked for. That was not parallelism; it was a change of subject every few
    minutes, and the fix for it is not a better timeout.

    The coordinator holds exactly one fact: which item each session is on. Everything
    else — the menu rules, the doctrine, the guards — stays in `Lead`, one per session,
    unchanged. A shared set is the whole of the coordination, because the only thing
    two sessions can do to each other is take the same work twice.
    """
    #: session name -> the item it was last handed.
    taken: dict[str, str] = field(default_factory=dict)

    #: agent name -> when it was last consulted, shared across the whole fleet.
    #:
    #: It lives HERE and not in `Lead` because `main()` builds one `Lead` per
    #: session, each with its own `agent_asked`, so a per-lead cooldown is a
    #: cooldown per (agent, session). The question these consultations ask — "the
    #: queue is stopped, what now" — is about the QUEUE, which is one thing; three
    #: leads asked it of the same agent within their own clocks.
    #:
    #: Measured on a consumer 2026-09-02: five consultations to `hermes-scrum-master`
    #: in 36 minutes, gaps of 96s, 1035s, 852s and 159s against a declared 1800s
    #: cooldown, every one of them answered rather than barred, all five carrying the
    #: same question about the same two items. They cost 49% of the observed window
    #: and produced no information the first had not.
    asked_at: dict[str, float] = field(default_factory=dict)

    @classmethod
    def restored(cls, log_path: Path | None) -> "Fleet":
        """Rebuild the claims from the log, so a restart does not hand work out twice.

        The claim lived only in memory, and every restart of the watchdog forgot it.
        Measured minutes after the fleet first worked: the lead was restarted to pick up
        a change, and two sessions were handed the same item — the exact collision this
        class exists to prevent, caused by the class starting empty.

        The log already records which session was handed what, so the state was never
        actually lost; it was only never read back. The LAST start per session wins,
        because that is the item that session is on now.
        """
        fleet = cls()
        if log_path is None or not log_path.is_file():
            return fleet
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return fleet
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (entry.get("event") == "start" and entry.get("sent")
                    and entry.get("session") and entry.get("item")):
                fleet.taken[entry["session"]] = entry["item"]
        return fleet

    def holder(self, item: str) -> str | None:
        for session, held in self.taken.items():
            if held == item:
                return session
        return None

    def claim(self, session: str, item: str) -> None:
        self.taken[session] = item

    def release(self, session: str) -> None:
        self.taken.pop(session, None)


def _log(path: Path | None, session: str, payload: dict) -> None:
    """Append one line. A lead nobody can audit is a lead nobody should trust.

    The timestamp is stamped here rather than by the caller, so no decision can reach
    the log without one. It was missing at first, and a log of decisions with no time
    on them cannot answer the question anyone actually asks — *when did it stop?*

    The `session` is stamped here for the same reason. It is a property of the
    watcher, not of the decision, and a fleet log without it cannot tell three
    lanes stalling once from one lane stalling three times (issue #24).
    """
    payload = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "session": session, **payload}
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


def watch_fleet(leads: list[Lead], markers: dict[str, Path | None], log: Path | None,
                poll: int, rounds: int | None = None) -> int:
    """Watch several sessions, one lead each, sharing one claim on the work.

    Round-robin rather than threads: each pass gives every session a turn, and a
    session that is busy costs one screen capture. Nothing here is concurrent, and
    nothing needs to be — the concurrency is in the SESSIONS, which is where a session
    can only ever have been.

    A lead that loses its session is dropped and the rest keep watching. One tmux
    window closing is not a reason for the other five to go unwatched.
    """
    served = 0
    alive = list(leads)
    while alive and (rounds is None or served < rounds):
        served += 1
        for lead in list(alive):
            if watch_once(lead, markers.get(lead.session), log, poll) != 0:
                alive.remove(lead)
                if lead.fleet is not None:
                    lead.fleet.release(lead.session)
        if alive:
            time.sleep(poll)
    return 0 if leads else 1


def watch_once(lead: Lead, marker: Path | None, log: Path | None, poll: int) -> int:
    """One pass over one session. Returns non-zero when the session is gone."""
    return watch(lead, marker, log, poll, rounds=1)


def watch(lead: Lead, marker: Path | None, log: Path | None,
          poll: int, rounds: int | None = None) -> int:
    served = 0
    while rounds is None or served < rounds:
        served += 1
        screen = lead.capture()
        if screen is None:
            _log(log, lead.session, {"event": "gone"})
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
        elif decision.action == "choose":
            entry["sent"] = lead.choose(screen, decision)
            entry["option_number"] = decision.option_number
            if decision.typed:
                entry["typed"] = decision.typed
        elif decision.action == "start":
            # Checked here, not in `decide`: this is the last moment before keystrokes,
            # and it is the only one where "is it still quiet?" has the right answer.
            if lead.still_quiet(marker):
                entry["sent"] = lead.start(decision)
                if entry["sent"] and lead.fleet is not None:
                    # Claimed only once the keystroke landed. Claiming on the decision
                    # would reserve an item for a session that never received it.
                    lead.fleet.claim(lead.session, decision.item)
            else:
                entry["sent"] = False
                entry["reason"] = ("the session moved between the decision and the "
                                   "keystrokes; not typing into a working session")
        _log(log, lead.session, entry)

        if decision.action == "asked":
            # An answer is not an action. It goes in the log for a person to read, and
            # the lead keeps watching — acting on it would be the lead deciding what
            # it just paid an agent to think about.
            lead.reported_stall = True
            lead.stall_reported_at = time.time()
            time.sleep(poll)
            continue

        if decision.action in ("start", "choose"):
            # The session has work again. The next stall is a new fact.
            lead.reported_stall = False
            time.sleep(poll)
            continue

        if decision.action == "still_stalled":
            # The heartbeat. Same stall, restated so the log proves the watch is
            # running; the clock restarts so the next one is a heartbeat away.
            lead.stall_reported_at = time.time()
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
            lead.stall_reported_at = time.time()
            time.sleep(poll)
            continue

        if decision.action in ("escalate", "exhausted"):
            # Reported once, and the watch CONTINUES.
            #
            # It used to `return 0` here, and the reason was sound as far as it went:
            # repeating "a person must answer" every poll buries the line in a log
            # nobody reads. But it bought that by killing the watchdog, and a watchdog
            # that dies at the first ambiguity is a watchdog for the first ambiguity.
            #
            # Measured on 2026-08-31 at 20:39: the lead correctly refused a scope
            # decision — the best call it made all day — and then exited, leaving the
            # session unwatched from that moment on. The same fix already landed for
            # `stalled` this morning, for the same reason, and this branch was missed.
            #
            # `surfaced` is what keeps the log quiet: the same question is raised once.
            lead.surfaced.add(f"{decision.item}|{decision.option}")
            time.sleep(poll)
            continue
        time.sleep(poll)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--session", default="squad",
                        help="tmux session to watch. Comma-separated for a fleet: each "
                             "session gets its own lead and no two are handed the same "
                             "item. One session works one item at a time — that is what "
                             "a session is — so a fleet is the only way to work several")
    parser.add_argument("--marker-dir", type=Path,
                        help="directory holding one activity marker per session, named "
                             "<session>.log. Used instead of --marker for a fleet")
    parser.add_argument("--marker", type=Path,
                        help="file whose mtime marks activity (the session's log)")
    parser.add_argument("--log", type=Path, help="append decisions here as JSONL")
    parser.add_argument("--idle", type=int, default=90,
                        help="seconds of silence before the lead may act")
    parser.add_argument("--poll", type=int, default=20)
    parser.add_argument("--max-per-item", type=int, default=3)
    parser.add_argument("--agents-when-stuck", action="store_true",
                        help="when the selector has no actionable answer, spend one "
                             "headless `claude -p` call asking the hermes-scrum-master agent "
                             "what to do. Off by default")
    parser.add_argument("--agent-budget-usd", type=float, default=40.00,
                        help="ceiling for ONE agent call (default 6.00). Measured: a "
                             "real menu consultation cost USD 3.67. To spend less, "
                             "raise --agent-cooldown rather than lowering this")
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
    names = [n.strip() for n in args.session.split(",") if n.strip()]
    if not names:
        print("FATAL: --session named nothing", file=sys.stderr)
        return 1

    fleet = Fleet.restored(args.log) if len(names) > 1 else None
    if fleet is not None and fleet.taken:
        print(f"==> restored {len(fleet.taken)} claim(s) from the log: "
              + ", ".join(f"{s}={i}" for s, i in sorted(fleet.taken.items())),
              file=sys.stderr)
    leads, markers = [], {}
    for name in names:
        leads.append(Lead(session=name, project=project, max_per_item=args.max_per_item,
                          idle_seconds=args.idle, stalled_seconds=args.stalled,
                          agents_when_stuck=args.agents_when_stuck,
                          agent_budget_usd=args.agent_budget_usd,
                          agent_cooldown=args.agent_cooldown, log_path=args.log,
                          fleet=fleet))
        markers[name] = (args.marker_dir / f"{name}.log") if args.marker_dir else args.marker

    if len(leads) == 1:
        return watch(leads[0], markers[names[0]], args.log, args.poll,
                     rounds=1 if args.once else None)
    return watch_fleet(leads, markers, args.log, args.poll,
                       rounds=1 if args.once else None)


if __name__ == "__main__":
    raise SystemExit(main())

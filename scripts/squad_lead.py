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


@dataclass
class Decision:
    action: str          # confirm · escalate · wait · exhausted · stalled · start
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
    #: True once a handed-back turn has been reported, so it is not repeated every
    #: poll. Cleared when the session moves again.
    reported_stall: bool = False
    #: How many times each item has been unblocked, and every question already
    #: answered. Both are stopping criteria, not statistics.
    interventions: dict[str, int] = field(default_factory=dict)
    answered: set[str] = field(default_factory=set)
    #: Items this lead has already started. Starting one twice is the loop the
    #: per-item ceiling exists to stop, one level up.
    started: set[str] = field(default_factory=set)

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
            if item and item not in self.started:
                return Decision(
                    "start", f"the session handed the turn back after "
                             f"{int(idle // 60)} minute(s); SELECT names {item} as next "
                             f"({why})", _START_TEMPLATE.format(item=item), item)

            if self.reported_stall:
                return Decision("wait", "no menu is waiting")
            # Either SELECT has nothing to hand out, or it keeps naming one this lead
            # already started. Both are a person's to clear, and both are reported with
            # SELECT's own words rather than a summary of them.
            already = " (already started once by this lead)" if item else ""
            return Decision("stalled",
                            f"the session ended its turn and has been idle for "
                            f"{int(idle // 60)} minute(s); no menu is waiting and the "
                            f"backlog offers nothing to start — {why}{already}")

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
        self.started.add(decision.item)
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
                idle_seconds=args.idle, stalled_seconds=args.stalled)
    return watch(lead, args.marker, args.log, args.poll, rounds=1 if args.once else None)


if __name__ == "__main__":
    raise SystemExit(main())

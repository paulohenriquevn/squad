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


@dataclass
class Decision:
    action: str          # confirm · escalate · wait · exhausted
    reason: str
    option: str = ""
    item: str = ""


@dataclass
class Lead:
    session: str
    max_per_item: int = 3
    idle_seconds: int = 90
    #: How many times each item has been unblocked, and every question already
    #: answered. Both are stopping criteria, not statistics.
    interventions: dict[str, int] = field(default_factory=dict)
    answered: set[str] = field(default_factory=set)

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
        if any(m in low for m in CONTENT_MARKERS):
            return "content"
        if any(m in low for m in FLOW_MARKERS):
            return "flow"
        return "unknown"

    def decide(self, screen: str) -> Decision:
        selected = _SELECTED_RE.search(screen)
        if not selected:
            return Decision("wait", "no menu is waiting")

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
            return Decision("escalate", "only a person can answer this", option_text, item)
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


def _log(path: Path | None, payload: dict) -> None:
    """Append one line. A lead nobody can audit is a lead nobody should trust."""
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
            # Working. A lead that interrupts a session mid-thought is worse than no
            # lead: it answers a menu the session was about to move past on its own.
            time.sleep(poll)
            continue

        decision = lead.decide(screen)
        if decision.action == "wait":
            time.sleep(poll)
            continue

        entry = {"event": decision.action, "item": decision.item,
                 "reason": decision.reason, "option": decision.option[:160],
                 "idle_seconds": None if idle == float("inf") else round(idle)}
        if decision.action == "confirm":
            entry["sent"] = lead.confirm(decision)
        _log(log, entry)

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
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    args = parser.parse_args(argv)

    lead = Lead(session=args.session, max_per_item=args.max_per_item,
                idle_seconds=args.idle)
    return watch(lead, args.marker, args.log, args.poll, rounds=1 if args.once else None)


if __name__ == "__main__":
    raise SystemExit(main())

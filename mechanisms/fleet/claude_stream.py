#!/usr/bin/env python3
"""Talk to Claude Code over its own protocol instead of through a terminal.

`claude -p --output-format stream-json` emits one JSON object per line and ends
with a `result` object carrying the outcome, the cost and the session id. That is
the difference this module exists for: with `--output-format text` every one of
those facts has to be inferred from prose, and inference is where a watchdog
starts believing things.

WHAT THE TEXT MODE COSTS, MEASURED
-----------------------------------
`claude -p` reports a blown budget on STDOUT and exits 0. Reading stdout as "the
answer" made the lead treat `Error: Exceeded USD budget` as the agent's reply,
find no rule in it, and escalate saying no rule covered the case — it had never
been asked. The guard against that was a prefix check on the first line, which is
a parser for one error message out of however many exist.

In stream-json the same run ends with `{"type":"result","subtype":"error_...",
"is_error":true}`, and the caller does not have to recognise the sentence.

WHAT IT BUYS BEYOND CORRECTNESS
--------------------------------
    total_cost_usd   what the call ACTUALLY cost. The lead had a ceiling and no
                     measurement: five duplicate consultations on a consumer were
                     invisible until the money was reconstructed by hand.
    session_id       the address for `--resume`, which is how a second turn
                     reaches the same conversation rather than starting a new one.
    num_turns        whether the agent worked or answered in one shot.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

class Unsupported(RuntimeError):
    """The installed CLI does not have the capability being asked for.

    Distinct from a failure: the command did not go wrong, it does not exist
    here. A caller may fall back; what it must not do is report the absence as
    an answer — "no sessions" and "I cannot see the sessions" are different
    facts, and this kit keeps finding the cost of confusing them.
    """


def _version() -> str:
    try:
        done = subprocess.run(["claude", "--version"], capture_output=True,  # noqa: PLW1510
                              text=True, timeout=15, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return "version unknown"
    return (done.stdout or "").strip() or "version unknown"


#: `--output-format stream-json` is refused without it, so it is not optional and
#: not a debugging flag: it is part of the invocation.
_REQUIRED = ("--output-format", "stream-json", "--verbose")


@dataclass
class StreamResult:
    """One `claude -p` run, as the protocol reported it."""

    text: str = ""
    #: `success`, or an `error_*` subtype the CLI names.
    subtype: str = ""
    is_error: bool = False
    cost_usd: float | None = None
    session_id: str | None = None
    num_turns: int | None = None
    #: Why no result arrived, when none did. Empty on a run that ended properly,
    #: whatever the verdict — a failed run and an unreadable one are different
    #: facts and the caller has to be able to tell them apart.
    transport_error: str = ""
    events: list[dict] = field(default_factory=list, repr=False)

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.is_error and not self.transport_error


def parse(stdout: str) -> StreamResult:
    """Read the event stream. The `result` line is the one that decides."""
    report = StreamResult()
    for line in stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue  # the CLI also prints plain notices; they are not events
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        report.events.append(event)
        if event.get("session_id") and not report.session_id:
            report.session_id = event["session_id"]
        if event.get("type") == "result":
            report.subtype = str(event.get("subtype") or "")
            report.is_error = bool(event.get("is_error")) or report.subtype.startswith("error")
            report.num_turns = event.get("num_turns")
            cost = event.get("total_cost_usd")
            report.cost_usd = float(cost) if isinstance(cost, (int, float)) else None
            report.text = str(event.get("result") or "").strip()

    if not report.events:
        report.transport_error = "the stream carried no JSON events"
    elif not report.subtype:
        # Events arrived and none of them closed the run: the process died mid
        # stream. Reporting the assistant text collected so far would be reporting
        # a partial answer as a complete one.
        report.transport_error = "the stream ended without a result event"
    return report


def ask(prompt: str, *, cwd: Path, budget_usd: float | None = None,
        timeout: int = 300, resume: str | None = None,
        extra: tuple[str, ...] = ()) -> StreamResult:
    """Run one prompt and return what the protocol said about it.

    `resume` continues an existing conversation instead of opening a new one —
    the second turn of a consultation costs the context once, not twice.
    """
    command = ["claude", "-p", prompt, *_REQUIRED, "--no-session-persistence"]
    if resume:
        # Persistence is what makes a session resumable, so the two are exclusive.
        command = ["claude", "-p", prompt, *_REQUIRED, "--resume", resume]
    if budget_usd is not None:
        command += ["--max-budget-usd", str(budget_usd)]
    command += list(extra)

    try:
        done = subprocess.run(  # noqa: PLW1510
            command, capture_output=True, text=True, timeout=timeout, cwd=str(cwd),
            # Closed, not inherited: `claude -p` reads stdin for piped input and
            # waits on a pipe that never delivers, which is what a daemon's stdin
            # is under tmux through `tee`.
            stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return StreamResult(transport_error=f"no answer in {timeout}s")
    except (OSError, subprocess.SubprocessError) as error:
        return StreamResult(transport_error=f"could not be run ({error})")

    report = parse(done.stdout)
    if report.transport_error and done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip()
        report.transport_error = f"exited {done.returncode}: {detail[:200] or 'no output'}"
    return report


def sessions(cwd: Path | None = None, timeout: int = 30) -> list[dict]:
    """Live Claude sessions, from `claude agents --json`.

    Each carries `name`, `sessionId`, `status` (`busy`/`idle`), `cwd` and `pid`.
    `status` is the fact a watchdog otherwise reconstructs by screen-scraping a
    terminal and timing how long it has not changed.

    An empty list on failure would say "no sessions" about a command that did not
    run; the caller gets an exception instead.
    """
    command = ["claude", "agents", "--json"]
    if cwd is not None:
        command += ["--cwd", str(cwd)]
    done = subprocess.run(command, capture_output=True, text=True,  # noqa: PLW1510
                          timeout=timeout, stdin=subprocess.DEVNULL)

    # `--json` arrived after 2.1.144. A consumer pinned to an older CLI gets
    # `unknown option`, and the CLI exits 0 while saying it — so a returncode
    # check alone reads the refusal as an empty session list. Measured on a real
    # runner: local 2.1.236 answered, remote 2.1.144 did not, and the difference
    # was invisible until the JSON failed to parse.
    combined = (done.stdout or "") + (done.stderr or "")
    if "unknown option" in combined or "unknown command" in combined:
        raise Unsupported(
            "`claude agents --json` is not in this CLI "
            f"({_version()}); it landed after 2.1.144. Upgrade, or read the "
            "sessions from tmux — but do not report an empty fleet")
    if done.returncode != 0:
        raise RuntimeError(f"`claude agents --json` exited {done.returncode}: "
                           f"{(done.stderr or '').strip()[:160]}")
    try:
        rows = json.loads(done.stdout or "[]")
    except ValueError as error:
        raise RuntimeError(f"`claude agents --json` returned no JSON: {error}") from error
    return [r for r in rows if isinstance(r, dict)]

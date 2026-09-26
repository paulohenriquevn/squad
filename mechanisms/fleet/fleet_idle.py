#!/usr/bin/env python3
"""Where a fleet's time actually goes, from the watchdog's own log.

    python3 mechanisms/fleet/fleet_idle.py [--project PATH] [--json]

The lead writes one JSON line per decision. That log answers "what happened"; it
does not answer "how much of the window was spent producing nothing", and that is
the question a stalled fleet raises.

HOW THE TIME IS COUNTED, AND WHY NOT THE OBVIOUS WAY
-----------------------------------------------------
Each event carries `idle_seconds` — how long the lead had been watching an idle
session when it decided. Summing that field is the obvious measure and it is
WRONG: consecutive observations overlap, so the total exceeds the window and the
error grows with the poll rate. Measured on a real log: summing gave 45.8 of 56
minutes, which is 82% and cannot be checked against anything.

What is counted here is the interval between consecutive events, attributed to
the event that opened it. Those intervals are disjoint by construction, they add
up to the window, and the report prints both so the arithmetic is visible.

An event kind that produces no work — `stalled`, `asked` — carries idle time by
definition. `start` carries the time a session was working, which is the only
part of the window that bought anything.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# `squad.paths` owns every data-root literal, and now the lead-log path with them.
for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import lead_log_path  # noqa: E402 — post-bootstrap import

#: Decisions that handed work to a session. Everything else is the queue not moving.
PRODUCTIVE = ("start",)


@dataclass
class IdleReport:
    events: int = 0
    window_seconds: float = 0.0
    accounted_seconds: float = 0.0
    by_event: dict[str, dict[str, float]] = field(default_factory=dict)
    handouts_per_session: dict[str, int] = field(default_factory=dict)
    idle_seconds: float = 0.0
    productive_seconds: float = 0.0
    #: Sessions the fleet watched that were never handed anything.
    starved_sessions: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def idle_share(self) -> float:
        return self.idle_seconds / self.window_seconds if self.window_seconds else 0.0


class LogUnreadable(OSError):
    """The decision log exists and could not be read.

    `read_events` used to return the empty list for this, and `main` has already
    confirmed the file exists — so the OSError it hid is a permission or I/O failure,
    and the report produced from an empty list reads "fewer than two events — there is
    no interval to measure", which is what a YOUNG FLEET looks like. An unreadable log
    and a fleet that just started became the same sentence.
    """


def read_events(log: Path) -> list[dict]:
    """Decision rows with a PARSEABLE timestamp, oldest-first order left to the caller.

    The stamp is parsed HERE, not in `measure`. `measure` called
    `dt.datetime.fromisoformat(event["at"])` inside a sort key and a subtraction, so one
    line whose `at` is not ISO-8601 raised ValueError out of `main`, and a log mixing
    aware with naive stamps raised TypeError on the subtraction. Both are ordinary in a
    log several processes append to.
    """
    rows: list[dict] = []
    if not log.exists():
        # Absent is a different fact from unreadable, and `main` reports it separately.
        return rows
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise LogUnreadable(f"{log} exists and could not be read: {exc}") from exc
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue  # the lead also writes plain lines; they are not decisions
        if isinstance(row, dict) and row.get("at"):
            rows.append(row)
    return rows


def _stamp(raw: object) -> dt.datetime | None:
    """`raw` as an AWARE UTC datetime, or None when it is not a timestamp.

    Naive stamps are read as UTC rather than dropped: the lead writes them with
    `datetime.now(timezone.utc).isoformat()`, and a log carrying both shapes is a log
    written across a change in that line — not a log to refuse.
    """
    if not isinstance(raw, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def measure(rows: list[dict], watched: list[str] | None = None) -> IdleReport:
    # Stamps are parsed HERE, before anything sorts or subtracts. `when()` used to call
    # `fromisoformat` inside the sort key and inside the subtraction, so ONE row whose
    # `at` is not ISO-8601 raised ValueError out of `main`, and a log mixing aware with
    # naive stamps raised TypeError on the subtraction. Both are ordinary in a log that
    # several processes append to across a change in how the stamp is written.
    usable, unparseable = [], 0
    for row in rows:
        stamp = _stamp(row.get("at"))
        if stamp is None:
            unparseable += 1
            continue
        usable.append({**row, "_at": stamp})
    if unparseable:
        print(f"fleet-idle: {unparseable} row(s) carry a timestamp that will not parse "
              f"and were dropped from the measurement", file=sys.stderr)
    rows = usable

    report = IdleReport(events=len(rows))
    if len(rows) < 2:
        report.detail = ("fewer than two events — there is no interval to measure. "
                         "This is not 'no idle time'; it is nothing to measure yet")
        return report

    def when(event: dict) -> dt.datetime:
        # Parsed and normalised by `read_events`; nothing here can raise.
        return event["_at"]

    rows = sorted(rows, key=when)
    report.window_seconds = (when(rows[-1]) - when(rows[0])).total_seconds()

    spans: dict[str, list[float]] = collections.defaultdict(list)
    for current, following in zip(rows, rows[1:]):
        spans[current.get("event") or "?"].append((when(following) - when(current)).total_seconds())

    for kind, values in spans.items():
        total = sum(values)
        report.accounted_seconds += total
        report.by_event[kind] = {
            "count": len(values),
            "total_seconds": round(total, 1),
            "median_seconds": round(sorted(values)[len(values) // 2], 1),
            "max_seconds": round(max(values), 1),
        }
        if kind in PRODUCTIVE:
            report.productive_seconds += total
        else:
            report.idle_seconds += total

    handed = collections.Counter(
        row.get("session") for row in rows
        if row.get("event") in PRODUCTIVE and row.get("session"))
    report.handouts_per_session = dict(handed)

    # A session nobody handed work to is capacity that was paid for and not used.
    # It is only visible against the list the lead was WATCHING: from the log alone
    # a starved session is indistinguishable from one that does not exist.
    if watched:
        report.starved_sessions = sorted(s for s in watched if not handed.get(s))

    report.detail = (f"{report.window_seconds/60:.1f} min observed, "
                     f"{report.accounted_seconds/60:.1f} min in intervals")
    return report


def render(report: IdleReport) -> str:
    if report.window_seconds == 0:
        return f"fleet-idle: {report.detail}"

    lines = [f"fleet-idle — {report.detail}", ""]
    lines.append(f"  idle:       {report.idle_seconds/60:6.1f} min  "
                 f"({100*report.idle_share:.0f}% of the window)")
    lines.append(f"  productive: {report.productive_seconds/60:6.1f} min")
    lines.append("")
    lines.append("  interval opened by each decision:")
    for kind, stats in sorted(report.by_event.items(),
                              key=lambda kv: -kv[1]["total_seconds"]):
        mark = " " if kind in PRODUCTIVE else "·"
        lines.append(f"   {mark} {kind:9} n={int(stats['count']):2}  "
                     f"total={stats['total_seconds']/60:5.1f} min  "
                     f"median={stats['median_seconds']:5.0f}s  "
                     f"max={stats['max_seconds']:5.0f}s")
    if report.handouts_per_session:
        lines.append("")
        lines.append("  handouts per session: " + ", ".join(
            f"{s}={n}" for s, n in sorted(report.handouts_per_session.items())))
    if report.starved_sessions:
        lines.append(f"  NEVER handed work:    {', '.join(report.starved_sessions)}"
                     "  — capacity paid for and unused")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # No literal default. `/tmp/squad-lead.jsonl` was spelled here and in two shell
    # scripts, so two fleets on one machine wrote into ONE file and every reader saw
    # them interleaved. `squad.paths` owns the path for the same reason it owns the
    # data roots — three copies is how they come to disagree.
    parser.add_argument("--log", type=Path, default=None,
                        help="default: the lead log of the project at --project")
    parser.add_argument("--project", type=Path, default=Path("."),
                        help="the project whose fleet this reads")
    parser.add_argument("--session", default="",
                        help="comma-separated sessions the lead watches, so a "
                             "starved one can be named")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.log is None:
        args.log = lead_log_path(args.project)

    if not args.log.is_file():
        print(f"fleet-idle: no log at {args.log} — nothing was measured, which is "
              f"not the same as an idle fleet", file=sys.stderr)
        return 2

    watched = [s.strip() for s in args.session.split(",") if s.strip()]
    try:
        rows = read_events(args.log)
    except LogUnreadable as exc:
        # The same refusal as the branch above, for the other way of not measuring. A
        # log that exists and cannot be read used to produce "fewer than two events",
        # which is what a fleet that just started looks like.
        print(f"fleet-idle: {exc} — nothing was measured, which is not the same as an "
              f"idle fleet", file=sys.stderr)
        return 2
    report = measure(rows, watched)
    print(json.dumps(asdict(report), indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

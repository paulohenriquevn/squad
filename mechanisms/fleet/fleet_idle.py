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
from squad.paths import lead_log_path  # noqa: E402

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


def read_events(log: Path) -> list[dict]:
    rows = []
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue  # the lead also writes plain lines; they are not decisions
        if isinstance(row, dict) and row.get("at"):
            rows.append(row)
    return rows


def measure(rows: list[dict], watched: list[str] | None = None) -> IdleReport:
    report = IdleReport(events=len(rows))
    if len(rows) < 2:
        report.detail = ("fewer than two events — there is no interval to measure. "
                         "This is not 'no idle time'; it is nothing to measure yet")
        return report

    def when(event: dict) -> dt.datetime:
        return dt.datetime.fromisoformat(event["at"])

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
    report = measure(read_events(args.log), watched)
    print(json.dumps(asdict(report), indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

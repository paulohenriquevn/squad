#!/usr/bin/env python3
"""The whole picture, as one JSON document: every item, where it is, what holds it.

Two sources, and they answer different questions:

  BACKLOG.md              WHERE each item stands right now — the state that survives
                          the session, and the only one that exists for work done
                          before the cycle was instrumented.
  cycle-events.jsonl      WHAT HAPPENED and when — the phase transitions, with the
                          verdict each one reached.

The second is the richer one and the one that is usually empty. It is per-machine and
per-session by decision (`.gitignore` carries the reason: one machine's run history
does not belong in everyone's diff), and it starts empty in every clone. So the board
must be legible from the registry ALONE, and treat the stream as detail it may or may
not have — a board that needs the stream shows an empty screen in the exact situation
someone first opens it.

Position is therefore derived twice, in order of confidence:

  1. the last phase the stream says finished, when there is a stream
  2. otherwise the phase implied by `status`, which is all the registry can say

`stream` vs `derived` is reported per item, because a board that presents an inference
and a measurement in the same typeface is doing the thing this ecosystem caps plans
at 49 for.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_backlog_structure import (  # noqa: E402
    OPEN_STATUS,
    _parse_items,
    declares_impediment,
    parse_blocked_by,
)

#: The board's columns, in cycle order. `killed` is a lane rather than a column: it is
#: a terminal OUTCOME, and the contract is explicit that it is a successful one, so
#: burying it after `release` would put a success at the end of a pipeline it left
#: early.
PHASES = ("backlog", "discover", "plan", "implement", "code-quality", "review",
          "release", "acceptance")

#: What a registry status implies about position when no stream exists. A status
#: records the phase that FINISHED, so the item sits in the next one.
STATUS_PHASE = {
    "raw": "backlog",
    "triaged": "discover",
    "planned": "plan",
    "shipped": "release",
    "killed": "killed",
}


def _events_path(project_root: Path) -> Path | None:
    for rel in (".claude/records/cycle-events.jsonl", "records/cycle-events.jsonl"):
        candidate = project_root / rel
        if candidate.is_file():
            return candidate
    return None


def read_events(project_root: Path) -> list[dict]:
    path = _events_path(project_root)
    if path is None:
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # A truncated last line is normal in an append-only file being written
            # right now. Dropping it beats refusing to render the board.
            continue
    return events


def build_state(project_root: Path) -> dict:
    backlog = project_root / "BACKLOG.md"
    if not backlog.is_file():
        return {"error": f"no BACKLOG.md under {project_root}", "items": [], "phases": list(PHASES)}

    items = _parse_items(backlog.read_text(encoding="utf-8-sig"))
    statuses = {i.item_id: i.fields.get("status", "") for i in items}
    events = read_events(project_root)

    # Last finished phase per item, from the stream.
    reached: dict[str, dict] = {}
    for event in events:
        slug = (event.get("slug") or "").upper()
        cycle = event.get("cycle") or ""
        if not slug or cycle not in PHASES or event.get("type") != "cycle:phase:end":
            continue
        if cycle in PHASES:
            prev = reached.get(slug)
            if prev is None or PHASES.index(cycle) >= PHASES.index(prev["phase"]):
                reached[slug] = {"phase": cycle, "verdict": event.get("verdict"),
                                 "at": event.get("timestamp")}

    out_items = []
    for item in items:
        iid = item.item_id
        status = item.fields.get("status", "")
        raw_block = item.fields.get("blocked_by", "")
        blockers = parse_blocked_by(raw_block)
        live = [b for b in blockers if statuses.get(b, "") in OPEN_STATUS]
        # `bool(...)`, because `and` yields its last truthy operand: without it the
        # field carried the blocker LIST where the contract says boolean. The page
        # happened to work — a non-empty array is truthy in JS — which is the kind of
        # accident that survives until someone reads the JSON and believes the type.
        impeded = bool(status in OPEN_STATUS and declares_impediment(raw_block)
                       and (live or not blockers))

        hit = reached.get(iid)
        if hit:
            # The stream says a phase finished; the item sits in the one after it.
            nxt = PHASES.index(hit["phase"]) + 1
            phase = PHASES[nxt] if nxt < len(PHASES) else "done"
            source = "stream"
        else:
            phase = STATUS_PHASE.get(status, "backlog")
            source = "derived"

        out_items.append({
            "id": iid,
            "title": item.title,
            "status": status,
            "phase": phase,
            "position_from": source,
            "blocked": impeded,
            "blockers": live,
            "blocked_note": raw_block.strip() if impeded and not live else "",
            "domain": item.fields.get("domain", ""),
            "repo": item.fields.get("repo", ""),
            "evidence": item.fields.get("evidence", ""),
            "last_verdict": (hit or {}).get("verdict"),
            "last_at": (hit or {}).get("at"),
        })

    out_items.sort(key=lambda d: _number(d["id"]))
    return {
        "project": project_root.name,
        "project_path": str(project_root),
        "phases": list(PHASES),
        "items": out_items,
        "events": events[-200:],
        "event_total": len(events),
        "has_stream": _events_path(project_root) is not None,
    }


def _number(item_id: str) -> int:
    match = re.search(r"(\d+)", item_id)
    return int(match.group(1)) if match else 1 << 30


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(build_state(root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

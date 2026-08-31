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
import time
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


#: An item id anywhere in a slug, with or without the hyphen.
_SLUG_ITEM_RE = re.compile(r"\bb-?(\d{3,})\b", re.IGNORECASE)


def item_id_of(slug: str) -> str:
    """The `B-NNN` a stream slug refers to, normalised.

    Two conventions reach the stream and both are correct in their own phase. The
    phases instrumented for the maintenance chain emit the ITEM id — `B-033` — because
    that is what the registry keys on. The phases that were already emitting
    (`implement`, `code-quality`, `review`) emit the PLAN slug — `b033-prometheus-url-
    dev-public` — because that is what names the artefact they produced.

    Matching on the raw string loses the second kind entirely. Measured on the first
    real run: 12 events, 6 of them plan slugs, and every one of those six invisible on
    the board — half the execution, missing from the view built to show it.
    """
    match = _SLUG_ITEM_RE.search(slug or "")
    return f"B-{match.group(1)}" if match else (slug or "").upper()


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


def read_lead(log_path: Path | None, marker_path: Path | None) -> dict:
    """What the supervisor decided, and whether the executing session is moving.

    This exists because of a question that had no answer on the board: the session had
    handed its turn back and sat still for two hours, and the only way to find out was
    to attach to a tmux pane and read it. A board that shows every item and not whether
    anything is working shows the shape of the work and not its state.

    Both sources are optional. A board with no supervisor is the normal case — the
    fields come back empty rather than absent, so the page renders one way.
    """
    out: dict = {"decisions": [], "idle_seconds": None, "watching": False}

    if marker_path is not None and marker_path.exists():
        out["watching"] = True
        try:
            out["idle_seconds"] = max(0, int(time.time() - marker_path.stat().st_mtime))
        except OSError:
            pass

    if log_path is None or not log_path.is_file():
        return out
    entries = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    # Newest first: the question is always "what just happened", never "what happened
    # first". Capped because a long-running lead's log outgrows a page.
    out["decisions"] = list(reversed(entries))[:40]
    return out


def build_state(project_root: Path, lead_log: Path | None = None,
                lead_marker: Path | None = None) -> dict:
    backlog = project_root / "BACKLOG.md"
    if not backlog.is_file():
        return {"error": f"no BACKLOG.md under {project_root}", "items": [],
                "phases": list(PHASES), "lead": read_lead(lead_log, lead_marker)}

    items = _parse_items(backlog.read_text(encoding="utf-8-sig"))
    statuses = {i.item_id: i.fields.get("status", "") for i in items}
    events = read_events(project_root)

    # A phase that STARTED and has not ended is work happening right now. Without it
    # the board can only draw what finished, which is a picture of the past: an item
    # under active work showed the verdict of a phase that was already over, and
    # nothing on the page said anything was running.
    running: dict[str, dict] = {}
    for event in events:
        slug = item_id_of(event.get("slug") or "")
        cycle = event.get("cycle") or ""
        if not slug or cycle not in PHASES:
            continue
        if event.get("type") == "cycle:phase:start":
            running[slug] = {"phase": cycle, "since": event.get("timestamp")}
        elif event.get("type") == "cycle:phase:end" and running.get(slug, {}).get("phase") == cycle:
            running.pop(slug, None)

    # Last finished phase per item, from the stream.
    reached: dict[str, dict] = {}
    for event in events:
        slug = item_id_of(event.get("slug") or "")
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

        # NOT `live`: that name already holds this item's live blockers a few lines up,
        # and shadowing it silently emptied every `blockers` list on the board.
        in_flight = running.get(iid)
        out_items.append({
            "id": iid,
            # The phase being worked on NOW, if any. It outranks `phase` for display:
            # where an item GOT TO matters less than what is happening to it.
            "running_phase": (in_flight or {}).get("phase"),
            "running_since": (in_flight or {}).get("since"),
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
        "lead": read_lead(lead_log, lead_marker),
        "running": sorted(running.keys()),
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

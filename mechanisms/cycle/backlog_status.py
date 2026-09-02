#!/usr/bin/env python3
"""Mechanize the BACKLOG.md status transitions — and the impediment edges.

Written because a measurement on 2026-08-30 found `planned` in the contract and in
zero items across every install: 22 `triaged`, 133 `shipped`, 11 `killed` in one
project, 3 `raw` and 2 `triaged` in another, and not one `planned` anywhere. The
cause was not discipline. Nothing wrote to BACKLOG.md at all — `detect_domains.py`
bootstraps it and `backlog_index.py` regenerates a marked block, and that is the
whole population of writers. Every transition was a human editing a line by hand,
so the middle one silently stopped happening and no check could see it: an item
that skipped `planned` is indistinguishable from one that has not reached it yet.

This module is the missing writer. It owns exactly one thing — the `status:` line
and the `blocked_by:` line of one item — and refuses any transition the contract
forbids.

## Impediment is a modifier, not a status

An item that discovers mid-flight that it needs another item does not LEAVE its
stage; it stops being able to advance from it. Modelling that as `status: blocked`
would destroy the very fact needed to resume — was it `triaged` or `planned` when
it stalled? So the stage stays, and the impediment is a separate field:

    status: planned
    blocked_by: B-100

The effective state (`blocked`) is DERIVED from the pair, which is what keeps it
honest: nothing can be blocked-on-paper while its blocker is already shipped,
because no one has to remember to clear a flag.

## One direction only

The edge is written on the blocked side and nowhere else. `blocks:` — the reverse
edge — is computed by the index, never typed. Storing both directions stores one
fact twice, and the two copies diverge the first time someone edits in a hurry.

Exit codes: 0 the write happened · 1 refused (illegal transition or bad edge)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LEGAL_STATUS = ("raw", "triaged", "planned", "shipped", "killed")

#: Where each status may go. `raw -> planned` is absent by contract: nothing reaches
#: a plan without passing DISCOVER's measurement. `planned -> triaged` is the
#: send-back — the pipeline returns an item whose plan did not survive review, and
#: it must land at the stage that produces plans, not at intake.
ALLOWED: dict[str, set[str]] = {
    "raw": {"triaged", "killed"},
    "triaged": {"planned", "killed"},
    "planned": {"triaged", "shipped", "killed"},
    "shipped": set(),
    "killed": set(),
}

OPEN_STATUS = {"raw", "triaged", "planned"}

ITEM_ID_RE = re.compile(r"\AB-\d{3,}\Z")
BLOCK_HEADER_RE = re.compile(r"^##\s+(B-\d+)\s+—\s+.*$", re.MULTILINE)
STATUS_LINE_RE = re.compile(r"^status:[ \t]*(\S*)[ \t]*$", re.MULTILINE)
BLOCKED_BY_LINE_RE = re.compile(r"^blocked_by:[ \t]*(.*)$", re.MULTILINE)
KILL_REASON_RE = re.compile(r"^kill_reason:[ \t]*(.+)$", re.MULTILINE)
_ID_IN_TEXT_RE = re.compile(r"\bB-\d{3,}\b")


class Refused(Exception):
    """A transition the contract does not allow. Carries the reason, not a code."""


def _blocks(content: str) -> dict[str, tuple[int, int]]:
    """Map every item id to the [start, end) span of its block body."""
    spans: dict[str, tuple[int, int]] = {}
    matches = list(BLOCK_HEADER_RE.finditer(content))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        spans[match.group(1)] = (match.end(), end)
    return spans


def _status_of(body: str) -> str | None:
    match = STATUS_LINE_RE.search(body)
    return match.group(1) if match else None


def declares_impediment(raw: str) -> bool:
    """True when a `blocked_by` value states an impediment at all.

    `none` and its spellings are accepted as "no impediment" because a human
    clearing a block by hand reaches for a word before reaching for an absent
    line, and rejecting that spelling would only leave a stale edge behind.
    """
    cleaned = raw.strip()
    return bool(cleaned) and cleaned.lower() not in {"none", "-", "none-yet", "nothing"}


def parse_blocked_by(raw: str) -> list[str]:
    """The item ids named anywhere in a `blocked_by` value.

    Ids are EXTRACTED rather than parsed from a fixed shape, because the field was
    already in use before it was specified. Measured on 2026-08-30: eight items in
    one install carried `blocked_by`, and only one named an item — the rest named a
    sponsor decision, a ratification, and a revocation in a hosting panel. Those are
    real impediments with no item to point at, and a parser demanding `B-NNN` would
    have called all seven malformed.

    So the value is prose that MAY contain ids. The ids become verifiable edges; the
    prose stays an impediment that no graph can resolve, which is honest — nothing
    in this repository can tell you whether a sponsor has decided.
    """
    if not declares_impediment(raw):
        return []
    return _ID_IN_TEXT_RE.findall(raw)


def blocked_by_of(body: str) -> list[str]:
    match = BLOCKED_BY_LINE_RE.search(body)
    return parse_blocked_by(match.group(1)) if match else []


def blocked_by_raw(body: str) -> str:
    match = BLOCKED_BY_LINE_RE.search(body)
    return match.group(1).strip() if match else ""


def effective_state(status: str, blockers: list[str], statuses: dict[str, str]) -> str:
    """The state a reader should see — `blocked` only while a blocker is still open.

    A blocker that shipped or was killed stops blocking the moment its own status
    says so. That is the whole reason the edge is not a status: resolution needs no
    second edit, so the registry cannot claim an impediment that no longer exists.
    """
    if status not in OPEN_STATUS:
        return status
    if any(statuses.get(b) in OPEN_STATUS for b in blockers):
        return "blocked"
    return status


def effective_state_of(body: str, statuses: dict[str, str]) -> str:
    """`effective_state` for a whole block body, prose impediments included.

    An impediment naming no item — "awaiting the sponsor's decision" — cannot be
    resolved by reading another item's status, so it holds until a human removes the
    line. That is a weaker guarantee than an id edge, and deliberately so: the
    alternative is pretending the registry knows something it does not.
    """
    status = _status_of(body) or ""
    raw = blocked_by_raw(body)
    if status not in OPEN_STATUS or not declares_impediment(raw):
        return status
    ids = parse_blocked_by(raw)
    if not ids:
        return "blocked"
    return effective_state(status, ids, statuses)


def _write_field(body: str, key: str, value: str, after: str) -> str:
    """Set `key: value` in a block body, inserting after `after` when absent."""
    line_re = re.compile(rf"^{key}:[ \t]*.*$", re.MULTILINE)
    if line_re.search(body):
        return line_re.sub(f"{key}: {value}", body, count=1)
    anchor = re.compile(rf"^({after}:[ \t]*.*)$", re.MULTILINE)
    if anchor.search(body):
        return anchor.sub(rf"\1\n{key}: {value}", body, count=1)
    return body.rstrip("\n") + f"\n{key}: {value}\n"


def _drop_field(body: str, key: str) -> str:
    return re.sub(rf"^{key}:[ \t]*.*\n", "", body, count=1, flags=re.MULTILINE)


def advance(content: str, item_id: str, to: str, kill_reason: str = "") -> str:
    """Move one item to `to`, refusing anything the contract forbids."""
    if to not in LEGAL_STATUS:
        raise Refused(f"{to!r} is not a status; the set is {', '.join(LEGAL_STATUS)}")
    spans = _blocks(content)
    if item_id not in spans:
        raise Refused(f"{item_id} is not in this backlog")

    start, end = spans[item_id]
    body = content[start:end]
    current = _status_of(body)
    if current is None:
        raise Refused(f"{item_id} carries no status line; fix the block first")
    if current == to:
        raise Refused(f"{item_id} is already {to}")
    if to not in ALLOWED.get(current, set()):
        allowed = ", ".join(sorted(ALLOWED.get(current, set()))) or "nothing — it is terminal"
        raise Refused(f"{item_id}: {current} -> {to} is not a legal transition; from {current} it may go to {allowed}")

    if to == "killed":
        if not kill_reason and not KILL_REASON_RE.search(body):
            raise Refused(f"{item_id}: killing an item requires --kill-reason (gate G-K)")
        if kill_reason:
            body = _write_field(body, "kill_reason", kill_reason, after="status")

    # An item cannot ship while something still blocks it. The check reads the
    # blockers' own status rather than a flag, so it cannot be fooled by a stale edge.
    if to == "shipped":
        statuses = {i: _status_of(content[s:e]) or "" for i, (s, e) in spans.items()}
        raw = blocked_by_raw(body)
        ids = parse_blocked_by(raw)
        still_open = [b for b in ids if statuses.get(b) in OPEN_STATUS]
        if still_open:
            raise Refused(f"{item_id} cannot ship while blocked by {', '.join(still_open)}")
        if declares_impediment(raw) and not ids:
            raise Refused(f"{item_id} still declares an impediment ({raw[:60]}); clear it or ship after it resolves")

    body = STATUS_LINE_RE.sub(f"status: {to}", body, count=1)
    return content[:start] + body + content[end:]


def block(content: str, item_id: str, blockers: list[str], note: str = "") -> str:
    """Record that `item_id` cannot advance until `blockers` (or `note`) resolve."""
    if not blockers and not note.strip():
        raise Refused("an impediment needs either an item id or a stated reason")
    spans = _blocks(content)
    if item_id not in spans:
        raise Refused(f"{item_id} is not in this backlog")
    for b in blockers:
        if not ITEM_ID_RE.match(b):
            raise Refused(f"{b!r} is not an item id (expected B-NNN)")
        if b == item_id:
            raise Refused(f"{item_id} cannot block itself")
        if b not in spans:
            raise Refused(f"{b} is not in this backlog — file the item before pointing at it")

    start, end = spans[item_id]
    merged = sorted(set(blocked_by_of(content[start:end])) | set(blockers))

    # A cycle is a deadlock: every item in it waits for another that waits for it,
    # and none can ever ship. Refusing at write time is the only cheap moment — once
    # written, the ring has to be found by a graph walk over the whole registry.
    edges = {i: blocked_by_of(content[s:e]) for i, (s, e) in spans.items()}
    edges[item_id] = merged
    cycle = _find_cycle(edges, item_id)
    if cycle:
        raise Refused(f"that edge closes a cycle: {' -> '.join(cycle)}")

    value = ", ".join(merged)
    if note.strip():
        value = f"{value} — {note.strip()}" if value else note.strip()
    body = _write_field(content[start:end], "blocked_by", value, after="status")
    return content[:start] + body + content[end:]


def unblock(content: str, item_id: str, blockers: list[str] | None = None) -> str:
    """Drop some (or every) impediment edge from `item_id`."""
    spans = _blocks(content)
    if item_id not in spans:
        raise Refused(f"{item_id} is not in this backlog")
    start, end = spans[item_id]
    body = content[start:end]
    current = blocked_by_of(body)
    if not current:
        raise Refused(f"{item_id} is not blocked")
    remaining = [b for b in current if b not in blockers] if blockers else []
    if blockers and remaining == current:
        raise Refused(f"{item_id} is not blocked by {', '.join(blockers)}")
    body = _write_field(body, "blocked_by", ", ".join(remaining), after="status") if remaining else _drop_field(body, "blocked_by")
    return content[:start] + body + content[end:]


def _find_cycle(edges: dict[str, list[str]], start: str) -> list[str] | None:
    """Return the ring reachable from `start`, or None. Depth-first, path-carrying."""
    stack: list[tuple[str, list[str]]] = [(start, [start])]
    seen: set[str] = set()
    while stack:
        node, path = stack.pop()
        for nxt in edges.get(node, []):
            if nxt == start:
                return path + [nxt]
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, path + [nxt]))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Move a BACKLOG.md item, or record an impediment.")
    parser.add_argument("backlog", type=Path)
    parser.add_argument("item", help="the item id, B-NNN")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--to", choices=LEGAL_STATUS, help="advance the item to this status")
    group.add_argument("--block-on", nargs="*", metavar="B-NNN", help="record that these items block it")
    group.add_argument("--unblock", nargs="*", metavar="B-NNN", help="clear some, or with no ids every, impediment")
    parser.add_argument("--because", default="", help="state a non-item impediment (a decision, an external action)")
    parser.add_argument("--kill-reason", default="", help="required when --to killed")
    parser.add_argument("--dry-run", action="store_true", help="print the new block, write nothing")
    args = parser.parse_args()

    if not args.backlog.is_file():
        print(f"REFUSED: {args.backlog} does not exist", file=sys.stderr)
        return 1
    content = args.backlog.read_text(encoding="utf-8")

    try:
        if args.to:
            updated = advance(content, args.item, args.to, args.kill_reason)
            action = f"{args.item} -> {args.to}"
        elif args.block_on is not None:
            updated = block(content, args.item, args.block_on, args.because)
            action = f"{args.item} blocked by {', '.join(args.block_on) or args.because}"
        else:
            updated = unblock(content, args.item, args.unblock or None)
            action = f"{args.item} unblocked"
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        start, end = _blocks(updated)[args.item]
        print(updated[start:end].strip())
        return 0

    args.backlog.write_text(updated, encoding="utf-8")
    print(f"OK: {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

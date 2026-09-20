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

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break

# Post-bootstrap, like the loop above requires: the kit ships as loose scripts.
from squad import backlog as _shared_backlog  # noqa: E402 — post-bootstrap import
from squad import shared_file  # noqa: E402 — post-bootstrap import

LEGAL_STATUS = ("raw", "triaged", "approved", "planned", "shipped", "killed")

#: Where each status may go.
#:
#: `raw -> planned` and `triaged -> planned` are absent by contract: nothing reaches a
#: plan without BOTH passing DISCOVER's measurement AND being approved. Those are two
#: different questions — "is the hunch real?" and "are we doing it?" — and collapsing
#: them is what let one registry hold 174 items and exactly 2 `planned`.
#:
#: Two send-backs, and they land in different places because they mean different things.
#: `approved -> triaged` withdraws the decision itself, before any plan existed.
#: `planned -> approved` returns a plan that did not survive review: the decision to do
#: the work still stands, only the plan failed, so it lands at the stage that produces
#: plans rather than at the stage that decides.
ALLOWED: dict[str, set[str]] = {
    "raw": {"triaged", "killed"},
    "triaged": {"approved", "raw", "killed"},
    "approved": {"planned", "triaged", "killed"},
    "planned": {"approved", "shipped", "killed"},
    "shipped": set(),
    "killed": set(),
}

OPEN_STATUS = {"raw", "triaged", "approved", "planned"}

#: The open chain in order. A move to an EARLIER entry is a withdrawal, which
#: `cycle-maintenance.md § Rollback` says is never silent: "An item advanced in error
#: is moved back with a note recording the advance and why it was withdrawn."
#:
#: The rule was unimplemented on the two backward moves the table already allowed.
#: Measured 2026-09-18: `approved -> triaged` was accepted and left the block reading
#: `status: triaged` and nothing else — a fresh-looking item, the exact outcome the
#: rule names as the thing to avoid. An item could be walked back through the whole
#: chain leaving no trace, while `triaged -> raw`, the same move one step down, was
#: refused outright.
#:
#: Ordered rather than enumerated as pairs: a list of legal rollbacks is a list
#: somebody extends the table without updating, which is how this half arrived.
OPEN_CHAIN = ("raw", "triaged", "approved", "planned")


def is_withdrawal(current: str, to: str) -> bool:
    """Does this move walk an item BACK down the open chain?"""
    if current not in OPEN_CHAIN or to not in OPEN_CHAIN:
        return False
    return OPEN_CHAIN.index(to) < OPEN_CHAIN.index(current)

#: Past this line an item stopped being a hypothesis. `killed` from here is a decision
#: being reversed rather than a measurement coming back negative, and `--kill-reason`
#: is held to a higher bar: it must name who reversed it and what changed. A reason
#: that only restates the evidence is what a hypothesis gets; a commitment gets a
#: person and a change of mind.
COMMITTED_STATUS = {"approved", "planned"}

#: Does a kill reason name a decision being reversed, rather than only a measurement?
#:
#: Deliberately shallow: it looks for a verb of reversal and for someone to attribute it
#: to. A deeper check would be a judgement, and a mechanism that judges prose is a
#: mechanism that refuses correct reasons it did not expect. This asks only that the
#: sentence be ABOUT a reversal — whether the reversal is right is the reader's call.
_REVERSAL_VERBS = ("reversed", "withdrew", "withdrawn", "cancelled", "canceled",
                   "rescinded", "revogad", "revertid", "cancelad", "retirad")


def _names_a_reversal(reason: str) -> bool:
    lowered = reason.lower()
    return any(verb in lowered for verb in _REVERSAL_VERBS)


#: Imported, not compiled. This module and the structure check each carried one
#: and disagreed about the separator, so an item could be approved in the brief
#: and invisible to the only thing allowed to write its status.
ITEM_ID_RE = _shared_backlog.ITEM_ID_RE
BLOCK_HEADER_RE = _shared_backlog.BLOCK_RE
STATUS_LINE_RE = re.compile(r"^status:[ \t]*(\S*)[ \t]*$", re.MULTILINE)
BLOCKED_BY_LINE_RE = re.compile(r"^blocked_by:[ \t]*(.*)$", re.MULTILINE)
KILL_REASON_RE = re.compile(r"^kill_reason:[ \t]*(.+)$", re.MULTILINE)
WITHDRAW_REASON_RE = re.compile(r"^withdraw_reason:[ \t]*(.+)$", re.MULTILINE)
_ID_IN_TEXT_RE = _shared_backlog.ID_IN_TEXT_RE


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


def _absent_reason(content: str, item_id: str) -> str:
    """Why is `item_id` not among the blocks — and is that even the true reason?

    `REFUSED: B-14 is not in this backlog` was printed about a block sitting in the
    file, whose header this parser did not recognise. The reader goes looking for a
    missing item and it is right there. Since 2026-09-20 one parser serves every
    reader, so the mismatch that produced that message is gone — and the message
    stays honest about which of the two it is, because a header can still be
    malformed in a way no pattern should silently accept.
    """
    if re.search(rf"^##.*{re.escape(item_id)}\b", content, re.MULTILINE):
        return (f"{item_id} has a heading in this backlog that does not parse as an "
                f"item block. The shape is `## {item_id} — Title`; the separator may "
                f"be an em dash, an en dash or a hyphen, and the id needs "
                f"{_shared_backlog.MIN_ID_DIGITS} digits")
    return f"{item_id} is not in this backlog"


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


def carries_prose(raw: str) -> bool:
    """Does the value say anything beyond a list of ids?

    Mirrors `check_backlog_structure.carries_prose` — one field, three readers,
    one meaning. The duplication is deliberate for the reason `live_blockers`
    states, and pinned by `test_blocked_by_readers_agree.py`.
    """
    return bool(_ID_IN_TEXT_RE.sub("", raw).strip(" ,—-"))


def without_ids(raw: str, ids: list[str]) -> str:
    """`raw` with `ids` removed, and whatever a human wrote left standing.

    The field is prose that MAY contain ids (`parse_blocked_by`), so clearing an
    id cannot be done by rebuilding the value from the ids that remain — that
    silently discards the reason beside them. `advance` refuses to ship while the
    line says anything at all, so a reason dropped here turns a refused ship into
    an allowed one with nothing recording that a barrier was removed.

    Returns `""` when nothing but separators is left, which is the caller's
    signal to drop the field entirely.
    """
    remaining = raw
    for item_id in ids:
        remaining = re.sub(rf"\b{re.escape(item_id)}\b", "", remaining)
    remaining = re.sub(r"\s+", " ", remaining)
    # Separators orphaned by the removal: a leading comma from `B-002, B-003`,
    # a dangling em dash from `B-002 — the sponsor has to sign`.
    remaining = re.sub(r"(?:^|(?<=\s)),", " ", remaining)
    return remaining.strip(" ,—-")


def live_blockers(raw: str, own_id: str, statuses: dict[str, str]) -> list[str] | None:
    """The writer's answer to "may `own_id` advance to shipped, given `raw`?"

    Same shape as `select_backlog_item.live_blockers` and by design: the writer
    must refuse a ship on exactly the state the selector calls blocked. A
    divergence here is either a deadlock — the writer refuses what the selector
    would clear, so the item cannot close — or a silent ship past a decision a
    person still owes, when the selector says blocked and the writer permits it.

    Return values carry the same three meanings:
      - `None`  — nothing blocks; the writer may ship
      - `[]`    — blocked with no id to name (a stated reason), writer must refuse
      - `[...]` — blocked by these still-open ids, writer must refuse

    The self-mention filter and the `carries_prose` distinction are duplicated
    on purpose. The writer does not import the gate any more than the gate may
    import the writer, and the audit on 2026-09-03 found this was the third
    reader missing both — a `blocked_by` value whose prose named the item
    itself made `advance` refuse the ship because the item blocked itself, and
    the item stayed open precisely because the ship was refused. The fix that
    already lived in the selector and the gate finally travelled here.
    """
    if not declares_impediment(raw):
        return None
    ids = parse_blocked_by(raw)
    # An item cannot block itself. `blocked_by` is prose, and a sentence that
    # names the item mentioning itself is normal — "Vide report B-060" — not a
    # self-block. Same reasoning as `select_backlog_item.py:141` and
    # `check_backlog_structure.impediment_edges`.
    ids = [b for b in ids if b != own_id]
    if not ids:
        return []
    open_ids = [b for b in ids if statuses.get(b, "") in OPEN_STATUS]
    if open_ids:
        return open_ids
    # Every named id has closed, but a stated reason outlives its id edge: the
    # ids in it are context, the reason is the barrier, and nothing in this
    # repository can tell whether the reason is discharged. Same rule the gate
    # holds for `stale_block` and the selector eventually learned.
    return [] if carries_prose(raw) else None


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


def advance(content: str, item_id: str, to: str, kill_reason: str = "",
            approved_by: str = "", withdraw_reason: str = "") -> str:
    """Move one item to `to`, refusing anything the contract forbids.

    `approved_by` is written when the move is to `approved`, and it is the only way to
    tell the two kinds of commitment apart later. `human/<name>` says a person read the
    item and committed to it; `system/autonomous-sweep` says the loop filed it under a
    standing authorisation. They are not worth the same, and a registry where everything
    is `system/…` is one nobody has read — a legitimate state to be in, and an
    illegitimate one to be in unknowingly.

    A bare `approved` with no attribution predates the field. It is not evidence that a
    person decided, and `check_chain_preconditions.py` reports it as such.
    """
    if to not in LEGAL_STATUS:
        raise Refused(f"{to!r} is not a status; the set is {', '.join(LEGAL_STATUS)}")
    spans = _blocks(content)
    if item_id not in spans:
        raise Refused(_absent_reason(content, item_id))

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

    if is_withdrawal(current, to):
        # `cycle-maintenance.md § Rollback` requires the note, and held the same bar
        # `--kill-reason` holds a committed item to — for the same reason, stated there:
        # "a reason that only restates the evidence is what a hypothesis gets; a
        # commitment gets a person and a change of mind." Somebody decided this item
        # would advance; walking it back reverses that decision, and what the next reader
        # cannot reconstruct is WHO changed their mind, never what the evidence said.
        reason = withdraw_reason or (WITHDRAW_REASON_RE.search(body).group(1)
                                     if WITHDRAW_REASON_RE.search(body) else "")
        if not reason:
            raise Refused(
                f"{item_id}: {current} -> {to} walks the item back, which requires "
                f"--withdraw-reason. A rollback with no note leaves a fresh-looking "
                f"`{to}` item, and an item whose `{current}` was withdrawn carries "
                f"information a fresh-looking one does not.")
        if not _names_a_reversal(reason):
            raise Refused(
                f"{item_id}: --withdraw-reason must name WHO withdrew the `{current}` "
                f"call and WHAT changed — not only what the evidence showed. Write it "
                f"as e.g. 'reversed by <who> <when>: <what changed>'.")
        # `withdrawn_from` records the advance itself, which the status line cannot:
        # after the move the block says `{to}` and nothing says it was ever `{current}`.
        body = _write_field(body, "withdrawn_from", current, after="status")
        body = _write_field(body, "withdraw_reason", reason, after="status")

    if to == "killed":
        if not kill_reason and not KILL_REASON_RE.search(body):
            raise Refused(f"{item_id}: killing an item requires --kill-reason (gate G-K)")

        # Killing a hypothesis and killing a commitment are different acts, and the
        # reason each needs is different. Before approval the item was a question and
        # the measurement answered it — "the leak does not reproduce" is the whole
        # story. After approval somebody with the authority decided the work would be
        # done, so ending it reverses a decision rather than reporting a result, and a
        # reason that only restates evidence does not name what is being undone.
        #
        # The registry's own doctrine used to say an item "is a hypothesis, not a
        # commitment" without qualification, which made these two acts cost the same.
        if current in COMMITTED_STATUS:
            reason = kill_reason or (KILL_REASON_RE.search(body).group(1) if KILL_REASON_RE.search(body) else "")
            if not _names_a_reversal(reason):
                raise Refused(
                    f"{item_id} is {current}, which is a commitment rather than a "
                    f"hypothesis: someone decided this would be done. Killing it "
                    f"reverses that decision, so --kill-reason must name WHO reversed "
                    f"it and WHAT changed — not only what the evidence showed. "
                    f"Write it as e.g. 'reversed by <who> <when>: <what changed>'."
                )

        if kill_reason:
            body = _write_field(body, "kill_reason", kill_reason, after="status")

    if to == "approved":
        # Demanded on the move that MAKES the decision, and only there.
        #
        # `triaged -> approved` is somebody committing to the work, and
        # `cycle-backlog.md` requires the attribution from that point on — it calls a
        # bare `approved` "not evidence that a person decided", which is exactly what
        # this function accepted until 2026-09-20 while `cycle-maintenance.md`
        # prescribed the command without the flag.
        #
        # `planned -> approved` is the send-back, and demanding it there would be
        # wrong: `test_planned_is_sent_back_to_approved_not_to_triaged` states the
        # reason — "a plan that failed review did not un-decide the work… someone
        # would have to approve the same item twice for one bad draft." The first
        # cut of this refusal did exactly that and four tests said so. An item that
        # reaches the send-back carrying no attribution is inherited debt, and
        # `check_backlog_structure.approval_unattributed` is what reports it.
        if current == "triaged" and not approved_by.strip():
            raise Refused(
                "--approved-by is required to approve. `human/<name>` if a person read "
                "the item and committed to it, `system/autonomous-sweep` if the loop "
                "filed it under a standing authorisation. The two are not worth the "
                "same, and a reader must be able to tell them apart without opening "
                "another file")
        body = _write_field(body, "approved_by", approved_by, after="status")

    # An item cannot ship while something still blocks it. `live_blockers`
    # answers the same question the selector and the gate already answer, so
    # a rule fixed in one copy cannot go stale in the third — the audit on
    # 2026-09-03 named the two defects this route used to carry: no
    # self-mention filter (deadlocking the item on its own prose) and no
    # `carries_prose` distinction (silently shipping past a stated reason
    # whose id edges had all closed).
    if to == "shipped":
        statuses = {i: _status_of(content[s:e]) or "" for i, (s, e) in spans.items()}
        raw = blocked_by_raw(body)
        blockers = live_blockers(raw, item_id, statuses)
        if blockers is not None:
            if blockers:
                raise Refused(f"{item_id} cannot ship while blocked by {', '.join(blockers)}")
            raise Refused(f"{item_id} still declares an impediment ({raw[:60]}); clear it or ship after it resolves")

    body = STATUS_LINE_RE.sub(f"status: {to}", body, count=1)
    return content[:start] + body + content[end:]


def block(content: str, item_id: str, blockers: list[str], note: str = "") -> str:
    """Record that `item_id` cannot advance until `blockers` (or `note`) resolve."""
    if not blockers and not note.strip():
        raise Refused("an impediment needs either an item id or a stated reason")
    spans = _blocks(content)
    if item_id not in spans:
        raise Refused(_absent_reason(content, item_id))
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
        raise Refused(_absent_reason(content, item_id))
    start, end = spans[item_id]
    body = content[start:end]
    current = blocked_by_of(body)
    raw = blocked_by_raw(body)

    #: A bare `--unblock` means "clear whatever is there", and what is there may be
    #: prose. The two readers of this field disagreed about what counts: `advance`
    #: asks `blocked_by_raw` and refuses to ship while the line says anything at
    #: all, while this function asked `blocked_by_of`, which extracts item ids, and
    #: refused with "is not blocked" when the line held a decision instead of an
    #: id. An item impeded by prose — the shape `--because` exists to write — could
    #: therefore neither ship nor be cleared, and hand-editing the registry is
    #: precisely what this module exists to prevent, so the deadlock had no
    #: legitimate exit.
    #:
    #: Measured 2026-09-05: B-168 in a consumer declared "fix estrutural pertence
    #: ao repo do kit", the fix landed in the kit and was verified in that
    #: consumer, and the mechanism could not move the item.
    if not current and not blockers and declares_impediment(raw):
        return content[:start] + _drop_field(body, "blocked_by") + content[end:]

    if not current:
        raise Refused(f"{item_id} is not blocked")
    remaining = [b for b in current if b not in blockers] if blockers else []
    if blockers and remaining == current:
        raise Refused(f"{item_id} is not blocked by {', '.join(blockers)}")

    # Rebuilt from the RAW value, never from the surviving ids. `", ".join(remaining)`
    # was the whole defect: an item blocked by `B-002 — awaiting the sponsor` lost the
    # sponsor along with B-002, and the ship `advance` had just refused went through.
    # A bare `--unblock` still clears everything, which is what it means.
    value = without_ids(raw, blockers) if blockers else ""
    body = (_write_field(body, "blocked_by", value, after="status") if value
            else _drop_field(body, "blocked_by"))
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
    parser.add_argument("--withdraw-reason", default="",
                        help="required when --to walks the item BACK down the open "
                             "chain; must name who withdrew the advance and what changed")
    parser.add_argument("--approved-by", default="", metavar="WHO",
                        help="who made the commitment, written when --to approved: "
                             "`human/<name>` or `system/autonomous-sweep`. A bare "
                             "`approved` is not evidence that a person decided")
    parser.add_argument("--dry-run", action="store_true", help="print the new block, write nothing")
    args = parser.parse_args()

    if not args.backlog.is_file():
        print(f"REFUSED: {args.backlog} does not exist", file=sys.stderr)
        return 1

    # The read and the write below are ONE transaction. They were not: the file was read
    # at the top, transformed, and `write_text` put the whole thing back — no lock across
    # the span and no atomic replace at the end. Three modules in `mechanisms/cycle` and
    # one in `mechanisms/fleet` rewrite this same registry, and the fleet runs lanes in
    # parallel by design, so two writers reading the same bytes silently lost one of the
    # two transitions. `squad/shared_file.py` carries the measurement.
    try:
        lock = shared_file.locked(args.backlog)
        lock.__enter__()
    except TimeoutError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    try:
        return _apply_under_lock(args)
    finally:
        lock.__exit__(None, None, None)


def _apply_under_lock(args: argparse.Namespace) -> int:
    content = args.backlog.read_text(encoding="utf-8")

    try:
        if args.to:
            updated = advance(content, args.item, args.to, args.kill_reason,
                              args.approved_by,
                              withdraw_reason=args.withdraw_reason)
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

    shared_file.write_atomic(args.backlog, updated)
    print(f"OK: {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

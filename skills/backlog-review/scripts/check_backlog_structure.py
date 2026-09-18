#!/usr/bin/env python3
"""Deterministic structural review of BACKLOG.md.

Sibling of the retired `check_roadmap_structure.py`. Written fresh rather than ported:
a roadmap is a finite, ordered, dependency-linked scope, and a backlog is none of those.
The M0-M8 cap and ordering checks have no meaning over independent items, so carrying
them across would have produced checks that always pass.

Cycle detection was dropped for the same reason and came back on 2026-08-30, when
`blocked_by` gave items edges. Backlog items are no longer independent: B-014 may wait
on B-100, and a ring of those is a deadlock in which nothing can ever ship. The check
returned because the premise that retired it stopped being true — not because the
original reasoning was wrong.

What it checks instead — the ways a maintenance registry actually rots:

  DETERMINISTIC (a machine can be sure)
    duplicate_id            two blocks share a B-NNN — the audit trail is broken
    duplicate_field         one field written twice in a block, with two values
    missing_field           a required field absent
    illegal_status          a status outside the declared set
    killed_without_reason   killed with no kill_reason (gate G-K, after the fact)
    status_contradicts_body  the block's prose declares it closed and its status says open
    triaged_without_evidence  triaged but evidence is still none-yet
    raw_with_evidence       raw but carrying evidence — status never advanced
    unroutable_repo         repo in no domain, on an OPEN item (gate G1)
    unroutable_repo_closed  same, on a shipped or killed one — history, not an impediment
    broken_route            domain exists but its specialist file does not
    invalid_mode            suggested_mode outside the four
    renumbered              ids not monotonic — a reused id destroys traceability
    blocker_missing         blocked_by points at an id no block defines
    blocker_cycle           a ring of impediments — every item waits, none can ship
    self_block              an item declaring itself its own blocker
    stale_block             every blocker closed, the edge still written
    closed_but_blocked      shipped while an open blocker is still declared
    lineage_missing         supersedes/regression_of names an undefined id, or the item itself
    lineage_wrong_status    the named ancestor exists but is not in the terminal state the field implies
    index_stale             the rendered index no longer matches the blocks it summarises

  HEURISTIC (a reader decides; labelled as such in every finding)
    vague_dod               a DoD bullet nothing could falsify
    thin_dod                zero DoD bullets
    stale_raw               raw for longer than the staleness window
    possible_duplicate      two open items whose titles overlap heavily

Every finding declares `kind` (deterministic | heuristic). The verdict is DERIVED from
the findings, never asserted — the same discipline the confidence scorers follow.

Exit codes: 0 SHIPPABLE / SHIPPABLE_WITH_CAVEATS · 1 INVALID · 3 NEEDS_REVISION
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

#: Statuses from which an item does not move again.
TERMINAL_STATUSES = frozenset({"shipped", "killed"})

#: A block saying, in its own words, that the work is done. Deliberately narrow: it matches the
#: remedy being NAMED (`closed in code`, `closed by deletion`), not the bare word "closed", which
#: appears in ordinary prose about closing an endpoint or a connection.
_DECLARES_CLOSED_RE = re.compile(
    r"\*{0,2}closed\s+(?:in\s+code|by\s+deletion|by\s+removal)\*{0,2}", re.IGNORECASE
)

BLOCK_RE = re.compile(r"^##\s+(B-\d+)\s+—\s+(.+?)\s*(?:\[( |x)\])?\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^([a-z_]+):\s*(.*)$", re.MULTILINE)
DOD_BULLET_RE = re.compile(r"^\s*-\s+(.+)$", re.MULTILINE)
REGISTERED_RE = re.compile(r"Registrado\s+(\d{4}-\d{2}-\d{2})|registered\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)

REQUIRED_FIELDS = ("domain", "repo", "suggested_mode", "source", "evidence", "why_now", "status")
LEGAL_STATUS = {"raw", "triaged", "approved", "planned", "shipped", "killed"}
LEGAL_MODES = {"review", "live-test", "bug", "evolve"}
OPEN_STATUS = {"raw", "triaged", "approved", "planned"}

# A DoD bullet built only from these cannot fail, so it cannot close an item.
VAGUE_TERMS = {
    "improve", "improved", "better", "faster", "fast", "scalable", "robust", "clean",
    "cleanup", "clean up", "optimize", "optimise", "enhance", "polish", "reliable",
    "performant", "best practices", "as needed", "etc", "and so on", "properly",
    "correctly", "appropriately", "melhorar", "melhor", "mais rápido", "adequado",
}
STALE_RAW_DAYS = 90


@dataclass
class Finding:
    check: str
    kind: str  # deterministic | heuristic
    severity: str  # blocker | major | minor
    item: str
    message: str


@dataclass
class Item:
    item_id: str
    title: str
    fields: dict[str, str] = field(default_factory=dict)
    dod: list[str] = field(default_factory=list)
    registered_on: date | None = None
    line: int = 0
    #: Fields declared more than once in the block. `fields` keeps the LAST value, so without
    #: this the earlier ones vanish and nothing says the block held two answers.
    duplicated: dict[str, list[str]] = field(default_factory=dict)
    #: The block's prose, kept because a block can CONTRADICT its own status field and the fields
    #: alone cannot see it. See `status_contradicts_body`.
    body: str = ""


def _parse_items(content: str) -> list[Item]:
    items: list[Item] = []
    matches = list(BLOCK_RE.finditer(content))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end]

        item = Item(
            item_id=match.group(1),
            title=match.group(2).strip(),
            body=body,
            line=content[: match.start()].count("\n") + 1,
        )
        seen_values: dict[str, list[str]] = {}
        for fmatch in FIELD_RE.finditer(body):
            key, value = fmatch.group(1), fmatch.group(2).strip()
            item.fields[key] = value
            seen_values.setdefault(key, []).append(value)
        item.duplicated = {k: v for k, v in seen_values.items() if len(v) > 1}

        dod_match = re.search(r"^dod:\s*$(.*?)(?=^[a-z_]+:|\Z)", body, re.MULTILINE | re.DOTALL)
        if dod_match:
            item.dod = [b.strip() for b in DOD_BULLET_RE.findall(dod_match.group(1)) if b.strip()]

        reg = REGISTERED_RE.search(body)
        if reg:
            raw = reg.group(1) or reg.group(2)
            try:
                item.registered_on = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                pass
        items.append(item)
    return items


def _is_vague(bullet: str) -> bool:
    """True when a bullet carries no falsifiable content.

    A bullet with a number, a comparison or a concrete artifact is treated as
    falsifiable even if it also contains a vague word — "p95 below 800ms" is a criterion
    that happens to mention speed, and flagging it would train people to ignore the check.
    """
    lowered = bullet.lower()
    if re.search(r"\d", lowered) or "`" in bullet:
        return False
    return any(term in lowered for term in VAGUE_TERMS)


def _title_overlap(a: str, b: str) -> float:
    wa = {w for w in re.findall(r"\w+", a.lower()) if len(w) > 3}
    wb = {w for w in re.findall(r"\w+", b.lower()) if len(w) > 3}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


#: Why the routing check did not run, set by `_routing` and read by `main`.
#:
#: A LIST, not a bool: `_routing` returned bare `None` for three different facts — the
#: tool could not be imported, no table was found, a table was found and would not parse
#: — and `main` printed "routing table unreadable" for all three. An operator who can see
#: the table, valid, in `.claude/rules/` reads that as a false alarm, and reads the next
#: real one the same way. The check that could not measure said so in terms too vague to
#: act on, which costs the same as not saying it.
_routing_gap: list[str] = []

#: The directory the routing table was read from, or None. The table's `agents/…` paths
#: are relative to THIS, not to wherever the registry happens to sit: a table at
#: `<root>/.claude/rules/` names `<root>/.claude/agents/`. Resolving against the
#: registry's own directory reported every domain of a nested `apps/<app>/BACKLOG.md` as
#: a broken route, on specialist files that were on disk (kit#138).
_routing_home: list[Path] = []


def _routing(backlog_dir: Path) -> dict[str, dict] | None:
    """Repos the routing table knows. None when the table cannot be read.

    None is not an empty set: an unreadable table means we cannot judge routing, and
    reporting every repo as unroutable from missing data would assert a violation the
    evidence does not support.

    `route_domain` is located relative to THIS FILE, not to the backlog. In real use the
    registry sits at the umbrella root while the tooling lives under `.claude/scripts/`,
    so resolving the importer against the backlog's directory finds nothing — and a bare
    `except Exception` around the import would swallow that into a silent None. The check
    would then never run while the report looked healthy.
    """
    # Cleared per call. These are module-level lists, and left accumulating they carry
    # one run's answer into the next: a suite where an earlier case had the specialist on
    # disk made a later case find it under the earlier case's tmpdir, and the missing-file
    # blocker silently stopped firing. Caught by `test_backlog_broken_route` the first
    # time the whole suite ran — a defect introduced by the fix above it.
    _routing_gap.clear()
    _routing_home.clear()

    _add_cycle_tooling_to_path()
    try:
        from route_domain import (
            _routing_table_path,
            parse_routing_table,
        )
    except ImportError:
        # The routing tool is genuinely unavailable — report inability, never a violation.
        _routing_gap.append("`route_domain` could not be imported, so no routing tool "
                            "was available to ask")
        return None

    # Walk UP. `_routing_table_path` looks beside the directory it is given and does not
    # climb, so a monorepo whose registry sits in `apps/<app>/BACKLOG.md` while `.claude/`
    # is at the root had its routing silently unchecked — every run, on a table present
    # and valid two directories above. The nearer table still wins: a sub-project with
    # its own routing is answering a different question than the umbrella's, and this
    # stops at the first one it finds.
    rule = None
    for candidate_root in (backlog_dir, *backlog_dir.parents):
        rule = _routing_table_path(candidate_root)
        if rule is not None:
            break
        if (candidate_root / ".git").exists():
            # The repository boundary. Climbing past it would read a table belonging to
            # whatever tree happens to contain this one on this machine.
            break
    if rule is None:
        _routing_gap.append(
            f"no `domain-routing.txt` found in `.squad/`, `rules/` or `.claude/rules/` "
            f"from {backlog_dir} up to the repository root")
        return None
    # `rules/domain-routing.txt` means the tree is its parent's parent; `.squad/` and any
    # other location means the parent itself. The table's `agents/…` hang off that tree.
    _routing_home.append(
        rule.parent.parent if rule.parent.name == "rules" else rule.parent)
    try:
        table = parse_routing_table(rule)
    except ValueError as exc:
        _routing_gap.append(f"{rule} could not be parsed: {exc}")
        # A malformed table is a real problem, but it is `backlog-review`'s job to review
        # items, not the rule. Decline to judge routing rather than blame every item.
        return None
    return table


_ID_IN_TEXT_RE = re.compile(r"\bB-\d{3,}\b")
_NO_IMPEDIMENT = {"none", "-", "none-yet", "nothing"}

#: The two lineage edges, and the terminal status each one asserts about its target.
#:
#: `check_intake_gates.ACTION_BY_STATUS` produces them: a dedup hit on a `killed` item
#: prescribes `supersedes`, on a `shipped` item `regression_of`. So each field is a
#: CLAIM about the state its target is in, and a claim is checkable. Until kit#55 both
#: were written and never read — the kit's own `mentioned-not-used` pattern, applied to
#: a schema field.
#:
#: Deliberately no cycle check: a lineage edge points only at a terminal item, and a
#: terminal item is not re-opened, so a ring is unreachable. G7 has no analogue here.
LINEAGE_EDGES = {
    "supersedes": "killed",
    "regression_of": "shipped",
}


def _add_cycle_tooling_to_path() -> None:
    """Make `mechanisms/cycle/` importable. Located relative to THIS FILE.

    In real use the registry sits at the umbrella root while the tooling lives under
    `.claude/scripts/`, so resolving against the backlog's directory finds nothing.
    """
    tooling = Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))


def declares_impediment(raw: str) -> bool:
    cleaned = raw.strip()
    return bool(cleaned) and cleaned.lower() not in _NO_IMPEDIMENT


def parse_blocked_by(raw: str) -> list[str]:
    """The item ids named anywhere in a `blocked_by` value. Mirrors the writer.

    Duplicated on purpose: this gate must review a registry written by anything —
    a human, an older kit, a hand edit — so it cannot import the writer and inherit
    its assumptions about what produced the file.

    Ids are extracted from prose rather than parsed from a fixed shape, because the
    field was in use before it was specified: of the eight items carrying it when it
    was measured, seven named a sponsor decision or an external action and only one
    named an item. Demanding `B-NNN` would have reported seven honest impediments as
    malformed.
    """
    if not declares_impediment(raw):
        return []
    return _ID_IN_TEXT_RE.findall(raw)


def carries_prose(raw: str) -> bool:
    """Does the value say anything beyond a list of ids?

    `blocked_by` is prose by design — of the eight items carrying it when the
    field was measured, seven named a sponsor decision or an external action and
    only one named an item. A value stating a reason is the normal case, and an
    ids-only value is the exception this distinction exists to find.
    """
    return bool(_ID_IN_TEXT_RE.sub("", raw).strip(" ,\u2014-"))


def impediment_edges(raw: str, own_id: str) -> list[str]:
    """The ids `raw` names as impediments, which never includes the item itself.

    An item's own id appears in its `blocked_by` prose constantly and innocently,
    because the prose describes the item: *"Vide report /idea-to-release B-060 de
    2026-08-31"*. The parser lifts every id it sees, so that sentence made B-060
    its own blocker — then a ring of one, then a deadlock no work can clear.
    Measured on a real registry on 2026-09-02: **14 items reported `self_block`
    and 14 more reported a `B-NNN -> B-NNN` cycle, 28 blockers in total, every
    one of them false**, and together they refused every push to the repository.

    `select_backlog_item.py:141` had already fixed this for the queue — same
    field, same reasoning, same one-line filter — and the fix did not travel to
    the gate. The duplication between the two is deliberate (this gate must read
    a registry written by anything, so it cannot import the writer), but a rule
    duplicated is a rule that can be fixed in one copy and stay broken in the
    other, and that is what happened.

    An ids-only value is left alone: `blocked_by: B-060` written on B-060 is a
    genuine self-block, it describes nothing, and the gate should still say so.
    """
    ids = parse_blocked_by(raw)
    return [b for b in ids if b != own_id] if carries_prose(raw) else ids


def _find_cycles(edges: dict[str, list[str]]) -> list[list[str]]:
    """Every distinct ring in the impediment graph, each reported once.

    Rings are keyed by their sorted membership so a three-item cycle is not reported
    three times — once per entry point — which would read as three deadlocks.
    """
    rings: dict[frozenset[str], list[str]] = {}
    for start in edges:
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        while stack:
            node, path = stack.pop()
            for nxt in edges.get(node, []):
                if nxt == start:
                    rings.setdefault(frozenset(path), path + [nxt])
                elif nxt not in path and nxt in edges:
                    stack.append((nxt, path + [nxt]))
    return list(rings.values())



def effective_state(status: str, blockers: list[str], statuses: dict[str, str]) -> str:
    """The derivation rule, asked of its owner in `mechanisms/cycle/backlog_status.py`.

    NOT the same call as `parse_blocked_by` above, whose duplication is deliberate and
    explained there: that one mirrors the WRITER, and this gate must review a registry
    produced by anything. This is the derivation — "a blocker that shipped or was killed
    stops blocking" — and there is one correct answer to it. Two copies meant the owner's
    version had no caller at all, so it could drift from the one that runs and its own
    tests would keep passing.

    Falls back to the local computation when the owner cannot be imported, because a
    counter that raises is worse than a counter that agrees with an older copy — and the
    fallback is the code that was here already, not a new second opinion.
    """
    try:
        from backlog_status import effective_state as _owner
    except ImportError:
        if status not in OPEN_STATUS:
            return status
        return "blocked" if any(statuses.get(b, "") in OPEN_STATUS for b in blockers) else status
    return _owner(status, blockers, statuses)


def _effective_counts(items: list[Item]) -> dict[str, int]:
    _add_cycle_tooling_to_path()
    statuses = {i.item_id: i.fields.get("status", "") for i in items}
    counts: dict[str, int] = {}
    for item in items:
        status = item.fields.get("status", "")
        raw = item.fields.get("blocked_by", "")
        state = status
        if status in OPEN_STATUS and declares_impediment(raw):
            ids = parse_blocked_by(raw)
            # No ids means a prose impediment: nothing another item's status can
            # resolve, so it holds until a human removes the line. The owner takes
            # only id edges, which is why that case is decided here.
            state = "blocked" if not ids else effective_state(status, ids, statuses)
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))



def _check_each_item(items: list[Item], known_repos: set[str] | None,
                     today: date) -> tuple[list[Finding], list[int]]:
    """Every per-item check, in the order the registry's own contract lists them.

    Extracted from `check_backlog`, which measured cyclomatic complexity 82 across 297
    lines: a preamble, this loop of fifteen per-item checks, and a tail of cross-item
    ones. Pure code movement — the body below is the body that was there.

    `seen_ids` and `numeric_ids` accumulate ACROSS items, which is why they live here
    rather than inside a per-item helper: the duplicate-id and monotonic-id checks are
    the two that cannot be answered one item at a time. `numeric_ids` travels back out
    because the tail's monotonicity check reads it.
    """
    findings: list[Finding] = []
    seen_ids: dict[str, Item] = {}
    numeric_ids: list[int] = []

    for item in items:
        iid = item.item_id

        if iid in seen_ids:
            findings.append(Finding("duplicate_id", "deterministic", "blocker", iid,
                f"`{iid}` appears twice (lines {seen_ids[iid].line} and {item.line}). "
                "Ids are the audit trail; two blocks sharing one destroys it."))
        seen_ids[iid] = item
        numeric_ids.append(int(iid.split("-")[1]))

        for required in REQUIRED_FIELDS:
            if required not in item.fields:
                findings.append(Finding("missing_field", "deterministic", "major", iid,
                    f"`{required}` is absent"))

        # `status` twice leaves the block with two answers, and every reader — this gate, the
        # index generator, a human skimming — silently takes the last one. Measured on db-engine:
        # `B-021` carries `raw` then `triaged`, `B-022` carries `planned` then `raw`. The index
        # buckets on `status`, so an ambiguous one makes the summary arbitrary rather than
        # wrong-in-a-way-you-can-see.
        #
        # ONLY `status`, deliberately. The first draft flagged every repeated field and lit up
        # control-plane: `partial_progress` four times on B-031 is an append-one-line-per-increment
        # log the team keeps on purpose, and `evidence: none-yet` followed by a pointer is an item
        # that advanced. Neither is a defect, and a gate that reports them is a gate people learn
        # to override — which is how the real one gets waved through.
        if "status" in item.duplicated:
            values = item.duplicated["status"]
            findings.append(Finding("duplicate_field", "deterministic", "blocker", iid,
                f"`status` is declared {len(values)} times ({' then '.join(values)}). "
                "Every reader takes the last one; the block has to say one thing."))

        # The narrowing above holds while the second line is about the SAME item. On a
        # consumer 2026-09-18 it was not: B-001 carried a second `evidence:` and a second
        # `blocked_by:` describing B-006 — its authorization work, its piece, its line
        # count — while B-006's own block read `evidence: none-yet, status: raw`. Someone
        # had pasted one block's fields into another. Seventeen blocks, and the only
        # finding was `index_stale`.
        #
        # B-001 stood at `triaged` on another item's evidence, and removing the foreign
        # lines made `triaged_without_evidence` fire at once — the honest state, and
        # always the state. The two extra lines also shifted every pointer below them by
        # exactly 2, breaking three `BACKLOG.md:N` citations in a scored opportunity.
        #
        # So: a placeholder followed by a real value is an ADVANCE and stays silent. Two
        # substantive values are two CLAIMS, and the block does not say which is the
        # item's. That keeps `evidence: none-yet` → pointer quiet, which is the case the
        # narrowing was reasoned for.
        if "evidence" in item.duplicated:
            claims = [v for v in item.duplicated["evidence"]
                      if v and v.lower() not in _NO_IMPEDIMENT]
            if len(claims) > 1:
                findings.append(Finding("duplicate_field", "deterministic", "blocker", iid,
                    f"`evidence` carries {len(claims)} substantive values "
                    f"({' / '.join(c[:60] for c in claims)}). A placeholder replaced by a "
                    "pointer is an item advancing; two pointers are two claims, and every "
                    "reader takes one of them while the other is invisible."))

        # `blocked_by` has no append semantics at all — it declares the edge SET, so a
        # second line does not add edges, it replaces them. The first line's blockers
        # leave the dependency graph without leaving a trace, which is a hole in what
        # `_check_impediment_edges` and the cycle detector are reading.
        if "blocked_by" in item.duplicated:
            values = item.duplicated["blocked_by"]
            findings.append(Finding("duplicate_field", "deterministic", "blocker", iid,
                f"`blocked_by` is declared {len(values)} times "
                f"({' then '.join(values)}). It names the whole edge set rather than "
                "adding to it, so every line but the last is dropped silently."))

        status = item.fields.get("status", "")
        if status and status not in LEGAL_STATUS:
            findings.append(Finding("illegal_status", "deterministic", "blocker", iid,
                f"status `{status}` is outside {sorted(LEGAL_STATUS)}"))

        mode = item.fields.get("suggested_mode", "")
        if mode and mode not in LEGAL_MODES:
            findings.append(Finding("invalid_mode", "deterministic", "major", iid,
                f"suggested_mode `{mode}` is outside {sorted(LEGAL_MODES)}"))

        evidence = item.fields.get("evidence", "")
        # A block can CONTRADICT its own status. Measured on a consumer 2026-09-18: twelve items
        # carried `remeasured …: **closed in code.**` in their prose and every one was still
        # `triaged`, while the report read SHIPPABLE across all 44.
        #
        # The cause is structural, not careless: `backlog_status.py` refuses `triaged -> shipped`
        # and `approved` is a human decision, so a remeasurement that finds an item DONE has
        # nowhere legal to put that. It goes in the prose, and the two halves disagree from then
        # on. The registry reports finished work as pending — the rot the maintenance loop exists
        # to prevent, arriving through the door the state machine left open.
        #
        # This asserts nothing about whether the item is really done; nothing here can measure
        # that. It asserts that a reader has two answers and no way to choose.
        if status not in TERMINAL_STATUSES and _DECLARES_CLOSED_RE.search(item.body):
            findings.append(Finding("status_contradicts_body", "deterministic", "major", iid,
                f"the block declares itself closed in its own prose and is filed as `{status}`. "
                "One of the two is wrong, and a reader cannot tell which."))
        if status == "killed" and not item.fields.get("kill_reason"):
            findings.append(Finding("killed_without_reason", "deterministic", "major", iid,
                "killed with no kill_reason — indistinguishable from an abandoned run (gate G-K)"))
        if status == "triaged" and evidence in ("", "none-yet"):
            findings.append(Finding("triaged_without_evidence", "deterministic", "blocker", iid,
                "triaged but evidence is still `none-yet`. Triaged means measured; "
                "without evidence the status is a claim nobody made."))
        if status == "raw" and evidence not in ("", "none-yet"):
            findings.append(Finding("raw_with_evidence", "deterministic", "major", iid,
                f"raw but carries evidence (`{evidence}`) — measurement happened and the "
                "status was never advanced"))

        repo = item.fields.get("repo", "")
        if repo and known_repos is not None and repo not in known_repos:
            #: G1 is about work that cannot proceed — `cycle-backlog.md` puts it as
            #: "an item nobody owns is an item nobody does". A shipped or killed item
            #: is not work; it is history, and nothing about it can be done by anyone.
            #:
            #: Firing on terminal items made the verdict PERMANENTLY INVALID, because
            #: the contract forbids both escapes. Renumbering: "the number is the audit
            #: trail; a killed B-007 stays B-007 forever." An impediment: "leaving
            #: blocked_by on a closed item — the registry then tells everyone after you
            #: that finished work is stuck." The only remaining move was widening the
            #: routing table to name a repository the project deliberately does not
            #: govern, which makes the table describe a scope that is not the scope.
            #:
            #: Measured on a consumer with 227 items: 10 unroutable_repo blockers, 3
            #: shipped and 6 killed. One was live, and it was the one that could act.
            if item.fields.get("status", "") in OPEN_STATUS:
                findings.append(Finding("unroutable_repo", "deterministic", "blocker", iid,
                    f"`{repo}` is in no domain — the item routes to nobody (gate G1)"))
            else:
                #: Reported, not silenced. The history stays visible — a registry that
                #: hides which closed items name repositories it no longer governs has
                #: lost the record, which is the one thing a terminal item is for.
                findings.append(Finding("unroutable_repo_closed", "deterministic", "minor", iid,
                    f"`{repo}` is in no domain, and this item is "
                    f"`{item.fields.get('status', '?')}` — history, not an impediment. "
                    "Nothing can be done about it and nothing should be: the id is the "
                    "audit trail and the routing table describes the scope as it is now"))

        if not item.dod:
            findings.append(Finding("thin_dod", "heuristic", "major", iid,
                "no DoD bullet — nothing states when this item is done, so it never closes"))
        else:
            for bullet in item.dod:
                if _is_vague(bullet):
                    findings.append(Finding("vague_dod", "heuristic", "minor", iid,
                        f"DoD bullet has nothing falsifiable: \"{bullet}\""))

        if status == "raw" and item.registered_on:
            age = (today - item.registered_on).days
            if age > STALE_RAW_DAYS:
                findings.append(Finding("stale_raw", "heuristic", "minor", iid,
                    f"raw for {age} days. Either it matters and nobody measured it, or it "
                    "does not and it should be killed with that as the reason."))

    return findings, numeric_ids


def _check_impediment_edges(items: list[Item]) -> list[Finding]:
    """Every `blocked_by` edge: does it resolve, does it hold, is it a ring?

    Extracted from `check_backlog`, which measured cyclomatic complexity 82 across 297
    lines. Pure code movement: the block below is the block that was there.
    """
    findings: list[Finding] = []
    # ── impediment edges ──────────────────────────────────────────────────────
    #
    # `blocked_by` is written on the blocked side only; the reverse edge is derived by
    # the index and never typed, so the two halves cannot drift apart. What CAN rot is
    # the edge itself, in four ways, and all four are deterministic.
    raw_values = {i.item_id: i.fields.get("blocked_by", "") for i in items}
    edges = {iid: impediment_edges(raw, iid) for iid, raw in raw_values.items()}
    statuses = {i.item_id: i.fields.get("status", "") for i in items}

    for item in items:
        iid = item.item_id
        blockers = edges.get(iid, [])
        if not declares_impediment(raw_values.get(iid, "")):
            continue

        if iid in blockers:
            findings.append(Finding("self_block", "deterministic", "blocker", iid,
                f"`{iid}` names itself in `blocked_by`. It can never be resolved."))

        unknown = [b for b in blockers if b not in statuses]
        if unknown:
            findings.append(Finding("blocker_missing", "deterministic", "blocker", iid,
                f"`blocked_by` names {', '.join(unknown)}, which no block in this file defines. "
                "An edge pointing at nothing never resolves; file the item or drop the edge."))

        known = [b for b in blockers if b in statuses]
        # Only an all-ids impediment can be called stale. A value that also states a
        # reason ("B-075, and the sponsor must ratify") outlives its item edge, and
        # nothing in this repository can tell whether the sponsor has ratified.
        prose_only = raw_values.get(iid, "")
        carries_prose = bool(_ID_IN_TEXT_RE.sub("", prose_only).strip(" ,—-"))
        if known and not carries_prose and all(statuses[b] not in OPEN_STATUS for b in known) and not unknown:
            findings.append(Finding("stale_block", "deterministic", "minor", iid,
                f"every blocker ({', '.join(known)}) is closed, but the edge is still written. "
                "The derived state already reads unblocked; the line is now noise."))

        if statuses.get(iid) not in OPEN_STATUS:
            open_blockers = [b for b in known if statuses[b] in OPEN_STATUS]
            if open_blockers:
                findings.append(Finding("closed_but_blocked", "deterministic", "major", iid,
                    f"`{iid}` is {statuses[iid]} while {', '.join(open_blockers)} is still open. "
                    "Either the item did not really close, or the edge was never cleared."))
            elif not known:
                findings.append(Finding("closed_but_blocked", "deterministic", "minor", iid,
                    f"`{iid}` is {statuses[iid]} but still states an impediment. "
                    "A closed item declaring a live block reads as unfinished to everyone after you."))

    for ring in _find_cycles(edges):
        findings.append(Finding("blocker_cycle", "deterministic", "blocker", ring[0],
            f"impediment cycle: {' -> '.join(ring)}. Every item in the ring waits for another "
            "in it, so none can ever ship. Break it by splitting one item or dropping one edge."))

    return findings


def _check_lineage_edges(items: list[Item]) -> list[Finding]:
    """Every `supersedes` / `regression_of` edge, and the status it implies.

    Extracted from `check_backlog`, which measured cyclomatic complexity 82 across 297
    lines. Pure code movement: the block below is the block that was there.
    """
    findings: list[Finding] = []
    statuses = {i.item_id: i.fields.get("status", "") for i in items}
    # ── lineage edges ─────────────────────────────────────────────────────────
    #
    # Same shape as the impediment edge above, one question shorter: a lineage edge
    # cannot go stale (its target is terminal and stays terminal) and cannot ring.
    # What it CAN do is name nothing, or name something that is not what the field
    # says it is.
    for item in items:
        iid = item.item_id
        for field_name, required_status in LINEAGE_EDGES.items():
            raw = item.fields.get(field_name, "").strip()
            if not raw or raw.lower() in _NO_IMPEDIMENT:
                continue
            targets = _ID_IN_TEXT_RE.findall(raw)
            if not targets:
                findings.append(Finding("lineage_missing", "deterministic", "blocker", iid,
                    f"`{field_name}: {raw}` names no item id. This edge exists to point at the "
                    f"item this one replaces; prose alone cannot be resolved."))
                continue
            for target in targets:
                if target == iid:
                    findings.append(Finding("lineage_missing", "deterministic", "blocker", iid,
                        f"`{field_name}` names `{iid}` itself. An item cannot be its own ancestor."))
                elif target not in statuses:
                    findings.append(Finding("lineage_missing", "deterministic", "blocker", iid,
                        f"`{field_name}` names {target}, which no block in this file defines. "
                        f"An edge pointing at nothing never resolves; the id is the audit trail."))
                elif statuses[target] != required_status:
                    findings.append(Finding("lineage_wrong_status", "deterministic", "major", iid,
                        f"`{field_name}` names {target}, which is `{statuses[target]}` and not "
                        f"`{required_status}`. The field asserts a state its target is not in — "
                        f"a duplicate of an OPEN item folds in as ITEM_MERGED instead."))

    return findings


#: `## Items` — the section `backlog-init` Step 3 prescribes, declared empty.
_ITEMS_SECTION_RE = re.compile(r"^##\s+Items\s*$", re.MULTILINE)


def declares_an_empty_items_section(content: str) -> bool:
    """Does this registry SAY it holds no items, rather than merely yielding none?

    "Correctly empty" had no way to be expressed, and two rules of this kit
    contradicted each other over it. `backlog-init/SKILL.md` Step 3 says **"Seed no
    items"** — an item nobody filed is a placeholder that gets inherited as a decision —
    while `registry_parses` fired on `content.strip() and not items`, true of every
    freshly-seeded registry. A registry created exactly as instructed was born INVALID.

    The check itself is right and stays: an unparseable registry reporting SHIPPABLE is
    the defect it was written for. What was missing is the file's ability to say which
    of the two it is. A registry that declares `## Items` and holds none is empty; one
    with no such section, or with text under it this parser cannot place, is unreadable
    — and those still block.
    """
    match = _ITEMS_SECTION_RE.search(content)
    if match is None:
        return False
    rest = content[match.end():]
    # Another `## ` heading ends the section. Everything between is what it holds.
    following = re.search(r"^##\s+\S", rest, re.MULTILINE)
    body = rest[:following.start()] if following else rest
    # A placeholder line is prose about the absence, not an item this parser lost.
    # Anything that looks like a heading under Items is content it could not place.
    return not re.search(r"^#{2,4}\s+\S", body, re.MULTILINE)


def check_backlog(backlog_path: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    content = backlog_path.read_text(encoding="utf-8-sig")
    items = _parse_items(content)
    findings: list[Finding] = []

    # A file with content that yields no item is a file THIS PARSER could not read, and
    # that is not the same fact as an empty registry. The verdict is derived from the
    # findings list, and no items means no findings — so counts were all zero, the
    # verdict was SHIPPABLE and `main` returned 0 over a registry nothing had parsed.
    # No branch asked whether the file it just read produced anything.
    if content.strip() and not items and not declares_an_empty_items_section(content):
        findings.append(Finding(
            item="(file)", check="registry_parses", severity="blocker",
            kind="deterministic",
            message=(f"{backlog_path.name} is {len(content.splitlines())} line(s) long "
                     f"and this parser found no `## B-NNN` item in it. That is a registry "
                     f"this check could not read, not a registry with nothing in it — and "
                     f"the two must not share a verdict"),
        ))

    project_root = backlog_path.resolve().parent
    routing = _routing(project_root)
    known_repos = (
        None if routing is None else {r for e in routing.values() for r in e["repos"]}
    )

    # A domain whose specialist file is absent routes every one of its items to nobody.
    #
    # `route_domain.py` calls that a BROKEN ROUTE and exits 3 — "a defect in the table itself" — but
    # this report never asked. Gate G1 checks whether a repo is IN the table, not whether the table's
    # answer exists, so a registry could read SHIPPABLE while all of its items resolved to a file
    # nobody had written. Measured on an adopter 2026-09-03: its table named a specialist file that
    # did not exist, every repo in it exited 3 from `route_domain.py`, and 106 items routed to nobody
    # while this report came back clean.
    #
    # The measurement is deliberately anonymous. `test_no_origin_ecosystem_leak` refuses a versioned
    # kit file that names a specific ecosystem's repositories, and its reason applies here: the kit
    # describes ANY product that adopts it, and a named one makes every consumer inherit a map of
    # repos they do not have. The first version of this comment named the adopter and the detector
    # caught it.
    #
    # This is the same failure the routing gate exists to prevent, one level up, and it failed in the
    # reassuring direction.
    if routing is not None:
        for domain, entry in sorted(routing.items()):
            agent = entry.get("agent")
            if agent is None:
                findings.append(Finding("broken_route", "deterministic", "blocker", domain,
                    f"domain `{domain}` names no specialist — every item it routes reaches nobody"))
                continue
            # Resolved against the tree the TABLE came from, not the registry's own
            # directory. `agents/x.md` in a table at `<root>/.claude/rules/` means
            # `<root>/.claude/agents/x.md`, and a registry at `apps/<app>/BACKLOG.md`
            # resolving it against `apps/<app>/` reported every domain broken on files
            # that were on disk (kit#138). `project_root` stays in the list so a
            # registry that sits beside its own `agents/` keeps working.
            homes = [*_routing_home, project_root]
            if not any((h / agent).exists() or (h / ".claude" / agent).exists()
                       for h in homes):
                findings.append(Finding("broken_route", "deterministic", "blocker", domain,
                    f"domain `{domain}` routes to `{agent}`, which is not on disk"))


    # The per-item half. `numeric_ids` comes back because the monotonicity check below
    # reads the order the ids appeared in.
    item_findings, numeric_ids = _check_each_item(items, known_repos, today)
    findings.extend(item_findings)


    if numeric_ids and numeric_ids != sorted(numeric_ids):
        findings.append(Finding("renumbered", "deterministic", "blocker", "-",
            "ids are not monotonic. Ids are never reused and never reordered — a reused "
            "id makes every earlier reference ambiguous."))

    open_items = [i for i in items if i.fields.get("status") in OPEN_STATUS]
    for idx, a in enumerate(open_items):
        for b in open_items[idx + 1 :]:
            if _title_overlap(a.title, b.title) >= 0.6:
                findings.append(Finding("possible_duplicate", "heuristic", "minor", a.item_id,
                    f"title overlaps heavily with {b.item_id} (\"{b.title}\") — the intake "
                    "dedup may have missed it"))

    # The index at the top has to agree with the blocks below it. Nothing forces the two to move
    # together — the index is regenerated by a command someone has to remember to run — so a
    # registry whose summary says "3 open" while 11 items are open reads as authoritative and is
    # wrong. That is strictly worse than having no index, because a reader stops at the summary.
    # Imported here rather than at module scope: `backlog_index` imports this module for the item
    # parser, and a top-level import in both directions is a cycle.
    from backlog_index import index_is_current

    index_current, _ = index_is_current(content)
    if not index_current:
        findings.append(Finding("index_stale", "deterministic", "major", "—",
            "the index at the top does not match the items below it (or is absent). "
            "Regenerate with `python3 backlog_index.py BACKLOG.md --write`."))

    findings.extend(_check_impediment_edges(items))
    findings.extend(_check_lineage_edges(items))

    counts = {"blocker": 0, "major": 0, "minor": 0}
    for f in findings:
        counts[f.severity] += 1

    if counts["blocker"]:
        verdict = "INVALID"
    elif counts["major"]:
        verdict = "NEEDS_REVISION"
    elif counts["minor"]:
        verdict = "SHIPPABLE_WITH_CAVEATS"
    else:
        verdict = "SHIPPABLE"

    return {
        "backlog": str(backlog_path),
        "items_total": len(items),
        "items_by_status": {
            s: sum(1 for i in items if i.fields.get("status") == s) for s in sorted(LEGAL_STATUS)
        },
        # The state a reader should act on. `blocked` is DERIVED here and stored
        # nowhere, which is what stops it from going stale: an item whose blockers
        # all shipped stops being blocked without anyone remembering to edit it.
        "items_by_effective_state": _effective_counts(items),
        "routing_table_read": known_repos is not None,
        "findings": [f.__dict__ for f in findings],
        "severity_counts": counts,
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic structural review of BACKLOG.md.")
    parser.add_argument("backlog", type=Path, nargs="?", default=Path("BACKLOG.md"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.backlog.exists():
        print(f"BACKLOG.md not found at {args.backlog} — run /backlog-init first", file=sys.stderr)
        return 2

    report = check_backlog(args.backlog)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Backlog : {report['backlog']}")
        print(f"Items   : {report['items_total']}  {report['items_by_status']}")
        if not report["routing_table_read"]:
            reason = _routing_gap[-1] if _routing_gap else "no reason recorded"
            print(f"WARN    : repo routing was NOT checked — {reason}")
        for f in report["findings"]:
            print(f"  [{f['severity'].upper()}/{f['kind'][:4]}] {f['item']} {f['check']}: {f['message']}")
        print(f"\nVerdict : {report['verdict']}  {report['severity_counts']}")

    return {"INVALID": 1, "NEEDS_REVISION": 3}.get(report["verdict"], 0)


if __name__ == "__main__":
    sys.exit(main())

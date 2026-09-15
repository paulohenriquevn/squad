"""The selection the maintenance chain specified and nothing implemented.

`cycle-maintenance.md § Chain` carried the filter and the ranking — with a section
justifying both — since it was written. No code read it, so the order was a paragraph
an agent was asked to remember, and the only runner carried a literal list of ids.
"""
from __future__ import annotations

from pathlib import Path

from backlog_fixtures import item_block
from check_backlog_structure import _parse_items
from select_backlog_item import live_blockers, rank, select


def _backlog(*blocks: str) -> str:
    return "# Backlog\n\n## Itens\n\n" + "".join(blocks)


# ── the ranking the contract justifies ────────────────────────────────────────


def test_triaged_outranks_raw() -> None:
    """A triaged item carries measured evidence; its cost to finish is known."""
    text = _backlog(item_block("B-001", status="raw"), item_block("B-002", status="triaged"))
    assert select(text).item_id == "B-002"


def test_oldest_first_within_a_status() -> None:
    """Ids are monotonic and never reused, so a lower number was registered earlier."""
    text = _backlog(item_block("B-009", status="triaged"), item_block("B-003", status="triaged"))
    assert select(text).item_id == "B-003"


def test_rank_puts_every_triaged_before_every_raw() -> None:
    text = _backlog(item_block("B-001", status="raw"), item_block("B-002", status="triaged"),
                    item_block("B-003", status="raw"), item_block("B-004", status="triaged"))
    assert [i.item_id for i in rank(_parse_items(text))] == ["B-002", "B-004", "B-001", "B-003"]


def test_planned_is_not_selectable() -> None:
    """It is open, but it already has a plan — SELECT hands out work, not plans."""
    text = _backlog(item_block("B-001", status="planned"))
    assert select(text).verdict == "BACKLOG_EMPTY"


def test_closed_items_are_not_selectable() -> None:
    text = _backlog(item_block("B-001", status="shipped"), item_block("B-002", status="killed"))
    assert select(text).verdict == "BACKLOG_EMPTY"


# ── eligibility, which the filter alone no longer decides ─────────────────────


def test_a_blocked_item_is_skipped_for_the_next_one() -> None:
    """The chain's `status in {raw, triaged}` predates impediments."""
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-002", status="triaged"),
                    item_block("B-100", status="raw"))
    assert select(text).item_id == "B-002"


def test_an_item_blocked_by_prose_is_skipped() -> None:
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: the sponsor must decide\n"),
                    item_block("B-002", status="triaged"))
    assert select(text).item_id == "B-002"


def test_a_resolved_blocker_frees_the_item_with_no_second_edit() -> None:
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-100", status="shipped"))
    assert select(text).item_id == "B-001"


def test_everything_blocked_is_not_an_empty_backlog() -> None:
    """"Run a sweep" would add items beside a wall instead of clearing it."""
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-100", status="planned"))
    result = select(text)
    assert result.verdict == "BACKLOG_BLOCKED"
    assert result.walls == {"B-001": ["B-100"]}


def test_an_empty_backlog_is_distinguished_from_a_blocked_one() -> None:
    assert select(_backlog(item_block("B-001", status="shipped"))).verdict == "BACKLOG_EMPTY"


def test_live_blockers_separates_prose_from_not_blocked() -> None:
    """[] and None mean different things: blocked-by-a-decision, and not blocked."""
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: a decision\n"),
                    item_block("B-002", status="triaged"))
    items = {i.item_id: i for i in _parse_items(text)}
    assert live_blockers(items["B-001"], {}) == []
    assert live_blockers(items["B-002"], {}) is None


# ── the narrow question ───────────────────────────────────────────────────────


def test_asking_about_a_blocked_item_is_refused() -> None:
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-100", status="raw"))
    result = select(text, requested="B-001")
    assert result.verdict == "BACKLOG_BLOCKED"
    assert "B-100" in result.reason


def test_asking_about_a_shipped_item_is_refused() -> None:
    """Refused, but named: `BACKLOG_BLOCKED` here claimed a wall that did not exist."""
    result = select(_backlog(item_block("B-001", status="shipped")), requested="B-001")
    assert result.verdict == "ITEM_SHIPPED"
    assert result.item_id == "B-001"


def test_asking_about_an_unknown_item_is_refused() -> None:
    assert select(_backlog(item_block("B-001", status="raw")), requested="B-404").verdict == "BACKLOG_BLOCKED"


def test_the_gate_and_the_selector_agree() -> None:
    """Two answers to one question is the defect a second implementation creates."""
    text = _backlog(item_block("B-001", status="raw"), item_block("B-002", status="triaged"))
    picked = select(text).item_id
    assert select(text, requested=picked).verdict == "ITEM_SELECTED"


# ── the batch caller ──────────────────────────────────────────────────────────


def test_the_queue_is_the_full_order_not_just_the_head() -> None:
    """The pipeline fills more than one lane; re-running per lane would be absurd."""
    text = _backlog(item_block("B-003", status="raw"), item_block("B-001", status="triaged"),
                    item_block("B-002", status="triaged"))
    assert select(text).queue == ["B-001", "B-002", "B-003"]


def test_the_queue_excludes_blocked_items() -> None:
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-002", status="triaged"), item_block("B-100", status="raw"))
    assert "B-001" not in select(text).queue


def test_the_wall_is_reported_even_on_success() -> None:
    text = _backlog(item_block("B-001", status="triaged"),
                    item_block("B-002", status="triaged", extra="blocked_by: B-100\n"),
                    item_block("B-100", status="raw"))
    result = select(text)
    assert result.verdict == "ITEM_SELECTED"
    assert result.walls["B-002"] == ["B-100"]


# ── blocked, versus already past this gate ────────────────────────────────────
#
# Found by using the tool: an item that had reached `planned`, whose blocker had
# SHIPPED, came back BACKLOG_BLOCKED. Nothing was blocking it — it was ready for the
# next phase. One verdict was carrying two states, and only one of them is a wall.


def test_a_planned_item_is_in_flight_not_blocked() -> None:
    text = _backlog(item_block("B-001", status="planned"))
    result = select(text, requested="B-001")
    assert result.verdict == "ITEM_IN_FLIGHT"


def test_a_planned_item_whose_blocker_shipped_is_not_reported_as_blocked() -> None:
    """The exact case that surfaced the defect."""
    text = _backlog(item_block("B-001", status="planned", extra="blocked_by: B-002\n"),
                    item_block("B-002", status="shipped"))
    assert select(text, requested="B-001").verdict == "ITEM_IN_FLIGHT"


def test_a_shipped_item_says_so() -> None:
    text = _backlog(item_block("B-001", status="shipped"))
    assert select(text, requested="B-001").verdict == "ITEM_SHIPPED"


def test_a_killed_item_says_so() -> None:
    text = _backlog(item_block("B-001", status="killed", extra="kill_reason: measured otherwise\n"))
    assert select(text, requested="B-001").verdict == "ITEM_KILLED"


def test_a_genuinely_blocked_item_is_still_blocked() -> None:
    """The distinction only helps if the real wall keeps its name."""
    text = _backlog(item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
                    item_block("B-002", status="raw"))
    assert select(text, requested="B-001").verdict == "BACKLOG_BLOCKED"


def test_an_unknown_status_is_not_silently_called_in_flight() -> None:
    """A status outside the contract means the contract moved; do not guess."""
    text = _backlog(item_block("B-001", status="marinating"))
    assert select(text, requested="B-001").verdict == "BACKLOG_BLOCKED"


def test_none_of_these_are_selectable() -> None:
    for status in ("planned", "shipped", "killed"):
        text = _backlog(item_block("B-001", status=status,
                                   extra="kill_reason: x\n" if status == "killed" else ""))
        assert select(text).verdict != "ITEM_SELECTED"


# ── an item a phase stopped on is not work to hand out ───────────────────────


def test_a_halted_item_is_not_selected(tmp_path: Path) -> None:
    """Measured on 2026-08-31: B-033 was `triaged`, nothing in the registry blocked it,
    and it held the oldest id among unblocked items — so SELECT chose it. A phase had
    already stopped on it and written a BLOCKED report. A caller that only asked SELECT
    would have relaunched the thing that halted, forever."""
    text = item_block("B-033", status="triaged") + item_block("B-057", status="triaged")
    result = select(text, halted=frozenset({"B-033"}))
    assert result.verdict == "ITEM_SELECTED"
    assert result.item_id == "B-057"
    assert result.halted == ["B-033"]
    assert "B-033" not in (result.queue or [])


def test_asking_about_a_halted_item_says_so_rather_than_yes(tmp_path: Path) -> None:
    text = item_block("B-033", status="triaged")
    result = select(text, "B-033", halted=frozenset({"B-033"}))
    assert result.verdict == "ITEM_HALTED"
    assert "BLOCKED report" in result.reason


def test_a_halt_is_not_reported_as_an_impediment(tmp_path: Path) -> None:
    """Two different things hold an item, and they need different actions from
    different people. Folding one into the other loses which is which."""
    text = item_block("B-033", status="triaged")
    result = select(text, halted=frozenset({"B-033"}))
    assert result.verdict == "BACKLOG_BLOCKED"
    assert result.walls == {}
    assert result.halted == ["B-033"]
    assert "1 by a phase that halted" in result.reason


def test_without_a_halt_set_nothing_changes(tmp_path: Path) -> None:
    """The parameter defaults to empty, so every existing caller keeps its answer."""
    text = item_block("B-033", status="triaged") + item_block("B-057", status="triaged")
    assert select(text).item_id == "B-033"


# ── the queue attacks the cause of a halt ────────────────────────────────────


def test_an_item_that_unblocks_a_halt_comes_first(tmp_path: Path) -> None:
    """Age normally decides, and still decides among equals. An item a halted item's
    report names as its cause is not an equal: every hour it waits, the halted item
    waits too.

    Measured on 2026-08-31: B-033 halted on B-168/169/170 and by age alone the queue
    would have reached them after twenty other items. The halt would have outlived
    all of them."""
    text = (item_block("B-057", status="triaged")
            + item_block("B-058", status="triaged")
            + item_block("B-168", status="triaged"))
    result = select(text, unblocking=frozenset({"B-168"}))
    assert result.item_id == "B-168"
    assert result.queue == ["B-168", "B-057", "B-058"]
    assert "names it as a cause" in result.reason


def test_priority_changes_order_never_eligibility(tmp_path: Path) -> None:
    """An unblocking item that is itself halted stays out of the queue. Ordering must
    not become a way in for something the rules hold."""
    text = item_block("B-057", status="triaged") + item_block("B-168", status="triaged")
    result = select(text, halted=frozenset({"B-168"}),
                    unblocking=frozenset({"B-168"}))
    assert result.item_id == "B-057"
    assert result.halted == ["B-168"]


def test_a_blocked_unblocking_item_still_waits_on_its_blocker(tmp_path: Path) -> None:
    text = (item_block("B-057", status="triaged")
            + item_block("B-168", status="triaged", extra="blocked_by: B-200\n")
            + item_block("B-200", status="triaged"))
    result = select(text, unblocking=frozenset({"B-168"}))
    assert result.item_id == "B-057"
    assert result.walls == {"B-168": ["B-200"]}


def test_without_a_priority_set_the_order_is_unchanged(tmp_path: Path) -> None:
    """Every existing caller keeps its answer: the parameter defaults to empty."""
    text = item_block("B-057", status="triaged") + item_block("B-168", status="triaged")
    assert select(text).item_id == "B-057"

def test_an_item_never_appears_as_its_own_wall() -> None:
    """`blocked_by` is prose and the parser lifts every `B-NNN` in it, so a sentence
    naming the item listed the item as its own blocker.

    The prose still holds it — that is the contract, and an impediment with no item
    to point at is exactly what an empty blocker list means. What must NOT happen is
    the board reporting `B-001 → B-001`: a wall pointing at itself is a deadlock no
    work can clear, and it reads like a cause somebody could go and fix.

    Measured on a consumer 2026-09-02: 26 selectable items behind seven roots, two
    of which were holding themselves, their prose reading "same wording as B-079
    and B-080".
    """
    text = _backlog(item_block(
        "B-001", status="triaged",
        extra="blocked_by: waiting on the same batch as B-001 itself, see the note\n"))

    report = select(text)

    assert report.verdict == "BACKLOG_BLOCKED", "the prose impediment still holds it"
    assert report.walls.get("B-001") == [], (
        f"the item must not be listed as its own wall: {report.walls}")


def test_a_real_blocker_beside_the_self_reference_still_holds() -> None:
    """Dropping the self-mention must not drop the blocker standing next to it."""
    text = _backlog(
        item_block("B-001", status="triaged",
                   extra="blocked_by: B-001's own note says this waits on B-002\n"),
        item_block("B-002", status="triaged"))

    assert select(text).item_id == "B-002", "B-001 is still held by B-002"


def _item_blocked_by(item_id: str, raw: str):
    """An item carrying `raw` in its `blocked_by`, and nothing else that matters."""
    from check_backlog_structure import Item
    it = Item(item_id=item_id, title="t", line=1)
    it.fields["blocked_by"] = raw
    it.fields["status"] = "triaged"
    return it


def test_a_closed_item_mentioned_in_passing_does_not_clear_a_human_impediment() -> None:
    """The reason is the barrier; the ids inside it are context.

    Measured on a consumer 2026-09-02. B-060's value reads "aguardando disposição
    de status: ... bala 2 movida para B-061 (shipped) ... Vide report B-060". The
    parser lifts both ids, the self-mention is dropped, B-061 is shipped — so no
    open id remained and the item was returned as NOT BLOCKED and handed to the
    queue as the next thing to work on. An incidental mention of a closed item had
    erased a decision a person still owes. B-126 went the same way, and the two of
    them were the entire remote queue that day.
    """
    raw = ("aguardando disposicao de status: bala 2 movida para B-061 (shipped), "
           "costura entregue. Vide report /idea-to-release B-060 de 2026-08-31.")
    statuses = {"B-060": "triaged", "B-061": "shipped"}

    blockers = live_blockers(_item_blocked_by("B-060", raw), statuses)

    assert blockers == [], "blocked, by something with no item to point at"
    assert blockers is not None, "None would put it in the queue"


def test_an_ids_only_value_whose_items_all_shipped_really_is_clear() -> None:
    """The narrowing must not trap items whose impediment genuinely ended. A value
    that is nothing but ids says nothing a closed item leaves unanswered."""
    statuses = {"B-060": "triaged", "B-061": "shipped", "B-062": "shipped"}

    assert live_blockers(
        _item_blocked_by("B-060", "B-061, B-062"), statuses) is None


def test_an_open_item_named_in_prose_is_still_the_wall_it_always_was() -> None:
    statuses = {"B-060": "triaged", "B-061": "triaged"}

    assert live_blockers(
        _item_blocked_by("B-060", "aguardando B-061 aterrissar"), statuses) == ["B-061"]


def test_prose_naming_no_item_at_all_was_already_a_wall_and_stays_one() -> None:
    """This path worked before and must keep working — it is the shape the fix
    generalises from."""
    statuses = {"B-060": "triaged"}

    assert live_blockers(
        _item_blocked_by("B-060", "aguardando decisao do sponsor"), statuses) == []


def test_an_item_held_by_a_person_is_named_as_such() -> None:
    """`AWAITING_HUMAN` was declared by five cycle rules with **Emit it.** and
    emitted by nothing.

    `check_orphan_verdicts` exists to catch exactly that and could not see it: it
    tested membership by substring, and `AWAITING_HUMAN` matched inside
    `INVALID_AWAITING_HUMAN`, in a comment. The defect hid itself, and the gate's
    own test asserted `findings == []` on the strength of that comment.

    The rules say what the absence costs, and it is measurable: "without the event
    it leaves no trace, and every reader — the board, the drift checker, the
    selector, the watchdog — sees an item that was never touched." Measured on a
    consumer on 2026-09-02: **14 items in exactly that state**, indistinguishable
    from untouched, while a fleet ran thirteen rounds reporting nothing to do.
    """
    text = "\n".join([
        item_block("B-001", status="triaged",
                   extra="blocked_by: aguardando decisao do sponsor\n"),
        item_block("B-002", status="triaged", extra="blocked_by: B-003\n"),
        item_block("B-003", status="triaged"),
    ])

    result = select(text)

    assert result.awaiting_human == ["B-001"], (
        "an impediment naming no item is a person's to open, and must be named "
        "apart from one waiting on another item")


def test_it_is_reported_even_when_there_is_work_to_do() -> None:
    """An item awaiting a person is awaiting one whether or not other work exists.
    Reporting it only on an empty queue is how 14 of them stayed invisible behind a
    queue of 5."""
    text = "\n".join([
        item_block("B-001", status="triaged",
                   extra="blocked_by: aguardando decisao do sponsor\n"),
        item_block("B-002", status="triaged"),
    ])

    result = select(text)

    assert result.verdict == "ITEM_SELECTED"
    assert result.item_id == "B-002"
    assert result.awaiting_human == ["B-001"], "held items vanished behind a non-empty queue"


def test_the_field_is_present_even_when_empty() -> None:
    """A reader that must infer "nobody is waiting on a person" from a missing key
    cannot tell it apart from a selector too old to report the field."""
    result = select(item_block("B-001", status="triaged"))

    assert result.as_dict()["awaiting_human"] == []


def test_waiting_on_another_item_is_not_awaiting_a_person() -> None:
    """The distinction is the whole point: one clears itself when the other item
    ships, the other never clears without a decision."""
    text = "\n".join([
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="triaged"),
    ])

    assert select(text).awaiting_human == []


# ── `--check <B-NNN>` on an item past the selection point ─────────────────────
#
# Nothing exercised this path, and the two tables it reads had already drifted:
# `NOT_SELECTABLE` gained `approved -> ITEM_AWAITING_PLAN` when the hypothesis /
# commitment split entered `cycle-backlog.md`, and the `nexts` lookup beside it
# did not. Every `--check` against an approved item raised KeyError instead of
# answering. Measured on a consumer's registry: 196 items, 5 approved, 5 crashes.

def test_checking_an_approved_item_answers_instead_of_crashing() -> None:
    text = _backlog(item_block("B-001", status="approved"))

    result = select(text, requested="B-001")

    assert result.verdict == "ITEM_AWAITING_PLAN"
    assert result.item_id == "B-001"


def test_every_unselectable_status_says_what_comes_next() -> None:
    """The note is the point of the verdict: it tells the reader where to go.

    A total lookup with an empty fallback would also have stopped the crash, and
    it would have answered `approved` with silence — the one status whose whole
    reason for existing is that a specific next step exists.
    """
    expected_next = {
        "approved": "/plan-write",
        "planned": "/idea-to-release",
    }
    for status, phrase in expected_next.items():
        result = select(_backlog(item_block("B-001", status=status)), requested="B-001")

        assert phrase in result.reason, f"{status} does not say where to go next"


def test_no_unselectable_status_can_lose_its_note() -> None:
    """The two tables cannot drift, because there is only one.

    This is the assertion that would have caught the original defect: a status
    added to the contract and not to the note table.
    """
    import select_backlog_item as sel

    for status in sel.NOT_SELECTABLE:
        result = select(_backlog(item_block("B-001", status=status)), requested="B-001")

        assert result.verdict == sel.NOT_SELECTABLE[status][0]
        assert result.reason, f"{status} produced no reason"


def test_a_terminal_status_is_answered_without_a_next_step() -> None:
    """`shipped` and `killed` are over. Pointing anywhere would be wrong."""
    for status in ("shipped", "killed"):
        result = select(_backlog(item_block("B-001", status=status)), requested="B-001")

        assert result.verdict in ("ITEM_SHIPPED", "ITEM_KILLED")
        assert "/" not in result.reason.split("past the point")[-1]


def test_checking_an_item_with_no_status_is_still_refused_by_the_contract() -> None:
    text = _backlog(item_block("B-001", status="wat"))

    result = select(text, requested="B-001")

    assert result.verdict == "BACKLOG_BLOCKED"
    assert "wat" in result.reason


def test_approved_items_are_reported_beside_the_queue_never_inside_it():
    """`queue` means "SELECT hands this out", and an approved item is past that point.

    Widening `queue` would send it back to `/discover-plan` to re-measure what its
    opportunity file already records. A separate key keeps both truths: the item is not
    SELECT's to hand out, and a scheduler still has to be able to see it.

    Without this key, `pipeline_orchestrator.from_selection` built its lanes from
    `queue` alone — so a consumer's registry of 87 approved and 5 triaged items handed
    the scheduler five.
    """
    text = ("# Backlog\n\n## Items\n\n"
            + item_block("B-001", status="triaged")
            + item_block("B-002", status="approved")
            + item_block("B-003", status="shipped"))
    result = select(text)
    assert "B-002" not in (result.queue or [])
    assert result.awaiting_plan == ["B-002"]
    assert "B-003" not in (result.awaiting_plan or []), "shipped is not awaiting a plan"


def test_the_awaiting_plan_key_is_always_present():
    """An absent key cannot be told from a selector too old to report it — the same
    reason `awaiting_human` is emitted when empty."""
    text = "# Backlog\n\n## Items\n\n" + item_block("B-001", status="triaged")
    assert select(text).as_dict()["awaiting_plan"] == []


def test_a_blocked_approved_item_is_not_offered_for_planning():
    """It reads `approved` on disk and cannot be worked; the queue already drops those."""
    text = ("# Backlog\n\n## Items\n\n"
            + item_block("B-001", status="approved", extra="blocked_by: B-002\n")
            + item_block("B-002", status="triaged"))
    assert select(text).awaiting_plan == []

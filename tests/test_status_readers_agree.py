"""Five readers decide on `status:` and each keeps its own copy of the values.

`backlog_status.py` owns the transitions, `check_backlog_structure.py` gates the
registry, `select_backlog_item.py` decides what may start, `board_state.py` maps
status to phase, and `backlog_index.py` renders it. None imports the others —
deliberately, because each must read a registry written by anything and cannot
inherit another's assumptions.

That independence is why the set has to be pinned across them. A sixth status
added to four of five is a status the fifth silently drops: an item in it is
neither selectable nor blocked nor rendered, and every surface reports normally.
This kit has measured that shape five times in one day, one level down, on
`blocked_by` and on item-id width — this is the same test one level up.

Sibling of `test_item_id_readers_agree.py` and `test_blocked_by_readers_agree.py`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The contract. `rules/cycle-backlog.md § Item schema` is the authority; this
#: list is the executable copy, and the first test below holds the two together.
CONTRACT_STATUSES = frozenset(
    {"raw", "triaged", "approved", "planned", "shipped", "killed"}
)

#: Every file that DECIDES using a status value, and what each is for. A file
#: that merely mentions one in prose is not here — the invariant is about
#: readers whose behaviour changes with the value.
READERS = {
    "mechanisms/cycle/backlog_status.py": "owns the transitions",
    "skills/backlog-review/scripts/check_backlog_structure.py": "gates the registry",
    "skills/backlog-review/scripts/select_backlog_item.py": "decides what may start",
    "skills/backlog-review/scripts/board_state.py": "maps status to phase",
    "skills/backlog-review/scripts/backlog_index.py": "renders the index",
    # Added 2026-09-05 by the sweep below, which found the list three short. Each
    # was missing `approved` in a way the enumerated tests could not see.
    "skills/backlog-item/scripts/check_intake_gates.py": "decides what a dedup hit means",
    "skills/backlog-review/scripts/squad_boss.py": "decides whether a halt's cause is still live",
    "skills/brainstorm-vision/scripts/build_agenda.py": "decides what reaches the agenda",
    # Moved out of EXEMPT on 2026-09-05, when the governance question kit#32 was
    # waiting on got an answer. It gates on status now (REQUIRES_STATUS), so it
    # decides, so it is pinned like the rest.
    "mechanisms/fleet/pipeline_orchestrator.py": "decides which status a finished stage may write",
}


def _statuses_named_in(path: Path) -> set[str]:
    """Status values a file names as string literals."""
    text = path.read_text(encoding="utf-8")
    found = set()
    for candidate in CONTRACT_STATUSES:
        if re.search(rf'["\']{candidate}["\']', text):
            found.add(candidate)
    return found


@pytest.mark.parametrize("rel", sorted(READERS))
def test_the_reader_exists(rel: str) -> None:
    """A reader that moved silently stops being checked by everything below."""
    assert (REPO_ROOT / rel).is_file(), f"{rel} is gone — {READERS[rel]}"


def test_the_contract_document_lists_exactly_these_statuses() -> None:
    """The executable copy above must match the document that governs it.

    `rules/cycle-backlog.md` carries the schema row enumerating the values. If
    the document gains a status and this list does not, every test below passes
    while the readers are measured against the wrong set.
    """
    rule = (REPO_ROOT / "rules" / "cycle-backlog.md").read_text(encoding="utf-8")
    row = re.search(r"(?m)^\|\s*`status`\s*\|.*$", rule)
    assert row, "rules/cycle-backlog.md has no `status` schema row"

    in_document = set(re.findall(r"`(raw|triaged|approved|planned|shipped|killed)`", row.group(0)))
    assert in_document == set(CONTRACT_STATUSES), (
        f"the rule's schema row and this test disagree.\n"
        f"  document: {sorted(in_document)}\n"
        f"  test:     {sorted(CONTRACT_STATUSES)}"
    )


def test_no_reader_names_a_status_the_contract_does_not_have() -> None:
    """A value one reader accepts and the contract does not is a value nothing
    else will ever produce — dead handling that reads as coverage."""
    for rel in sorted(READERS):
        named = _statuses_named_in(REPO_ROOT / rel)
        assert named <= CONTRACT_STATUSES, (
            f"{rel} names statuses outside the contract: {sorted(named - CONTRACT_STATUSES)}"
        )


def test_every_terminal_and_open_status_is_known_to_the_transition_owner() -> None:
    """`backlog_status.py` writes the field, so it must know every value.

    A status it does not name cannot be reached through the mechanism, which
    leaves hand-editing as the only route — and hand-editing is the failure this
    module was written to end.
    """
    named = _statuses_named_in(REPO_ROOT / "mechanisms/cycle/backlog_status.py")
    missing = CONTRACT_STATUSES - named
    assert not missing, (
        f"backlog_status.py cannot write these: {sorted(missing)}. An item can "
        f"only reach them by hand, which is what this module exists to prevent."
    )


def test_the_gate_knows_every_status_the_transition_owner_can_write() -> None:
    """Anything writable must be gateable, or the gate sweeps past it."""
    writer = _statuses_named_in(REPO_ROOT / "mechanisms/cycle/backlog_status.py")
    gate = _statuses_named_in(
        REPO_ROOT / "skills/backlog-review/scripts/check_backlog_structure.py"
    )
    missing = writer - gate
    assert not missing, (
        f"check_backlog_structure.py does not know {sorted(missing)}, which "
        f"backlog_status.py can write. An item in one of those passes the gate "
        f"by not being looked at."
    )


def test_the_index_buckets_every_status() -> None:
    """Every status must land in a bucket, or the item vanishes from the board.

    Written after this test file shipped WITHOUT it and missed exactly that. The
    `approved` status was added to the transition owner, the gate and the
    selector; `backlog_index.BUCKETS` was not, and the four assertions above all
    passed, because each of them checks a subset relation and a MISSING entry is
    a subset. The gap was caught by a skill-local test in a consumer, three
    commits later, through a failing gate chain.

    A subset check answers "does this reader invent statuses". It cannot answer
    "does this reader handle the ones that exist", and those are the two
    different ways the set can drift.
    """
    sys.path.insert(0, str(REPO_ROOT / "skills" / "backlog-review" / "scripts"))
    import backlog_index

    missing = CONTRACT_STATUSES - set(backlog_index.BUCKETS)
    assert not missing, (
        f"backlog_index.BUCKETS has no bucket for {sorted(missing)}. Those items "
        f"are collected as `unknown` and rendered outside every bucket count."
    )


def test_the_board_places_every_status() -> None:
    """Same invariant, the other renderer.

    `board_state.STATUS_PHASE` decides where an item sits when no stream event
    exists for it — which is the common case, since most items never emit one. A
    status absent from this map is an item the board cannot place at all.
    """
    sys.path.insert(0, str(REPO_ROOT / "skills" / "backlog-review" / "scripts"))
    import board_state

    missing = CONTRACT_STATUSES - set(board_state.STATUS_PHASE)
    assert not missing, (
        f"board_state.STATUS_PHASE cannot place {sorted(missing)}."
    )


def test_the_index_can_still_see_an_impediment_on_a_committed_item() -> None:
    """An item somebody committed to and then walled is the worst one to lose.

    `_STOPPABLE` decides whether a `blocked_by` line is still drawn. It listed
    the two open statuses and `planned`, so an `approved` item carrying an
    impediment would have rendered as unobstructed — and an approved item is
    precisely the one where a reader is waiting on the outcome.
    """
    sys.path.insert(0, str(REPO_ROOT / "skills" / "backlog-review" / "scripts"))
    import backlog_index

    assert "approved" in backlog_index._STOPPABLE, (
        "an approved item with a blocked_by line would render as unobstructed"
    )


def test_the_selector_classifies_every_status() -> None:
    """The selector must place every status somewhere: startable, or held.

    A status it does not name falls through to neither. The item is then absent
    from the queue AND absent from the reasons — invisible on both surfaces at
    once, which is the worst shape this registry can produce.
    """
    named = _statuses_named_in(
        REPO_ROOT / "skills/backlog-review/scripts/select_backlog_item.py"
    )
    missing = CONTRACT_STATUSES - named
    assert not missing, (
        f"select_backlog_item.py never names {sorted(missing)}. An item there is "
        f"neither offered nor explained."
    )


# ── killing a commitment is not killing a hypothesis ─────────────────────────

def _status_module():
    sys.path.insert(0, str(REPO_ROOT / "mechanisms" / "cycle"))
    import backlog_status
    return backlog_status


ITEM = """## B-001 — a title   [ ]

domain: engine
repo: theo
status: {status}
dod:
  - something falsifiable
"""


def test_killing_a_hypothesis_takes_any_stated_reason() -> None:
    """Before approval the item is a question and the measurement answered it.
    A reason that reports what the evidence showed is the whole requirement."""
    bs = _status_module()
    out = bs.advance(ITEM.format(status="triaged"), "B-001", "killed",
                     kill_reason="measured 2026-09-04: the leak does not reproduce")
    assert "status: killed" in out


def test_killing_a_commitment_needs_who_reversed_it() -> None:
    """After approval, somebody had decided. Reversing that is a decision, and a
    reason that only restates evidence does not name the decision being undone.

    This is the whole point of the `approved` state: without it, the cheapness of
    killing a hunch applied equally to work someone had committed to.
    """
    bs = _status_module()
    for status in ("approved", "planned"):
        with pytest.raises(bs.Refused) as excinfo:
            bs.advance(ITEM.format(status=status), "B-001", "killed",
                       kill_reason="the measurement did not hold up")
        assert "reversed" in str(excinfo.value).lower(), str(excinfo.value)


def test_a_commitment_killed_with_a_named_reverser_is_allowed() -> None:
    """The bar is higher, not impassable."""
    bs = _status_module()
    out = bs.advance(
        ITEM.format(status="approved"), "B-001", "killed",
        kill_reason="reversed by the sponsor 2026-09-04: the customer withdrew the "
                    "requirement this was approved for",
    )
    assert "status: killed" in out


def test_no_unenumerated_reader_decides_on_a_status() -> None:
    """READERS is a hardcoded list, and a hardcoded list drifts from the tree.

    Measured 2026-09-05, and the drift had already cost something: this file pinned
    five readers while the kit held seven. `pipeline_orchestrator.STATUS_ON_ENTERING`
    and `check_intake_gates.ACTION_BY_STATUS` both decide on status values and
    neither knew `approved`, so the pipeline could not advance an item past PLAN and
    a duplicate of an approved item fell through the dedup table. A Go reader in a
    consumer made eight.

    A test that enumerates the thing it guards has the defect it guards against.
    So the tree is swept: anything holding two or more status literals in one file
    either appears in READERS or is exempted here with the reason it does not
    decide. Two literals rather than one, because a single mention is usually prose.
    """
    import subprocess

    #: Files that name statuses without deciding on them. Each needs a reason —
    #: an exemption nobody probes is a door.
    EXEMPT = {
        # The contract itself, and this file, which quotes it.
        "rules/cycle-backlog.md",
        "tests/test_status_readers_agree.py",
        # History. Rewriting it destroys the evidence of what was true then.
        "CHANGELOG.md",
        # Tests of the readers above: they assert on statuses, they do not route on
        # them, and pinning them here would pin the pins.
        "tests/test_backlog_status.py",
        "skills/backlog-review/tests/test_select_backlog_item.py",
        "skills/backlog-review/tests/test_board_state.py",
        "skills/backlog-init/tests/test_detect_domains.py",
        "tests/test_pipeline_orchestrator.py",
        "tests/test_pipeline_does_not_approve.py",
        # Names statuses only in a comment about queue order.
        "mechanisms/fleet/squad_lead.py",
        # Tests OF the readers. They assert on statuses, they do not route on
        # them, and enumerating them here would pin the pins.
        "skills/backlog-review/tests/test_backlog_index.py",
        "skills/backlog-review/tests/test_check_backlog_structure.py",
        "skills/backlog-review/tests/test_squad_boss.py",
        "skills/brainstorm-vision/tests/test_build_agenda.py",
        "tests/test_advance_items.py",
        "tests/test_blocked_by_readers_agree.py",
        # Tests OF `backlog-approve`. They assert that a signed brief moves items to
        # `approved` and that `shipped` refuses the same move; the routing decision
        # they exercise belongs to `backlog_status.py`, which IS pinned.
        "skills/backlog-approve/tests/test_apply_approval.py",
        "skills/backlog-approve/tests/test_approval_brief.py",
        # `as-is-to-be` and its tests. The skill FILTERS by status (`--status triaged`)
        # and routes on none: every item it reads is rendered the same way whatever its
        # status says. A status added to the contract reaches it through the filter
        # without any branch here needing to change.
        "skills/as-is-to-be/tests/test_gap_analysis.py",
        "skills/as-is-to-be/scripts/build_gap_analysis.py",
        # The board's renderer, in JS. It branches on `shipped` and `killed` by
        # NAME and falls through for everything else, so a status added to the
        # contract renders in the default column rather than vanishing. Safe by
        # construction, and it would need a JS harness to pin from here.
        "skills/backlog-review/scripts/board.html",
    }

    found = subprocess.run(
        # `--untracked`: `git grep` reads the INDEX, so a reader added and not yet
        # committed is invisible to it. Measured here by mutation — dropping a new
        # file holding two status literals into the tree left this test green.
        ["git", "grep", "--untracked", "-lE",
         r'"(raw|triaged|approved|planned|shipped|killed)"'],
        cwd=REPO_ROOT, capture_output=True, text=True,
        check=False,
    )
    if found.returncode not in (0, 1):
        raise AssertionError(f"git grep failed: {found.stderr}")

    candidates = set()
    for rel in (p for p in found.stdout.split() if p):
        body = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        hits = {s for s in CONTRACT_STATUSES if f'"{s}"' in body}
        if len(hits) >= 2:
            candidates.add(rel)

    unenumerated = sorted(candidates - set(READERS) - EXEMPT)
    assert not unenumerated, (
        f"these decide on two or more status values and are neither pinned nor "
        f"exempted: {unenumerated}. A status added to the contract reaches the "
        f"pinned readers and silently misses these — which is how `approved` "
        f"stopped the pipeline advancing (kit#32)."
    )


def test_the_halt_reader_counts_a_committed_cause_as_live() -> None:
    """`squad_boss.OPEN_STATUS` decides whether a halt's cause still holds it.

    Enumerating the file in READERS proves it exists. It does not prove the set
    inside it is right — measured by mutation on 2026-09-05: removing `approved`
    from that tuple left every assertion in this file green.

    The direction of the failure is the bad one. A halt whose cause had been
    APPROVED — committed to by somebody with the authority — would read as no
    longer live, so the halt is reported resolvable while the thing holding it is
    open. An approved cause is more owned than a triaged one, not less.
    """
    sys.path.insert(0, str(REPO_ROOT / "skills" / "backlog-review" / "scripts"))
    import squad_boss

    terminal = {"shipped", "killed"}
    expected = CONTRACT_STATUSES - terminal
    missing = expected - set(squad_boss.OPEN_STATUS)
    assert not missing, (
        f"squad_boss.OPEN_STATUS is missing {sorted(missing)}. A halt whose cause "
        f"sits in one of those would be reported resolvable while the cause is "
        f"still open."
    )
    assert not (set(squad_boss.OPEN_STATUS) & terminal), (
        "a shipped or killed cause cannot be what holds anything"
    )


def test_the_intake_reader_folds_a_duplicate_into_every_open_status() -> None:
    """`check_intake_gates.ACTION_BY_STATUS` decides what a dedup hit means.

    Added to READERS by the sweep on 2026-09-05, which only proves the file exists.
    Written the same day as the halt-reader pin above and for the same reason: two
    of the three readers the sweep found had no assertion on their CONTENTS, so a
    set could go wrong inside a file this suite calls checked.

    An open status with no row falls through to "read the block before deciding",
    which reads as caution and behaves as a miss — a new item duplicating an
    approved one gets its own id, and one piece of work becomes two rows nobody
    reconciles.
    """
    sys.path.insert(0, str(REPO_ROOT / "skills" / "backlog-item" / "scripts"))
    import check_intake_gates

    open_statuses = CONTRACT_STATUSES - {"shipped", "killed"}
    missing = open_statuses - set(check_intake_gates.ACTION_BY_STATUS)
    assert not missing, (
        f"ACTION_BY_STATUS has no row for {sorted(missing)}, so a duplicate of an "
        f"item in that status falls through the table and is filed as new work."
    )
    assert all(check_intake_gates.ACTION_BY_STATUS[s] == "ITEM_MERGED"
               for s in open_statuses), (
        "every open status folds the duplicate in; only a terminal one supersedes"
    )

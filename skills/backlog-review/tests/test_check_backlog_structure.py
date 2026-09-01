"""Tests for check_backlog_structure.py — the ways a maintenance registry rots."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from backlog_fixtures import item_block, write_backlog
from check_backlog_structure import check_backlog


def _checks(report: dict) -> set[str]:
    return {f["check"] for f in report["findings"]}


def _find(report: dict, check: str) -> dict:
    return next(f for f in report["findings"] if f["check"] == check)


def test_clean_backlog_is_shippable(clean_backlog: Path) -> None:
    report = check_backlog(clean_backlog)
    assert report["verdict"] == "SHIPPABLE", report["findings"]
    assert report["items_total"] == 2


def test_status_counts(clean_backlog: Path) -> None:
    report = check_backlog(clean_backlog)
    assert report["items_by_status"]["raw"] == 1
    assert report["items_by_status"]["triaged"] == 1


def test_duplicate_id_is_a_blocker(tmp_path: Path) -> None:
    report = check_backlog(write_backlog(tmp_path, item_block("B-001"), item_block("B-001", "Outro")))
    assert "duplicate_id" in _checks(report)
    assert report["verdict"] == "INVALID"


def test_non_monotonic_ids_are_a_blocker(tmp_path: Path) -> None:
    """A reused or reordered id makes every earlier reference ambiguous."""
    report = check_backlog(write_backlog(tmp_path, item_block("B-005"), item_block("B-002", "Outro")))
    assert "renumbered" in _checks(report)
    assert report["verdict"] == "INVALID"


def test_triaged_without_evidence_is_a_blocker(tmp_path: Path) -> None:
    """Triaged means measured. Without evidence the status is a claim nobody made."""
    report = check_backlog(write_backlog(tmp_path, item_block(status="triaged", evidence="none-yet")))
    assert "triaged_without_evidence" in _checks(report)
    assert report["verdict"] == "INVALID"


def test_raw_carrying_evidence_is_flagged(tmp_path: Path) -> None:
    """Measurement happened and nobody advanced the status — the rot this loop prevents."""
    report = check_backlog(write_backlog(tmp_path, item_block(status="raw", evidence="src/x.ts:12")))
    assert "raw_with_evidence" in _checks(report)


def test_killed_without_reason_is_flagged(tmp_path: Path) -> None:
    report = check_backlog(write_backlog(tmp_path, item_block(status="killed")))
    assert "killed_without_reason" in _checks(report)


def test_killed_with_reason_is_clean(tmp_path: Path) -> None:
    report = check_backlog(
        write_backlog(tmp_path, item_block(status="killed", extra="kill_reason: measured, 1 query per request\n"))
    )
    assert "killed_without_reason" not in _checks(report)


def test_illegal_status_is_a_blocker(tmp_path: Path) -> None:
    report = check_backlog(write_backlog(tmp_path, item_block(status="in-progress")))
    assert "illegal_status" in _checks(report)
    assert report["verdict"] == "INVALID"


def test_invalid_mode_is_flagged(tmp_path: Path) -> None:
    report = check_backlog(write_backlog(tmp_path, item_block(suggested_mode="vibes")))
    assert "invalid_mode" in _checks(report)


def test_missing_field_is_flagged(tmp_path: Path) -> None:
    block = item_block().replace("why_now: the dashboard started loading 30d by default\n", "")
    report = check_backlog(write_backlog(tmp_path, block))
    assert "missing_field" in _checks(report)


ROUTING_TABLE = """# Cycle: BACKLOG

## Domain routing

| Domain | Repos | Specialist |
|---|---|---|
| `data-plane-ts` | `theo-lens`, `theo-memory` | `agents/data-plane-ts.md` |
| `platform-cli` | `theo-cli` | `agents/platform-cli.md` |

## Next
"""


def _with_routing_table(tmp_path: Path) -> Path:
    """Plant a real routing table next to the backlog so the G1 check actually runs."""
    rules = tmp_path / "rules"
    rules.mkdir(exist_ok=True)
    (rules / "cycle-backlog.md").write_text(ROUTING_TABLE, encoding="utf-8")
    return tmp_path


def test_unroutable_repo_is_a_blocker(tmp_path: Path) -> None:
    """A repo in no domain routes to nobody — gate G1.

    Plants a routing table so the check is genuinely exercised. Without one the checker
    correctly declines to judge, and the assertion would pass for the wrong reason: the
    check never ran.
    """
    _with_routing_table(tmp_path)
    report = check_backlog(write_backlog(tmp_path, item_block(repo="theo-gateway")))
    assert report["routing_table_read"] is True
    assert "unroutable_repo" in _checks(report)
    assert report["verdict"] == "INVALID"


def test_routable_repo_produces_no_finding(tmp_path: Path) -> None:
    _with_routing_table(tmp_path)
    report = check_backlog(write_backlog(tmp_path, item_block(repo="theo-lens")))
    assert report["routing_table_read"] is True
    assert "unroutable_repo" not in _checks(report)


def test_unreadable_routing_table_does_not_assert_violations(tmp_path: Path) -> None:
    """Missing data must not become a reported violation.

    With no routing table, every repo would look unroutable. Reporting that would assert
    a violation the evidence does not support — the same defect the thresholds resolver
    had when it silently used the wrong bands.
    """
    report = check_backlog(write_backlog(tmp_path, item_block(repo="anything-at-all")))
    assert report["routing_table_read"] is False
    assert "unroutable_repo" not in _checks(report)


def test_thin_dod_is_flagged(tmp_path: Path) -> None:
    report = check_backlog(write_backlog(tmp_path, item_block(dod=[])))
    assert "thin_dod" in _checks(report)


def test_vague_dod_is_heuristic_not_deterministic(tmp_path: Path) -> None:
    report = check_backlog(write_backlog(tmp_path, item_block(dod=["melhorar a performance"])))
    assert "vague_dod" in _checks(report)
    assert _find(report, "vague_dod")["kind"] == "heuristic"


def test_dod_with_a_number_is_not_vague(tmp_path: Path) -> None:
    """A criterion that happens to mention speed is still falsifiable.

    Flagging "p95 below 800ms" because it contains "fast"-adjacent wording would train
    people to ignore the check, which costs more than the false negatives it prevents.
    """
    report = check_backlog(write_backlog(tmp_path, item_block(dod=["p95 abaixo de 800ms, mais rápido que hoje"])))
    assert "vague_dod" not in _checks(report)


def test_stale_raw_is_flagged(tmp_path: Path) -> None:
    report = check_backlog(
        write_backlog(tmp_path, item_block(status="raw", registered="2026-01-01")),
        today=date(2026, 8, 5),
    )
    assert "stale_raw" in _checks(report)
    assert _find(report, "stale_raw")["kind"] == "heuristic"


def test_recent_raw_is_not_stale(tmp_path: Path) -> None:
    report = check_backlog(
        write_backlog(tmp_path, item_block(status="raw", registered="2026-08-01")),
        today=date(2026, 8, 5),
    )
    assert "stale_raw" not in _checks(report)


def test_possible_duplicate_between_open_items(tmp_path: Path) -> None:
    report = check_backlog(
        write_backlog(
            tmp_path,
            item_block("B-001", "Reduce round-trips in the trace listing"),
            item_block("B-002", "Reduce round-trips in the explorer trace listing"),
        )
    )
    assert "possible_duplicate" in _checks(report)


def test_closed_items_are_not_duplicate_candidates(tmp_path: Path) -> None:
    """A shipped item and a new one about the same area is normal — that is a follow-up.

    Only OPEN items compete for the same work; flagging closed ones would make every
    recurring area look duplicated forever.
    """
    report = check_backlog(
        write_backlog(
            tmp_path,
            item_block("B-001", "Reduce round-trips in the trace listing", status="shipped"),
            item_block("B-002", "Reduce round-trips in the explorer trace listing"),
        )
    )
    assert "possible_duplicate" not in _checks(report)


def test_verdict_is_derived_from_findings(tmp_path: Path) -> None:
    """The verdict is computed, never asserted — same discipline as the scorers."""
    blocker = check_backlog(write_backlog(tmp_path, item_block(status="bogus")))
    assert blocker["severity_counts"]["blocker"] >= 1 and blocker["verdict"] == "INVALID"

    major = check_backlog(write_backlog(tmp_path, item_block(dod=[])))
    assert major["severity_counts"]["blocker"] == 0 and major["verdict"] == "NEEDS_REVISION"

    minor = check_backlog(write_backlog(tmp_path, item_block(dod=["melhorar a performance"])))
    assert minor["severity_counts"]["major"] == 0 and minor["verdict"] == "SHIPPABLE_WITH_CAVEATS"


def test_every_finding_declares_its_kind(tmp_path: Path) -> None:
    """A reader must be able to tell "the machine is sure" from "a human should look"."""
    report = check_backlog(
        write_backlog(tmp_path, item_block(status="bogus", dod=["melhorar tudo"], suggested_mode="vibes"))
    )
    assert report["findings"]
    for f in report["findings"]:
        assert f["kind"] in ("deterministic", "heuristic"), f


def test_a_duplicated_status_is_a_blocker(tmp_path: Path) -> None:
    """Two `status:` lines leave the block with two answers, and every reader takes the last.

    Measured on theo-db: B-021 carries `raw` then `triaged`, B-022 `planned` then `raw`. The
    index buckets on status, so an ambiguous one makes the summary arbitrary rather than
    wrong-in-a-way-you-can-see.
    """
    backlog = write_backlog(tmp_path, item_block("B-001", status="raw", extra="status: triaged\n"))
    report = check_backlog(backlog)
    dup = [f for f in report["findings"] if f["check"] == "duplicate_field"]
    assert len(dup) == 1
    assert dup[0]["severity"] == "blocker"
    assert "raw then triaged" in dup[0]["message"]


def test_other_repeated_fields_are_not_reported(tmp_path: Path) -> None:
    """`partial_progress` four times on theo-cloud's B-031 is an append-one-line-per-increment
    log the team keeps on purpose, and `evidence: none-yet` followed by a pointer is an item that
    advanced. A gate that reports those is one people learn to override."""
    backlog = write_backlog(
        tmp_path,
        item_block("B-001", extra="partial_progress: primeira metade\npartial_progress: segunda\n"),
    )
    report = check_backlog(backlog)
    assert [f for f in report["findings"] if f["check"] == "duplicate_field"] == []


# ── impediment edges ──────────────────────────────────────────────────────────
#
# Items stopped being independent when `blocked_by` gave them edges, which is why
# cycle detection — dropped when this file was written — came back.


def _blocked(tmp_path: Path, *blocks: str) -> dict:
    return check_backlog(write_backlog(tmp_path, *blocks))


def test_an_edge_to_an_unfiled_item_is_a_blocker(tmp_path: Path) -> None:
    report = _blocked(tmp_path, item_block("B-001", status="triaged", extra="blocked_by: B-404\n"))
    assert "blocker_missing" in _checks(report)
    assert report["verdict"] == "INVALID"


def test_an_item_blocking_itself_is_caught(tmp_path: Path) -> None:
    report = _blocked(tmp_path, item_block("B-001", status="triaged", extra="blocked_by: B-001\n"))
    assert "self_block" in _checks(report)


def test_a_two_item_ring_is_reported_once(tmp_path: Path) -> None:
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw", extra="blocked_by: B-001\n"),
    )
    rings = [f for f in report["findings"] if f["check"] == "blocker_cycle"]
    assert len(rings) == 1, rings
    assert report["verdict"] == "INVALID"


def test_a_three_item_ring_is_reported_once(tmp_path: Path) -> None:
    """Keyed by membership, not entry point — otherwise one deadlock reads as three."""
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw", extra="blocked_by: B-003\n"),
        item_block("B-003", status="raw", extra="blocked_by: B-001\n"),
    )
    assert len([f for f in report["findings"] if f["check"] == "blocker_cycle"]) == 1


def test_a_chain_without_a_ring_is_clean(tmp_path: Path) -> None:
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw", extra="blocked_by: B-003\n"),
        item_block("B-003", status="raw"),
    )
    assert "blocker_cycle" not in _checks(report)


def test_an_edge_whose_blockers_all_closed_is_stale(tmp_path: Path) -> None:
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="shipped"),
    )
    assert "stale_block" in _checks(report)


def test_a_live_edge_is_not_stale(tmp_path: Path) -> None:
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw"),
    )
    assert "stale_block" not in _checks(report)


def test_a_closed_item_with_an_open_blocker_is_incoherent(tmp_path: Path) -> None:
    report = _blocked(
        tmp_path,
        item_block("B-001", status="shipped", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw"),
    )
    assert "closed_but_blocked" in _checks(report)


# ── the field as it was already used, before it was specified ─────────────────


def test_a_prose_impediment_is_not_malformed(tmp_path: Path) -> None:
    """Seven of the eight real values named no item at all. None is a defect."""
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: decisão do patrocinador\n"),
    )
    assert not {"blocker_missing", "stale_block"} & _checks(report)


def test_an_id_named_inside_prose_still_becomes_an_edge(tmp_path: Path) -> None:
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-404 — confirmado por medição\n"),
    )
    assert "blocker_missing" in _checks(report)


def test_an_edge_carrying_prose_is_never_called_stale(tmp_path: Path) -> None:
    """Nothing here can tell whether a sponsor ratified; saying so would be a lie."""
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-002 — and the sponsor must ratify\n"),
        item_block("B-002", status="shipped"),
    )
    assert "stale_block" not in _checks(report)


def test_none_declares_no_impediment(tmp_path: Path) -> None:
    report = _blocked(tmp_path, item_block("B-001", status="triaged", extra="blocked_by: none\n"))
    assert not {"blocker_missing", "stale_block", "self_block"} & _checks(report)


# ── the derived state ─────────────────────────────────────────────────────────


def test_effective_state_replaces_the_stage_while_a_blocker_is_open(tmp_path: Path) -> None:
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw"),
    )
    assert report["items_by_effective_state"]["blocked"] == 1
    assert report["items_by_status"]["triaged"] == 1


def test_effective_state_needs_no_second_edit_when_the_blocker_ships(tmp_path: Path) -> None:
    report = _blocked(
        tmp_path,
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="shipped"),
    )
    assert "blocked" not in report["items_by_effective_state"]

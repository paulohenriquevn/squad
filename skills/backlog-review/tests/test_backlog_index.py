"""The index that opens BACKLOG.md — generated, and checked against the items it summarises.

The tests that matter here are not "does it render a table". They are the two ways a summary
betrays a reader: saying an item is closed when it is open, and pointing at a detail block that
is not there.
"""
from __future__ import annotations

from pathlib import Path

from backlog_fixtures import item_block, write_backlog
from backlog_index import (
    BUCKETS,
    END,
    START,
    anchor,
    apply_index,
    index_is_current,
    render_index,
)
from check_backlog_structure import LEGAL_STATUS, _parse_items


def _indexed(tmp_path: Path, *blocks: str) -> tuple[Path, str]:
    path = write_backlog(tmp_path, *blocks)
    content = path.read_text(encoding="utf-8")
    written = apply_index(content, render_index(content, _parse_items(content)))
    path.write_text(written, encoding="utf-8")
    return path, written


class TestBuckets:
    def test_every_legal_status_has_a_bucket(self) -> None:
        """A status the contract allows and this table does not know would vanish from the
        summary — counted nowhere, listed nowhere. The registry would under-report itself."""
        assert set(BUCKETS) == LEGAL_STATUS

    def test_triaged_counts_as_open_not_in_flight(self) -> None:
        """Measurement has run, but no plan exists. `in-flight` answers "what is someone building
        right now?", and folding `triaged` into it makes that number answer a different question."""
        assert BUCKETS["triaged"] == "open"
        assert BUCKETS["planned"] == "in-flight"

    def test_killed_counts_as_closed(self) -> None:
        """Killing an item is a successful ending, not a pending one — `cycle-discover.md`."""
        assert BUCKETS["killed"] == "closed"


class TestStaleness:
    """The whole reason the index is generated rather than written."""

    def test_a_fresh_index_is_current(self, tmp_path: Path) -> None:
        _, written = _indexed(tmp_path, item_block("B-001"))
        assert index_is_current(written)[0]

    def test_an_index_is_stale_after_an_item_changes_status(self, tmp_path: Path) -> None:
        """The failure this exists to catch: the summary keeps claiming `raw` while the block
        below it says `shipped`. Nothing else in the registry compares the two."""
        path, _ = _indexed(tmp_path, item_block("B-001", status="raw"))
        content = path.read_text(encoding="utf-8")
        head, _, tail = content.partition(END)
        moved = head + END + tail.replace("status: raw", "status: shipped")
        assert not index_is_current(moved)[0]

    def test_an_index_is_stale_when_a_new_item_is_appended(self, tmp_path: Path) -> None:
        path, _ = _indexed(tmp_path, item_block("B-001"))
        appended = path.read_text(encoding="utf-8") + item_block("B-002", "Segundo item")
        assert not index_is_current(appended)[0]

    def test_a_backlog_with_no_index_is_stale(self, tmp_path: Path) -> None:
        """Absent counts as stale, not as exempt. Otherwise a registry opts out of the check by
        never having the section — which is exactly how the four on disk got to 592 items and
        zero index rows."""
        path = write_backlog(tmp_path, item_block("B-001"), index=False)
        assert not index_is_current(path.read_text(encoding="utf-8"))[0]

    def test_regenerating_twice_is_idempotent(self, tmp_path: Path) -> None:
        """A generator that keeps producing a new answer for unchanged input makes every run a
        diff, and a diff on every run is how people stop reading them."""
        _, once = _indexed(tmp_path, item_block("B-001"), item_block("B-002", "Outro"))
        twice = apply_index(once, render_index(once, _parse_items(once)))
        assert twice == once


class TestLinks:
    def test_every_row_links_to_a_heading_that_exists(self, tmp_path: Path) -> None:
        """A link into a detail block that is not there is the registry's version of a routing
        table naming a specialist nobody wrote."""
        import re

        _, written = _indexed(
            tmp_path,
            item_block("B-001", "Reduce round-trips in the listing"),
            item_block("B-002", "Corrigir exit code do deploy parcial", status="shipped"),
        )
        index = written[written.index(START) : written.index(END)]
        targets = set(re.findall(r"\]\(#([^)]+)\)", index))
        assert targets

        headings = {
            anchor(line.lstrip("#").strip())
            for line in written.splitlines()
            if line.startswith("## B-")
        }
        assert targets <= headings, f"links resolving to nothing: {sorted(targets - headings)}"

    def test_the_anchor_keeps_the_repeated_hyphens(self) -> None:
        """`B-018 — Title   [x]` really does render an anchor with doubled and tripled hyphens.
        Collapsing them here would look tidier and produce links that go nowhere."""
        assert anchor("B-018 — Nineteen files   [x]") == "b-018--nineteen-files---x"

    def test_the_anchor_drops_punctuation_and_keeps_case_folded(self) -> None:
        assert anchor("B-004 — Ask-bridge: promise abandoned   [x]") == (
            "b-004--ask-bridge-promise-abandoned---x"
        )


class TestPlacement:
    def test_the_index_lands_before_the_item_registry(self, tmp_path: Path) -> None:
        _, written = _indexed(tmp_path, item_block("B-001"))
        assert written.index(START) < written.index("## B-001")

    def test_both_spellings_of_the_registry_heading_are_anchored_on(self, tmp_path: Path) -> None:
        """`Items`, `Itens` and `Itens abertos` are all on disk in this ecosystem. Anchoring on one
        would append the index to the end of the file for the others — the one place nobody reads."""
        for heading in ("## Items", "## Itens", "## Itens abertos"):
            body = f"# Backlog\n\n{heading}\n\n" + item_block("B-001")
            out = apply_index(body, render_index(body, _parse_items(body)))
            assert out.index(START) < out.index(heading)

    def test_a_second_run_replaces_rather_than_stacks(self, tmp_path: Path) -> None:
        _, once = _indexed(tmp_path, item_block("B-001"))
        twice = apply_index(once, render_index(once, _parse_items(once)))
        assert twice.count(START) == 1

    def test_it_does_not_land_inside_another_derived_block(self) -> None:
        """`theo` opens its BACKLOG with a derived block of its own titled `## Itens abertos`.

        Anchoring on the registry heading's TEXT matched that heading, so the index was inserted
        inside somebody else's generated block — and the next regeneration of it ate the
        insertion silently. `--write` reported success and the marker was gone afterwards.
        The anchor is now a position (the last heading before the first item), not a name.
        """
        body = (
            "# Backlog\n\n"
            "<!-- OPEN-INDEX:BEGIN -->\n\n## Itens abertos\n\n| x |\n\n<!-- OPEN-INDEX:END -->\n\n"
            "## Items\n\n"
        ) + item_block("B-001")
        out = apply_index(body, render_index(body, _parse_items(body)))
        assert out.index("<!-- OPEN-INDEX:END -->") < out.index(START)
        assert out.index(START) < out.index("## Items")


class TestUnknownStatus:
    def test_an_unknown_status_is_surfaced_not_swallowed(self, tmp_path: Path) -> None:
        """If the contract grows a status, the index must SAY it does not know it. Dropping the
        item would make the registry under-report itself, quietly."""
        body = "# Backlog\n\n## Items\n\n" + item_block("B-001", status="parked")
        index = render_index(body, _parse_items(body))
        assert "B-001" in index
        assert "status this index does not know" in index


# ── impediment links, both directions ─────────────────────────────────────────
#
# Only one direction is stored. `blocks` is derived, so the two halves cannot drift.

from backlog_index import impediment_graph, lineage_chains  # noqa: E402


def _items(*blocks: str) -> list:
    from check_backlog_structure import _parse_items
    return _parse_items("".join(blocks))


def test_the_reverse_edge_is_derived(tmp_path: Path) -> None:
    items = _items(
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw"),
    )
    blocked_by, blocks = impediment_graph(items)
    assert blocked_by["B-001"] == ["B-002"]
    assert blocks["B-002"] == ["B-001"]


def test_one_blocker_holding_two_items_lists_both() -> None:
    items = _items(
        item_block("B-001", status="triaged", extra="blocked_by: B-100\n"),
        item_block("B-002", status="triaged", extra="blocked_by: B-100\n"),
        item_block("B-100", status="raw"),
    )
    _, blocks = impediment_graph(items)
    assert blocks["B-100"] == ["B-001", "B-002"]


def test_a_shipped_blocker_produces_no_edge() -> None:
    """Resolution needs no second edit — the edge disappears when the blocker closes."""
    items = _items(
        item_block("B-001", status="triaged", extra="blocked_by: B-002\n"),
        item_block("B-002", status="shipped"),
    )
    blocked_by, blocks = impediment_graph(items)
    assert blocked_by == {} and blocks == {}


def test_a_prose_impediment_blocks_with_no_edge() -> None:
    items = _items(item_block("B-001", status="triaged", extra="blocked_by: the sponsor must decide\n"))
    blocked_by, blocks = impediment_graph(items)
    assert blocked_by["B-001"] == []
    assert blocks == {}


def test_a_shipped_item_is_never_listed_as_blocked() -> None:
    items = _items(
        item_block("B-001", status="shipped", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw"),
    )
    blocked_by, _ = impediment_graph(items)
    assert "B-001" not in blocked_by


def test_the_rendered_index_shows_the_derived_state_and_the_stage(tmp_path: Path) -> None:
    """A reader needs both: the state to know it is stuck, the stage to know where it resumes."""
    from backlog_index import render_index

    content = "".join([
        item_block("B-001", status="planned", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw"),
    ])
    rendered = render_index(content, _parse_items(content))
    row = next(line for line in rendered.splitlines() if line.startswith("| [`B-001`]"))
    assert "blocked" in row and "planned" in row and "B-002" in row


def test_the_rendered_index_counts_blocked_items(tmp_path: Path) -> None:
    from backlog_index import render_index

    content = "".join([
        item_block("B-001", status="planned", extra="blocked_by: B-002\n"),
        item_block("B-002", status="raw"),
    ])
    rendered = render_index(content, _parse_items(content))
    assert "**Blocked** 1" in rendered


def test_an_unblocked_backlog_shows_no_blocked_count(tmp_path: Path) -> None:
    from backlog_index import render_index

    content = item_block("B-001", status="planned")
    rendered = render_index(content, _parse_items(content))
    assert "Blocked" not in rendered


# --- lineage: how many times has this been tried? (kit#55, step 3) ------------


def test_a_two_link_chain_reports_both_ancestors_newest_first() -> None:
    """B-200 regressed from B-050, which superseded B-012. That is a third attempt.

    The registry held every piece of this and could not answer the question,
    because nothing walked the edges (kit#55).
    """
    items = _items(
        item_block("B-012", status="killed", extra="kill_reason: measured, did not hold\n"),
        item_block("B-050", status="shipped", extra="supersedes: B-012\n"),
        item_block("B-200", status="raw", extra="regression_of: B-050\n"),
    )
    chains = lineage_chains(items)
    assert chains["B-200"] == ["B-050", "B-012"]


def test_an_item_with_no_ancestor_has_no_chain() -> None:
    """Most items are the first attempt, and that is not a fact worth printing."""
    items = _items(item_block("B-001", status="raw"))
    assert lineage_chains(items) == {}


def test_an_edge_naming_an_undefined_id_stops_the_walk_without_raising() -> None:
    """The index renders a registry the checker may not have passed yet.

    `check_backlog_structure` reports `lineage_missing` for this; the index must
    still render, and must not silently drop the part of the chain it CAN see.
    """
    items = _items(
        item_block("B-050", status="shipped", extra="supersedes: B-999\n"),
        item_block("B-200", status="raw", extra="regression_of: B-050\n"),
    )
    chains = lineage_chains(items)
    assert chains["B-200"] == ["B-050", "B-999"]
    assert chains["B-050"] == ["B-999"]


def test_a_corrupt_ring_terminates_instead_of_hanging() -> None:
    """A lineage ring is unreachable by the contract and cheap to survive anyway.

    The checker has no cycle gate here BECAUSE the edge points only at terminal
    items. That argument is about a well-formed registry; this function reads one
    that may be mid-edit, and a walker that trusts the argument hangs the index.
    """
    items = _items(
        item_block("B-001", status="killed", extra="kill_reason: x\nsupersedes: B-002\n"),
        item_block("B-002", status="killed", extra="kill_reason: y\nsupersedes: B-001\n"),
    )
    chains = lineage_chains(items)
    assert chains["B-001"] == ["B-002"]
    assert chains["B-002"] == ["B-001"]


def test_the_index_names_the_attempt_number(tmp_path: Path) -> None:
    """The row says it out loud, because the chain is why the item looks familiar."""
    from backlog_index import render_index
    items = _items(
        item_block("B-012", status="killed", extra="kill_reason: measured, did not hold\n"),
        item_block("B-050", status="shipped", extra="supersedes: B-012\n"),
        item_block("B-200", status="raw", extra="regression_of: B-050\n"),
    )
    rendered = render_index("", items)
    assert "3rd attempt" in rendered
    assert "B-050" in rendered

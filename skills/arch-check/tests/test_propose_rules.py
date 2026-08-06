"""The rule proposer — every candidate has to come from a measurement.

The tests here exist to pin two opposite failures. Proposing a rule the repo does not already
obey ships a config that fails on its first run, which teaches everyone to ignore it. Proposing
nothing when the graph is real wastes the only cheap moment to adopt boundaries. The refusal
tests are the important ones: a proposer that answers confidently about a codebase it never read
is the same defect the D5 meta-gate exists to catch.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from propose_rules import (  # noqa: E402
    Graph,
    _iter_json_objects,
    _unit_of_import,
    _unit_of_path,
    find_cycles,
    independent_pairs,
    one_way_candidates,
    propose,
)


def _graph(*edges: tuple[str, str, int]) -> Graph:
    g = Graph()
    for source, target, times in edges:
        g.see(source)
        g.see(target)
        for _ in range(times):
            g.add(source, target)
    return g


class TestOneWayCandidates:
    def test_a_one_way_edge_becomes_a_rule(self) -> None:
        [candidate] = one_way_candidates(_graph(("tui", "agents", 33)))
        assert (candidate.source, candidate.target) == ("agents", "tui")
        assert "33 import(s)" in candidate.evidence

    def test_traffic_in_both_directions_proposes_nothing(self) -> None:
        """There is no invariant to freeze — and a rule here would fail on its first run."""
        assert one_way_candidates(_graph(("a", "b", 5), ("b", "a", 1))) == []

    def test_the_rule_forbids_the_direction_that_is_empty(self) -> None:
        """Getting this backwards would forbid the 33 imports that actually exist."""
        [candidate] = one_way_candidates(_graph(("tui", "agents", 33)))
        assert candidate.source == "agents", "must forbid agents importing tui, not the reverse"

    def test_a_self_edge_is_not_a_dependency(self) -> None:
        assert one_way_candidates(_graph(("a", "a", 9))) == []


class TestIndependentPairs:
    def test_two_participating_units_that_never_meet_are_siblings(self) -> None:
        graph = _graph(("tui", "agents", 3), ("exec", "agents", 2))
        pairs = {(c.source, c.target) for c in independent_pairs(graph)}
        assert ("exec", "tui") in pairs

    def test_units_that_do_exchange_imports_are_not_siblings(self) -> None:
        graph = _graph(("tui", "exec", 1), ("exec", "agents", 2))
        assert ("exec", "tui") not in {(c.source, c.target) for c in independent_pairs(graph)}

    def test_a_unit_outside_the_graph_yields_no_pair(self) -> None:
        """Two directories with no edges at all are unrelated, not siblings — a rule between them
        would govern nothing, and D5 would then report it as vacuous."""
        graph = _graph(("a", "b", 1))
        graph.see("orphan")
        assert all("orphan" not in (c.source, c.target) for c in independent_pairs(graph))


class TestFindCycles:
    def test_an_acyclic_graph_has_none(self) -> None:
        assert find_cycles(_graph(("a", "b", 1), ("b", "c", 1))) == []

    def test_a_two_unit_cycle_is_found(self) -> None:
        assert find_cycles(_graph(("a", "b", 1), ("b", "a", 1))) == [("a", "b")]

    def test_a_longer_cycle_is_found(self) -> None:
        cycles = find_cycles(_graph(("a", "b", 1), ("b", "c", 1), ("c", "a", 1)))
        assert cycles == [("a", "b", "c")]


class TestPropose:
    def test_an_unread_repo_is_refused_not_answered(self) -> None:
        """The failure this whole file guards against: tree-sitter degrades to an empty result,
        so an empty graph is reachable without any error being raised."""
        result = propose(Graph())
        assert result["status"] == "refused"
        assert result["candidates"] == []

    def test_units_seen_but_no_imports_is_independence_not_refusal(self) -> None:
        """theo-contracts, measured: jwt, plan and serviceauth import none of each other."""
        graph = Graph()
        for unit in ("jwt", "plan", "serviceauth"):
            graph.see(unit)
        result = propose(graph)
        assert result["status"] == "proposed"
        assert [c["kind"] for c in result["candidates"]] == ["independence"]

    def test_one_unit_alone_is_refused(self) -> None:
        graph = Graph()
        graph.see("only")
        assert propose(graph)["status"] == "refused"

    def test_no_circular_is_proposed_when_there_are_no_cycles(self) -> None:
        result = propose(_graph(("a", "b", 1)))
        assert result["candidates"][0]["kind"] == "no-circular"

    def test_no_circular_is_withheld_when_a_cycle_exists(self) -> None:
        """Adopting it here would ship a config that is red on arrival."""
        result = propose(_graph(("a", "b", 1), ("b", "a", 1)))
        assert all(c["kind"] != "no-circular" for c in result["candidates"])
        assert result["not_proposed"][0]["kind"] == "no-circular"
        assert "backlog" in result["not_proposed"][0]["reason"]

    def test_every_candidate_carries_its_measurement(self) -> None:
        """A rule without the number that justifies it is the rule the next refactor deletes."""
        result = propose(_graph(("tui", "agents", 4), ("exec", "agents", 2)))
        for candidate in result["candidates"]:
            assert candidate["evidence"].strip(), candidate


class TestUnitResolution:
    def test_an_import_outside_the_module_is_not_a_unit(self) -> None:
        assert _unit_of_import("github.com/other/x/y", "github.com/us/repo") == ""

    def test_the_first_segment_under_the_module_is_the_unit(self) -> None:
        assert _unit_of_import("github.com/us/repo/internal/db", "github.com/us/repo") == "internal"

    def test_the_module_root_itself_is_not_a_unit(self) -> None:
        assert _unit_of_import("github.com/us/repo", "github.com/us/repo") == ""

    def test_a_vendored_path_is_not_a_unit(self) -> None:
        assert _unit_of_import("github.com/us/repo/vendor/x", "github.com/us/repo") == ""

    def test_a_file_at_the_root_has_no_unit(self, tmp_path: Path) -> None:
        assert _unit_of_path(tmp_path / "main.ts", tmp_path) == ""

    def test_a_file_in_a_directory_takes_that_directory(self, tmp_path: Path) -> None:
        assert _unit_of_path(tmp_path / "agents" / "goal" / "x.ts", tmp_path) == "agents"

    def test_a_path_outside_the_root_has_no_unit(self, tmp_path: Path) -> None:
        assert _unit_of_path(Path("/elsewhere/x.ts"), tmp_path) == ""


class TestGoListParsing:
    def test_concatenated_objects_are_all_read(self) -> None:
        """`go list -json` emits objects back to back, not a JSON array."""
        assert list(_iter_json_objects('{"a":1}\n{"a":2}\n')) == [{"a": 1}, {"a": 2}]

    def test_a_truncated_stream_stops_instead_of_raising(self) -> None:
        assert list(_iter_json_objects('{"a":1}\n{"a":')) == [{"a": 1}]

    def test_an_empty_stream_yields_nothing(self) -> None:
        assert list(_iter_json_objects("")) == []

"""Tests for route_domain.py — deterministic repo -> domain -> specialist routing."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from route_domain import parse_routing_table, route  # noqa: E402


RULE = PROJECT_ROOT / "rules" / "cycle-backlog.md"


@pytest.fixture(scope="module")
def table() -> dict:
    return parse_routing_table(RULE)


def test_routing_table_parses(table: dict) -> None:
    assert table, "the table parsed to zero rows — every item would be unroutable"
    assert len(table) == 8


def test_every_domain_declares_an_agent(table: dict) -> None:
    missing = [d for d, e in table.items() if not e["agent"]]
    assert missing == [], f"domains with no specialist declared: {missing}"


def test_every_declared_agent_exists_on_disk(table: dict) -> None:
    """The guard that makes the table more than prose.

    A domain naming an agent file that does not exist routes work to nobody, and the
    failure is silent: the item looks routed. Adding a domain without writing its
    specialist must fail here rather than at the moment someone tries to use it.
    """
    for domain, entry in table.items():
        agent_path = PROJECT_ROOT / entry["agent"]
        assert agent_path.is_file(), f"{domain} -> {entry['agent']} does not exist"


def test_every_agent_on_disk_is_reachable_from_the_table(table: dict) -> None:
    """The other direction: an agent nobody routes to is dead weight.

    Without this, a specialist can be written, reviewed and merged while no item can
    ever reach it — the work looks done and changes nothing.
    """
    declared = {entry["agent"] for entry in table.values()}
    on_disk = {
        f"agents/{p.name}"
        for p in (PROJECT_ROOT / "agents").glob("*.md")
        if p.name != "README.md"
    }
    assert on_disk - declared == set(), f"agents nothing routes to: {sorted(on_disk - declared)}"


def test_no_repo_belongs_to_two_domains(table: dict) -> None:
    """Gate G3 assumes one repo maps to exactly one specialist.

    A repo in two rows makes routing order-dependent — the same item would route
    differently depending on dict iteration, which is the worst kind of wrong: it works
    until it does not, and nothing changed.
    """
    seen: dict[str, str] = {}
    for domain, entry in table.items():
        for repo in entry["repos"]:
            assert repo not in seen, f"`{repo}` is in both {seen[repo]} and {domain}"
            seen[repo] = domain


@pytest.mark.parametrize(
    "repo,expected_domain",
    [
        ("theo", "engine-go"),
        ("theo-cloud", "control-plane"),
        ("theo-traefik-mcp", "control-plane"),
        ("theo-lens", "data-plane-ts"),
        ("theo-memory", "data-plane-ts"),
        ("theo-db", "theo-db"),
        ("theo-contracts", "contracts-auth"),
        ("theo-infra-live", "infra-terraform"),
        ("theo-cli", "platform-cli"),
        ("theo-storage", "platform-cli"),
    ],
)
def test_known_repos_route(table: dict, repo: str, expected_domain: str) -> None:
    result = route(repo, table)
    assert result is not None, f"`{repo}` did not route"
    assert result[0] == expected_domain


def test_uncloned_repo_does_not_route(table: dict) -> None:
    """Repos the umbrella's CLAUDE.md names but disk does not must NOT route.

    Measured 2026-08-05: theo-contextify, theo-gateway, theo-sandboox, theokit-app and
    theo-itself have no checkout. Routing an item to a repo nobody cloned sends it to a
    specialist who cannot open the code — so gate G1 refuses it instead.
    """
    for repo in ("theo-contextify", "theo-gateway", "theo-sandboox", "theokit-app", "theo-itself"):
        assert route(repo, table) is None, f"`{repo}` routed, but it has no checkout"


def test_unknown_repo_does_not_route(table: dict) -> None:
    assert route("some-other-project", table) is None


def test_missing_section_raises(tmp_path: Path) -> None:
    rule = tmp_path / "no-section.md"
    rule.write_text("# Cycle: BACKLOG\n\n## Purpose\n\nText.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Domain routing"):
        parse_routing_table(rule)


def test_empty_table_raises(tmp_path: Path) -> None:
    """Zero rows must be an error, never an empty dict.

    An empty dict would make every repo silently unroutable while the script exits 0 —
    the same shape as the thresholds file that parsed to zero bands and sent every score
    to INVALID.
    """
    rule = tmp_path / "empty.md"
    rule.write_text("# X\n\n## Domain routing\n\nNo table here.\n\n## Next\n", encoding="utf-8")
    with pytest.raises(ValueError, match="zero rows"):
        parse_routing_table(rule)


def test_every_domain_has_at_least_one_repo(table: dict) -> None:
    """A domain with zero repos is unreachable, and silently so.

    Caught in practice: `theo-cloud/dashboard` contains a slash, the repo pattern did not
    allow one, and `frontend-dashboard` parsed to an EMPTY repo list. Every other test
    still passed — an empty list violates no uniqueness assertion, declares an agent that
    exists, and looks entirely healthy. The domain simply could never receive an item.

    Zero repos must fail loudly here, because nothing downstream will notice.
    """
    empty = [d for d, e in table.items() if not e["repos"]]
    assert empty == [], f"domains no item can reach: {empty}"


def test_path_scoped_repo_routes(table: dict) -> None:
    """A repo split across domains is addressed by path, and the path must route."""
    result = route("theo-cloud/dashboard", table)
    assert result is not None, "the path-scoped dashboard identifier did not route"
    assert result[0] == "frontend-dashboard"

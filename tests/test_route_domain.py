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


def test_a_domain_naming_a_missing_specialist_exits_3(tmp_path, capsys) -> None:
    """The invariant moved from this file into the tool, and this pins that it moved.

    It lived only here, and `install.sh` does not copy `tests/` — so in every consumer repo the
    guard was absent. Measured while installing into TheoCode: a second three-column table inside
    `## Domain routing` parses as routing, inventing domains whose specialist files were never
    written, and `route_domain.py` answered `routed: true` / `agent: null` with exit 0.
    """
    from route_domain import main as route_main

    (tmp_path / "rules").mkdir()
    (tmp_path / "agents").mkdir()
    (tmp_path / "rules" / "cycle-backlog.md").write_text(
        "## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `ghost` | `some-repo` | `agents/ghost.md` |\n\n"
        "## Verdicts\n",
        encoding="utf-8",
    )
    code = route_main(["some-repo", "--rule", str(tmp_path / "rules" / "cycle-backlog.md")])
    assert code == 3
    assert "BROKEN ROUTE" in capsys.readouterr().out


def test_a_domain_whose_specialist_exists_still_routes(tmp_path) -> None:
    """The refusal must not swallow the normal case."""
    from route_domain import main as route_main

    (tmp_path / "rules").mkdir()
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "real.md").write_text("# real\n", encoding="utf-8")
    (tmp_path / "rules" / "cycle-backlog.md").write_text(
        "## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `real` | `some-repo` | `agents/real.md` |\n\n"
        "## Verdicts\n",
        encoding="utf-8",
    )
    assert route_main(["some-repo", "--rule", str(tmp_path / "rules" / "cycle-backlog.md")]) == 0


def test_item_repo_field_accepts_a_monorepo_path(tmp_path: Path) -> None:
    """`repo: packages/sdk` num arquivo de item tem de chegar inteiro ao roteador.

    A tabela sempre aceitou caminho (`theo-cloud/dashboard`, documentado como "um
    repo, dois domínios — resolvido por caminho"), mas o extrator do ITEM parava
    na barra e devolvia `packages`. O roteamento então falhava por um repo que
    ninguém escreveu. Descoberto ao derivar a tabela do `theokit-sdk`, onde 68 dos
    88 itens citam `packages/sdk`.
    """
    item = tmp_path / "item.md"
    item.write_text("## B-001 — algo\n\nrepo: packages/sdk\nstatus: raw\n", encoding="utf-8")
    from route_domain import ITEM_REPO_RE

    match = ITEM_REPO_RE.search(item.read_text(encoding="utf-8"))
    assert match is not None
    assert match.group(1) == "packages/sdk"


def _table_with(rows: str, tmp_path: Path) -> Path:
    """A minimal rule file carrying only a `## Domain routing` section."""
    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\n"
        "| Domain | Packages | Specialist |\n|---|---|---|\n" + rows,
        encoding="utf-8",
    )
    return rule


def test_a_repo_in_two_domains_is_refused_by_the_parser(tmp_path: Path) -> None:
    """The one-repo-one-domain invariant belongs to the TOOL, not to this suite.

    `test_no_repo_belongs_to_two_domains` above asserts it for THIS repository's table, and
    that is all it can do: it hard-codes `RULE = PROJECT_ROOT / "rules" / "cycle-backlog.md"`
    and `len(table) == 8`. Every consumer install carries its own table with its own domain
    count, and `install.sh` does not copy `tests/` — so in a consumer repo the invariant was
    asserted by nobody, exactly as the exit-3 guard was before it moved into the tool.

    Measured in the theokit-plugins install on 2026-08-24: 11 packages across 4 domains, and
    nothing anywhere checks that none of them appears twice. A repo in two rows makes routing
    depend on dict iteration order — the same item routing differently on different runs.

    So the parser refuses it, which is what makes the guarantee travel with the tool.
    """
    rule = _table_with(
        "| `alpha` | `pkg-one`, `pkg-two` | `agents/alpha.md` |\n"
        "| `beta` | `pkg-two` | `agents/beta.md` |\n",
        tmp_path,
    )

    with pytest.raises(ValueError, match=r"pkg-two.*(alpha|beta)"):
        parse_routing_table(rule)


def test_the_same_repo_twice_in_ONE_domain_is_not_a_duplicate(tmp_path: Path) -> None:
    """Two mentions in one row route identically, so nothing is ambiguous.

    Without this, the guard could be written as a naive count and would reject a table that
    is merely repetitive — turning a cosmetic edit into a broken install.
    """
    rule = _table_with(
        "| `alpha` | `pkg-one`, `pkg-one` | `agents/alpha.md` |\n",
        tmp_path,
    )

    assert parse_routing_table(rule)["alpha"]["repos"].count("pkg-one") == 2

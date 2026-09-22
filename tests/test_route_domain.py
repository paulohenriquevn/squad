"""Tests for route_domain.py — deterministic repo -> domain -> specialist routing.

WHY THESE TESTS NAME NO REPOSITORIES
------------------------------------
Until 2026-08-26 half of this file measured the table of the ecosystem the kit was
written in: `len(table) == 8`, `("web-console", "data-plane-ts")`, five repos with no
checkout. The eight specialists that table named left the kit (the table is DERIVED
from the project, `rules/cycle-backlog.md § Domain routing`), and with them goes any
possibility of asserting about a concrete map — this repository may have a table,
may not, or may have one entirely different from yesterday's.

What survives is stronger: the router's STRUCTURAL invariants, exercised against
synthetic tables, plus both directions of consistency between this repository's
table and the specialists on disk — whatever they are.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "mechanisms" / "cycle" / "route_domain.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for kit_agents
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from kit_agents import kit_agents  # noqa: E402 — post-bootstrap import

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "mechanisms" / "cycle"))

from route_domain import (  # noqa: E402 — post-bootstrap import
    count_candidate_rows,
    parse_routing_table,
    route,
)

RULE = PROJECT_ROOT / "rules" / "cycle-backlog.md"
AGENTS_DIR = PROJECT_ROOT / "agents"


def _table_with(rows: str, tmp_path: Path) -> Path:
    """A minimal rule file carrying only a `## Domain routing` section."""
    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\n"
        "| Domain | Packages | Specialist |\n|---|---|---|\n" + rows,
        encoding="utf-8",
    )
    return rule


# ---------------------------------------------------------------------------
# THIS repository's table — whatever state it is in
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def table() -> dict | None:
    """This project's derived table, or None while nobody has derived it.

    Empty is a LEGITIMATE state — it is how the kit is born and how it ships
    (`rules/templates/domain-routing.md`). A test demanding rows here would force
    the kit's repository to invent a map in order to stay green.
    """
    try:
        return parse_routing_table(RULE)
    except ValueError:
        return None


def test_the_section_exists_and_says_how_to_fill_itself() -> None:
    """With no table AND no instruction, emptiness becomes a mystery instead of a task.

    `parse_routing_table` distinguishes the two cases by exception — 'no section' is
    a corrupted file, 'zero rows' is configuration still to be derived. The section
    must always exist, and must name the script that fills it.
    """
    body = RULE.read_text(encoding="utf-8-sig")
    assert "## Domain routing" in body, "the section vanished — route_domain.py exits 2 on everything"
    assert "detect_domains.py" in body, (
        "the section does not name the script that derives the table — whoever finds "
        "it empty never discovers that filling it is their job"
    )


def test_the_repository_table_is_internally_consistent(table: dict | None) -> None:
    """The three invariants of the real table, in a test that NEVER skips.

    Each has a synthetic counterpart further down, exercising the parser and the
    tool. Here they apply to THIS repository's table — which is empty today, so the
    body is vacuously satisfied. Written that way on purpose: a `skip` while nobody
    has derived the table is a test that disappears from the report and comes back
    without anyone noticing. This one grows teeth on its own the day
    `detect_domains.py --write` runs here.

      1. Every domain declares a specialist, and the file exists — pointing at a
         file nobody wrote routes into the void, and the item LOOKS routed.
      2. A repo belongs to exactly one domain — gate G3 depends on it, and two rows
         make the routing follow dict iteration order.
      3. Every domain has at least one repo — zero repos is unreachable, silently.
    """
    seen: dict[str, str] = {}
    for domain, entry in (table or {}).items():
        assert entry["agent"], f"domain with no declared specialist: {domain}"
        assert (PROJECT_ROOT / entry["agent"]).is_file(), (
            f"{domain} -> {entry['agent']} does not exist on disk"
        )
        assert entry["repos"], f"domain no item can reach: {domain}"
        for repo in entry["repos"]:
            assert repo not in seen or seen[repo] == domain, (
                f"`{repo}` is in both {seen[repo]} and {domain}"
            )
            seen[repo] = domain


def test_every_specialist_on_disk_is_reachable_from_the_table(table: dict | None) -> None:
    """The other direction: a specialist nothing routes to is dead weight.

    Without this, a domain file can be written, reviewed and merged while no item
    can reach it — the work looks done and changes nothing. It holds even with an
    empty table, which is when the mismatch is easiest to create.
    """
    declared = {entry["agent"] for entry in (table or {}).values()}
    on_disk = {
        f"agents/{p.name}" for p in AGENTS_DIR.glob("*.md")
        if p.name not in kit_agents()
    }
    orphans = sorted(on_disk - declared)
    assert orphans == [], (
        f"specialists the table does not reach: {orphans}. Declare them in "
        f"`rules/cycle-backlog.md § Domain routing` or remove them."
    )


# ---------------------------------------------------------------------------
# The router, against synthetic tables
# ---------------------------------------------------------------------------

def test_a_known_repo_routes_to_its_domain(tmp_path: Path) -> None:
    table = parse_routing_table(
        _table_with(
            "| `alpha` | `pkg-one`, `pkg-two` | `agents/alpha.md` |\n"
            "| `beta` | `pkg-three` | `agents/beta.md` |\n",
            tmp_path,
        )
    )
    assert route("pkg-two", table) == ("alpha", "agents/alpha.md")
    assert route("pkg-three", table) == ("beta", "agents/beta.md")


def test_an_unknown_repo_does_not_route(tmp_path: Path) -> None:
    """Gate G1 refuses the item instead of sending it to someone who cannot open the code."""
    table = parse_routing_table(
        _table_with("| `alpha` | `pkg-one` | `agents/alpha.md` |\n", tmp_path)
    )
    assert route("some-other-project", table) is None


def test_a_path_scoped_repo_routes(tmp_path: Path) -> None:
    """A repo split across domains is addressed by path, and the path must route.

    Caught in practice: the identifier contained a slash, the repo pattern did not
    accept one, and the domain parsed with an EMPTY repo list. Every other test still
    passed — an empty list violates no uniqueness assertion, declares an agent that
    exists, and looks entirely healthy. The domain simply could never receive an item.
    """
    table = parse_routing_table(
        _table_with(
            "| `service` | `alpha-cloud` | `agents/service.md` |\n"
            "| `ui` | `alpha-cloud/dashboard` | `agents/ui.md` |\n",
            tmp_path,
        )
    )
    assert table["ui"]["repos"] == ["alpha-cloud/dashboard"], "a barra truncou o repo"
    assert route("alpha-cloud/dashboard", table) == ("ui", "agents/ui.md")
    assert route("alpha-cloud", table) == ("service", "agents/service.md")


def test_missing_section_raises(tmp_path: Path) -> None:
    rule = tmp_path / "no-section.md"
    rule.write_text("# Cycle: BACKLOG\n\n## Purpose\n\nText.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Domain routing"):
        parse_routing_table(rule)


def test_empty_table_raises(tmp_path: Path) -> None:
    """Zero rows must be an error, never an empty dict.

    An empty dict would leave every repo silently unreachable while the script exits
    0 — the same shape as the thresholds file that parsed to zero bands and sent
    every score to INVALID.
    """
    rule = tmp_path / "empty.md"
    rule.write_text("# X\n\n## Domain routing\n\nNo table here.\n\n## Next\n", encoding="utf-8")
    with pytest.raises(ValueError, match="zero rows"):
        parse_routing_table(rule)


def test_the_routing_file_a_consumer_is_born_with_parses_to_zero_rows(tmp_path) -> None:
    """The routing file the consumer receives must carry no domain of the kit's.

    If it parsed to a domain, every consumer would be born with a ghost that accepts no
    item and reports success — the defect measured on an adopter in 2026-08-18, where 88
    items were refused as `unroutable_repo` against a map from another ecosystem.

    THE ASSERTION MOVED WITH THE FILE, 2026-09-21. It used to open
    `<kit>/rules/domain-routing.txt`, because that is where the kit shipped a placeholder
    from. `squad.paths` had been writing the table to the project's write root since
    2026-09-11, so the kit was copying a placeholder into the one directory no writer
    fills, and recreating it on every reinstall.

    Checking the artifact the CONSUMER receives is the stronger test anyway: the old one
    held a file in this repository to a property that mattered somewhere else.
    """
    import subprocess

    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    done = subprocess.run(
        ["bash", str(PROJECT_ROOT / "mechanisms" / "distribution" / "install.sh"),
         str(tmp_path)],
        capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr

    sys.path.insert(0, str(PROJECT_ROOT))
    from squad.paths import write_routing_table

    born_with = write_routing_table(tmp_path)
    assert born_with.is_file(), "the consumer received no routing table at all"
    with pytest.raises(ValueError, match="no routing row"):
        parse_routing_table(born_with)


def test_a_domain_naming_a_missing_specialist_exits_3(tmp_path, capsys) -> None:
    """The invariant moved from this file into the tool, and this pins the move.

    It lived only here, and `install.sh` does not copy `tests/` — so in every
    consumer repository the guard was absent. Measured while installing into
    a TypeScript monorepo: a second three-column table inside `## Domain routing` parses as
    routing, inventing domains whose specialist files were never written, and
    `route_domain.py` answered `routed: true` / `agent: null` with exit 0.
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
    """`repo: packages/sdk` in an item file must reach the router whole.

    The table always accepted paths (documented as "one repo, two domains — resolved
    by path"), but the ITEM extractor stopped at the slash and returned `packages`.
    Routing then failed on a repo nobody wrote. Discovered while deriving an
    adopter's table, where 68 of the 88 items cite `packages/sdk`.
    """
    item = tmp_path / "item.md"
    item.write_text("## B-001 — algo\n\nrepo: packages/sdk\nstatus: raw\n", encoding="utf-8")
    from route_domain import ITEM_REPO_RE

    match = ITEM_REPO_RE.search(item.read_text(encoding="utf-8"))
    assert match is not None
    assert match.group(1) == "packages/sdk"


def test_a_repo_in_two_domains_is_refused_by_the_parser(tmp_path: Path) -> None:
    """The one-repo-one-domain invariant belongs to the TOOL, not to this suite.

    `test_the_repository_table_is_internally_consistent` above asserts it for THIS
    repository's table, and that is all it can do. Every consumer carries its own,
    with its own domain count, and `install.sh` does not copy `tests/` — so in a
    consumer repo the invariant was asserted by nobody, exactly as the exit-3 guard
    was before it moved into the tool.

    Measured on an install on 2026-08-24: 11 packages across 4 domains, and nothing
    anywhere checked that none of them appeared twice. A repo in two rows makes
    routing depend on dict iteration order — the same item routing differently
    between runs.
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

    Without this, the guard could be written as a naive count and would reject a
    merely repetitive table — turning a cosmetic edit into a broken install.
    """
    rule = _table_with(
        "| `alpha` | `pkg-one`, `pkg-one` | `agents/alpha.md` |\n",
        tmp_path,
    )

    assert parse_routing_table(rule)["alpha"]["repos"].count("pkg-one") == 2


# ── The table moved out of the kit's contract file ───────────────────────────


def test_the_table_is_read_from_the_projects_own_file(tmp_path: Path) -> None:
    """`rules/domain-routing.txt` is where the routing table lives.

    It used to be a section inside `rules/cycle-backlog.md`, which holds fifteen
    sections of the KIT's contract and exactly one thing belonging to the
    project. Everything that went wrong followed from that mixture:

    - `boundary-check.py` blocks `rules/*.md` as the kit's, so the kit invited an
      edit to a file it forbade editing — and `detect_domains.py --write` wrote
      there anyway, through `Path.write_text`, which no hook intercepts.
    - The section had to be replaced by regex, and the regex took the invariants
      with it.
    - The installer had to perform surgery to keep the consumer's table across a
      reinstall, in one of its two modes.

    `rules/*.txt` is already the allowlisted home for project configuration, and
    is already preserved by a reinstall. Moving the table there deletes all three
    problems rather than guarding against them.
    """
    routing = tmp_path / "domain-routing.txt"
    routing.write_text(
        "# comment ignored\n"
        "api      | svc-a, svc-b | agents/api.md\n"
        "frontend | web          | agents/frontend.md\n",
        encoding="utf-8",
    )
    table = parse_routing_table(routing)
    assert table == {
        "api": {"repos": ["svc-a", "svc-b"], "agent": "agents/api.md"},
        "frontend": {"repos": ["web"], "agent": "agents/frontend.md"},
    }


def test_a_markdown_table_still_parses(tmp_path: Path) -> None:
    """Consumers who have not migrated keep working.

    Readers fall back, writers do not — the same rule `resolve_knowledge_dir`
    follows for the wiki migration, and for the same reason: the kit cannot run
    anything inside another project's repository, so a hard cut breaks every
    consumer that updates without migrating.
    """
    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(
        "# x\n\n## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `api` | `svc-a` | `agents/api.md` |\n\n## Verdicts\n",
        encoding="utf-8",
    )
    assert parse_routing_table(rule) == {"api": {"repos": ["svc-a"], "agent": "agents/api.md"}}


def test_one_repo_one_domain_still_holds_in_the_new_format(tmp_path: Path) -> None:
    """The invariant is enforced regardless of which file the table came from.

    It is the reason the gate exists: a repo in two rows makes `route()` depend
    on dict iteration order, so the same item routes to a different specialist
    between runs with nothing having changed. Moving the table must not move the
    check out of its way.
    """
    routing = tmp_path / "domain-routing.txt"
    routing.write_text(
        "api      | shared | agents/api.md\n"
        "frontend | shared | agents/frontend.md\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="two domains"):
        parse_routing_table(routing)


def test_a_specialist_path_in_plugin_layout_is_recognised(tmp_path: Path) -> None:
    """`.claude/agents/x.md` is the same specialist as `agents/x.md`.

    `AGENT_RE` required the path to start with `agents/`, so a consumer that
    wrote the plugin-layout path — which is the correct path in a plugin
    install, and what `/backlog-init` prints there — had its specialist read as
    absent. Measured on an adopter: two domains, both with a specialist file
    on disk, both parsed with `agent: None`.

    A markdown link wrapping it is the same again. The consumers that wrote
    their table by hand all used `[`path`](path)`, because that is what makes it
    clickable in the registry they read.
    """
    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(
        "## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `tui-library` | an adopter | [`.claude/agents/tui-library.md`](.claude/agents/tui-library.md) |\n"
        "| `plain` | `svc-b` | `agents/plain.md` |\n\n## Verdicts\n",
        encoding="utf-8",
    )
    table = parse_routing_table(rule)
    assert table["tui-library"]["agent"] == "agents/tui-library.md"
    assert table["plain"]["agent"] == "agents/plain.md"


def test_rows_the_parser_skipped_are_countable(tmp_path: Path) -> None:
    """A partial parse must be distinguishable from a complete one.

    Migration turns this into a correctness question. Measured on `website`: a
    table of four domains — one repository, so domains are areas of
    responsibility and the second column lists PATHS — parsed to exactly one, and
    the migration wrote it out as if it were the whole map. A consumer would open
    `domain-routing.txt`, see one authoritative-looking row, and have lost three.

    Refusing to migrate is the correct answer there. But refusing requires
    KNOWING the parse was partial, which requires counting the rows that looked
    like data and did not become domains.

    Only the first contiguous table of the section counts. A second table under
    the same heading — an adopter keeps `| Domain | Reason |` for exclusions
    right below — is not a failed routing table, and counting its rows would
    refuse a migration that is complete.
    """
    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(
        "## Domain routing\n\n"
        "| Domain | Covers |\n|---|---|\n"
        "| `assistant` | `agents/` — the agent |\n"
        "| `site` | `app/` — pages |\n"
        "\n"
        "| Excluded | Reason |\n|---|---|\n"
        "| `other` | not maintained |\n\n## Verdicts\n",
        encoding="utf-8",
    )
    assert count_candidate_rows(rule.read_text(encoding="utf-8")) == 2


def test_a_broken_route_says_what_goes_in_the_missing_file(tmp_path, capsys) -> None:
    """Exit 3 must be a starting point, not a dead end.

    The message said the specialist file was absent and stopped there. Refusing
    to GENERATE it is right — `agents/README.md` requires build commands *that
    were checked*, and its closing line says a derived skeleton "routes correctly
    and judges nothing, which reads as a specialist that is ready". A generator
    would produce a plausible list, which is the fabricated-mechanism defect in
    new clothes.

    But refusing to fabricate the invariants is not the same as refusing to say
    what an invariant IS. The person hitting exit 3 has to open the file next;
    telling them the five requirements and the repos already known costs nothing
    and is the difference between a gate and a dead end.
    """
    from route_domain import main as route_main

    (tmp_path / "rules").mkdir()
    (tmp_path / "agents").mkdir()
    (tmp_path / "rules" / "domain-routing.txt").write_text(
        "api | svc-a, svc-b | agents/api.md\n", encoding="utf-8")

    assert route_main(["svc-a", "--rule", str(tmp_path / "rules" / "domain-routing.txt")]) == 3

    out = capsys.readouterr().out
    assert "invariants" in out.lower(), "must name what the file has to carry"
    assert "svc-a" in out and "svc-b" in out, "must hand over the repos already derived"
    assert "agents/README.md" in out, "must point at the contract rather than restate it whole"


# ── where the table is looked for ─────────────────────────────────────────────
#
# Every test above either passes `--rule` or calls the parser directly, which is
# how the defect below survived: nothing exercised the resolution that decides
# WHICH table gets parsed.

def _consumer_tree(root: Path, *, under_dot_claude: bool = False) -> Path:
    """A project with its own routing table and its own specialist on disk."""
    base = root / ".claude" if under_dot_claude else root
    (base / "rules").mkdir(parents=True, exist_ok=True)
    (base / "agents").mkdir(parents=True, exist_ok=True)
    (base / "rules" / "domain-routing.txt").write_text(
        "backend | my-service | agents/backend.md\n", encoding="utf-8"
    )
    (base / "agents" / "backend.md").write_text("# backend\n", encoding="utf-8")
    return root


def _route(project: Path, target: str, env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project), **env_extra}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.update(env_extra)
    return subprocess.run(  # noqa: PLW1510 — the returncode is the assertion
        [sys.executable, str(_SCRIPT), target, "--json"],
        capture_output=True, text=True, cwd=str(project), env=env,
    )


def test_it_routes_from_the_consumers_table_when_the_kit_lives_outside_the_project(
    tmp_path: Path,
) -> None:
    """The plugin-native layout, which is the one the manifest describes.

    `.claude-plugin/plugin.json`: "the kit's CODE lives outside the project, under
    $CLAUDE_PLUGIN_ROOT, and the project keeps only the cycle's DATA (records/,
    rules/*.txt, agents/*.md)."

    The root was derived from `Path(__file__)` — the mechanism's own location —
    which in that layout is inside the kit, and the kit has `rules/`, so the walk
    stopped there on its first step and parsed the empty table the kit ships.
    Reproduced 2026-09-08 (#37): exit 2, FATAL, naming the kit's path, with a
    perfectly good table sitting in the project.
    """
    project = _consumer_tree(tmp_path / "proj")

    done = _route(project, "my-service", {"CLAUDE_PLUGIN_ROOT": str(_REPO)})

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    payload = json.loads(done.stdout)
    assert payload["routed"] is True
    assert payload["domain"] == "backend"


def test_it_finds_the_table_under_dot_claude_in_a_copy_install(tmp_path: Path) -> None:
    """The copy install keeps working — `.claude/rules/` and `.claude/agents/`."""
    project = _consumer_tree(tmp_path / "proj", under_dot_claude=True)

    done = _route(project, "my-service", {})

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert json.loads(done.stdout)["routed"] is True


def test_it_routes_from_a_subdirectory_of_the_project(tmp_path: Path) -> None:
    """An agent invokes this from wherever it is standing."""
    project = _consumer_tree(tmp_path / "proj")
    deep = project / "services" / "api"
    deep.mkdir(parents=True)

    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project),
           "CLAUDE_PLUGIN_ROOT": str(_REPO)}
    done = subprocess.run(
        [sys.executable, str(_SCRIPT), "my-service", "--json"],
        capture_output=True, text=True, cwd=str(deep), env=env,
     check=False)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert json.loads(done.stdout)["routed"] is True


def test_an_explicit_rule_path_still_wins(tmp_path: Path) -> None:
    """`--rule` is the operator saying which table; nothing may second-guess it."""
    project = _consumer_tree(tmp_path / "proj")
    other = tmp_path / "elsewhere"
    (other / "agents").mkdir(parents=True)
    (other / "rules").mkdir(parents=True)
    (other / "rules" / "domain-routing.txt").write_text(
        "infra | terraform | agents/infra.md\n", encoding="utf-8"
    )
    (other / "agents" / "infra.md").write_text("# infra\n", encoding="utf-8")

    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    done = subprocess.run(
        [sys.executable, str(_SCRIPT), "terraform", "--json",
         "--rule", str(other / "rules" / "domain-routing.txt")],
        capture_output=True, text=True, cwd=str(project), env=env,
     check=False)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert json.loads(done.stdout)["domain"] == "infra"


def test_an_explicit_project_root_is_the_only_subject_considered(tmp_path: Path) -> None:
    """A caller that names its subject is not second-guessed.

    `check_intake_gates.py` judges the project it was pointed at, which need not
    be the one the shell stands in — and before `--project-root` existed it relied
    on the `__file__` walk to infer that, which is #37 one level up.
    """
    project = _consumer_tree(tmp_path / "proj")
    elsewhere = _consumer_tree(tmp_path / "other")
    (elsewhere / "rules" / "domain-routing.txt").write_text(
        "infra | my-service | agents/infra.md\n", encoding="utf-8"
    )
    (elsewhere / "agents" / "infra.md").write_text("# infra\n", encoding="utf-8")

    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(elsewhere)}
    done = subprocess.run(
        [sys.executable, str(_SCRIPT), "my-service", "--json",
         "--project-root", str(project)],
        capture_output=True, text=True, cwd=str(elsewhere), env=env,
     check=False)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert json.loads(done.stdout)["domain"] == "backend", (
        "the named project lost to the environment or the working directory"
    )


def test_a_row_missing_a_field_is_named_not_skipped(tmp_path: Path) -> None:
    """`rules/domain-routing.txt` is hand-edited configuration.

    A row missing its trailing `|` is a plausible edit, and `_rows_from_txt` dropped it
    with a bare `continue`. The domain then routed nowhere: `route_domain` printed
    UNROUTED for every repository that row owned, and the cause — one malformed line —
    appeared in no output. `parse_roster` and `parse_registry` already raise with the
    line number for exactly this shape.
    """
    table = tmp_path / "domain-routing.txt"
    table.write_text("# a comment\n"
                     "api | service-a, service-b | agents/api.md\n"
                     "ui | dashboard\n",  # the trailing field is gone
                     encoding="utf-8")

    with pytest.raises(ValueError, match="line 3"):
        parse_routing_table(table)


def test_a_row_with_no_domain_is_named(tmp_path: Path) -> None:
    table = tmp_path / "domain-routing.txt"
    table.write_text(" | service-a | agents/api.md\n", encoding="utf-8")

    with pytest.raises(ValueError, match="domain cell is empty"):
        parse_routing_table(table)


def test_a_well_formed_table_still_parses(tmp_path: Path) -> None:
    """The refusals must be about the malformed row, not about the format."""
    table = tmp_path / "domain-routing.txt"
    table.write_text("# header\n\napi | service-a, service-b | agents/api.md\n",
                     encoding="utf-8")

    parsed = parse_routing_table(table)

    assert parsed["api"]["repos"] == ["service-a", "service-b"]

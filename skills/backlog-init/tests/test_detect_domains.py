"""The routing table is project data, and it used to live inside the template.

`rules/cycle-backlog.md § Domain routing` used to embed 8 domains from the
ecosystem the kit was written in. Every install copied that table, and
`backlog-init` instructed people to classify the target's repos *inside* those 8,
forbidding them to "invent a ninth domain". The result, measured on `theokit-sdk`:
88 items with measured `file:line` evidence, all `BLOCKER/unroutable_repo`,
because `packages/sdk` and `theokit-sdk` do not exist in another ecosystem's map.

The gate was right to refuse — it did not know who to send the work to. What was
wrong was the table arriving ready-made from outside.
"""
from __future__ import annotations

from pathlib import Path

from detect_domains import detect_domains, render_table, rewrite_routing_section


def _repo(root: Path, name: str, *, git: bool = True) -> Path:
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    if git:
        (path / ".git").mkdir(exist_ok=True)
    return path


def test_single_repo_becomes_one_domain_named_after_it(tmp_path: Path) -> None:
    root = _repo(tmp_path, "theokit-sdk")
    domains = detect_domains(root)
    assert [d.name for d in domains] == ["theokit-sdk"]
    assert domains[0].repos == ["theokit-sdk"]
    assert domains[0].agent == "agents/theokit-sdk.md"


def test_npm_monorepo_lists_each_package_by_path(tmp_path: Path) -> None:
    """The theokit-sdk case: one repo, several packages, items citing `packages/x`.

    A single domain — there is one SDK, not six teams. The packages enter as
    path-addressed repos, a form the kit already supports.
    """
    root = _repo(tmp_path, "theokit-sdk")
    for pkg in ("sdk", "acp", "sdk-pty"):
        (root / "packages" / pkg).mkdir(parents=True)
        (root / "packages" / pkg / "package.json").write_text("{}", encoding="utf-8")
    (root / "node_modules" / "lodash").mkdir(parents=True)
    (root / "node_modules" / "lodash" / "package.json").write_text("{}", encoding="utf-8")

    domains = detect_domains(root)
    assert len(domains) == 1
    assert domains[0].repos == ["theokit-sdk", "packages/acp", "packages/sdk", "packages/sdk-pty"]


def test_go_workspace_modules_become_repos(tmp_path: Path) -> None:
    root = _repo(tmp_path, "theo")
    (root / "go.work").write_text("go 1.22\n\nuse (\n\t./api\n\t./operators\n\t../sibling\n)\n",
                                  encoding="utf-8")
    (root / "api").mkdir()
    (root / "operators").mkdir()
    domains = detect_domains(root)
    assert domains[0].repos == ["theo", "api", "operators"]  # the sibling outside the repo stays out


def test_umbrella_gives_one_domain_per_checked_out_repo(tmp_path: Path) -> None:
    """Umbrella workspace: the unit of ownership is the repository."""
    root = tmp_path / "umbrella"
    root.mkdir()
    _repo(root, "theo-lens")
    _repo(root, "theo-db")
    (root / "docs").mkdir()  # no .git — not a repo, does not become a domain
    domains = detect_domains(root)
    assert [d.name for d in domains] == ["theo-db", "theo-lens"]
    assert all(d.repos == [d.name] for d in domains)


def test_rendered_table_is_parseable_by_route_domain(tmp_path: Path) -> None:
    """The real contract: what comes out here must go into route_domain's parser."""
    import sys
    root = _repo(tmp_path, "theokit-sdk")
    (root / "packages" / "sdk").mkdir(parents=True)
    (root / "packages" / "sdk" / "package.json").write_text("{}", encoding="utf-8")

    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\n| Domain | Repos | Specialist |\n"
        "|---|---|---|\n| `velho` | `outro-eco` | `agents/velho.md` |\n\n"
        "## Verdicts\n\nintocado\n",
        encoding="utf-8",
    )
    rewrite_routing_section(rule, detect_domains(root))

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from route_domain import parse_routing_table, route

    table = parse_routing_table(rule)
    assert "velho" not in table, "a tabela do outro ecossistema tem de sair"
    assert route("packages/sdk", table) == ("theokit-sdk", "agents/theokit-sdk.md")
    assert route("theokit-sdk", table) == ("theokit-sdk", "agents/theokit-sdk.md")
    assert "## Verdicts" in rule.read_text(encoding="utf-8"), "the rest of the file survives"


def test_render_names_the_specialist_files_that_must_exist(tmp_path: Path) -> None:
    """route_domain exits 3 when the table names an agent that is not on disk —
    trading 88 blockers for that error would not be a fix."""
    root = _repo(tmp_path, "theokit-sdk")
    table = render_table(detect_domains(root))
    assert "agents/theokit-sdk.md" in table


# ---------------------------------------------------------------------------
# Deriving from the BACKLOG. Topology gives what EXISTS; it does not give the
# propriedade. Medido no theokit-sdk: o registro declara `sdk-core`,
# `repo-platform`, `sdk-satellites`, `edge-cli-acp` e `memory-adapters` — cinco
# SEMANTICS of ownership — domains no directory layout reveals, which the items carry.
# ---------------------------------------------------------------------------

from detect_domains import domains_from_backlog  # noqa: E402

_BACKLOG = """# Backlog

## B-001 — um   [ ]

domain: sdk-core
repo: packages/sdk
status: triaged

## B-002 — dois   [ ]

domain: repo-platform
repo: theokit-sdk
status: triaged

## B-003 — tres   [ ]

domain: sdk-satellites
repo: packages/sdk-pty
status: raw

## B-004 — quatro   [ ]

domain: sdk-core
repo: packages/sdk
status: raw
"""


def test_domains_come_from_the_pairs_the_items_declare(tmp_path: Path) -> None:
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_BACKLOG, encoding="utf-8")
    root = _repo(tmp_path, "theokit-sdk")
    (root / "packages" / "sdk").mkdir(parents=True)
    (root / "packages" / "sdk-pty").mkdir(parents=True)

    domains = domains_from_backlog(backlog, root)
    assert [d.name for d in domains] == ["repo-platform", "sdk-core", "sdk-satellites"]
    assert next(d for d in domains if d.name == "sdk-core").repos == ["packages/sdk"]
    assert next(d for d in domains if d.name == "sdk-core").agent == "agents/sdk-core.md"


def test_a_repo_the_items_cite_but_disk_does_not_have_is_surfaced(tmp_path: Path) -> None:
    """A repo that exists only in the registry routes to code nobody opens —
    the same divergence a hand-kept table documents instead of deleting."""
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_BACKLOG, encoding="utf-8")
    root = _repo(tmp_path, "theokit-sdk")
    (root / "packages" / "sdk").mkdir(parents=True)  # sdk-pty does NOT exist

    domains = domains_from_backlog(backlog, root)
    satellites = next(d for d in domains if d.name == "sdk-satellites")
    assert satellites.repos == ["packages/sdk-pty"]
    assert satellites.missing_on_disk == ["packages/sdk-pty"]


def test_one_repo_in_two_domains_is_refused(tmp_path: Path) -> None:
    """The invariant route_domain already requires: one repo, one domain. If the
    registry contradicts it, the derived table would route by iteration order."""
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_BACKLOG + """
## B-005 — cinco   [ ]

domain: edge-cli-acp
repo: packages/sdk
status: raw
""", encoding="utf-8")
    root = _repo(tmp_path, "theokit-sdk")
    (root / "packages" / "sdk").mkdir(parents=True)
    (root / "packages" / "sdk-pty").mkdir(parents=True)

    import pytest
    with pytest.raises(ValueError, match="packages/sdk"):
        domains_from_backlog(backlog, root)


# ---------------------------------------------------------------------------
# The registry's scope. `backlog-init` Step 0.2 refused to run when there was not
# more than one repo below ("no umbrella detected — run at the workspace root"),
# which in an autonomous project means creating the BACKLOG at the umbrella root,
# OUTSIDE the project. The principle ("one place to look") does not require an
# umbrella: it requires
# um registro por escopo governado.
# ---------------------------------------------------------------------------

from detect_domains import detect_scope  # noqa: E402


def test_umbrella_scope_when_more_than_one_repo_lives_below(tmp_path: Path) -> None:
    root = tmp_path / "framework"
    root.mkdir()
    _repo(root, "theokit-sdk")
    _repo(root, "theokit-ui")
    assert detect_scope(root) == "umbrella"


def test_single_repo_scope_is_valid_not_an_error(tmp_path: Path) -> None:
    """theokit-sdk: one repo, its own cycle, its own registry."""
    root = _repo(tmp_path, "theokit-sdk")
    (root / "packages" / "sdk").mkdir(parents=True)
    (root / "packages" / "sdk" / "package.json").write_text("{}", encoding="utf-8")
    assert detect_scope(root) == "single-repo"


def test_a_project_with_a_vendored_clone_is_still_single_repo(tmp_path: Path) -> None:
    """What decides is the root BEING a repository, not the count of `.git` below.

    The old guard counted `find -maxdepth 2 -name .git` and required `> 1`, so a
    project with a vendored clone inside passed as an umbrella and its registry
    went to the directory above.
    """
    root = _repo(tmp_path, "projeto")
    _repo(root, "vendored-thing")
    assert detect_scope(root) == "single-repo"


def test_umbrella_is_a_directory_that_is_not_itself_a_repo(tmp_path: Path) -> None:
    framework = tmp_path / "framework"
    framework.mkdir()
    _repo(framework, "um-repo-so")
    assert detect_scope(framework) == "umbrella"


# ---------------------------------------------------------------------------
# Grill kit-domain-agents-install, decision 2: deriving the table without
# resolving the specialist trades "another ecosystem's table" for "a table
# pointing at nobody" — `route_domain` answers BROKEN ROUTE. The skeleton comes
# from what was MEASURED, and declares of itself that it was not reviewed.
# ---------------------------------------------------------------------------

from detect_domains import UNREVIEWED_MARKER, render_specialist  # noqa: E402


def test_the_skeleton_declares_that_nobody_reviewed_it(tmp_path: Path) -> None:
    root = _repo(tmp_path, "meu-projeto")
    domain = detect_domains(root)[0]
    body = render_specialist(domain, root)
    assert "derived: true" in body
    assert "reviewed_by_human: false" in body
    assert UNREVIEWED_MARKER in body, "the debt must stay visible, not silent"


def test_the_skeleton_carries_only_measured_facts(tmp_path: Path) -> None:
    """Name, repos and detected languages. No invented invariants."""
    root = _repo(tmp_path, "meu-projeto")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    body = render_specialist(detect_domains(root)[0], root)
    assert "`meu-projeto`" in body
    assert "python" in body


def test_the_judgement_sections_exist_and_are_empty(tmp_path: Path) -> None:
    """The sections requiring human judgement stay present and empty: a specialist
    without them looks complete, and that is where it misleads."""
    root = _repo(tmp_path, "meu-projeto")
    body = render_specialist(detect_domains(root)[0], root)
    for section in ("Invariants", "What a real finding looks like here", "False positives"):
        assert section in body, section
    assert body.count(UNREVIEWED_MARKER) >= 3, "one marker per judgement section"


def test_a_skeleton_is_routable(tmp_path: Path) -> None:
    """O ponto de existir: a rota deixa de ser BROKEN."""
    import subprocess
    import sys
    root = _repo(tmp_path, "meu-projeto")
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "agents").mkdir(parents=True)
    rule = root / ".claude" / "rules" / "cycle-backlog.md"
    rule.write_text("# x\n\n## Domain routing\n\n| D | R | S |\n|---|---|---|\n| `velho` | `outro` | `agents/velho.md` |\n", encoding="utf-8")
    domains = detect_domains(root)
    rewrite_routing_section(rule, domains)
    (root / ".claude" / "agents" / "meu-projeto.md").write_text(
        render_specialist(domains[0], root), encoding="utf-8")

    out = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(Path(__file__).resolve().parents[3] / "scripts" / "route_domain.py"),
         "meu-projeto", "--rule", str(rule)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr


def test_write_does_not_destroy_the_invariants_the_code_enforces(tmp_path: Path) -> None:
    """`--write` may replace the table; it may not take the contract with it.

    `_ROUTING_SECTION_RE` runs `.*?` under DOTALL from the heading to the next
    `##`, so everything in between is replaced wholesale. The prose in there was
    two different things at once: bootstrap instructions, which expire the moment
    they run, and invariants, which never expire. Replacing the section deleted
    both — measured on an adopter, 45 lines down to 12.

    The one that hurts is `One repo, one domain`. `scripts/route_domain.py` still
    raises on a repo listed twice, and its own header says the rule file is the
    source of truth it refuses to copy. So the gate went on rejecting tables for
    a reason no longer written anywhere — the inverse of a fabricated mechanism:
    a real gate with no stated contract.

    This asserts against the SHIPPED rule, not a fixture. A fixture would prove
    the regex behaves and say nothing about whether the file consumers receive
    survives the command the kit tells them to run.
    """
    shipped = Path(__file__).resolve().parents[3] / "rules" / "cycle-backlog.md"
    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(shipped.read_text(encoding="utf-8"), encoding="utf-8")

    rewrite_routing_section(rule, detect_domains(_repo(tmp_path / "eco", "svc-a").parent))

    survived = rule.read_text(encoding="utf-8")
    assert "One repo, one domain" in survived, (
        "route_domain.py enforces this; the rule must keep stating it"
    )
    assert "Record the divergence instead of deleting it" in survived

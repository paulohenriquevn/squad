"""The consumer needs to know what is theirs and what came from the kit.

Measured on `speculative` (2026-08-20): the project has an auditor of its own,
`scripts/audit.py`, which walks `.claude/skills/*/SKILL.md` and demands the Agent
Skills spec of each. Before the install it said PASS; afterwards, FAIL — because
it started auditing the kit's 37 skills against the standard of the project's 9.

The install deleted nothing (46 untracked, zero modified). That was the entire
damage: a consumer gate that started measuring code that is not the consumer's.
Without a manifest, the only way to tell them apart would be guessing by name.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for kit_agents
from kit_agents import kit_agents  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent
MANIFEST = ".claude/.kit-manifest.txt"


def test_install_writes_a_manifest_of_what_the_kit_brought(tmp_path: Path) -> None:
    target = tmp_path / "consumidor"
    target.mkdir()
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    subprocess.run(
        ["bash", str(_REPO / "mechanisms" / "dist" / "install.sh"), str(target)],
        capture_output=True, text=True, check=True,
    )

    manifest = target / MANIFEST
    assert manifest.is_file(), "without a manifest the consumer cannot tell what is theirs"
    listed = {line.strip() for line in manifest.read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.startswith("#")}
    assert "skills/implement" in listed
    assert "skills/review" in listed
    # Every listed skill really exists in the target — a lying manifest is worse than none.
    for entry in listed:
        assert (target / ".claude" / entry).exists(), entry


def test_a_project_skill_is_absent_from_the_manifest(tmp_path: Path) -> None:
    """The point of the file: what the project wrote does NOT appear in it."""
    target = tmp_path / "consumidor"
    (target / ".claude" / "skills" / "minha-skill-de-dominio").mkdir(parents=True)
    (target / ".claude" / "skills" / "minha-skill-de-dominio" / "SKILL.md").write_text(
        "# minha\n", encoding="utf-8")
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    subprocess.run(
        ["bash", str(_REPO / "mechanisms" / "dist" / "install.sh"), str(target), "--merge"],
        capture_output=True, text=True, check=True,
    )

    listed = (target / MANIFEST).read_text(encoding="utf-8")
    assert "minha-skill-de-dominio" not in listed
    assert (target / ".claude" / "skills" / "minha-skill-de-dominio" / "SKILL.md").is_file()


def test_merge_never_overwrites_an_existing_rules_txt(tmp_path: Path) -> None:
    """`rules/*.txt` is the project's CONFIGURATION: enabled languages, live
    targets, allowlists, declared auxiliary skills. `--merge` copied the template
    over it — measured on `speculative`, where the declaration of the project's 9
    skills was erased by the reinstall that followed.

    The `.md` files keep being updated: they are the kit's normative contract.
    """
    target = tmp_path / "consumidor"
    rules = target / ".claude" / "rules"
    rules.mkdir(parents=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (rules / "code-quality-languages.txt").write_text(
        "python | pyproject.toml | ENABLED |\n", encoding="utf-8")

    subprocess.run(
        ["bash", str(_REPO / "mechanisms" / "dist" / "install.sh"), str(target), "--merge"],
        capture_output=True, text=True, check=True,
    )

    kept = (rules / "code-quality-languages.txt").read_text(encoding="utf-8")
    assert "python | pyproject.toml | ENABLED" in kept, "the project's config was overwritten"
    assert (rules / "cycle-backlog.md").is_file(), "as regras .md seguem sendo instaladas"


# ---------------------------------------------------------------------------
# Grill kit-domain-agents-install, decisions 1 and 4: the origin ecosystem's eight
# specialists stop being copied by default. Measured: 19 of the 41 consumers
# already lived without them, 11 write their own, and the routing table became
# derived from the project — the coupling that justified them vanished.
# ---------------------------------------------------------------------------

def _install(target: Path, *flags: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    subprocess.run(
        ["bash", str(_REPO / "mechanisms" / "dist" / "install.sh"), str(target), *flags],
        capture_output=True, text=True, check=True,
    )


def test_no_specialist_is_ever_installed(tmp_path: Path) -> None:
    """Only the README travels. A specialist describes ONE ecosystem's repos.

    The kit carried eight, from the ecosystem it was written in, and the
    `--with-domain-agents` flag delivered them on request. They left on 2026-08-26.
    This test does not pin the names that left — it pins the RULE, and therefore
    still holds for a specialist someone writes into the source tomorrow: nothing in
    `agents/` beyond the README is the consumer's until they derive it.
    """
    target = tmp_path / "consumidor"
    _install(target)
    agents = target / ".claude" / "agents"
    # The kit's own agents are mechanism — they name no repository and make no claim
    # about anyone's topology, which is precisely what disqualifies a specialist. The
    # list comes from the installer that copies them, so it cannot drift from it.
    installed = {p.name for p in agents.glob("*.md")} - kit_agents()
    assert installed == set(), (
        f"the install brought specialists from another ecosystem: {sorted(installed)}"
    )


def test_the_manifest_lists_the_agents_the_kit_installs_and_no_others(
        tmp_path: Path) -> None:
    """A lying manifest is worse than none: the consumer uses it to decide what is
    theirs — and the lie ran in both directions.

    Until 2026-09-02 this asserted the manifest held `agents/README.md` ALONE,
    while the installer copied the kit's four roles beside it. The manifest states
    its own rule in its header — *anything not here is the project's* — so omitting
    them declared kairos, iris, daedalus and hermes to be the consumer's work. A
    project reading it would conclude it owned four files the next install
    overwrites.

    It was measured downstream before it was noticed here: `check_squad_map` reads
    the manifest to tell a kit role from a domain specialist, found no kit roles
    listed, fell back to `git ls-files agents/` — correct only in the kit's own
    repository, where specialists are gitignored — and asked a consumer's map to
    name two of that project's own domain specialists.

    What must NOT appear is a specialist: the kit ships none, and an install that
    brought one would be carrying another ecosystem's domain into this project.
    """
    target = tmp_path / "consumidor"
    _install(target)
    listed = sorted(
        line.strip() for line in (target / MANIFEST).read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("agents/")
    )

    assert listed == sorted({f"agents/{p.name}" for p in (_REPO / "agents").glob("*.md")}), listed
    assert len(listed) == len(set(listed)), f"duplicate rows: {listed}"
    on_disk = sorted(f"agents/{p.name}"
                     for p in (target / ".claude" / "agents").glob("*.md"))
    assert listed == on_disk, "the manifest and the directory disagree about what arrived"


# ---------------------------------------------------------------------------
# The PROJECT's agents survive any install. Without this, a cleanup done in a
# consumer lasts until the next install — and worse, an install without --merge
# deleted the specialists the project wrote.
# ---------------------------------------------------------------------------

def _project_agents(target: Path) -> Path:
    agents = target / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "meu-dominio.md").write_text("# especialista do projeto\n", encoding="utf-8")
    (agents / "meu-validador.md").write_text("# validador do projeto\n", encoding="utf-8")
    (agents / "README.md").write_text("# README the project wrote\n", encoding="utf-8")
    return agents


def test_a_plain_install_never_deletes_project_agents(tmp_path: Path) -> None:
    """`rm -rf agents/` took what the project wrote along with it."""
    target = tmp_path / "consumidor"
    _project_agents(target)
    _install(target, "--force")
    agents = target / ".claude" / "agents"
    assert (agents / "meu-dominio.md").is_file()
    assert (agents / "meu-validador.md").is_file()


def test_an_existing_agents_readme_is_kept(tmp_path: Path) -> None:
    """The README lists the PROJECT's agents once someone adapts it."""
    target = tmp_path / "consumidor"
    _project_agents(target)
    _install(target, "--merge")
    kept = (target / ".claude" / "agents" / "README.md").read_text(encoding="utf-8")
    assert "the project wrote" in kept


def test_the_readme_is_written_when_absent(tmp_path: Path) -> None:
    target = tmp_path / "consumidor"
    _install(target)
    assert (target / ".claude" / "agents" / "README.md").is_file()


def test_the_removed_flag_is_refused_instead_of_ignored(tmp_path: Path) -> None:
    """`--with-domain-agents` left with the specialists. Accepting it silently would
    make whoever uses it believe they received something."""
    target = tmp_path / "consumidor"
    target.mkdir(parents=True, exist_ok=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(_REPO / "mechanisms" / "dist" / "install.sh"), str(target), "--with-domain-agents"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 2, proc.stdout
    assert "unknown flag" in proc.stderr


def test_merge_migrates_the_derived_routing_table_instead_of_losing_it(tmp_path: Path) -> None:
    """A legacy consumer's table survives the move — it changes file, not existence.

    It used to be a section inside `cycle-backlog.md`, which is the kit's
    contract and gets replaced on every install. Keeping the consumer's data
    there required the installer to cut the section out and paste it back, and it
    did that in one of its two modes: measured on `speculative`, the reinstall
    restored the origin ecosystem's table over the derived one and
    `route_domain speculative` went from exit 0 to exit 1 — the project lost the
    ability to route items about itself.

    The table now lives in `rules/domain-routing.txt`, which is the project's and
    is preserved like every other `rules/*.txt`. What this pins is the bridge: a
    consumer that still has the section gets it MIGRATED, once, at the only
    moment the kit is inside their repository with permission to write. A
    migration that asks the consumer to act is one the oldest tables never get.
    """
    target = tmp_path / "consumidor"
    rules = target / ".claude" / "rules"
    rules.mkdir(parents=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (rules / "cycle-backlog.md").write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `meu-dominio` | `meu-repo` | `agents/meu-dominio.md` |\n\n"
        "## Verdicts\n\nvelho\n",
        encoding="utf-8",
    )
    _install(target, "--merge")

    migrated = (rules / "domain-routing.txt").read_text(encoding="utf-8")
    assert "meu-dominio" in migrated, "the consumer's derived table was lost in the move"
    assert "meu-repo" in migrated

    body = (rules / "cycle-backlog.md").read_text(encoding="utf-8")
    assert "## Hard gates" in body, "the rest of the rule must arrive updated from the kit"


# ---------------------------------------------------------------------------
# The kit shipped ITS OWN configuration as if it were the consumer's. Measured on
# `speculative`: it was born with `python | pyproject.toml | ENABLED` (the kit is
# Python; the target has no pyproject) and with the origin ecosystem's live target
# — somebody else's dev environment URL. That is 41 installs in that condition.
# ---------------------------------------------------------------------------

def _active_lines(path: Path) -> list[str]:
    return [l for l in path.read_text(encoding="utf-8").splitlines()  # noqa: E741
            if l.strip() and not l.lstrip().startswith("#")]


def test_project_specific_config_is_installed_as_a_blank_template(tmp_path: Path) -> None:
    target = tmp_path / "consumidor"
    _install(target)
    rules = target / ".claude" / "rules"
    assert _active_lines(rules / "code-quality-languages.txt") == [], \
        "o consumidor nasceria com a linguagem do KIT habilitada"
    assert _active_lines(rules / "live-target.txt") == [], \
        "the consumer would be born probing another ecosystem's service"


def test_universal_defaults_are_still_shipped(tmp_path: Path) -> None:
    """The thresholds are kit defaults (`YOUR_ADR_REF` is a placeholder), not local
    calibration — emptying them would leave the gate with no band at all."""
    target = tmp_path / "consumidor"
    _install(target)
    body = (target / ".claude" / "rules" / "plan-confidence-thresholds.txt").read_text()
    assert "SHIPPABLE|90" in body


def test_the_projects_own_quality_gate_never_ships(tmp_path: Path) -> None:
    """`hooks/quality/` holds THIS repository's thresholds, not the installer's.

    `/quality-init` calibrates on the p90 of the code it measures: here that gave
    `max_file_lines = 367` and `max_function_lines = 29`. Those numbers say nothing
    about another project's codebase, and a gate calibrated on the wrong ruler starts
    red — which is how a gate gets switched off within the hour. Same defect the
    routing table and the `rules/*.txt` already fixed: distributing the author's
    configuration.
    """
    target = tmp_path / "consumidor"
    _install(target)
    hooks = target / ".claude" / "hooks"

    assert hooks.is_dir(), "os hooks do kit continuam vindo"
    assert not (hooks / "quality").exists(), (
        "the smell gate calibrated in this repository reached the consumer"
    )
    listed = (target / MANIFEST).read_text(encoding="utf-8")
    assert "hooks/quality" not in listed

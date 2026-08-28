"""The installation any OTHER machine receives.

WHY THE FILE LIST COMES FROM GIT
--------------------------------
Every installation test this repository had copied the working tree — and the
maintainer's working tree carries files `.gitignore` hides. `agents/**` is the
case — the whole directory is ignored, and the eight specialists the kit
distributed lived for months on one machine and on no other. As long as the test
installed from disk, it measured the machine running it, not what the kit
delivers.

Medido em 2026-08-26: um clone limpo instalado num alvo vazio produzia
an EMPTY `.claude/agents/` — not even the `README.md` the installer copies
unconditionally — and `check_xrefs.py --strict` exited 1, because
`rules/cycle-maintenance.md` cites `agents/README.md`. On the maintainer's
machine, green. The same `cp -r` carried 342 `.pyc` files to the consumer,
against an explicit promise in the installer's header that caches would be
skipped.

`git ls-files` is the only source that answers "what is versioned?" without
consulting the disk — and that is why the fixture below builds the tree from it,
file by file, instead of `shutil.copytree`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Directories that are tool cache — never kit content.
CACHE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


@pytest.fixture(scope="module")
def installed(versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory):
    """A real installation, from the versioned kit, into an empty target."""
    target = tmp_path_factory.mktemp("consumer")
    proc = subprocess.run(  # noqa: PLW1510
        ["bash", str(versioned_kit / "scripts" / "install.sh"), str(target)],
        capture_output=True,
        text=True,
    )
    return target, proc


def test_install_succeeds(installed):
    target, proc = installed
    assert proc.returncode == 0, f"install.sh falhou:\n{proc.stdout}\n{proc.stderr}"
    assert (target / ".claude").is_dir()


def test_strict_xrefs_passes_on_a_fresh_install(installed):
    """The validator install.sh itself calls must approve what it just wrote.

    `--strict` is deliberate: without it, a broken reference comes out as
    `Overall: PASS` com exit 0 (ver `test_ci_contract.py`).
    """
    target, _ = installed
    proc = subprocess.run(  # noqa: PLW1510
        ["python3", str(target / ".claude" / "scripts" / "check_xrefs.py"), "--strict"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "A freshly made installation does not pass its own validator:\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_routing_mechanism_reaches_the_consumer(installed):
    """`agents/README.md` describes the routing MECHANISM, not a domain.

    O instalador o copia incondicionalmente e `rules/cycle-maintenance.md` o
    cites it. If it is not versioned, it arrives empty in every consumer.
    """
    target, _ = installed
    readme = target / ".claude" / "agents" / "README.md"
    assert readme.is_file(), (
        "agents/README.md did not reach the consumer — either it is not versioned, "
        "or the installer stopped copying it."
    )
    assert readme.stat().st_size > 0


def test_no_domain_specialist_is_installed(installed):
    """No domain specialist reaches the consumer — they derive their own.

    They describe ONE ecosystem's repositories; in a consumer that is not that
    ecosystem, they are files about repositories that do not exist there. The kit
    stopped carrying them on 2026-08-26, and the fixture installs from
    `git ls-files`, so a specialist left on this machine's disk cannot mask the
    result.
    """
    target, _ = installed
    agents = target / ".claude" / "agents"
    specialists = [p for p in agents.glob("*.md") if p.name != "README.md"]
    assert specialists == [], f"domain specialists leaked: {specialists}"


def test_no_tool_cache_reaches_the_consumer(versioned_kit, tmp_path):
    """install.sh's header promises to skip caches. This test enforces the promise.

    It installs from a tree that HAS caches — like the maintainer's — and demands
    that none crosses over. Installing from `versioned_kit` would prove nothing:
    o git nunca carregou um `.pyc`.
    """
    dirty = tmp_path / "dirty-kit"
    subprocess.run(["cp", "-r", str(versioned_kit), str(dirty)], check=True)
    # Plants exactly the litter a real working tree accumulates.
    for rel in ("skills/__pycache__", "scripts/__pycache__", "skills/code-quality/.pytest_cache"):
        d = dirty / rel
        d.mkdir(parents=True, exist_ok=True)
        (d / "planted.pyc").write_bytes(b"\x00planted")

    target = tmp_path / "consumer"
    target.mkdir()
    proc = subprocess.run(  # noqa: PLW1510
        ["bash", str(dirty / "scripts" / "install.sh"), str(target)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    eco = target / ".claude"
    leaked_dirs = [p for p in eco.rglob("*") if p.is_dir() and p.name in CACHE_DIRS]
    leaked_pyc = list(eco.rglob("*.pyc"))
    assert not leaked_dirs, f"cache propagado ao consumidor: {[str(p) for p in leaked_dirs]}"
    assert not leaked_pyc, f".pyc propagado ao consumidor: {[str(p) for p in leaked_pyc]}"


def test_installed_payload_is_not_dominated_by_noise(installed, versioned_kit):
    """An order-of-magnitude guardrail on what the consumer receives.

    It does not pin a number — the kit grows. It pins the ratio: what is installed
    must not exceed by much what git carries, because everything beyond that is
    content nobody versioned.
    """
    target, _ = installed
    versioned = len(
        subprocess.run(
            ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.split()
    )
    installed_files = sum(1 for p in (target / ".claude").rglob("*") if p.is_file())
    assert installed_files <= versioned * 1.25, (
        f"installed {installed_files} files against {versioned} versioned — "
        "the excess is not the system."
    )


def test_the_routing_contract_survives_the_command_the_kit_prescribes(installed):
    """Install, derive, reinstall — the invariants must read exactly once throughout.

    Two mechanisms replace the `## Domain routing` span with the same regex:
    `install.sh` lays the empty template down, and `detect_domains.py --write`
    fills in the derived table. Anything inside that span is written to be
    overwritten.

    The invariants were inside it. So the consumer ran the command
    `agents/README.md` prescribes and lost `One repo, one domain` — while
    `route_domain.py` went on raising on a repo listed twice, for a reason no
    file stated any more. Measured on an adopter: 45 lines down to 12.

    `once` is the assertion, not `present`. The first fix moved the paragraphs to
    `## Routing invariants` but left the template's copy in place, so a fresh
    install carried each invariant twice — one piece of knowledge in two files,
    and the copy that gets deleted is the one people would read first.
    """
    target, _ = installed
    rule = target / ".claude" / "rules" / "cycle-backlog.md"
    invariants = ("One repo, one domain", "Record the divergence instead of deleting it")

    for text in invariants:
        assert rule.read_text(encoding="utf-8").count(text) == 1, f"after install: {text}"

    subprocess.run(  # noqa: PLW1510
        [sys.executable, ".claude/skills/backlog-init/scripts/detect_domains.py",
         "--root", ".", "--write", ".claude/rules/cycle-backlog.md"],
        cwd=target, capture_output=True, text=True,
    )
    for text in invariants:
        assert rule.read_text(encoding="utf-8").count(text) == 1, f"after --write: {text}"


@pytest.mark.parametrize("mode", ["--force", "--merge"])
def test_reinstalling_never_empties_the_derived_routing_table(
    versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory, mode: str
) -> None:
    """The derived table must survive a reinstall in EVERY mode, not just `--merge`.

    `install.sh` already says this, at the call site of `apply_routing_template`:
    *"The routing table is only born empty when there is no derived one to
    preserve. Overwriting the consumer's would trade a correct map for an empty
    one — the exact opposite of the defect this template fixes."* The save-and
    -reinject that honours it was written inside the `MERGE` branch only, so
    `--force` — the flag a reinstall actually uses — went on doing precisely what
    the comment forbids.

    Measured: a consumer with `svc-a` and `svc-b` derived came back as
    `_(empty — run detect_domains.py --write)_`, and `route_domain` on either
    repo went from exit 0 to unroutable. The same defect the comment cites as
    already measured on `speculative`, fixed once, in one of the two paths.
    """
    target = tmp_path_factory.mktemp(f"reinstall{mode.strip('-')}")
    (target / "svc-a").mkdir()
    for path in (target, target / "svc-a"):
        subprocess.run(["git", "init", "-q", "."], cwd=path, check=True)

    install = [str(versioned_kit / "scripts" / "install.sh"), str(target)]
    subprocess.run(["bash", *install], capture_output=True, check=True)
    subprocess.run(  # noqa: PLW1510
        [sys.executable, ".claude/skills/backlog-init/scripts/detect_domains.py",
         "--root", ".", "--write", ".claude/rules/domain-routing.txt"],
        cwd=target, capture_output=True, text=True,
    )
    rule = target / ".claude" / "rules" / "domain-routing.txt"
    assert "svc-a" in rule.read_text(encoding="utf-8"), "fixture did not derive a table"

    subprocess.run(["bash", *install, mode], capture_output=True, check=True)

    after = rule.read_text(encoding="utf-8")
    assert "svc-a" in after, (
        f"{mode} replaced the consumer's derived table with the empty template — "
        "the project can no longer route items about its own repository"
    )


@pytest.mark.parametrize("mode", ["--force", "--merge"])
def test_reinstalling_never_overwrites_the_projects_own_config(
    versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory, mode: str
) -> None:
    """`rules/*.txt` is the project's configuration and must survive every mode.

    The installer states the rule inside its `--merge` branch: *"`rules/*.txt` is
    the project's CONFIGURATION — enabled languages, live target, allowlists,
    declared auxiliary skills. Copying the template over it erases local tuning
    in silence: measured on `speculative`, where the declaration of the project's
    9 skills died on the next reinstall."*

    That `continue` guarding the consumer's file was written in the merge branch
    only. The non-merge path does `rm -rf rules/` and copies the templates over
    the top, so `--force` — the flag a reinstall uses — erases exactly what the
    comment says must not be erased. Same shape as the routing-table defect
    above, in the same file, for the same reason: the rule was implemented once,
    on one of the two paths.

    Measured while reinstalling the kit across 19 consumers: four npm projects
    lost `deny: Read(**/.env*)` and their `vitest`/`tsc` allowances, and the
    languages they had enabled came back as the empty template.
    """
    target = tmp_path_factory.mktemp(f"config{mode.strip('-')}")
    subprocess.run(["git", "init", "-q", "."], cwd=target, check=True)
    install = [str(versioned_kit / "scripts" / "install.sh"), str(target)]
    subprocess.run(["bash", *install], capture_output=True, check=True)

    # A marker the template cannot contain. `typescript` was the first choice and
    # it appears in the template as a commented example, so the assertion passed
    # against a file that had just been overwritten.
    marker = "zz-project-tuned-language"
    config = target / ".claude" / "rules" / "code-quality-languages.txt"
    assert marker not in config.read_text(encoding="utf-8")
    config.write_text(config.read_text(encoding="utf-8") + f"{marker}\n", encoding="utf-8")

    subprocess.run(["bash", *install, mode], capture_output=True, check=True)

    assert marker in config.read_text(encoding="utf-8"), (
        f"{mode} overwrote rules/code-quality-languages.txt with the empty template — "
        "the project's enabled languages died on a reinstall"
    )


@pytest.mark.parametrize("mode", ["--force", "--merge"])
def test_the_kit_can_still_update_its_own_contract(
    versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory, mode: str
) -> None:
    """A `.txt` the kit OWNS must keep being updated by a reinstall.

    `rules/*.txt` was a fine proxy for "the project's configuration" while every
    `.txt` under `rules/` was one. `rules/cycle-phases.txt` broke it: it declares
    the pipeline's phase chain, which is the kit's contract — the consumer never
    edits it and must receive its corrections. Preserving it by extension freezes
    a stale contract in every consumer, and `check_phase_drift.py` then measures
    the run against a chain the kit no longer ships.

    So the rule is stated by name rather than inferred from the suffix. Guessing
    ownership from a filename is what produced this pair of defects in the first
    place.
    """
    target = tmp_path_factory.mktemp(f"contract{mode.strip('-')}")
    subprocess.run(["git", "init", "-q", "."], cwd=target, check=True)
    install = [str(versioned_kit / "scripts" / "install.sh"), str(target)]
    subprocess.run(["bash", *install], capture_output=True, check=True)

    phases = target / ".claude" / "rules" / "cycle-phases.txt"
    phases.write_text("stale-contract-from-an-older-kit\n", encoding="utf-8")

    subprocess.run(["bash", *install, mode], capture_output=True, check=True)

    assert "stale-contract" not in phases.read_text(encoding="utf-8"), (
        f"{mode} preserved rules/cycle-phases.txt as if it were the project's — "
        "the kit can no longer correct its own phase chain in a consumer"
    )


@pytest.mark.parametrize("mode", ["--force", "--merge"])
def test_reinstalling_keeps_the_projects_permissions(
    versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory, mode: str
) -> None:
    """`settings.json` carries the kit's wiring AND the project's permissions.

    `boundary-check.sh` allowlists `settings.json` as *"this project's wiring"* —
    the consumer is explicitly allowed to edit it. The installer then copied its
    own over the top, so the kit invited an edit and destroyed it on the next
    reinstall.

    The cost is not symmetric. `hooks` and `statusLine` are the kit's and must be
    refreshed; a stale hook silently stops enforcing. `permissions` is the
    project's, and one of the entries measured lost across four npm consumers was
    `deny: Read(**/.env*)` — reinstalling the kit widened what an agent may read
    in someone else's repository, with no line of output saying so.
    """
    import json

    target = tmp_path_factory.mktemp(f"perms{mode.strip('-')}")
    subprocess.run(["git", "init", "-q", "."], cwd=target, check=True)
    install = [str(versioned_kit / "scripts" / "install.sh"), str(target)]
    subprocess.run(["bash", *install], capture_output=True, check=True)

    settings = target / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data.setdefault("permissions", {}).setdefault("deny", []).insert(0, "Read(**/.env*)")
    data["permissions"].setdefault("allow", []).append("Bash(npx vitest *)")
    settings.write_text(json.dumps(data, indent=2), encoding="utf-8")

    subprocess.run(["bash", *install, mode], capture_output=True, check=True)

    after = json.loads(settings.read_text(encoding="utf-8"))
    perms = after.get("permissions", {})
    assert "Read(**/.env*)" in perms.get("deny", []), (
        f"{mode} dropped the project's deny rule — reinstalling the kit widened "
        "what an agent may read in someone else's repository"
    )
    assert "Bash(npx vitest *)" in perms.get("allow", [])
    assert after.get("hooks"), f"{mode} must still refresh the kit's own wiring"


def test_a_consumer_with_a_markdown_table_is_migrated_once(
    versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A consumer whose table is still a `.md` section gets it moved, not lost.

    The kit cannot run anything inside another project's repository, so a
    migration that asks the consumer to act is a migration most consumers never
    perform — and the ones that skip it are exactly the ones whose table is
    oldest. Doing it at install time is the only moment the kit is inside the
    consumer with permission to write.

    Once, and only from a NON-empty section: migrating the empty placeholder
    would fabricate a derived table the project never derived, and the emptiness
    is what makes `/backlog-item` refuse items — which is the correct behaviour
    when nobody has said who owns what.
    """
    target = tmp_path_factory.mktemp("migrate")
    subprocess.run(["git", "init", "-q", "."], cwd=target, check=True)
    install = [str(versioned_kit / "scripts" / "install.sh"), str(target)]
    subprocess.run(["bash", *install], capture_output=True, check=True)

    rules = target / ".claude" / "rules"
    (rules / "domain-routing.txt").unlink(missing_ok=True)
    (rules / "cycle-backlog.md").write_text(
        "# x\n\n## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `api` | `svc-a`, `svc-b` | `agents/api.md` |\n\n## Verdicts\n\nx\n",
        encoding="utf-8",
    )

    subprocess.run(["bash", *install, "--force"], capture_output=True, check=True)

    migrated = (rules / "domain-routing.txt").read_text(encoding="utf-8")
    assert "api" in migrated and "svc-a" in migrated and "svc-b" in migrated, (
        "the consumer's derived table did not survive the migration"
    )

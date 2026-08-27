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
        f"instalados {installed_files} arquivos contra {versioned} versionados — "
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

"""The scaffold exists to remove a human barrier at the first step.

`detect_domains.py` derives the routing table and names one agent per domain;
`route_domain.py` refuses any domain whose specialist is not on disk. Writing those
files was human work, before anything else could run — which a system meant to work
unattended cannot afford.

What is tested here is the line the scaffold must not cross: it writes what it
measured and marks the rest open, and it never touches a specialist someone wrote.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scaffold_specialists.py"
sys.path.insert(0, str(SCRIPT.parent))

from scaffold_specialists import measure, render  # noqa: E402


def _repo(tmp_path: Path, name: str, *manifests: str) -> Path:
    repo = tmp_path / name
    (repo / ".git").mkdir(parents=True)
    for manifest in manifests:
        (repo / manifest).write_text("x\n", encoding="utf-8")
    return repo


# ── what it measures ─────────────────────────────────────────────────────────


def test_the_manifests_on_disk_become_implied_commands(tmp_path: Path) -> None:
    facts = measure(_repo(tmp_path, "engine", "go.mod", "Taskfile.yml"))
    assert set(facts["manifests"]) == {"go.mod", "Taskfile.yml"}
    assert "go test ./..." in facts["implied_commands"]
    assert "task test" in facts["implied_commands"]


def test_a_repo_with_no_manifest_implies_nothing(tmp_path: Path) -> None:
    """Rather than a default guess. A command printed as if it worked is the kind of
    fact a specialist exists to prevent."""
    facts = measure(_repo(tmp_path, "docs"))
    assert facts["manifests"] == []
    assert facts["implied_commands"] == []


# ── what it refuses to invent ────────────────────────────────────────────────


def test_commands_are_marked_implied_and_unverified(tmp_path: Path) -> None:
    """Nothing is run by the scaffold, and the file says so where someone will read it
    before trusting a command."""
    body = render("engine", {"engine": measure(_repo(tmp_path, "engine", "go.mod"))},
                  "2026-08-31")
    assert "IMPLIED, not verified" in body
    assert "Nothing here was run" in body


def test_the_three_unmeasurable_sections_are_marked_open(tmp_path: Path) -> None:
    """Invariants, finding shapes and blast radius need someone who knows the domain.
    An invariant asserted by nobody is worse than an absent one, because it is
    believed."""
    body = render("engine", {"engine": measure(_repo(tmp_path, "engine"))}, "2026-08-31")
    assert body.count("OPEN") >= 3
    for heading in ("invariants", "shape of a real finding", "Blast radius"):
        assert heading in body


def test_the_measured_table_carries_the_commit_count(tmp_path: Path) -> None:
    """An empty checkout must be visible as one, not read as a repo with no history
    worth mentioning."""
    body = render("engine", {"engine": measure(_repo(tmp_path, "engine"))}, "2026-08-31")
    assert "Commits" in body


# ── what it never touches ────────────────────────────────────────────────────


def test_an_existing_specialist_is_never_overwritten(tmp_path: Path) -> None:
    """A project's own specialist carries knowledge the scaffold cannot reproduce.
    Replacing it with a measured skeleton would trade something for less."""
    eco = tmp_path / "project"
    (eco / "agents").mkdir(parents=True)
    mine = eco / "agents" / "engine.md"
    mine.write_text("# written by a person\n", encoding="utf-8")
    (eco / ".claude").mkdir(exist_ok=True)

    out = subprocess.run([sys.executable, str(SCRIPT), "--root", str(eco), "--write"],
                         capture_output=True, text=True, timeout=120)
    assert mine.read_text(encoding="utf-8") == "# written by a person\n", out.stdout


def test_without_write_nothing_is_created(tmp_path: Path) -> None:
    eco = tmp_path / "project"
    (eco / "agents").mkdir(parents=True)
    subprocess.run([sys.executable, str(SCRIPT), "--root", str(eco)],
                   capture_output=True, text=True, timeout=120)
    assert list((eco / "agents").glob("*.md")) == []

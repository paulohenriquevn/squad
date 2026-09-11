"""The routing table moved to the write root, and old installs keep routing.

It was the one file under `rules/` that CODE produced — `detect_domains.py --write`
derives it and `route_domain.py` reads it, with nothing outside the kit touching
either. Measured 2026-09-10 across every `.json`, `.yml`, `.yaml` and `.toml` in the
tree: zero references. A file only the kit writes and only the kit reads is our own
output, and keeping it inside `.claude/` is what made the dependency un-deletable.

The tests that matter here are the fallback ones. A hard cut would break every
consumer that updates the kit without migrating, and the kit cannot run a migration
inside a repository it does not own.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

from squad.paths import ROUTING_TABLE, routing_table, write_routing_table  # noqa: E402


def _project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], capture_output=True, check=False)
    return tmp_path


def test_the_writer_never_falls_back(tmp_path: Path) -> None:
    """Readers fall back; writers do not. A writer that fell back would keep two
    tables alive and let the resolution order decide which one the project has."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / ROUTING_TABLE).write_text("old | r | a.md\n",
                                                               encoding="utf-8")

    assert write_routing_table(tmp_path) == tmp_path / ".squad" / ROUTING_TABLE


def test_a_legacy_install_still_routes(tmp_path: Path) -> None:
    """The consumer that updates the kit and migrates nothing keeps working."""
    proj = _project(tmp_path)
    (proj / ".claude" / "rules").mkdir(parents=True)
    (proj / ".claude" / "rules" / ROUTING_TABLE).write_text(
        "legacy | legacy-repo | agents/legacy.md\n", encoding="utf-8")
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".claude" / "agents" / "legacy.md").write_text("# legacy\n", encoding="utf-8")

    out = subprocess.run(
        [sys.executable, str(KIT / "mechanisms" / "cycle" / "route_domain.py"), "legacy-repo"],
        cwd=proj, capture_output=True, text=True, timeout=120, check=False)

    assert out.returncode == 0, out.stdout + out.stderr
    assert "legacy" in out.stdout


def test_the_write_root_wins_over_a_legacy_copy(tmp_path: Path) -> None:
    """Both present means a half-finished migration; the new location is the answer."""
    proj = _project(tmp_path)
    (proj / ".claude" / "rules").mkdir(parents=True)
    (proj / ".claude" / "rules" / ROUTING_TABLE).write_text("old | r | agents/old.md\n",
                                                            encoding="utf-8")
    (proj / ".squad").mkdir(parents=True)
    (proj / ".squad" / ROUTING_TABLE).write_text("new | r | agents/new.md\n", encoding="utf-8")

    assert routing_table(proj) == proj / ".squad" / ROUTING_TABLE


def test_bare_write_lands_in_the_write_root(tmp_path: Path) -> None:
    """`--write` with no path is the form every doc now teaches, so the caller does
    not carry the location and moving it again touches one file."""
    proj = _project(tmp_path)

    out = subprocess.run(
        [sys.executable,
         str(KIT / "skills" / "backlog-init" / "scripts" / "detect_domains.py"),
         "--root", str(proj), "--write"],
        cwd=proj, capture_output=True, text=True, timeout=120, check=False)

    assert out.returncode == 0, out.stdout + out.stderr
    assert (proj / ".squad" / ROUTING_TABLE).is_file()
    assert not (proj / ".claude" / "rules" / ROUTING_TABLE).exists()


def test_an_explicit_path_is_still_honoured(tmp_path: Path) -> None:
    """A consumer mid-migration may still aim it somewhere specific."""
    proj = _project(tmp_path)
    target = proj / "custom" / "table.txt"
    target.parent.mkdir(parents=True)

    subprocess.run(
        [sys.executable,
         str(KIT / "skills" / "backlog-init" / "scripts" / "detect_domains.py"),
         "--root", str(proj), "--write", str(target)],
        cwd=proj, capture_output=True, text=True, timeout=120, check=False)

    assert target.is_file()


def test_no_document_teaches_the_old_write_path() -> None:
    """Every doc repeated the path, so moving the table meant finding every copy.

    They now teach bare `--write`. This test is what stops the next one from being
    written with a hardcoded destination.
    """
    tracked = subprocess.run(["git", "ls-files", "*.md", "*.py", "*.sh"],
                             cwd=KIT, capture_output=True, text=True, check=False).stdout.split()
    offenders = []
    for rel in tracked:
        if "/tests/" in rel or rel.startswith("tests/"):
            continue
        text = (KIT / rel).read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            if "--write" in line and "rules/" + ROUTING_TABLE in line:
                offenders.append(f"{rel}:{i}")

    assert not offenders, (
        "these still teach writing the table into the kit's directory: " + ", ".join(offenders))


def test_moving_the_table_does_not_unroute_every_specialist(tmp_path: Path) -> None:
    """The regression the move introduced, found only by writing real specialists.

    `route_domain` resolved the specialist as `rule_path.parent.parent / agent`. That
    worked by accident: with the table at `<eco>/rules/`, two levels up landed on the
    installed kit, and specialists sit beside it. With the table at `.squad/`, two
    levels up is the PROJECT — so every domain reported BROKEN ROUTE while all seven
    files sat on disk the whole time.

    The location of the table and the location of the specialists are independent
    facts. Deriving one from the other is what coupled them.
    """
    proj = _project(tmp_path)
    (proj / ".squad").mkdir(parents=True, exist_ok=True)
    (proj / ".squad" / ROUTING_TABLE).write_text(
        "engine | engine-repo | agents/engine.md\n", encoding="utf-8")
    # The specialists live where a PLUGIN INSTALL puts them, not beside the table.
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".claude" / "agents" / "engine.md").write_text("# engine\n", encoding="utf-8")

    out = subprocess.run(
        [sys.executable, str(KIT / "mechanisms" / "cycle" / "route_domain.py"),
         "engine-repo", "--project-root", str(proj)],
        cwd=proj, capture_output=True, text=True, timeout=120, check=False)

    assert out.returncode == 0, out.stdout + out.stderr
    assert "BROKEN ROUTE" not in out.stdout
    assert "agents/engine.md" in out.stdout


def test_a_standalone_layout_still_resolves_its_specialists(tmp_path: Path) -> None:
    """No `.claude/` at all: the specialists sit at the project root."""
    proj = _project(tmp_path)
    (proj / ".squad").mkdir(parents=True, exist_ok=True)
    (proj / ".squad" / ROUTING_TABLE).write_text(
        "engine | engine-repo | agents/engine.md\n", encoding="utf-8")
    (proj / "agents").mkdir(parents=True)
    (proj / "agents" / "engine.md").write_text("# engine\n", encoding="utf-8")

    out = subprocess.run(
        [sys.executable, str(KIT / "mechanisms" / "cycle" / "route_domain.py"),
         "engine-repo", "--project-root", str(proj)],
        cwd=proj, capture_output=True, text=True, timeout=120, check=False)

    assert out.returncode == 0, out.stdout + out.stderr
    assert "BROKEN ROUTE" not in out.stdout

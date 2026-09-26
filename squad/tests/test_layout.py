"""Which of the three shapes is on disk, and the one that must not be silent."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.layout import Layout, has_kit, resolve


def _kit(at: Path) -> Path:
    for tree in ("skills", "rules", "hooks"):
        (at / tree).mkdir(parents=True, exist_ok=True)
    return at


def test_the_kit_own_repository_is_standalone(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    _kit(tmp_path)

    layout = resolve(tmp_path)

    assert layout is not None
    assert layout.kind == "standalone"
    assert layout.kit_dir == layout.eco == tmp_path.resolve()


def test_a_copy_install_puts_both_under_dot_claude(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    _kit(tmp_path / ".claude")

    layout = resolve(tmp_path)

    assert layout is not None and layout.kind == "copy"
    assert layout.kit_dir == layout.eco == (tmp_path / ".claude").resolve()


def test_a_plugin_install_separates_the_code_from_the_data(tmp_path: Path, monkeypatch) -> None:
    """The separation is the point: the consumer's agent cannot edit the kit."""
    kit = _kit(tmp_path / "elsewhere")
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(kit))

    layout = resolve(project)

    assert layout is not None and layout.kind == "plugin"
    assert layout.kit_dir == kit
    assert layout.eco == (project / ".claude").resolve()
    assert layout.kit_dir != layout.eco


def test_a_plugin_install_without_dot_claude_keeps_data_at_the_root(
        tmp_path: Path, monkeypatch) -> None:
    kit = _kit(tmp_path / "elsewhere")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(kit))

    layout = resolve(project)

    assert layout is not None and layout.eco == project.resolve()


def test_no_kit_anywhere_is_silent(tmp_path: Path, monkeypatch, capsys) -> None:
    """A project that does not use this must hear nothing at all."""
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

    assert resolve(tmp_path) is None
    assert capsys.readouterr() == ("", "")


def test_a_plugin_root_without_the_kit_is_loud(tmp_path: Path, monkeypatch, capsys) -> None:
    """Measured 2026-08-26: this case exited 0 without a word, and every gate was
    off while the session looked protected. Absent is silent; broken is not."""
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "empty"))

    assert resolve(project) is None
    err = capsys.readouterr().err
    assert "Incomplete install" in err
    assert "NOT active" in err, "the reader must learn the gates are off, not just that a path is odd"


def test_a_broken_plugin_root_never_falls_back_to_the_project(
        tmp_path: Path, monkeypatch) -> None:
    """Falling back would hide the corrupt install behind a working one."""
    project = _kit(tmp_path / "project")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "empty"))

    assert resolve(project, warn=False) is None


@pytest.mark.parametrize("missing", ["skills", "rules", "hooks"])
def test_all_three_trees_are_required(tmp_path: Path, missing: str) -> None:
    _kit(tmp_path)
    (tmp_path / missing).rmdir()

    assert has_kit(tmp_path) is False


def test_the_layout_is_frozen() -> None:
    """A hook that rewrites its own layout mid-run is a bug nobody would look for."""
    layout = Layout(Path("/k"), Path("/e"), Path("/p"), "standalone")

    with pytest.raises(AttributeError):
        layout.eco = Path("/other")  # type: ignore[misc] — assigning to a frozen field is the behaviour under test

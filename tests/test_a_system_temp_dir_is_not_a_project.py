"""A `.squad` left in `/tmp` made `/tmp` a project, and every run under it recorded there.

`project_root_for` walks up from the work it touched looking for a directory that owns a
write root. The walk was right about everything except where to stop: `/tmp` holds the
throwaway trees of every test, every smoke run and every manual `mktemp -d`, and one
`.squad` forgotten there turns all of them into one project.

Found by hunting a `/tmp/.squad` that kept reappearing. It was not a test — all four
batches of `tests/`, every slice and the whole suite in one invocation leave it absent —
it was residue from hand-run reproductions. The residue is the symptom; the defect is that
the walk accepts `/tmp` at all, because the next one will not be noticed either.

WHY THE STOP IS AT THE TEMP ROOT ITSELF AND NOT BELOW IT. `pytest`'s `tmp_path` lives
UNDER the system temp directory, and a test that builds a project there is building a real
project — the whole install suite does exactly that. Refusing everything under `/tmp` would
refuse those too. What is refused is the temp directory ITSELF as a root: `/tmp/.squad` is
somebody's leftover, `/tmp/pytest-of-x/test_y0/.squad` is a fixture.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_CYCLE = Path(__file__).resolve().parent.parent / "mechanisms" / "cycle"
sys.path.insert(0, str(_CYCLE))

from cycle_events import project_root_for  # noqa: E402


def test_a_squad_in_the_system_temp_dir_does_not_make_it_a_project(
    tmp_path: Path, monkeypatch,
) -> None:
    fake_tmp = tmp_path / "tmp"
    work = fake_tmp / "scratch-run" / "findings"
    work.mkdir(parents=True)
    (fake_tmp / ".squad").mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_tmp))

    root = project_root_for(work)

    assert root != fake_tmp, (
        "a forgotten `.squad` in the system temp dir makes every throwaway run record "
        "into one shared project"
    )
    assert root == work


def test_a_project_built_under_the_temp_dir_is_still_a_project(
    tmp_path: Path, monkeypatch,
) -> None:
    """THE CONTROL, and the reason the stop is not one level higher.

    `pytest`'s `tmp_path` is under the system temp directory and the install suite builds
    real projects there. A rule that refused everything below `/tmp` would refuse them.
    """
    fake_tmp = tmp_path / "tmp"
    project = fake_tmp / "pytest-of-someone" / "test_thing0" / "consumer"
    work = project / "work" / "findings"
    work.mkdir(parents=True)
    (project / ".squad").mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_tmp))

    assert project_root_for(work) == project


def test_the_walk_does_not_stop_early_at_a_real_project(tmp_path: Path) -> None:
    """THE OTHER CONTROL: ordinary resolution is untouched."""
    project = tmp_path / "repo"
    work = project / "deep" / "deeper"
    work.mkdir(parents=True)
    (project / ".squad").mkdir()

    assert project_root_for(work) == project


def test_the_real_system_temp_dir_is_refused_too(tmp_path: Path) -> None:
    """Not only a monkeypatched one — the default list must name the usual suspects.

    `/tmp` and `/var/tmp` are where residue actually accumulates, and a consumer whose
    `TMPDIR` points elsewhere gets that one from `tempfile.gettempdir()`.
    """
    from cycle_events import _is_system_temp_root

    assert _is_system_temp_root(Path("/tmp"))
    assert _is_system_temp_root(Path("/var/tmp"))
    assert not _is_system_temp_root(tmp_path)
    assert not _is_system_temp_root(Path("/"))

"""A first install leaves the record every later install reasons from.

`.kit-hooks.json` and `.kit-permissions.json` answer one question: what did the
KIT ship last time. Every subsequent install needs it to tell two things apart
that must never share an outcome — "the kit retired this" and "this project
removed it" — and `merge_permissions` states exactly that in its own comment.

Both files were written only by the MERGE path. A fresh install takes the other
branch (`cp settings.plugin.json`, because the target has no settings yet) and
wrote neither. Measured 2026-09-19 on a clean target: both absent.

So on a freshly installed consumer the first removal was not respected. A project
that deleted a hook from `settings.json` got it back on the next install, and the
reinstall after THAT respected the deletion — because by then a merge had finally
written the baseline. A rule that starts working on the second attempt is a rule
nobody can rely on and nobody can explain.

The failure shape is this repository's most common one, at the level of the
record rather than the check: the file the decision depends on did not exist, and
its absence was read as "nothing was removed" rather than "this cannot be told
yet". Writing it at the point the kit ships the hooks makes the absence mean what
it says — no install has happened here.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_INSTALL = _REPO / "mechanisms" / "distribution" / "install.sh"


@pytest.fixture(scope="module")
def fresh(tmp_path_factory) -> Path:
    target = tmp_path_factory.mktemp("clean")
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    subprocess.run(["bash", str(_INSTALL), str(target)],
                   capture_output=True, text=True, check=True)
    return target


@pytest.mark.parametrize("record", [".kit-hooks.json", ".kit-permissions.json"])
def test_the_baseline_exists_after_the_very_first_install(fresh: Path, record: str) -> None:
    path = fresh / ".claude" / record
    assert path.is_file(), (
        f"{record} is missing after a fresh install, so the next install cannot "
        f"tell a hook the project removed from one the kit never shipped")
    assert json.loads(path.read_text(encoding="utf-8")), f"{record} is empty"


def test_the_hook_baseline_names_what_was_actually_wired(fresh: Path) -> None:
    """A record that disagrees with the file it describes is worse than none."""
    settings = json.loads((fresh / ".claude" / "settings.json").read_text(encoding="utf-8"))
    baseline = json.loads((fresh / ".claude" / ".kit-hooks.json").read_text(encoding="utf-8"))

    wired = {event: {h.get("command") for group in groups for h in group.get("hooks", [])}
             for event, groups in (settings.get("hooks") or {}).items()}
    for event, commands in baseline.items():
        assert event in wired, f"{event} is recorded as shipped and is not in settings.json"
        for command in commands:
            assert command in wired[event], f"{event}: {command} recorded but not wired"


def test_the_first_removal_after_a_fresh_install_is_respected(tmp_path: Path) -> None:
    """The consequence, end to end. This is what the missing record cost."""
    target = tmp_path / "consumer"
    target.mkdir()
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    subprocess.run(["bash", str(_INSTALL), str(target)],
                   capture_output=True, text=True, check=True)

    settings = target / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert "UserPromptSubmit" in data["hooks"], "nothing to remove — the test proves nothing"
    data["hooks"].pop("UserPromptSubmit")
    settings.write_text(json.dumps(data, indent=2), encoding="utf-8")

    proc = subprocess.run(["bash", str(_INSTALL), str(target), "--force"],
                          capture_output=True, text=True)
    after = json.loads(settings.read_text(encoding="utf-8"))
    assert "UserPromptSubmit" not in after["hooks"], (
        "the first reinstall after a fresh install put back what the project removed")
    assert "left out" in proc.stdout, "the decision was respected in silence"

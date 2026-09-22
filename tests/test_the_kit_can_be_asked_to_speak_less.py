"""The kit spoke three times per turn and a project could not ask it to speak less.

Measured in a consumer on 2026-09-18: 1249 bytes in front of every prompt, 1835 once at
session start, 602 of advisory warnings at the end of a turn. The parsimony ladder's own
docstring argues the injection must be unconditional — *"a rule read at session start is a
rule forgotten by the fortieth prompt"* — and that argument is good for a session writing
code and false for one that is not. Asking what time it is got the ladder in front of it,
and a reader who sees doctrine attached to every question learns to skip doctrine.

`squad/injection.py` was designed and built inside that consumer's installed `.claude/`,
where the next `install.sh --force` would have erased it. Adopted here on 2026-09-22 (#164).

WHAT IT MUST NEVER REACH, and this file is where that stops being a comment:

  * `PreToolUse` — `boundary-check` and `validate-command` still refuse. A guard a config
    can silence is a guard that gets silenced on the day it would have mattered, by
    somebody who only wanted less text.
  * `Stop`'s BLOCKERS — a secret in the diff, production source with no changelog entry.
    Only the WARN half is advisory, and only the advisory half is noise.

A volume control and never a kill switch, kept apart by construction.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from squad.injection import QUIET_ENV, SETTING_FILE, is_quiet  # noqa: E402


def _kit(tmp_path: Path, setting: str | None) -> Path:
    kit = tmp_path / ".claude"
    (kit / "rules").mkdir(parents=True)
    if setting is not None:
        (kit / SETTING_FILE).write_text(setting, encoding="utf-8")
    return kit


@pytest.fixture(autouse=True)
def _no_ambient_override(monkeypatch):
    monkeypatch.delenv(QUIET_ENV, raising=False)


def test_speaking_is_the_default(tmp_path: Path) -> None:
    """THE CONTROL. A project that configured nothing hears what it always heard."""
    assert is_quiet(_kit(tmp_path, None)) is False


def test_the_project_can_ask_for_quiet(tmp_path: Path) -> None:
    assert is_quiet(_kit(tmp_path, "quiet = true\n")) is True


def test_the_variable_overrides_the_file_in_both_directions(
    tmp_path: Path, monkeypatch,
) -> None:
    """Turning it back ON matters as much as turning it off.

    A project quiet by default is one where somebody eventually needs the doctrine back,
    and editing a versioned file to get it for an afternoon is a change that gets
    committed by accident.
    """
    quiet_kit = _kit(tmp_path / "a", "quiet = true\n")
    loud_kit = _kit(tmp_path / "b", "quiet = false\n")

    monkeypatch.setenv(QUIET_ENV, "0")
    assert is_quiet(quiet_kit) is False
    monkeypatch.setenv(QUIET_ENV, "1")
    assert is_quiet(loud_kit) is True


def test_text_that_decides_nothing_falls_through_rather_than_quieting(
    tmp_path: Path, monkeypatch,
) -> None:
    """Silence is never the answer to a question that could not be read.

    A parse failure that quiets the kit removes the doctrine AND the report that
    something is wrong, which is this repository's most-repeated defect wearing its
    quietest face.
    """
    monkeypatch.setenv(QUIET_ENV, "maybe")

    assert is_quiet(_kit(tmp_path, "quiet = perhaps\n")) is False
    assert is_quiet(_kit(tmp_path / "c", "# only a comment\n")) is False
    assert is_quiet(None) is False


def test_an_unreadable_setting_file_does_not_quiet(tmp_path: Path) -> None:
    kit = _kit(tmp_path, None)
    (kit / SETTING_FILE).mkdir()  # a directory where a file belongs

    assert is_quiet(kit) is False


# ── the half it must never reach ─────────────────────────────────────────────

def _hook(name: str, payload: str, *, quiet: bool, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, QUIET_ENV: "1" if quiet else "0",
           "CLAUDE_PROJECT_DIR": str(cwd)}
    return subprocess.run([sys.executable, str(_ROOT / "hooks" / name)],
                          input=payload, capture_output=True, text=True,
                          check=False, env=env, cwd=str(cwd))


def test_quiet_does_not_silence_the_command_guard(tmp_path: Path) -> None:
    payload = ('{"hook_event_name":"PreToolUse","tool_name":"Bash",'
               '"tool_input":{"command":"git reset --hard HEAD~1"}}')

    out = _hook("validate-command.py", payload, quiet=True, cwd=_ROOT)

    assert out.returncode == 2, out.stdout + out.stderr
    assert "BLOCKED" in out.stdout + out.stderr


def test_quiet_does_not_silence_the_boundary_hook(tmp_path: Path) -> None:
    from squad.layout import _KIT_TREES

    consumer = tmp_path / "consumer"
    eco = consumer / ".claude"
    # A directory is a kit when it holds every tree `layout.has_kit` names; asked of the
    # owner rather than listed here, so a fourth tree does not quietly stop this fixture
    # from being a kit and turn the assertion below into a pass over nothing.
    for tree in _KIT_TREES:
        (eco / tree).mkdir(parents=True, exist_ok=True)
    (eco / ".kit-manifest.txt").write_text("mechanisms\n", encoding="utf-8")
    target = consumer / ".claude" / "mechanisms" / "cycle" / "x.py"
    payload = ('{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":'
               f'{{"file_path":"{target}","content":"x"}}}}')

    out = _hook("boundary-check.py", payload, quiet=True, cwd=consumer)

    assert out.returncode == 2, out.stdout + out.stderr
    assert "BOUNDARY VIOLATION" in out.stdout + out.stderr


# ── the three hooks, wired ───────────────────────────────────────────────────
#
# A module nothing calls is a capability that does not run — the defect this kit has
# named in its own gates twice today. These assert the wiring, not just the reader.

def test_all_three_unprompted_hooks_consult_the_setting() -> None:
    hooks = ("sessionstart-context.py", "userpromptsubmit-inject.py", "stop-validation.py")

    for name in hooks:
        body = (_ROOT / "hooks" / name).read_text(encoding="utf-8")
        assert "is_quiet" in body, f"{name} speaks unprompted and never asks"


def test_the_guards_do_not_import_it_at_all() -> None:
    """`PreToolUse` must not be able to consult a volume setting, by construction.

    Not "does not consult it today" — cannot. An import is how that stops being a
    convention: a guard with the function in scope is one line away from silence.
    """
    for name in ("validate-command.py", "boundary-check.py"):
        body = (_ROOT / "hooks" / name).read_text(encoding="utf-8")
        assert "is_quiet" not in body, f"{name} is a guard and must not reach the setting"


def test_the_stop_hook_suppresses_the_report_and_not_the_checks() -> None:
    """A volume control that stopped MEASURING is a kill switch under a quieter name."""
    body = (_ROOT / "hooks" / "stop-validation.py").read_text(encoding="utf-8")
    suppression = body.index("if warnings and is_quiet(")
    report = body.index("STOP VALIDATION — ADVISORY WARNINGS")
    blockers = body.index("STOP VALIDATION — HARD-GATE VIOLATION")

    assert suppression < report, "the suppression must reach the report, not the gates"
    assert suppression < blockers, "and must sit outside the blocking branch entirely"
    assert "blockers = []" not in body.split("is_quiet(")[1][:400], (
        "nothing near the suppression may empty the blocking half"
    )

"""A project can ask the kit to stop speaking into its sessions unprompted.

The kit injects on its own initiative three times per turn. Measured
2026-09-18 on a consumer:

    UserPromptSubmit   1249 bytes in front of EVERY prompt, unconditional
    SessionStart       1835 bytes once
    Stop                 602 bytes of advisory warnings at the end of a turn

The ladder's own docstring gives the reason it is unconditional — "a rule read at
session start is a rule forgotten by the fortieth prompt" — and that is true of a
session writing code. It is false of one that is not: asking what time it is gets
the parsimony ladder in front of it, and a reader who sees doctrine attached to
every question learns to skip doctrine.

So this is a VOLUME control, not an off switch for the kit. What stays on:

  * `PreToolUse` — `boundary-check` and `validate-command` still refuse. Being
    quiet is not being unprotected, and a guard that a config can silence is a
    guard that gets silenced on the day it would have mattered.
  * `Stop`'s BLOCKERS — a secret in the diff and production source with no
    changelog entry still stop the turn. Only the WARN half is advisory, and only
    the advisory half is noise.
  * `PostToolUse` lints, which say nothing when there is nothing to say.

`STOP_VALIDATION_WARN_ONLY=1` is the opposite axis and unaffected: it downgrades
blockers to warnings, where this suppresses warnings and never touches blockers.
The two compose without either one becoming a way to reach the other.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from squad.injection import QUIET_ENV, SETTING_FILE, is_quiet  # noqa: E402


@pytest.fixture
def kit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv(QUIET_ENV, raising=False)
    (tmp_path / "rules").mkdir()
    return tmp_path


def _write(kit: Path, body: str) -> None:
    (kit / SETTING_FILE).write_text(body, encoding="utf-8")


def test_the_default_is_unchanged(kit: Path) -> None:
    """No file and no variable means the kit behaves exactly as it always has.

    Pinned because the alternative would change nineteen installed consumers on
    their next update, silently, in the direction of saying less.
    """
    assert is_quiet(kit) is False


def test_a_project_can_declare_itself_quiet(kit: Path) -> None:
    _write(kit, "quiet = true\n")
    assert is_quiet(kit) is True


def test_the_file_is_read_the_way_every_other_rules_file_is(kit: Path) -> None:
    """`key = value`, `#` comments, whitespace — same as `notifications.txt`."""
    _write(kit, "# what this project chose\n\n   quiet   =   TRUE   # yes\n")
    assert is_quiet(kit) is True


def test_an_unreadable_setting_leaves_the_kit_speaking(kit: Path) -> None:
    """Silence is never the answer to a question that could not be read.

    A parse failure that quiets the kit removes the doctrine AND the report that
    something is wrong, which is the failure this repository names most often: a
    check that could not measure its subject reporting the quieter answer.
    """
    _write(kit, "quiet = perhaps\n")
    assert is_quiet(kit) is False


def test_the_variable_wins_in_both_directions(kit: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    """One session's override, over the project's default, either way.

    Turning it back ON for one session matters as much as turning it off: a
    project that is quiet by default is a project where someone eventually needs
    the doctrine back without editing a versioned file to get it.
    """
    _write(kit, "quiet = false\n")
    monkeypatch.setenv(QUIET_ENV, "1")
    assert is_quiet(kit) is True

    _write(kit, "quiet = true\n")
    monkeypatch.setenv(QUIET_ENV, "0")
    assert is_quiet(kit) is False


def test_a_meaningless_variable_does_not_decide(kit: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    _write(kit, "quiet = true\n")
    monkeypatch.setenv(QUIET_ENV, "maybe")
    assert is_quiet(kit) is True, "an unreadable override must not flip the project's choice"


def test_no_kit_means_no_opinion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(QUIET_ENV, raising=False)
    assert is_quiet(None) is False

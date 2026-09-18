"""The read-only zone, asked of the hooks that guard it.

`rules/reference-provenance.md` exists for a legal reason, not a stylistic one:
a literal copy of third-party material carries its licence into this repository.
Three of its four layers are hook-side and blocking — nothing is written INTO
the zone, nothing leaves it by command, and no commit message cites it.

TWO THINGS THESE TESTS RECORD
------------------------------
**The zone is `study-material/`, and it was not guarded.** The rule declared
`study-material/**` while every regex matched `records/(references|tools)/`.
`study-material/` exists in this repository; neither of the other two does. So
the layer that guards the zone guarded nothing at all, and the messages said
otherwise. Measured 2026-09-01.

**`records/references/` was retired, and that is a loss, stated.** It held
cloned peer projects, which the Cycle's DISCOVER studied. Squad inverted that
question on purpose — `README.md`: *"Prior art can never be evidence"* — and the
same session zeroed its weight in `assess_confidence.py`. A path nothing writes
to is protection nobody collects, so it left the zone. What that costs: a
consumer still holding material there is no longer guarded, which is why the
rule now tells them to move it.

These were ported from four shell test files that NOTHING executed — not CI, not
pytest, not `run_slice_tests.sh`. Three of the four already failed, on exactly
the case above. That is how a guard stays broken for months.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _hook(name: str) -> Path:
    found = sorted(p for p in (REPO / "hooks").glob(f"{name}.*") if p.suffix in (".sh", ".py"))
    assert len(found) == 1, f"expected one implementation of {name}, found {found}"
    return found[0]


def _run(name: str, payload: dict) -> subprocess.CompletedProcess:
    hook = _hook(name)
    cmd = ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]
    return subprocess.run(cmd, input=json.dumps(payload), capture_output=True,
                          text=True, cwd=REPO, check=False)


def _write(path: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Write",
            "tool_input": {"file_path": path}}


def _bash(command: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": command}}


# ── layer 0: nothing is written INTO the zone ─────────────────────────────────


@pytest.mark.parametrize("path", [
    "study-material/sometool/config.yaml",
    ".claude/study-material/tool/main.go",
    "/abs/project/study-material/vendor/lib.py",
    "study-material/readme.md",
])
def test_writing_into_the_zone_is_blocked(path: str) -> None:
    """The zone stays pristine: it is material we read, never material we edit."""
    assert _run("boundary-check", _write(path)).returncode == 2, path


@pytest.mark.parametrize("path", [
    "records/discoveries/blueprints/finding.md",   # where findings belong
    "src/main.py",
    "rules/testing.md",
    "docs/study-material-guide.md",                # names the zone, is not in it
    "study-materials/other.md",                    # near-miss, different directory
])
def test_writing_outside_the_zone_is_allowed(path: str) -> None:
    assert _run("boundary-check", _write(path)).returncode == 0, path


def test_an_empty_path_is_allowed() -> None:
    """Nothing to judge is not a violation."""
    assert _run("boundary-check", {"hook_event_name": "PreToolUse",
                                   "tool_name": "Write",
                                   "tool_input": {}}).returncode == 0


def test_the_retired_path_is_no_longer_guarded() -> None:
    """DOCUMENTED LOSS, not an oversight.

    `records/references/` left the zone with the practice that filled it. A
    consumer still holding material there is unguarded — `reference-provenance`
    says so and tells them to move it. Pinned so that re-adding the path is a
    deliberate act with a failing test attached, rather than a quiet revival.
    """
    assert _run("boundary-check", _write("records/references/peer/README.md")).returncode == 0


# ── layer 1: content does not leave the zone by command ───────────────────────


@pytest.mark.parametrize("command", [
    "cp study-material/tool/src.py ./mine.py",
    "mv study-material/a.txt src/",
    "rsync -a study-material/lib/ ./vendor/",
    "cat study-material/x.py > mine.py",
    "cat study-material/x.py | tee mine.py",
])
def test_copying_content_out_of_the_zone_is_blocked(command: str) -> None:
    """Reading is the zone's purpose; duplicating its bytes is what carries the
    licence across."""
    assert _run("validate-command", _bash(command)).returncode == 2, command


@pytest.mark.parametrize("command", [
    "cat study-material/tool/src.py",
    "grep -r pattern study-material/",
    "ls study-material/",
])
def test_reading_the_zone_stays_allowed(command: str) -> None:
    """§ 3 of the rule: reading, grepping and listing are the entire point."""
    assert _run("validate-command", _bash(command)).returncode == 0, command


# ── layer 2: the public history never cites the zone ──────────────────────────


def test_a_commit_message_citing_the_zone_is_blocked() -> None:
    assert _run("validate-command", _bash(
        'git commit -m "port the approach from study-material/tool/core.py"'
    )).returncode == 2


def test_an_ordinary_commit_message_is_allowed() -> None:
    assert _run("validate-command", _bash('git commit -m "fix: parser drops trailing comma"'
                                          )).returncode == 0

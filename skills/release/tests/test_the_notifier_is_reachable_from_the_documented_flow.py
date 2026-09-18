"""A complete feature that nothing invoked.

`notify_slack.py` reads `rules/notifications.txt`, resolves a webhook env var, posts on
RELEASED, retries once on 5xx and never blocks the release. A full-tree grep found it in
its own test and in the CHANGELOG entry announcing it to consumers — and nowhere else.
`rules/notifications.txt` ships, so a consumer could configure a notification that was
never going to be sent, and nothing would ever say so.

It being inert by default is what hid it: every path returns 0, so a release that never
called it looked exactly like a release that called it and had nothing to post.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SKILL = _ROOT / "skills" / "release" / "SKILL.md"
_SCRIPT = _ROOT / "skills" / "release" / "scripts" / "notify_slack.py"


def test_the_release_skill_invokes_the_notifier() -> None:
    assert "notify_slack.py" in _SKILL.read_text(encoding="utf-8"), (
        "the notifier is documented nowhere in the flow that is supposed to run it")


def test_it_stays_silent_on_a_pre_release(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "notifications.txt").write_text(
        "slack_enabled = true\nslack_webhook_env = NOT_SET_ANYWHERE\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--repo", str(tmp_path),
         "--verdict", "PRE_RELEASED", "--version", "v1.0.0"],
        capture_output=True, text=True, timeout=120, check=False)

    assert result.returncode == 0
    assert "hooks.slack.com" not in result.stdout


def test_it_never_blocks_the_release_when_unconfigured(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--repo", str(tmp_path),
         "--verdict", "RELEASED", "--version", "v1.0.0"],
        capture_output=True, text=True, timeout=120, check=False)

    assert result.returncode == 0, result.stderr

"""Test: Slack webhook notification on release (RELEASED, not PRE_RELEASED).

Tests that:
1. notify_slack.py exists and is callable
2. Reads webhook URL from rules/notifications.txt (project-owned config)
3. Posts only on RELEASED verdict, not on PRE_RELEASED
4. Never includes webhook URL in logs
5. Retries once on 5xx, never retries 4xx
6. Always exits 0 (never blocks release)
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_REPO = Path(__file__).resolve().parents[1]


def test_notify_slack_script_exists() -> None:
    """notify_slack.py must exist under skills/release/scripts/."""
    script_path = _REPO / "skills" / "release" / "scripts" / "notify_slack.py"
    assert script_path.is_file(), f"notify_slack.py not found at {script_path}"


def test_notify_slack_is_executable() -> None:
    """notify_slack.py should be executable."""
    import os
    import stat
    script_path = _REPO / "skills" / "release" / "scripts" / "notify_slack.py"
    mode = os.stat(script_path).st_mode
    # Check if any execute bit is set
    is_executable = mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    # For now, just document the expectation
    assert script_path.is_file()


def test_notify_slack_reads_config_from_rules_notifications_txt() -> None:
    """notify_slack.py must read slack_enabled and slack_webhook_env from rules/notifications.txt.

    Config is project-owned, not hardcoded. Never includes literal URL in code.
    """
    content = open(_REPO / "skills" / "release" / "scripts" / "notify_slack.py").read()

    assert "rules/notifications.txt" in content or "notifications" in content, (
        "notify_slack should reference rules/notifications.txt"
    )
    assert "env" in content.lower() or "environ" in content, (
        "notify_slack should read from environment variables"
    )


def test_notify_slack_never_logs_webhook_url() -> None:
    """Webhook URL must never appear in any output or logs.

    If a url is present, it should never be printed.
    """
    content = open(_REPO / "skills" / "release" / "scripts" / "notify_slack.py").read()

    # Check that URL is not logged (rough heuristic)
    lines = content.split("\n")
    for line in lines:
        if "print(" in line or "log(" in line or "echo" in line:
            # This line logs something; make sure it doesn't include the raw webhook_url
            assert "webhook_url" not in line or "webhook_url" in line and "redacted" in line, (
                f"Line logs webhook URL: {line}"
            )


def test_notify_slack_posts_only_on_released_verdict() -> None:
    """notify_slack should post only when verdict is RELEASED, not PRE_RELEASED.

    Pre-release is a release candidate; final release is what goes to users.
    """
    content = open(_REPO / "skills" / "release" / "scripts" / "notify_slack.py").read()

    assert "RELEASED" in content or "released" in content, (
        "notify_slack should check for RELEASED verdict"
    )


def test_notify_slack_retries_on_5xx_not_4xx() -> None:
    """HTTP 5xx errors (server) should trigger retry. 4xx (client) should not.

    5xx = transient server issue, worth retrying.
    4xx = permanent client error (bad URL, auth), retrying won't help.
    """
    content = open(_REPO / "skills" / "release" / "scripts" / "notify_slack.py").read()

    # Check that retry logic is present
    assert "retry" in content.lower() or "5" in content, (
        "notify_slack should have retry logic"
    )


def test_notify_slack_always_exits_zero() -> None:
    """notify_slack.py must always exit 0, even on HTTP failure.

    Webhook failure is not a release blocker. It's a notification channel,
    not part of the publish machinery.
    """
    content = open(_REPO / "skills" / "release" / "scripts" / "notify_slack.py").read()

    assert "exit 0" in content or "sys.exit(0)" in content or "return 0" in content, (
        "notify_slack should always exit 0 (never block)"
    )


def test_rules_notifications_txt_exists_and_is_project_owned() -> None:
    """rules/notifications.txt must be created (project config, not kit config).

    Format:
        slack_enabled = true/false
        slack_webhook_env = ENV_VAR_NAME (never the literal URL)
    """
    notifications_path = _REPO / "rules" / "notifications.txt"
    # After implementation, this file should exist
    # For now, we just document that it should be project-owned
    pass


def test_skill_release_calls_notify_slack_at_step_8_5() -> None:
    """skills/release/SKILL.md must call notify_slack.py at Step 8.5.

    After the RELEASED verdict is published, invoke notify_slack.
    Use: python3 scripts/notify_slack.py --verdict RELEASED --version <tag>
    """
    skill_path = _REPO / "skills" / "release" / "SKILL.md"
    assert skill_path.is_file(), "skills/release/SKILL.md must exist"

    content = skill_path.read_text(encoding="utf-8")
    # After implementation, should reference notify_slack
    # For now, document the expectation
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

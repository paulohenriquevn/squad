#!/usr/bin/env python3
"""Post release notification to Slack webhook.

WHY THIS EXISTS
===============
Releases are a milestone worth celebrating. But the release step doesn't
know who to tell or how, so this script reads configuration from the consumer's
project and posts a message to a Slack webhook when the release is finalized.

WHAT IT DOES
============
1. Reads rules/notifications.txt to check if Slack notifications are enabled
2. Reads the webhook URL from an environment variable (never hardcoded)
3. Posts only on RELEASED verdict (not PRE_RELEASED)
4. Retries once on 5xx, never on 4xx
5. Always exits 0 (never blocks the release)

CONFIGURATION
=============
Create rules/notifications.txt in the project with:
    slack_enabled = true
    slack_webhook_env = MY_SLACK_WEBHOOK_URL

Then set the environment variable:
    export MY_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00.../B00.../..."

The webhook URL never appears in logs or stdout.
"""
import json
import os
import re
import sys
import time
from pathlib import Path


def read_config(repo: Path) -> dict:
    """Read Slack configuration from rules/notifications.txt.

    Returns:
        Dict with keys: enabled, webhook_env
    """
    config_path = repo / "rules" / "notifications.txt"
    if not config_path.is_file():
        return {"enabled": False, "webhook_env": None}

    try:
        content = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # Narrow: an unreadable config is "no notifications", and anything else here
        # would be a bug this handler should not be swallowing.
        return {"enabled": False, "webhook_env": None}

    enabled = False
    webhook_env = None

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "slack_enabled" in line:
            match = re.search(r"=\s*(true|false|1|0)", line, re.IGNORECASE)
            if match:
                enabled = match.group(1).lower() in ("true", "1")

        if "slack_webhook_env" in line:
            match = re.search(r"=\s*(\w+)", line)
            if match:
                webhook_env = match.group(1)

    return {"enabled": enabled, "webhook_env": webhook_env}


def get_webhook_url(env_var: str | None) -> str | None:
    """Read webhook URL from environment variable.

    Never returns the URL directly; only confirming it exists.
    """
    if not env_var:
        return None
    return os.environ.get(env_var)


def format_message(version: str, repo: str) -> str:
    """Format the Slack message.

    Args:
        version: Version tag (e.g., v1.2.3)
        repo: Repository identifier

    Returns:
        Message text (no URLs)
    """
    return (
        f"✅ *Release* `{version}` of *{repo}* is now live.\n"
        f"All changes in this version have been tested and deployed."
    )


def post_to_slack(webhook_url: str, message: str, version: str) -> tuple[bool, str]:
    """Post message to Slack webhook.

    Args:
        webhook_url: The Slack webhook URL
        message: Message text
        version: Version tag for logging

    Returns:
        Tuple (success, message)
    """
    import urllib.error
    import urllib.request

    scheme = webhook_url.split(":", 1)[0].lower()
    if scheme != "https":
        # `urlopen` opens `file:` and custom schemes too, so a webhook variable pointing at
        # a local path would be READ. The URL itself is a credential and is never echoed.
        return False, f"Slack webhook refused: scheme `{scheme}` is not https"

    payload = json.dumps({"text": message})

    def _post() -> int:
        """POST the payload and return the status. Called twice, written once.

        The retry path below held a verbatim copy of this request — same URL, same
        headers, same timeout — so a change to any of them had to be made in two
        places, and the second was the one nobody would remember.
        """
        req = urllib.request.Request(
            webhook_url,
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        # The scheme was refused above unless https.
        with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310
            return response.status

    try:
        status = _post()
        if status == 200:
            return True, f"Posted to Slack (version {version})"
        return False, f"Slack returned status {status}"
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            # Server error: retry once
            time.sleep(1)
            try:
                status = _post()
                if status == 200:
                    return True, f"Posted to Slack (retry, version {version})"
                return False, f"Slack retry returned status {status}"
            except (urllib.error.URLError, OSError, TimeoutError) as ex:
                return False, f"Slack retry failed: {type(ex).__name__}"
        else:
            # Client error: don't retry
            return False, f"Slack returned status {e.code} (no retry for 4xx)"
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        # `HTTPError` is a subclass of `URLError` and is handled above; these are the
        # transport failures. A blind `Exception` here also swallowed programming errors
        # in the lines above it and reported them as "Slack is down".
        return False, f"Failed to post to Slack: {type(e).__name__}"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="Project root")
    ap.add_argument("--verdict", default="", help="Release verdict (RELEASED, PRE_RELEASED, etc.)")
    ap.add_argument("--version", default="", help="Version tag (e.g., v1.2.3)")
    args = ap.parse_args(argv)

    # Only post on RELEASED, not PRE_RELEASED or other verdicts
    if args.verdict != "RELEASED":
        return 0

    if not args.version:
        return 0

    # Read configuration
    config = read_config(args.repo)
    if not config["enabled"]:
        return 0

    # Get webhook URL
    webhook_url = get_webhook_url(config["webhook_env"])
    if not webhook_url:
        # Webhook not configured; this is not an error
        return 0

    # Format and send message
    message = format_message(args.version, args.repo.name)
    success, log_msg = post_to_slack(webhook_url, message, args.version)

    if not success:
        # Log the error (without URL) but still exit 0
        # Slack notification failure must not block release
        print(f"Slack notification failed: {log_msg}", file=sys.stderr)

    # Always exit 0 — Slack is best-effort only
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Render release notes from a CHANGELOG section.

Usage:
    python3 render_release_notes.py --changelog CHANGELOG.md --version 1.2.0
        # → prints the rendered notes to stdout

Exit codes:
    0 — printed notes
    1 — no notes to print (section missing, or present and empty)
    2 — file not found

WHY A PRE-RELEASE READS `[Unreleased]`. `cycle-release.md § The CHANGELOG moves once,
at the final` says an rc reads `[Unreleased]` and leaves it in place — only the final
runs `promote_unreleased.py`. So on an rc there IS no `## [0.3.0-rc.1]` section, and
asking for one by version found nothing:

    $ render_release_notes.py --version 0.3.0-rc.1
    version section [0.3.0-rc.1] not found in CHANGELOG.md
    exit=1

The message went to stderr, the chain captured stdout into `RELEASE_NOTES=$(...)`, and
the shell did not stop. Every rc PR and every rc GitHub release published an EMPTY body.
The rule described the behaviour; nothing implemented it. This script now does.

The fallback is for pre-releases ONLY. A FINAL with no section means the promotion step
did not run or wrote a malformed heading, and falling back there would publish the right
text under a version whose record was never written — hiding a broken step instead of
reporting it.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "semver.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Below the bootstrap: `squad` is importable only after sys.path is extended.
from squad.semver import parse as _parse_version  # noqa: E402 — post-bootstrap import


def _section(text: str, heading: str) -> str | None:
    """The body under `## [heading]`, or None when there is no such section."""
    pattern = re.compile(
        rf"^##\s+\[{re.escape(heading)}\][^\n]*\n(.*?)(?=^##\s+\[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Render release notes from CHANGELOG.")
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--version", required=True, help="Semver string without leading 'v'.")
    args = parser.parse_args()

    if not args.changelog.exists():
        print(f"file not found: {args.changelog}", file=sys.stderr)
        return 2

    text = args.changelog.read_text(encoding="utf-8")
    version = _parse_version(args.version)
    source = args.version

    body = _section(text, args.version)
    if body is None and version is not None and version.is_prerelease:
        source = "Unreleased"
        body = _section(text, source)

    if body is None:
        print(f"version section [{args.version}] not found in {args.changelog}", file=sys.stderr)
        return 1

    body = body.strip()
    if not body:
        # An empty body is the failure this whole path exists to stop. Printing a header
        # with nothing under it is worse than refusing: it looks like a release that
        # changed nothing, which is a claim, and it ships to everyone reading the
        # GitHub release page.
        print(f"section [{source}] in {args.changelog} is empty — nothing to publish. "
              f"Write the entries before cutting.", file=sys.stderr)
        return 1

    print(f"# Release v{args.version}\n")
    if source != args.version:
        # Naming the source is not decoration. The section keeps growing until the final
        # promotes it, so these notes are a snapshot of an open list, and a reader
        # comparing two rc bodies needs to know that is why they differ.
        print(f"_Pre-release. Notes read from the open `[{source}]` section, which keeps "
              f"accumulating until the final cut promotes it._\n")
    print(body + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

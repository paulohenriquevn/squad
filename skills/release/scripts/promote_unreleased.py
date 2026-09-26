#!/usr/bin/env python3
"""Promote CHANGELOG [Unreleased] body to a versioned section; leave [Unreleased] empty.

Preserves Keep-a-Changelog category ordering:
  Added → Changed → Deprecated → Removed → Fixed → Security

Usage:
    python3 promote_unreleased.py --changelog CHANGELOG.md --version 1.2.0 --date 2026-06-04

Exit codes:
    0 — rewrite successful
    1 — [Unreleased] section absent or empty
    2 — file not found / parse error
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

CATEGORY_ORDER = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]


#: Keep-a-Changelog headings carry a plain semver, no leading `v`. The optional
#: suffix covers the `-rc.N` cuts this kit makes.
for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "semver.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Below the bootstrap: `squad` is importable only after sys.path is extended.
from squad.semver import (  # noqa: E402 — post-bootstrap import
    parse_release as _parse_release,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote CHANGELOG [Unreleased] to a versioned section.")
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--version", required=True, help="Semver string without leading 'v' (e.g. '1.2.0').")
    parser.add_argument("--date", required=True, help="ISO date (YYYY-MM-DD).")
    args = parser.parse_args()

    # Both go into a heading that is never edited again, and `render_release_notes.py`
    # looks the section up by exact string. A typo produced `## [1.2.O] - yesterday` in
    # the permanent record, and the reader was then told "version section [1.2.0] not
    # found" — pointing at their argument instead of at the malformed heading three
    # commits back. This is the last writer before the record hardens.
    # ONE version, or several — `acme-core 0.69.0, @acme/http 2.3.0`. A monorepo cuts
    # packages together and Keep-a-Changelog has no opinion about the text between the
    # brackets; this took a single semver and refused the shape its own consumers release
    # in most of the time, so the promotion was performed by hand. Every component is still
    # validated, and one bad component refuses the whole line: partial acceptance writes a
    # typo into a heading nobody edits again.
    components = _parse_release(args.version)
    if components is None:
        print(f"not a release line this kit cuts: {args.version!r}. Expected "
              f"MAJOR.MINOR.PATCH, optionally -rc.N, no leading 'v' — or several as "
              f"'<package> <version>' separated by commas.", file=sys.stderr)
        return 2

    # `cycle-release.md § The CHANGELOG moves once, at the final` has always said an rc
    # must NOT run this, and until 2026-09-21 nothing enforced it — the old pattern
    # accepted ANY pre-release suffix. Promoting at `-rc.1` empties `[Unreleased]`, so
    # `-rc.2` and the final have nothing to publish, and the entries end up filed under
    # a version that was still a candidate. The section is the milestone's changelog and
    # it moves ONCE.
    # Per component: a line is a pre-release if ANY package in it is. Promoting at rc
    # empties `[Unreleased]` for every package in the heading, not only the candidate one.
    if any(version.is_prerelease for _, version in components):
        print(f"refusing to promote under a pre-release: {args.version}. An rc reads "
              f"[Unreleased] for its notes and LEAVES IT IN PLACE; only the final cut "
              f"promotes it (rules/cycle-release.md § The CHANGELOG moves once, at the "
              f"final).", file=sys.stderr)
        return 2
    try:
        date.fromisoformat(args.date)
    except ValueError:
        print(f"not an ISO date: {args.date!r}. Expected YYYY-MM-DD.", file=sys.stderr)
        return 2

    if not args.changelog.exists():
        print(f"file not found: {args.changelog}", file=sys.stderr)
        return 2

    text = args.changelog.read_text(encoding="utf-8")

    # B-046 — refuse a file carrying more than one `## [Unreleased]`.
    #
    # This function matches the FIRST heading and stops, so a second one was not skipped with a
    # warning: it was never seen. Measured on this repository, `grep -n "^## \[Unreleased\]"`
    # returned lines 6 and 610, and both releases cut in one session promoted straight past it.
    #
    # It REFUSES rather than merging or picking. The stale section here duplicated an entry already
    # filed under a released version, so merging would move a shipped entry back into the unreleased
    # set and re-announce it — and which section is correct is a judgement about what shipped, which
    # a script cannot make. Warning and continuing was rejected too: that is today's behaviour minus
    # the silence, and the release would still be cut from a file the tool distrusts
    # (`rules/error-handling.md` § 2 — fail fast at the boundary).
    #
    # Both line numbers are named, because a message that only says "duplicate" announces a problem
    # without pointing at it.
    headings = [
        line_number
        for line_number, line in enumerate(text.splitlines(), start=1)
        if re.match(r"^##\s+\[Unreleased\]", line)
    ]
    if len(headings) > 1:
        locations = ", ".join(str(n) for n in headings)
        print(
            f"{len(headings)} '## [Unreleased]' sections found, at lines {locations} — "
            "a release cannot be cut from a CHANGELOG with more than one. "
            "Decide which is the record and delete the other; this script will not guess.",
            file=sys.stderr,
        )
        return 1

    pattern = re.compile(
        r"(?P<head>^##\s+\[Unreleased\][^\n]*\n)(?P<body>.*?)(?=^##\s+\[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        print("no [Unreleased] section found", file=sys.stderr)
        return 1

    body = match.group("body")
    if not any(line.strip().startswith("- ") for line in body.splitlines()):
        print("[Unreleased] is empty", file=sys.stderr)
        return 1

    # Re-order categories to canonical order; preserve unrecognized headings at the end.
    sections: dict[str, list[str]] = {}
    current: str | None = None
    leading_blank: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            current = stripped[4:].strip()
            sections.setdefault(current, [])
        elif current is None:
            leading_blank.append(line)
        else:
            sections[current].append(line)

    ordered_lines: list[str] = []
    for cat in CATEGORY_ORDER:
        if cat in sections and any(ln.strip().startswith("- ") for ln in sections[cat]):
            ordered_lines.append(f"### {cat}")
            ordered_lines.extend(sections[cat])
            ordered_lines.append("")
            del sections[cat]
    # Preserve any unrecognized categories.
    for cat, lines in sections.items():
        if any(ln.strip().startswith("- ") for ln in lines):
            ordered_lines.append(f"### {cat}")
            ordered_lines.extend(lines)
            ordered_lines.append("")

    new_versioned_body = "\n".join(ordered_lines).rstrip() + "\n\n"

    fresh_unreleased = (
        "## [Unreleased]\n"
        "\n"
        "### Added\n"
        "\n"
        "### Changed\n"
        "\n"
        "### Deprecated\n"
        "\n"
        "### Removed\n"
        "\n"
        "### Fixed\n"
        "\n"
        "### Security\n"
        "\n"
    )

    versioned_header = f"## [{args.version}] - {args.date}\n\n"

    new_text = (
        text[: match.start()]
        + fresh_unreleased
        + versioned_header
        + new_versioned_body
        + text[match.end():]
    )

    args.changelog.write_text(new_text, encoding="utf-8")
    print(f"promoted [Unreleased] -> [{args.version}] in {args.changelog}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Compute the next semver version from current tag + bump level.

Bump-level resolution:
- Explicit: --bump {major,minor,patch} wins.
- Auto: derive from CHANGELOG.md [Unreleased] sections.
  - major: ### Removed non-empty OR any ### Changed entry starts with 'BREAKING:'
  - minor: ### Added non-empty AND no major trigger
  - patch: only ### Fixed / ### Security entries
  - ambiguous: prints 'AMBIGUOUS' to stdout, exits 3.

Usage:
    python3 compute_next_version.py --current v1.2.3 --bump auto --changelog CHANGELOG.md

Exit codes:
    0 — printed next version (e.g. '1.2.4')
    2 — error (invalid current tag, etc.)
    3 — bump cannot be derived; user must specify
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def parse_semver(tag: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(tag.strip())
    if not m:
        print(f"invalid semver tag: {tag}", file=sys.stderr)
        sys.exit(2)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def extract_unreleased_subsections(changelog: Path) -> dict[str, list[str]]:
    text = changelog.read_text(encoding="utf-8")
    match = re.search(
        r"^##\s+\[Unreleased\][^\n]*\n(.*?)(?=^##\s+\[|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return {}

    body = match.group(1)
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            current = stripped[4:].strip()
            sections.setdefault(current, [])
        elif current and stripped.startswith("- "):
            sections[current].append(stripped[2:].strip())
    return {k: v for k, v in sections.items() if v}


# B-044 — the marker is what matters, not the decoration around it.
#
# The parser strips the list marker and nothing else, so `- **BREAKING: foo**` arrived here as
# `**BREAKING: foo**` and `startswith("BREAKING:")` was false. Measured on two CHANGELOGs differing
# only in bold: the bare spelling derived 1.0.0 and the bold one derived 0.61.0 — and there was no
# pause, because the rule picked confidently and wrongly. House style is the spelling that failed:
# 43 of 61 entries in this CHANGELOG are bold.
#
# Stripped by CHARACTER SET rather than by enumerating `**`, `__`, `` ` `` and friends: the defect
# being fixed IS a spelling nobody enumerated, so a list of variants would fix the two someone
# thought of and fail on the third. A markdown parser would be a dependency and a maintenance
# surface for the question "does this line begin with a word" (Rules 9 and 10).
#
# The START ANCHOR stays. It is what separates a marked entry from prose that merely mentions the
# word — "…this avoids a breaking change…" must not ship a major bump, and a test pins that.
_EMPHASIS = "*_`~ "

# F-6 — the first fix hardened the DECORATION and left the wording. `**BREAKING CHANGE: foo**` — the
# Conventional Commits spelling, and the one most people reach for — still derived `minor`, silently.
# Same defect one word over, found by review immediately after the decoration was fixed.
_BREAKING = re.compile(r"^BREAKING(\s+CHANGE)?\s*:")


def _without_emphasis(entry: str) -> str:
    return entry.lstrip(_EMPHASIS)


def _is_breaking(entry: str) -> bool:
    return bool(_BREAKING.match(_without_emphasis(entry).upper()))


def derive_bump(unreleased: dict[str, list[str]]) -> str | None:
    if not unreleased:
        return None

    removed = unreleased.get("Removed", [])
    changed = unreleased.get("Changed", [])
    added = unreleased.get("Added", [])
    fixed = unreleased.get("Fixed", [])
    security = unreleased.get("Security", [])

    breaking_in_changed = any(_is_breaking(c) for c in changed)
    if removed or breaking_in_changed:
        return "major"
    if added:
        # Decided BEFORE `changed` on purpose. Under 0.x a breaking change is a minor bump, so when
        # `Added` is present the answer is minor whether or not the `Changed` entry breaks anyone —
        # the undecidable fact stops mattering. Pausing here would ask a question whose two answers
        # agree, and a pause nobody can act on differently is how pauses stop being read.
        return "minor"
    if changed:
        # B-094 — UNDECIDABLE, and therefore a pause rather than a guess.
        #
        # `cycle-release.md § Bump-level derivation` already argues this: a non-breaking `Changed`
        # is a MINOR if a caller depended on the old behaviour and a PATCH if not, and the section
        # text does not carry that fact. The pause is how the question reaches a human.
        #
        # It used to fire only when `Changed` was ALONE. Beside `Fixed` or `Security` — the common
        # shape — control fell through to `patch` below without `changed` ever being consulted.
        # Measured on the real 0.72.0 CHANGELOG: `--bump auto` returned `0.71.1`, exit 0, no pause,
        # for a release whose `### Changed` entry says two published functions now reject an input
        # class they previously accepted. That release went out as a minor only because a human
        # overrode the derivation by hand.
        #
        # Guessing either way is worse than asking. `minor` turns every reworded entry into a
        # compatibility signal; `patch` understates a real break and delivers it silently to anyone
        # on a caret range — the exact failure semver exists to prevent.
        return None
    if fixed or security:
        return "patch"
    return None


def level_under_zerover(level: str, current: tuple[int, int, int]) -> str:
    """B-100 — map a DERIVED level onto 0.x semantics. Not applied to an explicit `--bump`.

    `rules/cycle-release.md` states the policy: *"This package is 0.x ... Under 0.x a breaking
    change is a MINOR bump and a compatible one is a PATCH."* `derive_bump` answers with the semver
    CLASS, which is right; the class then has to be placed, and under 0.x the breaking class sits
    at the minor position because 0.x has made no compatibility promise at the major position yet.

    Measured 2026-08-20, cutting the release right after B-094 fixed the sibling branch of this
    same function: the real B-076 CHANGELOG carries a `### Removed`, and `--bump auto` returned
    **1.0.0**. Wrong twice over — the wrong number, and `rules/public-copy.md` § 3 forbids the 1.0
    claim until sustained production evidence exists. A script that can cut 1.0.0 unattended can
    make a marketing claim nobody approved.

    WHY HERE AND NOT INSIDE `bump_version`: provenance. `--bump major` is an assertion by a human;
    `--bump auto` is an inference by a script. Only the inference needs the guard rail, and putting
    the mapping in `bump_version` would have made 1.0.0 permanently unreachable — turning a guard
    into a cap, which `cycle-release.md`'s "revisit at 1.0.0" explicitly anticipates.
    """
    if current[0] == 0 and level == "major":
        return "minor"
    return level


def bump_version(current: tuple[int, int, int], level: str) -> str:
    major, minor, patch = current
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    print(f"invalid bump level: {level}", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute next semver from current tag + bump.")
    parser.add_argument("--current", required=True, help="Current version tag (v1.2.3 or 1.2.3).")
    parser.add_argument(
        "--bump",
        default="auto",
        choices=("auto", "major", "minor", "patch"),
        help="Bump level. 'auto' derives from CHANGELOG.",
    )
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    args = parser.parse_args()

    current = parse_semver(args.current)

    if args.bump == "auto":
        if not args.changelog.exists():
            print(f"changelog not found for auto-bump: {args.changelog}", file=sys.stderr)
            return 2
        unreleased = extract_unreleased_subsections(args.changelog)
        derived = derive_bump(unreleased)
        if derived is not None:
            # B-100 — the DERIVED class is placed under 0.x semantics here, where we know it came
            # from an inference rather than from a person.
            derived = level_under_zerover(derived, current)
        if derived is None:
            # B-047 — the pause STAYS, and it stops being one word.
            #
            # A `Changed`-only [Unreleased] is an ordinary release shape — "we changed how something
            # already published behaves, without adding or removing anything" — and it is genuinely
            # undecidable from the section alone, BECAUSE this package is 0.x. Under 0.x a breaking
            # change is a MINOR bump and a compatible one is a PATCH, so the level depends on a fact
            # the section does not contain. Guessing minor turns every reworded entry into a
            # compatibility signal; guessing patch understates a real break — the failure semver
            # exists to prevent, delivered silently to anyone on a caret range.
            #
            # stdout keeps EXACTLY `AMBIGUOUS` because `skills/release/SKILL.md` parses it and a
            # caller may capture it into a version variable. The question goes to stderr, where a
            # human reading a paused chain looks.
            print("AMBIGUOUS")
            print(
                "\n"
                "The [Unreleased] sections do not determine a level: no `Added`, no `Removed`,\n"
                "and no entry opening with `BREAKING:`.\n"
                "\n"
                "  The question: does this change behaviour a caller depends on?\n"
                "\n"
                "    yes -> minor   (under 0.x, MINOR is the breaking level)\n"
                "    no  -> patch   (a compatible change: internals, wording, performance)\n"
                "\n"
                "Re-run with --bump minor or --bump patch. rules/cycle-release.md\n"
                "\u00a7 Bump-level derivation records why this is not derived.",
                file=sys.stderr,
            )
            return 3
        bump = derived
    else:
        bump = args.bump

    next_version = bump_version(current, bump)
    print(next_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())

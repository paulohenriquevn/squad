#!/usr/bin/env python3
"""Compute the next semver version from current tag + bump level.

Bump-level resolution:
- Explicit: --bump {major,minor,patch} wins.
- Auto: derive from CHANGELOG.md [Unreleased] sections.
  - major: ### Removed non-empty OR any ### Changed entry starts with 'BREAKING:'
  - minor: ### Added non-empty AND no major trigger
  - patch: only ### Fixed / ### Security entries
  - minor: any ### Changed entry (see cycle-release.md — resolved, not guessed)
  - undeterminable (an [Unreleased] with no entries at all): prints 'AMBIGUOUS', exits 3.

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

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "semver.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Below the bootstrap: `squad` is importable only after sys.path is extended.
from squad.semver import RC, SEMVER_RE, Version, parse  # noqa: E402 — post-bootstrap import

# `RC` and `SEMVER_RE` are re-exported rather than redefined. This script used to own
# both, and owning them is what let the three readers of a version in this slice drift
# apart — see `tests/test_one_reading_of_a_version.py` for what the drift cost.


def parse_semver(tag: str) -> Version:
    """(major, minor, patch, rc) — `rc` is None for a final version.

    Returns a `Version`, which IS that 4-tuple, so every existing unpacking still works
    and callers gain `.core` and an ordering that puts a final above its own rcs.
    """
    m = parse(tag)
    if m is None:
        print(f"invalid semver tag: {tag}", file=sys.stderr)
        sys.exit(2)
    return m


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


#: Which clause of § Bump-level derivation decided, so a caller can say WHY without
#: re-deriving it. Split out when the `changed` clause stopped pausing (2026-09-08):
#: a level that resolves a genuinely undecidable question must be able to name the rule
#: that resolved it, or it is indistinguishable from a guess to everyone downstream.
_RULE_TO_LEVEL = {
    "removed": "major",
    "breaking": "major",
    "added": "minor",
    "changed": "minor",
    "fixed": "patch",
}


def deciding_rule(unreleased: dict[str, list[str]]) -> str | None:
    """Name the clause that decides this body's level, or None if none does.

    Order is the contract, not an implementation detail — each clause is reached only
    when every clause above it declined. `changed` sits ABOVE `fixed` deliberately:
    control used to fall through to `patch` without `changed` ever being consulted, and
    the real 0.72.0 release shipped as a patch because of it.
    """
    if not unreleased:
        return None

    if unreleased.get("Removed"):
        return "removed"
    if any(_is_breaking(c) for c in unreleased.get("Changed", [])):
        return "breaking"
    if unreleased.get("Added"):
        # Decided BEFORE `changed` on purpose. Under 0.x a breaking change is a minor bump,
        # so when `Added` is present the answer is minor whether or not the `Changed` entry
        # breaks anyone — the undecidable fact stops mattering.
        return "added"
    if unreleased.get("Changed"):
        # B-094 — undecidable from the section, and resolved to `minor` rather than asked.
        #
        # A non-breaking `Changed` is a MINOR under 0.x if a caller depended on the old
        # behaviour and a PATCH if not, and the section text does not carry that fact. It
        # never will: a CHANGELOG records what changed, not who depended on it.
        #
        # Until 2026-09-08 this returned None and paused the chain for a person. Nobody is
        # coming — `rules/autonomy-envelope.md § The autonomous span` places RELEASE inside
        # the system's own authority — so the pause was a stopped release wearing the
        # costume of caution.
        #
        # `minor` is not a coin toss between two equal errors. `patch` on a real break
        # delivers it SILENTLY to everyone on a caret range, the single failure semver
        # exists to prevent; `minor` on a compatible change leaves a version number larger
        # than it needed to be, which a caret range does not even pick up. One error reaches
        # a consumer and the other does not, so the rule decides toward the recoverable
        # side. `rules/cycle-release.md § Why a `Changed`-only release resolves to `minor``
        # carries the argument and the stated cost.
        return "changed"
    if unreleased.get("Fixed") or unreleased.get("Security"):
        return "fixed"
    return None


def derive_bump(unreleased: dict[str, list[str]]) -> str | None:
    """The level the [Unreleased] sections imply, or None when there are no entries."""
    rule = deciding_rule(unreleased)
    return _RULE_TO_LEVEL[rule] if rule else None


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


def _bump_core(core: tuple[int, int, int], level: str) -> str:
    major, minor, patch = core
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    print(f"invalid bump level: {level}", file=sys.stderr)
    sys.exit(2)


def bump_version(current: tuple[int, int, int, int | None], level: str, mode: str = "final") -> str:
    """Next version, in one of two modes.

    THE ASYMMETRY IS THE POINT
    --------------------------
    `pre` bumps the CORE only once — on the first rc of a version — and after that
    only advances the counter. `final` does NOT bump at all when an rc is standing:
    it promotes `0.3.0-rc.5` to `0.3.0`, because the rc series already reserved that
    number and bumping again would publish a version nobody's pre-releases pointed at.

        0.2.0        --pre-->   0.3.0-rc.1     (core bumped once, by `level`)
        0.3.0-rc.1   --pre-->   0.3.0-rc.2     (counter only)
        0.3.0-rc.2   --final->  0.3.0          (promotion, no bump)
        0.2.0        --final->  0.3.0          (no rc standing: ordinary bump)
    """
    core = current[:3]
    # A 3-tuple is a version with no rc. Accepted rather than rejected so that
    # callers predating the rc series keep working — `(0, 73, 0)` means exactly what
    # `(0, 73, 0, None)` means, and rejecting it would be a breaking change for a
    # distinction it does not make.
    rc = current[3] if len(current) > 3 else None

    if mode == "pre":
        if rc is not None:
            major, minor, patch = core
            return f"{major}.{minor}.{patch}-{RC}.{rc + 1}"
        return f"{_bump_core(core, level)}-{RC}.1"

    if mode == "final":
        if rc is not None:
            major, minor, patch = core
            return f"{major}.{minor}.{patch}"
        return _bump_core(core, level)

    print(f"invalid mode: {mode} (expected 'pre' or 'final')", file=sys.stderr)
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
    parser.add_argument(
        "--mode",
        default="pre",
        choices=("pre", "final"),
        help="'pre' cuts the next -rc.N (the default: most cuts are pre-releases). "
             "'final' promotes a standing rc, or bumps when none is standing.",
    )
    args = parser.parse_args()

    current = parse_semver(args.current)

    # A standing rc already fixed the core version, so no level is needed in either
    # mode: `pre` only advances the counter and `final` only drops the suffix. Asking
    # the CHANGELOG for a level here would surface AMBIGUOUS on a `Changed`-only body
    # and pause a chain over a number that cannot change the answer.
    if current[3] is not None:
        print(bump_version(current, "patch", args.mode))
        return 0

    if args.bump == "auto":
        if not args.changelog.exists():
            print(f"changelog not found for auto-bump: {args.changelog}", file=sys.stderr)
            return 2
        unreleased = extract_unreleased_subsections(args.changelog)
        rule = deciding_rule(unreleased)
        derived = derive_bump(unreleased)

        if rule == "changed":
            # The one level this script RESOLVES rather than reads. It travels with its
            # reason on stderr, where stdout stays exactly the version string every caller
            # parses. A resolved question that leaves no trace of having been resolved is
            # how a rule decays back into a guess nobody can audit.
            print(
                "bump: minor — derived from `### Changed` with no `Added`, no `Removed` "
                "and no `BREAKING:` entry.\n"
                "Under 0.x this body cannot distinguish a break from a compatible change, "
                "so it resolves toward the recoverable error: `patch` would ship a break "
                "silently to every caret range.\n"
                "See rules/cycle-release.md \u00a7 Why a `Changed`-only release resolves "
                "to `minor`. Pass --bump patch to override.",
                file=sys.stderr,
            )
        if derived is not None:
            # B-100 — the DERIVED class is placed under 0.x semantics here, where we know it came
            # from an inference rather than from a person.
            derived = level_under_zerover(derived, current)
        if derived is None:
            # The `Changed`-only body stopped arriving here on 2026-09-08 — it now resolves
            # to `minor` above. What still reaches this branch is an [Unreleased] with NO
            # entries in any section, and that is not an undecidable level: it is a release
            # with nothing in it.
            #
            # It stays a refusal rather than becoming a default, and it is the one exit-3 the
            # autonomous span tolerates, because no choice of level makes an empty release
            # correct. `changelog_section_nonempty.py` is the gate that normally catches this
            # first; this is the same fact reaching the version computation.
            #
            # stdout keeps EXACTLY `AMBIGUOUS` because `skills/release/SKILL.md` parses it and
            # a caller may capture it into a version variable.
            print("AMBIGUOUS")
            print(
                "\n"
                "The [Unreleased] section carries no entries at all — there is nothing to\n"
                "release, which is a different problem from an underivable level.\n"
                "\n"
                "  Write what this release contains under Added / Changed / Fixed /\n"
                "  Removed / Security, then re-run. rules/cycle-release.md\n"
                "  \u00a7 Bump-level derivation lists what each section derives.",
                file=sys.stderr,
            )
            return 3
        bump = derived
    else:
        bump = args.bump

    next_version = bump_version(current, bump, args.mode)
    print(next_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())

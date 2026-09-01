"""B-044 — a breaking change written in house style must derive a major bump.

Measured with the real script on two CHANGELOGs differing only in bold:

    - BREAKING: foo now takes two args.        ->  1.0.0
    - **BREAKING: foo now takes two args.**    ->  0.61.0

The parser strips the list marker and nothing else, so the entry arrives as `**BREAKING: …` and
`startswith("BREAKING:")` is false. There is no pause: `cycle-release.md` says the chain pauses when
the rule cannot pick deterministically, and here it picks confidently and wrongly — so a genuinely
breaking change ships as a minor and every consumer's `^` range absorbs it silently.

House style is the spelling that fails: 36 entries in this CHANGELOG match `^- \\*\\*` against 18
that do not.

These assert LEVELS, not versions, so they keep meaning what they mean as the current tag moves.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from compute_next_version import (
    bump_version,
    derive_bump,
    level_under_zerover,
    parse_semver,
)

SCRIPT = Path(__file__).parent.parent / "scripts" / "compute_next_version.py"


def test_a_bare_breaking_marker_still_derives_major() -> None:
    # The control. A fix that broke the working spelling while fixing the bold one would pass every
    # other test in this file.
    assert derive_bump({"Changed": ["BREAKING: foo now takes two args."]}) == "major"


def test_a_bold_breaking_marker_still_derives_major() -> None:
    # The defect: identical text, one pair of asterisks, a different release.
    assert derive_bump({"Changed": ["**BREAKING: foo now takes two args.**"]}) == "major"


def test_every_emphasis_spelling_derives_major() -> None:
    # D1 chose to NORMALISE rather than enumerate, because the defect being fixed IS a spelling
    # nobody enumerated. These are the shapes that convention allows; the point is that the code
    # does not need to know them individually.
    for entry in (
        "*BREAKING: foo*",
        "__BREAKING: foo__",
        "_BREAKING: foo_",
        "`BREAKING:` foo",
        "**breaking: foo**",
    ):
        assert derive_bump({"Changed": [entry]}) == "major", entry


def test_the_marker_must_open_the_entry_not_merely_appear_in_it() -> None:
    # The anchor is what separates a MARKED entry from one that merely contains the marker's text.
    #
    # The first version of this test used "…avoids a breaking change." — no colon, lowercase — and
    # was therefore blind to the very mutant it was written for: dropping the anchor and searching
    # anywhere in the line passed all four tests, because `find("BREAKING:")` misses that string
    # too. Caught by mutation, not by review, which is the whole reason to mutate a fix that passes
    # its own tests.
    #
    # These contain the marker verbatim and must still NOT derive major.
    for entry in (
        "Renamed the flag; see BREAKING: notes in the migration guide.",
        "Documented what BREAKING: means for this project.",
    ):
        assert derive_bump({"Changed": [entry]}) != "major", entry


def test_the_conventional_commits_spelling_also_derives_major() -> None:
    # F-6 — the first fix hardened the DECORATION and left the WORDING. `BREAKING CHANGE:` is the
    # Conventional Commits marker and the one most people reach for; it derived `minor`, silently,
    # with an `Added` entry alongside it to make the wrong answer look reasonable.
    for entry in (
        "**BREAKING CHANGE: foo now takes two args.**",
        "BREAKING CHANGE: foo now takes two args.",
        "breaking change: foo now takes two args.",
    ):
        assert derive_bump({"Changed": [entry], "Added": ["something"]}) == "major", entry


def test_the_published_rule_table_is_pinned_end_to_end() -> None:
    # F-4/F-5 — mutation found `Removed -> major` and `Added -> minor` both mutate away GREEN: two
    # thirds of the rule this script publishes were unpinned by its only test file. Every branch of
    # `cycle-release.md` § Bump-level derivation now has a case.
    assert derive_bump({"Removed": ["a public API"]}) == "major"
    assert derive_bump({"Added": ["a feature"]}) == "minor"
    assert derive_bump({"Fixed": ["a bug"]}) == "patch"
    assert derive_bump({"Security": ["a CVE"]}) == "patch"
    # Precedence: a removal outranks an addition, and both outrank a fix.
    assert derive_bump({"Removed": ["x"], "Added": ["y"], "Fixed": ["z"]}) == "major"
    assert derive_bump({"Added": ["y"], "Fixed": ["z"]}) == "minor"
    # Nothing at all is not a bump — it is the AMBIGUOUS path the caller must handle (B-047).
    assert derive_bump({}) is None


# B-047 — a `Changed`-only release derives AMBIGUOUS, and the pause is one word.
#
# Measured 2026-08-18 cutting B-021: `--current 0.61.0 --bump auto` -> `AMBIGUOUS`, on an
# [Unreleased] with one `### Changed` entry. The script is behaving CORRECTLY — `cycle-release.md`
# says the chain pauses when the rule cannot pick deterministically, and this is that case.
#
# The pause STAYS. Under 0.x a breaking change is a MINOR bump and a compatible one is a PATCH, so
# `Changed` maps to either depending on a fact the section does not contain: did behaviour a caller
# depends on change? Guessing minor turns every reworded entry into a compatibility signal; guessing
# patch understates a real break, which is the failure semver exists to prevent. And guessing is
# what B-043, B-044 and B-046 — the three sibling findings of the same session — are all about.
#
# What changes is that the pause says what it is asking.

def _changelog(tmp_path: Path, section: str, entry: str = "- something") -> Path:
    p = tmp_path / "CHANGELOG.md"
    p.write_text(
        f"# Changelog\n\n## [Unreleased]\n\n### {section}\n\n{entry}\n\n"
        "## [0.61.0] - 2026-08-01\n\n- older\n",
        encoding="utf-8",
    )
    return p


def _run(
    changelog: Path, current: str = "0.61.0", mode: str = "final"
) -> subprocess.CompletedProcess[str]:
    """`mode="final"` by default HERE, deliberately, though the CLI defaults to `pre`.

    These tests are about the LEVEL the CHANGELOG derives — minor / patch / the
    breaking class under 0.x — and an rc suffix on every expectation would obscure
    exactly the digit under test. The CLI's own default is pinned separately by
    `test_the_cli_defaults_to_a_pre_release`, so nothing here hides it.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--changelog", str(changelog),
         "--current", current, "--bump", "auto", "--mode", mode],
        capture_output=True, text=True, check=False,
    )


def test_added_only_derives_minor(tmp_path: Path) -> None:
    result = _run(_changelog(tmp_path, "Added"))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.62.0"


def test_removed_only_derives_the_breaking_class_placed_under_0x(tmp_path: Path) -> None:
    """B-100 — this test asserted `1.0.0` and was PINNING THE DEFECT AS THE CONTRACT.

    Renamed rather than edited in place, because the old name said what the old behaviour did
    ("derives major") and reading it would go on suggesting 1.0.0 is the right answer here.

    `### Removed` still derives the breaking CLASS — that was never wrong. What changed is where
    the class lands: under 0.x it sits at the MINOR position (`rules/cycle-release.md`), and
    `rules/public-copy.md` § 3 forbids the 1.0 claim until sustained production evidence exists.
    The fixture's current version is 0.61.x, so the answer is 0.62.0.

    Form 4 of the false-oracle taxonomy — a test that encodes the bug as the specification — and
    the second one found in this file tonight. The first was B-094's `Changed` branch.
    """
    result = _run(_changelog(tmp_path, "Removed"))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.62.0"


def test_fixed_only_derives_patch(tmp_path: Path) -> None:
    result = _run(_changelog(tmp_path, "Fixed"))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.61.1"


def test_changed_only_pauses_and_says_why(tmp_path: Path) -> None:
    result = _run(_changelog(tmp_path, "Changed"))

    # The parse contract: `SKILL.md` reads stdout, so the token and the exit code must not move.
    assert result.returncode == 3
    assert result.stdout.strip() == "AMBIGUOUS"
    assert "\n" not in result.stdout.strip(), "no prose may leak into stdout"

    # The question the human actually has to answer, and what each answer means under 0.x.
    assert "minor" in result.stderr
    assert "patch" in result.stderr
    assert "behaviour" in result.stderr.lower() or "behavior" in result.stderr.lower()

def test_non_breaking_changed_is_undecidable_even_beside_fixed_or_security() -> None:
    """B-094 — the shape that shipped 0.72.0 as a patch until a human overrode it.

    `Changed` without an explicit BREAKING marker cannot be derived under 0.x: it is a MINOR if a
    caller depended on the old behaviour and a PATCH if not, and the section text does not carry
    that fact. `cycle-release.md § Bump-level derivation` argues exactly this, and the pause is how
    the question gets asked.

    The defect was that the pause only fired when `Changed` was ALONE. Beside `Fixed` or
    `Security` — the common shape — control reached `if fixed or security: return "patch"` without
    `changed` ever being consulted, and the question was never asked.

    Measured on the real 0.72.0 CHANGELOG: `--current 0.71.0 --bump auto` returned `0.71.1`, exit 0,
    no pause, for a release whose own `### Changed` entry says two published functions now reject an
    input class they previously accepted.
    """
    real_072 = {
        "Security": ["setTerminalTitle and osc8Link refuse control bytes."],
        "Changed": ["setTerminalTitle and osc8Link reject inputs they previously accepted."],
        "Fixed": ["The exported VERSION constant reports 0.72.0."],
    }
    assert derive_bump(real_072) is None

    # Each pairing on its own, so a future reader can see it is the PRESENCE of `Changed` that
    # decides, not some interaction between the other two sections.
    assert derive_bump({"Changed": ["reworded"], "Fixed": ["a bug"]}) is None
    assert derive_bump({"Changed": ["reworded"], "Security": ["a CVE"]}) is None


def test_added_beside_changed_is_decidable_and_must_not_pause() -> None:
    """The other half, and the reason this is not simply "pause whenever Changed is present".

    Under 0.x a breaking change is a MINOR bump. So when `Added` is present the answer is minor
    whether or not the `Changed` entry breaks anyone — the undecidable fact stops mattering, and
    pausing would ask a question whose two answers agree.

    A pause nobody can act on differently is noise, and noise is how a pause stops being read.
    """
    assert derive_bump({"Changed": ["reworded"], "Added": ["a feature"]}) == "minor"
    assert (
        derive_bump({"Changed": ["reworded"], "Added": ["a feature"], "Fixed": ["a bug"]})
        == "minor"
    )


def test_a_derived_breaking_change_under_0x_lands_on_minor_not_1_0_0() -> None:
    """B-100 — the other branch of the defect B-094 fixed, found cutting the very next release.

    `rules/cycle-release.md` states the policy in as many words: *"This package is 0.x ... so 0.x
    semantics apply ... Under 0.x a breaking change is a MINOR bump and a compatible one is a
    PATCH."*

    `derive_bump` correctly answers "major" for a `### Removed` section — that is the semver
    CLASS, and it was never wrong. What was wrong is that the class went straight into
    `bump_version`, which produced 1.0.0. Under 0.x that is wrong twice: the wrong number, and
    `rules/public-copy.md` § 3 forbids the 1.0 claim until sustained production evidence exists.
    A release script able to cut 1.0.0 on its own can make a marketing claim nobody approved.

    Measured 2026-08-20 on the real B-076 CHANGELOG: `--current 0.73.0 --bump auto` -> `1.0.0`.
    """
    assert derive_bump({"Removed": ["a published field"]}) == "major"

    # The mapping lives where PROVENANCE is known — a derived level, not an asserted one.
    assert level_under_zerover("major", (0, 73, 0)) == "minor"
    assert bump_version((0, 73, 0), level_under_zerover("major", (0, 73, 0))) == "0.74.0"
    assert bump_version((0, 1, 5), level_under_zerover("major", (0, 1, 5))) == "0.2.0"

    # minor and patch are untouched, so the three levels do not collapse into each other.
    assert level_under_zerover("minor", (0, 73, 0)) == "minor"
    assert level_under_zerover("patch", (0, 73, 0)) == "patch"


def test_an_EXPLICIT_major_is_honoured_so_1_0_0_stays_reachable() -> None:
    """The 0.x clause must not become a permanent cap on the project's own version.

    `cycle-release.md` says to revisit at 1.0.0, which is only possible if a HUMAN can still ask
    for it. That is the whole reason the mapping is applied to the derived path and not inside
    `bump_version`: `--bump major` is an assertion by a person, `--bump auto` is an inference by a
    script, and only the inference needs the guard rail.
    """
    assert bump_version((0, 73, 0), "major") == "1.0.0"


def test_at_1_x_and_above_the_zerover_clause_does_nothing() -> None:
    """Scoped to 0.x, not written as "never bump major"."""
    assert level_under_zerover("major", (1, 4, 2)) == "major"
    assert bump_version((1, 4, 2), "major") == "2.0.0"
    assert bump_version((2, 0, 0), "major") == "3.0.0"


# ── the rc series ─────────────────────────────────────────────────────────────
#
# `/release` cuts a pre-release per batch and a final release only when a milestone
# closes (`rules/cycle-release.md § Two cuts`). The asymmetry below is the contract:
# the core version is bumped ONCE, by the first rc, and the final promotes rather
# than bumping again — otherwise it would publish a number none of the rcs pointed at.


def test_the_cli_defaults_to_a_pre_release(tmp_path: Path) -> None:
    """Most cuts are pre-releases, so that is the default — and a default is behaviour."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--changelog", str(_changelog(tmp_path, "Added")),
         "--current", "0.61.0", "--bump", "auto"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.62.0-rc.1"


def test_the_first_rc_bumps_the_core_and_the_next_only_counts() -> None:
    assert bump_version((0, 2, 0, None), "minor", "pre") == "0.3.0-rc.1"
    assert bump_version((0, 3, 0, 1), "minor", "pre") == "0.3.0-rc.2"
    assert bump_version((0, 3, 0, 9), "minor", "pre") == "0.3.0-rc.10"


def test_the_final_promotes_a_standing_rc_without_bumping_again() -> None:
    """The rc series already reserved 0.3.0. Bumping here would publish 0.4.0 —
    a version none of the pre-releases pointed at."""
    assert bump_version((0, 3, 0, 5), "minor", "final") == "0.3.0"


def test_a_final_with_no_rc_standing_bumps_normally() -> None:
    """A milestone closing on work that never cut an rc still gets a release."""
    assert bump_version((0, 2, 0, None), "minor", "final") == "0.3.0"


def test_a_standing_rc_needs_no_level_and_never_pauses(tmp_path: Path) -> None:
    """A `Changed`-only body returns AMBIGUOUS and pauses the chain — but with an rc
    standing the core is already fixed, so no level can change the answer and asking
    would pause over a number that does not matter."""
    changed_only = _changelog(tmp_path, "Changed")
    for mode in ("pre", "final"):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--changelog", str(changed_only),
             "--current", "0.3.0-rc.4", "--bump", "auto", "--mode", mode],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, f"{mode}: {result.stderr}"
        assert "AMBIGUOUS" not in result.stdout
    

def test_the_rc_counter_survives_parsing() -> None:
    """The pattern used to end `(?:[-+].*)?` — matching a pre-release and discarding
    it — so every rc parsed as the final release of its version."""
    assert parse_semver("v0.3.0-rc.7") == (0, 3, 0, 7)
    assert parse_semver("0.3.0") == (0, 3, 0, None)
    assert parse_semver("v1.2.3+build.9") == (1, 2, 3, None)

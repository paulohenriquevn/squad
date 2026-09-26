r"""`squad.semver` orders versions the way a release series depends on.

The ordering is the part that is easy to get subtly wrong and expensive to notice: a
comparison that ranks `0.3.0-rc.9` above `0.3.0` cuts the next release BACKWARDS, and a
comparison done on strings ranks `0.9.0` above `0.10.0` the first time a minor reaches
double digits. Both produce a version number that is published and immutable.
"""
from __future__ import annotations

import pytest

from squad.semver import Version, highest, parse


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.2.3", Version(1, 2, 3)),
        ("v1.2.3", Version(1, 2, 3)),
        ("0.3.0-rc.2", Version(0, 3, 0, 2)),
        ("v0.3.0-rc.10", Version(0, 3, 0, 10)),
        ("1.0.0-rc.1+build.5", Version(1, 0, 0, 1)),
        ("  1.2.3  ", Version(1, 2, 3)),
    ],
)
def test_the_shapes_this_kit_cuts_are_read(text: str, expected: Version) -> None:
    assert parse(text) == expected


@pytest.mark.parametrize("text", ["0.3.0-beta.1", "0.3.0-alpha", "1.2", "x", "", "1.2.3.4"])
def test_what_cannot_be_ordered_is_refused_rather_than_ranked(text: str) -> None:
    """`-beta.1` is valid semver. It is not a version this kit cuts, and ranking it
    against an `-rc.N` would be a guess wearing a number."""
    assert parse(text) is None


def test_a_final_outranks_its_own_pre_releases() -> None:
    """Semver orders a pre-release BELOW its own final; a sentinel rc number cannot
    express that, because any number chosen is either above some real rc or below it."""
    assert highest([parse("0.3.0-rc.9"), parse("0.3.0")]) == parse("0.3.0")


def test_a_later_rc_outranks_an_earlier_one() -> None:
    assert highest([parse("0.3.0-rc.2"), parse("0.3.0-rc.10")]) == parse("0.3.0-rc.10")


def test_versions_compare_numerically_not_lexically() -> None:
    """As strings `"0.9.0" > "0.10.0"`, which ships a release below the last one."""
    assert highest([parse("0.9.0"), parse("0.10.0")]) == parse("0.10.0")


def test_a_pre_release_outranks_the_final_below_it() -> None:
    assert highest([parse("0.2.0"), parse("0.3.0-rc.1")]) == parse("0.3.0-rc.1")


def test_highest_of_nothing_is_nothing() -> None:
    """Not `0.0.0` — a guessed base below everything published is the defect
    `detect_current_version.py` exists to prevent."""
    assert highest([]) is None


def test_the_string_form_round_trips() -> None:
    for text in ("1.2.3", "0.3.0-rc.2"):
        assert str(parse(text)) == text


def test_a_build_suffix_carries_no_ordering_weight() -> None:
    """Semver says build metadata is ignored when comparing, and dropping it on parse
    is how that is enforced here rather than remembered at each comparison."""
    assert parse("1.0.0+a") == parse("1.0.0+b") == parse("1.0.0")

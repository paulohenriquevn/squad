r"""`squad.allowlist` holds the exemption policy three `rules/*.txt` declare.

The window, what expiry means, and that a malformed line is an error rather than a
skipped one. The FIELDS are each consumer's own and are not tested here.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from squad.allowlist import MAX_SUNSET_DAYS, MalformedEntry, active, parse

SOON = (date.today() + timedelta(days=30)).isoformat()
PAST = (date.today() - timedelta(days=1)).isoformat()
TODAY = date.today().isoformat()
FAR = (date.today() + timedelta(days=MAX_SUNSET_DAYS + 1)).isoformat()


def _file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "allowlist.txt"
    path.write_text(body, encoding="utf-8")
    return path


def _parse(tmp_path: Path, body: str, fields: int = 3, sunset: int = 1):
    return parse(_file(tmp_path, body), field_count=fields, sunset_index=sunset)


def test_comments_and_blank_lines_are_skipped(tmp_path: Path) -> None:
    entries = _parse(tmp_path, f"# a comment\n\nslug|{SOON}|why\n")

    assert len(entries) == 1
    assert entries[0].fields == ("slug", SOON, "why")


def test_a_missing_file_is_an_empty_allowlist(tmp_path: Path) -> None:
    """Exempting nothing is the correct default; absence must not block a project."""
    assert parse(tmp_path / "nope.txt", field_count=3, sunset_index=1) == []


def test_an_expired_entry_parses_and_is_reported(tmp_path: Path) -> None:
    """Refusing to PARSE an expired entry would hide the expiry instead of surfacing
    it. The contract is that it is ignored at scoring time and reported."""
    entries = _parse(tmp_path, f"slug|{PAST}|ran out\n")

    assert len(entries) == 1 and entries[0].expired
    assert active(entries) == []


def test_a_sunset_of_today_still_exempts(tmp_path: Path) -> None:
    """The boundary belongs to the entry: it expires the day AFTER its sunset."""
    entries = _parse(tmp_path, f"slug|{TODAY}|last day\n")

    assert active(entries) == entries


@pytest.mark.parametrize(
    "body",
    [
        "slug|only-two\n",
        "slug|2026-13-45|bad month and day\n",
        "slug|not-a-date|nope\n",
        "slug|26-01-01|two-digit year\n",
    ],
)
def test_a_malformed_entry_is_refused_not_skipped(tmp_path: Path, body: str) -> None:
    """A dropped line is an exemption somebody believes they have and does not."""
    with pytest.raises(MalformedEntry):
        _parse(tmp_path, body)


def test_a_window_beyond_the_policy_is_refused(tmp_path: Path) -> None:
    """A longer one is a permanent exemption with a date on it."""
    with pytest.raises(MalformedEntry, match=str(MAX_SUNSET_DAYS)):
        _parse(tmp_path, f"slug|{FAR}|forever\n")


def test_the_refusal_names_the_file_and_the_line(tmp_path: Path) -> None:
    """A reader must be able to go straight to the entry."""
    with pytest.raises(MalformedEntry) as refused:
        _parse(tmp_path, f"# c\nslug|{SOON}|ok\nbroken\n")

    assert "line 3" in str(refused.value)


def test_a_consumer_shape_with_more_fields_works(tmp_path: Path) -> None:
    """The CVE allowlist is six fields with the sunset fifth."""
    entries = _parse(
        tmp_path, f"npm|lodash|>=4.0.0|GHSA-xxxx-xxxx-xxxx|{SOON}|test-only dep\n",
        fields=6, sunset=4,
    )

    assert entries[0].fields[3] == "GHSA-xxxx-xxxx-xxxx"
    assert not entries[0].expired

"""T2.2 — plan-confidence-thresholds.txt allowlist tests."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path


def _read_thresholds(rules_dir: Path) -> str:
    return (rules_dir / "plan-confidence-thresholds.txt").read_text(encoding="utf-8")


def _data_lines(content: str) -> list[str]:
    return [
        line for line in content.splitlines()
        if line and not line.startswith("#") and "|" in line
    ]


def test_thresholds_file_exists(rules_dir: Path) -> None:
    assert (rules_dir / "plan-confidence-thresholds.txt").exists()


def test_thresholds_parseable_4_rows(rules_dir: Path) -> None:
    content = _read_thresholds(rules_dir)
    rows = _data_lines(content)
    assert len(rows) == 4, f"expected 4 data rows, got {len(rows)}"


def test_thresholds_have_four_columns(rules_dir: Path) -> None:
    content = _read_thresholds(rules_dir)
    for row in _data_lines(content):
        parts = row.split("|")
        assert len(parts) == 4, f"row {row!r} has {len(parts)} cols, expected 4"


def test_thresholds_in_descending_order(rules_dir: Path) -> None:
    content = _read_thresholds(rules_dir)
    scores = [int(row.split("|")[1]) for row in _data_lines(content)]
    assert scores == sorted(scores, reverse=True), f"scores {scores} not descending"


def test_thresholds_band_names_canonical(rules_dir: Path) -> None:
    content = _read_thresholds(rules_dir)
    bands = [row.split("|")[0] for row in _data_lines(content)]
    expected = {"SHIPPABLE", "SHIPPABLE_WITH_CAVEATS", "NON_SHIPPABLE", "INVALID"}
    assert set(bands) == expected


def test_every_sunset_is_a_date_the_reader_can_act_on(rules_dir: Path) -> None:
    """A sunset must parse and must be a real date. NOT "is it still in the future".

    That was the assertion here, against `date.today()`, and it made the suite go red
    on a calendar day with no code change — the test failing said nothing about the
    code and everything about when it ran. Whether a threshold is overdue for review is
    a REPORT the rule file's reader produces, not a test outcome; a test that fails for
    the passage of time gets its date bumped, which is the opposite of a review.
    """
    content = _read_thresholds(rules_dir)

    for row in _data_lines(content):
        sunset_str = row.split("|")[2].strip()
        parsed = date.fromisoformat(sunset_str)
        assert parsed.year >= 2025, f"{sunset_str} is not a date anyone set on purpose"


def test_an_overdue_sunset_is_reportable(rules_dir: Path) -> None:
    """The real question, asked in the way that does not rot: given a date, can a
    reader tell whether it has passed? Fixed inputs, so the answer never depends on
    when the suite runs."""
    content = _read_thresholds(rules_dir)
    rows = _data_lines(content)
    sunsets = [date.fromisoformat(row.split("|")[2].strip()) for row in rows]

    assert [s for s in sunsets if s < date(2020, 1, 1)] == [], (
        "a sunset before the project existed is a placeholder, not a review date")


def test_thresholds_sunset_iso_format(rules_dir: Path) -> None:
    content = _read_thresholds(rules_dir)
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for row in _data_lines(content):
        sunset = row.split("|")[2]
        assert iso_pattern.match(sunset), f"sunset {sunset!r} not ISO YYYY-MM-DD"


def test_thresholds_adr_ref_consistent(rules_dir: Path) -> None:
    content = _read_thresholds(rules_dir)
    refs = [row.split("|")[3] for row in _data_lines(content)]
    assert len(set(refs)) == 1, f"ADR refs inconsistent: {set(refs)}"


def test_thresholds_specific_values(rules_dir: Path) -> None:
    """Lock the band cutoffs as per ADR D5 / SOTA report."""
    content = _read_thresholds(rules_dir)
    band_to_min = {
        row.split("|")[0]: int(row.split("|")[1]) for row in _data_lines(content)
    }
    assert band_to_min == {
        "SHIPPABLE": 90,
        "SHIPPABLE_WITH_CAVEATS": 70,
        "NON_SHIPPABLE": 50,
        "INVALID": 0,
    }


# ── a sunset nobody detects is a deadline that silently became permanent ──────
#
# Two checkers declared "cap 89; sunset 2026-09-07 — after which promotes to hard
# cap 70 via ADR". The date passed, `run_structural` still applied 89, no ADR
# existed, and nothing noticed. The kit treats an expired sunset as load-bearing in
# a consumer's config; it had one of its own, unread, for ten days.


def test_no_source_promises_a_promotion_on_a_date() -> None:
    """A cap is the rule it currently is, or it is a promise nobody is keeping."""
    import re as _re

    root = Path(__file__).resolve().parents[3]
    offenders: list[str] = []
    promise = _re.compile(r"sunset\s+(\d{4}-\d{2}-\d{2})\s*[—;-]\s*(?:after which|then)",
                          _re.IGNORECASE)
    for path in sorted(root.glob("skills/*/scripts/*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # A QUOTED promise is a record of one that was removed — the correction
            # itself has to be able to name what it corrected.
            if '"' in line or "`" in line:
                continue
            if promise.search(line):
                offenders.append(f"{path.relative_to(root)}:{number}: {line.strip()}")

    assert offenders == [], (
        "these promise a threshold promotion on a date. A date arriving is not a "
        "decision, and nothing here detects the expiry:\n" + "\n".join(offenders))

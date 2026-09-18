"""Two checkers accepted a substring where they meant a token, and both fail OPEN.

* `_has_tdd_block` accepted a task when the uppercased body after `#### TDD` contained
  `RED:` or `RED ` as a raw substring. `REQUIRED `, `COVERED `, `TRIGGERED `, `ENTERED `
  and `ORDERED ` all contain `RED `. So a bug-fix task with an empty `#### TDD` heading
  followed by ordinary prose counted as having TDD, `coverage_ratio` reached 1.0, and
  `_detect_hard_caps` skipped the `bugfix_without_tdd` cap — a fix shipping with no
  regression test, scored as one that has one.
* `_section_exists` compared the citation's section token to each heading with `in`,
  over the whole heading. `architecture.md §1` therefore resolved against
  `## 21 — Retry policy`, `## Phase 1`, or any heading containing the character `1`.
  For a single-digit section it effectively could not fail, and the result feeds the
  `fabricated_citation` cap — one of the two that force INVALID.

Both directions matter: a checker that cannot fail is not a checker, and a checker that
fires on a legitimate plan gets switched off.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))

from check_evidence_citations import _section_exists  # noqa: E402 — post-bootstrap import
from check_tdd_in_bugfix import _has_tdd_block  # noqa: E402 — post-bootstrap import


@pytest.mark.parametrize("prose", [
    "The change is REQUIRED before the release.",
    "That path is already COVERED elsewhere.",
    "The handler is TRIGGERED by the queue.",
    "The row has ENTERED the registry.",
    "The list is ORDERED by severity.",
])
def test_a_word_ending_in_red_is_not_a_red_test(prose: str) -> None:
    body = f"### T1.1 — fix the thing\n\n#### TDD\n\n{prose}\n"

    assert not _has_tdd_block(body), f"{prose!r} counted as a RED test"


def test_a_real_red_line_still_counts() -> None:
    body = ("### T1.1 — fix the thing\n\n#### TDD\n\n"
            "RED: test_it_refuses_a_negative_balance — asserts the refusal.\n")

    assert _has_tdd_block(body)


def test_a_red_label_without_a_colon_still_counts() -> None:
    body = "### T1.1 — fix\n\n#### TDD\n\nRED  write the failing test first\n"

    assert _has_tdd_block(body)


def _doc(tmp_path: Path, headings: list[str]) -> Path:
    path = tmp_path / "architecture.md"
    path.write_text("\n\n".join(f"## {h}" for h in headings) + "\n", encoding="utf-8")
    return path


def test_a_section_number_does_not_match_a_longer_one(tmp_path: Path) -> None:
    doc = _doc(tmp_path, ["21 — Retry policy", "Phase 1 of the rollout"])

    assert not _section_exists(doc, "§1"), (
        "`§1` resolved against a heading that merely contains the character 1")


def test_the_section_it_names_resolves(tmp_path: Path) -> None:
    doc = _doc(tmp_path, ["1 — The first section", "2 — The second"])

    assert _section_exists(doc, "§1")
    assert _section_exists(doc, "1")


def test_a_named_section_resolves(tmp_path: Path) -> None:
    doc = _doc(tmp_path, ["Retry policy", "Backpressure"])

    assert _section_exists(doc, "Retry policy")
    assert not _section_exists(doc, "Timeout policy")

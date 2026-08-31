"""A verdict nothing can emit is a promise the contract cannot keep.

Written after a sweep found 48 declared verdicts and 6 reachable from nowhere — the
same defect that had just been fixed twice by hand (`NEEDS_SPLIT` in a verdict table
and no code path; `planned` in a contract and in zero items anywhere). Both were found
by a person noticing, and neither was findable by any check.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from check_orphan_verdicts import check_orphan_verdicts


def _repo(tmp_path: Path, rule_body: str, code: str = "", doc: str = "") -> Path:
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "cycle-thing.md").write_text(rule_body, encoding="utf-8")
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "runner.py").write_text(code or "# nothing\n", encoding="utf-8")
    skill = tmp_path / "skills" / "doer"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(doc or "# doer\n", encoding="utf-8")
    return tmp_path


_TABLE = """# Cycle: Thing

## Verdicts

| Verdict | Meaning | Next |
|---|---|---|
| `{verdict}` | something happened | stop |
"""


def test_a_verdict_no_one_emits_is_reported(tmp_path: Path) -> None:
    report = check_orphan_verdicts(_repo(tmp_path, _TABLE.format(verdict="GHOST_STATE")))
    assert [f.verdict for f in report.findings] == ["GHOST_STATE"]


def test_a_verdict_a_script_emits_is_clean(tmp_path: Path) -> None:
    report = check_orphan_verdicts(_repo(
        tmp_path, _TABLE.format(verdict="REAL_STATE"), code='print("REAL_STATE")\n'))
    assert report.findings == []
    assert report.by_code == 1


def test_a_verdict_only_a_skill_names_counts_as_agent_emitted(tmp_path: Path) -> None:
    """Judgement a person or agent supplies is not a defect — it is the design."""
    report = check_orphan_verdicts(_repo(
        tmp_path, _TABLE.format(verdict="JUDGED_STATE"), doc="Emit `JUDGED_STATE` when...\n"))
    assert report.findings == []
    assert report.by_agent == 1


def test_an_exemption_needs_a_reason(tmp_path: Path) -> None:
    body = _TABLE.format(verdict="OUTSIDE_STATE").replace(
        "| stop |", "| stop | _(emitted externally: another repository writes it)_ |")
    report = check_orphan_verdicts(_repo(tmp_path, body))
    assert report.findings == []
    assert report.exempt == 1


def test_an_exemption_without_a_reason_does_not_count(tmp_path: Path) -> None:
    """`_(emitted externally)_` with no reason leaves the reader unable to judge it."""
    body = _TABLE.format(verdict="VAGUE_STATE").replace("| stop |", "| stop | _(emitted externally)_ |")
    report = check_orphan_verdicts(_repo(tmp_path, body))
    assert [f.verdict for f in report.findings] == ["VAGUE_STATE"]


def test_a_rule_without_a_verdicts_section_is_skipped(tmp_path: Path) -> None:
    report = check_orphan_verdicts(_repo(tmp_path, "# Cycle: Thing\n\n## Chain\n\nnothing\n"))
    assert report.rules_swept == 0
    assert report.findings == []


def test_a_cross_reference_in_the_meaning_column_is_not_a_second_verdict(tmp_path: Path) -> None:
    """Only the first name on a row is the verdict; the rest point at other rows."""
    body = ("# Cycle: Thing\n\n## Verdicts\n\n| Verdict | Meaning |\n|---|---|\n"
            "| `FIRST_STATE` | unlike `SECOND_STATE`, this one stops |\n")
    report = check_orphan_verdicts(_repo(tmp_path, body, code='print("FIRST_STATE")\n'))
    assert report.total == 1
    assert report.findings == []


def test_the_header_row_is_not_counted(tmp_path: Path) -> None:
    report = check_orphan_verdicts(_repo(
        tmp_path, _TABLE.format(verdict="ONE_STATE"), code='print("ONE_STATE")\n'))
    assert report.total == 1


@pytest.mark.parametrize("noise", ["NNN", "JSON", "TODO"])
def test_words_that_look_like_verdicts_are_not(tmp_path: Path, noise: str) -> None:
    body = f"# Cycle: Thing\n\n## Verdicts\n\n| Verdict | Meaning |\n|---|---|\n| `{noise}` | a placeholder |\n"
    assert check_orphan_verdicts(_repo(tmp_path, body)).total == 0


# ── the kit itself ────────────────────────────────────────────────────────────


def test_this_repository_has_no_orphaned_verdict() -> None:
    """The guard, running where it matters. Exemptions are allowed; silence is not."""
    report = check_orphan_verdicts(Path(__file__).resolve().parent.parent)
    assert report.findings == [], [f"{f.rule}: {f.verdict}" for f in report.findings]


def test_a_subsection_does_not_truncate_the_verdicts_section(tmp_path: Path) -> None:
    """A coverage gate that loses coverage without saying so is the failure it exists
    to prevent, one level up.

    Measured on 2026-08-31: adding a `###` under `cycle-maintenance.md`'s verdict
    table dropped the swept count from 51 to 49 — no finding, no warning, nothing in
    the output to notice. Fixing the delimiter raised it to 54, so three verdicts had
    been outside the sweep before anyone touched the file.
    """
    rules = tmp_path / "rules"
    rules.mkdir(parents=True)
    (rules / "cycle-demo.md").write_text(
        "# Demo\n\n"
        "## Verdicts\n\n"
        "| `FIRST_ONE` | before the subsection |\n\n"
        "### A subsection under Verdicts\n\n"
        "| `SECOND_ONE` | after it, still about verdicts |\n\n"
        "## Something else\n\n"
        "| `NOT_A_VERDICT_HERE` | outside the section |\n",
        encoding="utf-8")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "emit.py").write_text(
        'print("FIRST_ONE"); print("SECOND_ONE")\n', encoding="utf-8")

    report = check_orphan_verdicts(tmp_path)
    assert report.total >= 2, "the subsection truncated the section again"
    assert not report.findings

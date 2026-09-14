"""Running a criterion instead of reading it.

`score_alignment` grades a criterion `executable` from a text match over the bullet: it
asks whether a command is NAMED, never whether it could run or whether its answer
distinguishes anything. A consumer measured the consequence — a brief scored 14/14
executable where two criteria could not pass at all, and roughly thirty criteria across
eighteen briefs returned the same answer before and after the work.

None of that is visible to a reader of the text. All of it is visible in one run.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_criteria_discriminate as cd  # noqa: E402


def _brief(tmp_path: Path, *bullets: str) -> Path:
    path = tmp_path / "b-001-alignment.md"
    path.write_text("# Brief\n\n## Acceptance Criteria\n\n"
                    + "".join(f"- {b}\n" for b in bullets), encoding="utf-8")
    return path


# ── the class this exists to catch ──────────────────────────────────────────

def test_a_criterion_that_already_passes_is_refused(tmp_path):
    """It cannot tell a finished item from an unstarted one, whatever it says."""
    brief = _brief(tmp_path, "AC-001: `echo 1` prints 1")
    rep = cd.run(brief, tmp_path)
    assert len(rep.already_passing) == 1


def test_a_criterion_that_fails_today_has_something_to_prove(tmp_path):
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1")
    rep = cd.run(brief, tmp_path)
    assert rep.already_passing == []


def test_an_exit_zero_criterion_that_already_exits_zero_is_refused(tmp_path):
    """`go test -run <pattern-that-matches-nothing>` exits 0 with `[no tests to run]`.

    Measured on a consumer: eight criteria in one brief were satisfied by writing no
    test at all.
    """
    brief = _brief(tmp_path, "AC-001: `true` exits 0")
    assert cd.run(brief, tmp_path).already_passing


# ── what it must not claim ──────────────────────────────────────────────────

def test_a_criterion_whose_expectation_is_unstated_is_undecidable_not_sound(tmp_path):
    """Reporting a criterion as sound because the comparison was too hard is the
    failure this file exists to end, one level up."""
    brief = _brief(tmp_path, "AC-001: `echo hello` behaves correctly")
    rep = cd.run(brief, tmp_path)
    assert rep.already_passing == []
    assert len(rep.undecidable) == 1


def test_a_placeholder_criterion_is_not_run_and_not_counted_as_sound(tmp_path):
    brief = _brief(tmp_path, "AC-001: `go test ./<module>/...` exits 0")
    rep = cd.run(brief, tmp_path)
    assert rep.unrunnable and not rep.already_passing
    assert "placeholder" in rep.results[0].note


def test_a_bullet_naming_no_command_is_reported_as_unrunnable(tmp_path):
    brief = _brief(tmp_path, "AC-001: the system feels faster")
    rep = cd.run(brief, tmp_path)
    assert rep.unrunnable
    assert "no runnable command" in rep.results[0].note


def test_a_hanging_criterion_is_stopped_and_named(tmp_path):
    brief = _brief(tmp_path, "AC-001: `sleep 30` exits 0")
    rep = cd.run(brief, tmp_path, timeout=1.0)
    assert rep.unrunnable
    # The note lives on the CLAUSE since decomposition: a conjunction can have one
    # clause that hangs and another that answered, and a single note could not say so.
    assert "did not finish" in rep.results[0].clauses[0].note


# ── the honest limits, stated in the output ─────────────────────────────────

def test_the_report_says_it_checked_one_state_of_three(tmp_path):
    """A green run means "no criterion is vacuous in the cheapest way". It does not
    mean the criteria are good, and the page must not let a reader think it does."""
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1")
    text = cd.render(cd.run(brief, tmp_path), brief)
    assert "does not" in text and "wrong implementation" in text


def test_a_brief_with_no_acceptance_section_is_not_measured(tmp_path, monkeypatch):
    path = tmp_path / "empty.md"
    path.write_text("# Brief\n\nno criteria here\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv",
                        ["check_criteria_discriminate.py", str(path),
                         "--repo-root", str(tmp_path)])
    assert cd.main() == 2


def test_exit_zero_only_when_every_criterion_fails_today(tmp_path, monkeypatch):
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1", "AC-002: `false` exits 0")
    monkeypatch.setattr(sys, "argv",
                        ["check_criteria_discriminate.py", str(brief),
                         "--repo-root", str(tmp_path)])
    assert cd.main() == 0


# ── decomposition: N clauses need N readings ────────────────────────────────

def test_every_runnable_clause_is_executed(tmp_path):
    """Only the first span was run until decomposition, so the second half of a
    conjunction was never executed at all — not folded into one verdict, skipped."""
    brief = _brief(tmp_path, "AC-001: `echo a` prints a AND `echo b` prints b")
    rep = cd.run(brief, tmp_path)
    assert [c.command for c in rep.results[0].clauses] == ["echo a", "echo b"]


def test_a_vacuous_clause_masked_by_a_failing_one_is_caught(tmp_path):
    """The case that motivated the executor and that one verdict could not see.

    Measured on a consumer's B-067:

        clause 1 (the gate exists)  -> 0, because the gate is not written yet
        clause 2 (`go test -run TestGateRegistryParity`) -> exit 0, [no tests to run]

    The conjunction fails today, so a single reading calls the criterion sound. But
    clause 2 exits 0 today and will exit 0 after the work, because the test it names
    exists nowhere — so when the gate is built the whole criterion passes with clause 2
    measuring nothing.
    """
    brief = _brief(tmp_path, "AC-004: `false` prints 1 AND `true` exits 0")
    rep = cd.run(brief, tmp_path)
    result = rep.results[0]
    assert result.passes_today is False, "the conjunction must still read as failing"
    assert len(result.passing_clauses) == 1, "and the vacuous half must be named"
    assert rep.already_passing, "a criterion carrying one is refused"


def test_each_clause_is_judged_against_its_own_expectation(tmp_path):
    """`prints 1` and `exits 0` are different questions about different clauses.

    Applying the bullet's first expectation to every clause made one that exits 0 read
    as failing — the exact opposite of the finding decomposition exists to surface.
    """
    brief = _brief(tmp_path, "AC-001: `echo 1` prints 1 AND `false` exits 0")
    clauses = cd.run(brief, tmp_path).results[0].clauses
    assert clauses[0].passes_today is True
    assert clauses[1].passes_today is False


def test_the_refusal_separates_the_whole_from_the_half(tmp_path):
    """A reader needs to know which of the two shapes they have."""
    brief = _brief(tmp_path, "AC-001: `false` prints 1 AND `true` exits 0")
    text = cd.render(cd.run(brief, tmp_path), brief)
    assert "FAIL as a whole today" in text
    assert "will pass after the work too" in text

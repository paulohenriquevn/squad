"""A plan may not demand a name the project refuses, nor evidence at a shared path."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_symbol_naming import check_symbol_naming  # noqa: E402 — post-bootstrap import


def _plan(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "x-plan.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_a_plan_may_not_demand_a_test_named_by_a_ticket(tmp_path: Path) -> None:
    """Measured on a consumer 2026-09-16: seven plans demanded `TestB069_*`,
    `TestB046_*`, `TestB047_*` — 101 occurrences — while the string appeared in ZERO `.go`
    files. The tests exist under behaviour-shaped names, renamed by an implementer for
    exactly the reason the plan ignores.

    The plans also contradicted their own alignment briefs, which already carried the
    correct names, so the contradiction sat inside one item's own documents and nothing
    compared them.
    """
    report = check_symbol_naming(_plan(
        tmp_path, "- [ ] `grep -c '^--- PASS: TestB069_Retry'` prints 3\n"))
    assert report.soft_floor
    assert "TestB069" in report.distinct


def test_absence_is_not_the_signal_a_red_criterion_looks_the_same() -> None:
    """The check cannot key on the string being missing: that is what a RED criterion IS.
    It keys on the NAME being one the project refuses, which is decidable from the plan
    alone and needs no repository scan."""
    from check_symbol_naming import _TICKET_IN_SYMBOL  # noqa: PLC0415 — local by design

    assert _TICKET_IN_SYMBOL.search("TestB069_RetryReleaseActivation")
    assert _TICKET_IN_SYMBOL.search("test_b004_english_only")
    # A version and an algorithm are not tickets.
    assert not _TICKET_IN_SYMBOL.search("TestV2ParserAcceptsEmptyInput")
    assert not _TICKET_IN_SYMBOL.search("TestSHA256Digest")


def test_a_line_explaining_the_rule_is_not_a_demand(tmp_path: Path) -> None:
    """A plan that RENAMED its tests says so, and naming the retired symbol while
    explaining why it went is the behaviour to encourage."""
    report = check_symbol_naming(_plan(
        tmp_path, "The tests were renamed from `TestB069_Retry` because § 5.1 forbids a "
                  "ticket number in a test name.\n"))
    assert not report.soft_floor


def test_evidence_at_a_fixed_tmp_path_is_a_shared_mutable_global(tmp_path: Path) -> None:
    """`/tmp/b069-baseline.txt` collided across two concurrent lanes on that consumer:
    both files ended zero bytes, the `comm -13` criterion over them printed 0 and PASSED
    while proving nothing, and the file's mtime belonged to the OTHER lane — 82 seconds
    before its first commit.

    The substance held and the instrument was void, which is the worst combination: a
    criterion that cannot fail is indistinguishable from one that is satisfied.
    """
    report = check_symbol_naming(_plan(
        tmp_path, "- [ ] `comm -13 /tmp/b069-baseline.txt /tmp/b069-after.txt` prints 0\n"))
    assert report.soft_floor
    assert any("shared mutable global" in r for r in report.reasons)


def test_mktemp_is_the_answer_and_is_not_flagged(tmp_path: Path) -> None:
    report = check_symbol_naming(_plan(
        tmp_path, "- [ ] `D=$(mktemp -d); go test ./... > $D/after.txt` exits 0\n"))
    assert not report.soft_floor


def test_a_plan_that_could_not_be_read_caps_rather_than_passing(tmp_path) -> None:
    """The OSError branch returned the DEFAULT report.

    Every field empty means `soft_floor` is False, and `run_structural` applies no cap —
    so a plan nobody could open scored exactly like a plan with no forbidden name in it.
    A check cannot vouch for a file it never read.
    """
    from check_symbol_naming import check_symbol_naming

    a_directory = tmp_path / "looks-like-a-plan.md"
    a_directory.mkdir()

    report = check_symbol_naming(a_directory)

    assert report.unmeasured_because, "the reason was not recorded"
    assert report.soft_floor is True, "an unmeasured plan did not cap"
    assert report.stable_id == "soft_floor_symbol_naming_unmeasured"


def test_a_readable_plan_with_no_bad_name_does_not_cap(tmp_path) -> None:
    """The cap must be about the unread file, not about every plan."""
    from check_symbol_naming import check_symbol_naming

    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nName things for what they do.\n", encoding="utf-8")

    report = check_symbol_naming(plan)

    assert report.unmeasured_because == ""
    assert report.soft_floor is False

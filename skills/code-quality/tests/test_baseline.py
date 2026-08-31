"""Debt that was already there must not fail a change that did not cause it.

A consumer wrote the consequence into its own config on 2026-08-19, as the reason Go
stayed disabled: *the D1 pass brings 36 REAL dead-code findings, and the verdict is one
per language — turning it on before paying them fails the delivery over legitimate
debt, which is how a gate becomes something people work around*. That is exactly what
happened: every language went DEFER or DISABLED, the gate then audited nothing,
`no_languages_audited` fired, and every plan came back INVALID. Each step was right and
the system was deadlocked.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from _detector_contract import Finding, compute_verdict, load_baseline


def _finding(severity: str, key: str, path: str = "api/svc.go") -> Finding:
    return Finding(detector="d1_dead_code", language="go", severity=severity,
                   file_path=path, symbol_or_line="OldHelper",
                   message="unused", allowlist_key=key)


# ── the verdict ───────────────────────────────────────────────────────────────


def test_a_baselined_finding_does_not_fail_the_change() -> None:
    hard = _finding("HARD", "go|api/svc.go|dead_code|OldHelper")
    assert compute_verdict([hard])[0] == "FAIL_HARD"
    assert compute_verdict([hard], frozenset({hard.allowlist_key}))[0] == "PASS"


def test_a_new_finding_still_fails_beside_baselined_ones() -> None:
    """The whole point: old debt is held, new defects are not."""
    old = _finding("HARD", "go|api/svc.go|dead_code|OldHelper")
    new = _finding("HARD", "go|api/svc.go|dead_code|NewHelper")
    verdict, caps = compute_verdict([old, new], frozenset({old.allowlist_key}))
    assert verdict == "FAIL_HARD"
    assert caps


def test_a_new_finding_in_a_baselined_file_still_fails() -> None:
    """Keyed by finding, not by file — a baselined file is not an exempt file."""
    old = _finding("HARD", "go|api/svc.go|dead_code|OldHelper")
    new = _finding("SOFT_CAP", "go|api/svc.go|orphan_export|Other")
    assert compute_verdict([old, new], frozenset({old.allowlist_key}))[0] == "FAIL_SOFT"


def test_an_empty_baseline_changes_nothing() -> None:
    hard = _finding("HARD", "go|api/svc.go|dead_code|OldHelper")
    assert compute_verdict([hard], frozenset()) == compute_verdict([hard])


def test_the_severity_ladder_survives_baselining() -> None:
    """Baselining the top of the ladder must reveal the next rung, not skip to PASS."""
    k1, k2, k3 = ("go|a.go|dead_code|One", "go|a.go|orphan_export|Two",
                  "go|a.go|mutation_low|Three")
    ladder = [_finding("HARD", k1), _finding("SOFT_CAP", k2), _finding("SOFT_FLOOR", k3)]
    assert compute_verdict(ladder, frozenset({k1}))[0] == "FAIL_SOFT"
    assert compute_verdict(ladder, frozenset({k1, k2}))[0] == "PASS_WITH_CAVEATS"
    assert compute_verdict(ladder, frozenset({k1, k2, k3}))[0] == "PASS"


# ── reading the file ──────────────────────────────────────────────────────────


def test_comments_and_blanks_are_skipped(tmp_path: Path) -> None:
    f = tmp_path / "baseline.txt"
    f.write_text("# a header\n\ngo|api/svc.go|dead_code|OldHelper\n\n", encoding="utf-8")
    assert load_baseline(f) == frozenset({"go|api/svc.go|dead_code|OldHelper"})


def test_an_absent_baseline_is_empty_not_an_error(tmp_path: Path) -> None:
    assert load_baseline(tmp_path / "nope.txt") == frozenset()
    assert load_baseline(None) == frozenset()


def test_an_inline_comment_does_not_become_part_of_the_key(tmp_path: Path) -> None:
    f = tmp_path / "baseline.txt"
    f.write_text("go|api/svc.go|dead_code|X  # paid in Q4\n", encoding="utf-8")
    assert load_baseline(f) == frozenset({"go|api/svc.go|dead_code|X"})


# ── it must not become decoration ─────────────────────────────────────────────


def test_the_deadlock_the_baseline_exists_to_break() -> None:
    """36 pre-existing findings, one new one. Before: everything fails. After: the new one."""
    debt = [_finding("HARD", f"go|api/f{i}.go|dead_code|Sym{i}") for i in range(36)]
    assert compute_verdict(debt)[0] == "FAIL_HARD"

    baseline = frozenset(f.allowlist_key for f in debt)
    assert compute_verdict(debt, baseline)[0] == "PASS"

    introduced = _finding("HARD", "go|api/new.go|dead_code|Regression")
    assert compute_verdict(debt + [introduced], baseline)[0] == "FAIL_HARD"

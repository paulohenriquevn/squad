"""`/review`'s pre-condition stops depending on someone remembering it.

THE DEFECT THIS FIXES
---------------------
`code-quality-golden-rule.md § 1` says `FAIL_SOFT` only advances to `/review`
with an "explicit ADR dismissing each soft cap", and `cycle-review.md §
Pre-conditions` repeats the requirement. Grep across `/review`'s scripts on
2026-08-26: zero. The entire check was prose in `SKILL.md`:

    # /code-quality audit exists AND verdict ∈ {PASS, PASS_WITH_CAVEATS}
    test -f .claude/records/audits/{slug}-code-quality-*.md

A `test -f` the agent has to remember to run is not a gate — it is a note. And
the ADR, the piece that makes a soft cap dismissible, was looked for by nobody:
asserting it existed was enough.

WHY THIS LIVES IN THE CONSOLIDATOR, NOT IN A SEPARATE STEP
-----------------------------------------------------------
A separate step has the same fragility as the prose: someone has to call it.
`/review`'s verdict is already computed by `consolidate_findings.py`, so the
pre-condition enters as a synthetic BLOCKER in that same computation. A verdict
that ignores the upstream stops being possible, instead of stopping being
recommended.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_upstream_gate import check_upstream_gate


def _audit(root: Path, slug: str, verdict: str, soft: str = "_none_", hard: str = "_none_") -> Path:
    audits = root / "records" / "audits"
    audits.mkdir(parents=True, exist_ok=True)
    path = audits / f"{slug}-code-quality-2026-08-26.md"
    path.write_text(
        f"# Code-quality audit — {slug}\n\n"
        f"**Verdict:** {verdict}\n"
        f"**Score cap:** 70\n"
        f"**Hard caps triggered:** {hard}\n"
        f"**Soft caps triggered:** {soft}\n",
        encoding="utf-8",
    )
    return path


def _adr(root: Path, name: str, body: str) -> Path:
    adrs = root / "records" / "adrs"
    adrs.mkdir(parents=True, exist_ok=True)
    path = adrs / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The paths that must BLOCK
# ---------------------------------------------------------------------------

def test_a_missing_audit_blocks(tmp_path: Path) -> None:
    """With no audit, `/review` would be reviewing code nobody swept."""
    findings = check_upstream_gate(tmp_path, "demo")
    assert len(findings) == 1
    assert findings[0]["severity"] == "BLOCKER"
    assert "no /code-quality audit" in findings[0]["title"]


def test_fail_hard_blocks(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "FAIL_HARD", hard="dead_code_unallowlisted_python")
    findings = check_upstream_gate(tmp_path, "demo")
    assert len(findings) == 1
    assert findings[0]["severity"] == "BLOCKER"
    assert "FAIL_HARD" in findings[0]["title"]


def test_invalid_blocks(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "INVALID")
    assert check_upstream_gate(tmp_path, "demo")[0]["severity"] == "BLOCKER"


def test_fail_soft_without_any_adr_blocks(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "FAIL_SOFT", soft="soft_cap_orphan_export_python")
    findings = check_upstream_gate(tmp_path, "demo")
    assert len(findings) == 1
    assert findings[0]["severity"] == "BLOCKER"
    assert "soft_cap_orphan_export_python" in findings[0]["evidence"]


def test_an_adr_that_dismisses_only_one_of_two_caps_still_blocks(tmp_path: Path) -> None:
    """"Each soft cap" is the strict reading, and it is the one that closes the hole.

    With two caps and an ADR naming one, the loose reading ("an ADR exists")
    approves — and the cap nobody examined rides along with the one that was.
    """
    _audit(tmp_path, "demo", "FAIL_SOFT",
           soft="soft_cap_orphan_export_python, soft_cap_mutation_score_low_python")
    _adr(tmp_path, "0007-orphans", "# ADR: orphan exports\n\nsoft_cap_orphan_export_python is accepted because ...\n")

    findings = check_upstream_gate(tmp_path, "demo")

    assert len(findings) == 1
    assert "soft_cap_mutation_score_low_python" in findings[0]["evidence"]
    assert "soft_cap_orphan_export_python" not in findings[0]["evidence"]


# ---------------------------------------------------------------------------
# The paths that must PASS
# ---------------------------------------------------------------------------

def test_pass_produces_no_finding(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "PASS")
    assert check_upstream_gate(tmp_path, "demo") == []


def test_pass_with_caveats_produces_no_finding(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "PASS_WITH_CAVEATS")
    assert check_upstream_gate(tmp_path, "demo") == []


def test_fail_soft_with_an_adr_per_cap_passes(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "FAIL_SOFT",
           soft="soft_cap_orphan_export_python, soft_cap_mutation_score_low_python")
    _adr(tmp_path, "0007-caps", "# ADR\n\nWe dismiss soft_cap_orphan_export_python and "
                                "soft_cap_mutation_score_low_python because ...\n")
    assert check_upstream_gate(tmp_path, "demo") == []


def test_the_plans_adr_section_counts_as_the_dismissal(tmp_path: Path) -> None:
    """The ADR may live in the plan — that is where `/plan-write` writes them."""
    _audit(tmp_path, "demo", "FAIL_SOFT", soft="soft_cap_orphan_export_python")
    plans = tmp_path / "records" / "plans"
    plans.mkdir(parents=True)
    (plans / "demo-plan.md").write_text(
        "# Plan\n\n## ADRs\n\n- soft_cap_orphan_export_python: accepted because ...\n", encoding="utf-8")

    assert check_upstream_gate(tmp_path, "demo") == []


def test_the_newest_audit_wins(tmp_path: Path) -> None:
    """Re-auditing after a fix must count; the old audit must not block."""
    _audit(tmp_path, "demo", "FAIL_HARD", hard="dead_code_unallowlisted_python")
    audits = tmp_path / "records" / "audits"
    (audits / "demo-code-quality-2026-08-27.md").write_text(
        "**Verdict:** PASS\n**Hard caps triggered:** _none_\n**Soft caps triggered:** _none_\n",
        encoding="utf-8")

    assert check_upstream_gate(tmp_path, "demo") == []


# ---------------------------------------------------------------------------
# Robustez
# ---------------------------------------------------------------------------

def test_an_audit_without_a_verdict_line_blocks(tmp_path: Path) -> None:
    """An unreadable report is an absent verdict, not a favourable one."""
    audits = tmp_path / "records" / "audits"
    audits.mkdir(parents=True)
    (audits / "demo-code-quality-2026-08-26.md").write_text("# vazio\n", encoding="utf-8")

    findings = check_upstream_gate(tmp_path, "demo")
    assert findings[0]["severity"] == "BLOCKER"
    assert "unreadable" in findings[0]["title"]


@pytest.mark.parametrize("layout", ["records", ".claude/records"])
def test_both_install_layouts_are_searched(tmp_path: Path, layout: str) -> None:
    """The kit lives in two layouts, and a gate that sees only one of them is half a gate."""
    audits = tmp_path / layout / "audits"
    audits.mkdir(parents=True)
    (audits / "demo-code-quality-2026-08-26.md").write_text(
        "**Verdict:** PASS\n**Hard caps triggered:** _none_\n**Soft caps triggered:** _none_\n",
        encoding="utf-8")

    assert check_upstream_gate(tmp_path, "demo") == []

"""The CVE gate stops depending on someone remembering to honour it.

THE DEFECT THIS FIXES
---------------------
`cycle-plan.md § Phase contracts` lists, among the phase's hard gates, "no critical
CVE on a planned dependency" — and says, on the next line, what no other gate in
the cycle needs to say:

    **The `deps-audit` gate is the one gate in this cycle nothing mechanizes.**
    Every other hard gate above is checked by a script that can fail the phase.
    This one is not.

`skills/deps-audit/SKILL.md § 35` repeats: "Its gate is human-enforced, not
mechanized. `/plan-confidence` does not read this audit's verdict."

The declared reason was procedural: wiring the gate EXTENDS
`plan-confidence-golden-rule.md`'s contract, and extending a contract requires a
record. The record is written in the golden rule (§ "Rules that cannot be bent"), in the format this
repository actually uses — the files under `records/adrs/` are gitignored
and do not reach whoever clones.

WHAT THIS CHECK ASSERTS, AND WHAT IT REFUSES TO ASSERT
-------------------------------------------------------
It does NOT look for CVEs: `/deps-audit` does that, with the scanners. It reads
the VERDICT that run left on disk and turns it into a cap. Three states:

| State                                              | Effect |
|---|---|
| Plan declares no new dependency                    | does not apply |
| Declares one, and no report exists                 | soft floor (≤ 89) — nobody checked |
| Report with a CRITICAL/HIGH CVE in a declared dep  | hard cap (≤ 49) |

Absence of an audit never becomes "no CVE". Same rule as a zero denominator in D4
and an unreadable coverage report: not measured is not measured, never approved.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_deps_audit import (  # noqa: E402
    _declared_dependencies,
    check_deps_audit,
)

_PLAN_WITH_DEPS = """# Plan

## Dependencies

| Package | Version | Why |
|---|---|---|
| `requests` | 2.31.0 | HTTP client for the webhook sender |

## Phase 1
"""

_PLAN_NO_DEPS = """# Plan

## Dependencies

(none — no new dependency)

## Phase 1
"""

_PLAN_WITHOUT_SECTION = """# Plan

## Phase 1

Nothing about dependencies.
"""


def _plan(root: Path, body: str, slug: str = "demo") -> Path:
    plans = root / "records" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    path = plans / f"{slug}-plan.md"
    path.write_text(body, encoding="utf-8")
    return path


def _audit(root: Path, verdict: str, slug: str = "demo", caps: str = "") -> Path:
    audits = root / "records" / "audits"
    audits.mkdir(parents=True, exist_ok=True)
    path = audits / f"{slug}-deps-audit-2026-08-26.md"
    path.write_text(
        f"# Deps Audit: {slug}\n\n**Date:** 2026-08-26\n**Mode:** plan-bound:{slug}\n"
        f"**Verdict:** {verdict}\n**Hard caps triggered:** {caps or '_none_'}\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# When the check does NOT apply
# ---------------------------------------------------------------------------

def test_a_plan_with_no_dependencies_section_is_untouched(tmp_path: Path) -> None:
    plan = _plan(tmp_path, _PLAN_WITHOUT_SECTION)
    report = check_deps_audit(plan)
    assert report.applies is False
    assert report.hard_cap is False
    assert report.soft_floor is False


def test_an_explicit_none_is_untouched(tmp_path: Path) -> None:
    """`(none — no new dependency)` is a declaration, and the gate respects it."""
    plan = _plan(tmp_path, _PLAN_NO_DEPS)
    report = check_deps_audit(plan)
    assert report.applies is False


# ---------------------------------------------------------------------------
# When nobody audited
# ---------------------------------------------------------------------------

def test_declared_dependencies_without_an_audit_are_a_soft_floor(tmp_path: Path) -> None:
    """I cannot assert there is a CVE. I can assert nobody looked."""
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    report = check_deps_audit(plan)
    assert report.applies is True
    assert report.soft_floor is True
    assert report.hard_cap is False
    assert report.stable_id == "soft_floor_deps_audit_missing"
    assert "requests" in " ".join(report.reasons)


# ---------------------------------------------------------------------------
# When the audit exists
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("verdict", ["PASS", "PASS_WITH_CAVEATS"])
def test_a_clean_audit_clears_the_gate(tmp_path: Path, verdict: str) -> None:
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, verdict)
    report = check_deps_audit(plan)
    assert report.applies is True
    assert report.hard_cap is False
    assert report.soft_floor is False


def test_an_insecure_audit_is_a_hard_cap(tmp_path: Path) -> None:
    """The gate `cycle-plan.md` declared and nothing enforced."""
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, "FAIL_INSECURE", caps="critical_cve_in_declared_dep")
    report = check_deps_audit(plan)
    assert report.hard_cap is True
    assert report.stable_id == "deps_audit_insecure"
    assert "FAIL_INSECURE" in " ".join(report.reasons)


def test_a_medium_audit_is_a_soft_floor(tmp_path: Path) -> None:
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, "FAIL_MEDIUM")
    report = check_deps_audit(plan)
    assert report.hard_cap is False
    assert report.soft_floor is True
    assert report.stable_id == "soft_floor_deps_audit_medium"


def test_an_invalid_audit_is_a_hard_cap(tmp_path: Path) -> None:
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, "INVALID_PLAN_DEPS")
    assert check_deps_audit(plan).hard_cap is True


def test_an_audit_with_no_verdict_line_does_not_count_as_clean(tmp_path: Path) -> None:
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    audits = tmp_path / "records" / "audits"
    audits.mkdir(parents=True, exist_ok=True)
    (audits / "demo-deps-audit-2026-08-26.md").write_text("# empty\n", encoding="utf-8")

    report = check_deps_audit(plan)

    assert report.soft_floor is True, "an unreadable report is an absent verdict"


def test_the_newest_audit_wins(tmp_path: Path) -> None:
    """Re-auditing after bumping the dependency must count."""
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, "FAIL_INSECURE")
    audits = tmp_path / "records" / "audits"
    (audits / "demo-deps-audit-2026-08-27.md").write_text(
        "**Verdict:** PASS\n", encoding="utf-8")

    assert check_deps_audit(plan).hard_cap is False


@pytest.mark.parametrize("layout", ["records", ".claude/records"])
def test_both_install_layouts_are_searched(tmp_path: Path, layout: str) -> None:
    plans = tmp_path / layout / "plans"
    plans.mkdir(parents=True)
    plan = plans / "demo-plan.md"
    plan.write_text(_PLAN_WITH_DEPS, encoding="utf-8")
    audits = tmp_path / layout / "audits"
    audits.mkdir(parents=True)
    (audits / "demo-deps-audit-2026-08-26.md").write_text("**Verdict:** PASS\n", encoding="utf-8")

    assert check_deps_audit(plan).hard_cap is False
    assert check_deps_audit(plan).soft_floor is False


# ── one `(none)` discarded every dependency in the section ──────────────────


#: The shape `skills/deps-audit/SKILL.md § 160` prescribes, verbatim: an Existing table
#: carrying real packages, and a Removed table whose single row reads `(none)`.
_SKILL_TEMPLATE_SHAPE = """## Dependencies

### Existing — use as-is

| Package | Version | Ecosystem | Why |
|---|---|---|---|
| `github.com/go-chi/chi/v5` | `v5.2.5` | go | The router every api route is served through |

### New — to be introduced

| Package | Version | Ecosystem | Rule 9 rationale | Why this one |
|---|---|---|---|---|
| (none) | | | | |

### Removed

| Package | Last version | Why removed |
|---|---|---|
| (none) | | |

## Tasks
"""


def test_the_shape_the_skill_prescribes_does_not_discard_its_own_packages():
    """A plan following `deps-audit/SKILL.md` word for word declared nothing.

    The explicit-none marker was searched across the WHOLE `## Dependencies` body, so
    the `(none)` the template puts in the Removed table discarded the Existing table
    above it. `applies` went false and no audit was required — of a section naming a
    router with three fixed advisories against its pinned version.

    A security-driven bump of an existing dependency is the case where an audit matters
    most, and it was the one case the gate could not see.
    """
    assert _declared_dependencies(_SKILL_TEMPLATE_SHAPE) == ["github.com/go-chi/chi/v5"]


def test_a_none_marker_speaks_only_for_its_own_subsection():
    assert _declared_dependencies(
        "## Dependencies\n\n### New: (none)\n\n### Existing\n\n"
        "| Package | From | To | Why |\n|---|---|---|---|\n"
        "| `golang.org/x/net` | v0.30.0 | v0.33.0 | CVE-2026-72816 (HIGH) |\n"
    ) == ["golang.org/x/net"]


def test_a_none_marker_in_the_preamble_still_speaks_for_the_section():
    """Two consumer plans open with "This change adds no dependency — (none — no new
    package, module, library, tool or service)" and then spend paragraphs naming the
    packages they do NOT change. A statement made before any subsection exists is about
    the section, and scoping every marker to its own chunk would have made those plans
    demand an audit for packages they only mention while explaining the absence."""
    assert _declared_dependencies(
        "## Dependencies\n\n"
        "**This change adds no dependency — (none — no new package).**\n"
        "It imports `k8s.io/api/rbac/v1`, already required at `infra/tests/go.mod:14`.\n\n"
        "### Notes\n\n- `charts/web-api/values.yaml` gains four comments\n"
    ) == []


def test_both_subsections_empty_still_declares_nothing():
    assert _declared_dependencies(
        "## Dependencies\n\n### New: (none)\n\n### Existing: (none)\n") == []


def test_a_package_is_declared_in_a_row_or_a_bullet_not_in_a_sentence():
    """Reading every backticked token pulled `serviceAccount.name`, `r.logger` and
    `charts/web-api/values.yaml` out of prose and rationale columns — 45 false
    dependencies across 3 consumer plans, each of which would then have demanded a
    `/deps-audit` for something no ecosystem can resolve."""
    body = (
        "## Dependencies\n\n### Existing\n\n"
        "| Package | Version | Why |\n|---|---|---|\n"
        "| `log/slog` | stdlib | Already imported by `domain_provisioner.go`; "
        "logs through `r.logger` |\n"
    )
    assert _declared_dependencies(body) == ["log/slog"]


def test_a_file_the_plan_edits_is_not_a_package_it_depends_on():
    """`api/go.mod` and `api/go.sum` reached the package list once rows started being
    read. A manifest is the thing a dependency is declared IN, never one itself."""
    body = (
        "## Dependencies\n\n### Existing\n\n"
        "| Package | Version |\n|---|---|\n"
        "| `github.com/go-chi/chi/v5` | v5.3.2 |\n"
        "| `api/go.mod` | pinned |\n"
        "| `render.go` | n/a |\n"
    )
    assert _declared_dependencies(body) == ["github.com/go-chi/chi/v5"]

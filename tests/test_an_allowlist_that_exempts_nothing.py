r"""An allowlist a gate tells you to write must be one something reads.

Three files in `rules/` document the same exemption contract — pipe-separated fields,
an ISO sunset within 90 days, expired entries ignored, a malformed entry refused. One
of the three was read by anything:

    code-quality-allowlist.txt     load_allowlist()   parsed and enforced
    deps-audit-allowlist.txt       -                  no reader anywhere
    plan-confidence-allowlist.txt  -                  no reader anywhere

`check_deps_audit.py` is the worse of the two, because it INSTRUCTS a reader to use the
file it does not read. Inside its HARD cap: *"Bump the dependency, or allowlist the CVE
in `rules/deps-audit-allowlist.txt` with rationale and sunset."* Following that
instruction changed nothing and the gate went on failing with the same message.

`plan-confidence-allowlist.txt` promises *"Plans listed here are permitted to return
verdict=INVALID without failing CI"* in the file itself, in `PORTABLE.md` § 4 and in
`plan-confidence-golden-rule.md`. `setup.sh` installs it and `test_portability.py`
asserts it exists — a test that attests the file's PRESENCE and never that it does
anything, which is how a dead allowlist looks alive.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DEPS_GATE = REPO / "skills" / "plan-confidence" / "scripts" / "check_deps_audit.py"

SOON = (date.today() + timedelta(days=30)).isoformat()
PAST = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def deps_project(tmp_path: Path) -> Path:
    """A project whose plan declares a dependency the audit reports a CRITICAL CVE on."""
    (tmp_path / ".squad" / "records" / "plans").mkdir(parents=True)
    (tmp_path / ".squad" / "records" / "audits").mkdir(parents=True)
    (tmp_path / "rules").mkdir()
    (tmp_path / ".squad" / "records" / "plans" / "widget-plan.md").write_text(
        "# Plan\n\n## Dependencies\n\n"
        "| Package | Version | Why |\n|---|---|---|\n"
        "| `lodash` | 4.17.20 | utility belt |\n\n## Phase 1\n", encoding="utf-8")
    (tmp_path / ".squad" / "records" / "audits" / "widget-deps-audit-2026-09-21.md").write_text(
        "# Deps audit\n\n**Verdict:** FAIL_INSECURE\n\nlodash — GHSA-35jh-r3h4-6jhm, CRITICAL.\n",
        encoding="utf-8")
    return tmp_path


def _check(project: Path):
    sys.path.insert(0, str(DEPS_GATE.parent))
    sys.path.insert(0, str(REPO))
    try:
        import importlib

        import check_deps_audit
        importlib.reload(check_deps_audit)
        return check_deps_audit.check_deps_audit(
            project / ".squad" / "records" / "plans" / "widget-plan.md")
    finally:
        sys.path.pop(0)
        sys.path.pop(0)


def test_the_cve_gate_still_caps_without_an_allowlist(deps_project: Path) -> None:
    """The premise. Nothing here loosens the gate for a CVE nobody exempted."""
    assert _check(deps_project).hard_cap is True


def test_an_allowlisted_cve_is_exempt(deps_project: Path) -> None:
    """The instruction the gate prints must be one that works when followed."""
    (deps_project / "rules" / "deps-audit-allowlist.txt").write_text(
        f"npm | lodash | >=4.0.0,<4.17.21 | GHSA-35jh-r3h4-6jhm | {SOON} | "
        f"test-only dep, not in the production bundle\n", encoding="utf-8")

    report = _check(deps_project)

    assert report.hard_cap is False, report.reasons
    assert any("allowlist" in r.lower() for r in report.reasons), (
        "an exemption must be stated, not silent — a reader has to know a CVE was "
        "waived rather than absent"
    )


def test_an_expired_entry_does_not_exempt(deps_project: Path) -> None:
    """`Expired entries are IGNORED — the finding re-fires at full severity.`"""
    (deps_project / "rules" / "deps-audit-allowlist.txt").write_text(
        f"npm | lodash | >=4.0.0 | GHSA-35jh-r3h4-6jhm | {PAST} | expired waiver\n",
        encoding="utf-8")

    report = _check(deps_project)

    assert report.hard_cap is True
    assert any("expired" in r.lower() for r in report.reasons), report.reasons


def test_an_entry_for_a_different_cve_does_not_exempt(deps_project: Path) -> None:
    """An allowlist is per-advisory. A waiver for one CVE is not a waiver for the next."""
    (deps_project / "rules" / "deps-audit-allowlist.txt").write_text(
        f"npm | lodash | >=4.0.0 | GHSA-0000-0000-0000 | {SOON} | a different advisory\n",
        encoding="utf-8")

    assert _check(deps_project).hard_cap is True


def test_a_malformed_entry_is_refused_not_skipped(deps_project: Path) -> None:
    """A dropped line is an exemption somebody believes they have and does not."""
    (deps_project / "rules" / "deps-audit-allowlist.txt").write_text(
        "npm | lodash | oops\n", encoding="utf-8")

    report = _check(deps_project)

    assert report.hard_cap is True
    assert any("malformed" in r.lower() for r in report.reasons), report.reasons


def test_a_sunset_beyond_the_window_is_refused(deps_project: Path) -> None:
    """`MUST be ≤ 90 days` — a longer one is a permanent exemption with a date on it."""
    far = (date.today() + timedelta(days=400)).isoformat()
    (deps_project / "rules" / "deps-audit-allowlist.txt").write_text(
        f"npm | lodash | >=4.0.0 | GHSA-35jh-r3h4-6jhm | {far} | forever\n", encoding="utf-8")

    report = _check(deps_project)

    assert report.hard_cap is True
    assert any("90" in r for r in report.reasons), report.reasons


# ---------------------------------------------------------------------------
# plan-confidence: the allowlist three documents promise and nothing read
# ---------------------------------------------------------------------------

STRUCTURAL = REPO / "skills" / "plan-confidence" / "scripts" / "run_structural.py"


@pytest.fixture
def invalid_plan(tmp_path: Path) -> Path:
    """A project whose plan scores INVALID through an incomplete Coverage Matrix.

    NOT the example the allowlist file itself gives. `my-followup-plan|…|Follow-up note
    (not a full plan); no Coverage Matrix by design` describes a plan with NO Coverage
    Matrix section, and that does not reach INVALID at all — `run_structural.py` exits
    **2** with "No '## Coverage Matrix' section found in plan", which is the code for a
    plan it could not read. A waiver on the exit code must not cover that: exit 2 says
    the scoring never happened, and exempting it would turn "unreadable" into "passed".

    So the case exercised here is the one the waiver CAN serve — a plan that scored, and
    scored INVALID.
    """
    plans = tmp_path / ".squad" / "records" / "plans"
    plans.mkdir(parents=True)
    (tmp_path / "rules").mkdir()
    (plans / "followup-note-plan.md").write_text(
        "# Follow-up note\n\n## Coverage Matrix\n\n"
        "| # | Gap | Task(s) | Resolution |\n"
        "|---|-----|---------|------------|\n"
        "| 1 | the gap nobody mapped | not yet assigned | open |\n",
        encoding="utf-8")
    return tmp_path


def _score(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STRUCTURAL),
         str(project / ".squad" / "records" / "plans" / "followup-note-plan.md"),
         "--structural-only"],
        capture_output=True, text=True, cwd=project,
        check=False,
    )


def test_an_invalid_plan_fails_without_an_allowlist(invalid_plan: Path) -> None:
    """The premise: exit 1 is what the allowlist is supposed to be able to waive."""
    assert _score(invalid_plan).returncode == 1, _score(invalid_plan).stdout[-400:]


def test_an_allowlisted_plan_does_not_fail_ci(invalid_plan: Path) -> None:
    """`Plans listed here are permitted to return verdict=INVALID without failing CI.`"""
    (invalid_plan / "rules" / "plan-confidence-allowlist.txt").write_text(
        f"followup-note|{SOON}|Follow-up note, not a full plan; no Coverage Matrix by design\n",
        encoding="utf-8")

    result = _score(invalid_plan)

    assert result.returncode == 0, result.stdout[-400:] + result.stderr[-400:]


def test_the_verdict_is_still_reported_as_invalid(invalid_plan: Path) -> None:
    """The waiver is on the EXIT CODE, never on the verdict.

    Rewriting INVALID to something greener would hide the plan's state from every
    reader of the report, which is a different and worse thing than not failing CI.
    """
    (invalid_plan / "rules" / "plan-confidence-allowlist.txt").write_text(
        f"followup-note|{SOON}|documented deferral\n", encoding="utf-8")

    result = _score(invalid_plan)

    assert "INVALID" in result.stdout, result.stdout[-400:]
    assert "allowlist" in (result.stdout + result.stderr).lower(), (
        "a waived plan must say it was waived; silence reads as a plan that passed"
    )


def test_an_expired_plan_entry_fails_again(invalid_plan: Path) -> None:
    (invalid_plan / "rules" / "plan-confidence-allowlist.txt").write_text(
        f"followup-note|{PAST}|deferral that ran out\n", encoding="utf-8")

    assert _score(invalid_plan).returncode == 1


def test_an_entry_for_another_plan_does_not_waive_this_one(invalid_plan: Path) -> None:
    (invalid_plan / "rules" / "plan-confidence-allowlist.txt").write_text(
        f"some-other-plan|{SOON}|not this one\n", encoding="utf-8")

    assert _score(invalid_plan).returncode == 1

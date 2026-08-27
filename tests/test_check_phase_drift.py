"""The declared phase plan, confronted with what actually ran.

THE DEFECT THIS CLOSES — AND WHY IT IS THE ONE THAT MATTERS
------------------------------------------------------------
Measured 2026-08-27 in `deer-workflow` (studied, never adopted): a Workflow
declaring `meta.phases = [Plan, Execute]`, running `Plan` and `Undeclared`, and
never entering `Execute`, exits 0 with no warning. The event stream carries the
published plan and the execution that contradicts it, and **nothing compares
them**. Their generator SKILL asks the agent to check it, as item 3 of a
15-item list — the same delegation this repository has been removing from its
own gates all along.

That is why instrumenting alone is not enough. Events without this comparison
buy a prettier log of the same drift. Reading `rules/cycle-phases.txt` against
`records/cycle-events.jsonl` is the half neither system had.

THE FOUR THINGS IT ANSWERS
--------------------------
| Finding | Question |
|---|---|
| `phase_ran_undeclared` | a phase emitted that the chain does not know |
| `phase_out_of_order` | a phase emitted before one it depends on |
| `phase_advanced_over_blocking_verdict` | work continued past a FAIL |
| `phase_declared_never_ran` | a `required` phase left no event (`--expect-complete`) |

The third is the one worth the whole movement. `check_upstream_gate.py` already
refuses `/review` when the `/code-quality` audit is FAIL_HARD — but it reads the
audit file, so it can only speak for the run that produced that file. The stream
records the ORDER, which is what makes "review ran anyway, after the FAIL" a
question anyone can ask afterwards.

WHAT IT REFUSES TO CONCLUDE
---------------------------
A `conditional` phase that is missing is never a finding. An item killed in
DISCOVER never reaches PLAN, and `cycle-discover.md` calls that a SUCCESSFUL
outcome. Reporting those absences as debt is how a report earns the habit of
being ignored.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_phase_drift import check_phase_drift, load_declared_phases  # noqa: E402
from cycle_events import emit_phase_end, emit_phase_start  # noqa: E402

_PLAN = """\
# comment
backlog       | required    | entry point
discover      | required    | measures it
plan          | conditional | absent when killed
implement     | conditional | absent when killed
code-quality  | conditional | absent when implement never ran
review        | conditional | absent when implement never ran
"""


def _project(tmp_path: Path, plan: str = _PLAN) -> Path:
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "cycle-phases.txt").write_text(plan, encoding="utf-8")
    (tmp_path / ".claude" / "records").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _ran(root: Path, cycle: str, slug: str = "demo", verdict: str | None = "PASS") -> None:
    emit_phase_start(root, cycle=cycle, slug=slug)
    emit_phase_end(root, cycle=cycle, slug=slug, verdict=verdict)


def _kinds(report) -> list[str]:
    return [f.kind for f in report.findings]


# ---------------------------------------------------------------------------
# Reading the declaration
# ---------------------------------------------------------------------------

def test_the_plan_is_read_in_file_order(tmp_path: Path) -> None:
    """Order is positional. A phase list whose order came from a dict would
    reorder between runs and make `phase_out_of_order` a coin flip."""
    root = _project(tmp_path)

    phases = load_declared_phases(root)

    assert [p.name for p in phases] == [
        "backlog", "discover", "plan", "implement", "code-quality", "review",
    ]
    assert phases[0].required is True
    assert phases[2].required is False


def test_an_unknown_requirement_word_is_refused(tmp_path: Path) -> None:
    """`optional` is not `conditional`, and quietly treating it as one would let
    a typo silently downgrade a required phase."""
    root = _project(tmp_path, "backlog | optional | typo\n")

    with pytest.raises(ValueError, match="optional"):
        load_declared_phases(root)


def test_an_absent_declaration_is_an_error_not_an_empty_plan(tmp_path: Path) -> None:
    """An empty plan would make every stream conform to it. Same shape as the
    empty band table that made every discover plan INVALID, inverted: here it
    would make everything PASS."""
    (tmp_path / "rules").mkdir()

    with pytest.raises(FileNotFoundError):
        load_declared_phases(tmp_path)


# ---------------------------------------------------------------------------
# The comparison
# ---------------------------------------------------------------------------

def test_a_run_that_follows_the_chain_is_clean(tmp_path: Path) -> None:
    root = _project(tmp_path)
    for cycle in ("backlog", "discover", "plan", "implement"):
        _ran(root, cycle)

    report = check_phase_drift(root)

    assert report.findings == []
    assert report.slugs_seen == ["demo"]


def test_a_phase_the_chain_does_not_know_is_reported(tmp_path: Path) -> None:
    """The deer-workflow case, exactly: `Undeclared` ran and the plan never
    named it."""
    root = _project(tmp_path)
    _ran(root, "backlog")
    _ran(root, "undeclared-phase")

    report = check_phase_drift(root)

    assert _kinds(report) == ["phase_ran_undeclared"]
    assert "undeclared-phase" in report.findings[0].detail


def test_a_phase_running_before_its_predecessor_is_reported(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _ran(root, "implement")
    _ran(root, "discover")

    report = check_phase_drift(root)

    assert "phase_out_of_order" in _kinds(report)


def test_advancing_past_a_blocking_verdict_is_reported(tmp_path: Path) -> None:
    """The finding this whole movement exists for.

    `check_upstream_gate.py` refuses `/review` on a FAIL_HARD audit — but it
    reads the audit file, so it speaks only for the run that produced it. The
    stream records ORDER, which is what makes "review ran anyway, afterwards" a
    question anyone can ask.
    """
    root = _project(tmp_path)
    _ran(root, "implement")
    _ran(root, "code-quality", verdict="FAIL_HARD")
    _ran(root, "review")

    report = check_phase_drift(root)

    assert "phase_advanced_over_blocking_verdict" in _kinds(report)
    finding = next(f for f in report.findings
                   if f.kind == "phase_advanced_over_blocking_verdict")
    assert "code-quality" in finding.detail and "FAIL_HARD" in finding.detail


@pytest.mark.parametrize("verdict", ["PASS", "PASS_WITH_CAVEATS", "FAIL_SOFT"])
def test_a_non_blocking_verdict_does_not_stop_the_chain(tmp_path: Path, verdict: str) -> None:
    """`FAIL_SOFT` admits `/review` with an ADR per cap — the golden rule says
    so. Reporting it here would duplicate a judgement another gate already makes
    with more information."""
    root = _project(tmp_path)
    _ran(root, "code-quality", verdict=verdict)
    _ran(root, "review")

    assert check_phase_drift(root).findings == []


def test_a_missing_conditional_phase_is_not_a_finding(tmp_path: Path) -> None:
    """An item killed in DISCOVER never reaches PLAN, and the rule calls that a
    successful outcome."""
    root = _project(tmp_path)
    _ran(root, "backlog")
    _ran(root, "discover", verdict="ITEM_KILLED")

    assert check_phase_drift(root).findings == []


def test_a_missing_required_phase_is_reported_only_when_completeness_is_claimed(
    tmp_path: Path,
) -> None:
    """Mid-run, a required phase that has not happened yet is not a defect —
    it is a run in progress. `--expect-complete` is the caller stating that the
    run is finished, which is the only context where absence means something."""
    root = _project(tmp_path)
    _ran(root, "discover")

    assert check_phase_drift(root).findings == []

    report = check_phase_drift(root, expect_complete=True)

    assert "phase_declared_never_ran" in _kinds(report)
    assert "backlog" in report.findings[0].detail


# ---------------------------------------------------------------------------
# Several items in one stream
# ---------------------------------------------------------------------------

def test_each_slug_is_judged_on_its_own_chain(tmp_path: Path) -> None:
    """One stream carries every item's phases interleaved. Judging them as one
    sequence would report order violations that never happened."""
    root = _project(tmp_path)
    _ran(root, "backlog", slug="b-001")
    _ran(root, "backlog", slug="b-002")
    _ran(root, "discover", slug="b-001")
    _ran(root, "discover", slug="b-002")

    report = check_phase_drift(root)

    assert report.findings == []
    assert sorted(report.slugs_seen) == ["b-001", "b-002"]


def test_events_with_no_slug_are_judged_as_one_anonymous_chain(tmp_path: Path) -> None:
    """A standalone `/code-quality` sweep carries no slug. Dropping those events
    would hide exactly the ad-hoc runs most likely to skip a phase."""
    root = _project(tmp_path)
    emit_phase_end(root, cycle="code-quality", slug="", verdict="PASS")

    report = check_phase_drift(root)

    assert report.slugs_seen == ["(no slug)"]
    assert report.findings == []


def test_an_empty_stream_reports_nothing_rather_than_everything(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = check_phase_drift(root)

    assert report.findings == []
    assert report.events_read == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_the_cli_exits_nonzero_on_drift(tmp_path: Path) -> None:
    import subprocess

    root = _project(tmp_path)
    _ran(root, "code-quality", verdict="FAIL_HARD")
    _ran(root, "review")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_phase_drift.py"),
         "--project-root", str(root)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "phase_advanced_over_blocking_verdict" in result.stdout


def test_the_cli_reports_what_it_read_even_when_clean(tmp_path: Path) -> None:
    """A checker that says PASS without saying how much it inspected is the
    empty gate this ecosystem refuses everywhere else."""
    import subprocess

    root = _project(tmp_path)
    _ran(root, "backlog")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_phase_drift.py"),
         "--project-root", str(root)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0
    assert "2 event" in result.stdout


def test_this_repository_declares_a_readable_phase_plan() -> None:
    """The shipped `rules/cycle-phases.txt` must parse, or the gate is a gate
    over nothing."""
    phases = load_declared_phases(REPO_ROOT)

    assert [p.name for p in phases][:3] == ["backlog", "discover", "plan"]
    assert any(p.required for p in phases), "a plan where nothing is required checks nothing"

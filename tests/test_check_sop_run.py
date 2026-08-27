"""The run record: what was judged, and why it differed.

WHY THIS IS A SEPARATE ARTIFACT FROM THE SOP
---------------------------------------------
`rules/sop-schema.md` keeps the script and the judgement in different files, and
this checker is why that split has teeth. A procedure that absorbs its own
exceptions stops being a procedure — the next reader cannot tell the official
sequence from the six times somebody worked around it.

So the SOP says what to do, the run record says what happened, and the gate is
that the second accounts for the first.

THE TWO FINDINGS THAT CARRY THE DESIGN
--------------------------------------
**`step_unaccounted`** — a step the record does not mention is indistinguishable
from a step somebody skipped. Omitting is cheaper than admitting, and that
asymmetry is exactly what `/implement`'s checkpoint gate exists to close:
measured there, a task recorded as `pending` was caught HIGH while the same task
simply left out passed every gate.

**`deviation_without_condition`** — a deviation with no observed condition is not
judgement, it is improvisation with better manners. The condition is the whole
value of the record: it is what lets the next reader decide whether the SOP
should change or the situation was genuinely singular. Without it, a deviation
teaches nobody anything.

WHAT IT REFUSES TO JUDGE
------------------------
Whether the deviation was RIGHT. That is the skill, and no checker has it. What
the checker can demand is that the deviation be legible enough for a human to
judge later — the condition, the action, and who decided.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_sop_run import check_sop_runs  # noqa: E402

_SOP = """\
---
sop: demo-procedure
version: 1.0.0
owner: kit maintainer
last_reviewed: 2026-08-20
review_interval_days: 180
---

# Demo

## Steps
1. **Verify** the suite is green.
2. **Copy** the script into the sibling kit.
3. **Run** the gate.

## Escalation
- **The script is missing there** → stop and mark it not mechanized.
"""

_RUN = """\
---
sop: demo-procedure
sop_version: 1.0.0
run: 2026-08-27
operator: kit maintainer
outcome: COMPLETED_WITH_DEVIATIONS
---

## Steps
| # | Status | Note |
|---|---|---|
| 1 | done | suite green in 19s |
| 2 | adapted | see deviation |
| 3 | done | 0 unresolved |

## Deviations
- **Step 2** — condition observed: the sibling kit has no `suite_runners.py` →
  cited the runner without backticks instead → decided by: kit maintainer.
"""


def _project(tmp_path: Path, sop: str = _SOP, run: str = _RUN) -> Path:
    sops = tmp_path / "records" / "sops"
    runs = tmp_path / "records" / "sop-runs"
    sops.mkdir(parents=True, exist_ok=True)
    runs.mkdir(parents=True, exist_ok=True)
    if sop:
        (sops / "demo-procedure.md").write_text(sop, encoding="utf-8")
    if run:
        (runs / "demo-procedure-2026-08-27.md").write_text(run, encoding="utf-8")
    return tmp_path


def _kinds(report) -> list[str]:
    return sorted({f.kind for f in report.findings})


# ---------------------------------------------------------------------------
# The shape that passes
# ---------------------------------------------------------------------------

def test_a_complete_record_produces_no_finding(tmp_path: Path) -> None:
    root = _project(tmp_path)

    report = check_sop_runs(root)

    assert report.findings == [], [f.detail for f in report.findings]
    assert report.runs_read == 1
    assert report.steps_accounted == 3


# ---------------------------------------------------------------------------
# Accounting for every step
# ---------------------------------------------------------------------------

def test_a_step_the_record_never_mentions_is_reported(tmp_path: Path) -> None:
    """Omitting is cheaper than admitting — the asymmetry the checkpoint gate
    in `/implement` exists to close."""
    run = _RUN.replace("| 3 | done | 0 unresolved |\n", "")
    root = _project(tmp_path, run=run)

    report = check_sop_runs(root)

    assert "step_unaccounted" in _kinds(report)
    assert "3" in next(f.detail for f in report.findings if f.kind == "step_unaccounted")


def test_a_record_may_report_a_step_as_skipped(tmp_path: Path) -> None:
    """Skipping is a legitimate outcome; being silent about it is not."""
    run = _RUN.replace("| 3 | done | 0 unresolved |",
                       "| 3 | skipped | gate not installed in that kit |")
    root = _project(tmp_path, run=run)

    assert "step_unaccounted" not in _kinds(check_sop_runs(root))


def test_a_step_with_an_unknown_status_is_reported(tmp_path: Path) -> None:
    """`done` / `skipped` / `adapted` / `blocked` are the vocabulary. A status
    nobody recognises cannot be counted, and a record that cannot be counted is
    prose."""
    run = _RUN.replace("| 1 | done | suite green in 19s |",
                       "| 1 | fine | suite green in 19s |")
    root = _project(tmp_path, run=run)

    assert "unknown_step_status" in _kinds(check_sop_runs(root))


def test_a_record_accounting_for_a_step_the_sop_does_not_have_is_reported(
    tmp_path: Path,
) -> None:
    """The other direction: a step the operator performed and the SOP never
    declared. Either the procedure grew and nobody wrote it down, or the record
    is about a different SOP."""
    run = _RUN.replace("| 3 | done | 0 unresolved |",
                       "| 3 | done | 0 unresolved |\n| 4 | done | extra work |")
    root = _project(tmp_path, run=run)

    assert "step_not_in_sop" in _kinds(check_sop_runs(root))


# ---------------------------------------------------------------------------
# Deviations — the judgement half
# ---------------------------------------------------------------------------

def test_an_adapted_step_without_a_deviation_entry_is_reported(tmp_path: Path) -> None:
    """`adapted` in the table and nothing in `## Deviations` records that
    something changed and not what."""
    run = _RUN.split("## Deviations")[0]
    root = _project(tmp_path, run=run)

    assert "adapted_step_without_deviation" in _kinds(check_sop_runs(root))


def test_a_deviation_without_an_observed_condition_is_reported(tmp_path: Path) -> None:
    """The finding that carries the design.

    Without the condition, a deviation teaches nobody anything: the next reader
    cannot tell whether the SOP should change or the situation was singular.
    """
    run = _RUN.replace(
        "- **Step 2** — condition observed: the sibling kit has no `suite_runners.py` →\n"
        "  cited the runner without backticks instead → decided by: kit maintainer.",
        "- **Step 2** — did it differently → decided by: kit maintainer.",
    )
    root = _project(tmp_path, run=run)

    report = check_sop_runs(root)

    assert "deviation_without_condition" in _kinds(report)


def test_a_deviation_without_a_decider_is_reported(tmp_path: Path) -> None:
    """A judgement nobody signed is a judgement nobody answers for."""
    run = _RUN.replace(" → decided by: kit maintainer.", ".")
    root = _project(tmp_path, run=run)

    assert "deviation_without_decider" in _kinds(check_sop_runs(root))


def test_a_deviation_naming_no_step_is_reported(tmp_path: Path) -> None:
    run = _RUN.replace("- **Step 2** — condition observed:", "- condition observed:")
    root = _project(tmp_path, run=run)

    assert "deviation_without_step" in _kinds(check_sop_runs(root))


# ---------------------------------------------------------------------------
# Binding the record to the procedure
# ---------------------------------------------------------------------------

def test_a_record_pointing_at_a_sop_that_does_not_exist_is_reported(tmp_path: Path) -> None:
    root = _project(tmp_path, sop="")

    report = check_sop_runs(root)

    assert "run_references_unknown_sop" in _kinds(report)


def test_a_record_made_against_an_older_version_is_reported(tmp_path: Path) -> None:
    """Not a defect — a fact worth knowing. The procedure changed after this run,
    so the record describes a sequence that no longer exists, and reading it as
    current evidence would be reading the wrong document."""
    sop = _SOP.replace("version: 1.0.0", "version: 2.0.0")
    root = _project(tmp_path, sop=sop)

    report = check_sop_runs(root)

    assert "run_against_superseded_version" in _kinds(report)
    assert report.findings[0].severity == "INFO"


@pytest.mark.parametrize("field", ["sop", "operator", "outcome"])
def test_a_missing_required_field_is_reported(tmp_path: Path, field: str) -> None:
    run = "\n".join(line for line in _RUN.splitlines() if not line.startswith(f"{field}:"))
    root = _project(tmp_path, run=run)

    assert "malformed_run_frontmatter" in _kinds(check_sop_runs(root))


def test_an_outcome_outside_the_vocabulary_is_reported(tmp_path: Path) -> None:
    run = _RUN.replace("outcome: COMPLETED_WITH_DEVIATIONS", "outcome: went fine")
    root = _project(tmp_path, run=run)

    assert "unknown_outcome" in _kinds(check_sop_runs(root))


def test_an_outcome_claiming_no_deviations_while_recording_one_is_reported(
    tmp_path: Path,
) -> None:
    """The record contradicting itself is worse than either half alone: whoever
    reads only the frontmatter gets the wrong answer with no way to know."""
    run = _RUN.replace("outcome: COMPLETED_WITH_DEVIATIONS", "outcome: COMPLETED")
    root = _project(tmp_path, run=run)

    assert "outcome_contradicts_record" in _kinds(check_sop_runs(root))


# ---------------------------------------------------------------------------
# Sweeping
# ---------------------------------------------------------------------------

def test_a_project_with_no_runs_reports_nothing(tmp_path: Path) -> None:
    (tmp_path / "records" / "sops").mkdir(parents=True)

    report = check_sop_runs(tmp_path)

    assert report.findings == []
    assert report.runs_read == 0


def test_the_cli_exits_nonzero_on_a_blocking_finding(tmp_path: Path) -> None:
    import subprocess

    run = _RUN.replace(" → decided by: kit maintainer.", ".")
    root = _project(tmp_path, run=run)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_sop_run.py"),
         "--project-root", str(root)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "deviation_without_decider" in result.stdout


def test_the_cli_does_not_fail_on_info_alone(tmp_path: Path) -> None:
    """An INFO is a fact worth surfacing, not a reason to block a session."""
    import subprocess

    sop = _SOP.replace("version: 1.0.0", "version: 2.0.0")
    root = _project(tmp_path, sop=sop)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_sop_run.py"),
         "--project-root", str(root)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0
    assert "run_against_superseded_version" in result.stdout


def test_this_repository_has_sound_run_records() -> None:
    report = check_sop_runs(REPO_ROOT)

    blocking = [f for f in report.findings if f.severity != "INFO"]
    assert blocking == [], "\n".join(f"{f.run}: [{f.kind}] {f.detail}" for f in blocking)

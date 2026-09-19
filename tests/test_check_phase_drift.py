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
sys.path.insert(0, str(REPO_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(REPO_ROOT / "mechanisms" / "gates"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_phase_drift import (  # noqa: E402 — post-bootstrap import
    check_phase_drift,
    load_declared_phases,
)
from cycle_events import (  # noqa: E402 — post-bootstrap import
    emit_phase_end,
    emit_phase_start,
)

_PLAN = """\
# comment
backlog       | required    | entry point
discover      | required    | measures it
plan          | conditional | absent when killed
implement     | conditional | absent when killed
code-quality  | conditional | absent when implement never ran
review        | conditional | absent when implement never ran
"""


#: The real list is shipped in `rules/blocking-verdicts.txt`; a fixture that copied
#: it would pass while the shipped file said something else, so the file itself is
#: checked separately (see the shipped-rules tests below).
_BLOCKING = "FAIL\nFAIL_HARD\nINVALID\nNEEDS_FIXES\nNOT_VALIDATED\n"

#: Same reasoning for the band registry, added 2026-09-08 when `_CLEAN_VERDICTS`
#: stopped being a frozenset inside the checker. Only the tokens these fixtures
#: actually emit are classified — a fixture that mirrored the shipped file would pass
#: while the shipped file said something else, and the shipped file has its own test.
_BANDS = """
PASS                    | clean      | the fixture's ordinary success
IMPLEMENTATION_COMPLETE | clean      | the completion promise
FAIL                    | structural | the fixture's ordinary failure
FAIL_HARD               | structural | a hard cap
FAIL_SOFT               | redo       | soft caps fired; sends work back without blocking
INVALID                 | structural | a broken contract
NEEDS_FIXES             | redo       | findings that return the slice to implement
NOT_VALIDATED           | structural | the run established neither outcome
"""


def _project(tmp_path: Path, plan: str = _PLAN,
             blocking: str = _BLOCKING, bands: str = _BANDS) -> Path:
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "cycle-phases.txt").write_text(plan, encoding="utf-8")
    (tmp_path / "rules" / "blocking-verdicts.txt").write_text(blocking, encoding="utf-8")
    (tmp_path / "rules" / "verdict-bands.txt").write_text(bands, encoding="utf-8")
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
        [sys.executable, str(REPO_ROOT / "mechanisms" / "gates" / "check_phase_drift.py"),
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
        [sys.executable, str(REPO_ROOT / "mechanisms" / "gates" / "check_phase_drift.py"),
         "--project-root", str(root)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0
    assert "2 event" in result.stdout


def test_this_repository_declares_a_readable_phase_plan() -> None:
    """The shipped `rules/cycle-phases.txt` must parse, or the gate is a gate
    over nothing."""
    phases = load_declared_phases(REPO_ROOT)

    assert [p.name for p in phases][:5] == ["brainstorm", "design", "backlog", "discover", "plan"]
    assert any(p.required for p in phases), "a plan where nothing is required checks nothing"

    # The asymmetry is the contract rather than an oversight. `brainstorm` is
    # `conditional` because the kit is adopted into repositories that predate the
    # cycle, and reporting every one of them as missing a phase is how a drift
    # report teaches its reader to ignore it.
    #
    # `backlog` stays `required`: every unit of maintenance enters through it, so a
    # run with no backlog event is a run whose subject is unaccounted for.
    #
    # `discover` was `required` here until 2026-09-19 and is now `conditional`, for
    # the same reason `brainstorm` is: an item arriving with the evidence the phase
    # would produce — a reproduced bug with a failing test — has nothing to gain
    # from it, and `cycle-plan.md` already said so in its own pre-conditions
    # ("otherwise, run DISCOVER first"). The guard against planning on a hunch was
    # never this word; it is `triaged_without_evidence`, a BLOCKER that asks for
    # the evidence rather than for the ceremony that usually produces it.
    by_name = {p.name: p for p in phases}
    assert not by_name["brainstorm"].required
    assert by_name["backlog"].required, (
        "nothing would be required, and a plan where nothing is required checks "
        "nothing")
    assert not by_name["discover"].required


# ── going back is not going out of order ──────────────────────────────────────
#
# A gate that fails sends the work back: `code-quality` returns FAIL_SOFT and
# `implement` runs again. That is the chain doing its job. Measured on 2026-08-31, an
# item went code-quality(FAIL_SOFT) -> implement and the rule called it a defect.


def test_work_sent_back_by_a_failed_gate_is_not_out_of_order(tmp_path: Path) -> None:
    root = _project(tmp_path)
    for cycle in ("backlog", "discover", "plan", "implement"):
        _ran(root, cycle)
    _ran(root, "code-quality", verdict="FAIL_SOFT")
    _ran(root, "implement", verdict="FAIL")

    assert "phase_out_of_order" not in _kinds(check_phase_drift(root))


def test_going_back_with_no_failed_gate_is_still_out_of_order(tmp_path: Path) -> None:
    """The shape this check exists for: a step repeated with nothing sending it back."""
    root = _project(tmp_path)
    for cycle in ("backlog", "discover", "plan", "implement"):
        _ran(root, cycle)
    _ran(root, "code-quality", verdict="PASS")
    _ran(root, "implement")

    assert "phase_out_of_order" in _kinds(check_phase_drift(root))


def test_the_forward_chain_is_still_clean_after_the_change(tmp_path: Path) -> None:
    """The fix must not blind the check by making every order acceptable."""
    root = _project(tmp_path)
    for cycle in ("backlog", "discover", "plan", "implement", "code-quality", "review"):
        _ran(root, cycle)

    assert _kinds(check_phase_drift(root)) == []


def test_a_return_after_implementation_complete_is_out_of_order(tmp_path: Path) -> None:
    """`IMPLEMENTATION_COMPLETE` is the Step 4 milestone: the tasks are committed and
    the ACs verified. Nothing sent the work back, so a phase running earlier again is
    a step out of sequence, not rework.

    It appeared in the stream on 2026-08-31 — B-169 — and in twelve rule files, but in
    neither of the two lists that classify verdicts. Absent from `_CLEAN_VERDICTS`, a
    return after it read as rework: the conservative error, but by omission rather
    than by decision."""
    project = _project(tmp_path)
    _ran(project, "implement", verdict="IMPLEMENTATION_COMPLETE")
    _ran(project, "discover", verdict="SHIPPABLE")
    findings = check_phase_drift(project).findings
    assert [f.kind for f in findings] == ["phase_out_of_order"]


# ── a phase that runs INSIDE another is not a step out of sequence ──────────


_PLAN_NESTED = _PLAN.replace(
    "code-quality  | conditional | absent when implement never ran",
    "code-quality  | conditional | nested-in: implement — invoked by run_validation.py")


def test_a_nested_phase_is_not_judged_by_its_position(tmp_path: Path) -> None:
    """`cycle-phases.txt` has always said `code-quality` is "invoked internally by
    run_validation.py", and this gate — reading that same file — judged it by position
    anyway.

    Measured on a consumer 2026-09-15: `code-quality` fires many times per item around
    `implement`, which is `run_validation.py` doing exactly what the declaration
    describes. It produced ALL 19 of that run's divergences — 5 `phase_out_of_order`
    and 4 `phase_advanced_over_blocking_verdict` — and not one was real. A gate that
    reports the chain working correctly as a defect is worse than no gate: it teaches
    its reader to skip the output.
    """
    root = _project(tmp_path, plan=_PLAN_NESTED)
    _ran(root, "code-quality", verdict="INVALID")
    _ran(root, "implement", verdict="FAIL")
    _ran(root, "code-quality", verdict="FAIL_SOFT")
    _ran(root, "implement", verdict="PASS")
    assert _kinds(check_phase_drift(root)) == []


def test_the_nesting_marker_does_not_switch_the_ordering_check_off(tmp_path: Path) -> None:
    """Widening is only safe if what the gate exists for is still caught. `review`
    before `implement`, with nothing sent back, is the shape it was built to find."""
    root = _project(tmp_path, plan=_PLAN_NESTED)
    _ran(root, "discover")
    _ran(root, "review")
    _ran(root, "implement")
    assert "phase_out_of_order" in _kinds(check_phase_drift(root))


def test_a_blocking_verdict_still_stops_a_sequential_phase(tmp_path: Path) -> None:
    """The exemption is for nested phases only. A phase that IS a step in the sequence,
    running after a verdict that forbids advancing, is still reported."""
    root = _project(tmp_path, plan=_PLAN_NESTED)
    _ran(root, "discover", verdict="FAIL")
    _ran(root, "review")
    assert "phase_advanced_over_blocking_verdict" in _kinds(check_phase_drift(root))


def test_a_nested_phase_after_a_blocking_verdict_is_not_reported(tmp_path: Path) -> None:
    """The other side of the same line: `code-quality` running after `implement` failed
    is `run_validation.py` finishing its work, not the chain advancing past a gate."""
    root = _project(tmp_path, plan=_PLAN_NESTED)
    _ran(root, "implement", verdict="FAIL")
    _ran(root, "code-quality", verdict="FAIL_SOFT")
    assert "phase_advanced_over_blocking_verdict" not in _kinds(check_phase_drift(root))


def test_the_shipped_plan_marks_the_phase_run_validation_invokes() -> None:
    """The marker is only worth anything if the shipped declaration carries it."""
    phases = load_declared_phases(Path(__file__).resolve().parents[1])
    by_name = {p.name: p for p in phases}
    assert by_name["code-quality"].nested_in == "implement"
    assert not by_name["implement"].nested_in
    assert not by_name["review"].nested_in


def test_the_rule_says_nothing_invokes_this_gate_today() -> None:
    """Five pre-conditions in `cycle-idea-to-release.md` name this gate as their enforcer.

    It is written, tested and correct — and no entry point runs it, with or without
    `--expect-complete`. A rule naming a mechanism that nothing invokes reads as an
    enforced gate, which is the defect `check_gate_mechanisms` exists to catch from the
    other side. The claim now carries the debt, dated, and names the caller it needs.
    """
    rule = Path(__file__).resolve().parents[1] / "rules" / "cycle-idea-to-release.md"
    text = rule.read_text(encoding="utf-8")

    assert "not invoked by anything today" in text, (
        "the rule still presents check_phase_drift as an enforced gate")
    assert "not mechanized: debt" in text, "the debt carries no class"


def test_nothing_has_started_invoking_it_without_updating_the_rule() -> None:
    """The mirror: the day a caller appears, the note above becomes false and must go."""
    root = Path(__file__).resolve().parents[1]
    callers = []
    for base in ("mechanisms", "skills", "hooks"):
        directory = root / base
        for path in list(directory.rglob("*.py")) + list(directory.rglob("*.sh")):
            if "tests" in path.parts or "__pycache__" in path.parts:
                continue
            if path.name == "check_phase_drift.py":
                continue
            body = path.read_text(encoding="utf-8", errors="replace")
            # The gate being RUN, not mentioned. `board_state.py` names it in a comment
            # about which file declares the chain, and also happens to import subprocess
            # for unrelated reasons — "both strings appear in this file" is not evidence
            # of a call, and reading it as one is the same conflation this suite exists
            # to refuse.
            import re as _re
            if _re.search(r'["\']?check_phase_drift(\.py)?["\']?\s*[,)\]]', body) \
                    and "run(" in body:
                callers.append(str(path.relative_to(root)))

    assert not callers, (
        f"something now invokes the gate; the rule's debt note is stale: {callers}")

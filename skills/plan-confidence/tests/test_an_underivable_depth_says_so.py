"""An inability to derive the depth must not be reported as a derivation.

`classify_alignment_depth.classify` returns a verdict carrying two fields that exist for
exactly this: `measurable` and `why_unmeasurable`. `_depth_for` returned `.depth` and
dropped both, so a plan graded against the FULL rubric because the registry could not be
found read identically to one graded against FULL because the item needs it.

Measured by the consumer that reported it, from inside a worktree the registry is not in:

    check_alignment_gate.py <plan>
    ✗ alignment gate: BLOCKED
      alignment scores 68%, below the 90% threshold. Close these first:
      nfr_measurable, flows, scenario_classes, system_diagram.

From where the registry is, same item, same brief: depth LOCAL, and the brief scores
22/24 = 92%. It passes. Four of the criteria the message ordered closed are four of the
five artifacts LOCAL removes — whose absence is the point of LOCAL existing.

A lane read that message, concluded the `--depth` flag did not exist and that every LOCAL
item in every consumer was unbuildable, and stopped. The flag exists and this gate uses
it. The message was the only evidence available and it pointed at the item.

THE DEFAULT DOES NOT MOVE. FULL is the safe direction and the reverse would be the escape
hatch `alignment-threshold.md` refuses. What changes is that the reader can tell "this item
needs those artifacts" from "I could not find out whether it needs them" — the same
distinction `check_plugin_freshness` keeps between `unverifiable` and `aligned`, and the
same one this repository added to `check_verification_freshness` today between a killed run
and a failing one.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))
sys.path.insert(0, str(_ROOT / "tests"))

from check_alignment_gate import check_alignment_gate  # noqa: E402
from test_check_alignment_gate import _brief, _complete_brief, _plan  # noqa: E402


def _tree(tmp_path: Path, *, registry: bool) -> Path:
    """A plan and a complete brief. The registry is what decides whether depth derives."""
    plan = _plan(tmp_path)
    _brief(tmp_path, _complete_brief())
    if registry:
        # The CITED item, not just any registry. `_plan` writes a one-line registry that
        # names B-001, and the plan cites B-014 — so with that file in place the depth is
        # still underivable, for a different and equally honest reason. Asserting the
        # control against it would have passed on the wrong fact.
        (tmp_path / "BACKLOG.md").write_text(
            "# Backlog\n\n## Itens\n\n## B-014 — trace the p95   [ ]\n\n"
            "domain: data-plane-ts\nrepo: web-console\nsuggested_mode: review\n"
            "source: human\nevidence: `src/scan.ts:20`\nwhy_now: the scan got slower\n"
            "status: triaged\ndod:\n- the named case passes\n",
            encoding="utf-8")
    else:
        (tmp_path / "BACKLOG.md").unlink()
    return plan


def test_the_report_says_the_depth_was_not_derived(tmp_path: Path) -> None:
    report = check_alignment_gate(_tree(tmp_path, registry=False))
    assert report.depth_unmeasured, (
        "the gate graded a rubric it could not confirm was this item's, and the report "
        f"says nothing: verdict={report.verdict!r} reason={report.reason!r}")
    assert "BACKLOG" in report.depth_unmeasured, report.depth_unmeasured


def test_a_derivable_depth_carries_no_warning(tmp_path: Path) -> None:
    """The discrimination. A field that is always set has told the reader nothing."""
    report = check_alignment_gate(_tree(tmp_path, registry=True))
    assert not report.depth_unmeasured, report.depth_unmeasured


def test_the_reader_sees_it_in_the_rendered_output(tmp_path: Path) -> None:
    """A field no renderer prints is a field, not a message."""
    import subprocess

    plan = _tree(tmp_path, registry=False)
    gate = _ROOT / "skills" / "plan-confidence" / "scripts" / "check_alignment_gate.py"
    out = subprocess.run([sys.executable, str(gate), str(plan)],
                         capture_output=True, text=True, check=False)
    assert "NOT MEASURED" in out.stdout, out.stdout


def test_the_report_names_the_item_and_the_rubric_it_graded(tmp_path: Path) -> None:
    """A reader told to close four criteria cannot act without knowing whose rubric named them.

    Requested by the consumer that measured the wrong-item defect: the four criteria this
    gate named most often were four of the five artifacts the LOCAL rubric removes, so the
    reader was being sent to write documents their item does not require — and the message
    never said which item it had graded.
    """
    report = check_alignment_gate(_tree(tmp_path, registry=True))
    assert report.graded_as, "the report does not say what it graded"
    assert "B-014" in report.graded_as, report.graded_as
    assert "depth" in report.graded_as, report.graded_as

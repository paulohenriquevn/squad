#!/usr/bin/env python3
"""The run record: what was judged, and why it differed.

`rules/sop-schema.md` keeps the script and the judgement in separate files, and
this is what gives that split teeth. A procedure that absorbs its own exceptions
stops being a procedure — the next reader cannot tell the official sequence from
the six times somebody worked around it. So the SOP says what to do, the record
says what happened, and the gate is that the second accounts for the first.

THE TWO FINDINGS THAT CARRY THE DESIGN
--------------------------------------
**`step_unaccounted`** — a step the record does not mention is indistinguishable
from a step somebody skipped. Omitting is cheaper than admitting, and that
asymmetry is what `/implement`'s checkpoint gate exists to close: measured
there, a task recorded `pending` was caught HIGH while the same task simply left
out passed every gate.

**`deviation_without_condition`** — a deviation with no observed condition is not
judgement, it is improvisation with better manners. The condition is the whole
value of the record: it is what lets the next reader decide whether the SOP
should change or the situation was singular.

WHAT IT REFUSES TO JUDGE
------------------------
Whether the deviation was RIGHT. That is the skill, and no checker has it. What
a checker can demand is that the deviation be legible enough for a human to
judge later: the condition, the action, and who decided.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The family this file lives in, plus `lib/` — the import namespace stayed flat
# when `scripts/` became `mechanisms/<family>/`, so a sibling family is reached
# by path rather than by package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "conventions"))

from sop_format import (
    bullets,
    excerpt,
    knowledge_base_dir,
    resolve_knowledge_dir,
    section,
    split_frontmatter,
)
from squad.paths import authored_wiki_dir  # noqa: E402 — post-bootstrap import

#: The status vocabulary. A status nobody recognises cannot be counted, and a
#: record that cannot be counted is prose.
_STATUSES = frozenset({"done", "skipped", "adapted", "blocked"})

#: Outcomes, matching the verdict-token discipline the cycles already use.
_OUTCOMES = frozenset({"COMPLETED", "COMPLETED_WITH_DEVIATIONS", "ABORTED"})

_REQUIRED_FIELDS = ("sop", "run", "operator", "outcome")

_STEP_ROW_RE = re.compile(r"^\|\s*(?P<num>\d+)\s*\|\s*(?P<status>[\w-]*)\s*\|")
_SOP_STEP_RE = re.compile(r"^\s*(?P<num>\d+)[.)]\s+\S")
_DEVIATION_STEP_RE = re.compile(r"\bstep\s*(?P<num>\d+)\b", re.IGNORECASE)

#: The three things a deviation must carry to be legible later.
_CONDITION_MARKERS = ("condition observed", "observed:", "because", "condition:")
_DECIDER_MARKERS = ("decided by", "decision by", "approved by", "escalated to")


@dataclass(frozen=True)
class RunFinding:
    """One defect in one run record."""

    run: str
    kind: str
    detail: str
    severity: str = "BLOCKING"


@dataclass
class RunReport:
    """What the sweep saw."""

    runs_read: int = 0
    steps_accounted: int = 0
    deviations_read: int = 0
    findings: list[RunFinding] = field(default_factory=list)





def _sop_steps(sops_dir: Path | None, slug: str) -> set[int] | None:
    """The step numbers the SOP declares, or None when the SOP is unreachable."""
    if sops_dir is None:
        return None
    path = sops_dir / f"{slug}.md"
    if not path.is_file():
        return None
    _fields, body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    steps = section(body, "Steps") or ""
    return {int(m.group("num")) for line in steps.splitlines()
            if (m := _SOP_STEP_RE.match(line))}


def _sop_version(sops_dir: Path | None, slug: str) -> str | None:
    """`sops_dir` is resolved from BOTH bundles by the caller — see `_sops_dir_for`."""
    if sops_dir is None:
        return None
    path = sops_dir / f"{slug}.md"
    if not path.is_file():
        return None
    fields, _body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    return fields.get("version")


def check_sop_runs(project_root: Path) -> RunReport:
    """Sweep `records/sop-runs/` and bind each record to its procedure."""
    project_root = Path(project_root)
    report = RunReport()
    # The trail stays in the records; the procedures may have moved to
    # the bundle. Two different resolutions on purpose — a record of one
    # execution is not a concept, and the split is the decision this migration
    # rests on (docs/wiki/decisions/where-knowledge-lives.md).
    runs_dir = knowledge_base_dir(project_root, "sop-runs")
    # Both bundles, in the order a project's own comes first. The kit's authored SOPs
    # left the write root on 2026-09-21 and `resolve_knowledge_dir` answers from the
    # write root alone — so a run-file naming one of them resolved to nothing, and a
    # step-count mismatch against a SOP that could not be found reads exactly like a
    # SOP with no steps.
    sops_dir = (resolve_knowledge_dir(project_root, "sops")
                or authored_wiki_dir(project_root, "sops"))
    if runs_dir is None:
        return report

    for path in sorted(runs_dir.glob("*.md")):
        report.runs_read += 1
        fields, body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        _judge_one(path.name, fields, body, sops_dir, report)
    return report


def _judge_one(
    name: str, fields: dict[str, str], body: str, sops_dir: Path | None, report: RunReport
) -> None:
    missing = [key for key in _REQUIRED_FIELDS if not fields.get(key)]
    if missing:
        report.findings.append(RunFinding(
            name, "malformed_run_frontmatter",
            f"missing required field(s): {', '.join(missing)} — a record with no "
            "operator or outcome cannot be read as evidence that anyone ran anything",
        ))

    outcome = fields.get("outcome", "")
    if outcome and outcome not in _OUTCOMES:
        report.findings.append(RunFinding(
            name, "unknown_outcome",
            f"outcome {outcome!r} is outside the vocabulary "
            f"({', '.join(sorted(_OUTCOMES))}) — a token nobody recognises cannot be "
            "counted or compared across runs",
        ))

    slug = fields.get("sop", "")
    declared = _sop_steps(sops_dir, slug) if slug else None
    if slug and declared is None:
        report.findings.append(RunFinding(
            name, "run_references_unknown_sop",
            f"names SOP {slug!r}, and no `sops/{slug}.md` exists — a record bound to "
            "nothing describes a procedure nobody can read",
        ))

    recorded, adapted = _read_step_table(name, body, report)
    report.steps_accounted += len(recorded)

    if declared:
        for number in sorted(declared - set(recorded)):
            report.findings.append(RunFinding(
                name, "step_unaccounted",
                f"step {number} is declared in the SOP and the record never mentions it "
                "— a step nobody wrote about is indistinguishable from a step somebody "
                "skipped, and omitting is cheaper than admitting",
            ))
        for number in sorted(set(recorded) - declared):
            report.findings.append(RunFinding(
                name, "step_not_in_sop",
                f"step {number} is recorded and the SOP does not declare it — either "
                "the procedure grew and nobody wrote it down, or this record is about a "
                "different SOP",
            ))

    deviations = _read_deviations(name, body, report)

    for number in sorted(adapted - deviations):
        report.findings.append(RunFinding(
            name, "adapted_step_without_deviation",
            f"step {number} is marked `adapted` and `## Deviations` says nothing about "
            "it — recording that something changed without recording what leaves the "
            "reader worse off than silence, because it looks accounted for",
        ))

    if outcome == "COMPLETED" and (deviations or adapted):
        report.findings.append(RunFinding(
            name, "outcome_contradicts_record",
            "outcome is `COMPLETED` while the record carries a deviation — whoever "
            "reads only the frontmatter gets the wrong answer with no way to know. "
            "Use `COMPLETED_WITH_DEVIATIONS`",
        ))

    recorded_version = fields.get("sop_version")
    current = _sop_version(sops_dir, slug) if slug else None
    if recorded_version and current and recorded_version != current:
        report.findings.append(RunFinding(
            name, "run_against_superseded_version",
            f"ran against SOP v{recorded_version}; the procedure is now v{current} — "
            "the record describes a sequence that no longer exists, and reading it as "
            "current evidence would be reading the wrong document",
            severity="INFO",
        ))


def _read_step_table(name: str, body: str, report: RunReport) -> tuple[list[int], set[int]]:
    body_section = section(body, "Steps") or ""
    recorded: list[int] = []
    adapted: set[int] = set()
    for line in body_section.splitlines():
        match = _STEP_ROW_RE.match(line.strip())
        if not match:
            continue
        number = int(match.group("num"))
        status = match.group("status").strip().lower()
        recorded.append(number)
        if status not in _STATUSES:
            report.findings.append(RunFinding(
                name, "unknown_step_status",
                f"step {number} has status {status!r} — the vocabulary is "
                f"{', '.join(sorted(_STATUSES))}, and a status nobody recognises cannot "
                "be counted",
            ))
        elif status == "adapted":
            adapted.add(number)
    return recorded, adapted


def _read_deviations(name: str, body: str, report: RunReport) -> set[int]:
    body_section = section(body, "Deviations")
    if body_section is None:
        return set()

    entries = bullets(body_section)
    steps: set[int] = set()
    for entry in entries:
        report.deviations_read += 1
        lowered = entry.lower()

        match = _DEVIATION_STEP_RE.search(entry)
        if match is None:
            report.findings.append(RunFinding(
                name, "deviation_without_step",
                f"deviation names no step: {excerpt(entry)!r} — a deviation floating "
                "free of the sequence cannot be checked against the procedure",
            ))
        else:
            steps.add(int(match.group("num")))

        if not any(marker in lowered for marker in _CONDITION_MARKERS):
            report.findings.append(RunFinding(
                name, "deviation_without_condition",
                f"deviation records no observed condition: {excerpt(entry)!r} — a "
                "deviation with no condition is not judgement, it is improvisation "
                "with better manners. The condition is what lets the next reader "
                "decide whether the SOP should change or the situation was singular",
            ))

        if not any(marker in lowered for marker in _DECIDER_MARKERS):
            report.findings.append(RunFinding(
                name, "deviation_without_decider",
                f"deviation names nobody who decided it: {excerpt(entry)!r} — a "
                "judgement nobody signed is a judgement nobody answers for",
            ))
    return steps




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bind each SOP run record to the procedure it claims to follow.",
    )
    parser.add_argument(
        "--root", "--project-root", dest="root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)

    report = check_sop_runs(args.root)
    blocking = [f for f in report.findings if f.severity != "INFO"]

    plural = "" if report.runs_read == 1 else "s"
    print(
        f"read {report.runs_read} run record{plural}: {report.steps_accounted} step(s) "
        f"accounted, {report.deviations_read} deviation(s) — {len(blocking)} blocking "
        f"finding(s), {len(report.findings) - len(blocking)} informational"
    )
    print(
        "  (legibility only: whether a deviation was RIGHT is judgement this checker "
        "does not claim)"
    )
    for finding in report.findings:
        marker = "" if finding.severity == "BLOCKING" else " (info)"
        print(f"  [{finding.kind}]{marker} {finding.run}: {finding.detail}")

    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())

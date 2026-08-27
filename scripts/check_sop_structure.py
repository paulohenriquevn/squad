#!/usr/bin/env python3
"""The shape of an operating procedure, checked.

`rules/sop-schema.md` splits the static script from the judgement that runs it.
This checks the half a text scan can check — the script's shape — and refuses to
pretend it can judge the other half.

WHAT IT CHECKS
--------------
| Finding | What it catches |
|---|---|
| `step_without_imperative` | "the branch should be workspace" — a state, not an instruction |
| `decision_branch_without_exit` | a branch the tree opens and never closes |
| `missing_escalation` | a procedure asserting reality never departs from it |
| `escalation_without_route` | "escalate if needed" — names neither trigger nor action |
| `competency_without_verification` | a training matrix with the training left out |
| `sop_stale` | past its own declared review interval |
| `malformed_frontmatter` / `owner_names_nobody` | no version, no date, no one to ask |

THE ONE THAT MATTERS MOST
-------------------------
`missing_escalation`. Every other finding is about a badly written script; this
one is about a script that claims to be complete. A SOP with no escalation
section asserts the world never differs from its assumption, and that assertion
is what converts a deviation into an undocumented improvisation — the document
offered nowhere to put it.

WHAT IT DELIBERATELY CANNOT DO
------------------------------
It does not judge whether the steps are the RIGHT steps, whether the declared
`standard:` is actually satisfied, or whether an escalation route is sensible.
That is judgement — the skill half — and a checker asserting it would be the
fabricated confidence this ecosystem caps a plan at 49 for. It checks shape, and
says so in its own output.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sop_format import (
    bullets,
    excerpt,
    has_content,
    resolve_knowledge_dir,
    section,
    split_frontmatter,
)

_SOPS_DIR = "sops"

#: OKF reserved filenames: navigation and history, never concepts.
_RESERVED_FILENAMES = frozenset({"index.md", "log.md"})

_REQUIRED_FIELDS = ("sop", "version", "owner", "last_reviewed")
_DEFAULT_REVIEW_INTERVAL = 180

#: An owner a reader can actually reach. "the team" cannot be asked a question,
#: and an unanswerable owner is the same as none.
_ANONYMOUS_OWNERS = frozenset({
    "the team", "team", "everyone", "anyone", "tbd", "n/a", "-", "_none_", "us",
})

#: A numbered step: `1. ...` or `1) ...`.
_STEP_RE = re.compile(r"^\s*\d+[.)]\s+(?P<body>.+)$")

#: Mermaid edge with a label — `B -->|yes| C` — and without — `A --> B`.
_EDGE_RE = re.compile(r"^\s*(?P<src>\w+)\s*-->\s*(?:\|[^|]*\|\s*)?(?P<dst>\w+)")
#: A decision node is written with braces: `B{Mechanism exists here?}`.
_DECISION_NODE_RE = re.compile(r"(?P<id>\w+)\{")

#: An escalation entry: a condition and a route, separated by an arrow.
_ESCALATION_ARROW = ("\u2192", "->")

#: Words that betray a described state rather than a commanded action. Checked
#: on the step's opening clause only: "verify the branch should exist" is an
#: instruction, "the branch should exist" is not.
_NON_IMPERATIVE_OPENERS = re.compile(
    r"^(the|a|an|it|this|that|there|we|you|i|all|each|every|any|no|"
    r"once|after|before|when|if|while|during|ensure that)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SopFinding:
    """One structural defect in one SOP."""

    sop: str
    kind: str
    detail: str


@dataclass
class SopReport:
    """What the sweep saw. Counts print whether or not anything failed."""

    sops_read: int = 0
    steps_read: int = 0
    branches_read: int = 0
    findings: list[SopFinding] = field(default_factory=list)






def check_sop_structure(project_root: Path, *, today: str | None = None) -> SopReport:
    """Sweep `records/sops/` and report every structural defect."""
    project_root = Path(project_root)
    report = SopReport()
    directory = resolve_knowledge_dir(project_root, _SOPS_DIR)
    if directory is None:
        return report

    reference = date.fromisoformat(today) if today else date.today()

    for path in sorted(directory.glob("*.md")):
        # `index.md` and `log.md` are OKF reserved filenames at any level of the
        # hierarchy — a directory listing and a change history, never concepts.
        # Reading them as SOPs reported the bundle's own navigation as a
        # malformed procedure.
        if path.name in _RESERVED_FILENAMES:
            continue
        report.sops_read += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        fields, body = split_frontmatter(text)
        name = path.name

        _check_frontmatter(name, fields, reference, report)
        _check_steps(name, body, report)
        _check_decisions(name, body, report)
        _check_escalation(name, body, report)
        _check_competencies(name, body, report)

    return report


def _check_frontmatter(
    name: str, fields: dict[str, str], reference: date, report: SopReport
) -> None:
    missing = [key for key in _REQUIRED_FIELDS if not fields.get(key)]
    if missing:
        report.findings.append(SopFinding(
            name, "malformed_frontmatter",
            f"missing required field(s): {', '.join(missing)} — a procedure with no "
            "version, date or owner cannot be audited, re-read on schedule, or "
            "questioned by whoever it fails",
        ))

    owner = fields.get("owner", "").strip().lower()
    if owner and owner in _ANONYMOUS_OWNERS:
        report.findings.append(SopFinding(
            name, "owner_names_nobody",
            f"owner is {fields['owner']!r} — an owner is someone a reader can reach "
            "when the procedure fails them, and a collective noun cannot be asked a "
            "question",
        ))

    reviewed = fields.get("last_reviewed", "")
    if reviewed:
        try:
            reviewed_on = date.fromisoformat(reviewed)
        except ValueError:
            report.findings.append(SopFinding(
                name, "malformed_frontmatter",
                f"last_reviewed {reviewed!r} is not an ISO date",
            ))
            return
        try:
            interval = int(fields.get("review_interval_days", _DEFAULT_REVIEW_INTERVAL))
        except ValueError:
            interval = _DEFAULT_REVIEW_INTERVAL
        due = reviewed_on + timedelta(days=interval)
        if reference > due:
            overdue = (reference - due).days
            report.findings.append(SopFinding(
                name, "sop_stale",
                f"last reviewed {reviewed}, interval {interval} days, {overdue} day(s) "
                "overdue — a procedure nobody re-read since the system changed under it "
                "keeps being followed after it stopped describing the thing",
            ))


def _check_steps(name: str, body: str, report: SopReport) -> None:
    body_section = section(body, "Steps")
    if not has_content(body_section):
        report.findings.append(SopFinding(
            name, "malformed_frontmatter" if body_section is None else "missing_steps",
            "no `## Steps` section with content — a SOP without a sequence is a note",
        ))
        return

    for line in (body_section or "").splitlines():
        match = _STEP_RE.match(line)
        if not match:
            continue
        report.steps_read += 1
        opener = match.group("body").strip()
        # Strip bold markers so house style is not mistaken for the contract.
        bare = re.sub(r"^\*{1,2}", "", opener).lstrip()
        if _NON_IMPERATIVE_OPENERS.match(bare):
            report.findings.append(SopFinding(
                name, "step_without_imperative",
                f"step opens with a description, not a command: {excerpt(opener)!r} — "
                "passive voice hides the actor, and a step whose actor is unclear is a "
                "step nobody performs",
            ))


def _check_decisions(name: str, body: str, report: SopReport) -> None:
    body_section = section(body, "Decisions")
    if body_section is None:
        # Not every procedure branches. Demanding a diagram from a linear
        # procedure produces a diagram drawn to satisfy a checker.
        return

    edges: list[tuple[str, str]] = []
    decision_nodes: set[str] = set()
    for line in body_section.splitlines():
        edge = _EDGE_RE.match(line)
        if edge:
            edges.append((edge.group("src"), edge.group("dst")))
        decision_nodes.update(_DECISION_NODE_RE.findall(line))

    outgoing: dict[str, int] = {}
    for src, _dst in edges:
        outgoing[src] = outgoing.get(src, 0) + 1
    report.branches_read += sum(outgoing.get(node, 0) for node in decision_nodes)

    for node in sorted(decision_nodes):
        count = outgoing.get(node, 0)
        if count < 2:
            report.findings.append(SopFinding(
                name, "decision_branch_without_exit",
                f"decision node `{node}` has {count} outgoing branch(es) — a question "
                "with fewer than two answers is not a decision, and a branch the tree "
                "opens and never closes is the same defect as a declared phase that "
                "never runs: the diagram looks complete and the path is not there",
            ))


def _check_escalation(name: str, body: str, report: SopReport) -> None:
    body_section = section(body, "Escalation")
    if not has_content(body_section):
        report.findings.append(SopFinding(
            name, "missing_escalation",
            "no `## Escalation` section with content — this is the gate that carries "
            "the SOP/skill distinction. A procedure with no escalation asserts that "
            "reality never departs from it, and that assertion is what turns a "
            "deviation into an improvisation nobody records: the document offered "
            "nowhere to put it",
        ))
        return

    entries = bullets(body_section or "")
    for entry in entries:
        if not any(arrow in entry for arrow in _ESCALATION_ARROW):
            report.findings.append(SopFinding(
                name, "escalation_without_route",
                f"escalation entry names no route: {excerpt(entry)!r} — an entry must "
                "carry the observed condition AND what to do about it, separated by "
                "`→`. \"Escalate if needed\" names neither the trigger nor the action",
            ))


def _check_competencies(name: str, body: str, report: SopReport) -> None:
    body_section = section(body, "Competencies")
    if not has_content(body_section):
        # Optional by design: a procedure only one role ever performs does not
        # need a matrix, and demanding one produces a row written to fill it.
        return

    for line in (body_section or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3 or set(stripped) <= set("|-: "):
            continue
        if cells[0].lower() in ("competency", "competência", "skill"):
            continue
        if not cells[2]:
            report.findings.append(SopFinding(
                name, "competency_without_verification",
                f"competency {cells[0]!r} says who may perform it and not how anyone "
                "knows they can — a matrix that lists a name without evidence is a "
                "training record with the training left out",
            ))



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the structural shape of this project's SOPs.",
    )
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--today", default=None, help="ISO date, for testing staleness")
    args = parser.parse_args(argv)

    report = check_sop_structure(args.project_root, today=args.today)

    plural = "" if report.sops_read == 1 else "s"
    print(
        f"read {report.sops_read} SOP{plural}: {report.steps_read} step(s), "
        f"{report.branches_read} decision branch(es) — {len(report.findings)} "
        "structural finding(s)"
    )
    print(
        "  (shape only: whether these are the RIGHT steps, and whether a declared "
        "standard is met, is judgement this checker does not claim)"
    )
    for finding in report.findings:
        print(f"  [{finding.kind}] {finding.sop}: {finding.detail}")

    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())

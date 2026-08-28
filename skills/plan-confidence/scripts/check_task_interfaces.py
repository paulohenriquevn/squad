#!/usr/bin/env python3
"""Cross-check task interfaces in a plan, before any of it is implemented.

WHY THIS EXISTS
---------------
`check_wiring.py` asks the same question one phase too late: it runs after
`/implement`, when the mismatched calls have already been written. Two tasks that
disagree about a signature are cheapest to reconcile while both are still prose.

The method is taken from an observed `subagent-driven-development` run
(obra/superpowers, 2026-08-28), whose pre-flight pass cross-checked 14
producer/consumer pairs before any code and found six defects in the plan:
a helper no task called, a duplicate import, unrelated changes riding along, and
— the one that pays for the whole pass — `assert.throws` returning `undefined`
at eight call sites, which would have failed every test in two files.

WHAT IT READS, AND WHY ONLY THAT
--------------------------------
Only `#### Pseudo-code / Signatures` blocks. Inferring symbols from prose would
fire on any task that mentions a function name in passing, and a gate that cries
wolf in a consumer is a gate somebody disables — measured this same week on
`check_evidence_citations`, which raised `fabricated_citation` on the kit's own
detector vocabulary and cost a cycle.

Blocks in other shapes — a ```js block holding real test code, which is how the
motivating plan declared its interfaces — are deliberately NOT read. Harvesting
symbols from any code block would pick up locals, imports and fixtures, and the
noise would bury the signal. Measured: run against that plan, this reports 7
tasks and 7 unchecked, which is the honest answer.

Tasks without a signature block are COUNTED and reported as unchecked, never as
clean. The template calls those blocks optional ("skip for trivially-defined
tasks"), so a pass reporting clean over a plan it could not read would be a green
tick that measured nothing.

Usage:
    python3 check_task_interfaces.py <plan.md> [--json]

Exit codes:
    0 — nothing to report
    1 — at least one interface finding
    2 — the plan could not be read
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: `### T1.2 — Title` opens a task in this kit's template. `### Task 4: Title` is
#: accepted too — it is what the plan that motivated this checker used, and a
#: checker that cannot read the document that proved it necessary is a checker
#: nobody can validate.
_TASK_RE = re.compile(
    r"^###\s+(T(?:ask)?\s*[\d.]+)\s*[—:-]?\s*(.*)$", re.MULTILINE | re.IGNORECASE
)

#: The signature block a task declares its interface in.
_SIGNATURE_BLOCK_RE = re.compile(
    r"^####\s+Pseudo-code\s*/\s*Signatures.*?```(?:pseudocode)?\n(.*?)```",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)

#: `function name(args)` / `def name(args)` — what the task PRODUCES.
_PRODUCES_RE = re.compile(r"^\s*(?:function|def|fn)\s+([A-Za-z_][\w]*)\s*\(", re.MULTILINE)

#: `name(args)` anywhere else in the block — what the task CONSUMES.
_CALL_RE = re.compile(r"(?<![\w.])([a-z_][\w]*)\s*\(")

#: Control flow and built-ins that are calls but not interfaces. Kept short on
#: purpose: every name here is one the checker will never report, so a long list
#: is a long list of blind spots.
_NOT_INTERFACES = frozenset({
    "if", "for", "while", "return", "switch", "catch", "print", "len",
    "append", "push", "map", "filter", "join", "split", "assert",
})


@dataclass(frozen=True)
class InterfaceReport:
    tasks_total: int
    tasks_with_signatures: int
    #: Declared by one task and called by none — a helper with no caller.
    produced_never_consumed: tuple[str, ...] = field(default=())
    #: Called by a task and declared by none — breaks at runtime.
    consumed_never_produced: tuple[str, ...] = field(default=())
    #: Called by a task that runs BEFORE the one declaring it.
    consumed_before_produced: tuple[str, ...] = field(default=())

    @property
    def has_findings(self) -> bool:
        return bool(self.produced_never_consumed
                    or self.consumed_never_produced
                    or self.consumed_before_produced)


def _tasks(content: str) -> list[tuple[str, str]]:
    """`(task id, body)` in plan order."""
    matches = list(_TASK_RE.finditer(content))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        out.append((m.group(1), content[m.end():end]))
    return out


def check_task_interfaces(plan_path: Path) -> InterfaceReport:
    """Producer/consumer coherence across the plan's tasks, in declaration order."""
    content = Path(plan_path).read_text(encoding="utf-8-sig")
    tasks = _tasks(content)

    produced: dict[str, int] = {}     # symbol -> index of the task producing it
    consumed: dict[str, int] = {}     # symbol -> index of the FIRST task using it
    with_signatures = 0

    for index, (_task_id, body) in enumerate(tasks):
        block = _SIGNATURE_BLOCK_RE.search(body)
        if not block:
            continue
        with_signatures += 1
        text = block.group(1)

        declares = set(_PRODUCES_RE.findall(text))
        for name in declares:
            produced.setdefault(name, index)

        for name in _CALL_RE.findall(text):
            if name in _NOT_INTERFACES or name in declares:
                continue
            consumed.setdefault(name, index)

    # A symbol is only orphaned if some LATER task could have called it. What the
    # final task produces is the plan's entry point by construction — nothing
    # inside the plan calls it, and reporting that would fire on every correct
    # plan. Caught by the test fixture on the first run: `checkExample`, declared
    # last, flagged as a helper with no caller.
    last_task = len(tasks) - 1
    orphan = tuple(sorted(
        n for n, at in produced.items()
        if n not in consumed and at < last_task
    ))
    undefined = tuple(sorted(n for n in consumed if n not in produced))
    out_of_order = tuple(sorted(
        f"{name} (used by task #{consumed[name] + 1}, produced by #{produced[name] + 1})"
        for name in consumed
        if name in produced and consumed[name] < produced[name]
    ))

    return InterfaceReport(
        tasks_total=len(tasks),
        tasks_with_signatures=with_signatures,
        produced_never_consumed=orphan,
        consumed_never_produced=undefined,
        consumed_before_produced=out_of_order,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = check_task_interfaces(args.plan)
    except OSError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    unchecked = report.tasks_total - report.tasks_with_signatures

    if args.json:
        print(json.dumps({
            "tasks_total": report.tasks_total,
            "tasks_with_signatures": report.tasks_with_signatures,
            "tasks_unchecked": unchecked,
            "produced_never_consumed": list(report.produced_never_consumed),
            "consumed_never_produced": list(report.consumed_never_produced),
            "consumed_before_produced": list(report.consumed_before_produced),
        }, indent=2))
        return 1 if report.has_findings else 0

    print(f"tasks: {report.tasks_total} · with signatures: {report.tasks_with_signatures} "
          f"· unchecked: {unchecked}")
    if unchecked:
        print(f"  {unchecked} task(s) declare no signature block — unknown, not clean.")
    for label, items, why in (
        ("produced and never consumed", report.produced_never_consumed,
         "a helper with no caller; D1 would flag it a phase later, after it was written"),
        ("consumed and never produced", report.consumed_never_produced,
         "a call to something no task declares — this one breaks at runtime"),
        ("consumed before produced", report.consumed_before_produced,
         "the symbol resolves, but the plan cannot be executed in its own order"),
    ):
        if items:
            print(f"\n{label} ({len(items)}) — {why}:")
            for item in items:
                print(f"  - {item}")
    if not report.has_findings:
        print("no interface findings")
    return 1 if report.has_findings else 0


if __name__ == "__main__":
    sys.exit(main())

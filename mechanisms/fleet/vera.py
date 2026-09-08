#!/usr/bin/env python3
"""VERA — the emitter behind `vera-technical-arbiter`.

WHAT THIS IS, AND WHAT IT IS NOT
================================
It is a **formatter**. It turns a judgement somebody made into one issue a lane
can execute: the title, the body, the labels, the schema. Formatting is
computation, and computation is what a mechanism may do.

It is not the arbiter. The arbiter is the agent — `agents/vera-technical-arbiter.md`
— who read the code. That file already stated the split before this module
implemented it:

    `mechanisms/fleet/vera.py` still owns the emission — the issue body, the
    labels, the schema. It is a formatter, and formatting is computation. You
    supply the judgement it used to fake.

    The split is the point. The script cannot be wrong about a label; you cannot
    be right about a lens without reading. Neither does the other's job.

WHAT IT USED TO DO, AND WHY THAT WAS THE DEFECT
===============================================
Until 2026-09-08 (#38) the "fake" was literal. `_detect_violations` matched a list
of substrings against the problem text; `_assess_severity` matched another;
`_estimate_work` contained `"57" in str(context)`, so a `file:line` reference
whose LINE NUMBER was 57 turned a typo into a two-week refactor; and
`_propose_solution` returned one of five hard-coded Solutions chosen by the lens
alone — its `problem` and `violations` parameters were never read, so the fix
proposed for a secret in a log was "Make structure immediately obvious".

Two further consequences of guessing, both measured:

- The `FAIL_FAST` block appeared twice, so a fail-fast match counted double and
  skewed the `max()` that picked the lens; and on the ordinary tie that `max()`
  returned the first member in the Enum's declaration order. The "dominant lens"
  was decided by the order someone wrote an Enum.
- Its default evidence strings were Portuguese and went into GitHub issue bodies
  in a repository that is English by policy.

This is the shape `mechanisms/cycle/delegated_decision.py` names in its own
docstring — *"a number that measured nothing but its own matcher"* — and it was
already fixed there once. Now here.

REFUSAL IS THE FEATURE
======================
Given no lens, no severity, no evidence or no `file:line`, this module raises
rather than supplying one. An inability to judge must never leave here as a
judgement: the output is filed as an issue, and a lane executes what it says.

Usage:
    python3 mechanisms/fleet/vera.py B-022 \\
      --problem      "<the violation, in one sentence>" \\
      --evidence     "<what you found>" \\
      --refs         "<path:line>,<path:line>" \\
      --lens         solid \\
      --severity     high \\
      --solution     "<the title of the fix>" \\
      --what-changes "<what actually changes in the code>" \\
      --how-to-verify "<how anyone knows it is done>"

Exit codes: 0 — the issue was emitted · 2 — the judgement was incomplete
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# ── The Five Lenses ────────────────────────────────────────────────────────────

class Lens(Enum):
    """Engineering principles a verdict can rest on.

    The value is the principle's definition, not a matcher. Nothing in this module
    reads a problem statement to choose between them — that is the agent's reading,
    and a substring is not a reading.
    """
    SOLID = "single-responsibility, open-closed, liskov, interface-segregation, dependency-inversion"
    DRY = "don't-repeat-yourself: knowledge must have one authoritative place"
    COUPLING = "low-coupling, high-cohesion: minimize dependencies across boundaries"
    FAIL_FAST = "fail loud and early: silent failures are the worst kind"
    CLARITY = "code as communication: structure must be immediately obvious to the next reader"


class Severity(Enum):
    """How bad this is. Supplied, never inferred."""
    BLOCKER = "blocker"  # Production-critical, breaks invariants
    HIGH = "high"  # Architecture violated, refactor required
    MEDIUM = "medium"  # Debt accumulated, affects maintainability
    LOW = "low"  # Nice-to-have, improves clarity


class WorkSize(Enum):
    """T-shirt sizing for the fix."""
    T1 = "t1"  # 1 file, 1-2 hours
    T2 = "t2"  # 2-5 files, 1-2 days
    T3 = "t3"  # 5+ files, major refactor, 1-2 weeks
    EPIC = "epic"  # Multiple phases, coordination required


#: What each lens says, as a principle. Selected by the lens the agent chose, so
#: it states a definition rather than analysing anything — the one thing this
#: module can be right about without reading the code.
_PRINCIPLE: dict[Lens, str] = {
    Lens.SOLID: "Principle: Single Responsibility, Open/Closed, Liskov Substitution, "
                "Interface Segregation, Dependency Inversion. SOLID violations cause "
                "brittleness at scale.",
    Lens.DRY: "Principle: Don't Repeat Yourself. Knowledge must have one authoritative "
              "source. When duplicated, versions diverge.",
    Lens.COUPLING: "Principle: Low coupling, high cohesion. Layering must be respected. "
                   "Infrastructure leakage breaks abstractions.",
    Lens.FAIL_FAST: "Principle: Fail loud and early. Silent failures hide bugs until "
                    "cascading damage. Better to fail immediately, with context.",
    Lens.CLARITY: "Principle: Code is communication. Structure must be immediately "
                  "obvious to the next maintainer.",
}


class JudgementMissing(ValueError):
    """The caller did not supply something only a reader of the code can supply.

    Raised rather than defaulted. Every field this refuses on was, at some point,
    filled in by a guess — and the guess reached a GitHub issue that a lane then
    executed.
    """


@dataclass(frozen=True)
class Solution:
    """The fix, as the arbiter stated it."""
    title: str
    description: str
    why_this: str  # the principle of the lens — the one part this module supplies
    what_changes: str  # what actually changes in the code
    how_to_verify: str  # how to know it is done right


@dataclass
class Verdict:
    """One arbitrated problem, ready to be filed."""
    problem_id: str
    problem_statement: str
    evidence: str
    code_references: list[str]
    dominant_lens: Lens
    severity: Severity
    work_size: WorkSize
    solution: Solution
    rationale: str
    scope_notes: str = ""
    created_issue: Optional[str] = None

    def to_issue(self) -> dict:
        """Format as a GitHub issue."""
        references = "\n".join(f"- `{ref}`" for ref in self.code_references)
        return {
            "title": f"[{self.severity.value}] {self.solution.title}",
            "body": f"""## Problem

{self.problem_statement}

## Evidence

{self.evidence}

{references}

## Root Cause

Violation of **{self.dominant_lens.name}**: {self.rationale}

## Solution

{self.solution.description}

### Why this solution

{self.solution.why_this}

### What changes

{self.solution.what_changes}

### How to verify

{self.solution.how_to_verify}

## Scope

- Size: **{self.work_size.value}**
- Severity: **{self.severity.value}**
{self.scope_notes and chr(10) + self.scope_notes}
---
*Emitted by `mechanisms/fleet/vera.py` from `vera-technical-arbiter`'s judgement.*
*Ref: {self.problem_id}*
""",
            "labels": [
                f"severity:{self.severity.value}",
                f"size:{self.work_size.value}",
                f"lens:{self.dominant_lens.name.lower()}",
            ],
        }


def size_from_reach(code_references: list[str], override: WorkSize | None = None) -> WorkSize:
    """How big the fix is, from how many places it touches.

    Countable, and that is the whole justification for computing it here: the
    number of distinct files a verdict cites is a fact about the verdict, not a
    reading of the problem. Anything less countable — "is this a major refactor?"
    — belongs to the arbiter, which is what `override` is for.

    The predecessor derived this from `"57" in str(context)`, which matched the
    line number of `app/main.py:57` and called a typo a two-week refactor.
    """
    if override is not None:
        return override
    files = {ref.split(":", 1)[0] for ref in code_references if ref.strip()}
    if len(files) > 5:
        return WorkSize.T3
    if len(files) > 2:
        return WorkSize.T2
    return WorkSize.T1


def emit(
    problem_id: str,
    problem_statement: str,
    *,
    lens: Lens | None,
    severity: Severity | None,
    solution_title: str,
    what_changes: str,
    how_to_verify: str,
    evidence: str,
    refs: list[str],
    description: str = "",
    size: WorkSize | None = None,
    scope_notes: str = "",
) -> Verdict:
    """Assemble a `Verdict` from a judgement, refusing to fill any part of it in.

    Each refusal below replaced a default that used to fire silently, and every
    one of those defaults ended up in an issue somebody was asked to execute.
    """
    if lens is None:
        raise JudgementMissing(
            "no lens: which principle this violates is a reading of the code, and "
            "this module does not read code. Supply --lens."
        )
    if severity is None:
        raise JudgementMissing(
            "no severity: how bad this is depends on what the code does, not on "
            "which words the problem statement contains. Supply --severity."
        )
    if not evidence.strip():
        raise JudgementMissing(
            "no evidence: an issue without a measurement spends a maintainer's "
            "attention and teaches them to skim the next one."
        )
    cited = [ref.strip() for ref in refs if ref.strip()]
    if not cited:
        raise JudgementMissing(
            "no file reference: a verdict nobody can go and check is a verdict "
            "about nothing."
        )
    if not solution_title.strip():
        raise JudgementMissing("no solution title: the issue would have no subject.")
    if not what_changes.strip():
        raise JudgementMissing(
            "the solution does not say what changes: a lane cannot execute a "
            "principle, only an edit."
        )
    if not how_to_verify.strip():
        raise JudgementMissing(
            "the solution does not say how to verify it: without that, 'done' is "
            "an opinion."
        )

    solution = Solution(
        title=solution_title.strip(),
        description=(description.strip() or solution_title.strip()),
        why_this=_PRINCIPLE[lens],
        what_changes=what_changes.strip(),
        how_to_verify=how_to_verify.strip(),
    )
    return Verdict(
        problem_id=problem_id,
        problem_statement=problem_statement,
        evidence=evidence.strip(),
        code_references=cited,
        dominant_lens=lens,
        severity=severity,
        work_size=size_from_reach(cited, size),
        solution=solution,
        rationale=_PRINCIPLE[lens],
        scope_notes=scope_notes.strip(),
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """VERA CLI."""
    import argparse

    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="Every judgement flag is required: this emits an issue a lane will "
               "execute, and a guess here is executed too.",
    )
    ap.add_argument("problem_id")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--evidence", required=True,
                    help="what you measured, in your words")
    ap.add_argument("--refs", required=True,
                    help="comma-separated code references (path:line)")
    ap.add_argument("--lens", required=True,
                    choices=[lens.name.lower() for lens in Lens],
                    help="the principle violated — YOUR reading, not a keyword match")
    ap.add_argument("--severity", required=True,
                    choices=[s.value for s in Severity])
    ap.add_argument("--solution", required=True, help="the title of the fix")
    ap.add_argument("--description", default="",
                    help="the fix in a paragraph (defaults to the title)")
    ap.add_argument("--what-changes", required=True,
                    help="what actually changes in the code")
    ap.add_argument("--how-to-verify", required=True,
                    help="how anyone knows it is done right")
    ap.add_argument("--size", choices=[w.value for w in WorkSize], default=None,
                    help="override the size derived from how many files are cited")
    ap.add_argument("--scope-notes", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        verdict = emit(
            args.problem_id,
            args.problem,
            lens=Lens[args.lens.upper()],
            severity=Severity(args.severity),
            solution_title=args.solution,
            description=args.description,
            what_changes=args.what_changes,
            how_to_verify=args.how_to_verify,
            evidence=args.evidence,
            refs=args.refs.split(","),
            size=WorkSize(args.size) if args.size else None,
            scope_notes=args.scope_notes,
        )
    except JudgementMissing as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(verdict.to_issue(), indent=2, ensure_ascii=False))
    else:
        print(f"Problem: {verdict.problem_statement}")
        print(f"Lens: {verdict.dominant_lens.name}")
        print(f"Severity: {verdict.severity.value}")
        print(f"Size: {verdict.work_size.value}")
        print(f"\nSolution: {verdict.solution.title}")
        print(f"{verdict.solution.description}")
        print(f"\nRationale: {verdict.rationale}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

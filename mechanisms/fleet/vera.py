#!/usr/bin/env python3
"""VERA — Verifiable Engineering Reference Arbiter.

The autonomous technical decision-maker for Squad. VERA reads problems,
applies FAANG-level engineering lenses, proposes the obvious solution,
and creates actionable issues for lanes to execute.

VERA does not equivocate. When SOLID says decouple, VERA says decouple.
When DRY says consolidate, VERA says consolidate. VERA speaks with the
authority of Dijkstra, McConnell, and Martin — not because she invented
these principles, but because software at scale requires them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

# ── The Five Lenses ────────────────────────────────────────────────────────────

class Lens(Enum):
    """Engineering principles that decide technical choices."""
    SOLID = "single-responsibility, open-closed, liskov, interface-segregation, dependency-inversion"
    DRY = "don't-repeat-yourself: knowledge must have one authoritative place"
    COUPLING = "low-coupling, high-cohesion: minimize dependencies across boundaries"
    FAIL_FAST = "fail loud and early: silent failures are the worst kind"
    CLARITY = "code as communication: structure must be immediately obvious to the next reader"


class Severity(Enum):
    """How bad is this violation."""
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


@dataclass(frozen=True)
class Violation:
    """A technical principle being violated."""
    lens: Lens
    file_or_area: str
    evidence: str
    consequence: str


@dataclass(frozen=True)
class Solution:
    """The obvious fix."""
    title: str
    description: str
    why_this: str  # Why this solution, not others
    what_changes: str  # What actually changes in the code
    how_to_verify: str  # How to know it's done right


@dataclass
class Verdict:
    """VERA's analysis of a problem."""
    problem_id: str
    problem_statement: str
    violations: list[Violation]
    dominant_lens: Lens
    severity: Severity
    work_size: WorkSize
    solution: Solution
    rationale: str
    scope_notes: str = ""
    created_issue: Optional[str] = None

    def to_issue(self) -> dict:
        """Format as a GitHub issue."""
        return {
            "title": f"[{self.severity.value}] {self.solution.title}",
            "body": f"""## Problem

{self.problem_statement}

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

---
*This issue was created by VERA, Squad's autonomous technical arbiter.*
*Ref: {self.problem_id}*
""",
            "labels": [
                f"severity:{self.severity.value}",
                f"size:{self.work_size.value}",
                f"lens:{self.dominant_lens.name.lower()}",
            ],
        }


# ── VERA's Decision Engine ─────────────────────────────────────────────────────

@dataclass
class VERA:
    """The Verifiable Engineering Reference Arbiter.
    
    VERA is given a technical problem, applies five FAANG-level lenses,
    and produces a verdict: the obvious solution and why it's obvious.
    """
    
    def analyze(self, problem_id: str, problem_statement: str, 
                context: dict) -> Verdict:
        """Analyze a technical problem and produce a verdict.
        
        Args:
            problem_id: B-001, B-022, etc.
            problem_statement: What's wrong
            context: {
                "evidence": "measured facts",
                "code_references": ["file:line"],
                "current_approach": "how it's currently done",
                "impact": "who/what is affected"
            }
        
        Returns:
            Verdict with solution and rationale
        """
        # Identify violations by applying each lens
        violations = self._detect_violations(problem_statement, context)
        
        # Pick the dominant lens (the one most violated)
        dominant_lens = max(
            (l for l in Lens),
            key=lambda l: sum(1 for v in violations if v.lens == l),
            default=Lens.CLARITY
        )
        
        # Determine severity and size
        severity = self._assess_severity(problem_statement, violations)
        size = self._estimate_work(violations, context)
        
        # Generate the solution
        solution = self._propose_solution(problem_statement, dominant_lens, 
                                         violations, context)
        
        # Rationale: why this lens decides it
        rationale = self._explain_rationale(dominant_lens, violations)
        
        return Verdict(
            problem_id=problem_id,
            problem_statement=problem_statement,
            violations=violations,
            dominant_lens=dominant_lens,
            severity=severity,
            work_size=size,
            solution=solution,
            rationale=rationale,
        )
    
    def _detect_violations(self, problem: str, context: dict) -> list[Violation]:
        """Apply the five lenses and identify violations."""
        violations: list[Violation] = []

        problem_lower = problem.lower()
        evidence_lower = context.get("evidence", "").lower()
        full_context = (problem_lower + " " + evidence_lower).lower()

        # Fail-Fast violations (highest priority)
        if any(w in full_context for w in ["silent", "silencio", "não percebe", "undetected",  # english-only: these are the words matched in Portuguese context
                                             "orfan", "orphan", "invisível", "unnoticed"]):
            violations.append(Violation(
                lens=Lens.FAIL_FAST,
                file_or_area=context.get("code_references", ["unknown"])[0],
                evidence=context.get("evidence", "falha silenciosa detectada"),
                consequence="errors go unnoticed until they cause cascading failures"
            ))

        # SOLID violations
        if any(w in full_context for w in ["acoplad", "coupled", "depend", "tight", "bloqueada"]):
            violations.append(Violation(
                lens=Lens.SOLID,
                file_or_area=context.get("code_references", ["unknown"])[0],
                evidence=context.get("evidence", "acoplamento detectado"),
                consequence="high-level module cannot be deployed independently"
            ))
        
        # DRY violations
        if any(w in problem_lower for w in ["duplic", "repeat", "duas árvore", "dois lugar"]):
            violations.append(Violation(
                lens=Lens.DRY,
                file_or_area=context.get("code_references", ["unknown"])[0],
                evidence=context.get("evidence", "duplicação detectada"),
                consequence="knowledge lives in multiple places; changes become brittle"
            ))
        
        # Coupling violations
        if any(w in problem_lower for w in ["acoplam", "depend", "boundary", "fronteira"]):
            violations.append(Violation(
                lens=Lens.COUPLING,
                file_or_area=context.get("code_references", ["unknown"])[0],
                evidence=context.get("evidence", "coupling detectado"),
                consequence="layering violated; infrastructure leaks into domain"
            ))
        
        # Fail-Fast violations
        if any(w in problem_lower for w in ["silent", "silencio", "não percebe", "undetected", "orfan"]):  # english-only: these are the words matched in Portuguese context
            violations.append(Violation(
                lens=Lens.FAIL_FAST,
                file_or_area=context.get("code_references", ["unknown"])[0],
                evidence=context.get("evidence", "falha silenciosa detectada"),
                consequence="errors go unnoticed until they cause cascading failures"
            ))
        
        # Clarity violations
        if any(w in problem_lower for w in ["confus", "ment", "unclear", "nome", "structure", "organiz"]):
            violations.append(Violation(
                lens=Lens.CLARITY,
                file_or_area=context.get("code_references", ["unknown"])[0],
                evidence=context.get("evidence", "falta clareza"),
                consequence="next maintainer cannot find or understand what is where"
            ))
        
        # Default if nothing matched: it's a clarity issue
        if not violations:
            violations.append(Violation(
                lens=Lens.CLARITY,
                file_or_area=context.get("code_references", ["unknown"])[0],
                evidence=context.get("evidence", problem),
                consequence="structure is not immediately obvious"
            ))
        
        return violations
    
    def _assess_severity(self, problem: str, violations: list[Violation]) -> Severity:
        """Judge how bad this is."""
        problem_lower = problem.lower()
        
        # BLOCKER: silent failures in critical paths
        if any(w in problem_lower for w in ["silent", "silencio", "undetect", "orfan", "orphan", 
                                             "segredo", "secret", "crypto", "não percebe"]):  # english-only: these are the words matched in Portuguese context
            return Severity.BLOCKER
        if any(w in problem_lower for w in ["arquitetura", "architecture", "acoplad", "depend"]):
            return Severity.HIGH
        if any(w in problem_lower for w in ["dívid", "debt", "test", "runbook"]):
            return Severity.MEDIUM
        if any(w in problem_lower for w in ["nome", "mensag", "message", "ux", "clarity"]):
            return Severity.LOW
        
        return Severity.MEDIUM
    
    def _estimate_work(self, violations: list[Violation], context: dict) -> WorkSize:
        """Estimate effort to fix."""
        code_refs = context.get("code_references", [])
        impact = context.get("impact", "unknown")
        
        if len(code_refs) > 5 or "múltiplo" in impact.lower() or "57" in str(context):
            return WorkSize.T3
        elif len(code_refs) > 2:
            return WorkSize.T2
        else:
            return WorkSize.T1
    
    def _propose_solution(self, problem: str, lens: Lens,
                         violations: list[Violation],
                         context: dict) -> Solution:
        """Propose the obvious solution."""
        
        if lens == Lens.SOLID:
            return Solution(
                title="Decouple high-level from low-level modules",
                description="Introduce an abstraction layer. High-level module depends on "
                           "interface, low-level implements it. This is dependency inversion.",
                why_this="SOLID DIP is the principle that lets large systems scale. When violated, "
                        "every change to infrastructure breaks every consumer.",
                what_changes="New interface in domain package; implementations in infrastructure package; "
                            "dependency arrow reversed.",
                how_to_verify="High-level module can be deployed independently of low-level. "
                             "Change one implementation without touching others.",
            )
        
        elif lens == Lens.DRY:
            return Solution(
                title="Consolidate duplicated knowledge into one authority",
                description="Identify the duplicated concept. Extract it to a single, "
                           "authoritative location. All consumers import from there.",
                why_this="DRY is about knowledge, not lines. When the same rule lives in two places, "
                        "they diverge. Which one is the truth?",
                what_changes="New shared module/package; remove copies; all sites import from one place.",
                how_to_verify="Search the codebase for the concept. One canonical definition remains.",
            )
        
        elif lens == Lens.COUPLING:
            return Solution(
                title="Move infrastructure out of domain boundary",
                description="Identify what leaked. Infrastructure (persistence, transport, secrets) "
                           "should not be known by domain logic.",
                why_this="Coupling across boundaries locks abstractions together. "
                        "Changes to one layer force changes across the boundary.",
                what_changes="Move persistence/transport references out of domain classes. "
                            "Introduce interface at boundary.",
                how_to_verify="Domain classes have zero imports from infrastructure packages.",
            )
        
        elif lens == Lens.FAIL_FAST:
            return Solution(
                title="Detect and fail immediately when invariant is violated",
                description="Silent failures are the worst kind. When the invariant is violated, "
                           "fail loud. Throw an exception with the specific context.",
                why_this="Silent failures hide bugs until they cause cascading damage. "
                        "Fail fast means debugging cost is low (happens immediately, context preserved).",
                what_changes="Add explicit check. Throw meaningful exception if check fails. "
                            "Add test for both pass and fail case.",
                how_to_verify="Add test: normal case passes, violation case throws with specific message.",
            )
        
        else:  # CLARITY
            return Solution(
                title="Make structure immediately obvious",
                description="Structure must communicate intent. Names must tell the truth. "
                           "Organization must reflect responsibility.",
                why_this="Code is read 10x more than it's written. Structure is the first thing "
                        "the next maintainer sees.",
                what_changes="Rename for truth. Reorganize by responsibility. Document the organization.",
                how_to_verify="A person unfamiliar with the code can navigate it and find what they need.",
            )
    
    def _explain_rationale(self, lens: Lens, violations: list[Violation]) -> str:
        """Why this lens decides it."""
        explanations = {
            Lens.SOLID: "Principle: Single Responsibility, Open/Closed, Liskov Substitution, "
                       "Interface Segregation, Dependency Inversion. SOLID violations cause "
                       "brittleness at scale.",
            Lens.DRY: "Principle: Don't Repeat Yourself. Knowledge must have one authoritative "
                     "source. When duplicated, versions diverge.",
            Lens.COUPLING: "Principle: Low coupling, high cohesion. Layering must be respected. "
                          "Infrastructure leakage breaks abstractions.",
            Lens.FAIL_FAST: "Principle: Fail loud and early. Silent failures hide bugs until "
                           "cascading damage. Better to fail immediately with context.",
            Lens.CLARITY: "Principle: Code is communication. Structure must be immediately "
                         "obvious to the next maintainer.",
        }
        return explanations.get(lens, "Engineering principle violation.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """VERA CLI."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("problem_id")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--evidence", default="")
    ap.add_argument("--refs", default="", help="comma-separated code references")
    ap.add_argument("--impact", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    
    vera = VERA()
    verdict = vera.analyze(
        args.problem_id,
        args.problem,
        {
            "evidence": args.evidence,
            "code_references": [r.strip() for r in args.refs.split(",") if r.strip()],
            "impact": args.impact,
        }
    )
    
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

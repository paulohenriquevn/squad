#!/usr/bin/env python3
"""Acceptance-Criteria / DoD enforcement gate for /implement (GAP 1+2).

`run_validation.py` runs the test/typecheck/lint/coverage commands, but the plan's
Acceptance Criteria and DoD checkboxes were otherwise honored only by the LLM
ticking `- [x]` in the implementation contract — with no script confronting those
claims against reality. This gate closes that bypass in three ways:

  1. **Inventory** — parse every AC/DoD checkbox in the plan and categorize it, so
     the gate knows what was promised.
  2. **Enforce the mechanizable ones run_validation does NOT cover** — file-size
     budget (`<= N lines` per changed file) and CHANGELOG-updated, both checked
     against the real committed diff. A self-ticked `- [x]` cannot mask a 600-line
     file or a missing CHANGELOG entry.
  3. **Surface the non-mechanizable ones** — "backward compatibility preserved" and
     other claims a script cannot prove are reported as
     `criterion_requires_human_evidence` (LOW) so they are visible for review
     instead of laundered through as silently-accepted ticks.

Categories already covered elsewhere are tagged, not re-checked:
  coverage/lint/typecheck/test → run_validation; complexity → /code-quality;
  runtime_metric → wiring pillar (c).

Exit codes (CLI):
  0 — no HIGH/BLOCKER finding (PASS / WARN / SKIP)
  1 — at least one HIGH/BLOCKER (e.g. file-size budget blown)
  2 — invocation error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# Headers whose checkbox body holds acceptance obligations.
_SECTION_RE = re.compile(
    r"^#{2,4}\s+.*(?:Acceptance Criteria|Definition of Done|\bDoD\b).*$",
    re.MULTILINE | re.IGNORECASE,
)
_ANY_HEADER_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
_CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[[ xX]\]\s*(.+?)\s*$", re.MULTILINE)
_FILE_SIZE_LIMIT_RE = re.compile(r"(\d{2,5})\s*lines", re.IGNORECASE)

# B-036 — the budget is a complexity proxy for CODE, and it was being applied to every file a slice
# touched. `CHANGELOG.md` is touched by every slice (Unbreakable Rule 6 requires the entry) and its
# released sections may never be rewritten, so it can only grow: 519 lines when B-036 was filed,
# 589 one session later. The budget could never be met again, by any slice, for obeying a different
# rule — and a gate nobody can satisfy is one people learn to read past.
#
# The exemption is by KIND, not by an allowlist of filenames, because an allowlist reproduces the
# problem for the next append-only document (`BACKLOG.md`, `ROADMAP.md`, an ADR) and depends on
# somebody remembering. An extension set is a list too — of KINDS, not INSTANCES: a new `.md` file
# is exempt the day it is created and a new `.ts` file is budgeted the same day, with nobody
# editing this script.
_SOURCE_SUFFIXES = frozenset({
    ".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".go", ".rs", ".java", ".rb", ".c", ".h", ".cc", ".cpp", ".hpp",
    ".sh", ".bash", ".zsh", ".sql",
})
# Build files carry no extension and are unambiguously source: they are executed, they accumulate
# logic, and length there is exactly the complexity the budget is about. Matched by NAME because
# they have no suffix to match on — the one place where a name list is the only available test.
_SOURCE_NAMES = frozenset({"Makefile", "GNUmakefile", "Dockerfile", "Justfile", "Rakefile"})


def _is_source(rel: str) -> bool:
    """Whether the budget is about this file at all.

    A long changelog is the rule being followed; a long module is the defect the budget looks for.
    """
    path = PurePosixPath(rel)
    return path.suffix.lower() in _SOURCE_SUFFIXES or path.name in _SOURCE_NAMES

# Categories run_validation / CQ / wiring already enforce — tagged, not re-checked.
_COVERED_ELSEWHERE = {
    "coverage": "run_validation",
    "lint": "run_validation",
    "typecheck": "run_validation",
    "test": "run_validation",
    "complexity": "code_quality",
    "runtime_metric": "wiring_pillar_c",
}
# Categories this gate cannot mechanically prove — surfaced for human review.
_NEEDS_EVIDENCE = {"backward_compat", "other"}


@dataclass(frozen=True)
class Criterion:
    text: str
    category: str
    # B-036 — the declared budget, read ONCE at parse time. It used to be re-extracted later by a
    # second pass over the same regex, which left a "no number found" branch that could not run:
    # a criterion only reaches category `file_size` by matching this very regex. A mutant flipping
    # that branch's value was killed by NOTHING, because nothing can reach it. Carrying the number
    # on the criterion removes the unreachable path instead of testing around it.
    limit: int | None = None


@dataclass(frozen=True)
class Finding:
    severity: str  # BLOCKER | HIGH | MEDIUM | LOW | INFO
    code: str
    message: str


@dataclass(frozen=True)
class AcceptanceReport:
    total_criteria: int
    by_category: dict[str, int]
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def has_high_or_blocker(self) -> bool:
        return any(f.severity in ("HIGH", "BLOCKER") for f in self.findings)

    @property
    def status(self) -> str:
        if self.total_criteria == 0:
            return "SKIP"
        if self.has_high_or_blocker:
            return "FAIL"
        if self.findings:
            return "WARN"
        return "PASS"


def categorize(text: str) -> str:
    """Map a criterion to a category by keyword. First match wins (order matters)."""
    t = text.lower()
    if "coverage" in t:
        return "coverage"
    if "lint" in t:
        return "lint"
    if "type error" in t or "typecheck" in t or "type-check" in t or "type errors" in t:
        return "typecheck"
    if "complexity" in t or "cyclomatic" in t:
        return "complexity"
    if "changelog" in t:
        return "changelog"
    if "backward" in t or "compatib" in t:
        return "backward_compat"
    if "metric" in t or "counter" in t:
        return "runtime_metric"
    # B-036 — a budget, not merely the WORD. `_categorise` used to return `file_size` for any text
    # containing "line" or "size", so B-022's "the widest-line delta between the old and new
    # snapshot is recorded" — a measurement, promising a number — armed a size gate over that whole
    # slice. Reading a measurement as a limit invents an obligation the author never wrote.
    #
    # The consequence is a stricter contract on the plan author: a budget must now be stated in the
    # `<= N lines` shape to be enforced. That is the right direction — an enforced budget nobody
    # declared is the defect being fixed here.
    if _FILE_SIZE_LIMIT_RE.search(t) and ("line" in t or "size" in t):
        return "file_size"
    if "test" in t:
        return "test"
    return "other"


def parse_criteria(plan_path: Path) -> list[Criterion]:
    content = plan_path.read_text(encoding="utf-8-sig")
    criteria: list[Criterion] = []
    for section in _SECTION_RE.finditer(content):
        start = section.end()
        nxt = _ANY_HEADER_RE.search(content, pos=start)
        body = content[start: nxt.start() if nxt else len(content)]
        for box in _CHECKBOX_RE.finditer(body):
            text = box.group(1).strip()
            category = categorize(text)
            limit_match = (
                _FILE_SIZE_LIMIT_RE.search(text) if category == "file_size" else None
            )
            criteria.append(Criterion(
                text=text,
                category=category,
                limit=int(limit_match.group(1)) if limit_match else None,
            ))
    return criteria


def _changed_files(repo_root: Path, shas: list[str]) -> list[str]:
    """Files touched by the given commits (name-only). Empty on any git failure."""
    if not shas:
        return []
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "show", "--name-only", "--pretty=format:", *shas],
            capture_output=True, text=True, timeout=20, check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    seen: list[str] = []
    for line in result.stdout.splitlines():
        f = line.strip()
        if f and f not in seen:
            seen.append(f)
    return seen


def check_acceptance_criteria(
    plan_path: Path,
    repo_root: Path | None = None,
    shas: list[str] | None = None,
) -> AcceptanceReport:
    criteria = parse_criteria(plan_path)
    by_category: dict[str, int] = {}
    for c in criteria:
        by_category[c.category] = by_category.get(c.category, 0) + 1

    if not criteria:
        return AcceptanceReport(total_criteria=0, by_category={})

    findings: list[Finding] = []
    shas = shas or []
    changed = _changed_files(repo_root, shas) if repo_root is not None else []

    # --- file_size budget (mechanizable, NOT covered by run_validation) ----------
    # B-036 — the declared budget IS the condition. There used to be two: a `file_size` category
    # check and a separate lookup that re-ran the same regex, leaving a "no number found" branch
    # nothing could reach. Measured: mutating that branch was killed by ZERO tests, twice, because
    # a criterion only reaches the category by matching the regex the lookup then re-ran. One
    # expression removes the unreachable path rather than testing around it — and mutating THIS
    # default to a number is caught, by `test_a_budget_the_plan_never_declared_is_not_enforced`.
    limit = next((c.limit for c in criteria if c.limit is not None), None)
    if limit is not None and repo_root is not None and changed:
        for rel in changed:
            if not _is_source(rel):
                continue
            path = repo_root / rel
            if not path.is_file():
                continue
            try:
                loc = sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            if loc > limit:
                findings.append(Finding(
                    severity="HIGH",
                    code="file_size_exceeded",
                    message=f"`{rel}` has {loc} lines, exceeding the <= {limit}-line "
                            f"budget this plan declares in its acceptance criteria.",
                ))

    # --- CHANGELOG updated (mechanizable) ----------------------------------------
    if by_category.get("changelog") and repo_root is not None and shas:
        if not any(Path(f).name == "CHANGELOG.md" for f in changed):
            findings.append(Finding(
                severity="MEDIUM",
                code="changelog_not_updated",
                message="Plan DoD requires a CHANGELOG.md entry, but no committed "
                        "diff in this implementation touched CHANGELOG.md "
                        "(Unbreakable Rule 6).",
            ))

    # --- non-mechanizable criteria: surface for human review ---------------------
    needs_evidence = [c for c in criteria if c.category in _NEEDS_EVIDENCE]
    if needs_evidence:
        sample = "; ".join(c.text for c in needs_evidence[:4])
        findings.append(Finding(
            severity="LOW",
            code="criterion_requires_human_evidence",
            message=f"{len(needs_evidence)} acceptance criterion(s) cannot be "
                    f"machine-verified and need explicit evidence in review (not a "
                    f"silently-ticked box): {sample}",
        ))

    return AcceptanceReport(
        total_criteria=len(criteria),
        by_category=by_category,
        findings=tuple(findings),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--sha", action="append", default=[], help="commit SHA (repeatable)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.plan.exists():
        print(f"plan file not found: {args.plan}", file=sys.stderr)
        return 2

    report = check_acceptance_criteria(args.plan, repo_root=args.repo_root, shas=args.sha)

    if args.json:
        print(json.dumps({
            "total_criteria": report.total_criteria,
            "by_category": report.by_category,
            "status": report.status,
            "findings": [{"severity": f.severity, "code": f.code, "message": f.message}
                         for f in report.findings],
            "has_high_or_blocker": report.has_high_or_blocker,
        }, indent=2))
    else:
        print(f"Acceptance criteria: {report.total_criteria} ({report.status})")
        for f in report.findings:
            print(f"  [{f.severity}] {f.code}: {f.message}")

    return 1 if report.has_high_or_blocker else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Diff cohesion check for /implement Step 4.7 mini review.

For a given phase, compares the set of files declared in `Files to edit`
(per task in the plan) against the set of files ACTUALLY modified during
the phase (per .progress-{slug}.json or git log). Flags ONE class:

  (1) Scope drift — file modified that no phase task declared in `Files to edit`.
                    HIGH severity. Often signals an opportunistic edit slipping in.

NOT IMPLEMENTED — cross-layer mix. This section listed it as "(2)", a MEDIUM finding
that "only fires if the project declares layers in rules/architecture.md", and the code
has never been able to emit it: line 336 says "intentionally not implemented yet" and
appends an INFO `cross_layer_check_skipped` on EVERY run, unconditionally, whatever the
project declares. So the contract advertised a second class of finding, and a reader
seeing only scope-drift findings concluded the layers were clean.

Stated as a gap rather than as a class with a condition on it: the condition was never
evaluated. Implementing it needs a layer model the project declares, and `arch-check`
is the skill that owns that question.
  - Git history is preferred for diff (`git log <first-sha>..<last-sha>`), with
    progress-file fallback when git is unavailable or commit SHAs are missing.
  - Files outside the source tree (CHANGELOG, docs, fixtures) are NOT flagged —
    declared scope is about source code under src/, lib/, internal/, etc.

Usage:
    python3 check_diff_cohesion.py \\
        --plan records/plans/foo-plan.md \\
        --progress records/implementations/.progress-foo.json \\
        --phase 1 \\
        --json

Exit codes:
    0 — PASS / INFO only
    1 — at least one HIGH / BLOCKER finding
    2 — invocation error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

TASK_HEADER_RE = re.compile(r"^###\s+(T\d+\.\d+)\s*[—\-–:]\s*(.+?)\s*$", re.MULTILINE)
NEXT_TASK_OR_H2_RE = re.compile(r"^(##\s+\S|###\s+T\d+\.\d+)", re.MULTILINE)
FILES_TO_EDIT_RE = re.compile(
    r"^####\s+Files\s+to\s+edit\s*$(.+?)(?=^####\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
#: The path a `Files to edit` bullet DECLARES, annotation and all.
#:
#: The first version anchored at `$`, so only a bare path on a line by itself matched.
#: Every plan in a real registry annotates — `- \`api/internal/x.go\` — add the error
#: branch`, `(new)`, `: the discard` — and an annotated list parsed as ZERO declared
#: files, which raised HIGH `no_declared_scope` against a plan that declares its scope
#: precisely. Measured on a consumer 2026-09-15: three phases of one plan, all of them
#: correct. A gate that reports correct work as a defect spends the reviewer's attention
#: and returns nothing.
#:
#: The path must still be the FIRST thing on the bullet: a sentence that happens to
#: mention a filename declares nothing.
FILE_LINE_RE = re.compile(
    r"^[\-*\s]*`?([^\s`]+\.[a-zA-Z0-9]+)`?(?:\s*[—\-:(].*)?\s*$", re.MULTILINE)

# Files that are ALWAYS allowed to be touched (cross-cutting, low risk).
NON_SOURCE_PATHS = (
    "CHANGELOG.md", "README.md", ".gitignore", ".gitattributes",
    "package.json", "package-lock.json", "go.mod", "go.sum",
    "Cargo.toml", "Cargo.lock", "pyproject.toml", "requirements.txt",
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class DiffCohesionReport:
    phase: str
    declared_files: tuple[str, ...]
    modified_files: tuple[str, ...]
    drift_files: tuple[str, ...]     # in modified but NOT in declared (excluding NON_SOURCE)
    diff_source: str                  # "git" | "progress" | "none"
    cross_layer_checked: bool
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def has_high_or_blocker(self) -> bool:
        return any(f.severity in ("HIGH", "BLOCKER") for f in self.findings)


def _extract_task_blocks(content: str) -> list[tuple[str, str]]:
    """Return list of (task_id, body) — body stops at next task/H2."""
    matches = list(TASK_HEADER_RE.finditer(content))
    blocks: list[tuple[str, str]] = []
    for m in matches:
        tid = m.group(1)
        start = m.end()
        nxt = NEXT_TASK_OR_H2_RE.search(content, pos=start)
        end = nxt.start() if nxt else len(content)
        blocks.append((tid, content[start:end]))
    return blocks


def _phase_of(task_id: str) -> str:
    # T<N>.<M> → "<N>"
    match = re.match(r"T(\d+)\.\d+", task_id)
    return match.group(1) if match else ""


#: A task DECLARING that it edits nothing. `None.`, `(none)`, `_none_` — the ways a plan
#: says the section is empty on purpose.
#:
#: An explicit none and an absent section are different statements, and reading them
#: alike is the same defect as the deps-audit `(none)` that discarded a whole section.
#: Measured on a consumer 2026-09-15: a verification phase whose task says `None.` drew
#: HIGH `no_declared_scope` — the gate demanding a declaration the task had already
#: made. Failing a task for declaring the truth teaches the next author to list a file
#: they did not touch, which is the workaround that kills gates.
#: The declaration may carry its REASON on the same line — "None. This task writes one
#: scratch artifact and no tracked file" — and a pattern anchored at `$` reads that as
#: prose rather than as the declaration it is. The none must OPEN the section; what
#: follows it is the author explaining, which is the behaviour to encourage.
_EXPLICIT_NO_FILES_RE = re.compile(
    r"^\s*(?:\(?\s*none\s*\)?|_none_|n/?a)\b[\s.,;:—-]*", re.IGNORECASE)


def _phase_declares_no_files(plan_path: Path, phase: str) -> bool:
    """True when every task in the phase has a `Files to edit` section saying "none"."""
    content = plan_path.read_text(encoding="utf-8-sig")
    saw_section = False
    for tid, body in _extract_task_blocks(content):
        if _phase_of(tid) != str(phase):
            continue
        block = FILES_TO_EDIT_RE.search(body)
        if block is None:
            return False
        saw_section = True
        if not _EXPLICIT_NO_FILES_RE.search(block.group(1) or ""):
            return False
    return saw_section


def _declared_files_for_phase(plan_path: Path, phase: str) -> set[str]:
    content = plan_path.read_text(encoding="utf-8-sig")
    declared: set[str] = set()
    for tid, body in _extract_task_blocks(content):
        if _phase_of(tid) != str(phase):
            continue
        files_block = FILES_TO_EDIT_RE.search(body)
        if not files_block:
            continue
        for line in files_block.group(1).splitlines():
            match = FILE_LINE_RE.match(line)
            if match:
                declared.add(match.group(1).strip())
    return declared


def _modified_files_via_progress(progress_path: Path, phase: str) -> set[str]:
    data = json.loads(progress_path.read_text(encoding="utf-8-sig"))
    modified: set[str] = set()
    for task in data.get("tasks", []):
        if str(task.get("phase")) != str(phase):
            continue
        for f in task.get("files", []):
            modified.add(f.strip())
    return modified


def _modified_files_via_git(progress_path: Path, phase: str, repo_root: Path) -> set[str] | None:
    """Use git log to list files modified in the phase. Returns None on failure."""
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None
    phase_tasks = [t for t in data.get("tasks", []) if str(t.get("phase")) == str(phase)]
    shas = [t.get("commit_sha") for t in phase_tasks if t.get("commit_sha")]
    if not shas:
        return None
    try:
        cmd = ["git", "-C", str(repo_root), "show", "--name-only", "--pretty=format:"] + shas
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def check_diff_cohesion(
    plan_path: Path,
    progress_path: Path,
    phase: str,
    repo_root: Path | None = None,
) -> DiffCohesionReport:
    declared = _declared_files_for_phase(plan_path, phase)

    diff_source = "none"
    modified: set[str] = set()
    if repo_root is not None:
        git_files = _modified_files_via_git(progress_path, phase, repo_root)
        if git_files is not None:
            modified = git_files
            diff_source = "git"
    if not modified:
        modified = _modified_files_via_progress(progress_path, phase)
        if modified:
            diff_source = "progress"

    findings: list[Finding] = []

    # B-038 — a phase that declared NOTHING used to get the verdict a fully-declared phase gets.
    #
    # The old comment here said: "we cannot distinguish drift from everything-is-undeclared in that
    # state." True, and the wrong conclusion. Not being able to distinguish them is precisely the
    # condition under which a check must REFUSE TO ANSWER — "cannot check" is not "checked, and
    # fine". `cycle-acceptance.md` draws the same line between NOT_VALIDATED and ACCEPTED, and
    # `coverage_gate.py` reports WARN rather than PASS for a report it could not parse.
    #
    # Measured cost of the old behaviour: the b033 phase-2 mini review of 2026-08-18 reported
    # declared_files 0, modified_files 14, drift_files 0 — verdict PHASE_REVIEW_PASS. The same check
    # flagged four files on b025 phase 1, one on phase 3, two on b020 and one on b034, correctly and
    # each needing a fix. So declaring some files bought scrutiny and declaring none bought a pass.
    #
    # HIGH only when the phase actually MODIFIED something: a phase that declared nothing and changed
    # nothing is a documentation phase, there is nothing that could have drifted, and failing it
    # would teach people to declare a file they did not touch — the workaround that kills gates.
    if not declared and _phase_declares_no_files(plan_path, phase):
        # The phase SAID it edits nothing. If it then modified something, that is drift
        # measured against a real declaration — the strongest form this check has, not
        # the weakest. If it modified nothing, the declaration held.
        # The cross-cutting exemption applies on THIS path too. A phase that declares no
        # source file and writes only its CHANGELOG entry has not drifted — it has done
        # what `Unbreakable Rule 6` requires of every phase. Measured on a consumer
        # 2026-09-15: the sole modified file of the phase this fired on was
        # `CHANGELOG.md`, already on the always-allowed list four lines below.
        drift = {
            f for f in modified
            if Path(f).name not in NON_SOURCE_PATHS and f not in NON_SOURCE_PATHS
        }
        if drift:
            findings.append(Finding(
                severity="HIGH",
                code="scope_drift",
                message=(
                    f"Phase {phase} declares `#### Files to edit: none` and modified "
                    f"{len(drift)} source file(s): {', '.join(sorted(drift)[:5])}. The "
                    f"declaration and the diff disagree."
                ),
            ))
    elif not declared:
        sample = ", ".join(sorted(modified)[:5])
        findings.append(Finding(
            severity="HIGH" if modified else "MEDIUM",
            code="no_declared_scope",
            message=(
                f"Phase {phase} tasks did not declare `#### Files to edit` sections, so scope drift "
                f"CANNOT be checked for the {len(modified)} file(s) it modified"
                + (f" (first 5: {sample})" if modified else "")
                + ". Declare them, or record why they are out of scope."
            ),
        ))
        drift: set[str] = set()
    else:
        drift = {
            f for f in modified
            if f not in declared
            and Path(f).name not in NON_SOURCE_PATHS
            and f not in NON_SOURCE_PATHS
        }
        if drift:
            sample = ", ".join(sorted(drift)[:5])
            findings.append(Finding(
                severity="HIGH",
                code="scope_drift",
                message=(
                    f"Phase {phase}: {len(drift)} file(s) modified that were NOT in any task's "
                    f"`Files to edit` declaration: {sample}. Opportunistic edits violate plan scope."
                ),
            ))

    # The OTHER half of scope drift, and the half five adversarial cases missed: every
    # one of them was about touching something undeclared, none about declaring
    # something untouched. A plan that declares five files and edits two has a scope
    # claim that is wrong, and a wrong claim with a right conclusion is the hardest kind
    # to catch — the consumer session found this by mutating a plan to declare a file the
    # phase never touched and getting no finding at all.
    #
    # MEDIUM rather than HIGH: nothing unreviewed reached the tree. What is wrong is the
    # declaration, and a phase legitimately splits work across commits, so this is only
    # judged where the diff was actually readable.
    if declared and diff_source != "none":
        undelivered = {
            f for f in declared
            if f not in modified
            and Path(f).name not in NON_SOURCE_PATHS and f not in NON_SOURCE_PATHS
        }
        if undelivered:
            findings.append(Finding(
                severity="MEDIUM",
                code="declared_but_untouched",
                message=(
                    f"Phase {phase} declares {len(undelivered)} file(s) it never modified: "
                    f"{', '.join(sorted(undelivered)[:5])}. Either the work is unfinished "
                    f"or the declaration is wider than the change."
                ),
            ))

    # A phase that DECLARED it edits nothing and edited nothing is complete, not
    # inconclusive. Reading it as inconclusive is the third instance in one consumer item
    # of the same shape — `None.` in `Files to edit`, `committed` with no SHA, and this:
    # an honest statement of nothing with no state to hold it.
    if diff_source == "none" and _phase_declares_no_files(plan_path, phase) and not modified:
        findings.append(Finding(
            severity="INFO",
            code="declared_and_delivered_no_files",
            message=(
                f"Phase {phase} declares it edits no tracked file and modified none. "
                f"The declaration held; there is nothing to check and nothing missing."
            ),
        ))
    elif diff_source == "none":
        findings.append(Finding(
            severity="MEDIUM",
            code="no_diff_source",
            message=(
                "Neither git history nor progress file had usable file lists for this phase. "
                "Cohesion check could not run; treat as inconclusive."
            ),
        ))

    # NOT IMPLEMENTED, and said on every run rather than conditionally. The docstring
    # used to advertise this as a finding class gated on `rules/architecture.md`; the
    # condition is not evaluated anywhere, so the INFO below is the whole behaviour.
    findings.append(Finding(
        severity="INFO",
        code="cross_layer_check_skipped",
        message=(
            "Cross-layer cohesion detection requires per-project layer config in "
            "rules/architecture.md. Skipped — implement when project declares its layers."
        ),
    ))

    return DiffCohesionReport(
        phase=str(phase),
        declared_files=tuple(sorted(declared)),
        modified_files=tuple(sorted(modified)),
        drift_files=tuple(sorted(drift)),
        diff_source=diff_source,
        cross_layer_checked=False,
        findings=tuple(findings),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--repo-root", type=Path, default=None, help="Override git repo root (default: cwd)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.plan.exists():
        print(f"plan file not found: {args.plan}", file=sys.stderr)
        return 2
    if not args.progress.exists():
        print(f"progress file not found: {args.progress}", file=sys.stderr)
        return 2

    repo_root = args.repo_root or Path.cwd()
    report = check_diff_cohesion(args.plan, args.progress, args.phase, repo_root)

    if args.json:
        out = {
            "phase": report.phase,
            "declared_files_count": len(report.declared_files),
            "modified_files_count": len(report.modified_files),
            "drift_files": list(report.drift_files),
            "diff_source": report.diff_source,
            "cross_layer_checked": report.cross_layer_checked,
            "findings": [{"severity": f.severity, "code": f.code, "message": f.message} for f in report.findings],
            "has_high_or_blocker": report.has_high_or_blocker,
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"Phase {report.phase}: declared={len(report.declared_files)}, "
              f"modified={len(report.modified_files)}, drift={len(report.drift_files)}, "
              f"source={report.diff_source}")
        for f in report.findings:
            print(f"  [{f.severity}] {f.code}: {f.message}")

    return 1 if report.has_high_or_blocker else 0


if __name__ == "__main__":
    sys.exit(main())

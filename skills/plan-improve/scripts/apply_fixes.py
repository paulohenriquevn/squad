"""apply_fixes.py — deterministic fixes that improve a plan's M2 score.

Three fix categories (all SAFE, deterministic):

1. **weak_imperatives**: should/could/may/might -> must
2. **loopholes**: 'if possible' / 'when applicable' / 'where feasible' / 'as appropriate' -> removed
3. **tdd_template**: bug-fix tasks without #### TDD block -> inject standard template

ALL fixes:
- Skip content inside fenced code blocks (```...```).
- Skip task header lines (### T\\d+\\.\\d+).
- Are idempotent (running twice = no second change).

A 4th category, ADR alternatives, is INTENTIONALLY out of scope here —
that requires semantic understanding and is handled by the LLM inside the
ralph-loop iteration. apply_fixes covers the deterministic 80%.

Usage:
    python3 apply_fixes.py <plan-path>             # apply all fixes
    python3 apply_fixes.py <plan-path> --dry-run   # report without modifying
    python3 apply_fixes.py <plan-path> --json      # JSON output for tooling
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

WEAK_IMPERATIVE_PATTERNS: list[tuple[str, str]] = [
    (r"\bshould\b", "must"),
    (r"\bShould\b", "Must"),
    (r"\bcould\b", "must"),
    (r"\bCould\b", "Must"),
    (r"\bmay\b", "must"),
    (r"\bMay\b", "Must"),
    (r"\bmight\b", "must"),
    (r"\bMight\b", "Must"),
]

LOOPHOLE_PHRASES: list[str] = [
    # longest first to avoid partial replacements
    "where feasible",
    "when applicable",
    "as appropriate",
    "if possible",
]

TASK_HEADER_RE = re.compile(r"^###\s+T\d+\.\d+\b")

#: Sections whose CONTENT is modality. Rewriting `may` to `must` inside them inverts
#: what they say: a risk is something that MAY happen and an unresolved question is
#: something that MIGHT be, so "the cache may go stale" became "the cache must go
#: stale" — a drawback rewritten into a promise, by a fix the module calls "SAFE,
#: deterministic". Deterministic it is; meaning-preserving it is not.
#:
#: The plan template mandates both (`check_drawbacks_section.py` enforces them), so
#: every plan the fix runs over has them.
MODALITY_SECTIONS = ("drawbacks", "risks", "unresolved questions", "open questions",
                     "trade-offs", "tradeoffs", "prior art", "alternatives considered")

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")


def _in_modality_section(line: str, current: str | None) -> str | None:
    """The section this line is in, tracked heading by heading.

    Returns the lowered heading when it is one whose content is modality, and None
    otherwise — so the caller can leave those lines alone.
    """
    heading = _HEADING_RE.match(line)
    if heading is None:
        return current
    title = heading.group(2).lower()
    return title if any(name in title for name in MODALITY_SECTIONS) else None
TASK_HEADER_FULL_RE = re.compile(r"^###\s+(T\d+\.\d+)\s*[—\-–:]\s*(.+)$")
BUGFIX_KEYWORDS = (
    "bug-fix", "bug fix", "bugfix", "regression", "fix a bug", "fix the bug",
    "resolve a bug", "fix bug", "parser bug",
)

TDD_TEMPLATE = """#### TDD

```
RED:     test_describes_the_bug() — failing test that reproduces the bug
RED:     test_describes_the_fix() — assertion about expected behavior after fix
GREEN:   Implement the minimal change to make RED tests pass
REFACTOR: Clean up if needed (or "None expected")
VERIFY:  pytest tests/ -v
```
"""


@dataclass
class FixReport:
    category: str
    changes_proposed: int = 0
    changes_applied: int = 0
    locations: list[str] = field(default_factory=list)


@dataclass
class TotalReport:
    per_category: list[FixReport] = field(default_factory=list)
    total_changes_proposed: int = 0
    total_changes_applied: int = 0


# ---------------------------------------------------------------------------
# Code-block awareness
# ---------------------------------------------------------------------------

def _split_with_state(content: str) -> list[tuple[str, bool]]:
    """Return list of (line, in_code_block) tuples."""
    lines = content.splitlines(keepends=True)
    out: list[tuple[str, bool]] = []
    fence_count = 0
    for line in lines:
        is_fence = line.lstrip().startswith("```")
        currently_in = (fence_count % 2) == 1
        out.append((line, currently_in))
        if is_fence:
            fence_count += 1
    return out


# ---------------------------------------------------------------------------
# Fix 1: weak imperatives
# ---------------------------------------------------------------------------

def _is_fence_line(line: str) -> bool:
    """Detect if line is a code fence (``` or indented ```)."""
    return line.lstrip().startswith("```")


_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _sub_outside_inline_code(
    line: str, apply: Callable[[str], tuple[str, int]]
) -> tuple[str, int]:
    """Run `apply` on the prose parts of a line, never on inline `code` spans.

    The fenced-block guard above protects ``` blocks; this protects the backticked
    token in the middle of a sentence. Rewriting `should` inside backticks changes
    what the plan claims the code contains — a flag name, a field, a literal.

    This replaced a mask/restore pair that was written for the job and never called.
    Masking cannot work here: the substitutions change the line's length ("should" is
    six characters, "must" is four), so the absolute span positions the restore step
    would need are stale by the time it runs. Splitting on the spans and rejoining
    needs no positions at all.

    Returns the rebuilt line and the number of substitutions made in prose only, so a
    change that was not made is never reported as made.
    """
    parts: list[str] = []
    total = 0
    last = 0
    for match in _INLINE_CODE_RE.finditer(line):
        text, count = apply(line[last:match.start()])
        parts.append(text)
        total += count
        parts.append(match.group(0))
        last = match.end()
    text, count = apply(line[last:])
    parts.append(text)
    return "".join(parts), total + count


def _rewrite_lines(plan_path: Path, category: str, *, skip_task_headers: bool,
                   rewrite, tidy) -> FixReport:
    """Walk the plan line by line, rewrite what is not code, and write once.

    `fix_weak_imperatives` and `fix_loopholes` were this loop written twice: split with
    fence state, skip fenced and fence lines, walk a phrase table through
    `_sub_outside_inline_code`, count into the same three report fields, re-normalise
    leading whitespace, join, honour `dry_run`, write only if changed. Twenty-five lines
    each, diverging in exactly two places — which table is walked, and whether the
    whitespace pass also closes the gap before punctuation.

    Those two places are the arguments. `rewrite(modified, report, line_no)` returns
    `(text, changes)`; `tidy(rest)` returns the tidied remainder of a changed line.
    """
    report = FixReport(category=category)
    content = plan_path.read_text(encoding="utf-8")

    new_lines: list[str] = []
    for line_no, (line, in_code) in enumerate(_split_with_state(content), start=1):
        if in_code or _is_fence_line(line) or (skip_task_headers
                                               and TASK_HEADER_RE.match(line)):
            new_lines.append(line)
            continue
        modified, line_changes = rewrite(line, report, line_no)
        # Only normalise whitespace if THIS LINE was modified — touching an untouched
        # line would reflow indented prose and lists that triggered no pattern.
        if line_changes > 0:
            leading_match = re.match(r"^(\s*)", modified)
            leading = leading_match.group(1) if leading_match else ""
            modified = leading + tidy(modified[len(leading):])
        new_lines.append(modified)

    new_content = "".join(new_lines)
    return report, new_content


def _commit(plan_path: Path, report: FixReport, new_content: str,
            dry_run: bool) -> FixReport:
    """Write the rewritten plan, unless this is a dry run. One writer for both fixes."""
    if dry_run:
        return report
    if new_content != plan_path.read_text(encoding="utf-8"):
        plan_path.write_text(new_content, encoding="utf-8")
        report.changes_applied = report.changes_proposed
    return report


def fix_weak_imperatives(plan_path: Path, dry_run: bool = False) -> FixReport:
    section: list[str | None] = [None]

    def rewrite(line: str, report: FixReport, line_no: int) -> tuple[str, int]:
        section[0] = _in_modality_section(line, section[0])
        if section[0] is not None:
            # Inside a section whose subject IS modality. `may` there is the content.
            return line, 0
        modified, line_changes = line, 0
        for pattern, replacement in WEAK_IMPERATIVE_PATTERNS:
            new_modified, count = _sub_outside_inline_code(
                modified, lambda seg, p=pattern, r=replacement: re.subn(p, r, seg))
            if count > 0:
                report.changes_proposed += count
                line_changes += count
                report.locations.append(
                    f"L{line_no}: {pattern} -> {replacement} (x{count})")
                modified = new_modified
        return modified, line_changes

    def tidy(rest: str) -> str:
        # Through `_sub_outside_inline_code`, so a double space inside a code span
        # survives — it may be significant there and is not prose.
        tidied, _ = _sub_outside_inline_code(rest, lambda seg: re.subn(r"  +", " ", seg))
        return tidied

    report, new_content = _rewrite_lines(
        plan_path, "weak_imperatives", skip_task_headers=True,
        rewrite=rewrite, tidy=tidy)
    return _commit(plan_path, report, new_content, dry_run)


def fix_loopholes(plan_path: Path, dry_run: bool = False) -> FixReport:
    def rewrite(line: str, report: FixReport, line_no: int) -> tuple[str, int]:
        modified, line_changes = line, 0
        for phrase in LOOPHOLE_PHRASES:
            pattern = re.compile(rf"\s*\b{re.escape(phrase)}\b", flags=re.IGNORECASE)
            new_modified, count = _sub_outside_inline_code(
                modified, lambda seg, p=pattern: p.subn("", seg))
            if count > 0:
                report.changes_proposed += count
                line_changes += count
                report.locations.append(f"L{line_no}: removed '{phrase}' (x{count})")
                modified = new_modified
        return modified, line_changes

    def tidy(rest: str) -> str:
        # Removing a phrase leaves a gap before punctuation as well as a double space,
        # which is the one way this fix's tidying differs from the other's.
        rest = re.sub(r"  +", " ", rest)
        return re.sub(r" +([.,;:])", r"\1", rest)

    report, new_content = _rewrite_lines(
        plan_path, "loopholes", skip_task_headers=False,
        rewrite=rewrite, tidy=tidy)
    return _commit(plan_path, report, new_content, dry_run)


# ---------------------------------------------------------------------------
# Fix 3: TDD template injection
# ---------------------------------------------------------------------------

def _is_bugfix_title(title: str) -> bool:
    low = title.lower()
    return any(kw in low for kw in BUGFIX_KEYWORDS)


def _find_task_blocks(content: str) -> list[tuple[int, int, str, str]]:
    """Return list of (start_line, end_line, task_id, task_title) for each `### T-id` task.

    Lines are 0-indexed; end_line is EXCLUSIVE.
    """
    lines = content.splitlines(keepends=True)
    headers: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        m = TASK_HEADER_FULL_RE.match(line)
        if m:
            headers.append((i, m.group(1), m.group(2).strip()))

    blocks: list[tuple[int, int, str, str]] = []
    for idx, (start, tid, title) in enumerate(headers):
        end = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        # Also stop at next H2 within the task block
        for j in range(start + 1, end):
            if lines[j].startswith("## "):
                end = j
                break
        blocks.append((start, end, tid, title))
    return blocks


def fix_tdd_template(plan_path: Path, dry_run: bool = False) -> FixReport:
    report = FixReport(category="tdd_template")
    content = plan_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    blocks = _find_task_blocks(content)

    # Process tasks in reverse so insertion indices stay valid.
    insertions: list[tuple[int, str]] = []
    for start, end, tid, title in reversed(blocks):
        body = "".join(lines[start:end])
        if not _is_bugfix_title(title):
            continue
        if "#### TDD" in body:
            continue
        # Find anchor for insertion: just before #### Acceptance Criteria,
        # or #### DoD, or end of block.
        insert_at = end
        for j in range(start + 1, end):
            stripped = lines[j].lstrip()
            if stripped.startswith(("#### Acceptance Criteria", "#### DoD")):
                insert_at = j
                break
        report.changes_proposed += 1
        report.locations.append(f"L{start + 1}-{end}: {tid} (bug-fix without TDD)")
        # Insert template with a trailing blank line so the next section
        # doesn't lose its leading blank.
        block_to_insert = TDD_TEMPLATE + "\n"
        insertions.append((insert_at, block_to_insert))

    if dry_run or not insertions:
        if dry_run:
            return report
        return report

    # Apply insertions in reverse order
    for at, block_text in insertions:
        lines.insert(at, block_text)
    new_content = "".join(lines)
    if new_content != content:
        plan_path.write_text(new_content, encoding="utf-8")
        report.changes_applied = report.changes_proposed
    return report


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def apply_all_fixes(plan_path: Path, dry_run: bool = False) -> TotalReport:
    total = TotalReport()
    for fn in (fix_weak_imperatives, fix_loopholes, fix_tdd_template):
        r = fn(plan_path, dry_run=dry_run)
        total.per_category.append(r)
        total.total_changes_proposed += r.changes_proposed
        total.total_changes_applied += r.changes_applied
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply deterministic plan-improve fixes.")
    parser.add_argument("plan", help="path to plan .md")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"ERROR: plan not found: {plan_path}", file=sys.stderr)
        return 2

    report = apply_all_fixes(plan_path, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        for r in report.per_category:
            verb = "would change" if args.dry_run else "changed"
            print(f"[{r.category}] {verb} {r.changes_applied if not args.dry_run else r.changes_proposed} item(s)")
            for loc in r.locations:
                print(f"  {loc}")
        total_n = report.total_changes_applied if not args.dry_run else report.total_changes_proposed
        print(f"\nTotal: {total_n} change(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

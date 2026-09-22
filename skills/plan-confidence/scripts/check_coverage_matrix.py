"""Coverage Matrix structural check for /plan-write plans (M2 deterministic).

Parses a plan .md file, extracts the `## Coverage Matrix` section,
counts mapped gaps and detects orphan task references in the body.

v1.1 EC-4 fix: orphan detection EXCLUDES task definition headers
(lines matching `^###\\s+T\\d+\\.\\d+`) — otherwise every task header
would be counted as a "mention" and produce false orphans.

v1.1 EC-8 fix: uses `encoding='utf-8-sig'` to tolerate UTF-8 BOM.
"""
from __future__ import annotations

import re
import sys as _sys
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "markdown.py").is_file():
        _sys.path.insert(0, str(_up))
        break
from squad.markdown import (  # noqa: E402 — post-bootstrap import
    FENCED_CODE_RE as _FENCED_CODE_OWNER,  # noqa: E402 — post-bootstrap import
)

TASK_ID_RE = re.compile(r"T\d+\.\d+")
TASK_HEADER_RE = re.compile(r"^###\s+T\d+\.\d+", re.MULTILINE)
COVERAGE_HEADER_RE = re.compile(r"^##\s+Coverage Matrix\s*$", re.MULTILINE)
#: The Final Phase closes requirements that no numbered task does — it validates the whole
#: of the work end to end, and five plans cite it in the Task column by name. It has no
#: `T<n>.<n>` id in any plan, so those rows counted as requirements nothing closed: eleven
#: of nineteen such rows had this cause rather than an authoring one.
#:
#: THE NAME IS ACCEPTED; NO ID IS CREATED. Giving the Final Phase a task id would make it a
#: task to every other reader of that pattern — `check_tdd_in_bugfix.py` matches
#: `### T<n>.<n>` headings and demands a RED-test shape per bugfix task,
#: `check_concurrency_tests.py` reads the same shape. Forcing a RED test onto a phase that
#: validates work already done satisfies a regex and describes nothing. One id would have
#: propagated a requirement through three gates to fix a citation in one.
FINAL_PHASE_CITATION_RE = re.compile(r"final\s+phase", re.IGNORECASE)
FINAL_PHASE_SECTION_RE = re.compile(r"^##\s+Final Phase\b", re.IGNORECASE | re.MULTILINE)
NEXT_H2_RE = re.compile(r"^##\s+", re.MULTILINE)
#: The ONE fenced-code regex, from `squad.markdown`. Eleven scripts each defined
#: their own, in two forms that do not mask the same input: five saw only backtick
#: fences, six also saw `~~~`. A plan whose example block used tildes was masked by
#: six readers and read as prose by the other five, so the same document scored
#: differently depending on which checker asked.
FENCED_CODE_RE = _FENCED_CODE_OWNER
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


#: The header names that mean "which task closes this". The template declares
#: `Task(s)`; `Closed by` is what plans in the wild wrote instead. Matched
#: case-insensitively after stripping, and deliberately a SHORT list: every name added
#: here is a shape the template does not declare, and the point is to read the plans that
#: exist, not to make the template optional.
TASK_COLUMN_HEADERS = ("task(s)", "tasks", "task", "closed by", "closed-by")

#: The column that identifies WHICH gap a row is about. Everything that is neither this
#: nor the task column is extra and ignored — `Resolution`, `Verified by`, `Severidade`.
GAP_COLUMN_HEADERS = ("gap / requirement", "gap/requirement", "gap", "requirement",
                      "requirements", "gap / req")

OUT_OF_SCOPE_PATTERNS = (
    "out-of-scope",
    "out of scope",
    "deferred",
    "n/a — d",  # "N/A — D9" pattern
    "n/a -- d",
    "(d",  # "(out-of-scope D9)" or "(D9)" — caught after substring "out-of-scope"
)


def _is_out_of_scope_marker(task_col: str) -> bool:
    """Detect whether a row's task column signals deliberate deferral.

    v1.1+ #2 fix: 'N/A — D9 out-of-scope', '(out-of-scope D5)', 'DEFERRED to v2'
    etc. are not 'missed' gaps; they are explicit deferrals.
    """
    col_lower = task_col.lower()
    return any(pattern in col_lower for pattern in OUT_OF_SCOPE_PATTERNS)


@dataclass(frozen=True)
class CoverageReport:
    """Structural report for a plan's Coverage Matrix."""

    total_gaps: int
    mapped_gaps: int
    deferred_gaps: int = 0  # v1.1+ #2 fix: explicitly out-of-scope, not missed
    unmapped_gaps: tuple[str, ...] = field(default_factory=tuple)
    orphan_tasks: tuple[str, ...] = field(default_factory=tuple)
    coverage_ratio: float = 0.0
    is_complete: bool = False
    #: The header cells as written, and whether a task column was found among them.
    #: `_parse_matrix_rows` used to read `cells[2:]` by POSITION and drop any row with
    #: fewer than four cells, so a two-column matrix produced zero rows — which is
    #: byte-identical to a matrix nobody wrote. Nine plans of twelve were INVALID for
    #: that reason and the report said `gaps: 0`. Unreadable and empty are two answers.
    header: tuple[str, ...] = field(default_factory=tuple)
    header_recognised: bool = True


def _read_plan(plan_path: Path) -> str:
    """Read plan with UTF-8 BOM tolerance (EC-8 fix)."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan file not found: {plan_path}")
    # utf-8-sig auto-strips BOM if present.
    return plan_path.read_text(encoding="utf-8-sig")


def _extract_coverage_section(content: str) -> str:
    """Extract text between '## Coverage Matrix' and next H2."""
    header_match = COVERAGE_HEADER_RE.search(content)
    if header_match is None:
        raise ValueError("No '## Coverage Matrix' section found in plan")
    start = header_match.end()
    # Find next H2 after our header
    next_h2 = NEXT_H2_RE.search(content, pos=start)
    end = next_h2.start() if next_h2 else len(content)
    return content[start:end]


def _is_data_row(stripped: str) -> bool:
    """Validate row starts/ends with | and isn't a separator."""
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return False
    inner = stripped[1:-1]
    return not bool(re.match(r"^[\s\-:|]+$", inner))


def _cells(stripped: str) -> list[str]:
    return [c.strip() for c in stripped[1:-1].split("|")]


def _parse_header(section: str) -> tuple[str, ...]:
    """The first table row in the section — the header, by markdown's own rule."""
    for line in section.splitlines():
        stripped = line.strip()
        if _is_data_row(stripped):
            return tuple(_cells(stripped))
    return ()


def _column_index(header: tuple[str, ...], names: tuple[str, ...]) -> int | None:
    for i, cell in enumerate(header):
        if cell.lower().strip() in names:
            return i
    return None


def _parse_matrix_rows(
    section: str, header: tuple[str, ...],
) -> tuple[list[tuple[str, str, str]], bool]:
    """Rows as (gap_id, gap_desc, task_col), and whether the header was recognised.

    BY NAME, not by position. The previous reader took the task from `cells[2:]` and
    skipped any row with fewer than four cells, which meant a plan that wrote two columns
    parsed to nothing and reported as a plan with no gaps. Measured across twelve plans:
    seven wrote two columns, two wrote `Requirement | Closed by | Verified by` with the
    task in `cells[1]`, and all nine came back INVALID under `coverage_lt_100` — a true
    statement about a table nobody had read.

    Reading by name was chosen over refusing a non-conforming header at authoring time.
    A refusal helps the next plan and none of the nine; those would all still be INVALID,
    for a reason still unstated. The template remains the declared shape — what changed is
    that the parser stopped depending on column POSITION to find a column it can name.
    """
    task_idx = _column_index(header, TASK_COLUMN_HEADERS)
    if task_idx is None:
        return [], False
    gap_idx = _column_index(header, GAP_COLUMN_HEADERS)
    if gap_idx is None:
        # No named gap column: the first cell that is neither the counter nor the task.
        gap_idx = next(
            (i for i in range(len(header))
             if i != task_idx and header[i].strip() != "#"),
            0,
        )
    numbered = bool(header) and header[0].strip() == "#"

    rows: list[tuple[str, str, str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not _is_data_row(stripped):
            continue
        cells = _cells(stripped)
        if tuple(cells) == header or len(cells) <= task_idx:
            continue
        gap_desc = cells[gap_idx] if gap_idx < len(cells) else ""
        gap_id = cells[0] if numbered else gap_desc
        rows.append((gap_id, gap_desc, cells[task_idx]))
    return rows, True


def _strip_code(content: str) -> str:
    """Remove fenced code blocks and inline code so they don't pollute prose scans.

    v1.1 EC-9 follow-up: task IDs and smells inside ```code``` or `inline` are
    examples/documentation, not real references. Replace with whitespace to
    preserve line numbers (important for downstream line-aware reports).
    """
    # Replace each block with whitespace of equal length (preserve newlines).
    def blank_keeping_lines(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    no_fenced = FENCED_CODE_RE.sub(blank_keeping_lines, content)
    no_inline = INLINE_CODE_RE.sub(blank_keeping_lines, no_fenced)
    return no_inline


def _find_orphan_references(content: str, matrix_task_ids: set[str]) -> list[str]:
    """Find T{N}.{M} references in body that are TRULY orphan.

    A task ID is orphan iff:
      1. It is mentioned in PROSE (excluding fenced code blocks).
      2. It is NOT in the Coverage Matrix.
      3. It does NOT have a '### T{N}.{M}' header definition somewhere in the plan.

    v1.1 EC-4 fix: headers like '### T1.1 — Title' are definitions, not references.
    v1.1 EC-9 follow-up: code blocks contain examples (test names), not real refs.
    v1.1+ relaxation: tasks defined as `### T-id` headers are LEGITIMATE plan tasks
    even if not in the matrix (e.g., wrap-up/honesty-gate-phase tasks). Only "mentions
    in prose with no definition" are true orphans (typos, refs to non-existent tasks).
    """
    prose_only = _strip_code(content)

    defined_ids: set[str] = set()
    header_lines: set[int] = set()
    for match in TASK_HEADER_RE.finditer(content):
        line_no = content[: match.start()].count("\n")
        header_lines.add(line_no)
        # Extract the T-id from the header line for the defined set.
        header_line_text = content.splitlines()[line_no]
        for tid_match in TASK_ID_RE.finditer(header_line_text):
            defined_ids.add(tid_match.group(0))

    mentions: set[str] = set()
    for line_no, line in enumerate(prose_only.splitlines()):
        if line_no in header_lines:
            continue
        for match in TASK_ID_RE.finditer(line):
            mentions.add(match.group(0))

    # Orphans = mentioned in prose, NOT in matrix, NOT defined as header.
    return sorted(mentions - matrix_task_ids - defined_ids)


def check_coverage_matrix(plan_path: Path) -> CoverageReport:
    """Parse plan and produce a CoverageReport.

    Raises:
        FileNotFoundError: if plan_path doesn't exist.
        ValueError: if no '## Coverage Matrix' section is found.
    """
    content = _read_plan(plan_path)
    section = _extract_coverage_section(content)
    header = _parse_header(section)
    rows, header_recognised = _parse_matrix_rows(section, header)

    total_gaps = len(rows)
    mapped_gaps = 0
    deferred_gaps = 0
    unmapped: list[str] = []
    matrix_task_ids: set[str] = set()

    # Checked once, not per row: whether the plan HAS the section its rows cite. A row may
    # close a requirement against the Final Phase only if there is one — otherwise the
    # citation is a dead pointer, which is what this kit refuses everywhere else.
    has_final_phase = bool(FINAL_PHASE_SECTION_RE.search(content))

    for gap_id, gap_desc, task_col in rows:
        task_refs = TASK_ID_RE.findall(task_col)
        if task_refs:
            mapped_gaps += 1
            matrix_task_ids.update(task_refs)
        elif has_final_phase and FINAL_PHASE_CITATION_RE.search(task_col):
            mapped_gaps += 1
        elif _is_out_of_scope_marker(task_col):
            # v1.1+ #2 fix: explicit deferral, not a miss
            deferred_gaps += 1
        else:
            unmapped.append(f"#{gap_id}: {gap_desc}")

    orphans = _find_orphan_references(content, matrix_task_ids)

    # Effective coverage = (mapped + deferred) / total
    effective_covered = mapped_gaps + deferred_gaps
    coverage_ratio = (
        (1.0 if not orphans else 0.0)
        if total_gaps == 0
        else effective_covered / total_gaps
    )

    # `is_complete` requires a matrix that PARSED. Zero gaps gave `coverage_ratio =
    # 1.0` — 100% of nothing — and that cleared `coverage_lt_100`, one of the two caps
    # that force INVALID. So a plan whose Coverage Matrix heading carried no readable
    # row scored better on coverage than one whose rows were readable and partly
    # unmapped. A heading with nothing under it is not a plan with no gaps; it is a
    # plan whose gaps nobody could read.
    is_complete = (coverage_ratio >= 1.0 and not orphans and total_gaps > 0
                   and header_recognised)

    return CoverageReport(
        total_gaps=total_gaps,
        mapped_gaps=mapped_gaps,
        deferred_gaps=deferred_gaps,
        unmapped_gaps=tuple(unmapped),
        orphan_tasks=tuple(orphans),
        coverage_ratio=coverage_ratio,
        is_complete=is_complete,
        header=header,
        header_recognised=header_recognised,
    )

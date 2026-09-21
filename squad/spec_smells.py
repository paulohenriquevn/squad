"""Spec-smell detection — one implementation, three callers.

Reads a rubric's smell categories (patterns + penalties) and scans an artifact for
matches with word-boundary regex, outside fenced and inline code. Returns a
`SmellReport` with hits, per-category counts and the total penalty.

WHY THIS IS HERE AND NOT IN A SKILL
===================================
`check_spec_smells.py` existed three times — `plan-confidence`, `discover-confidence`
and `discover-plan-confidence` — and each copy said so in its own header: *"Copy of
plan-confidence/scripts/check_spec_smells.py — same algorithm"*, *"Copy-with-attribution
… Same algorithm"*.

It was. Measured 2026-09-21 by comparing the three syntax trees with docstrings and
comments stripped: **89 lines of code, 4 of them different, and all four were the name
of one parameter** (`artifact_path` against `artifact_path`). Three copies of one algorithm
is three places for it to drift, and the drift would be silent — a smell fixed in one
scorer leaves the other two detecting the old shape.

The kit already learned this for `_rubric_loader.py`, which was byte-identical in the
same three skills and became `squad/rubric.py` with each copy reduced to a documented
re-export. This is that fix, one file along.

WHAT EACH CALLER STILL OWNS
===========================
The rubric. `plan-confidence` reads `rubric-v1.md`, `discover-confidence` reads
`rubric-opportunity.md`, `discover-plan-confidence` reads `rubric-measurement-plan.md`.
The categories, the patterns and the penalties are the skill's; only the scan is shared.

v1.1 EC-13 known limitation: English-only dictionaries.
"""
from __future__ import annotations

import re
import sys as _sys
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import Path as _P
from typing import Any

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "markdown.py").is_file():
        _sys.path.insert(0, str(_up))
        break
from squad.rubric import load_rubric  # noqa: E402 — post-bootstrap import
from squad.markdown import (  # noqa: E402 — post-bootstrap import
    FENCED_CODE_RE as _FENCED_CODE_OWNER,  # noqa: E402 — post-bootstrap import
)

CONTEXT_WINDOW = 20  # chars on each side of a match
#: The ONE fenced-code regex, from `squad.markdown`. Eleven scripts each defined
#: their own, in two forms that do not mask the same input: five saw only backtick
#: fences, six also saw `~~~`. A plan whose example block used tildes was masked by
#: six readers and read as prose by the other five, so the same document scored
#: differently depending on which checker asked.
FENCED_CODE_RE = _FENCED_CODE_OWNER
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _strip_code(content: str) -> str:
    """Remove code blocks (v1.1 EC-9 follow-up).

    Smells inside ```code``` or `inline` are typically examples or test names
    (e.g., 'RED: test_should_handle_empty'), not prose. Replace with whitespace
    of equal length to preserve line numbers.
    """
    def blank_keeping_lines(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    no_fenced = FENCED_CODE_RE.sub(blank_keeping_lines, content)
    no_inline = INLINE_CODE_RE.sub(blank_keeping_lines, no_fenced)
    return no_inline


@dataclass(frozen=True)
class SmellHit:
    category: str
    pattern_matched: str
    line: int
    context: str


@dataclass(frozen=True)
class SmellReport:
    total_hits: int
    by_category: dict[str, int] = field(default_factory=dict)
    hits: tuple[SmellHit, ...] = field(default_factory=tuple)
    total_penalty: int = 0


def _build_category_regex(spec: dict[str, Any]) -> re.Pattern[str]:
    """Build a compiled regex for one smell category."""
    pattern_type = spec.get("pattern_type")
    if pattern_type == "regex":
        return re.compile(spec["pattern"], re.IGNORECASE | re.UNICODE)
    if pattern_type == "dictionary":
        entries = spec.get("words") or spec.get("phrases") or []
        if not entries:
            return re.compile(r"$.^")  # match nothing
        # Sort by length desc so multi-word phrases match first.
        sorted_entries = sorted(entries, key=len, reverse=True)
        escaped = [re.escape(e) for e in sorted_entries]
        # Use word boundaries; multi-word phrases naturally include spaces.
        joined = "|".join(escaped)
        return re.compile(rf"(?<!\w)({joined})(?!\w)", re.IGNORECASE | re.UNICODE)
    raise ValueError(f"Unknown pattern_type: {pattern_type!r}")


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _context_around(text: str, start: int, end: int) -> str:
    ctx_start = max(0, start - CONTEXT_WINDOW)
    ctx_end = min(len(text), end + CONTEXT_WINDOW)
    snippet = text[ctx_start:ctx_end].replace("\n", " ")
    return snippet.strip()


def check_spec_smells(artifact_path: Path, rubric_path: Path) -> SmellReport:
    """Scan plan for smells defined in rubric. Returns SmellReport.

    v1.1 EC-9 follow-up: smells inside code blocks are skipped (examples, not prose).
    """
    raw = artifact_path.read_text(encoding="utf-8-sig")
    content = _strip_code(raw)
    rubric = load_rubric(rubric_path)
    smells_spec = rubric.get("smells", {})

    # Penalty weights live under node id=4 in the rubric.
    penalty_weights: dict[str, int] = {}
    for node in rubric.get("nodes", []):
        if node.get("detector") == "spec_smells":
            penalty_weights = node.get("penalty_weights", {})
            break

    hits: list[SmellHit] = []
    by_category: dict[str, int] = {}

    for category, spec in smells_spec.items():
        try:
            regex = _build_category_regex(spec)
        except (re.error, KeyError) as exc:
            # Malformed rubric entry — skip but record
            raise ValueError(f"Invalid pattern for {category}: {exc}") from exc

        for match in regex.finditer(content):
            matched_text = match.group(0)
            line_no = _line_of(content, match.start())
            ctx = _context_around(content, match.start(), match.end())
            hits.append(
                SmellHit(
                    category=category,
                    pattern_matched=matched_text,
                    line=line_no,
                    context=ctx,
                )
            )

    # Aggregate
    for hit in hits:
        by_category[hit.category] = by_category.get(hit.category, 0) + 1

    total_penalty = sum(
        penalty_weights.get(cat, 0) * count for cat, count in by_category.items()
    )

    # Sort hits for determinism
    hits.sort(key=lambda h: (h.line, h.category, h.pattern_matched))

    return SmellReport(
        total_hits=len(hits),
        by_category=dict(sorted(by_category.items())),
        hits=tuple(hits),
        total_penalty=total_penalty,
    )

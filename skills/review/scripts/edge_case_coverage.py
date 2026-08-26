#!/usr/bin/env python3
"""Analyze edge-case coverage: edge cases declared in the plan vs tests that exercise them.

Heuristic:
  1. Extract edge cases from the plan markdown — looks for:
     - "Edge case:" / "Edge cases:" inline
     - Bullets under "## Deep Dives" / "### Deep Dives" section per task
     - Bullets mentioning "empty", "null", "max", "boundary", "race", "concurrent", "timeout"
  2. For each edge case, search tests/ for assertions exercising it (keyword + AST pattern)
  3. Classify per edge case: covered / partial / missing

Output: JSON report.

Exit codes:
  0 — All declared edge cases covered (coverage = 100%)
  1 — Some declared edge cases not covered (coverage < 100%)
  2 — Error (plan not found, etc.)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EDGE_CASE_KEYWORDS = (
    "empty",
    "null",
    "undefined",
    "boundary",
    "max",
    "maximum",
    "min",
    "minimum",
    "limit",
    "overflow",
    "race",
    "concurrent",
    "concurrency",
    "timeout",
    "retry",
    "idempotent",
    "duplicate",
    "malformed",
    "invalid",
    "missing",
    "negative",
    "zero",
    "large",
    "huge",
    "edge case",
    "edge cases",
    "corner case",
    "corner cases",
)

# B-018 — a declared case is a bullet under a task's `#### Deep Dives` beginning `Edge case:` or
# `Negative case:`. Both lenses count: `rules/testing.md` § 4.1 keeps them distinct and requires
# both, and filtering negative cases out would hide exactly the failures they exist to catch.
#
# What used to be here: three patterns. One captured the text AFTER the prefix, a second captured
# the same bullet WITH the prefix (so every case counted twice — the dedup compared the two
# spellings and never matched), and a third swept EVERY bullet in the whole document carrying a
# keyword. Measured on b025-silent-guards: 7 declared, 27 reported, of which 15 came from the third
# pattern — Baseline Context citations and Unresolved Questions, sentences no test can ever cover.
#
# The sweep is deleted rather than filtered. Its output was not badly-worded edge cases; it was a
# different kind of sentence, and scoping makes guessing at intent unnecessary (parsimony rung 1).
DECLARED_CASE_RE = re.compile(
    r"^\s*[-*]\s+((?:edge|negative|corner)[\s-]*case[s]?:\s*.+?)$",
    re.IGNORECASE | re.MULTILINE,
)
DEEP_DIVES_SECTION_RE = re.compile(
    r"^####\s+Deep[\s-]*Dives\s*$([\s\S]*?)(?=^####\s+|^###\s+|^##\s+|\Z)",
    re.MULTILINE,
)
# The `#### TDD` block of the SAME task names the tests that cover its cases. That claim is
# checkable by identifier; keyword matching guesses at vocabulary and got 3 of 5 wrong on a plan
# whose tests all existed.
TDD_SECTION_RE = re.compile(
    r"^####\s+TDD\s*$([\s\S]*?)(?=^####\s+|^###\s+|^##\s+|\Z)",
    re.MULTILINE,
)
TASK_SPLIT_RE = re.compile(r"(?=^###\s+)", re.MULTILINE)
TEST_IDENT_RE = re.compile(r"\b(test_[a-z0-9_]+)\b", re.IGNORECASE)

# The fallback demanded that ALL of the five longest words co-occur in one file. A test name is a
# restatement, not a quotation, so a near-verbatim one failed. A fraction is strictly less wrong;
# it is still a heuristic, and it only runs when the task named no test.
FALLBACK_KEYWORD_FRACTION = 0.6

# A single shared word is not evidence that a test covers a case. Measured while building this:
# "a message containing an ESC yields no raw control byte" was attributed to
# `test_hostile_message_cannot_forge_a_second_record` on the word "message" alone, because ties at
# one word broke alphabetically. Below this floor the case falls to the keyword fallback, which
# reports WHY it matched instead of naming a test that does not cover it.
MIN_NAMED_TEST_OVERLAP = 2


def _tasks(plan_text: str) -> list[str]:
    """Split the plan at `### ` headings so a case keeps the TDD block of its own task."""
    parts = TASK_SPLIT_RE.split(plan_text)
    return [p for p in parts if p.strip()]


def _named_tests(task_text: str) -> list[str]:
    tests: list[str] = []
    for section in TDD_SECTION_RE.finditer(task_text):
        for ident in TEST_IDENT_RE.finditer(section.group(1)):
            name = ident.group(1)
            if name not in tests:
                tests.append(name)
    return tests


def _extract_edge_cases_from_plan(plan_text: str) -> list[dict[str, str]]:
    """Every `Edge case:` / `Negative case:` bullet under a task's `#### Deep Dives`, once."""
    cases: list[dict[str, str]] = []
    seen: set[str] = set()
    for task in _tasks(plan_text):
        named = _named_tests(task)
        for section in DEEP_DIVES_SECTION_RE.finditer(task):
            for match in DECLARED_CASE_RE.finditer(section.group(1)):
                description = match.group(1).strip()
                key = description.split(":", 1)[-1].strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                cases.append({
                    "source": "deep-dives-declared-case",
                    "description": description,
                    "named_tests": named,
                })
    return cases


def _extract_keywords_for_test_search(description: str) -> list[str]:
    """Extract searchable keywords from an edge case description.

    Strategy: lowercase, drop common stopwords, keep substantive nouns/verbs.
    """
    stopwords = {
        "the", "a", "an", "is", "are", "be", "in", "on", "at", "to", "for", "of",
        "with", "and", "or", "but", "if", "when", "then", "else", "as", "by",
        "should", "must", "will", "shall", "can", "could", "may", "might",
        "this", "that", "these", "those", "it", "its", "they", "them",
        "what", "which", "who", "whom", "whose", "where", "why", "how",
    }
    words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", description.lower())
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]
    # Cap to top 5 most "specific" (longest); avoids false positives from common words
    return sorted(set(keywords), key=len, reverse=True)[:5]


def _grep_in_dir(test_dir: Path, keywords: list[str]) -> list[Path]:
    """Find test files containing ALL the keywords."""
    if not keywords or not test_dir.exists():
        return []

    needed = max(1, round(len(keywords) * FALLBACK_KEYWORD_FRACTION))
    matches: set[Path] = set()
    for pattern in ("*.test.ts", "*.test.tsx", "*test*.py"):
        for test_file in test_dir.rglob(pattern):
            try:
                content = test_file.read_text(encoding="utf-8-sig").lower()
            except (OSError, UnicodeDecodeError):
                continue
            if sum(1 for kw in keywords if kw in content) >= needed:
                matches.add(test_file)
    return sorted(matches)


def _find_identifier(test_dir: Path, identifier: str) -> list[Path]:
    """Files declaring `identifier`.

    The `test_` prefix is a PLAN convention, not always part of the name. Measured on the two plans
    this was built against: b025 writes `test_record_is_one_physical_line` and the suite declares
    `it("test_record_is_one_physical_line")`; b001 writes `test_omits_the_cost_meter_when_...` and
    the suite declares `it("omits_the_cost_meter_when_...")`. Requiring the literal string scored
    all four b001 cases as unnamed and dropped them to the keyword fallback.
    """
    if not test_dir.exists():
        return []
    spellings = {identifier}
    if identifier.lower().startswith("test_"):
        spellings.add(identifier[len("test_"):])
    matches: set[Path] = set()
    for pattern in ("*.test.ts", "*.test.tsx", "*test*.py", "*.spec.ts", "*.spec.tsx"):
        for test_file in test_dir.rglob(pattern):
            try:
                content = test_file.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            if any(s in content for s in spellings):
                matches.add(test_file)
    return sorted(matches)


def _overlap(description: str, identifier: str) -> int:
    """Substantive words shared by a declared case and a test identifier.

    Without this, every case in a task matched the FIRST named test that existed — a per-TASK
    signal reported as a per-CASE one. Measured on b025: all four cases of the first task claimed
    `test_record_escapes_control_characters`, including the one about a hostile second line.
    """
    words = {w for w in re.findall(r"[a-z0-9]+", description.lower()) if len(w) > 3}
    ident = {w for w in re.findall(r"[a-z0-9]+", identifier.lower()) if len(w) > 3 and w != "test"}
    return len(words & ident)


def classify_coverage(edge_case: dict[str, object], test_dir: Path) -> dict[str, object]:
    """Return: covered / partial / missing per declared case.

    Two routes, in order. The plan's own `#### TDD` block names its tests, and an identifier either
    exists in the tree or it does not — no vocabulary is guessed. Only when a task names none does
    the keyword fallback run.

    A named test that is ABSENT does not make its case covered: otherwise coverage could be
    declared by writing a plan.

    Stated limit: when a task names tests but none for a PARTICULAR case, the ranking can attach the
    nearest neighbour above the floor. Measured on b001 — "a non-positive context window throws a
    typed error" is attributed to `test_renders_the_absolute_count_when_no_context_window_is_given`
    on {context, window}, while its real test, `throws_a_typed_error_naming_itself_on_a_non_positive_
    context_window`, is never named in the plan. The STATUS is right (a test does exist); the
    attribution is not. `match_overlap` is reported so a 2 can be told from a 5, and closing this
    properly means the plan naming a test per case, which is a template change and not this item.
    """
    description = str(edge_case["description"])
    named = [str(i) for i in (edge_case.get("named_tests") or [])]
    # Rank by shared vocabulary, and require at least one shared word: a task's tests are a list,
    # not an ordered mapping onto its cases.
    ranked = sorted(
        ((_overlap(description, i), i) for i in named),
        key=lambda pair: (-pair[0], pair[1]),
    )
    for score, identifier in ranked:
        if score < MIN_NAMED_TEST_OVERLAP:
            break
        found = _find_identifier(test_dir, identifier)
        if found:
            return {
                **edge_case,
                "route": "named-test",
                "matched_test": identifier,
                "match_overlap": score,
                "search_keywords": [],
                "matching_tests": [str(p) for p in found[:3]],
                "matching_count": len(found),
                "status": "covered",
            }

    keywords = _extract_keywords_for_test_search(description)
    matching_tests = _grep_in_dir(test_dir, keywords)
    return {
        **edge_case,
        "route": "keyword-fallback",
        "matched_test": None,
        "search_keywords": keywords,
        "matching_tests": [str(p) for p in matching_tests[:3]],
        "matching_count": len(matching_tests),
        "status": "covered" if matching_tests else "missing",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Edge-case coverage analyzer (plan vs tests).")
    parser.add_argument("--plan", type=Path, required=True, help="Path to plan markdown")
    parser.add_argument("--tests-dir", type=Path, default=Path("tests"), help="Tests root directory")
    args = parser.parse_args()

    if not args.plan.exists():
        print(json.dumps({"error": f"Plan not found: {args.plan}"}), file=sys.stderr)
        return 2

    plan_text = args.plan.read_text(encoding="utf-8-sig")
    edge_cases = _extract_edge_cases_from_plan(plan_text)

    if not edge_cases:
        output = {
            "plan": str(args.plan),
            "tests_dir": str(args.tests_dir),
            "edge_cases_found_in_plan": 0,
            "covered": 0,
            "partial": 0,
            "missing": 0,
            "coverage_ratio": 1.0,  # vacuously true
            "note": "No edge cases extracted from plan (may indicate plan is missing Edge Cases section, OR plan uses different naming convention)",
            "items": [],
        }
        print(json.dumps(output, indent=2))
        return 0

    classified = [classify_coverage(ec, args.tests_dir) for ec in edge_cases]

    covered = sum(1 for c in classified if c["status"] == "covered")
    partial = sum(1 for c in classified if c["status"] == "partial")
    missing = sum(1 for c in classified if c["status"] == "missing")
    total = len(classified)

    output = {
        "plan": str(args.plan),
        "tests_dir": str(args.tests_dir),
        "edge_cases_found_in_plan": total,
        "covered": covered,
        "partial": partial,
        "missing": missing,
        "coverage_ratio": round(covered / total, 3) if total else 1.0,
        "items": classified,
    }
    print(json.dumps(output, indent=2))

    return 0 if missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

"""M3 v0.1 — fabricated_citation detector for /plan-confidence.

Scans a plan's `#### Evidence` blocks (and prose surrounding them) for citations
of the following kinds, and flags ones that do not resolve:

  - rule            — `name.md` or `name.md §X`
  - opportunity     — `Opportunity §X` (legacy `Blueprint §X` still accepted)
  - adr             — `D{n}` or `ADR D{n}` (intra-plan ADR)
  - unbreakable_rule — `Unbreakable Rule {n}` (n must be in 1..13)

Citations inside fenced code blocks are ignored (they are examples).

Per `plan-confidence-golden-rule.md` § 3, ≥1 unresolved citation → hard cap 49
(stable identifier: `fabricated_citation`).

Per ADR D1 of `harden-fabrication-and-cq-gate-plan.md`, code-file refs
(`src/foo.py:42`) are out-of-scope for v0.1 (overlap with /code-quality D2).
"""
from __future__ import annotations

import re
import sys as _sys
from pathlib import Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "markdown.py").is_file():
        _sys.path.insert(0, str(_up))
        break
# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap  # noqa: E402 — post-bootstrap import
from dataclasses import dataclass, field  # noqa: E402 — post-bootstrap import
from pathlib import Path  # noqa: E402 — post-bootstrap import
from pathlib import Path as _Path_bootstrap  # noqa: E402 — post-bootstrap import

from squad.markdown import (  # noqa: E402 — post-bootstrap import
    FENCED_CODE_RE as _FENCED_CODE_OWNER,  # noqa: E402 — post-bootstrap import
)

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import

UNBREAKABLE_RULE_MAX = 13

# Rule refs: `architecture.md`, `rules/architecture.md`, either with `§1` or
# `§"Some Title"`. Backtick is explicitly excluded from the section token so that
# ``architecture.md §1`` strips properly when inline code normalizes to whitespace
# mid-match.
#
# The leading directory segments are read, and for a long time they were not. This said
# so — "Excludes paths containing slashes … v0.1 keeps the regex conservative" — honest
# about its scope, and the scope was the wrong one: `rules/<name>.md` is how every rule
# file and every plan in this kit cites, so the `fabricated_citation` hard cap could not
# fire on the dominant spelling. Measured by a consumer against 34 plans with the prefix
# read: four cite a path that does not resolve, three of them one-line repoints to a
# document that moved.
#
# THE LOOKBEHIND IS UNCHANGED, and that is the fix rather than an omission from it. It
# excludes `-` as well as `/`, so deleting the slash alone would let
# a nested path whose second-to-last segment ends in `-rules` match as if it named a
# file directly under the rules directory, and
# the kit would report its own correct citations as broken. Keeping `/` in the lookbehind
# is what forbids a match STARTING mid-path; the prefix group is what consumes the path
# from its beginning. A segment may open with `_` because `_kit-rules` does.
#
# `.` joined the lookbehind with the prefix group, and had to. Reading paths made
# `https://github.com/<owner>/<repo>/blob/main/docs/wiki/decisions/<name>.md` match from
# `com/...`, because the character before `com` is a dot and nothing forbade it — so every
# URL to a markdown file in this repository's own rules became an unresolved citation. A
# citation at the start of a sentence is unaffected: the space after the period is what the
# lookbehind sees.
_RULE_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:[a-z_][a-z0-9_.-]*/)*[a-z][a-z0-9_-]*\.md)"
    r"(?:\s*§\s*(?:\"([^\"]+)\"|([^\s,.;)\"`]+)))?"
)

# Blueprint refs: `Blueprint §Q1` or `Blueprint §"Cross-cutting"`.
# `Opportunity §X` is the current form. `Blueprint §X` is the ancestor's name for the
# same artifact (see rules/cycle-discover.md § the rename) and stays accepted so plans
# written before the rename keep resolving.
_BLUEPRINT_REF_RE = re.compile(
    r"(?:Opportunity|Blueprint)\s*§\s*(?:\"([^\"]+)\"|([A-Za-z0-9][^\s,.;)\"`]*))"
)

# ADR refs: `ADR D8` OR standalone `D8` followed by word boundary (skip dates like 2026-06-04).
# Backtick is a valid boundary because plans idiomatically wrap citations as ``D8``.
_ADR_REF_RE = re.compile(r"\bADR\s+(D\d+)\b|(?<![A-Za-z0-9_])(D\d+)(?=[\s,.;)`]|$)")

#: `D1`..`D5` are the kit's own DETECTOR names — `rules/code-quality-golden-rule.md`
#: § 5 uses them throughout, and so does every plan that reasons about which
#: detector produced a finding.
#:
#: The bare `D\d+` half of `_ADR_REF_RE` cannot tell the two apart, so a plan
#: that wrote "Disable D4 in the thresholds file" as a REJECTED ALTERNATIVE was
#: read as citing an undefined ADR: `fabricated_citation`, INVALID, score 49.
#: Measured on a consumer, and it cost a cycle plus a rewrite to avoid a token.
#:
#: A fabrication gate that fires on the kit's own vocabulary is what teaches
#: people to ignore fabrication gates.
_KIT_DETECTOR_IDS = frozenset({"D1", "D2", "D3", "D4", "D5"})

_UNBREAKABLE_RULE_RE = re.compile(r"Unbreakable\s+Rule\s+(\d+)")

# Section header in markdown — captures `## Title`, `### Title`, etc.
_MD_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)

# Fenced code blocks (``` or ~~~). DOTALL so they span multiple lines.
#: The ONE fenced-code regex, from `squad.markdown`. Eleven scripts each defined
#: their own, in two forms that do not mask the same input: five saw only backtick
#: fences, six also saw `~~~`. A plan whose example block used tildes was masked by
#: six readers and read as prose by the other five, so the same document scored
#: differently depending on which checker asked.
_FENCED_CODE_RE = _FENCED_CODE_OWNER


@dataclass(frozen=True)
class Citation:
    """A single citation extracted from a plan.

    `kind`: one of {"rule", "blueprint", "adr", "unbreakable_rule"}.
    `raw_text`: the exact substring matched (e.g., "architecture.md §99").
    `location_line`: 1-based line number in the plan.
    `reason`: human-readable explanation of why it failed to resolve.
    """

    kind: str
    raw_text: str
    location_line: int
    reason: str


@dataclass(frozen=True)
class EvidenceReport:
    """Structural report for evidence citations in a plan."""

    total_citations: int
    unresolved_citations: tuple[Citation, ...] = field(default_factory=tuple)


def check_evidence_citations(plan_path: Path, project_root: Path) -> EvidenceReport:
    """Scan plan for citations and verify each resolves.

    Citations inside fenced code blocks are ignored. Headers are also stripped
    from the scan (they are titles, not claims). The plan itself is the
    authoritative source for intra-plan ADR resolution.
    """
    content = plan_path.read_text(encoding="utf-8-sig")
    prose, line_index = _strip_fenced_code(content)

    defined_adrs = _collect_defined_adrs(content)
    citations: list[tuple[Citation, bool]] = []  # (citation, resolved?)

    citations.extend(_scan_rule_refs(prose, line_index, project_root))
    citations.extend(_scan_blueprint_refs(prose, line_index, project_root))
    citations.extend(_scan_adr_refs(prose, line_index, defined_adrs))
    citations.extend(_scan_unbreakable_rule_refs(prose, line_index))

    unresolved = tuple(c for c, resolved in citations if not resolved)
    return EvidenceReport(total_citations=len(citations), unresolved_citations=unresolved)


# ---------------------------------------------------------------------------
# Strip code + line indexing
# ---------------------------------------------------------------------------


def _strip_fenced_code(content: str) -> tuple[str, list[int]]:
    """Replace fenced code spans with whitespace (preserving newlines).

    INLINE code spans (single backticks) are deliberately kept: plans idiomatically
    write real citations as ``architecture.md §1`` and stripping them would silently
    skip the very thing we want to verify. Meta-plans that document the detector
    itself accept some false positives — fence long examples instead.

    Returns (stripped_content, line_index) where line_index[i] is the 1-based
    line number of character offset i in the original content.
    """

    def blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    stripped = _FENCED_CODE_RE.sub(blank, content)
    line_index = _build_line_index(stripped)
    return stripped, line_index


def _build_line_index(content: str) -> list[int]:
    """Return list where index[i] = 1-based line number of char i."""
    out = [1] * (len(content) + 1)
    line = 1
    for i, ch in enumerate(content):
        out[i] = line
        if ch == "\n":
            line += 1
    out[len(content)] = line
    return out


# ---------------------------------------------------------------------------
# Rule refs
# ---------------------------------------------------------------------------


def _scan_rule_refs(
    prose: str, line_index: list[int], project_root: Path
) -> list[tuple[Citation, bool]]:
    out: list[tuple[Citation, bool]] = []
    for m in _RULE_REF_RE.finditer(prose):
        filename = m.group(1)
        section = m.group(2) or m.group(3)
        raw = m.group(0)
        line_no = line_index[m.start()]
        resolved_path = _resolve_rule_file(filename, project_root)
        if resolved_path is None:
            out.append(
                (
                    Citation(
                        kind="rule",
                        raw_text=filename,
                        location_line=line_no,
                        reason=f"file {filename!r} not found in rules/, records/, or project root",
                    ),
                    False,
                )
            )
            continue
        if section is None:
            out.append((Citation(kind="rule", raw_text=filename, location_line=line_no, reason=""), True))
            continue
        if _section_exists(resolved_path, section):
            out.append((Citation(kind="rule", raw_text=raw, location_line=line_no, reason=""), True))
        else:
            out.append(
                (
                    Citation(
                        kind="rule",
                        raw_text=raw,
                        location_line=line_no,
                        reason=f"section §{section!r} not found in {filename}",
                    ),
                    False,
                )
            )
    return out


def _resolve_rule_file(filename: str, project_root: Path) -> Path | None:
    """Locate filename in conventional places. None if not found."""
    # Common locations, ordered by specificity.
    candidates = [
        project_root / "rules" / filename,
        project_root / ".claude" / "rules" / filename,
        write_records_dir(project_root) / filename,
        write_records_dir(project_root).parent / filename,
        # The DATA root, one level above `records/`. The cycle's own rules cite artifacts
        # by a path relative to it — `wiki/product/objectives.md`, per
        # `rules/cycle-brainstorm.md` — and nothing looked there. It did not matter while
        # a slashed path never matched at all; reading prefixes made it the difference
        # between a citation this detector resolves and a hard cap it raises on a file the
        # cycle wrote exactly where it was told to.
        project_root / filename,  # e.g. CHANGELOG.md, CLAUDE.md
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    # Last-resort: shallow search inside records/ (handles ADRs etc.).
    kb = write_records_dir(project_root)
    if kb.exists():
        try:
            for p in kb.rglob(filename):
                if p.is_file():
                    return p
        except OSError:
            pass
    return None


def _section_exists(file_path: Path, section: str) -> bool:
    """Return True if a markdown header in file_path matches `section`.

    Match strategy: section token compared against (a) header title verbatim,
    (b) header normalized (lowercase, whitespace collapsed), (c) trailing
    portion of the header. The token `1` matches a header like `## §1 Foo` or
    `## 1 — Foo` or `## D1 — Title`. The token `"Cross-cutting"` matches
    `## Cross-cutting Comparison`.
    """
    try:
        content = file_path.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    section_norm = section.strip().lower()
    bare = section_norm.lstrip("§").strip()
    # A NUMBERED section is matched at a word boundary, and a NAMED one by substring.
    # `in` over the whole heading applied to both, so `§1` resolved against
    # `## 21 — Retry policy` and `## Phase 1` — for a single digit the check
    # effectively could not fail, and its result feeds `fabricated_citation`, one of
    # the two caps that force INVALID. A section number is a token; a section name is
    # prose, and prose is where a substring is the right tool.
    numbered = re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", bare)
    # ANCHORED at the start of the heading, after an optional section sign. A bare
    # boundary match still accepted `## Phase 1 of the rollout` as section 1 — the
    # digit is a word there, not a section number. Numbered sections are written
    # `## 1 — Foo` or `## §1 — Foo`, which is what this matches.
    pattern = (re.compile(rf"^§?\s*{re.escape(bare)}(?![0-9.])") if numbered else None)
    for m in _MD_HEADER_RE.finditer(content):
        title_norm = m.group(2).strip().lower()
        if pattern is not None:
            if bare and pattern.search(title_norm):
                return True
            continue
        if section_norm in title_norm:
            return True
        # Tolerate "§N" or just "N" in titles like "## §1 — Foo".
        if bare and bare in title_norm:
            return True
    return False


# ---------------------------------------------------------------------------
# Blueprint refs
# ---------------------------------------------------------------------------


def _scan_blueprint_refs(
    prose: str, line_index: list[int], project_root: Path
) -> list[tuple[Citation, bool]]:
    out: list[tuple[Citation, bool]] = []
    # `/discover-execute` writes to `opportunities/`. This scanner read `blueprints/`
    # — the ancestor's directory, which nothing has written to since the rename — so
    # every `Opportunity §X` citation in a real plan resolved against an empty set and
    # was reported fabricated. Both are searched: the current path first, the legacy
    # one after, so plans predating the rename keep resolving.
    discoveries = write_records_dir(project_root, "discoveries")
    available = []
    for sub in ("opportunities", "blueprints"):
        d = discoveries / sub
        if not d.exists():
            continue
        try:
            available.extend(p for p in d.iterdir() if p.is_file() and p.suffix == ".md")
        except OSError:
            continue
    for m in _BLUEPRINT_REF_RE.finditer(prose):
        section = m.group(1) or m.group(2)
        raw = m.group(0)
        line_no = line_index[m.start()]
        if not available:
            out.append(
                (
                    Citation(
                        kind="blueprint",
                        raw_text=raw,
                        location_line=line_no,
                        reason="no opportunities exist in records/discoveries/opportunities/",
                    ),
                    False,
                )
            )
            continue
        resolved = any(_section_exists(bp, section) for bp in available)
        if resolved:
            out.append((Citation(kind="blueprint", raw_text=raw, location_line=line_no, reason=""), True))
        else:
            out.append(
                (
                    Citation(
                        kind="blueprint",
                        raw_text=raw,
                        location_line=line_no,
                        reason=f"section §{section!r} not found in any opportunity",
                    ),
                    False,
                )
            )
    return out


# ---------------------------------------------------------------------------
# Intra-plan ADRs
# ---------------------------------------------------------------------------


def _collect_defined_adrs(content: str) -> set[str]:
    """Return set of ADR identifiers defined in the plan (e.g., {"D1", "D2"})."""
    defined: set[str] = set()
    for m in _MD_HEADER_RE.finditer(content):
        title = m.group(2).strip()
        adr_match = re.match(r"^(D\d+)\b", title)
        if adr_match:
            defined.add(adr_match.group(1))
    return defined


def _scan_adr_refs(
    prose: str, line_index: list[int], defined_adrs: set[str]
) -> list[tuple[Citation, bool]]:
    out: list[tuple[Citation, bool]] = []
    seen: set[tuple[int, str]] = set()  # dedupe by (line, id) to avoid double-count from regex alternation
    for m in _ADR_REF_RE.finditer(prose):
        adr_id = m.group(1) or m.group(2)
        if adr_id is None:
            continue
        line_no = line_index[m.start()]
        key = (line_no, adr_id)
        if key in seen:
            continue
        seen.add(key)
        # A bare `D4` that resolves to a defined ADR IS a citation — the plan
        # said so by defining it. One that does not, and names a kit detector,
        # is the kit's vocabulary rather than a fabricated reference. Deciding
        # only on the unresolved case keeps every real citation working.
        if adr_id not in defined_adrs and adr_id in _KIT_DETECTOR_IDS and not m.group(1):
            continue
        resolved = adr_id in defined_adrs
        if resolved:
            out.append((Citation(kind="adr", raw_text=adr_id, location_line=line_no, reason=""), True))
        else:
            out.append(
                (
                    Citation(
                        kind="adr",
                        raw_text=adr_id,
                        location_line=line_no,
                        reason=f"ADR {adr_id} is referenced but not defined under '## ADRs' in the plan",
                    ),
                    False,
                )
            )
    return out


# ---------------------------------------------------------------------------
# Unbreakable Rules
# ---------------------------------------------------------------------------


def _scan_unbreakable_rule_refs(
    prose: str, line_index: list[int]
) -> list[tuple[Citation, bool]]:
    out: list[tuple[Citation, bool]] = []
    for m in _UNBREAKABLE_RULE_RE.finditer(prose):
        num_str = m.group(1)
        line_no = line_index[m.start()]
        try:
            num = int(num_str)
        except ValueError:
            continue
        raw = m.group(0)
        if 1 <= num <= UNBREAKABLE_RULE_MAX:
            out.append((Citation(kind="unbreakable_rule", raw_text=raw, location_line=line_no, reason=""), True))
        else:
            out.append(
                (
                    Citation(
                        kind="unbreakable_rule",
                        raw_text=raw,
                        location_line=line_no,
                        reason=f"Unbreakable Rule {num} is out of range (1..{UNBREAKABLE_RULE_MAX})",
                    ),
                    False,
                )
            )
    return out

"""ADR completeness check: each ADR must list alternatives in Rationale.

A plan has the structure:
  ## ADRs

  ### D1 — Title
  - **Decisão:** ...
  - **Rationale:** ... alternative rejected ... or similar
  - **Consequências:** ...

  ### D2 — Title
  ...

An ADR is "complete" iff its Rationale section explicitly mentions
alternatives ("rejected", "instead of", "considered", "trade-off").

    Portuguese terms were accepted here until 2026-08-27. A checker that
    reads a second language has decided the English-only policy is
    advisory, and a plan written in Portuguese passed this gate while
    failing the one that governs the repository.

Returns ADRReport with total, with_alternatives, completeness_ratio, missing IDs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: Both spellings, because this kit writes both and matched only one.
#:
#: `plan-template.md` prescribes `D1, D2, …` and this matched that. The rest of the kit writes
#: `ADR-N` — `rules/cycle-code-quality.md`, `rules/cycle-rule-schema.md`, `docs/ADR/0025-…` — and
#: authors followed the majority. Measured 2026-09-23 across one consumer's plans: `### ADR-N`
#: ninety-six times against `### D1` five.
#:
#: What that cost is the whole point. `plan-confidence-golden-rule.md:42` declares
#: *"ADR without alternatives in Rationale → score ≤ 70"*, and with no ADR matched the cap has no
#: subject: a plan with one ADR rejecting nothing reported `total_adrs=0,
#: completeness_ratio=1.0` — a gate reporting itself applied while applying nothing.
#:
#: Found by the ORTHOGONAL seat of a plan panel: the reviewer outside the kit's model family
#: approved the artifact and brought back a defect of the kit that neither same-family seat saw.
ADR_HEADER_RE = re.compile(r"^###\s+(ADR-\d+|D\d+)\s*[—\-–:]", re.MULTILINE)
ADRS_SECTION_RE = re.compile(r"^##\s+ADRs?\s*$", re.MULTILINE)
NEXT_H2_RE = re.compile(r"^##\s+", re.MULTILINE)

# Keywords that indicate alternative-consideration in Rationale (v1.1+ #4 fix: expanded).
#
# English only. `rules/english-only.md` says this checker reads English, and six
# Portuguese phrases survived here after that was written, so a Portuguese rationale
# satisfied the check while breaking the rule governing the plan it sits in (#216).
ALTERNATIVE_KEYWORDS = (
    # Direct mentions
    "alternatives",
    "alternative",
    "rejected",
    # Comparisons
    "instead of",
    "vs.",
    "vs ",
    # Trade-off / decision pattern
    "trade-off",
    "tradeoff",
    "trade off",
    "trade-offs",
    # Why-not pattern
    "why not",
    # "Considered X" pattern
    "considered ",
    # Alt A/B/C inline
    " alt a",
    " alt b",
    " alt c",
)


@dataclass(frozen=True)
class ADRReport:
    total_adrs: int
    with_alternatives: int
    completeness_ratio: float
    missing_alternatives: tuple[str, ...] = field(default_factory=tuple)
    #: Decisions that never say what being wrong would cost. Reported by
    #: `run_structural.py` under `sub_reports.adr_completeness`; it was collected
    #: and dropped for as long as this field had no reader.
    #:
    #: REPORT-ONLY — it caps nothing, and deliberately so. `rules/plan-confidence-
    #: golden-rule.md` is the only place a cap is declared, and its table has a row
    #: for `adr_without_alternatives` and none for this. On a consumer registry of
    #: 34 plans measured 2026-09-23, all but one were missing it on at least one
    #: decision, so a cap here would fire on ordinary work — the shape a gate earns
    #: by being switched off. Read the list; do not build a threshold on it.
    missing_cost_if_wrong: tuple[str, ...] = ()


def _extract_adrs_section(content: str) -> str:
    """Extract content from '## ADRs' header to next H2."""
    m = ADRS_SECTION_RE.search(content)
    if m is None:
        return ""
    start = m.end()
    nxt = NEXT_H2_RE.search(content, pos=start)
    end = nxt.start() if nxt else len(content)
    return content[start:end]


def _split_into_adr_blocks(section: str) -> dict[str, str]:
    """Split section into {adr_id: body} dict."""
    blocks: dict[str, str] = {}
    matches = list(ADR_HEADER_RE.finditer(section))
    for i, m in enumerate(matches):
        adr_id = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        blocks[adr_id] = section[start:end]
    return blocks


#: How a decision states what happens if it turns out wrong.
#:
#: Borrowed from an observed `subagent-driven-development` run (obra/superpowers,
#: 2026-08-28), where every ruling ended with one: *"Cost if wrong: cosmetic
#: only"*, *"Cost if wrong: none — the helper asserts strictly more"*, *"Cost if
#: wrong: the skill carries a figure whose guarded arm describes an engine
#: crash"*. That last one is why it matters: naming the cost is what separated
#: the six fixes applied immediately from the two recorded-not-fixed and the one
#: escalated to a human.
#:
#: Listing pros and cons argues the choice is right. This asks what happens when
#: it is not — and a cost the author cannot name is a decision they have not
#: finished making.
COST_KEYWORDS = (
    "cost if wrong",
    "custo se errado",
    "if this is wrong",
    "if wrong:",
    "blast radius",
    "cost of being wrong",
)


def _has_cost_if_wrong(adr_body: str) -> bool:
    """True when the decision states what it costs to be wrong."""
    lower = adr_body.lower()
    return any(kw in lower for kw in COST_KEYWORDS)


def _has_alternative_mention(adr_body: str) -> bool:
    lower = adr_body.lower()
    return any(kw in lower for kw in ALTERNATIVE_KEYWORDS)


def _has_global_alternatives_section(content_lower: str) -> bool:
    """Detect template-style '## Alternativas Rejeitadas' section with entries."""
    section_headers = (
        "## alternativas rejeitadas",
        "## rejected alternatives",
        "## alternatives considered",
    )
    for header in section_headers:
        alt_pos = content_lower.find(header)
        if alt_pos == -1:
            continue
        after = content_lower[alt_pos : alt_pos + 5000]
        entry_keywords = ("alt a", "alt b", "alt c", "rejeitada por", "rejected by")
        if any(kw in after for kw in entry_keywords):
            return True
    return False


def check_adr_completeness(plan_path: Path) -> ADRReport:
    """ADR is 'complete' if its own body mentions alternatives OR if the plan has
    a global '## Alternativas Rejeitadas' / '## Rejected Alternatives' section.

    v1.1 follow-up: plan template often groups alternatives in a single section,
    not per-ADR; both styles satisfy the intent.
    """
    content = plan_path.read_text(encoding="utf-8-sig")
    adr_section = _extract_adrs_section(content)
    blocks = _split_into_adr_blocks(adr_section)

    total = len(blocks)
    if total == 0:
        return ADRReport(
            total_adrs=0,
            with_alternatives=0,
            completeness_ratio=1.0,
            missing_alternatives=(),
            missing_cost_if_wrong=(),
        )

    # `cost if wrong` is per-decision by nature: a global section can hold the
    # rejected alternatives for the whole plan, but the cost of being wrong
    # belongs to one decision and cannot be shared.
    no_cost = tuple(sorted(i for i, b in blocks.items() if not _has_cost_if_wrong(b)))

    if _has_global_alternatives_section(content.lower()):
        return ADRReport(
            total_adrs=total,
            with_alternatives=total,
            completeness_ratio=1.0,
            missing_alternatives=(),
            missing_cost_if_wrong=no_cost,
        )

    missing: list[str] = []
    with_alt = 0
    for adr_id, body in blocks.items():
        if _has_alternative_mention(body):
            with_alt += 1
        else:
            missing.append(adr_id)

    return ADRReport(
        total_adrs=total,
        with_alternatives=with_alt,
        completeness_ratio=with_alt / total,
        missing_alternatives=tuple(sorted(missing)),
        missing_cost_if_wrong=no_cost,
    )

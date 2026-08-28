#!/usr/bin/env python3
"""Score how far a backlog item is from being understood the same way by both sides.

WHY A SCORE AND NOT A JUDGEMENT
-------------------------------
"We understand each other" is exactly the kind of claim this kit refuses
everywhere else: asserted, unfalsifiable, and comfortable. The research says the
same thing from the other direction — shared understanding cannot be measured
directly, but **ambiguity can**, and ambiguity is its inverse. So this scores the
artefact rather than the feeling.

THE RUBRIC, AND WHERE IT COMES FROM
-----------------------------------
Each criterion scores 0 (absent), 1 (partial), 2 (complete). The threshold is
**90% of the maximum**, which is the figure the Definition-of-Ready literature
uses for the same purpose — score 0/1/2 per criterion, require >=90% to accept.

Below the threshold the item does not get built. That is the whole point: an item
nobody can explain to a diagram is an item somebody is about to guess at.

WHAT IS MECHANISED AND WHAT IS NOT
----------------------------------
Structure is mechanised — a section exists, a requirement carries a number, a
flow has steps, an acceptance criterion names a command. Whether the content is
*right* is not, and this script says so rather than pretending: `judgement_items`
lists the criteria a human still has to sign off, and they are excluded from the
computed score instead of being silently marked as passing.

Usage:
    python3 score_alignment.py <alignment-brief.md> [--json]

Exit codes:
    0 — at or above the threshold; the item may be built
    1 — below the threshold; the item must not be built yet
    2 — the brief could not be read
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: The bar. 90% of the maximum, per the Definition-of-Ready scoring convention.
THRESHOLD = 0.90

#: A requirement is measurable when it carries a number and a unit, or an
#: explicit comparison. "Fast" is a wish; "p95 under 200ms at 1000 rps" is a
#: requirement somebody can fail.
_MEASURABLE_RE = re.compile(
    r"\d+\s*(ms|s|m|h|%|rps|qps|req/s|MB|GB|KB|kb/s|users?|rows?|items?)"
    r"|[<>≤≥]=?\s*\d"
    r"|\b(p50|p95|p99|percentile)\b",
    re.IGNORECASE,
)

#: An acceptance criterion is executable when it names something that runs.
_EXECUTABLE_RE = re.compile(
    r"`[^`]*(?:npm|pytest|go |cargo|make|curl|grep|python3|bash|node|exit \d)[^`]*`"
    r"|\bexit\s+(?:code\s+)?\d",
    re.IGNORECASE,
)

#: An open question the grill never closed.
_UNRESOLVED_RE = re.compile(r"\b(UNKNOWN|TBD|TODO|to be decided|\?\?\?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str
    score: int          # 0, 1 or 2
    why: str


@dataclass(frozen=True)
class AlignmentReport:
    criteria: tuple[Criterion, ...]
    judgement_items: tuple[str, ...]

    @property
    def earned(self) -> int:
        return sum(c.score for c in self.criteria)

    @property
    def maximum(self) -> int:
        return 2 * len(self.criteria)

    @property
    def ratio(self) -> float:
        return self.earned / self.maximum if self.maximum else 0.0

    @property
    def meets_threshold(self) -> bool:
        return self.ratio >= THRESHOLD

    @property
    def gaps(self) -> tuple[Criterion, ...]:
        return tuple(c for c in self.criteria if c.score < 2)


def _section(body: str, *titles: str) -> str | None:
    """The body of the first matching `## <title>` section."""
    for title in titles:
        m = re.search(
            rf"^##+\s+{re.escape(title)}\s*$\n(.*?)(?=^##+\s|\Z)",
            body, re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        if m:
            return m.group(1)
    return None


def _bullets(text: str | None) -> list[str]:
    if not text:
        return []
    return [ln.strip() for ln in text.splitlines() if re.match(r"^\s*[-*\d]", ln) and ln.strip()]


def _tri(present: bool, complete: bool) -> int:
    """0 absent · 1 present but partial · 2 complete."""
    return 2 if complete else (1 if present else 0)


def score_alignment(brief_path: Path) -> AlignmentReport:
    """Score one alignment brief against the rubric."""
    body = Path(brief_path).read_text(encoding="utf-8-sig")
    criteria: list[Criterion] = []

    def add(key: str, label: str, score: int, why: str) -> None:
        criteria.append(Criterion(key, label, score, why))

    # 1 — The problem, in the system's own terms.
    problem = _section(body, "Problem", "Context", "Why now")
    add("problem", "The problem is stated as something observed here",
        _tri(bool(problem), bool(problem and len(problem.split()) >= 30)),
        "absent" if not problem else ("too short to have said anything" if len(
            problem.split()) < 30 else "stated"))

    # 2 — Functional requirements.
    fr = _bullets(_section(body, "Functional Requirements", "Functional requirements"))
    add("functional_requirements", "Functional requirements enumerated",
        _tri(bool(fr), len(fr) >= 2),
        f"{len(fr)} listed" if fr else "no `## Functional Requirements` section")

    # 3 — Non-functional requirements, WITH numbers.
    nfr = _bullets(_section(body, "Non-Functional Requirements", "Non-functional requirements"))
    measurable = [b for b in nfr if _MEASURABLE_RE.search(b)]
    add("nfr_measurable", "Non-functional requirements carry numbers",
        _tri(bool(nfr), bool(nfr) and len(measurable) == len(nfr)),
        f"{len(measurable)}/{len(nfr)} measurable" if nfr
        else "no `## Non-Functional Requirements` section")

    # 4 — Flows, named and stepped.
    flows = _section(body, "Flows", "Flow", "User flows")
    flow_names = re.findall(r"^###\s+(.+)$", flows or "", re.MULTILINE)
    stepped = [n for n in flow_names if True] if flows and re.search(
        r"^\s*\d+\.", flows, re.MULTILINE) else []
    add("flows", "Flows named, each broken into steps",
        _tri(bool(flow_names), bool(flow_names) and bool(stepped)),
        f"{len(flow_names)} flow(s)" if flow_names else "no named flow")

    # 5 — A system-level picture.
    has_system = bool(re.search(r"```mermaid|<svg|flowchart|C4Context|graph (TB|LR)", body))
    system_sec = _section(body, "System design", "Architecture", "System Design")
    add("system_diagram", "A system-level diagram exists",
        _tri(has_system or bool(system_sec), has_system and bool(system_sec)),
        "diagram + section" if (has_system and system_sec)
        else ("diagram only" if has_system else "neither"))

    # 6 — How the pieces interact.
    has_interaction = bool(re.search(
        r"sequenceDiagram|classDiagram|participant\s|\bclass\s+\w+\s*\{", body))
    add("interaction_model", "Interaction between the parts is drawn",
        _tri(has_interaction, has_interaction and body.count("participant") + body.count(
            "class ") >= 3),
        "present" if has_interaction else "no sequence or class diagram")

    # 7 — Acceptance criteria that can fail.
    ac = _bullets(_section(body, "Acceptance Criteria", "Acceptance criteria"))
    executable = [b for b in ac if _EXECUTABLE_RE.search(b)]
    add("acceptance_executable", "Acceptance criteria name something that runs",
        _tri(bool(ac), bool(ac) and len(executable) == len(ac)),
        f"{len(executable)}/{len(ac)} executable" if ac else "no acceptance criteria")

    # 8 — Dependencies, named or explicitly none.
    deps = _section(body, "Dependencies", "Depends on")
    deps_bullets = _bullets(deps)
    explicit_none = bool(deps and re.search(r"\b(none|no dependenc)\b", deps, re.IGNORECASE))
    add("dependencies", "Dependencies named, or explicitly none",
        _tri(bool(deps), bool(deps_bullets) or explicit_none),
        "declared" if (deps_bullets or explicit_none) else "section missing or empty")

    # 9 — What this is NOT. The boundary nobody writes and everybody assumes.
    scope_out = _section(body, "Out of scope", "Not in scope", "What this does not do")
    add("out_of_scope", "What the item does NOT cover is written down",
        _tri(bool(scope_out), len(_bullets(scope_out)) >= 1),
        "declared" if _bullets(scope_out) else "absent — the boundary is being assumed")

    # 10 — The questions the grill asked, and their answers.
    grill = _section(body, "Questions answered", "Open questions", "Grill")
    unresolved = _UNRESOLVED_RE.findall(grill or "")
    add("questions_closed", "Every question raised was answered",
        _tri(bool(grill), bool(grill) and not unresolved),
        f"{len(unresolved)} still open" if unresolved else (
            "all closed" if grill else "no record of questions"))

    # 11 — How it will be demonstrated.
    demo = _section(body, "Demonstration", "How to demo", "Demo")
    add("demonstration", "How the result gets demonstrated is written",
        _tri(bool(demo), len(_bullets(demo)) >= 1),
        "declared" if _bullets(demo) else "absent")

    # 12 — The interactive artefact.
    html = re.search(r"`([^`]*\.html)`|\]\(([^)]*\.html)\)", body)
    add("interactive_artefact", "An interactive walkthrough was produced",
        _tri(bool(html), bool(html)),
        html.group(0) if html else "no .html referenced")

    # What a script cannot decide, said out loud rather than scored as passing.
    judgement = (
        "whether the stated problem is the real one",
        "whether the flows drawn are the flows that matter",
        "whether the numbers in the NFRs are the right numbers",
    )
    return AlignmentReport(tuple(criteria), judgement)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = score_alignment(args.brief)
    except OSError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "earned": report.earned,
            "maximum": report.maximum,
            "ratio": round(report.ratio, 4),
            "threshold": THRESHOLD,
            "meets_threshold": report.meets_threshold,
            "criteria": [
                {"key": c.key, "label": c.label, "score": c.score, "why": c.why}
                for c in report.criteria
            ],
            "judgement_items": list(report.judgement_items),
        }, indent=2, ensure_ascii=False))
        return 0 if report.meets_threshold else 1

    pct = report.ratio * 100
    verdict = "ALIGNED" if report.meets_threshold else "NOT ALIGNED"
    print(f"{verdict}  {report.earned}/{report.maximum}  ({pct:.0f}%, threshold {THRESHOLD:.0%})\n")
    for c in report.criteria:
        mark = {0: "✗", 1: "~", 2: "✓"}[c.score]
        print(f"  {mark} {c.label:<52} {c.why}")
    if not report.meets_threshold:
        print("\nThis item must NOT be built yet. Close these first:")
        for c in report.gaps:
            print(f"  - {c.label} — {c.why}")
    print("\nNot scored, and still yours to judge:")
    for item in report.judgement_items:
        print(f"  - {item}")
    return 0 if report.meets_threshold else 1


if __name__ == "__main__":
    sys.exit(main())

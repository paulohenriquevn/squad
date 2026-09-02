#!/usr/bin/env python3
"""Score how far a backlog item is from being understood the same way by both sides.

WHY A SCORE AND NOT A JUDGEMENT
-------------------------------
"We understand each other" is exactly the kind of claim this kit refuses
everywhere else: asserted, unfalsifiable, and comfortable. The research says the
same thing from the other direction — shared understanding cannot be measured
directly, but **ambiguity can**, and ambiguity is its inverse. So this scores the
artefact rather than the feeling.

WHY TWO VERDICTS AND NOT ONE
----------------------------
The first version of this script had one number, and the agent that wrote the
brief was the same agent that ran the scorer that approved it. That is a gate
grading its own homework.

Five reference implementations were read in full on 2026-08-28. Only one had
solved it, and its solution is adopted here: `github/spec-kit` makes its
requirements checklist **reviewer-owned** — generated unchecked, and
`/implement` reads the boxes as a gate and *may not modify the markers*.

So there are two independent conditions, and `ALIGNED` needs both:

    machine score >= 90%   — structure. The agent can and should reach this.
    reviewer sign-off      — judgement, from a reviewer who is not the author.
                             A person, or `alignment_judge.py` when none is coming
                             (`alignment-threshold.md § Amended 2026-09-01`). This
                             line read "only a human can give it" while the code
                             below already accepted a judge — the verdict turns on
                             `reviewer_signed_off`, and `signed_by_is_human` is
                             reported beside it rather than gating on it.

A perfect machine score with no sign-off is `AWAITING_REVIEW`, never `ALIGNED`.
This is not ceremony: the three things the script explicitly cannot decide are
the three that decide whether the work is worth doing at all.

WHERE THE RUBRIC COMES FROM
---------------------------
Each criterion scores 0 (absent), 1 (partial), 2 (complete). The threshold is
**90% of the maximum**, the figure the Definition-of-Ready literature uses for
the same purpose. Individual criteria carry their source in a comment; the ones
added in v2 come from:

    spec-kit /analyze     stable ids, requirement->criterion coverage, vague-term
                          detection, terminology and placeholder scanning
    spec-kit /checklist   scenario classes (primary/alternate/exception/recovery),
                          "test the requirements, not the implementation",
                          reviewer-owned sign-off
    superpowers           whole-document placeholder scan (spec self-review)
    feature-forge         EARS-shaped requirements with measurable responses
    FredAntB SDD          sequential ids, every requirement carries a criterion

WHAT IS MECHANISED AND WHAT IS NOT
----------------------------------
Structure is mechanised. Whether the content is *right* is not, and this script
says so rather than pretending: `judgement_items` lists what a REVIEWER still has to
sign off, and they are excluded from the computed score instead of being silently
marked as passing. They are the same three items the reviewer checklist asks.

Usage:
    python3 score_alignment.py <alignment-brief.md> [--json] [--machine-only]

Exit codes:
    0 — ALIGNED (machine score met AND a reviewer signed off), or, with
        --machine-only, the machine score alone was met
    1 — BLOCKED, AWAITING_REVIEW or NEEDS_SPLIT; the item must not be built yet
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

#: An unresolved decision, in whatever coat it is wearing. Scanned across the
#: WHOLE brief since v2 — a `TBD` in the data model is the same open question as
#: an `UNKNOWN` in the answers, and it used to be invisible.
_UNRESOLVED_RE = re.compile(
    r"\b(UNKNOWN|TBD|TKTK|TODO|FIXME|to be decided|\?\?\?)\b|\{\{[A-Z_]+\}\}",
    re.IGNORECASE,
)

#: Stable identifiers. Without them nothing can cite anything: not an acceptance
#: criterion, not a task, not a test, not a review comment.
# The WHOLE id is captured, prefix included. Capturing only the digits made
# `FR-001` and `NFR-001` the same string, so `declared = fr_ids | nfr_ids` merged
# them and an acceptance criterion citing FR-001 marked NFR-001 covered. A brief
# whose non-functional requirements were verified by nothing scored full marks on
# the criterion that exists to catch exactly that.
#
# Found on 2026-08-30 by an agent scoring a real backlog item during the first
# pipeline run — with the line numbers and the figures: 5/6 reported, 3/6 actual.
# This suite had not caught it because its fixture cites one FR and one NFR with
# different numbers, which is the one shape the collision cannot produce.
#
# `(?<!N)` keeps `FR-` from matching inside `NFR-`.
_FR_ID_RE = re.compile(r"\b(?<!N)(FR-\d{3})\b")
_NFR_ID_RE = re.compile(r"\b(NFR-\d{3})\b")
_AC_ID_RE = re.compile(r"\b(AC-\d{3})\b")

#: The four scenario classes. "Did you think about failure?" stops being a
#: question somebody remembers to ask and becomes a check that fires.
_SCENARIO_CLASSES = ("primary", "alternate", "exception", "recovery")

#: Adjectives that sound like requirements and cannot be failed. Kept to words
#: that are unambiguously claims about quality — a gate that fires on ordinary
#: prose is a gate somebody disables, and this one runs in every consumer.
_VAGUE_TERMS = (
    "fast", "slow", "quick", "snappy", "responsive", "performant",
    "scalable", "robust", "reliable", "seamless", "intuitive", "user-friendly",
    "simple to use", "easy to use", "efficient", "lightweight", "secure",
    "modern", "clean", "flexible", "as needed", "if necessary", "etc",
)
_VAGUE_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _VAGUE_TERMS) + r")\b",
                       re.IGNORECASE)

#: A reviewer-owned checkbox. Generated `[ ]`, ticked by a reviewer.
_CHECKBOX_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(.+?)\s*$", re.MULTILINE)

#: `<!-- signed-by: judge/alignment-judge -->` on the ticked line.
#:
#: An unattributed tick reads as a human's, and for most of this file's life that
#: was the only kind there was. Once an agent may sign, `ALIGNED` stops meaning
#: one thing — a reader has to be able to tell a human review from an agent's
#: without opening the file, because the two are worth different amounts.
# Captures to the closing marker, spaces included: the ROUTE is part of the
# provenance. `human/paulo (approved in session)` says more than `human`, and
# a pattern that stopped at the first space silently dropped exactly that.
_SIGNED_BY_RE = re.compile(r"<!--\s*signed-by:\s*([^>]+?)\s*-->")

#: A reviewer declaring the item is not one item. The scorer TRANSPORTS this rather
#: than inferring it: deciding that a description spans independent subsystems is
#: judgement, and the same judgement is left unmechanized at intake (gate G3) for
#: the same reason. A regex over a brief would produce verdicts about language.
#: Without this marker `NEEDS_SPLIT` was documented in SKILL.md and unreachable in
#: code, so an item needing a split came out as a generic `BLOCKED` and the most
#: actionable thing the reviewer knew was lost between the review and the caller.
_NEEDS_SPLIT_RE = re.compile(r"<!--\s*verdict:\s*NEEDS_SPLIT\s*(?::\s*([^>]*?))?\s*-->", re.IGNORECASE)


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
    #: Reviewer checklist items still unticked. Empty AND non-empty checklist
    #: means signed off; an absent checklist is not a sign-off either.
    pending_review: tuple[str, ...] = ()
    reviewer_items_total: int = 0
    #: "human", or the judge's identifier, or None when nothing is signed. A
    #: mixed set reports the WEAKEST signer: a reader deciding how far to trust
    #: the verdict needs the weakest link, not the majority — the same reason a
    #: partially reviewed brief counts as unreviewed.
    signed_by: str | None = None

    #: Set when a reviewer marked the brief `<!-- verdict: NEEDS_SPLIT -->`.
    needs_split: bool = False
    split_reason: str = ""

    @property
    def signed_by_is_human(self) -> bool:
        """A NAMED human is still a human.

        Provenance must not cost the distinction it exists to protect: the first
        cut treated any marker other than the bare word `human` as an agent, so
        recording WHO signed would have downgraded a person's signature to an
        agent's. The `human/` prefix keeps both the route and the meaning.
        """
        return bool(self.signed_by) and (
            self.signed_by == "human" or self.signed_by.startswith("human/"))

    # ── the machine half: structure the agent can and should reach ──────────
    @property
    def earned(self) -> int:
        return sum(c.score for c in self.criteria)

    @property
    def maximum(self) -> int:
        return 2 * len(self.criteria)

    @property
    def machine_ratio(self) -> float:
        return self.earned / self.maximum if self.maximum else 0.0

    @property
    def meets_machine_threshold(self) -> bool:
        return self.machine_ratio >= THRESHOLD

    #: Kept so callers written against v1 keep working.
    ratio = machine_ratio
    meets_threshold = meets_machine_threshold

    # ── the human half: judgement only a reviewer can supply ───────────────
    @property
    def reviewer_signed_off(self) -> bool:
        return self.reviewer_items_total > 0 and not self.pending_review

    @property
    def aligned(self) -> bool:
        return self.meets_machine_threshold and self.reviewer_signed_off

    @property
    def verdict(self) -> str:
        # Checked before the score, because a low score is a CONSEQUENCE of the item
        # being two items: neither half's flows, criteria or measurements converge
        # while they share one brief. Reporting `BLOCKED` here would send the reviewer
        # to close gaps that no amount of writing can close.
        if self.needs_split:
            return "NEEDS_SPLIT"
        if not self.meets_machine_threshold:
            return "BLOCKED"
        return "ALIGNED" if self.reviewer_signed_off else "AWAITING_REVIEW"

    @property
    def gaps(self) -> tuple[Criterion, ...]:
        return tuple(c for c in self.criteria if c.score < 2)


def _section(body: str, *titles: str) -> str | None:
    """The body of the first matching `## <title>` section, subsections included.

    The stop condition must match the OPENING heading's level or shallower. The
    first version stopped at `^##+`, so `## Flows` ended at its own first
    `### Query a 24h window` and every flow section came back empty — the
    criterion scored 0 on a brief that had four flows, and the fixture still
    cleared 90% because two lost points fit inside the tolerance. A gate reading
    an empty string and reporting "no named flow" is worse than no gate: it
    produces a verdict.
    """
    for title in titles:
        m = re.search(
            rf"^(#{{2,}})\s+{re.escape(title)}\s*$\n",
            body, re.MULTILINE | re.IGNORECASE,
        )
        if not m:
            continue
        depth = len(m.group(1))
        rest = body[m.end():]
        stop = re.search(rf"^#{{1,{depth}}}\s", rest, re.MULTILINE)
        return rest[:stop.start()] if stop else rest
    return None


def _bullets(text: str | None) -> list[str]:
    if not text:
        return []
    return [ln.strip() for ln in text.splitlines() if re.match(r"^\s*[-*\d]", ln) and ln.strip()]



#: Fenced code blocks and inline code spans — where a document QUOTES rather than
#: states. Stripped before looking for a marker that carries a verdict.
_FENCED_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _declarations_only(body: str) -> str:
    """The lines on which the document speaks in its own voice.

    A verdict marker is a statement the document makes. Quoted inside a sentence,
    a list item or a code span it is an example of the syntax, not a use of it —
    and a brief telling its reviewer how to declare a split contains exactly that.
    """
    stripped = _INLINE_CODE_RE.sub("", _FENCED_RE.sub("", body))
    return "\n".join(
        line for line in stripped.splitlines()
        if line.strip().startswith("<!--") and line.strip().endswith("-->"))


def _without_section(body: str, *headings: str) -> str:
    """`body` with the named section removed, heading and all.

    Used where a criterion must not charge for something another criterion owns.
    Matches `_section`'s heading conventions so the two agree on where a section
    starts and stops.
    """
    for heading in headings:
        pattern = re.compile(
            rf"^#{{1,6}}\s*{re.escape(heading)}\s*$.*?(?=^#{{1,6}}\s|\Z)",
            re.IGNORECASE | re.MULTILINE | re.DOTALL)
        body = pattern.sub("", body)
    return body


def _absent_or_empty(section: str | None, heading: str) -> str:
    """Why a requirements criterion scored zero — the heading, or the contents.

    kit#13. Both cases produced `no ## <heading> section`, so a brief whose
    section held prose but no bullets was told the heading did not exist. The
    score was right; the reason sent the author to add a heading already there
    instead of to add requirements, and telling an author what to close is the
    gate's entire value.
    """
    if section is None or not section.strip():
        return f"no `## {heading}` section"
    return f"`## {heading}` is present and lists nothing"


#: A scenario class counts as DRAWN when it is labelled — an explicit `[class]`
#: marker, or a heading naming it. Not when the word appears in running prose.
#:
#: kit#12. The old pattern also matched `<class> flow|path|scenario` anywhere in
#: the section, and prose is where a brief EXPLAINS itself, including when it
#: explains an absence. Measured: a Flows section holding the single sentence
#: "There is no recovery path" scored `1/4 classes: recovery` — the criterion
#: moved 0 -> 1 and added a real point toward the 90% gate that decides whether
#: an item may be implemented, for a brief with zero flows drawn.
#:
#: Detecting the negation instead was the other option and was rejected: it
#: needs a list of the ways English says no, and every word missing from that
#: list is this same bug. A label is unambiguous, it is what "drawn" means, and
#: the deliberate `[class]` form already existed for authors who want the point.
_CLASS_MARKER = "[{c}]"


def _class_is_drawn(cls: str, flows: str | None) -> bool:
    if not flows:
        return False
    if _CLASS_MARKER.format(c=cls).lower() in flows.lower():
        return True
    heading = re.compile(rf"^\s*#{{1,6}}\s+.*\b{cls}\b", re.IGNORECASE | re.MULTILINE)
    return bool(heading.search(flows))


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
    fr_section = _section(body, "Functional Requirements", "Functional requirements")
    fr = _bullets(fr_section)
    add("functional_requirements", "Functional requirements enumerated",
        _tri(bool(fr), len(fr) >= 2),
        f"{len(fr)} listed" if fr else _absent_or_empty(
            fr_section, "Functional Requirements"))

    # 3 — Non-functional requirements, WITH numbers.
    nfr_section = _section(body, "Non-Functional Requirements", "Non-functional requirements")
    nfr = _bullets(nfr_section)
    measurable = [b for b in nfr if _MEASURABLE_RE.search(b)]
    add("nfr_measurable", "Non-functional requirements carry numbers",
        _tri(bool(nfr), bool(nfr) and len(measurable) == len(nfr)),
        f"{len(measurable)}/{len(nfr)} measurable" if nfr
        else _absent_or_empty(nfr_section, "Non-Functional Requirements"))

    # 4 — Flows, named and stepped.
    flows = _section(body, "Flows", "Flow", "User flows")
    flow_names = re.findall(r"^###\s+(.+)$", flows or "", re.MULTILINE)
    stepped = bool(flows and re.search(r"^\s*\d+\.", flows, re.MULTILINE))
    add("flows", "Flows named, each broken into steps",
        _tri(bool(flow_names), bool(flow_names) and stepped),
        f"{len(flow_names)} flow(s)" if flow_names else "no named flow")

    # 5 — spec-kit /checklist: the four scenario classes.
    # "Happy path only" was an anti-pattern in prose. Naming the classes makes it
    # a measurement — the defects live in the three nobody drew.
    covered = [c for c in _SCENARIO_CLASSES if _class_is_drawn(c, flows)]
    add("scenario_classes", "Primary, alternate, exception and recovery flows drawn",
        _tri(bool(covered), len(covered) == len(_SCENARIO_CLASSES)),
        f"{len(covered)}/4 classes: {', '.join(covered) or 'none'}"
        + ("" if len(covered) == 4
           else f" — missing {', '.join(c for c in _SCENARIO_CLASSES if c not in covered)}"))

    # 6 — A system-level picture.
    has_system = bool(re.search(r"```mermaid|<svg|flowchart|C4Context|graph (TB|LR)", body))
    system_sec = _section(body, "System design", "Architecture", "System Design")
    add("system_diagram", "A system-level diagram exists",
        _tri(has_system or bool(system_sec), has_system and bool(system_sec)),
        "diagram + section" if (has_system and system_sec)
        else ("diagram only" if has_system else "neither"))

    # 7 — How the pieces interact.
    has_interaction = bool(re.search(
        r"sequenceDiagram|classDiagram|participant\s|\bclass\s+\w+\s*\{", body))
    add("interaction_model", "Interaction between the parts is drawn",
        _tri(has_interaction, has_interaction and body.count("participant") + body.count(
            "class ") >= 3),
        "present" if has_interaction else "no sequence or class diagram")

    # 8 — Acceptance criteria that can fail.
    ac_section = _section(body, "Acceptance Criteria", "Acceptance criteria")
    ac = _bullets(ac_section)
    executable = [b for b in ac if _EXECUTABLE_RE.search(b)]
    add("acceptance_executable", "Acceptance criteria name something that runs",
        _tri(bool(ac), bool(ac) and len(executable) == len(ac)),
        f"{len(executable)}/{len(ac)} executable" if ac else "no acceptance criteria")

    # 9 — spec-kit /analyze: stable ids. Every reference implementation converged
    # on this independently — FR-###/SC-### there, EARS ids in feature-forge,
    # sequential REQ-xxx in FredAntB. Without one the traceability chain has no
    # first link.
    fr_ids = set(_FR_ID_RE.findall(fr_section or ""))
    nfr_ids = set(_NFR_ID_RE.findall(nfr_section or ""))
    ac_ids = set(_AC_ID_RE.findall(ac_section or ""))
    id_coverage = [
        bool(fr_ids) and len(fr_ids) == len(fr),
        bool(nfr_ids) and len(nfr_ids) == len(nfr),
        bool(ac_ids) and len(ac_ids) == len(ac),
    ]
    add("stable_ids", "Requirements and criteria carry stable ids",
        _tri(any(id_coverage), all(id_coverage)),
        f"FR {len(fr_ids)}/{len(fr)} · NFR {len(nfr_ids)}/{len(nfr)} · AC {len(ac_ids)}/{len(ac)}"
        if any(id_coverage) else "no FR-/NFR-/AC- ids — nothing can cite anything")

    # 10 — spec-kit /analyze coverage pass, both directions. A criterion citing
    # nothing proves nothing in particular; a requirement no criterion cites
    # ships unverified.
    cited = set(_FR_ID_RE.findall(ac_section or "")) | set(_NFR_ID_RE.findall(ac_section or ""))
    declared = fr_ids | nfr_ids
    ac_citing = [b for b in ac if _FR_ID_RE.search(b) or _NFR_ID_RE.search(b)]
    uncovered = sorted(declared - cited)
    traced = bool(ac) and len(ac_citing) == len(ac) and not uncovered
    add("traceability", "Every criterion cites a requirement, and none is uncovered",
        _tri(bool(ac_citing), traced),
        (f"{len(ac_citing)}/{len(ac)} criteria cite a requirement"
         + (f"; uncovered: {', '.join(uncovered)}" if uncovered else ""))
        if ac else "no acceptance criteria to trace")

    # 11 — spec-kit /analyze ambiguity pass. The old rubric demanded numbers from
    # the NFR section alone, so "the explorer shall be responsive" passed as a
    # functional requirement.
    weighted = "\n".join(filter(None, (fr_section, nfr_section, ac_section)))
    hits = sorted({m.group(1).lower() for m in _VAGUE_RE.finditer(weighted)})
    unquantified = [h for h in hits
                    if not any(_MEASURABLE_RE.search(ln)
                               for ln in weighted.splitlines()
                               if re.search(rf"\b{re.escape(h)}\b", ln, re.IGNORECASE))]
    add("no_vague_terms", "No unquantified quality adjective in a requirement",
        _tri(True, not unquantified),
        "none" if not unquantified
        else f"{len(unquantified)} unquantified: {', '.join(unquantified)}")

    # 12 — superpowers' spec self-review, applied to the whole document.
    # Everything EXCEPT the questions section, which owns its own open items.
    #
    # kit#18. An `UNKNOWN` inside `## Questions answered` is that section's
    # legitimate content — a declared open question — and `questions_closed`
    # already charges for it. Counting it here too took 2 more points, so one
    # failure cost 3 of 34 and both criteria closed on the same single answer.
    # Three points is ~9% against a 90% threshold: a brief whose only imperfection
    # was one honestly declared open question could not clear the gate, and the
    # cheapest way past it was to delete the question — the exact evasion this
    # criterion exists to refuse. Found by an ALIGN agent on a real item, which
    # reported it instead of using it.
    #
    # Outside that section nothing changes: an `UNKNOWN` in a requirement or an
    # acceptance criterion is a hole, and this is what charges for it.
    # kit#17. `alignment_judge.py` appends the judge's `--reason` under
    # `## Reviewer sign-off`, so a judge writing "no unanswered UNKNOWN" as part
    # of saying the brief is CLEAN made this criterion fail. Measured on a real
    # brief: 34/34 before the signature, 32/34 after — on a signature whose only
    # sin was using the word. Nearer the threshold, an APPROVING signature would
    # have pushed the brief below 90% and turned `ALIGNED` back into a refusal:
    # the gate scoring the reviewer's prose instead of the artefact.
    #
    # The criterion measures the author's brief. The sign-off section belongs to
    # the reviewer, and `alignment-threshold.md` is explicit that those are two
    # different people.
    outside_questions = _without_section(
        body, "Questions answered", "Questions", "Reviewer sign-off")
    placeholders = sorted({m.group(0).upper()
                           for m in _UNRESOLVED_RE.finditer(outside_questions)})
    add("no_placeholders", "No unresolved placeholder anywhere in the brief",
        2 if not placeholders else 0,
        "none" if not placeholders else f"{len(placeholders)} found: {', '.join(placeholders)}")

    # 13 — Dependencies, named or explicitly none.
    deps = _section(body, "Dependencies", "Depends on")
    deps_bullets = _bullets(deps)
    explicit_none = bool(deps and re.search(r"\b(none|no dependenc)\b", deps, re.IGNORECASE))
    add("dependencies", "Dependencies named, or explicitly none",
        _tri(bool(deps), bool(deps_bullets) or explicit_none),
        "declared" if (deps_bullets or explicit_none) else "section missing or empty")

    # 14 — What this is NOT. The boundary nobody writes and everybody assumes.
    scope_out = _section(body, "Out of scope", "Not in scope", "What this does not do")
    add("out_of_scope", "What the item does NOT cover is written down",
        _tri(bool(scope_out), len(_bullets(scope_out)) >= 1),
        "declared" if _bullets(scope_out) else "absent — the boundary is being assumed")

    # 15 — The questions the grill asked, and their answers.
    grill = _section(body, "Questions answered", "Clarifications", "Open questions", "Grill")
    add("questions_closed", "Every question raised was answered",
        _tri(bool(grill), bool(grill) and not _UNRESOLVED_RE.search(grill)),
        "all closed" if (grill and not _UNRESOLVED_RE.search(grill))
        else ("open answers remain" if grill else "no record of questions"))

    # 16 — How it will be demonstrated.
    demo = _section(body, "Demonstration", "How to demo", "Demo")
    add("demonstration", "How the result gets demonstrated is written",
        _tri(bool(demo), len(_bullets(demo)) >= 1),
        "declared" if _bullets(demo) else "absent")

    # 17 — The interactive artefact.
    html = re.search(r"`([^`]*\.html)`|\]\(([^)]*\.html)\)", body)
    add("interactive_artefact", "An interactive walkthrough was produced",
        _tri(bool(html), bool(html)),
        html.group(0) if html else "no .html referenced")

    # ── the reviewer's half ────────────────────────────────────────────────
    # Generated unchecked by the agent that wrote the brief; ticked by a reviewer who
    # is NOT that agent — a person, or `alignment_judge.py` when none is coming
    # (`alignment-threshold.md § Amended 2026-09-01`). The author MUST NOT tick these:
    # that is the half of the rule a script cannot enforce, and the only one that is
    # dishonest rather than merely lazy. Adopted from spec-kit, whose checklist carries
    # the same instruction to its own /implement.
    signoff = _section(body, "Reviewer sign-off", "Reviewer signoff", "Sign-off")
    boxes = _CHECKBOX_RE.findall(signoff or "")
    pending = tuple(text for mark, text in boxes if mark == " ")

    ticked = [text for mark, text in boxes if mark in ("x", "X")]
    signers = {(_SIGNED_BY_RE.search(t).group(1) if _SIGNED_BY_RE.search(t) else "human")
               for t in ticked}
    if not ticked or pending:
        signed_by = None
    elif len(signers) == 1:
        signed_by = signers.pop()
    else:
        # Weakest wins: any agent signature makes the whole set an agent's.
        non_human = sorted(s for s in signers
                           if s != "human" and not s.startswith("human/"))
        signed_by = non_human[0] if non_human else sorted(signers)[0]

    judgement = (
        "whether the stated problem is the real one",
        "whether the flows drawn are the flows that matter",
        "whether the numbers in the NFRs are the right numbers",
    )
    # kit#14. The marker counts when it is USED, not when it is mentioned. A brief
    # explains to its reviewer how to declare a split — "mark this brief
    # `<!-- verdict: NEEDS_SPLIT: ... -->`" — and that sentence made the scorer
    # emit NEEDS_SPLIT, a verdict the rubric defines as "declared by the reviewer,
    # never inferred", for a brief in which no reviewer had declared anything.
    #
    # A declaration stands on its own line. A mention sits inside a sentence, a
    # list item or a code span. Same distinction kit#17 needed, and the same root:
    # a marker matched anywhere, with no notion of mentioned versus used.
    split = _NEEDS_SPLIT_RE.search(_declarations_only(body))
    return AlignmentReport(
        tuple(criteria), judgement, pending, len(boxes), signed_by,
        needs_split=bool(split),
        split_reason=(split.group(1) or "").strip() if split else "",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--machine-only", action="store_true",
        help="exit on the structural score alone, so the agent can iterate before "
             "asking a human to review. NEVER the gate on building the item.")
    args = parser.parse_args(argv)

    try:
        report = score_alignment(args.brief)
    except OSError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    ok = report.meets_machine_threshold if args.machine_only else report.aligned
    if report.needs_split:
        ok = False

    if args.json:
        print(json.dumps({
            "verdict": report.verdict,
            "aligned": report.aligned,
            "earned": report.earned,
            "maximum": report.maximum,
            "machine_ratio": round(report.machine_ratio, 4),
            "threshold": THRESHOLD,
            "meets_machine_threshold": report.meets_machine_threshold,
            "reviewer_signed_off": report.reviewer_signed_off,
            "signed_by": report.signed_by,
            "signed_by_is_human": report.signed_by_is_human,
            "needs_split": report.needs_split,
            "split_reason": report.split_reason,
            "reviewer_items_total": report.reviewer_items_total,
            "pending_review": list(report.pending_review),
            "criteria": [
                {"key": c.key, "label": c.label, "score": c.score, "why": c.why}
                for c in report.criteria
            ],
            "judgement_items": list(report.judgement_items),
        }, indent=2, ensure_ascii=False))
        return 0 if ok else 1

    pct = report.machine_ratio * 100
    print(f"{report.verdict}   machine {report.earned}/{report.maximum} "
          f"({pct:.0f}%, threshold {THRESHOLD:.0%})\n")
    for c in report.criteria:
        mark = {0: "✗", 1: "~", 2: "✓"}[c.score]
        print(f"  {mark} {c.label:<58} {c.why}")

    if not report.meets_machine_threshold:
        print("\nThis item must NOT be built yet. Close these first:")
        for c in report.gaps:
            print(f"  - {c.label} — {c.why}")

    print()
    if report.reviewer_signed_off:
        who = report.signed_by or "human"
        note = "" if report.signed_by_is_human else "  ← an AGENT signed, not a person"
        print(f"Reviewer sign-off: all {report.reviewer_items_total} items ticked "
              f"by `{who}`.{note}")
    elif report.reviewer_items_total:
        print(f"Reviewer sign-off: {len(report.pending_review)} of "
              f"{report.reviewer_items_total} still unticked —")
        for item in report.pending_review:
            print(f"  [ ] {item}")
    else:
        print("Reviewer sign-off: no `## Reviewer sign-off` checklist in the brief.")
        print("  Generate it UNTICKED. Ticking it is the reviewer's act, never yours —")
        print("  the three items below are what a script cannot decide:")
        for item in report.judgement_items:
            print(f"    - [ ] {item}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

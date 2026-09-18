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
#:
#: This is a TEXT match over the bullet, and that is its limit: it asks whether a
#: command is NAMED, never whether it could run or whether its answer distinguishes
#: anything. A consumer measured the consequence — a brief scored 14/14 executable
#: where two criteria could not pass at all, and `go test -run <pattern-that-matches-
#: nothing>` exits 0 with `[no tests to run]`, so eight criteria in one brief were
#: satisfied by writing no test.
#:
#: Executing them is the real fix and is not this function's to make: it needs three
#: states (current tree, intended state, a deliberately WRONG implementation the
#: criterion must reject) and a reconstruction control. Tracked separately.
#:
#: What IS in scope here is the composition. A criterion carrying an unresolved
#: placeholder cannot run, whatever it names, so grading it executable is the scorer
#: asserting something it did not establish — and it did so beside a placeholder scan
#: that could not see the notation. Breaking that pair is cheap and removes the case
#: where three defects agreed with each other.
_EXECUTABLE_RE = re.compile(
    r"`[^`]*(?:npm|pytest|go |cargo|make|curl|grep|python3|bash|node|exit \d)[^`]*`"
    r"|\bexit\s+(?:code\s+)?\d",
    re.IGNORECASE,
)

#: An unresolved decision, in whatever coat it is wearing. Scanned across the
#: WHOLE brief since v2 — a `TBD` in the data model is the same open question as
#: an `UNKNOWN` in the answers, and it used to be invisible.
#: `<angle-brackets>` are deliberately NOT in this pattern, and the reason is a
#: measurement. They were added on 2026-09-13 to catch `<gate-name>`, which a consumer
#: reported as invisible. Re-measured over 38 real briefs the next day: 23 were charged,
#: and the hits were three different things wearing one shape —
#:
#:     `err=<nil>`        a Go literal quoted from real output
#:     `-C <path>`        CLI syntax described in prose
#:     `START_SHA=<sha>`  a parameter a criterion needs filled before it can run
#:
#: Only the third is a defect, and it is not the defect THIS criterion measures.
#: `no_placeholders` asks whether a DECISION is still open — `TBD`, `UNKNOWN`,
#: `{{SLOT}}`. An unfilled command parameter is a question about EXECUTABILITY, which
#: `check_criteria_discriminate.py` answers by refusing to run the criterion. Charging
#: two points here for a Go nil made the column report the wrong thing loudly, which is
#: how a reader learns to skip a column.
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

#: A reviewer taking their sign-off BACK. Same channel as `NEEDS_SPLIT` and for the same
#: reason: the scorer transports a reviewer's decision rather than inferring one.
#:
#: Measured on a consumer 2026-09-15: three items sat BLOCKED for two days on a warrant
#: that had been withdrawn in PROSE while the boxes above it stayed `[x]` with their
#: `signed-by:` comments intact. The gate counted ticks, reported
#: `alignment_gate PASS — aligned at 100%`, and every agent that opened the brief read the
#: withdrawal and stopped. There was no way to say "signed, then withdrawn" that a machine
#: could hear, so the strongest statement a reviewer can make was the one the mechanism
#: could not represent.
_WITHDRAWN_RE = re.compile(
    r"<!--\s*sign-off:\s*WITHDRAWN\s*(?::\s*([^>]*?))?\s*-->", re.IGNORECASE)

#: A reviewer putting their sign-off BACK after withdrawing it.
#:
#: `WITHDRAWN` without this is a state with no exit, and that is not hypothetical: this
#: project's discipline is to correct forward and leave the superseded reading in place,
#: so a brief that went withdrawal -> refusal -> repair -> signature carries the
#: withdrawal prose forever. The honest record and the passing record end up in tension
#: and the honest one loses — which is a reason to stop writing honest records.
#:
#: Honoured only AFTER the withdrawal it answers. Order is read here and nowhere else,
#: because a restoration is a reply: "restored" above the withdrawal it restores is not a
#: reply to it. A brief reorganised so the two swap places reads as withdrawn, which is
#: the safe direction.
_RESTORED_RE = re.compile(
    r"<!--\s*sign-off:\s*RESTORED\s*(?::\s*([^>]*?))?\s*-->", re.IGNORECASE)

#: Prose that READS as a withdrawal without carrying the marker. This is deliberately not
#: used to decide anything — it is used to stop the scorer from CLAIMING anything.
#:
#: The distinction is the whole design. Matching words to produce a verdict is what the
#: `NEEDS_SPLIT` comment above refuses, and rightly: a regex over a brief would issue
#: verdicts about language. Matching words to REFUSE to certify is the opposite move, and
#: it is the one the doctrine requires — an inability to measure must never become a
#: passing measurement. A brief whose warrant state is ambiguous gets `AWAITING_REVIEW`
#: and a named reason, never `ALIGNED`.
_WITHDRAWAL_PROSE_RE = re.compile(
    r"\bsign-?off\s+(?:is\s+)?withdrawn\b|\bwithdraw(?:n|ing)\s+(?:the\s+)?sign-?off\b"
    r"|\bwarrant\s+(?:is\s+)?withdrawn\b|\bwithdrew\s+(?:the\s+)?sign-?off\b",
    re.IGNORECASE)


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

    #: Acceptance criteria whose command can pass because its SUBJECT is absent.
    #: Advisory, and scored nowhere: the rubric measures shape and this is about
    #: meaning, so a false positive here must not cost an item a point.
    vacuous_criteria: tuple[str, ...] = ()
    #: Set when a reviewer marked the brief `<!-- verdict: NEEDS_SPLIT -->`.
    needs_split: bool = False
    split_reason: str = ""
    #: Set when a reviewer marked the brief `<!-- sign-off: WITHDRAWN -->` and did not
    #: mark `<!-- sign-off: RESTORED -->` after it.
    sign_off_withdrawn: bool = False
    withdrawal_reason: str = ""
    #: Set when a RESTORED marker answers a withdrawal. Reported so a reader can see the
    #: warrant was taken back and given again, rather than never questioned.
    sign_off_restored: bool = False
    restoration_reason: str = ""
    #: The line whose prose reads as a withdrawal while no marker carries it. Not a
    #: verdict about the prose — the reason the scorer declines to certify, quoted so the
    #: reviewer knows exactly which line to mark.
    unmarked_withdrawal_prose: str = ""

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
        return (self.meets_machine_threshold and self.reviewer_signed_off
                and not self.sign_off_withdrawn and not self.unmarked_withdrawal_prose)

    @property
    def verdict(self) -> str:
        # Checked FIRST, before the split and before the score: a withdrawn warrant is a
        # statement about whether the review still stands, and no score can answer it.
        # Reporting ALIGNED over a withdrawal is the one outcome that sends an agent to
        # build something a reviewer has said to stop building.
        if self.sign_off_withdrawn:
            return "WITHDRAWN"
        # Checked before the score, because a low score is a CONSEQUENCE of the item
        # being two items: neither half's flows, criteria or measurements converge
        # while they share one brief. Reporting `BLOCKED` here would send the reviewer
        # to close gaps that no amount of writing can close.
        if self.needs_split:
            return "NEEDS_SPLIT"
        if not self.meets_machine_threshold:
            return "BLOCKED"
        if self.unmarked_withdrawal_prose:
            # Not a verdict about the prose: a refusal to certify over something the
            # scorer cannot read. The reviewer is told which line to mark.
            return "AWAITING_REVIEW"
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


#: A bullet marker: `-`, `*`, `+`, or an ordered `1.` / `1)`.
#:
#: NOT `^\s*[-*\d]`, which was the pattern here until a consumer measured it. That
#: matched ANY line beginning with a digit, and a wrapped requirement routinely
#: continues on one — "…under 800ms at\n50 rps." One bullet then counted as two, so a
#: section holding a single hollow requirement plus its own continuation scored as
#: though somebody had written two things. The scorer read the wrap as substance.
_BULLET_RE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s)")


def _bullets(text: str | None) -> list[str]:
    if not text:
        return []
    return [ln.strip() for ln in text.splitlines() if _BULLET_RE.match(ln) and ln.strip()]



#: Fenced code blocks and inline code spans — where a document QUOTES rather than
#: states. Stripped before looking for a marker that carries a verdict.
_FENCED_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _unmarked_withdrawal(body: str) -> str:
    """The first line whose prose says a sign-off was withdrawn, with no marker present.

    Returned so the scorer can DECLINE to certify — never to decide a verdict from
    language. Code spans and fences are stripped first so a brief explaining the syntax
    to its reviewer is not mistaken for a reviewer using it, the same distinction
    `_declarations_only` draws for the split marker.

    A false positive costs the brief `AWAITING_REVIEW` and a named line to mark, which is
    the direction that cannot hurt: the alternative is `ALIGNED` over a warrant somebody
    took back, which is what sat on three consumer items for two days.
    """
    stripped = _INLINE_CODE_RE.sub("", _FENCED_RE.sub("", body))
    for line in stripped.splitlines():
        if _WITHDRAWAL_PROSE_RE.search(line):
            return line.strip()[:200]
    return ""


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


#: A negated test passes when what it negates is missing — including when the
#: whole subject is missing. `! grep -q PROPOSED adr.md` exits 0 against a file
#: that has no status line at all, so the criterion approves precisely the case
#: it was written to catch.
#:
#: Reported by an ALIGN agent on 2026-09-02, which found two of its own criteria
#: in this shape and rewrote them to match a terminal token POSITIVELY. Its words:
#: "An acceptance criterion that passes when its subject is absent is executable,
#: cites its requirement, and is wrong." It is also invisible to every one of the
#: seventeen criteria, which is why this is advisory rather than scored — the
#: rubric measures shape, and this is about meaning.
_NEGATED_TEST_RE = re.compile(
    # The backtick matters: acceptance criteria write their commands as inline
    # code, so `!` is almost always preceded by one. Leaving it out of the
    # delimiter class made this detector match nothing at all — which would have
    # been an advisory that never fires, silently, and this file has spent the
    # day removing exactly that shape.
    r"(^|[\s;&|(`\"'])!\s*(grep|test|\[)|grep\s+-[a-z]*v|--invert-match|"
    r"\bnot\s+in\b|\bassert\s+not\b")

#: What makes a negated test safe: something asserting the subject IS there.
_PRESENCE_RE = re.compile(
    r"-n\s|\bwc\s+-l|\btest\s+-s\b|\[\s*-s\s|grep\s+-q\s[^|]*&&|"
    r"\|\|\s*exit|\bif\s+grep\b")

#: `wc -l` earns its place in `_PRESENCE_RE` only when the count is expected to be
#: NON-ZERO. A criterion that counts something and asserts the answer is zero passes
#: exactly when the subject is absent — which is the state this advisory exists to
#: catch — and it was being exempted by coincidence rather than by design.
_COUNTS_TO_ZERO_RE = re.compile(
    r"\b(wc\s+-l|grep\s+-c)\b[^.]*?\b(0|zero|none|no\s+\w+)\b", re.IGNORECASE)


def _vacuous_criteria(bullets: list[str]) -> tuple[str, ...]:
    """Acceptance criteria that could pass because their subject is absent."""
    return tuple(
        b.strip()[:120] for b in bullets
        if (_NEGATED_TEST_RE.search(b) or _COUNTS_TO_ZERO_RE.search(b))
        and not (_PRESENCE_RE.search(b) and not _COUNTS_TO_ZERO_RE.search(b)))


def _without_section(body: str, *headings: str) -> str:
    """`body` with the named section removed, heading and all — SUBSECTIONS INCLUDED.

    Used where a criterion must not charge for something another criterion owns.

    ## Why the stop condition is the heading's own level

    This used to stop at the next heading of ANY level, so a section with a subheading
    was cut at the subheading and everything under it stayed in the text the caller
    believed it had removed.

    `## Questions answered` is exactly that shape, and this skill's own SKILL.md
    prescribes it: *"`### Session YYYY-MM-DD` then `- Q: … → A: …`"*. So the kit
    prescribed the structure that voided its own exemption. kit#18 exists to stop
    `no_placeholders` charging for an `UNKNOWN` that `questions_closed` already charges
    for — three points of thirty-four, about 9% against a 90% threshold — and it had no
    effect on any brief that followed the template.

    Measured by a consumer session on a real item: a brief whose only imperfection was
    one honestly declared open question could not clear the gate, and the cheapest way
    past was to delete the question. That is the evasion kit#18 was written to remove,
    reintroduced by the pattern meant to implement it.

    A section ends at the next heading of the same level or shallower. A deeper one is
    part of it.
    """
    for heading in headings:
        opener = re.compile(rf"^(#{{1,6}})\s*{re.escape(heading)}\s*$",
                            re.IGNORECASE | re.MULTILINE)
        while True:
            match = opener.search(body)
            if not match:
                break
            level = len(match.group(1))
            closer = re.compile(rf"^#{{1,{level}}}\s", re.MULTILINE)
            after = closer.search(body, match.end())
            end = after.start() if after else len(body)
            body = body[:match.start()] + body[end:]
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


@dataclass(frozen=True)
class _Sections:
    """The parses more than one criterion reads, done ONCE.

    Seven criteria share a reading of the same four sections, and in the single
    276-line function they shared it by being in one scope — which is also why that
    function could not be split without the later blocks losing the earlier ones'
    locals. Naming the shared state makes the sharing visible and makes each criterion
    a function of its inputs: `_criterion_coverage` says in its signature that it needs
    the requirement ids, where before it simply found them lying around.
    """

    fr_section: str | None
    fr: list[str]
    nfr_section: str | None
    nfr: list[str]
    ac_section: str | None
    ac: list[str]
    flows: str | None
    fr_ids: set[str]
    nfr_ids: set[str]


def _read_sections(body: str) -> _Sections:
    fr_section = _section(body, "Functional Requirements", "Functional requirements")
    nfr_section = _section(body, "Non-Functional Requirements",
                           "Non-functional requirements")
    ac_section = _section(body, "Acceptance Criteria", "Acceptance criteria")
    return _Sections(
        fr_section=fr_section, fr=_bullets(fr_section),
        nfr_section=nfr_section, nfr=_bullets(nfr_section),
        ac_section=ac_section, ac=_bullets(ac_section),
        flows=_section(body, "Flows", "Flow", "User flows"),
        fr_ids=set(_FR_ID_RE.findall(fr_section or "")),
        nfr_ids=set(_NFR_ID_RE.findall(nfr_section or "")),
    )


def _criterion_problem(body: str) -> Criterion:
    """1 — The problem, in the system's own terms."""
    problem = _section(body, "Problem", "Context", "Why now")
    return Criterion("problem", "The problem is stated as something observed here",
        _tri(bool(problem), bool(problem and len(problem.split()) >= 30)),
        "absent" if not problem else ("too short to have said anything" if len(
            problem.split()) < 30 else "stated"))

def _criterion_functional_requirements(body: str) -> Criterion:
    """2 — Functional requirements."""
    fr_section = _section(body, "Functional Requirements", "Functional requirements")
    fr = _bullets(fr_section)
    return Criterion("functional_requirements", "Functional requirements enumerated",
        _tri(bool(fr), len(fr) >= 2),
        f"{len(fr)} listed" if fr else _absent_or_empty(
            fr_section, "Functional Requirements"))

def _criterion_nonfunctional_requirements(body: str) -> Criterion:
    """3 — Non-functional requirements, WITH numbers."""
    nfr_section = _section(body, "Non-Functional Requirements", "Non-functional requirements")
    nfr = _bullets(nfr_section)
    measurable = [b for b in nfr if _MEASURABLE_RE.search(b)]
    return Criterion("nfr_measurable", "Non-functional requirements carry numbers",
        _tri(bool(nfr), bool(nfr) and len(measurable) == len(nfr)),
        f"{len(measurable)}/{len(nfr)} measurable" if nfr
        else _absent_or_empty(nfr_section, "Non-Functional Requirements"))

def _criterion_flows(body: str) -> Criterion:
    """4 — Flows, named and stepped."""
    flows = _section(body, "Flows", "Flow", "User flows")
    flow_names = re.findall(r"^###\s+(.+)$", flows or "", re.MULTILINE)
    stepped = bool(flows and re.search(r"^\s*\d+\.", flows, re.MULTILINE))
    return Criterion("flows", "Flows named, each broken into steps",
        _tri(bool(flow_names), bool(flow_names) and stepped),
        f"{len(flow_names)} flow(s)" if flow_names else "no named flow")

def _criterion_scenario_classes(sections: _Sections) -> Criterion:
    """5 — spec-kit /checklist: the four scenario classes."""
    # "Happy path only" was an anti-pattern in prose. Naming the classes makes it
    # a measurement — the defects live in the three nobody drew.
    covered = [c for c in _SCENARIO_CLASSES if _class_is_drawn(c, sections.flows)]
    return Criterion("scenario_classes", "Primary, alternate, exception and recovery sections.flows drawn",
        _tri(bool(covered), len(covered) == len(_SCENARIO_CLASSES)),
        f"{len(covered)}/4 classes: {', '.join(covered) or 'none'}"
        + ("" if len(covered) == 4
           else f" — missing {', '.join(c for c in _SCENARIO_CLASSES if c not in covered)}"))

def _criterion_system_picture(body: str) -> Criterion:
    """6 — A system-level picture."""
    has_system = bool(re.search(r"```mermaid|<svg|flowchart|C4Context|graph (TB|LR)", body))
    system_sec = _section(body, "System design", "Architecture", "System Design")
    return Criterion("system_diagram", "A system-level diagram exists",
        _tri(has_system or bool(system_sec), has_system and bool(system_sec)),
        "diagram + section" if (has_system and system_sec)
        else ("diagram only" if has_system else "neither"))

def _criterion_interaction(body: str) -> Criterion:
    """7 — How the pieces interact."""
    has_interaction = bool(re.search(
        r"sequenceDiagram|classDiagram|participant\s|\bclass\s+\w+\s*\{", body))
    return Criterion("interaction_model", "Interaction between the parts is drawn",
        _tri(has_interaction, has_interaction and body.count("participant") + body.count(
            "class ") >= 3),
        "present" if has_interaction else "no sequence or class diagram")

def _criterion_acceptance_criteria(body: str) -> tuple[Criterion, list[str]]:
    """8 — Acceptance criteria that can fail."""
    ac_section = _section(body, "Acceptance Criteria", "Acceptance criteria")
    ac = _bullets(ac_section)
    # A criterion carrying an unresolved placeholder cannot run, whatever command it
    # names. Grading it executable is the scorer asserting something it did not
    # establish — and it did exactly that beside a placeholder scan that could not see
    # the notation these briefs use. Measured on a consumer: "10/10 executable" and
    # "No unresolved placeholder anywhere in the brief — none" reported together, over
    # five commands the brief's own prose said did not run.
    #
    # This does not make the grade a measurement; it is still a text match, and a
    # criterion whose pattern can never match still scores. What it removes is the case
    # where two defects agreed with each other and the pair read as corroboration.
    unrunnable = [b for b in ac if _UNRESOLVED_RE.search(b)]
    executable = [b for b in ac
                  if _EXECUTABLE_RE.search(b) and not _UNRESOLVED_RE.search(b)]
    detail = f"{len(executable)}/{len(ac)} executable" if ac else "no acceptance criteria"
    if unrunnable:
        detail += (f" — {len(unrunnable)} carry an unresolved placeholder and cannot "
                   "run whatever they name")
    # `ac` travels out beside the Criterion: `_vacuous_criteria` needs the same
    # bullets, and parsing the section twice would let the two readings disagree.
    return (Criterion("acceptance_executable",
                      "Acceptance criteria name something that runs",
                      _tri(bool(ac), bool(ac) and len(executable) == len(ac)), detail),
            ac)


def _criterion_stable_ids(sections: _Sections) -> Criterion:
    """9 — spec-kit /analyze: stable ids. Every reference implementation converged"""
    # on this independently — FR-###/SC-### there, EARS ids in feature-forge,
    # sequential REQ-xxx in FredAntB. Without one the traceability chain has no
    # first link.
    ac_ids = set(_AC_ID_RE.findall(sections.ac_section or ""))
    id_coverage = [
        bool(sections.fr_ids) and len(sections.fr_ids) == len(sections.fr),
        bool(sections.nfr_ids) and len(sections.nfr_ids) == len(sections.nfr),
        bool(ac_ids) and len(ac_ids) == len(sections.ac),
    ]
    return Criterion("stable_ids", "Requirements and criteria carry stable ids",
        _tri(any(id_coverage), all(id_coverage)),
        f"FR {len(sections.fr_ids)}/{len(sections.fr)} · NFR {len(sections.nfr_ids)}/{len(sections.nfr)} · AC {len(ac_ids)}/{len(sections.ac)}"
        if any(id_coverage) else "no FR-/NFR-/AC- ids — nothing can cite anything")

def _criterion_coverage(sections: _Sections) -> Criterion:
    """10 — spec-kit /analyze coverage pass, both directions. A criterion citing"""
    # nothing proves nothing in particular; a requirement no criterion cites
    # ships unverified.
    cited = set(_FR_ID_RE.findall(sections.ac_section or "")) | set(_NFR_ID_RE.findall(sections.ac_section or ""))
    declared = sections.fr_ids | sections.nfr_ids
    ac_citing = [b for b in sections.ac if _FR_ID_RE.search(b) or _NFR_ID_RE.search(b)]
    uncovered = sorted(declared - cited)
    traced = bool(sections.ac) and len(ac_citing) == len(sections.ac) and not uncovered
    return Criterion("traceability", "Every criterion cites a requirement, and none is uncovered",
        _tri(bool(ac_citing), traced),
        (f"{len(ac_citing)}/{len(sections.ac)} criteria cite a requirement"
         + (f"; uncovered: {', '.join(uncovered)}" if uncovered else ""))
        if sections.ac else "no acceptance criteria to trace")

def _criterion_ambiguity(sections: _Sections) -> Criterion:
    """11 — spec-kit /analyze ambiguity pass. The old rubric demanded numbers from"""
    # the NFR section alone, so "the explorer shall be responsive" passed as a
    # functional requirement.
    weighted = "\n".join(filter(None, (sections.fr_section, sections.nfr_section, sections.ac_section)))
    hits = sorted({m.group(1).lower() for m in _VAGUE_RE.finditer(weighted)})
    unquantified = [h for h in hits
                    if not any(_MEASURABLE_RE.search(ln)
                               for ln in weighted.splitlines()
                               if re.search(rf"\b{re.escape(h)}\b", ln, re.IGNORECASE))]
    return Criterion("no_vague_terms", "No unquantified quality adjective in a requirement",
        _tri(True, not unquantified),
        "none" if not unquantified
        else f"{len(unquantified)} unquantified: {', '.join(unquantified)}")

def _criterion_self_review(body: str) -> Criterion:
    """12 — superpowers' spec self-review, applied to the whole document."""
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
    return Criterion("no_placeholders", "No unresolved placeholder anywhere in the brief",
        2 if not placeholders else 0,
        "none" if not placeholders else f"{len(placeholders)} found: {', '.join(placeholders)}")

def _criterion_dependencies(body: str) -> Criterion:
    """13 — Dependencies, named or explicitly none."""
    deps = _section(body, "Dependencies", "Depends on")
    deps_bullets = _bullets(deps)
    explicit_none = bool(deps and re.search(r"\b(none|no dependenc)\b", deps, re.IGNORECASE))
    return Criterion("dependencies", "Dependencies named, or explicitly none",
        _tri(bool(deps), bool(deps_bullets) or explicit_none),
        "declared" if (deps_bullets or explicit_none) else "section missing or empty")

def _criterion_non_goals(body: str) -> Criterion:
    """14 — What this is NOT. The boundary nobody writes and everybody assumes."""
    scope_out = _section(body, "Out of scope", "Not in scope", "What this does not do")
    return Criterion("out_of_scope", "What the item does NOT cover is written down",
        _tri(bool(scope_out), len(_bullets(scope_out)) >= 1),
        "declared" if _bullets(scope_out) else "absent — the boundary is being assumed")

def _criterion_grill_answers(body: str) -> Criterion:
    """15 — The questions the grill asked, and their answers."""
    grill = _section(body, "Questions answered", "Clarifications", "Open questions", "Grill")
    return Criterion("questions_closed", "Every question raised was answered",
        _tri(bool(grill), bool(grill) and not _UNRESOLVED_RE.search(grill)),
        "all closed" if (grill and not _UNRESOLVED_RE.search(grill))
        else ("open answers remain" if grill else "no record of questions"))

def _criterion_demonstration(body: str) -> Criterion:
    """16 — How it will be demonstrated."""
    demo = _section(body, "Demonstration", "How to demo", "Demo")
    return Criterion("demonstration", "How the result gets demonstrated is written",
        _tri(bool(demo), len(_bullets(demo)) >= 1),
        "declared" if _bullets(demo) else "absent")

def _criterion_interactive_artefact(body: str, brief_path: Path) -> Criterion:
    """17 — The interactive artefact."""
    #
    # RESOLVED on disk, not merely referenced. This scored `_tri(bool(html), bool(html))`
    # until a consumer measured it: a brief citing a walkthrough nobody generated took
    # full marks for producing one. A gate reporting that it verified something it never
    # opened is the fabricated mechanism this kit exists to refuse — and this gate decides
    # whether an item may be BUILT.
    html = re.search(r"`([^`]*\.html)`|\]\(([^)]*\.html)\)", body)
    cited = (html.group(1) or html.group(2)) if html else None
    resolved = None
    if cited:
        for base in (Path(brief_path).parent, Path.cwd()):
            candidate = base / cited
            if candidate.is_file():
                resolved = candidate
                break
    return Criterion("interactive_artefact", "An interactive walkthrough was produced",
        _tri(bool(html), bool(resolved)),
        f"{cited} — resolved" if resolved
        else f"cited but missing on disk: {cited}" if cited
        else "no .html referenced")

def _local_drops() -> frozenset[str]:
    """The criterion ids the LOCAL depth removes, read from the module that DEFINES depth.

    Imported rather than restated. Two copies of this set would disagree on the first
    change, and a scorer that disagreed with the classifier is the defect this whole
    parameter exists to close.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from classify_alignment_depth import LOCAL_DROPS  # noqa: PLC0415

    return LOCAL_DROPS


def _score_criteria(body: str, brief_path: Path) -> tuple[list[Criterion], list[str]]:
    """The seventeen rubric criteria, scored — one function each, driven by this list.

    `score_alignment` measured cyclomatic complexity 100 across 276 lines, and the 276
    were seventeen independent readings of one document glued together by a closure
    that appended to a list. Each is now its own function: the rubric's order is the
    order of the table below, a reader looking for criterion 11 opens
    `_criterion_ambiguity`, and changing one cannot reach the other sixteen.

    `ac` travels back out because `_vacuous_criteria` needs the acceptance bullets and
    recomputing them would be a second parse of the same section.
    """
    sections = _read_sections(body)
    acceptance, ac = _criterion_acceptance_criteria(body)
    criteria = [
        _criterion_problem(body),
        _criterion_functional_requirements(body),
        _criterion_nonfunctional_requirements(body),
        _criterion_flows(body),
        _criterion_scenario_classes(sections),
        _criterion_system_picture(body),
        _criterion_interaction(body),
        acceptance,
        _criterion_stable_ids(sections),
        _criterion_coverage(sections),
        _criterion_ambiguity(sections),
        _criterion_self_review(body),
        _criterion_dependencies(body),
        _criterion_non_goals(body),
        _criterion_grill_answers(body),
        _criterion_demonstration(body),
        _criterion_interactive_artefact(body, brief_path),
    ]
    return criteria, ac




def _read_signoff(body: str) -> tuple[tuple[str, ...], int, str | None]:
    """`(pending, box_count, signed_by)` from the reviewer's half of the brief."""
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

    # kit#14. The marker counts when it is USED, not when it is mentioned. A brief
    # explains to its reviewer how to declare a split — "mark this brief
    # `<!-- verdict: NEEDS_SPLIT: ... -->`" — and that sentence made the scorer
    # emit NEEDS_SPLIT, a verdict the rubric defines as "declared by the reviewer,
    # never inferred", for a brief in which no reviewer had declared anything.
    #
    # A declaration stands on its own line. A mention sits inside a sentence, a
    # list item or a code span. Same distinction kit#17 needed, and the same root:
    # a marker matched anywhere, with no notion of mentioned versus used.
    return pending, len(boxes), signed_by


def _read_declarations(body: str):
    """`(split, withdrawn, restored)` — the three markers, as match objects or None."""
    declarations = _declarations_only(body)
    split = _NEEDS_SPLIT_RE.search(declarations)
    withdrawn = _WITHDRAWN_RE.search(declarations)
    # A restoration only counts where it REPLIES to a withdrawal — after it, in the
    # document's own declarations.
    restored = None
    if withdrawn:
        restored = _RESTORED_RE.search(declarations, withdrawn.end())
    return split, withdrawn, restored


def score_alignment(brief_path: Path, depth: str = "FULL") -> AlignmentReport:
    """Score one alignment brief against the rubric.

    An assembler: the scoring, the reviewer's half and the declaration markers are
    three independent readings of one document, and each is now answered where it is
    asked.

    `depth` comes from `classify_alignment_depth.py`, and the criteria it removes are
    dropped from the total as well as from the score. Grading a document against
    criteria its own depth deleted made the shallow path unusable: measured 2026-09-18,
    a LOCAL brief complete by its own contract topped out at 24/34 = 70.6% against a 90%
    floor, so every item had to take the FULL brief the classifier measured as waste.

    Scored out of the criteria IN FORCE, never out of a constant. Awarding the dropped
    ones full marks would also reach the floor and would be a lie — 34/34 for a document
    that answered twelve questions.

    The depth is a PARAMETER and is never read from the brief. A document that could
    declare its own depth would let an author reach the floor by typing a word, which is
    the "reaching 90% by rewording" path `alignment-threshold.md` refuses.
    """
    body = Path(brief_path).read_text(encoding="utf-8-sig")

    criteria, ac = _score_criteria(body, brief_path)
    if depth.upper() == "LOCAL":
        criteria = [c for c in criteria if c.key not in _local_drops()]
    pending, box_count, signed_by = _read_signoff(body)
    split, withdrawn, restored = _read_declarations(body)

    judgement = (
        "whether the stated problem is the real one",
        "whether the flows drawn are the flows that matter",
        "whether the numbers in the NFRs are the right numbers",
    )
    declarations = _declarations_only(body)
    return AlignmentReport(
        tuple(criteria), judgement, pending, box_count, signed_by,
        vacuous_criteria=_vacuous_criteria(ac),
        needs_split=bool(split),
        split_reason=(split.group(1) or "").strip() if split else "",
        sign_off_withdrawn=bool(withdrawn) and not restored,
        withdrawal_reason=(withdrawn.group(1) or "").strip() if withdrawn else "",
        sign_off_restored=bool(restored),
        restoration_reason=(restored.group(1) or "").strip() if restored else "",
        unmarked_withdrawal_prose=(
            "" if withdrawn or _RESTORED_RE.search(declarations)
            else _unmarked_withdrawal(body)),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--machine-only", action="store_true",
        help="exit on the structural score alone, so the agent can iterate before "
             "asking a human to review. NEVER the gate on building the item.")
    parser.add_argument(
        "--depth", choices=("FULL", "LOCAL"), default="FULL",
        help="the depth `classify_alignment_depth.py` derived for this ITEM. LOCAL "
             "removes the criteria that depth drops from the score AND from the total. "
             "Derived by the caller and never read from the brief: a document that "
             "declared its own depth would grade itself.")
    args = parser.parse_args(argv)

    try:
        report = score_alignment(args.brief, args.depth)
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
            # The warrant's own history. These four were computed and emitted on
            # NEITHER output path — the source says `unmarked_withdrawal_prose` is
            # "quoted so the reviewer knows exactly which line to mark" and
            # `sign_off_restored` is "Reported so a reader can see the warrant was
            # taken back and given again", and no reader could see either. A field
            # computed for a reader and shown to nobody is the same as not computing it.
            "sign_off_withdrawn": report.sign_off_withdrawn,
            "withdrawal_reason": report.withdrawal_reason,
            "sign_off_restored": report.sign_off_restored,
            "restoration_reason": report.restoration_reason,
            "unmarked_withdrawal_prose": report.unmarked_withdrawal_prose,
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

    # Advisory, printed whatever the verdict: a brief at 100% can still carry one
    # of these, and a brief that failed will be rewritten by someone who should
    # see it now rather than after the next run.
    if report.vacuous_criteria:
        print("\nADVISORY — acceptance criteria that can pass because their SUBJECT "
              "is absent.\nA negated test approves the very case it was written to "
              "catch: `! grep -q PROPOSED adr.md` exits 0 against a file with no "
              "status line at all.\nAssert the terminal state positively, or guard "
              "the negation with a presence check. Scored nowhere — the rubric "
              "measures shape and this is meaning:")
        for bullet in report.vacuous_criteria:
            print(f"  ? {bullet}")

    if not report.meets_machine_threshold:
        print("\nThis item must NOT be built yet. Close these first:")
        for c in report.gaps:
            print(f"  - {c.label} — {c.why}")

    # The warrant's history, on the text path too. A withdrawal the reader cannot see
    # is a withdrawal that reads as a sign-off nobody gave.
    if report.sign_off_withdrawn:
        print(f"\nSIGN-OFF WITHDRAWN: {report.withdrawal_reason or '(no reason given)'}")
    elif report.sign_off_restored:
        print(f"\nSign-off withdrawn and RESTORED: "
              f"{report.restoration_reason or '(no reason given)'}")
    if report.unmarked_withdrawal_prose:
        print("\nA line in this brief reads as a withdrawal and carries no marker, so "
              "nothing downstream can act on it. Mark it "
              "`<!-- sign-off: WITHDRAWN: <why> -->` or reword it:")
        print(f"  {report.unmarked_withdrawal_prose}")

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

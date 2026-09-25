#!/usr/bin/env python3
"""Score the four product documents, and refuse to sign them itself.

    python3 score_product_alignment.py [--root .] [--json]

WHAT THIS MEASURES, AND WHAT IT REFUSES TO CLAIM
------------------------------------------------
Seventeen criteria over structure — a section exists, an objective carries a
number, a citation resolves, no placeholder survives. The count is not a
coincidence: `skills/plan-alignment/scripts/score_alignment.py` scores an ITEM
on seventeen structural criteria at a 90% floor, and this is the same instrument
pointed one level up. Choosing a second threshold for the same purpose would
have meant defending two numbers instead of one.

Three things are NOT scored, and the report says so on every run:

  - whether the stated problem is the real one,
  - whether the objectives are the right objectives,
  - whether the metrics are the right metrics.

No script decides those. Scoring them silently would make the number claim more
than it measured, which `skills/_kit-rules/alignment-threshold.md` calls evidence
theatre and this kit refuses everywhere else.

WHY IT CANNOT SIGN
------------------
`alignment-threshold.md § Amended 2026-09-01` allows a JUDGE to sign an item's
alignment brief, because the judge reads the item's evidence — something that
exists independently of the brief and can contradict it.

At product level there is no such thing. The vision is not measured against
anything; it is what everything else is measured against. A judge scoring it would
grade the document against itself, which is the failure the sign-off exists to
prevent, arriving through the door that amendment opened.

So `AWAITING_REVIEW` is terminal for this script. It can compute the 90%; it
cannot supply the signature, and there is no flag that makes it.

A signature reads `human/{who}` and nothing else is accepted — an ALLOWLIST, the
same one `score_alignment.py` applies at item level. Refusing only `judge/` is a
denylist of one against an open set of names, and it let this cascade's own author
sign it.

Exit codes:
  0 — PRODUCT_ALIGNED (>= 90% and signed by a person)
  1 — NEEDS_REVISION or AWAITING_REVIEW (recoverable; the report says which)
  2 — INVALID (a document is missing or empty, one is still the unfilled
      template, or a citation has no referent)
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import write_wiki_dir  # noqa: E402 — post-bootstrap import
from squad.signoff import SignOff, is_human, read as read_signoff  # noqa: E402 — post-bootstrap import
from squad.rubric import ALIGNMENT_FLOOR_PCT  # noqa: E402 — post-bootstrap import

#: Read rather than restated — `squad.rubric` owns the figure and the item-level
#: scorer reads the same one. G-B4 in `cycle-brainstorm.md` always said this cycle
#: reuses the number; until 2026-09-19 it declared its own.
FLOOR_PCT = ALIGNMENT_FLOOR_PCT


#: A guide comment in a shipped template: `<!-- what to write here -->`.
#:
#: Stripped before ANYTHING is scored, and that is the single fix behind four of
#: this file's criteria. Measured 2026-09-20 with the four templates copied into
#: `wiki/product/` and not edited: 100.0%, 34/34, every criterion green. The
#: instructions ARE the document as far as a length check, a `\d` search or a
#: non-empty field test can tell — `metric:` scored a number on the `2` in the
#: words "Gate G-B2", and "Who it is for" scored complete on 132 characters of
#: advice about what to put there.
#:
#: Non-greedy and DOTALL: the templates wrap their guidance across lines, and a
#: greedy match would swallow everything between the first `<!--` and the last `-->`.
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_comments(text: str) -> str:
    """The document as a reader would act on it, with the scaffold's advice removed."""
    return COMMENT_RE.sub("", text)


def is_empty(text: str) -> bool:
    """Nothing here but the shape a scaffold leaves behind.

    Whitespace and heading lines only, AFTER the guide comments are gone. Drawn
    narrowly ON PURPOSE: a heading AND a paragraph is a PARTIAL document, and
    partial is exactly what `NEEDS_REVISION` exists for. The wider rule — "scores
    zero on every criterion" — would call a badly structured but genuinely written
    document absent, which is a worse lie than the one being fixed.
    """
    for line in strip_comments(text).splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return False
    return True

VISION = "product-vision.md"
OBJECTIVES = "objectives.md"
TRD = "trd.md"
PIECES = "technical-pieces.md"
ALIGNMENT = "alignment.md"

DOCS = (VISION, OBJECTIVES, TRD, PIECES)

#: Anything that means "not decided yet". A placeholder surviving into an agreed
#: document is a decision nobody made, which the next reader resolves by guessing.
#:
#: The word forms keep their `\b`; the symbol forms must not have one. `\b` needs a
#: word character on one side, and neither `<` nor `?` is one — so for most of this
#: file's life `<who-it-is-for>` and `???` were in the pattern and unmatchable, and
#: `{{SCOPE}}`, which every shipped template carries, was not in it at all.
PLACEHOLDER_RE = re.compile(
    r"\b(?:TBD|TODO|FIXME|XXX|LOREM)\b"
    r"|\?\?\?"
    r"|\{\{[^}]*\}\}"
    r"|<[a-z][a-z0-9-]*>",
    re.IGNORECASE)

#: `{{SCOPE}}`, `{{TITLE}}`, `{{DATE}}` — the substitution markers every shipped
#: template carries. Their own hard cap, separate from `PLACEHOLDER_RE`: a `TODO`
#: in a written document is a gap the author knows about and the criterion scores
#: it, but a surviving `{{…}}` means the scaffold was copied and never filled in.
#: That is a structural fact about the file, and `NEEDS_REVISION` would send
#: somebody to improve a document nobody has started.
TEMPLATE_TOKEN_RE = re.compile(r"\{\{[^}]*\}\}")

OBJ_RE = re.compile(r"^##\s+(OBJ-\d+)\s*(?:—|-)\s*(.+)$", re.MULTILINE)
REQ_RE = re.compile(r"^##\s+(REQ-\d+)\s*(?:—|-)\s*(.+)$", re.MULTILINE)
PIECE_RE = re.compile(r"^##\s+(PIECE-\d+)\s*(?:—|-)\s*(.+)$", re.MULTILINE)

#: The block each document is read as, written the way the reader above accepts it. A
#: test holds each form to its pattern, so the printed example cannot drift from the parse.
OBJ_FORM = "## OBJ-1 — <objective>"
REQ_FORM = "## REQ-1 — <requirement>"
PIECE_FORM = "## PIECE-1 — <piece>"

#: The vision's prose sections, by criterion. Lifted out of `_gate_vision` so the refusal
#: prints the heading the reader looks for (#139).
VISION_SECTIONS = (
    ("vision_user", "Who it is for"),
    ("vision_problem", "The problem"),
    ("vision_what", "What it is"),
)
NONGOALS_HEADER = "What it is NOT"
#: The `field:` lines each block is read for.
METRIC_FIELD, HORIZON_FIELD, SERVES_FIELD, REALISES_FIELD = (
    "metric", "horizon", "serves", "realises")
_VISION_MIN_CHARS = 80
_PLACEHOLDER_SHAPE = ("no `TBD`, `TODO`, `FIXME`, `XXX`, `LOREM`, `???`, `{{…}}` or "
                      "`<lowercase-token>` left in {doc}")

#: What each criterion ACCEPTS, printed under every one it refuses (#139). Measured over a
#: 20-hour consumer session: `brainstorm-pieces` was the skill whose source was read most
#: often to learn the shape it wanted — 11 reads — because `0 objective(s)` names the
#: count and not the block that would have been counted.
ACCEPTED_SHAPES: dict[str, str] = {
    **{key: (f"`## {header}` in {VISION} with at least {_VISION_MIN_CHARS} characters "
             "under it") for key, header in VISION_SECTIONS},
    "vision_nongoals": f"`## {NONGOALS_HEADER}` in {VISION} with at least 2 `- ` bullets",
    "vision_no_placeholder": _PLACEHOLDER_SHAPE.format(doc=VISION),
    "obj_present": f"at least one `{OBJ_FORM}` block in {OBJECTIVES}",
    "obj_metric": f"a `{METRIC_FIELD}: <value with a number>` line in every OBJ block",
    "obj_horizon": f"a `{HORIZON_FIELD}: <when>` line in every OBJ block",
    "obj_no_placeholder": _PLACEHOLDER_SHAPE.format(doc=OBJECTIVES),
    "req_present": f"at least one `{REQ_FORM}` block in {TRD}",
    "req_cites": f"a `{SERVES_FIELD}: OBJ-1` line in every REQ block",
    "req_cites_resolve": f"every `OBJ-n` a REQ serves is defined in {OBJECTIVES}",
    "req_no_placeholder": _PLACEHOLDER_SHAPE.format(doc=TRD),
    "piece_present": f"at least one `{PIECE_FORM}` block in {PIECES}",
    "piece_cites": f"a `{REALISES_FIELD}: REQ-1` line in every PIECE block",
    "piece_cites_resolve": f"every `REQ-n` a PIECE realises is defined in {TRD}",
    "piece_no_placeholder": _PLACEHOLDER_SHAPE.format(doc=PIECES),
}

#: Who signed and how many boxes carry a mark — read by `squad.signoff`, the one
#: reader every gate in this kit shares. This file compiled its own pattern and its
#: own rule until 2026-09-20, and the three copies disagreed: see that module for what
#: each spelling let through.
#:
#: The POLICY stays here, because it differs by level. At product level every signer
#: must be a person: `alignment-threshold.md § Amended 2026-09-01` admits a judge for
#: an ITEM because the judge reads evidence that exists independently of the brief, and
#: a product vision has no such evidence — it is what everything else is measured
#: against.


@dataclass
class Criterion:
    key: str
    doc: str
    score: int  # 0 absent · 1 partial · 2 complete
    note: str


@dataclass
class Report:
    criteria: list[Criterion] = field(default_factory=list)
    #: The coverage direction, kept as four fields rather than two booleans: a citation
    #: pointing at nothing and a goal nothing points at are different findings, and which
    #: ids are on each side is what a reader acts on.
    objectives_declared: set = field(default_factory=set)
    objectives_served: set = field(default_factory=set)
    objectives_unserved: list = field(default_factory=list)
    requirements_realised: set = field(default_factory=set)
    requirements_unrealised: list = field(default_factory=list)
    #: Structural. No edit to the artifact that carries them can fix these — a document
    #: that is not there, a citation whose referent does not exist. Verdict INVALID.
    hard_caps: list[str] = field(default_factory=list)
    #: The gates `cycle-brainstorm.md` declares hard, which ARE fixable by editing.
    #: They force NEEDS_REVISION regardless of the percentage, because a rubric of
    #: seventeen criteria dilutes any single one: an objective with no number costs
    #: one point of thirty-four and still scores 97%. Scoring alone would have let
    #: the gate read as enforced while passing exactly what it names.
    floor_caps: list[str] = field(default_factory=list)
    #: Present on disk and holding nothing a reader could act on. Kept apart from
    #: `missing_docs` because the two send a person to different places.
    empty_docs: list[str] = field(default_factory=list)
    #: Still carrying `{{SCOPE}}` and friends: the template, copied, not filled in.
    unfilled_docs: list[str] = field(default_factory=list)
    unreadable_docs: list[str] = field(default_factory=list)
    missing_docs: list[str] = field(default_factory=list)
    dangling: list[str] = field(default_factory=list)
    signers: list[str] = field(default_factory=list)
    unticked: int = 0
    #: Boxes a reviewer actually marked. Counted because "nothing is unticked" is
    #: also true of a checklist with NO boxes — `TICKED_RE` was defined here and
    #: read nowhere, and a sign-off section with its four boxes DELETED scored
    #: `PRODUCT_ALIGNED`. The template forbids removing one in prose; this is the
    #: half a script can hold.
    ticked: int = 0

    @property
    def earned(self) -> int:
        return sum(c.score for c in self.criteria)

    @property
    def possible(self) -> int:
        return 2 * len(self.criteria)

    @property
    def pct(self) -> float:
        return 100.0 * self.earned / self.possible if self.possible else 0.0


def _section(text: str, header: str) -> str:
    m = re.search(rf"^##\s+{re.escape(header)}\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def _blocks(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str, str]]:
    """(id, title, body) for each `## ID — title` block."""
    out = []
    hits = list(pattern.finditer(text))
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        out.append((m.group(1), m.group(2).strip(), text[m.end():end]))
    return out


def _field(body: str, name: str) -> str:
    r"""The value on the field's OWN line, or nothing.

    `\s*` matches a newline, so an empty `horizon:` reached across the blank that
    followed it and returned the NEXT line's text — `why: …` became the horizon.
    An empty field that borrows its neighbour's value is worse than an absent one:
    the gate reports it as carried. `[ \t]*` cannot leave the line.
    """
    m = re.search(rf"^[ \t]*{re.escape(name)}[ \t]*:[ \t]*(.+)$",
                  body, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _has_number(value: str) -> bool:
    """A metric without a number cannot ever be reported as met."""
    return bool(re.search(r"\d", value))


def _gate_vision(rep: Report, texts: dict[str, str]) -> None:
    """vision: 5 criteria (G-B1)

    Extracted from `score`, which measured cyclomatic complexity 66 across 136 lines
    holding five independent gate sections. Pure code movement: the block below is the
    block that was there, reading the same documents. What changed is that each section
    now declares what it reads and what it produces, instead of leaving both lying in a
    shared scope.
    """
    # ---- vision: 5 criteria (G-B1) ------------------------------------------
    v = texts[VISION]
    for key, header in VISION_SECTIONS:
        body = _section(v, header).strip()
        rep.criteria.append(Criterion(
            key, VISION, 2 if len(body) >= _VISION_MIN_CHARS else (1 if body else 0),
            f"'{header}' {'present' if body else 'absent'} ({len(body)} chars)"))

    # `- ` with nothing after it is the shape the template ships, twice. Counting
    # the bullet rather than what is on it awarded the section to a file nobody
    # had written in.
    nongoals = [ln for ln in _section(v, NONGOALS_HEADER).splitlines()
                if ln.strip().startswith("-") and ln.strip().lstrip("-").strip()]
    rep.criteria.append(Criterion(
        "vision_nongoals", VISION, 2 if len(nongoals) >= 2 else (1 if nongoals else 0),
        f"{len(nongoals)} non-goal(s) — the half that is always omitted"))

    rep.criteria.append(Criterion(
        "vision_no_placeholder", VISION, 0 if PLACEHOLDER_RE.search(v) else 2,
        "placeholder found" if PLACEHOLDER_RE.search(v) else "no placeholder"))

    if not nongoals:
        rep.floor_caps.append("vision_without_non_goal")
    if not _section(v, VISION_SECTIONS[0][1]).strip():
        rep.floor_caps.append("vision_without_named_user")


def _gate_objectives(rep: Report, texts: dict[str, str]) -> set[str]:
    """objectives: 4 criteria (G-B2)

    Extracted from `score`, which measured cyclomatic complexity 66 across 136 lines
    holding five independent gate sections. Pure code movement: the block below is the
    block that was there, reading the same documents. What changed is that each section
    now declares what it reads and what it produces, instead of leaving both lying in a
    shared scope.
    """
    # ---- objectives: 4 criteria (G-B2) --------------------------------------
    objectives = _blocks(texts[OBJECTIVES], OBJ_RE)
    obj_ids = {oid for oid, _, _ in objectives}
    rep.objectives_declared = set(obj_ids)
    rep.criteria.append(Criterion(
        "obj_present", OBJECTIVES, 2 if objectives else 0, f"{len(objectives)} objective(s)"))

    with_metric = [o for o in objectives if _has_number(_field(o[2], METRIC_FIELD))]
    with_horizon = [o for o in objectives if _field(o[2], HORIZON_FIELD)]
    rep.criteria.append(Criterion(
        "obj_metric", OBJECTIVES,
        2 if objectives and len(with_metric) == len(objectives) else (1 if with_metric else 0),
        f"{len(with_metric)}/{len(objectives)} carry a metric containing a number"))
    rep.criteria.append(Criterion(
        "obj_horizon", OBJECTIVES,
        2 if objectives and len(with_horizon) == len(objectives) else (1 if with_horizon else 0),
        f"{len(with_horizon)}/{len(objectives)} carry a horizon"))
    rep.criteria.append(Criterion(
        "obj_no_placeholder", OBJECTIVES, 0 if PLACEHOLDER_RE.search(texts[OBJECTIVES]) else 2,
        "placeholder found" if PLACEHOLDER_RE.search(texts[OBJECTIVES]) else "no placeholder"))

    if not objectives:
        rep.floor_caps.append("no_objective")
    if len(with_metric) != len(objectives):
        rep.floor_caps.append("objective_without_measurable_metric")
    if len(with_horizon) != len(objectives):
        rep.floor_caps.append("objective_without_horizon")
    return obj_ids


def _gate_trd(rep: Report, texts: dict[str, str], obj_ids: set[str]) -> tuple[list, set[str], list]:
    """trd: 4 criteria (G-B3)

    Extracted from `score`, which measured cyclomatic complexity 66 across 136 lines
    holding five independent gate sections. Pure code movement: the block below is the
    block that was there, reading the same documents. What changed is that each section
    now declares what it reads and what it produces, instead of leaving both lying in a
    shared scope.
    """
    # ---- trd: 4 criteria (G-B3) ---------------------------------------------
    reqs = _blocks(texts[TRD], REQ_RE)
    req_ids = {rid for rid, _, _ in reqs}
    rep.criteria.append(Criterion(
        "req_present", TRD, 2 if reqs else 0, f"{len(reqs)} requirement(s)"))

    cited = [(rid, _field(body, SERVES_FIELD)) for rid, _, body in reqs]
    # Matched against the ID PATTERN, not against emptiness. `serves: OBJ-<!-- … -->`
    # was non-empty, so it counted as a citation — and matched no `OBJ-\d+`, so it
    # was not dangling either. A requirement escaped G-B3 by being unreadable, which
    # is the one way past a gate that checks referents.
    with_cite = [c for c in cited if re.search(r"OBJ-\d+", c[1])]
    rep.criteria.append(Criterion(
        "req_cites", TRD,
        2 if reqs and len(with_cite) == len(reqs) else (1 if with_cite else 0),
        f"{len(with_cite)}/{len(reqs)} name the objective they serve"))

    for rid, raw in cited:
        for ref in re.findall(r"OBJ-\d+", raw):
            if ref not in obj_ids:
                rep.dangling.append(f"{rid} serves {ref}, which {OBJECTIVES} does not define")
            else:
                rep.objectives_served.add(ref)
    rep.criteria.append(Criterion(
        "req_cites_resolve", TRD, 0 if rep.dangling else 2,
        f"{len(rep.dangling)} dangling citation(s)"))
    rep.criteria.append(Criterion(
        "req_no_placeholder", TRD, 0 if PLACEHOLDER_RE.search(texts[TRD]) else 2,
        "placeholder found" if PLACEHOLDER_RE.search(texts[TRD]) else "no placeholder"))
    return reqs, req_ids, with_cite


def _gate_pieces(rep: Report, texts: dict[str, str], reqs: list, req_ids: set[str], with_cite: list) -> None:
    """pieces: 4 criteria (G-B3)

    Extracted from `score`, which measured cyclomatic complexity 66 across 136 lines
    holding five independent gate sections. Pure code movement: the block below is the
    block that was there, reading the same documents. What changed is that each section
    now declares what it reads and what it produces, instead of leaving both lying in a
    shared scope.
    """
    # ---- pieces: 4 criteria (G-B3) ------------------------------------------
    pieces = _blocks(texts[PIECES], PIECE_RE)
    rep.criteria.append(Criterion(
        "piece_present", PIECES, 2 if pieces else 0, f"{len(pieces)} piece(s)"))

    p_cited = [(pid, _field(body, REALISES_FIELD)) for pid, _, body in pieces]
    # Same rule as `serves:` above, and for the same reason.
    p_with = [c for c in p_cited if re.search(r"REQ-\d+", c[1])]
    rep.criteria.append(Criterion(
        "piece_cites", PIECES,
        2 if pieces and len(p_with) == len(pieces) else (1 if p_with else 0),
        f"{len(p_with)}/{len(pieces)} name the requirements they realise"))

    before = len(rep.dangling)
    for pid, raw in p_cited:
        for ref in re.findall(r"REQ-\d+", raw):
            if ref not in req_ids:
                rep.dangling.append(f"{pid} realises {ref}, which {TRD} does not define")
            else:
                rep.requirements_realised.add(ref)
    rep.criteria.append(Criterion(
        "piece_cites_resolve", PIECES, 2 if len(rep.dangling) == before else 0,
        f"{len(rep.dangling) - before} dangling citation(s)"))
    rep.criteria.append(Criterion(
        "piece_no_placeholder", PIECES, 0 if PLACEHOLDER_RE.search(texts[PIECES]) else 2,
        "placeholder found" if PLACEHOLDER_RE.search(texts[PIECES]) else "no placeholder"))

    if reqs and len(with_cite) != len(reqs):
        rep.floor_caps.append("requirement_serving_no_objective")
    if pieces and len(p_with) != len(pieces):
        rep.floor_caps.append("piece_realising_no_requirement")

    # THE COVERAGE DIRECTION, which this phase asked nowhere. The two caps above resolve
    # citations pointing UP the chain — a `serves:` or a `realises:` naming nothing. Whether
    # every objective is served, and every requirement realised, was asked by no criterion
    # here.
    #
    # It IS asked eventually: `check_objective_coverage` exits 1 on an objective no ITEM
    # serves. That is at `/backlog-approve`, after DESIGN drew a system without the goal in
    # it and BACKLOG filed items against that system. The argument `check_merge_autonomy`
    # makes applies verbatim — discovering it per-item costs the run, announcing it here
    # costs one criterion.
    #
    # Guarded on the documents being READABLE, because reporting every objective as
    # unserved when the TRD is missing turns an inability to measure into a measurement.
    if rep.objectives_declared and texts.get(TRD, "").strip():
        rep.objectives_unserved = sorted(rep.objectives_declared - rep.objectives_served)
        if rep.objectives_unserved:
            rep.floor_caps.append("objective_served_by_no_requirement")
    if req_ids and texts.get(PIECES, "").strip():
        rep.requirements_unrealised = sorted(req_ids - rep.requirements_realised)
        if rep.requirements_unrealised:
            rep.floor_caps.append("requirement_realised_by_no_piece")

    if rep.dangling:
        # Same rule the kit applies to a `file:line`: a pointer with no referent
        # caps the artifact, because no edit to the CITING document can fix it.
        rep.hard_caps.append("citation_without_referent")


def _gate_signature(rep: Report, product: Path) -> None:
    """the signature (G-B5)

    Extracted from `score`, which measured cyclomatic complexity 66 across 136 lines
    holding five independent gate sections. Pure code movement: the block below is the
    block that was there, reading the same documents. What changed is that each section
    now declares what it reads and what it produces, instead of leaving both lying in a
    shared scope.
    """
    # ---- the signature (G-B5) ------------------------------------------------
    align = product / ALIGNMENT
    if align.is_file():
        # NOT stripped of comments: here the comment IS the payload. `signed-by:`
        # travels in one, so that a signature cannot be typed by accident and a
        # reader sees who gave it without opening anything else.
        sheet = read_signoff(align.read_text(encoding="utf-8"))
    else:
        # No checklist at all: an absent gate is not a passed one.
        sheet = SignOff(absent=True, ticked=-1, unticked=-1)
    rep.signers = sheet.signers
    rep.unticked = sheet.unticked
    rep.ticked = sheet.ticked
    rep.sheet = sheet


def score(root: Path) -> Report:
    rep = Report()
    product = write_wiki_dir(root, "product")
    texts: dict[str, str] = {}
    for name in DOCS:
        path = product / name
        if not path.is_file():
            rep.missing_docs.append(name)
            texts[name] = ""
            continue
        try:
            # Stripped of guide comments HERE, once, so every criterion below reads
            # the document a person wrote rather than the instructions they were
            # given. Doing it per-criterion is what let four of them disagree about
            # what the document contained.
            texts[name] = strip_comments(path.read_text(encoding="utf-8"))
        except OSError as exc:
            # Present and unreadable is not present. Scoring it from `""` would
            # award the six criteria that are vacuously true of emptiness.
            rep.unreadable_docs.append(f"{name}: {exc}")
            texts[name] = ""
            continue
        # The line above USED to be the whole story, and the cap below asked the
        # filesystem rather than the document. A missing document has already been
        # scored from `""` two lines up, so missing and empty ran the identical
        # scoring path and only the cap separated them — on the wrong question.
        # Measured 2026-09-19 with four files holding one heading each:
        # NEEDS_REVISION, 35.3%, `hard_caps: []`. `touch` turned INVALID into a
        # recoverable verdict and published "a third of this is done" over nothing.
        if is_empty(texts[name]):
            rep.empty_docs.append(name)
        elif TEMPLATE_TOKEN_RE.search(texts[name]):
            # Measured 2026-09-20: the four templates copied in and not edited scored
            # 100.0%, 34/34. Their guide comments are gone by the time anything is
            # scored now, but `{{SCOPE}}` in a heading is not a comment and a heading
            # is not "empty" — so the copy would have come back low rather than
            # structurally refused, and "revise this" is the wrong instruction for a
            # file nobody has written in.
            rep.unfilled_docs.append(name)

    if rep.missing_docs:
        rep.hard_caps.append("missing_document")
    if rep.empty_docs:
        # A separate cap, not `missing_document`: `missing_documents` must keep
        # meaning the file is not there, or the report sends somebody to create a
        # file they already have.
        rep.hard_caps.append("empty_document")
    if rep.unfilled_docs:
        rep.hard_caps.append("unfilled_template")
    if rep.unreadable_docs:
        rep.hard_caps.append("unreadable_document")

    _gate_vision(rep, texts)
    obj_ids = _gate_objectives(rep, texts)
    reqs, req_ids, with_cite = _gate_trd(rep, texts, obj_ids)
    _gate_pieces(rep, texts, reqs, req_ids, with_cite)
    _gate_signature(rep, product)

    return rep


def verdict(rep: Report) -> tuple[str, int]:
    if rep.hard_caps:
        return "INVALID", 2
    if rep.floor_caps or rep.pct < FLOOR_PCT:
        return "NEEDS_REVISION", 1
    # A judge may not stand in here — see the module docstring.
    #
    # Three conditions, and each one was a hole. `ticked > 0`: a checklist whose
    # boxes were DELETED has nothing unticked. `signers`: an unsigned gate is not a
    # passed one. `all(signed_by_is_human)`: an ALLOWLIST, because refusing only
    # `judge/` accepted every other name an agent could sign under — and reporting
    # the WEAKEST signer is what stops one human tick from laundering the rest,
    # exactly as `score_alignment.py` does at item level.
    if not rep.sheet.complete or not rep.sheet.signers:
        return "AWAITING_REVIEW", 1
    if not rep.sheet.human_signed:
        return "AWAITING_REVIEW", 1
    return "PRODUCT_ALIGNED", 0


NOT_SCORED = (
    "whether the stated problem is the real one",
    "whether these are the right objectives",
    "whether these are the right metrics",
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rep = score(args.root)
    tok, code = verdict(rep)

    payload = {
        "verdict": tok,
        "score_pct": round(rep.pct, 1),
        "floor_pct": FLOOR_PCT,
        "earned": rep.earned,
        "possible": rep.possible,
        "hard_caps": rep.hard_caps,
        "floor_caps": rep.floor_caps,
        "missing_documents": rep.missing_docs,
        "empty_documents": rep.empty_docs,
        "unfilled_documents": rep.unfilled_docs,
        "unreadable_documents": rep.unreadable_docs,
        "dangling_citations": rep.dangling,
        "signers": rep.signers,
        "signed_by_is_human": rep.sheet.human_signed,
        "unticked_boxes": rep.unticked,
        "ticked_boxes": rep.ticked,
        "criteria": [{**c.__dict__, "accepts": ACCEPTED_SHAPES[c.key]}
                     for c in rep.criteria],
        "not_scored": list(NOT_SCORED),
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return code

    print(f"{tok}  {rep.pct:.1f}% ({rep.earned}/{rep.possible}, floor {FLOOR_PCT}%)")
    for c in rep.criteria:
        mark = {0: "✗", 1: "~", 2: "✓"}[c.score]
        print(f"  {mark} {c.key:24s} {c.note}")
        if c.score < 2:
            print(f"      accepts: {ACCEPTED_SHAPES[c.key]}")
    for cap in rep.hard_caps:
        print(f"  HARD CAP:  {cap}")
    for cap in rep.floor_caps:
        print(f"  FLOOR CAP: {cap}")
    for d in rep.dangling:
        print(f"  DANGLING: {d}")
    if rep.missing_docs:
        # WHERE, not only which: the directory is derived from the write root, and a
        # reader told `objectives.md` is missing still had to find out where it goes.
        print(f"  MISSING:  {', '.join(rep.missing_docs)} — expected under "
              f"{write_wiki_dir(args.root, 'product')}")
    # Worded so the two never read the same. "Missing" sends a person to create a
    # file; "empty" sends them to open one they already have, and a reader handed
    # the wrong one of those loses the time it takes to find out.
    if rep.empty_docs:
        print(f"  EMPTY:    {', '.join(rep.empty_docs)} — the file is there and "
              f"holds nothing but headings")
    if rep.unfilled_docs:
        print(f"  UNFILLED: {', '.join(rep.unfilled_docs)} — still carrying the "
              f"template's {{{{…}}}} markers; the scaffold was copied, not written")
    if rep.unreadable_docs:
        print(f"  UNREADABLE: {', '.join(rep.unreadable_docs)}")
    if tok == "AWAITING_REVIEW":
        non_human = rep.sheet.non_human_signers
        if non_human:
            # Named, not merely refused: a person who signed as `paulo` and a
            # judge that signed as itself get the same verdict for different
            # reasons, and only one of the two is a typo away from passing.
            print(f"  Signed by {', '.join(non_human)} — not a person. A signature "
                  f"reads `human/{{who}}`; anything else is an agent, and an agent "
                  f"may not sign this one.")
        elif rep.ticked == 0:
            print("  The sign-off section has no checkboxes. They are not ticked by "
                  "being deleted — restore the four from the template and ask for "
                  "the review.")
        else:
            print("  The structure is complete and nobody has signed. "
                  "This script cannot sign it.")
    print("\nNot scored, and no script can decide them:")
    for n in NOT_SCORED:
        print(f"  - {n}")
    return code


if __name__ == "__main__":
    sys.exit(main())

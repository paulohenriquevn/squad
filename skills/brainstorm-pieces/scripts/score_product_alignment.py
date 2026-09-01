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

Exit codes:
  0 — PRODUCT_ALIGNED (>= 90% and signed by a person)
  1 — NEEDS_REVISION or AWAITING_REVIEW (recoverable; the report says which)
  2 — INVALID (a document is missing, or a citation has no referent)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

FLOOR_PCT = 90.0

VISION = "product-vision.md"
OBJECTIVES = "objectives.md"
TRD = "trd.md"
PIECES = "technical-pieces.md"
ALIGNMENT = "alignment.md"

DOCS = (VISION, OBJECTIVES, TRD, PIECES)

#: Anything that means "not decided yet". A placeholder surviving into an agreed
#: document is a decision nobody made, which the next reader resolves by guessing.
PLACEHOLDER_RE = re.compile(r"\b(TBD|TODO|FIXME|XXX|\?\?\?|<[a-z-]+>|LOREM)\b", re.IGNORECASE)

OBJ_RE = re.compile(r"^##\s+(OBJ-\d+)\s*(?:—|-)\s*(.+)$", re.MULTILINE)
REQ_RE = re.compile(r"^##\s+(REQ-\d+)\s*(?:—|-)\s*(.+)$", re.MULTILINE)
PIECE_RE = re.compile(r"^##\s+(PIECE-\d+)\s*(?:—|-)\s*(.+)$", re.MULTILINE)

#: `signed-by:` names WHO signed, so a person's agreement and a machine's are
#: different claims a reader tells apart without opening the file. The kit's
#: item-level scorer reports the weakest signer for the same reason.
SIGNED_BY_RE = re.compile(r"<!--\s*signed-by:\s*([^\s>]+)\s*-->")
TICKED_RE = re.compile(r"^\s*-\s*\[[xX]\]\s+\S", re.MULTILINE)
UNTICKED_RE = re.compile(r"^\s*-\s*\[\s*\]\s+\S", re.MULTILINE)


@dataclass
class Criterion:
    key: str
    doc: str
    score: int  # 0 absent · 1 partial · 2 complete
    note: str


@dataclass
class Report:
    criteria: list[Criterion] = field(default_factory=list)
    #: Structural. No edit to the artifact that carries them can fix these — a document
    #: that is not there, a citation whose referent does not exist. Verdict INVALID.
    hard_caps: list[str] = field(default_factory=list)
    #: The gates `cycle-brainstorm.md` declares hard, which ARE fixable by editing.
    #: They force NEEDS_REVISION regardless of the percentage, because a rubric of
    #: seventeen criteria dilutes any single one: an objective with no number costs
    #: one point of thirty-four and still scores 97%. Scoring alone would have let
    #: the gate read as enforced while passing exactly what it names.
    floor_caps: list[str] = field(default_factory=list)
    missing_docs: list[str] = field(default_factory=list)
    dangling: list[str] = field(default_factory=list)
    signers: list[str] = field(default_factory=list)
    unticked: int = 0

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
    m = re.search(rf"^\s*{re.escape(name)}\s*:\s*(.+)$", body, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _has_number(value: str) -> bool:
    """A metric without a number cannot ever be reported as met."""
    return bool(re.search(r"\d", value))


def score(root: Path) -> Report:
    rep = Report()
    product = root / "wiki" / "product"
    texts: dict[str, str] = {}
    for name in DOCS:
        path = product / name
        if not path.is_file():
            rep.missing_docs.append(name)
            texts[name] = ""
        else:
            texts[name] = path.read_text(encoding="utf-8")

    if rep.missing_docs:
        rep.hard_caps.append("missing_document")

    # ---- vision: 5 criteria (G-B1) ------------------------------------------
    v = texts[VISION]
    for key, header in (
        ("vision_user", "Who it is for"),
        ("vision_problem", "The problem"),
        ("vision_what", "What it is"),
    ):
        body = _section(v, header).strip()
        rep.criteria.append(Criterion(
            key, VISION, 2 if len(body) >= 80 else (1 if body else 0),
            f"'{header}' {'present' if body else 'absent'} ({len(body)} chars)"))

    nongoals = [ln for ln in _section(v, "What it is NOT").splitlines() if ln.strip().startswith("-")]
    rep.criteria.append(Criterion(
        "vision_nongoals", VISION, 2 if len(nongoals) >= 2 else (1 if nongoals else 0),
        f"{len(nongoals)} non-goal(s) — the half that is always omitted"))

    rep.criteria.append(Criterion(
        "vision_no_placeholder", VISION, 0 if PLACEHOLDER_RE.search(v) else 2,
        "placeholder found" if PLACEHOLDER_RE.search(v) else "no placeholder"))

    if not nongoals:
        rep.floor_caps.append("vision_without_non_goal")
    if not _section(v, "Who it is for").strip():
        rep.floor_caps.append("vision_without_named_user")

    # ---- objectives: 4 criteria (G-B2) --------------------------------------
    objectives = _blocks(texts[OBJECTIVES], OBJ_RE)
    obj_ids = {oid for oid, _, _ in objectives}
    rep.criteria.append(Criterion(
        "obj_present", OBJECTIVES, 2 if objectives else 0, f"{len(objectives)} objective(s)"))

    with_metric = [o for o in objectives if _has_number(_field(o[2], "metric"))]
    with_horizon = [o for o in objectives if _field(o[2], "horizon")]
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

    # ---- trd: 4 criteria (G-B3) ---------------------------------------------
    reqs = _blocks(texts[TRD], REQ_RE)
    req_ids = {rid for rid, _, _ in reqs}
    rep.criteria.append(Criterion(
        "req_present", TRD, 2 if reqs else 0, f"{len(reqs)} requirement(s)"))

    cited = [(rid, _field(body, "serves")) for rid, _, body in reqs]
    with_cite = [c for c in cited if c[1]]
    rep.criteria.append(Criterion(
        "req_cites", TRD,
        2 if reqs and len(with_cite) == len(reqs) else (1 if with_cite else 0),
        f"{len(with_cite)}/{len(reqs)} name the objective they serve"))

    for rid, raw in cited:
        for ref in re.findall(r"OBJ-\d+", raw):
            if ref not in obj_ids:
                rep.dangling.append(f"{rid} serves {ref}, which {OBJECTIVES} does not define")
    rep.criteria.append(Criterion(
        "req_cites_resolve", TRD, 0 if rep.dangling else 2,
        f"{len(rep.dangling)} dangling citation(s)"))
    rep.criteria.append(Criterion(
        "req_no_placeholder", TRD, 0 if PLACEHOLDER_RE.search(texts[TRD]) else 2,
        "placeholder found" if PLACEHOLDER_RE.search(texts[TRD]) else "no placeholder"))

    # ---- pieces: 4 criteria (G-B3) ------------------------------------------
    pieces = _blocks(texts[PIECES], PIECE_RE)
    rep.criteria.append(Criterion(
        "piece_present", PIECES, 2 if pieces else 0, f"{len(pieces)} piece(s)"))

    p_cited = [(pid, _field(body, "realises")) for pid, _, body in pieces]
    p_with = [c for c in p_cited if c[1]]
    rep.criteria.append(Criterion(
        "piece_cites", PIECES,
        2 if pieces and len(p_with) == len(pieces) else (1 if p_with else 0),
        f"{len(p_with)}/{len(pieces)} name the requirements they realise"))

    before = len(rep.dangling)
    for pid, raw in p_cited:
        for ref in re.findall(r"REQ-\d+", raw):
            if ref not in req_ids:
                rep.dangling.append(f"{pid} realises {ref}, which {TRD} does not define")
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

    if rep.dangling:
        # Same rule the kit applies to a `file:line`: a pointer with no referent
        # caps the artifact, because no edit to the CITING document can fix it.
        rep.hard_caps.append("citation_without_referent")

    # ---- the signature (G-B5) ------------------------------------------------
    align = product / ALIGNMENT
    if align.is_file():
        body = align.read_text(encoding="utf-8")
        rep.signers = SIGNED_BY_RE.findall(body)
        rep.unticked = len(UNTICKED_RE.findall(body))
    else:
        rep.unticked = -1  # no checklist at all: an absent gate is not a passed one

    return rep


def verdict(rep: Report) -> tuple[str, int]:
    if rep.hard_caps:
        return "INVALID", 2
    if rep.floor_caps or rep.pct < FLOOR_PCT:
        return "NEEDS_REVISION", 1
    # A judge may not stand in here — see the module docstring.
    if rep.unticked != 0 or not rep.signers:
        return "AWAITING_REVIEW", 1
    if any(s.startswith("judge/") for s in rep.signers):
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
        "dangling_citations": rep.dangling,
        "signers": rep.signers,
        "unticked_boxes": rep.unticked,
        "criteria": [c.__dict__ for c in rep.criteria],
        "not_scored": list(NOT_SCORED),
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return code

    print(f"{tok}  {rep.pct:.1f}% ({rep.earned}/{rep.possible}, floor {FLOOR_PCT}%)")
    for c in rep.criteria:
        mark = {0: "✗", 1: "~", 2: "✓"}[c.score]
        print(f"  {mark} {c.key:24s} {c.note}")
    for cap in rep.hard_caps:
        print(f"  HARD CAP:  {cap}")
    for cap in rep.floor_caps:
        print(f"  FLOOR CAP: {cap}")
    for d in rep.dangling:
        print(f"  DANGLING: {d}")
    if rep.missing_docs:
        print(f"  MISSING:  {', '.join(rep.missing_docs)}")
    if tok == "AWAITING_REVIEW":
        print("  The structure is complete and nobody has signed. This script cannot sign it.")
    print("\nNot scored, and no script can decide them:")
    for n in NOT_SCORED:
        print(f"  - {n}")
    return code


if __name__ == "__main__":
    sys.exit(main())

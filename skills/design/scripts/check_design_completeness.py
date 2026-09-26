#!/usr/bin/env python3
"""Are the technical drawings complete enough that a backlog can be written from them?

    python3 skills/design/scripts/check_design_completeness.py
    python3 skills/design/scripts/check_design_completeness.py --project . --json

## The gap this closes

`brainstorm-pieces` names PIECE-N as *"a responsibility with a boundary"* and says
plainly what it does NOT do: *"A piece may map to a repo, several repos, or part of
one. The mapping is not decided here."* `backlog-init` then inventories repos from
disk. Nothing joins the two, so items get written against a system nobody drew — and
the two decisions that cannot be retrofitted, state ownership and trust boundary, are
the two nobody is forced to make.

## Why these five, and why four of them are mandatory

They are not a diagram set. They are four DECISIONS plus a summary, and the order is
the order in which they remove ambiguity:

| Id | Drawing | The decision it forces |
|---|---|---|
| D1 | states | what the central object's lifecycle IS — which transitions exist, which are irreversible, who triggers each |
| D2 | trust | where third-party or user code runs, what crosses the boundary, with which credential |
| D3 | sequence | the real call order INCLUDING failure paths — which reveals the components prose invented |
| D4 | durability | what survives a process death, a node restart, a platform deploy |
| D5 | system-map | the components and their edges — DERIVED from D1-D4, never drawn first |

D5 is not mandatory as an input. A component map drawn FIRST is decoration: it looks
like design happened and forces no choice. Drawn last it is a summary, and this gate
checks it against the pieces rather than against taste.

## What it checks, and what it cannot

CHECKED — every mandatory drawing exists, carries a mermaid block that parses as the
kind it claims, is not a placeholder, and every `PIECE-N` from `technical-pieces.md`
appears somewhere in D5. Plus the signature, read the same way every other gate in
this kit reads one.

NOT CHECKED — whether any drawing is CORRECT. A state machine with the wrong states
passes; a trust boundary drawn in the wrong place passes. This counts and cross-
references; the judgement is what the signature is for, and why it must be a person's.

Exit codes:
  0  DESIGN_AGREED — complete, covered, signed
  1  NEEDS_REVISION or AWAITING_REVIEW — the report says which
  2  INVALID — a required document is missing entirely; nothing was assessed
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import wiki_dir  # noqa: E402 — post-bootstrap import
from squad.signoff import (  # noqa: E402 — post-bootstrap import
    SignOff,
    read as read_signoff,
)


#: The drawings, in the order they remove ambiguity. `mermaid` is the kind the block
#: must declare — a sequence diagram filed as the state machine is a drawing that
#: answers a different question than the one its slot exists for.
@dataclass(frozen=True)
class Drawing:
    key: str
    filename: str
    mermaid_kind: tuple[str, ...]
    decides: str
    mandatory: bool = True


DRAWINGS: tuple[Drawing, ...] = (
    Drawing("states", "states.md", ("stateDiagram-v2", "stateDiagram"),
            "what the central object's lifecycle is, and which transitions are irreversible"),
    Drawing("trust", "trust.md", ("flowchart", "graph"),
            "where untrusted code runs, what crosses the boundary, and with which credential"),
    Drawing("sequence", "sequence.md", ("sequenceDiagram",),
            "the real call order including the failure paths"),
    Drawing("durability", "durability.md", ("flowchart", "graph", "stateDiagram-v2"),
            "what survives a process death, a node restart and a platform deploy"),
    Drawing("system-map", "system-map.md", ("flowchart", "graph", "C4Context", "C4Container"),
            "the components and their edges — derived from the four above", mandatory=False),
)

DESIGN_LEAF = "design"
PIECES_DOC = "technical-pieces.md"
PIECE_RE = re.compile(r"^##\s+(PIECE-\d+)\s*(?:—|-)\s*(.+)$", re.MULTILINE)
MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
#: Who signed and how many boxes carry a mark come from `squad.signoff`, the one
#: reader every gate shares. This file carried its own `([^\s>]+)` and its own rule,
#: and the pair failed in both directions at once — see that module.
#:
#: The word forms keep their `\b`; `???` must not have one. `\b` needs a word character
#: beside it and `?` is not one, so `owner: ???` sat in the pattern unmatchable — the
#: same defect the product scorer carried in the same expression.
PLACEHOLDER_RE = re.compile(r"\b(?:TBD|TODO|FIXME|XXX|LOREM)\b|\?\?\?", re.IGNORECASE)

#: A `PIECE-N` mention in the map. Matched as a WHOLE id: `"PIECE-1" in map_body` is a
#: substring test and `PIECE-1` is a substring of `PIECE-10`. Measured 2026-09-20 with
#: eleven pieces and a map naming only PIECE-10 and PIECE-11 — "11 declared, 3 covered".
#: It fails only in the permissive direction, and it fires on any product with ten or
#: more pieces.
#: Every `PIECE-N` a body NAMES, for the reverse of `_mentions`. The negative lookahead
#: is the same guard: `PIECE-1` must not be harvested out of `PIECE-10`.
PIECE_IN_TEXT_RE = re.compile(r"\b(PIECE-\d+)\b(?!-?\d)")


def _mentions(piece_id: str, body: str) -> bool:
    return re.search(rf"\b{re.escape(piece_id)}\b(?!-?\d)", body) is not None

#: A mermaid block under this many non-empty lines is a kind line and one edge —
#: which asserts a relationship exists and nothing about it.
#:
#: The floor was 4 and it was wrong. A durability drawing reading
#:
#:     flowchart TB
#:         agent -->|checkpoint every 30s| store
#:         store -->|restore on reschedule| agent
#:
#: is three lines carrying two LABELLED edges, and it answers its slot's question
#: exactly. A check that flags it teaches people to pad diagrams to clear a counter,
#: which is worse than no check.
MIN_MERMAID_LINES = 3


@dataclass
class Finding:
    code: str
    severity: str      # blocker | major | minor
    subject: str
    detail: str


@dataclass
class Report:
    verdict: str = ""
    present: list[str] = field(default_factory=list)
    #: Optional drawings that are NOT on disk. They were put in `present`, so
    #: `render` printed `ok  system-map  (derived)` for a file nobody had
    #: written — the one non-mandatory drawing, reported as done because it was
    #: allowed to be absent. Absent and optional is a third state, and it is the
    #: one a reader needs to see.
    absent_optional: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    pieces: list[str] = field(default_factory=list)
    #: Named by the map and declared by nobody. Its own field, because "the map forgot
    #: a piece" and "the map invented one" are different findings and one number out of
    #: two questions is the class this fix belongs to.
    undeclared: list[str] = field(default_factory=list)
    uncovered: list[str] = field(default_factory=list)
    signers: list[str] = field(default_factory=list)
    unticked: int = -1
    #: The parsed sign-off. `SignOff(absent=True)` until one is read, so an absent
    #: checklist and an empty one are the same refusal by construction.
    sheet: SignOff = field(default_factory=lambda: SignOff(absent=True))
    findings: list[Finding] = field(default_factory=list)
    unmeasured_because: str = ""


class Unreadable(Exception):
    """On disk and could not be opened. NOT the same fact as absent.

    `_read` swallowed `OSError` into `""`, so a present-but-unreadable drawing was
    reported MISSING and the verdict became INVALID — "draw it", about a file the
    person already has. The product scorer keeps `unreadable_document` as its own cap
    for the same reason.
    """


def _read(path: Path) -> str:
    """The body, `""` when there is no such file, `Unreadable` when there is one.

    The split matters and only the second half is new: NOT THERE and THERE BUT SHUT
    are different facts, and the caller reports them to different people. A missing
    file keeps returning `""` so an absent drawing stays `drawing_missing`.
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return ""
    except IsADirectoryError:
        return ""
    except OSError as exc:
        raise Unreadable(str(exc)) from exc


def _read_or_empty(path: Path) -> str:
    """For documents whose absence and unreadability the caller treats alike."""
    try:
        return _read(path)
    except Unreadable:
        return ""


def mermaid_blocks(body: str) -> list[str]:
    return [b.strip() for b in MERMAID_RE.findall(body) if b.strip()]


def declares_kind(block: str, kinds: tuple[str, ...]) -> bool:
    """The first non-empty line of a mermaid block names its type."""
    head = next((line.strip() for line in block.splitlines() if line.strip()), "")
    return any(head.startswith(kind) for kind in kinds)


#: A label carrying a delimiter — `:`, `,`, `|` — outside quotes ends the statement
#: early for every mermaid parser. Found by running `diagram-design`'s extractor over a
#: real drawing: `ops[Operators: app, tenant, preview]` reported "unterminated statement
#: at line 6", and the gate had passed the same file, because it checked that a block
#: EXISTS and declares the right kind, never that it parses.
#:
#: This is not a parser. It catches the one shape that breaks them all, which is the
#: shape a person writing an honest label reaches for.
_UNQUOTED_LABEL = re.compile(r"""[\[\{]\s*(?!["'])([^"'\]\}\n]*[:,|][^"'\]\}\n]*)[\]\}]""")


def unquoted_delimiters(block: str) -> list[str]:
    """Labels holding a delimiter outside quotes — each one ends its statement early."""
    out = []
    for line in block.splitlines():
        stripped = line.strip()
        #: An edge label sits between pipes and is a different construct; `|a, b|` is
        #: only broken when the mermaid version predates quoted edge labels, and
        #: flagging it here would report working diagrams.
        if stripped.startswith(("%%", "|")):
            continue
        for match in _UNQUOTED_LABEL.findall(line):
            if match.strip():
                out.append(match.strip())
    return out


def check(project: Path) -> Report:
    rep = Report()
    design = wiki_dir(project, DESIGN_LEAF)
    product = wiki_dir(project, "product")

    if design is None or not design.is_dir():
        rep.verdict = "INVALID"
        rep.unmeasured_because = (
            f"no design directory under {project}. `/design` writes the five drawings "
            "there; without it nothing was assessed, and reporting that as a pass would "
            "say a backlog may be written from drawings nobody made")
        return rep

    for drawing in DRAWINGS:
        path = design / drawing.filename
        try:
            body = _read(path)
        except Unreadable as exc:
            rep.present.append(drawing.key)
            rep.findings.append(Finding(
                "drawing_unreadable", "blocker" if drawing.mandatory else "major",
                drawing.filename,
                f"the file is on disk and could not be opened ({exc}). Reporting this "
                "as MISSING would send somebody to draw what they already have"))
            continue
        if not body.strip():
            (rep.missing if drawing.mandatory
             else rep.absent_optional).append(drawing.key)
            if drawing.mandatory:
                rep.findings.append(Finding(
                    "drawing_missing", "blocker", drawing.filename,
                    f"nothing decides {drawing.decides}. This is one of the four that "
                    "cannot be retrofitted once code exists"))
            continue

        rep.present.append(drawing.key)
        blocks = mermaid_blocks(body)
        if not blocks:
            rep.findings.append(Finding(
                "drawing_has_no_mermaid", "blocker" if drawing.mandatory else "major",
                drawing.filename,
                "the document exists and carries no mermaid block. Prose about a "
                "diagram is not a diagram, and nothing downstream can read it"))
            continue

        if not any(declares_kind(b, drawing.mermaid_kind) for b in blocks):
            rep.findings.append(Finding(
                "wrong_diagram_kind", "major", drawing.filename,
                f"no block declares {' or '.join(drawing.mermaid_kind)}. A drawing filed "
                f"in this slot answers a different question than the slot exists for: "
                f"{drawing.decides}"))

        if all(len([ln for ln in b.splitlines() if ln.strip()]) < MIN_MERMAID_LINES
               for b in blocks):
            rep.findings.append(Finding(
                "drawing_is_a_stub", "major", drawing.filename,
                f"every mermaid block is under {MIN_MERMAID_LINES} lines — a header and "
                "almost nothing else. A stub in this slot reads as a decision that was "
                "made"))

        for block in blocks:
            for label in unquoted_delimiters(block):
                rep.findings.append(Finding(
                    "unquoted_delimiter_in_label", "major", drawing.filename,
                    f'the label `{label}` carries a delimiter outside quotes, which ends '
                    f'the statement early for every mermaid parser. Write it as '
                    f'`["{label}"]`. Measured on a real drawing: the extractor reported '
                    '"unterminated statement" and this gate had passed the same file'))
                break

        if PLACEHOLDER_RE.search(body):
            rep.findings.append(Finding(
                "placeholder_in_drawing", "major", drawing.filename,
                "carries TBD/TODO/FIXME. An open question drawn as if settled is worse "
                "than an absent drawing, which at least reports itself"))

    # ---- coverage: every declared piece has a place in the map -----------------
    pieces_body = _read_or_empty(product / PIECES_DOC) if product else ""
    if not pieces_body:
        rep.findings.append(Finding(
            "pieces_unreadable", "major", PIECES_DOC,
            "no technical-pieces.md, so coverage was NOT checked — not that it passed. "
            "The drawings may omit half the product and nothing here would know"))
    else:
        rep.pieces = [pid for pid, _title in PIECE_RE.findall(pieces_body)]
        map_body = _read_or_empty(design / "system-map.md")
        if rep.pieces and map_body:
            rep.uncovered = [p for p in rep.pieces if not _mentions(p, map_body)]
            # THE OTHER DIRECTION, which was not computed at all. A map may name a piece
            # `technical-pieces.md` never declared, and the two readings mean different
            # things: a piece missing from the map is work the drawing forgot, while a
            # piece in the map that nobody declared is the map drawing something no one
            # decided — or a piece list that lost an entry. This cycle exists to settle
            # the shape before any item is filed against it, so both answers are worth
            # having then.
            #
            # Matched with the same whole-id rule `_mentions` uses, for the same measured
            # reason: `PIECE-1` is a substring of `PIECE-10`, and a substring test here
            # would call `PIECE-10` declared on the strength of `PIECE-1`.
            declared = set(rep.pieces)
            rep.undeclared = sorted(
                {pid for pid in PIECE_IN_TEXT_RE.findall(map_body)} - declared,
                key=lambda pid: int(pid.split("-")[1]))
            for piece in rep.undeclared:
                rep.findings.append(Finding(
                    "piece_not_declared", "major", piece,
                    f"drawn in the system map and declared in no {PIECES_DOC}. Either "
                    "the map is drawing a responsibility nobody decided, or the piece "
                    "list lost an entry — and the map is not the place that decides"))
            for piece in rep.uncovered:
                rep.findings.append(Finding(
                    "piece_not_in_map", "major", piece,
                    "declared as a responsibility with a boundary and absent from the "
                    "system map. Either it has no place in the system as drawn, or the "
                    "map is missing a component — both are answers worth having before "
                    "an item is filed against it"))
        elif rep.pieces and not map_body:
            rep.findings.append(Finding(
                "coverage_unchecked", "major", "system-map.md",
                f"{len(rep.pieces)} piece(s) declared and no system map to check them "
                "against. Coverage was not verified"))

    # ---- the signature ---------------------------------------------------------
    signoff_path = design / "sign-off.md"
    try:
        signoff = _read(signoff_path) if signoff_path.is_file() else ""
    except Unreadable as exc:
        signoff = ""
        rep.findings.append(Finding(
            "signoff_unreadable", "major", "sign-off.md",
            f"the checklist is on disk and could not be opened ({exc}), so nothing "
            "here knows whether it was signed"))
    if signoff:
        rep.sheet = read_signoff(signoff)
        rep.signers = rep.sheet.signers
        rep.unticked = rep.sheet.unticked

    rep.verdict = verdict_of(rep)
    return rep


def verdict_of(rep: Report) -> str:
    """Derived, never asserted. Tokens come from `rules/verdict-bands.txt`."""
    severities = {f.severity for f in rep.findings}
    if "blocker" in severities:
        return "INVALID"
    if "major" in severities:
        return "NEEDS_REVISION"
    #: A complete, covered set of drawings that nobody signed is not agreed. The same
    #: shape `score_product_alignment` holds: the machine can count, and what it cannot
    #: do is say the drawings are RIGHT.
    #:
    #: Three conditions, because two of them were holes. `complete` requires boxes that
    #: were TICKED — a section whose boxes were DELETED has nothing unticked in it —
    #: and `human_signed` is an ALLOWLIST. Refusing only `judge/` agreed a design
    #: signed `daedalus-tech-lead`, the agent that draws them, while the same run
    #: refused `human/paulo (approved in session)` because the local pattern could not
    #: see a route. `cycle-design.md`: "a person, and only a person".
    if not rep.sheet.complete or not rep.sheet.signers:
        return "AWAITING_REVIEW"
    if not rep.sheet.human_signed:
        return "AWAITING_REVIEW"
    return "DESIGN_AGREED"


EXIT = {"DESIGN_AGREED": 0, "NEEDS_REVISION": 1, "AWAITING_REVIEW": 1, "INVALID": 2}

NOT_CHECKED = (
    "whether any drawing is CORRECT — a state machine with the wrong states passes",
    "whether the trust boundary is in the right place",
    "whether the sequence matches what will actually be built",
    "whether a piece the map covers is covered WELL, or just mentioned",
)


def render(rep: Report) -> str:
    out = ["design completeness", ""]
    if rep.unmeasured_because:
        out += [f"  NOT MEASURED — {rep.unmeasured_because}", "",
                f"  verdict: {rep.verdict}"]
        return "\n".join(out)

    for drawing in DRAWINGS:
        if drawing.key in rep.present:
            mark = "ok "
        elif drawing.key in rep.absent_optional:
            mark = "absent (optional — not drawn, not a failure)"
        else:
            mark = "MISSING"
        flag = "" if drawing.mandatory else "  (derived)"
        out.append(f"  {mark:8} {drawing.key:12}{flag}")
    out.append("")
    if rep.pieces:
        out.append(f"  pieces: {len(rep.pieces)} declared, "
                   f"{len(rep.pieces) - len(rep.uncovered)} covered by the map")
    out.append(f"  signed: {', '.join(rep.signers) or '(nobody)'}"
               + (f" · {rep.unticked} box(es) unticked" if rep.unticked > 0 else ""))
    out.append("")

    for finding in sorted(rep.findings, key=lambda f: ("blocker", "major", "minor").index(f.severity)):
        out.append(f"  [{finding.severity}] {finding.code} — {finding.subject}")
        out.append(f"      {finding.detail}")
    if rep.findings:
        out.append("")

    out.append(f"  verdict: {rep.verdict}")
    out.append("")
    out.append("  NOT CHECKED — the judgement the signature is for:")
    for line in NOT_CHECKED:
        out.append(f"    · {line}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rep = check(args.project.resolve())
    if args.json:
        print(json.dumps({**rep.__dict__,
                          "findings": [f.__dict__ for f in rep.findings],
                          "not_checked": list(NOT_CHECKED)}, indent=2, default=str))
    else:
        print(render(rep))
    return EXIT[rep.verdict]


if __name__ == "__main__":
    raise SystemExit(main())

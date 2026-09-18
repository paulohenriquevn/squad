#!/usr/bin/env python3
"""How much alignment does THIS item need? Derived from the item, never chosen.

    python3 classify_alignment_depth.py <project> <B-NNN> [--json]

    0  LOCAL — a minimal brief is enough
    1  FULL  — the item needs the whole document
    2  could not measure

## The measurement this exists because of

A consumer ran the chain for three days and produced, on a registry of 93 items:

    501 artefacts · 4 implementations · 0 shipped
    78 hours of cycle time per item, none finished
    2,740 KB of alignment briefs, signed by a person ZERO times

A brief is 40-50 KB — longer than the code it describes, which measured 40 to 250
lines across the four items that reached a branch. The walkthrough HTML is another
28 KB per item, an artefact made for a person to look at, and 38 of them were never
opened.

`cycle-brainstorm` and `cycle-design` are already conditional. `plan-alignment` was
not, so deleting an unreferenced package crossed the same seven phases as redesigning
the data plane.

## What the depth decides, and what it does not

FULL keeps everything: requirements, four scenario classes, system design, interaction
model, the walkthrough, and the 17-criterion score at 90%.

LOCAL keeps what the GATES read — functional requirements with ids, acceptance criteria
that execute, out-of-scope, closed questions — and drops the prose and the walkthrough.
**Nothing a later phase consumes is removed.** A criterion still has to discriminate,
`traces_to` still has to resolve, and the signature is still required.

## The line, and why it is drawn here

An item needs the full document when two readers could picture different systems from
its description. That is not directly measurable, so this measures its signals:

| Signal | FULL when |
|---|---|
| evidence spans modules | the cited files live in more than one top-level directory |
| the item is blocked | something else must land first, so the shape depends on it |
| no executable criterion | nothing in the DoD names a command, so the work is not yet concrete |
| the mode is `evolve` | `cycle-backlog` defines it as changing what the system IS |

Any one of them means FULL. The default is FULL, not LOCAL: shallower is the
irreversible direction, because a brief nobody wrote cannot be consulted later, and a
brief nobody needed only cost time.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: The rubric criteria the LOCAL depth removes, by their id in `score_alignment.py`.
#:
#: Declared HERE and not in the scorer, because this module is what decides what a depth
#: MEANS. Two lists would disagree on the first change, and the disagreement is the defect
#: this constant exists to end: measured 2026-09-18, the classifier said "DROPPED: the
#: prose sections and the walkthrough HTML" in prose, the scorer graded all seventeen
#: criteria, and a LOCAL brief complete by its own contract topped out at 24/34 = 70.6%
#: against a 90% floor. The classifier told an author to remove ten points and the scorer
#: required them.
#:
#: These five and no others. The criteria the gates downstream READ — requirements with
#: ids, acceptance criteria that execute, traceability, out-of-scope, closed questions,
#: the signature — are kept at every depth, because dropping one of those would make the
#: depth a way to pass rather than a way to write less.
LOCAL_DROPS = frozenset(
    {
        "flows",
        "scenario_classes",
        "system_diagram",
        "interaction_model",
        "interactive_artefact",
    }
)

CODE_EXT = frozenset({
    "go", "py", "ts", "tsx", "js", "jsx", "mjs", "yaml", "yml", "json", "md", "sh",
    "tf", "html", "css", "sql", "toml", "rs", "java", "rb", "proto",
})

_PATH_RE = re.compile(r"(?<![\w.-])((?:\.?[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.([A-Za-z0-9]{1,5}))")
_COMMAND_RE = re.compile(r"`[^`]*\b(go|pytest|npm|cargo|grep|test|bash|python3|make|jq|rg)\b[^`]*`")


@dataclass
class Verdict:
    item: str
    depth: str = "FULL"
    reasons: list = field(default_factory=list)
    modules: list = field(default_factory=list)
    measurable: bool = True
    why_unmeasurable: str = ""


def _block(backlog_text: str, item: str) -> str:
    match = re.search(rf"^## {re.escape(item)}\b.*?(?=^## B-|\Z)", backlog_text,
                      re.M | re.S)
    return match.group(0) if match else ""


def _field(block: str, name: str) -> str:
    literal = re.search(rf"^{name}:\s*\|\s*\n((?:(?:[ \t]+.*)?\n)*?)(?=^\S|\Z)", block, re.M)
    if literal:
        return " ".join(ln.strip() for ln in literal.group(1).splitlines() if ln.strip())
    plain = re.search(rf"^{name}:\s*(.*)$", block, re.M)
    return plain.group(1).strip() if plain else ""


def _modules(evidence: str) -> list[str]:
    """Top-level directories the cited files live in."""
    found = set()
    for match in _PATH_RE.finditer(evidence):
        if match.group(2).lower() not in CODE_EXT:
            continue
        head = match.group(1).split("/")[0]
        if head and not head.startswith("."):
            found.add(head)
    return sorted(found)


def classify(project: Path, item: str) -> Verdict:
    v = Verdict(item=item)
    backlog = project / "BACKLOG.md"
    if not backlog.is_file():
        v.measurable = False
        v.why_unmeasurable = f"no BACKLOG.md under {project}"
        return v
    block = _block(backlog.read_text(encoding="utf-8-sig"), item)
    if not block:
        v.measurable = False
        v.why_unmeasurable = f"{item} is not in this registry"
        return v

    evidence = _field(block, "evidence")
    blocked = _field(block, "blocked_by")
    mode = _field(block, "suggested_mode")
    dod = re.search(r"^dod:\s*\n((?:\s+-\s+.*\n(?:\s{4,}.*\n)*)+)", block, re.M)
    dod_text = dod.group(1) if dod else ""

    v.modules = _modules(evidence)
    if len(v.modules) > 1:
        v.reasons.append(f"evidence spans {len(v.modules)} modules: {', '.join(v.modules)}")
    if blocked and blocked.lower() not in ("none", "-", "—", ""):
        v.reasons.append(f"blocked on {blocked[:40]} — its shape depends on what lands first")
    if not _COMMAND_RE.search(dod_text):
        v.reasons.append("no DoD bullet names a command; the work is not concrete yet")
    if mode == "evolve":
        v.reasons.append("mode `evolve` changes what the system IS, not how it behaves")

    v.depth = "FULL" if v.reasons else "LOCAL"
    return v


def render(v: Verdict) -> str:
    if not v.measurable:
        return f"NOT MEASURED: {v.why_unmeasurable}\n"
    lines = [f"{v.item}: {v.depth}", ""]
    if v.depth == "FULL":
        lines.append("  Needs the full document, because:")
        lines += [f"    · {r}" for r in v.reasons]
    else:
        lines += [
            f"  One module ({v.modules[0] if v.modules else 'unscoped'}), not blocked, "
            "a DoD that names a command, and a mode that changes behaviour rather than",
            "  shape. A minimal brief carries what the gates read.",
            "",
            "  DROPPED: the prose sections and the walkthrough HTML.",
            "  KEPT: requirements with ids, acceptance criteria that execute,",
            "        out-of-scope, closed questions, and the signature.",
        ]
    lines += ["", "  FULL is the default. Shallower is the irreversible direction — a brief",
              "  nobody wrote cannot be consulted later, and one nobody needed only cost time."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decide how much alignment an item needs, from the item.")
    parser.add_argument("project", type=Path)
    parser.add_argument("item")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    v = classify(args.project.resolve(), args.item.upper())
    if args.json:
        print(json.dumps({"item": v.item, "depth": v.depth, "reasons": v.reasons,
                          "modules": v.modules, "measurable": v.measurable},
                         indent=2, ensure_ascii=False))
    else:
        print(render(v), end="")
    if not v.measurable:
        return 2
    return 0 if v.depth == "LOCAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""What each assigned reviewer must read, and what it is being asked.

    python3 mechanisms/cycle/panel_brief.py --slug theo --phase design --project .
    python3 mechanisms/cycle/panel_brief.py --slug theo --phase design --reviewer vera-technical-arbiter

## Why this is a separate step

`convene_panel.py` ASSIGNS and does not invoke: a `loop-*` plugin and a subagent are
driven by a session, so a Python mechanism can decide who must review and refuse their
absence, but cannot be the thing that runs them. That split is deliberate and this does
not close it.

What it does close is the gap where the session had to invent the briefing. A reviewer
told only "review this" produces a review of whatever it decided to look at, and three
such reviews are not a panel — they are three opinions about three different questions.

So the brief is DERIVED: the artifact paths come from the phase, the contract comes from
the phase's golden rule, and the questions come from that contract. The session invokes;
it does not compose.

## What it refuses

  - A phase with no golden rule. A panel with no contract grades against taste, and
    three reviewers grading against taste disagree for reasons nobody can adjudicate.
  - An assignment that does not exist. Briefing reviewers nobody assigned produces
    votes `review_panel.py` refuses at tally time, which is late.

Exit codes:
  0  briefs emitted
  1  the phase has no contract, or the assignment names nobody
  2  no assignment on disk; nothing was briefed
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import (  # noqa: E402 — post-bootstrap import
    RECORDS,
    WIKI,
    data_root,
    records_dir,
    write_records_dir,
)

#: Where each phase keeps what a panel judges, and the contract it judges against.
#: Read from here rather than guessed per call: a reviewer pointed at the wrong
#: artifact returns an honest verdict about the wrong thing, which reads as coverage.
#: Every path is COMPOSED from the root names `squad.paths` owns, never spelled. The
#: literals were `"wiki/design/states.md"` and `check_write_containment.py` refused
#: them, correctly: a second module that can name a root is how six lists in four
#: different orders happened, and with a copy in play no scan can prove where the
#: writers write.
_DESIGN = f"{WIKI}/design"
_PRODUCT = f"{WIKI}/product"
_DISCOVERIES = f"{RECORDS}/discoveries/opportunities"
_PLANS = f"{RECORDS}/plans"

PHASE_SOURCES: dict[str, dict[str, object]] = {
    "design": {
        "artifacts": tuple(f"{_DESIGN}/{n}.md" for n in
                           ("states", "trust", "sequence", "durability", "system-map")),
        "contract": "rules/design-golden-rule.md",
        "also_read": (f"{_PRODUCT}/technical-pieces.md", f"{_PRODUCT}/trd.md"),
    },
    "discover": {
        "artifacts": (f"{_DISCOVERIES}/{{slug}}-opportunity.md",),
        "contract": "rules/discover-opportunity-golden-rule.md",
        "also_read": (),
    },
    "plan": {
        "artifacts": (f"{_PLANS}/{{slug}}-plan.md",),
        "contract": "rules/plan-confidence-golden-rule.md",
        "also_read": (),
    },
}


def eco_dir(project: Path) -> Path:
    nested = project / ".claude"
    return nested if (nested / "rules").is_dir() else project


def data_path(project: Path, relative: str) -> Path:
    """Produced data resolves under the write root; rules resolve under the kit.

    The prefixes come from `squad.paths` rather than being spelled here — a second
    module that can name a root is how six lists in four different orders happened, and
    with a copy in play no scan can prove where the writers write.
    """
    if relative.split("/", 1)[0] in (WIKI, RECORDS):
        return data_root(project) / relative
    return eco_dir(project) / relative


def assignment_path(project: Path, slug: str, phase: str) -> Path:
    base = records_dir(project, "panels") or write_records_dir(project, "panels")
    return base / f"{slug}-{phase}.assignment.json"


def build(project: Path, slug: str, phase: str) -> dict:
    source = PHASE_SOURCES.get(phase)
    if source is None:
        raise SystemExit(
            f"no contract declared for phase `{phase}`. A panel with no golden rule "
            "grades against taste, and three reviewers grading against taste disagree "
            "for reasons nobody can adjudicate. Add the phase to PHASE_SOURCES with the "
            "artifacts it judges and the rule it judges against.")

    apath = assignment_path(project, slug, phase)
    if not apath.is_file():
        # 2, by hand, because `SystemExit("text")` prints the text and exits 1 — the
        # same code the missing-contract branch above gives. The header separates the
        # two ON PURPOSE: this one the caller clears by running `convene_panel`, that
        # one is a kit defect nobody at this end can fix. Arriving as one code erases
        # the only difference that matters to whoever is reading the exit status.
        print(f"no assignment at {apath}. Run `convene_panel.py --slug {slug} "
              f"--phase {phase} --write` first — briefing reviewers nobody assigned "
              f"produces votes the tally refuses, which is late.", file=sys.stderr)
        raise SystemExit(2)

    assignment = json.loads(apath.read_text(encoding="utf-8"))
    contract = data_path(project, str(source["contract"]))
    artifacts = [data_path(project, str(a).format(slug=slug)) for a in source["artifacts"]]
    context = [data_path(project, str(a)) for a in source["also_read"]]

    missing = [str(p) for p in artifacts if not p.is_file()]
    return {
        "slug": slug,
        "phase": phase,
        "author": assignment.get("author", ""),
        "contract": str(contract),
        "contract_present": contract.is_file(),
        "artifacts": [str(p) for p in artifacts if p.is_file()],
        "artifacts_missing": missing,
        "context": [str(p) for p in context if p.is_file()],
        "reviewers": [
            {**seat, "brief": _brief(seat, slug, phase, contract, artifacts, context,
                                     assignment.get("author", ""))}
            for seat in assignment.get("seats", [])
        ],
    }


def _brief(seat: dict, slug: str, phase: str, contract: Path,
           artifacts: list[Path], context: list[Path], author: str) -> str:
    reads = "\n".join(f"  - {p}" for p in artifacts if p.is_file())
    extra = "\n".join(f"  - {p}" for p in context if p.is_file())
    return f"""You are `{seat.get('agent')}`, seated on the {phase.upper()} panel for `{slug}`.

READ FIRST — the contract you judge against:
  - {contract}

THE ARTIFACT UNDER REVIEW:
{reads}

CONTEXT (not under review; the artifact is judged against it):
{extra or '  (none)'}

The author of this artifact is `{author}`. You did not write it and you may not edit it.

RETURN exactly one verdict — `approve`, `return`, or `abstain` — and a reason of at
least fifteen words naming WHAT you checked against WHICH evidence. A `return` must name
the specific drawing, section or claim it objects to. `abstain` when you could not audit,
and say why: an abstention is counted as an incomplete panel, never as agreement.

Record it with:
  python3 mechanisms/cycle/cast_vote.py --slug {slug} --phase {phase} \\
      --reviewer {seat.get('agent')} --model {seat.get('model')} \\
      --verdict <approve|return|abstain> --reason "<your reason>"
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--reviewer", default="", help="print one reviewer's brief only")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    out = build(args.project.resolve(), args.slug, args.phase)

    if out["artifacts_missing"]:
        print("REFUSED: the panel would review an artifact that is not there:",
              file=sys.stderr)
        for path in out["artifacts_missing"]:
            print(f"  {path}", file=sys.stderr)
        return 1
    if not out["contract_present"]:
        print(f"REFUSED: no contract at {out['contract']}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    if args.reviewer:
        one = next((r for r in out["reviewers"] if r["agent"] == args.reviewer), None)
        if one is None:
            print(f"`{args.reviewer}` is not on this panel. Assigned: "
                  + ", ".join(r["agent"] for r in out["reviewers"]), file=sys.stderr)
            return 1
        print(one["brief"])
        return 0

    print(f"{out['phase'].upper()} panel for `{out['slug']}` — "
          f"{len(out['reviewers'])} reviewer(s), {len(out['artifacts'])} artifact(s)\n")
    for reviewer in out["reviewers"]:
        print(f"  {reviewer['agent']:<32} {reviewer['family']:<10} {reviewer['invocation']}")
    print(f"\nBriefs: --reviewer <agent>. Contract: {out['contract']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

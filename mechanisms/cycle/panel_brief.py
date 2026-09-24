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
_ALIGNMENT = f"{RECORDS}/alignment"

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
    # One seat, and the contract is the threshold rule rather than a golden rule, because that
    # is where the sign-off's terms are written: what each checkbox asks, and that the author
    # never signs. Added 2026-09-23 with the `alignment` seat — declaring the phase in
    # `panel_phases` without an entry here made `test_every_panel_phase_has_a_contract` fail,
    # which is the check doing its job: a panel with no contract grades against taste.
    #
    # The walkthrough is an artifact and not an `also_read`. A reviewer who reads only the brief
    # can confirm a document is internally consistent and nothing else; the flows are where a
    # scenario class either exists or does not, and the sign-off asks about exactly that.
    "alignment": {
        "artifacts": (f"{_ALIGNMENT}/{{slug}}-alignment.md",
                      f"{_ALIGNMENT}/{{slug}}-walkthrough.html"),
        "contract": "skills/_kit-rules/alignment-threshold.md",
        "also_read": (f"{_DISCOVERIES}/{{slug}}-opportunity.md",),
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


def locate(project: Path, slug: str, phase: str) -> dict:
    """Where this phase's artifact and contract WOULD be, present or not.

    Split out of `build` because locating and judging fail on different things.
    `build` refuses when the artifact is missing, which is right for convening a
    panel over nothing — and exactly backwards for a caller whose question is
    where the file goes. Answered with a refusal, such a caller has no choice but
    to hard-code a path, which is how a plugin ended up reading the pre-2026-08
    root and the pre-rename filename in the same string, on all four of its
    stages, for every item in a registry.

    It adds no convention of its own. `PHASE_SOURCES` is the same table `build`
    reads, so a later rename moves one string and every reader follows — which is
    the whole point of the table having been written down once.
    """
    source = PHASE_SOURCES.get(phase)
    if source is None:
        return {"phase": phase, "slug": slug, "known_phases": sorted(PHASE_SOURCES)}
    artifacts = [data_path(project, str(a).format(slug=slug))
                 for a in source["artifacts"]]
    contract = data_path(project, str(source["contract"]))
    return {
        "slug": slug,
        "phase": phase,
        "artifacts": [str(p) for p in artifacts],
        "present": [str(p) for p in artifacts if p.is_file()],
        "missing": [str(p) for p in artifacts if not p.is_file()],
        "contract": str(contract),
        "contract_present": contract.is_file(),
        "context": [str(data_path(project, str(a))) for a in source["also_read"]],
        "known_phases": sorted(PHASE_SOURCES),
    }


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


def _kit_root_note(contract: Path) -> str:
    """Where this project keeps the kit, so a reviewer can resolve a `rules/...` citation.

    Every rule file, every skill and every plan in this ecosystem cites `rules/<name>.md` —
    the kit's own convention. A reviewer handed the plan and nothing else does not, and an
    EXTERNAL seat has no other way to learn it.

    This said `check_evidence_citations.py` "knows the prefix" and told reviewers to run
    it. Both halves were false, and each was falsifiable from the file itself: it has no
    `__main__` — it is a library `run_structural.py` imports, so running it prints nothing
    and exits 0 — and its own comment says it "Excludes paths containing slashes ... v0.1
    keeps the regex conservative", which is the prefix form it was said to know.

    Five readers followed the instruction and read that exit 0 as a pass: a peer session
    four times, and the `vera-technical-arbiter` seat once, which recorded
    "check_evidence_citations exits 0" inside a vote. None of them was careless — the
    instruction was categorical. A brief contradicting, with authority, a limit a detector
    states about itself is worse than the narrow detector: the detector is honest.

    Measured 2026-09-18: the `openai` seat of a PLAN panel returned a plan on exactly this
    — "those paths do not resolve, while only `.claude/rules/...` exists" — while the kit's
    own checker reported 3 citations and 0 unresolved on the same file. The reviewer was
    right about the literal path and wrong about the defect, and the brief is what withheld
    the difference.

    The cost is not one wasted round. A seat that cannot resolve a project's paths returns
    on EVERY plan, so the cross-family requirement stops being the correlated-failure guard
    it is bought to be and becomes a permanent block — and the obvious way out is to stop
    seating the outside reviewer, which is the one seat that catches what two Claudes agree
    on.
    """
    parent = contract.resolve().parent
    if parent.name != "rules" or parent.parent.name != ".claude":
        return ""
    root = parent.parent
    return (
        f"\nHOW PATHS IN THIS PROJECT RESOLVE:\n"
        f"  The kit is installed at `{root}`. A citation written `rules/<name>.md` — the\n"
        f"  convention every rule file and every plan here uses — resolves to\n"
        f"  `{root}/rules/<name>.md`. That is not a broken path.\n"
        f"  What decides it mechanically is the scorer, which runs the citation detector\n"
        f"  for you: `python3 skills/plan-confidence/scripts/run_structural.py <plan>`.\n"
        f"  Read `sub_reports.evidence_citations` in its JSON.\n"
        f"  One limit that detector declares about itself, so you do not read silence as\n"
        f"  clean: it does not look at citations written with a directory prefix. A plan\n"
        f"  citing `rules/<name>.md` may show zero citations found. That is the detector's\n"
        f"  scope, not a verdict on the path — resolve the path yourself against the root\n"
        f"  named above before returning a plan on it.\n"
    )


def _brief(seat: dict, slug: str, phase: str, contract: Path,
           artifacts: list[Path], context: list[Path], author: str) -> str:
    reads = "\n".join(f"  - {p}" for p in artifacts if p.is_file())
    extra = "\n".join(f"  - {p}" for p in context if p.is_file())
    return f"""You are `{seat.get('agent')}`, seated on the {phase.upper()} panel for `{slug}`.

READ FIRST — the contract you judge against:
  - {contract}
{_kit_root_note(contract)}
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
    ap.add_argument("--locate", action="store_true",
                    help="where this phase's artifact and contract go, present or "
                         "not, without convening anything. For a reader outside the "
                         "kit that would otherwise hard-code the path")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.locate:
        found = locate(args.project.resolve(), args.slug, args.phase)
        if "artifacts" not in found:
            # 2 — could not measure. Composing a path from the pattern of the other
            # phases would be the kit inventing a convention for a caller, which is
            # how the wrong path became load bearing in the first place. Saying what
            # IS known keeps the caller from guessing twice.
            print(f"phase `{args.phase}` is not in PHASE_SOURCES, so this kit has no "
                  f"artifact path declared for it. Declared: "
                  f"{', '.join(found['known_phases'])}.", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(found, indent=2))
        else:
            for path in found["artifacts"]:
                print(f"{'present' if path in found['present'] else 'absent '}  {path}")
            print(f"contract  {found['contract']}")
        return 0

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

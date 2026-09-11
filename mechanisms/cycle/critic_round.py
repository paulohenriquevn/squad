#!/usr/bin/env python3
"""Record a critic's round, and decide whether the work goes back or the disagreement escalates.

    python3 mechanisms/cycle/critic_round.py --phase acceptance --slug M3 --project . --brief
    python3 mechanisms/cycle/critic_round.py --phase acceptance --slug M3 \
        --verdict returned --finding "the report names ACCEPTED; the script emitted NOT_VALIDATED"

## The rule this holds

**A critic returns work. It does not stop the chain and wait for a person.**

`verdict-bands.txt` already separates the two axes and argues why deriving one from the
other is wrong in both directions: `FAIL_SOFT` is `redo` and deliberately does NOT block
— *"it sends work back without forbidding the chain from advancing once redone"* —
because blocking ordinary rework *"would wall every loop that is working correctly"*.

So `CRITIC_RETURNED` is that band. The agent fixes what was named and the phase runs
again, inside the same autonomous span.

## And the ceiling, which is the other half of the rule

A critic with no round limit stops the chain by another route: two parties disagreeing
forever is a halt nobody declared and nobody can see. After `max_rounds` — declared per
phase, because a release note and an acceptance verdict do not deserve the same patience
— the disposition passes to `halt_disposition.py`, which is where this kit already
decides whether a stop returns the item to the registry or waits for a person.

The escalation is therefore the one that already exists. This adds a critic, not a
second way of halting.

## What it refuses

  - A phase with no critic declared. `rules/critic-phases.txt` is the population, and a
    phase absent from it has no critic ON PURPOSE — asking for one is asking to add a
    fourth opinion where three already vote.
  - A `returned` with no finding. "I disagree" returns work and tells the agent nothing
    about what to change, which produces the second round and the third.
  - A finding under ten words, for the same reason the panel refuses a thin reason.

Exit codes:
  0  accepted — the phase may proceed
  1  returned — the agent fixes what was named and re-runs the phase
  2  the phase has no critic, or the round could not be recorded
  3  rounds exhausted — the disposition is now halt_disposition.py's
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
from squad.paths import records_dir, write_records_dir  # noqa: E402

CRITICS_LEAF = "critics"
VERDICTS = ("accepted", "returned")
MIN_FINDING_WORDS = 10


@dataclass(frozen=True)
class CriticPhase:
    phase: str
    contract: str
    max_rounds: int
    asked: str


def eco_dir(project: Path) -> Path:
    nested = project / ".claude"
    return nested if (nested / "rules").is_dir() else project


def load_phases(project: Path) -> dict[str, CriticPhase]:
    path = eco_dir(project) / "rules" / "critic-phases.txt"
    out: dict[str, CriticPhase] = {}
    if not path.is_file():
        return out
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4:
            raise ValueError(f"{path}:{lineno}: expected "
                             "`phase | contract | max_rounds | what it is asked`")
        try:
            rounds = int(parts[2])
        except ValueError:
            raise ValueError(f"{path}:{lineno}: max_rounds `{parts[2]}` is not a number") from None
        out[parts[0]] = CriticPhase(parts[0], parts[1], rounds, parts[3])
    return out


def record_path(project: Path, phase: str, slug: str, *, write: bool = False) -> Path:
    base = (write_records_dir(project, CRITICS_LEAF) if write
            else (records_dir(project, CRITICS_LEAF) or write_records_dir(project, CRITICS_LEAF)))
    return base / f"{slug}-{phase}.json"


def load_record(project: Path, phase: str, slug: str) -> dict:
    path = record_path(project, phase, slug)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"slug": slug, "phase": phase, "rounds": []}


def brief(critic: CriticPhase, project: Path, slug: str) -> str:
    record = load_record(project, critic.phase, slug)
    done = len(record["rounds"])
    prior = ""
    if record["rounds"]:
        prior = "\n\nPRIOR ROUNDS — do not repeat a finding the agent already addressed:\n"
        for i, r in enumerate(record["rounds"], 1):
            prior += f"  {i}. [{r['verdict']}] {r.get('finding', '')}\n"

    return f"""You are the critic for the {critic.phase.upper()} phase of `{slug}`.
Round {done + 1} of {critic.max_rounds}.

READ — the contract this phase is judged against:
  {eco_dir(project) / critic.contract}

WHAT YOU ARE ASKED:
  {critic.asked}
{prior}
RETURN `accepted` or `returned`.

A `returned` MUST name what to change, in at least {MIN_FINDING_WORDS} words. "I
disagree" returns the work and tells the agent nothing, which produces this round again.

You return work; you do not stop the chain. The agent fixes what you name and the phase
runs again inside the same autonomous span. After round {critic.max_rounds} the
disposition passes to `halt_disposition.py` — so a finding you cannot make actionable is
better recorded as `accepted` with the concern stated than as a round nobody can close.

Record with:
  python3 mechanisms/cycle/critic_round.py --phase {critic.phase} --slug {slug} \\
      --verdict <accepted|returned> --finding "<what to change>"
"""


def cast(project: Path, phase: str, slug: str, verdict: str, finding: str) -> dict:
    phases = load_phases(project)
    critic = phases.get(phase)
    if critic is None:
        raise SystemExit(
            f"no critic declared for `{phase}`. `rules/critic-phases.txt` is the "
            "population, and a phase absent from it has no critic ON PURPOSE — "
            f"declared: {', '.join(sorted(phases)) or '(none)'}")

    if verdict not in VERDICTS:
        raise SystemExit(f"`{verdict}` is not one of {', '.join(VERDICTS)}")
    if verdict == "returned" and len(finding.split()) < MIN_FINDING_WORDS:
        raise SystemExit(
            f"a `returned` carries {len(finding.split())} word(s); the floor is "
            f"{MIN_FINDING_WORDS}. Name what to change — returning work without saying "
            "what to change produces this round again, and the one after it")

    record = load_record(project, phase, slug)
    record["rounds"].append({
        "verdict": verdict,
        "finding": finding.strip(),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    path = record_path(project, phase, slug, write=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    rounds = len(record["rounds"])
    if verdict == "accepted":
        outcome, code = "CRITIC_ACCEPTED", 0
    elif rounds >= critic.max_rounds:
        #: NOT a new way of halting. The disposition passes to the mechanism that
        #: already decides whether a stop returns the item to the registry or waits for
        #: a person, so the same stop gets the same treatment it gets everywhere else.
        outcome, code = "CRITIC_EXHAUSTED", 3
    else:
        outcome, code = "CRITIC_RETURNED", 1

    return {"outcome": outcome, "exit": code, "rounds": rounds,
            "max_rounds": critic.max_rounds, "record": str(path)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--brief", action="store_true", help="print the critic's brief and stop")
    ap.add_argument("--verdict", default="")
    ap.add_argument("--finding", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    project = args.project.resolve()
    try:
        phases = load_phases(project)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    if args.brief:
        critic = phases.get(args.phase)
        if critic is None:
            print(f"no critic declared for `{args.phase}`. Declared: "
                  f"{', '.join(sorted(phases)) or '(none)'}", file=sys.stderr)
            return 2
        print(brief(critic, project, args.slug))
        return 0

    if not args.verdict:
        ap.error("give --verdict, or --brief to see what the critic is asked")

    try:
        out = cast(project, args.phase, args.slug, args.verdict, args.finding)
    except SystemExit as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(out, indent=2) if args.json else
          f"{out['outcome']} — round {out['rounds']}/{out['max_rounds']}\n"
          f"  {out['record']}" + (
              "\n  The agent fixes what was named and the phase runs again."
              if out["outcome"] == "CRITIC_RETURNED" else
              "\n  Rounds exhausted. `halt_disposition.py` decides what happens to this "
              "stop — the escalation this kit already has, not a second one."
              if out["outcome"] == "CRITIC_EXHAUSTED" else ""))
    return out["exit"]


if __name__ == "__main__":
    raise SystemExit(main())

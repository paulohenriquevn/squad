#!/usr/bin/env python3
"""The phase number a skill claims must agree with the chain that orders it.

    python3 check_phase_numbering.py [--root .] [--json]

WHY THIS EXISTS
---------------
Third of the phase sweeps, and the one that looks INSIDE a cycle.
`check_phase_drift.py` reads `rules/cycle-phases.txt` and asks whether the eight
declared pipeline phases ran. `check_phase_emitters.py` asks whether anything
records each of them. Neither looks at the order of skills WITHIN one cycle,
which is written in two places that had no way to disagree out loud:

  - `rules/cycle-<name>.md § Chain` — the order, as a diagram
  - each `SKILL.md § Cycle contract` — the number, as a sentence

Measured 2026-08-31, and quoted below under the names those skills carried that
day: `/to-plan` and `/edge-case-plan` were renamed to `/plan-write` and
`/plan-edge-cases` later the same day, and rewriting the quotes would describe a
defect in files that did not exist yet.

`/deps-audit` was inserted into `cycle-plan` on 2026-08-26
(the extension is recorded in `deps-audit-golden-rule.md`), and only its own file
was renumbered. The result:

    deps-audit       "phase 3 ... between /edge-case-plan (phase 2)
                      and /plan-confidence (phase 4)"
    plan-confidence  "phase 3"
    plan-improve     "phase 4"

Two skills claimed phase 3, and one of them was told by the other that it was
phase 4. An agent reading either file learned something true about the kit and
false about the other file, and the kit had shipped it to every consumer.

`/to-plan` carried the same insertion defect in prose: its chain listed
`/edge-case-plan → /plan-confidence` with no `/deps-audit`, while
`commands-help` listed it. Two indexes of one chain, disagreeing — caught by
reading, which is exactly what does not scale.

THE INVARIANT, AND WHY IT IS NOT "THE NUMBERS ARE 1..N"
------------------------------------------------------
Cycles number differently on purpose. `cycle-discover` is 1-based;
`cycle-plan` opens with an OPTIONAL phase 0 and a phase 0.5 that was inserted
between two integers precisely so nothing downstream had to move. A checker
demanding a dense 1..N sequence would report all of that as broken and be
switched off within a week.

So the invariant is convention-agnostic, and there are three clauses:

  UNIQUE     — no two skills of one cycle declare the same number
  MONOTONIC  — for the skills a cycle's Chain block orders, the declared
               numbers increase in that order
  UNSKIPPED  — a skill's `requires` predecessor is not a skill the chain places
               BEFORE its actual predecessor

The first two are properties of any sane numbering, whatever base it starts from
and however many half-steps it carries. The third is about the same fact written
in a third place — the `requires` field — and is narrower for the reason below.

WHAT IT DOES NOT CHECK, SAID OUT LOUD
-------------------------------------
It does not check that a number is the RIGHT one, only that the set is coherent.
Renumbering every skill of a cycle consistently but wrongly passes here, and
would be caught by reading the Chain block — which is what a person does and this
does not replace.

The third clause is deliberately narrow. `requires` cannot simply be compared to
the chain: `plan-grill` is optional so `plan-alignment` requires nothing,
`idea-to-release` requires sixteen skills because it orchestrates them, and a
chain may hand off to a skill that belongs to another cycle and whose `requires`
speaks about that one. Checked naively, five of the six mismatches in this kit are
correct work. What is never correct is a skill reaching PAST its predecessor to
something earlier in the same chain: that is an insertion nobody finished.

It also does not require a skill to declare a number at all. A cycle with one
phase says "the only phase", and a conditional skill invoked out of line —
`/plan-improve` — is legitimately absent from the Chain diagram. Demanding a
number from those would manufacture findings, and a checker that fires on correct
work is one somebody disables.

Exit codes:
    0 — every cycle's numbering is coherent
    1 — at least one cycle has a duplicate, an out-of-order number, or a
        `requires` reaching past its own predecessor
    2 — the root is not readable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

#: The ordered skill invocations inside a cycle rule's ``` Chain ``` block.
_INVOCATION_RE = re.compile(r"^\s*/([a-z0-9-]+)", re.MULTILINE)
_CHAIN_RE = re.compile(r"^##+\s*Chain\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
_FENCE_RE = re.compile(r"```(.*?)```", re.DOTALL)

#: `## Cycle contract` and the phase claim inside it. The number is read only from
#: that section: a `SKILL.md` mentioning "phase 2" while explaining someone else's
#: chain is describing, not declaring, and reading it as a declaration is the
#: substring defect this kit has paid for more than once.
_CONTRACT_RE = re.compile(r"^##+\s*Cycle contract\s*$(.*?)(?=^##\s|\Z)",
                          re.MULTILINE | re.DOTALL)
_CLAIM_RE = re.compile(r"\*\*[Pp]hase\s+([0-9]+(?:\.[0-9]+)?)[^*]*\*\*\s*(?:—[^—]*—\s*)?"
                       r"of\s+\[`(cycle-[a-z-]+)`\]")

#: The predecessor a skill declares in its own frontmatter.
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_REQUIRES_RE = re.compile(r"^requires:\s*\[(.*?)\]", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Finding:
    cycle: str
    kind: str          # duplicate_phase_number · phase_out_of_chain_order
                       # · requires_skips_a_phase
    detail: str


def chain_order(rule: Path) -> list[str]:
    """The skills a cycle rule's Chain block invokes, in order, deduplicated."""
    text = rule.read_text(encoding="utf-8", errors="replace")
    section = _CHAIN_RE.search(text)
    if not section:
        return []
    block = "\n".join(_FENCE_RE.findall(section.group(1)))
    order, seen = [], set()
    for name in _INVOCATION_RE.findall(block):
        if name not in seen:
            seen.add(name)
            order.append(name)
    return order


def declared_phase(skill_md: Path) -> tuple[float, str] | None:
    """`(number, cycle)` this skill claims in its own Cycle contract, or None."""
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    contract = _CONTRACT_RE.search(text)
    if not contract:
        return None
    claim = _CLAIM_RE.search(contract.group(1))
    if not claim:
        return None
    return float(claim.group(1)), claim.group(2)


def declared_requires(skill_md: Path) -> list[str]:
    """The skills this one names as prerequisites, from its frontmatter."""
    front = _FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8", errors="replace"))
    if not front:
        return []
    found = _REQUIRES_RE.search(front.group(1))
    if not found:
        return []
    return [name.strip() for name in found.group(1).split(",") if name.strip()]


def _kit_under(root: Path) -> Path:
    """`root` itself, or its `.claude/` when that is where the kit lives.

    A consumer keeps the kit in `.claude/`, so `--root .` — the natural thing to
    type from a project — pointed at a directory with no `skills/` and swept
    nothing. Before the empty-sweep fix that printed a clean PASS; now it prints
    NOTHING_DECLARED, which is honest and still not what the caller meant.
    """
    if (root / "skills").is_dir():
        return root
    nested = root / ".claude"
    return nested if (nested / "skills").is_dir() else root


def surveyed(root: Path) -> tuple[int, int]:
    """`(cycles, skills)` this gate actually looked at under `root`.

    An empty finding list means BOTH "every declared numbering is coherent" and
    "there was nothing declared", and the two must not print the same sentence.
    Measured on 2026-09-02 against an empty tree: this gate printed *"Overall:
    PASS — every cycle's declared numbering is unique and in chain order"* after
    examining zero cycles. That is the shape this kit keeps finding — an
    inability to measure published as a measurement — and five sibling gates
    given the same empty tree said "swept 0 cycle rule(s)" instead.
    """
    root = _kit_under(root)
    rules_dir, skills_dir = root / "rules", root / "skills"
    if not rules_dir.is_dir() or not skills_dir.is_dir():
        return 0, 0
    skills = [s for s in sorted(skills_dir.glob("*/SKILL.md"))
              if declared_phase(s) is not None]
    cycles = {declared_phase(s)[1] for s in skills}
    return len(cycles), len(skills)


def check(root: Path) -> list[Finding]:
    root = _kit_under(root)
    rules_dir = root / "rules"
    skills_dir = root / "skills"
    if not rules_dir.is_dir() or not skills_dir.is_dir():
        return []

    claims: dict[str, dict[str, float]] = {}
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        found = declared_phase(skill_md)
        if found is None:
            continue
        number, cycle = found
        claims.setdefault(cycle, {})[skill_md.parent.name] = number

    findings: list[Finding] = []
    for rule in sorted(rules_dir.glob("cycle-*.md")):
        cycle = rule.stem
        declared = claims.get(cycle, {})
        if len(declared) < 2:
            continue

        # UNIQUE — checked across every skill of the cycle, including the ones the
        # Chain block does not order. `/plan-improve` is invoked conditionally and
        # appears in no diagram, and its number still has to be its own.
        by_number: dict[float, list[str]] = {}
        for name, number in sorted(declared.items()):
            by_number.setdefault(number, []).append(name)
        for number, names in sorted(by_number.items()):
            if len(names) > 1:
                findings.append(Finding(
                    cycle, "duplicate_phase_number",
                    f"phase {number:g} is claimed by {', '.join(names)} — one number, "
                    f"two contracts, and a reader believes whichever file it opened"))

        # MONOTONIC — over the subset the chain actually orders.
        ordered = [(n, declared[n]) for n in chain_order(rule) if n in declared]
        for (before, first), (after, second) in zip(ordered, ordered[1:]):
            if first >= second:
                findings.append(Finding(
                    cycle, "phase_out_of_chain_order",
                    f"`{before}` runs before `{after}` in the Chain block but claims "
                    f"phase {first:g} against {second:g}"))

    # UNSKIPPED — a skill reaching past its own predecessor to something earlier.
    for rule in sorted(rules_dir.glob("cycle-*.md")):
        order = chain_order(rule)
        position = {name: index for index, name in enumerate(order)}
        for previous, current in zip(order, order[1:]):
            skill_md = skills_dir / current / "SKILL.md"
            if not skill_md.is_file():
                continue
            for required in declared_requires(skill_md):
                if position.get(required, len(order)) < position[previous]:
                    findings.append(Finding(
                        rule.stem, "requires_skips_a_phase",
                        f"`{current}` requires `{required}`, which the chain places "
                        f"before `{previous}` — its actual predecessor. Something was "
                        f"inserted between them and this file was not updated"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"FATAL: {root} is not a directory", file=sys.stderr)
        return 2

    findings = check(root)
    cycles, skills = surveyed(root)
    if args.json:
        print(json.dumps({"root": str(root),
                          "cycles_examined": cycles, "skills_examined": skills,
                          "findings": [asdict(f) for f in findings],
                          "verdict": ("FAIL" if findings
                                      else "PASS" if skills else "NOTHING_DECLARED")},
                         indent=2))
        return 1 if findings else 0

    print(f"phase numbering — {root}")
    for finding in findings:
        print(f"  [{finding.kind}] {finding.cycle}: {finding.detail}")
    print()
    if findings:
        print(f"Overall: FAIL — {len(findings)} incoherent phase number(s)")
        return 1
    if not skills:
        print("Overall: NOTHING_DECLARED — 0 skill(s) declare a phase under this "
              "root, so nothing was checked. This is not a pass.")
        return 0
    print(f"Overall: PASS — {skills} skill(s) across {cycles} cycle(s): every "
          f"declared numbering is unique and in chain order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

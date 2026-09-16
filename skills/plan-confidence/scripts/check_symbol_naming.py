#!/usr/bin/env python3
"""A plan may not demand a symbol whose NAME the project's own rule forbids.

THE DEFECT THIS CLOSES
----------------------
Measured on a consumer 2026-09-16: seven plans demanded test names carrying a ticket
number — `TestB069_*`, `TestB046_*`, `TestB047_*` — **101 occurrences**, and the string
appears in ZERO `.go` files. The tests exist under behaviour-shaped names, because the
naming rule forbids the ticket prefix and an implementer renamed them for exactly that
reason. The code is the half that is right.

The plan also contradicted its own alignment brief, which already carried the correct
names. So the contradiction was inside the item's own documents, and nothing compared them.

WHY IT IS INVISIBLE WITHOUT THIS
--------------------------------
**A criterion demanding a string that does not exist reads identically to one nobody has
satisfied yet.** That is the whole point of a RED criterion: the string is supposed to be
absent. `run_validation` filed it under category `test` and passed over it, correctly —
by then the contradiction is already inherited.

So the check cannot key on absence. It keys on the NAME being one the project refuses:
a ticket id inside a symbol. That is decidable from the plan alone, needs no repository
scan, and cannot be confused with a test not yet written.

WHY HERE AND NOT AT IMPLEMENT
-----------------------------
The consumer's own words: "the check belongs where the plan is SCORED, because by
`/implement` the contradiction is already inherited." A plan that demands a forbidden name
is a plan that cannot be satisfied without breaking the rule or breaking the plan, and
finding that out during implementation costs the implementation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: A test symbol carrying a ticket id: `TestB069_x`, `test_b004_y`, `B052ExitCode`,
#: `TestABC-12Foo`. The id is letters-then-digits, or a bare number, glued to the symbol.
#:
#: Deliberately narrow. `TestV2Parser` and `TestSHA256` are NOT tickets — a version and an
#: algorithm — so the pattern requires the digits to be followed by a separator or a
#: capital that starts a new word, AND the prefix to look like a tracker id.
_TICKET_IN_SYMBOL = re.compile(
    r"\b(?:Test|test_|it_)"          # a test symbol's conventional opening
    r"[_]?"
    # ONE letter glued to digits (`B069`, `b004`), or a multi-letter prefix that REQUIRES
    # the hyphen (`ABC-123`). Without the hyphen requirement `TestSHA256Digest` matched —
    # three letters and three digits read as a tracker id, and an algorithm name became a
    # naming violation. The pattern was mine and too broad, which is the same failure as a
    # pre-filter too narrow: the guard deciding instead of measuring.
    r"(?P<id>[A-Za-z]-?\d{2,}|[A-Za-z]{2,4}-\d+)"
    r"(?=[_A-Z]|\b)",
    re.UNICODE,
)

#: Where a plan states what must exist. A symbol named in prose ABOUT the rule — this
#: file's own docstring, a plan explaining why it renamed something — is not a demand.
_DEMAND_CONTEXT = re.compile(
    r"^\s*(?:[-*+]|\d+\.|\|)|`|^####?\s", re.MULTILINE)


#: A criterion writing evidence to a FIXED path under the system temp directory.
#: `/tmp/b069-baseline.txt` is a shared mutable global across concurrent worktrees, and on
#: a consumer 2026-09-16 it collided: two lanes ran, both files ended zero bytes, the
#: `comm -13` criterion over them printed 0 and PASSED while proving nothing, and the
#: file's mtime belonged to the OTHER lane — 82 seconds before its first commit.
#:
#: `mktemp` is exempt: it is the answer, not the problem.
#: An EVIDENCE file, which carries an extension. `/tmp/theo-ops` is a binary the criterion
#: invokes, not a file it writes — and `check_criteria_discriminate` already refuses that
#: separately, by name, as "a binary this will not run unattended". Flagging it here said
#: a shared evidence path was at risk of collision when nothing was being written at all.
#:
#: The extension is the discriminator and its limit is worth stating: an evidence file
#: written without one would be missed. That is the safe direction — the check reports a
#: collision risk, and a false negative costs a warning while a false positive costs the
#: plan a cap it did not earn.
_FIXED_TMP_PATH = re.compile(r"(?<!\$\()/tmp/(?!\$)[\w.-]*\w\.\w{1,8}\b")


@dataclass
class NamingFinding:
    symbol: str
    line_number: int
    line: str


@dataclass
class SymbolNamingReport:
    findings: tuple[NamingFinding, ...] = ()
    occurrences: int = 0
    distinct: tuple[str, ...] = ()
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def soft_floor(self) -> bool:
        """A demand the project's rule forbids caps the plan until it is rewritten."""
        return bool(self.findings)

    #: Findings of the second kind, kept apart so the cap names what fired.
    collisions: tuple[NamingFinding, ...] = ()

    @property
    def stable_id(self) -> str:
        """The id names which of the two fired. One check, two findings, one id was a
        report that lied about its own cause — a plan capped for a `/tmp` path read as
        having been capped for a test name."""
        if self.distinct and self.collisions:
            return "soft_floor_symbol_named_by_ticket_and_shared_evidence_path"
        if self.collisions:
            return "soft_floor_evidence_at_shared_path"
        return "soft_floor_symbol_named_by_ticket"


def check_symbol_naming(plan_path: Path) -> SymbolNamingReport:
    try:
        body = plan_path.read_text(encoding="utf-8-sig")
    except OSError:
        return SymbolNamingReport()

    findings: list[NamingFinding] = []
    for number, line in enumerate(body.splitlines(), 1):
        # Fences and inline code are where a plan WRITES the name it demands; prose
        # explaining a rename mentions it. Both are checked — a demand in prose is still
        # a demand — but a line that only quotes the rule is not.
        if re.search(r"forbid|must not|never name|renamed|§\s*5\.1|rule", line, re.I):
            continue
        for match in _TICKET_IN_SYMBOL.finditer(line):
            findings.append(NamingFinding(match.group(0), number, line.strip()[:160]))

    collisions: list[NamingFinding] = []
    for number, line in enumerate(body.splitlines(), 1):
        if "mktemp" in line or re.search(r"forbid|must not|never|collid", line, re.I):
            continue
        for match in _FIXED_TMP_PATH.finditer(line):
            collisions.append(NamingFinding(match.group(0), number, line.strip()[:160]))

    distinct = tuple(sorted({f.symbol for f in findings}))
    reasons: tuple[str, ...] = ()
    if findings:
        reasons = (
            f"the plan demands {len(findings)} symbol(s) named by a ticket id "
            f"({', '.join(distinct[:4])}{'…' if len(distinct) > 4 else ''}). A ticket "
            f"number dies and the artifact stays, pointing at a tracker that may not "
            f"resolve it — so a plan demanding one cannot be satisfied without breaking "
            f"the naming rule or breaking the plan. Name the test for the behaviour it "
            f"asserts, and check the alignment brief: on the consumer that produced this "
            f"check, the brief already carried the correct names and the plan contradicted "
            f"it.",
        )
    if collisions:
        paths = sorted({c.symbol for c in collisions})
        reasons = reasons + (
            f"{len(collisions)} criterion line(s) write evidence to a FIXED path under "
            f"/tmp ({', '.join(paths[:3])}{'…' if len(paths) > 3 else ''}). That is a "
            f"shared mutable global across concurrent worktrees — on the consumer that "
            f"produced this check it collided, both files ended zero bytes, and the "
            f"criterion over them printed 0 and PASSED while proving nothing. Use "
            f"`mktemp` or a path inside the lane's own worktree.",
        )
    return SymbolNamingReport(tuple(findings) + tuple(collisions), len(findings),
                              distinct, reasons, tuple(collisions))


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = check_symbol_naming(args.plan)
    if args.json:
        import json
        print(json.dumps({
            "occurrences": report.occurrences,
            "distinct": list(report.distinct),
            "soft_floor": report.soft_floor,
            "stable_id": report.stable_id,
            "reasons": list(report.reasons),
        }, indent=2))
    else:
        print(f"symbols named by a ticket: {report.occurrences}")
        for finding in report.findings[:10]:
            print(f"  {args.plan.name}:{finding.line_number}  {finding.symbol}")
        for reason in report.reasons:
            print(f"\n  {reason}")
    return 1 if report.soft_floor else 0


if __name__ == "__main__":
    raise SystemExit(main())

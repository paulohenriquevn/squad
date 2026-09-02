#!/usr/bin/env python3
"""Every declared phase must have something that records it ran.

Third of the contract-versus-code sweeps, after `check_gate_mechanisms.py` (does a
hard gate name what enforces it?) and `check_orphan_verdicts.py` (can anything emit
this verdict?). This one reads `rules/cycle-phases.txt` and asks: **when this phase
runs, does anything write it to the stream?**

WHY IT EXISTS
-------------
Measured on 2026-08-30, before any of the phases below were instrumented:

    backlog       required     silent
    discover      required     silent
    plan          conditional  silent
    implement     conditional  emits
    code-quality  conditional  emits
    review        conditional  emits
    release       conditional  SILENT  <- the verdict ADVANCE consumes
    acceptance    conditional  emits

Four of eight, and the two silent ones were the cycle's ONLY `required` phases. The
one real registry examined — 166 items, 133 of them shipped — had no event file at
all.

The cost is not bookkeeping. `cycle-maintenance.md`'s ADVANCE moves an item to
`shipped` when release reports `RELEASED`, and nothing emitted that, so ADVANCE could
only have INFERRED the release from files on disk. That is what `cycle_events.py`
exists to replace, in its own words: *a missing file is evidence of nothing in
particular*. An ADVANCE built on the inference would write `shipped` on a guess, into
the one artefact that outlives the session, and the contract's own anti-pattern names
that error: *if nothing was released, nothing shipped*.

WHAT IT PROVES, AND WHAT IT DOES NOT
------------------------------------
It proves the phase name reaches an emitter — a `--cycle <phase>` invocation or a
`cycle="<phase>"` argument. It does NOT prove the emitter runs, runs at the right
moment, or runs on every path. An instruction in a SKILL.md is weaker than a line of
code, and that weakness is real: what compensates for it is
`check_phase_drift.py --expect-complete`, which reports a `required` phase that left
no event. This sweep and that one are complementary — one asks whether an emitter
exists at all, the other whether it fired in a given run.

Exit codes: 0 every phase has an emitter · 1 at least one phase is silent
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PHASES_FILE = "rules/cycle-phases.txt"

#: How an emitter names its phase: the CLI flag, or the keyword argument.
def _emitter_patterns(phase: str) -> tuple[re.Pattern[str], ...]:
    escaped = re.escape(phase)
    # `(?![\w-])`, not `\b`. A word boundary sits between `release` and the hyphen of
    # `release-notes`, so `--cycle release-notes` satisfied `release` and a silent phase
    # read as instrumented. Hyphens must still be allowed INSIDE a phase name, because
    # `code-quality` is one.
    return (
        re.compile(rf"--cycle[ \t=]+{escaped}(?![\w-])"),
        re.compile(rf"""cycle=["']{escaped}["']"""),
    )

SEARCH_GLOBS = ("scripts/*.py", "skills/*/scripts/*.py", "skills/*/SKILL.md", "commands/*.md")

#: Files that MENTION a phase without emitting for it — this sweep's own prose, the
#: drift checker's, and the emitter's. Excluded by path so the sweep cannot pass by
#: reading its own docstring.
_SELF = ("mechanisms/gates/check_phase_emitters.py", "mechanisms/gates/check_phase_drift.py",
         "mechanisms/cycle/cycle_events.py")


#: Any phase name an emitter passes, whether or not a contract declares it. The
#: mirror of the sweep below: that one asks whether a declared phase has an emitter,
#: this pattern finds emitters for phases nobody declared.
_EMITTED_NAME_RE = (
    re.compile(r"--cycle[ \t=]+([a-z][a-z0-9-]*)"),
    re.compile(r"""cycle=["']([a-z][a-z0-9-]*)["']"""),
)


@dataclass
class PhaseFinding:
    phase: str
    requirement: str
    detail: str


@dataclass
class EmitterReport:
    phases: int = 0
    emitting: int = 0
    findings: list[PhaseFinding] = field(default_factory=list)
    where: dict[str, list[str]] = field(default_factory=dict)
    #: Phases something emits that `cycle-phases.txt` does not declare.
    undeclared: list[PhaseFinding] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "phases": self.phases,
            "emitting": self.emitting,
            "silent": len(self.findings),
            "undeclared": len(self.undeclared),
            "findings": [f.__dict__ for f in self.findings + self.undeclared],
            "where": self.where,
        }


def declared_phases(repo_root: Path) -> list[tuple[str, str]]:
    """(name, requirement) for each row of `cycle-phases.txt`."""
    path = repo_root / PHASES_FILE
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "|" not in stripped:
            continue
        parts = [p.strip() for p in stripped.split("|")]
        if len(parts) >= 2 and parts[0]:
            out.append((parts[0], parts[1]))
    return out


def check_phase_emitters(repo_root: Path) -> EmitterReport:
    report = EmitterReport()
    corpus: list[tuple[str, str]] = []
    for pattern in SEARCH_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            rel = path.relative_to(repo_root).as_posix()
            if rel in _SELF:
                continue
            try:
                corpus.append((rel, path.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue

    for phase, requirement in declared_phases(repo_root):
        report.phases += 1
        patterns = _emitter_patterns(phase)
        hits = [rel for rel, text in corpus if any(p.search(text) for p in patterns)]
        if hits:
            report.emitting += 1
            report.where[phase] = hits
        else:
            report.findings.append(PhaseFinding(
                phase=phase, requirement=requirement,
                detail=("declared in cycle-phases.txt and named by no emitter — "
                        "nothing records that this phase ran")))

    # The mirror. An emitter for a phase nobody declared writes events that every
    # reader drops: `check_phase_drift.py` scores against the declared set and the
    # board renders a column per declared phase, so the work happens, is recorded,
    # and is invisible anyway.
    #
    # Measured on the first autonomous run: `deps-audit` and `idea-to-release` both
    # emitted into a live stream and neither appears in `cycle-phases.txt` — one of
    # them with a null verdict. Twelve events, and two of the six phases producing
    # them were unknown to everything downstream.
    declared_names = {name for name, _ in declared_phases(repo_root)}
    if declared_names:
        seen: dict[str, str] = {}
        for rel, text in corpus:
            for pattern in _EMITTED_NAME_RE:
                for name in pattern.findall(text):
                    if name not in declared_names:
                        seen.setdefault(name, rel)
        for name, rel in sorted(seen.items()):
            report.undeclared.append(PhaseFinding(
                phase=name, requirement="undeclared",
                detail=(f"emitted from {rel} and absent from {PHASES_FILE} — events for it "
                        "are written and then dropped by every reader")))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = check_phase_emitters(args.repo_root)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
        return 1 if (report.findings or report.undeclared) else 0

    print(f"{report.phases} declared phase(s): {report.emitting} have an emitter, "
          f"{len(report.findings)} silent, {len(report.undeclared)} emitted but undeclared")
    for finding in report.findings:
        print(f"  [silent] {finding.phase} ({finding.requirement})")
        print(f"      {finding.detail}")
    for finding in report.undeclared:
        print(f"  [undeclared] {finding.phase}")
        print(f"      {finding.detail}")

    if report.findings or report.undeclared:
        print("\nA phase nothing records cannot be told from one that was skipped; a phase "
              "nobody declares is recorded and then dropped. Emit the first, declare the "
              "second in " + PHASES_FILE + ".")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

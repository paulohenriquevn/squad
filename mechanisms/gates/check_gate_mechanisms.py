#!/usr/bin/env python3
"""Every declared hard gate names the mechanism that computes it.

WHAT THIS MEASURES, AND WHAT IT REFUSES TO CLAIM
------------------------------------------------
It reads the `## Hard gates` sections of `rules/cycle-*.md` and asks one
question per gate: **does this line say what enforces it?**

It does NOT verify that the named script actually enforces the gate. Proving
that a given `.py` implements a given English sentence is not something a text
scan can do, and pretending otherwise would be the fabricated confidence this
ecosystem caps plans at 49 for. What it proves is narrower and still worth
having: the reader of a rule can reach the mechanism, and a rule cannot name a
mechanism that does not exist.

WHY IT EXISTS
-------------
Measured 2026-08-27 over the nine cycle rules carrying the section: **61 gates
declared, 11 naming a script**. Sampling the five BLOCKERs of `cycle-review.md`
against the hooks showed four of them mechanized and none of them saying so.

A mechanized gate whose rule names no mechanism is indistinguishable, to the
reader, from a gate nobody enforces. This repository has already recorded the
cost of one direction of that confusion:

    "A gate listed among four automatic ones reads as automatic, and a gate
    believed to be automatic is a gate nobody runs."

THE THREE ACCEPTED FORMS
------------------------
| Form | Example | Meaning |
|---|---|---|
| executable | `` `check_wiring.py` `` | this file computes it |
| owner pointer | ``[`cycle-acceptance § Hard gates`](cycle-acceptance.md)`` | another rule owns it |
| explicit exemption | `_(not mechanized: judgement — ...)_` | a human decides, on purpose |

The third form is what keeps the check honest. `/backlog-item`'s G3/G4/G5 are
judgement by design, and the rule that made them conversational said so
deliberately. Demanding a script name on every line would push someone to
invent one — the same defect with extra steps.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date as _date_cls
from pathlib import Path

#: An executable named in backticks. Bare prose mentions do not count: a gate
#: that merely says "vulture" has not told the reader what to run.
#:
#: The corollary matters as much: backticks around a filename in these rules
#: assert *this repository enforces it here*. Referring to a sibling kit's
#: module — "the Squad closed this with a per-language suite runner" — is prose
#: and must stay unbackticked, or the check correctly reports a mechanism that
#: does not exist. It caught exactly that during the port.
#:
#: Trailing arguments stay inside the citation — `flip_milestone_checkbox.py
#: --commit` names the mechanism better than the bare filename, because the flip
#: is only atomic under that flag. Refusing the fuller form would push the author
#: to write the poorer one to satisfy the checker.
_EXECUTABLE_RE = re.compile(r"`([\w./-]+\.(?:py|sh))(?:[ \t][^`]*)?`")

#: A markdown link to a sibling rule, used when another cycle owns the gate.
#: Resolved once so a long sweep cannot straddle midnight and report two ages.
_TODAY = _date_cls.today()


def _date(text: str) -> _date_cls:
    return _date_cls.fromisoformat(text)


_RULE_POINTER_RE = re.compile(r"\]\((?:\./)?((?:rules/)?[\w./-]+\.md)(?:#[\w-]+)?\)")

#: The deliberate exemption. The reason after the colon is mandatory.
#: A qualifier may sit between the marker and the colon — "not mechanized at the
#: point of action:" says something the bare marker cannot, and refusing it would
#: push the author to drop the precision rather than keep it.
_UNMECHANIZED_RE = re.compile(
    r"_\(not mechanized[^:)]*(?::\s*(?P<reason>[^)]+))?\)_"
)

#: The FOUR claims an exemption can make. Added 2026-09-08, because `0 unresolved`
#: proved every gate carried a reason and could not say which KIND of reason — and
#: the seventeen exemptions held three unrelated ones summed into a single number.
#:
#:   judgement   automating it would produce verdicts about LANGUAGE, not about the
#:               work. Permanent by decision, and measured: four were pressure-tested
#:               across model tiers on 2026-08-28 — redundant on Opus, and one caught
#:               a fabricated justification on Haiku. See
#:               `.squad/wiki/references/judgement-gates-are-insurance.md`.
#:   debt        it is missing, and the line says what is missing.
#:   regression  a mechanism EXISTED and was withdrawn. Lost coverage, not debt never
#:               paid — and reading it as debt hides that the kit used to be stricter.
#:   external    a third-party plugin enforces it; this kit can state the wiring and
#:               cannot verify it.
#:
#: "17 gates are not mechanized" invites the wrong conclusion in both directions: that
#: the kit has 17 holes, or that 17 deliberate decisions are equally fine.
#:   composed    it IS enforced, by reading verdicts other mechanisms already
#:               emitted, rather than by one script of its own. Filing this as debt
#:               would report an enforced gate as a hole.
EXEMPTION_CLASSES = ("judgement", "debt", "regression", "external", "composed")

#: `debt` and `regression` end; `judgement` and `external` do not. Only the first two
#: carry a date, so a date on the others would be decoration that goes stale.
_DATED_CLASSES = frozenset({"debt", "regression"})

#: `debt since 2026-01-15 — …` / `judgement — …`
_CLASS_RE = re.compile(
    r"^(?P<klass>" + "|".join(EXEMPTION_CLASSES) + r")\b"
    r"(?:\s+since\s+(?P<date>\d{4}-\d{2}-\d{2}))?\s*[—:-]",
    re.IGNORECASE,
)

#: `## Hard gates`, `### Hard gates (per iteration)`, and so on. The section ends
#: at the next heading of the SAME level or higher — not at any heading at all.
#:
#: It used to stop at `^#{1,6} `, so a subsection under Hard gates truncated it
#: and the sweep silently covered less. Sibling `check_orphan_verdicts.py` fixed
#: the same defect on 2026-08-31 with the measurement in its own comment: adding
#: a `###` under a verdict table dropped its swept count from 51 to 49 with no
#: finding and nothing in the output to notice. This regex was still the pre-fix
#: form until a test forced it into line. A coverage gate that loses coverage
#: without saying so is the failure it exists to prevent, one level up.
#:
#: `(?P=level)` requires the closing heading to be at least as shallow: `###` no
#: longer ends a `##` section, and `##` still does.
#: ANY heading naming a gate, not the literal string `Hard gate`. Measured 2026-09-11:
#: 14 cycle rules on disk, 9 swept. `cycle-design.md` heads its section `## Gates` and
#: `cycle-idea-to-release.md` heads its `## Confidence gates between phases`; both fell
#: through `if not sections: continue`, which neither swept them nor said so. The sweep
#: then reported `0 unresolved` over a population that excluded them — absent reading as
#: clean, which `reference-provenance.md` §6 names and `check_reference_leakage.py`
#: avoids by reporting PARTIAL rather than claiming coverage silently.
_SECTION_RE = re.compile(
    r"^(?P<level>#{2,})[^\n]*[Gg]ate[^\n]*\n(.*?)(?=^(?P=level)(?!#) |\Z)",
    re.MULTILINE | re.DOTALL,
)

#: Not a cycle. It is the schema every cycle rule is written against, so it declares no
#: gates of its own and is not a rule the sweep failed to read.
_NOT_A_CYCLE = {"cycle-rule-schema.md"}

#: A markdown table's separator row: `|---|---|`.
_SEPARATOR_CHARS = set("|-: ")


@dataclass(frozen=True)
class GateFinding:
    """One gate line that cannot be traced to a mechanism."""

    rule: str
    gate: str
    kind: str
    detail: str = ""


@dataclass
class GateReport:
    """What the sweep saw. The counts are part of the output, not a footnote.

    `partial` exists because the two clean categories flatter the result. A gate
    that names a script AND declares a residue — enforced downstream, not at the
    point of action — is neither mechanized nor exempt, and filing it as either
    would overstate what this movement achieved.
    """

    total_gates: int = 0
    named: int = 0
    partial: int = 0
    unmechanized: int = 0
    rules_swept: int = 0
    #: Cycle rules holding no gate section at all. NAMED rather than dropped: a sweep
    #: whose population is smaller than the directory must say which files it did not
    #: read, or `0 unresolved` means something narrower than a reader takes it to mean.
    rules_without_gates: list[str] = field(default_factory=list)
    #: Cycle rules holding no gate section at all. NAMED rather than dropped: a sweep
    #: whose population is smaller than the directory must say which files it did not
    #: read, or `0 unresolved` means something narrower than a reader takes it to mean.
    rules_without_gates: list[str] = field(default_factory=list)
    findings: list[GateFinding] = field(default_factory=list)

    #: How many exemptions of each class. Reported separately because the four make
    #: unrelated claims — see EXEMPTION_CLASSES.
    by_class: dict = field(default_factory=dict)

    #: The earliest date on a `debt` or `regression` exemption, so the report can say
    #: how long the oldest one has stood. Ageing is REPORTED and not enforced by
    #: default: how long a debt may live is the operator's call, and a gate that
    #: failed on age would fire on every consumer that has not set a ceiling.
    oldest_debt: str | None = None


def _is_separator(stripped: str) -> bool:
    """`|---|---|` — the row that makes the line above it a header."""
    return stripped.startswith("|") and set(stripped) <= _SEPARATOR_CHARS


def _gate_lines(section_body: str) -> list[str]:
    """Bullets and table rows. Prose paragraphs between them declare nothing.

    A table's header row is identified structurally — it is whatever line the
    separator follows — rather than by a vocabulary of expected column names.
    The first version matched `#`/`Gate`/`Verdict` and let `| Cap | Trigger |`
    through as a gate, which is the failure mode of every allowlist of words:
    it is correct until someone names a column something else.
    """
    raw_lines = [raw.rstrip() for raw in section_body.splitlines()]
    header_indexes = {
        index - 1
        for index, line in enumerate(raw_lines)
        if index > 0 and _is_separator(line.strip())
    }

    # A gate is the whole bullet or row, wrapped lines included. Reading only
    # the first physical line made the check report three freshly annotated
    # `cycle-review.md` gates as unnamed, because the mechanism had landed on
    # the wrapped line — a checker failing on correct input, which this
    # ecosystem treats as worse than no checker.
    lines: list[str] = []
    for index, line in enumerate(raw_lines):
        stripped = line.strip()
        if index in header_indexes:
            continue
        if not stripped:
            lines and lines.append("")  # blank line ends any open continuation
            continue
        starts_row = line.startswith("|")
        starts_bullet = bool(re.match(r"^\s*[-*]\s+\S", line))

        if starts_row and _is_separator(stripped):
            continue
        if starts_row or starts_bullet:
            lines.append(stripped)
            continue
        # Indented text under an open gate continues it; anything else is prose.
        if lines and lines[-1] and line[:1].isspace():
            lines[-1] = f"{lines[-1]} {stripped}"
    return [line for line in lines if line]


def _executables(repo_root: Path) -> set[str]:
    """Every `.py`/`.sh` in the repository, by basename.

    By basename and not by path because a rule legitimately cites
    `check_tdd_shape.py` without repeating `skills/implement/scripts/`. The
    looser match is the deliberate choice: this check proves reachability, not
    location.
    """
    names: set[str] = set()
    skip = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.suffix not in (".py", ".sh"):
            continue
        if skip & set(path.relative_to(repo_root).parts):
            continue
        names.add(path.name)
    return names


def check_gate_mechanisms(repo_root: Path, *, max_debt_age_days: int | None = None) -> GateReport:
    """Sweep `rules/cycle-*.md` and report every gate with no reachable mechanism."""
    repo_root = Path(repo_root)
    report = GateReport()
    executables = _executables(repo_root)
    rules_dir = repo_root / "rules"
    if not rules_dir.is_dir():
        return report

    for rule_path in sorted(rules_dir.glob("cycle-*.md")):
        text = rule_path.read_text(encoding="utf-8", errors="replace")
        if rule_path.name in _NOT_A_CYCLE:
            continue
        sections = _SECTION_RE.findall(text)
        if not sections:
            #: Named, not skipped. A rule with no gate section is a fact about the
            #: population — `check_prose_write_paths.py` sets the precedent of printing
            #: what was swept so CLEAN can never mean "nothing read".
            report.rules_without_gates.append(rule_path.name)
            continue
        report.rules_swept += 1

        for _hashes, body in sections:
            # A table specifies the output contract of a mechanism the section's
            # prose already named; its rows are not further gates with further
            # enforcers. Bullets never inherit — five bullets under one paragraph
            # are five autonomous claims.
            prose = _prose_of(body)
            inherited = [
                name for name in _EXECUTABLE_RE.findall(prose)
                if Path(name).name in executables
            ]
            # A section-level exemption is inherited the same way and for the
            # same reason: one note where the reader meets the table beats the
            # identical marker pasted into every row, which would read as N
            # independent decisions instead of one.
            prose_exemption = _UNMECHANIZED_RE.search(prose)
            inherited_exemption = bool(
                prose_exemption and (prose_exemption.group("reason") or "").strip()
            )
            for gate in _gate_lines(body):
                report.total_gates += 1
                is_row = gate.startswith("|")
                finding = _classify(
                    rule_path, gate, executables, rules_dir, report,
                    inherited=inherited if is_row else [],
                    inherited_exemption=inherited_exemption and is_row,
                    max_debt_age_days=max_debt_age_days,
                )
                if finding is not None:
                    report.findings.append(finding)
    return report


def _prose_of(section_body: str) -> str:
    """Everything in the section that is neither a bullet nor a table row."""
    return "\n".join(
        line for line in section_body.splitlines()
        if not line.lstrip().startswith("|") and not re.match(r"^\s*[-*]\s+\S", line)
    )


def _classify(
    rule_path: Path,
    gate: str,
    executables: set[str],
    rules_dir: Path,
    report: GateReport,
    inherited: list[str],
    inherited_exemption: bool = False,
    max_debt_age_days: int | None = None,
) -> GateFinding | None:
    exemption = _UNMECHANIZED_RE.search(gate)
    cited = _EXECUTABLE_RE.findall(gate)

    if exemption is not None:
        reason = (exemption.group("reason") or "").strip()
        if not reason:
            return GateFinding(
                rule_path.name, _excerpt(gate), "unmechanized_without_reason",
                "the marker carries no reason — an exemption nobody justified is "
                "an escape hatch, not a record",
            )
        missing = [name for name in cited if Path(name).name not in executables]
        if missing:
            return GateFinding(
                rule_path.name, _excerpt(gate), "fabricated_mechanism",
                f"names {', '.join(missing)}, which does not exist in this repository",
            )
        klass_match = _CLASS_RE.match(reason)
        if klass_match is None:
            return GateFinding(
                rule_path.name, _excerpt(gate), "exemption_without_class",
                "the reason names no class — one of "
                f"{', '.join(EXEMPTION_CLASSES)} must open it, because "
                "'not mechanized' alone conflates a permanent decision, a declared "
                "debt, withdrawn coverage, and somebody else's enforcement",
            )
        klass = klass_match.group("klass").lower()
        date = klass_match.group("date")
        if klass in _DATED_CLASSES and not date:
            return GateFinding(
                rule_path.name, _excerpt(gate), "undated_exemption",
                f"'{klass}' must carry `since YYYY-MM-DD` — without a date nothing "
                "can say how long it has stood, and an undated debt is one nobody "
                "can notice ageing",
            )
        report.by_class[klass] = report.by_class.get(klass, 0) + 1
        if date and (report.oldest_debt is None or date < report.oldest_debt):
            report.oldest_debt = date
        if date and max_debt_age_days is not None:
            age = (_TODAY - _date(date)).days
            if age > max_debt_age_days:
                return GateFinding(
                    rule_path.name, _excerpt(gate), "debt_too_old",
                    f"{klass} standing since {date} ({age} days) exceeds the "
                    f"{max_debt_age_days}-day ceiling this project set",
                )

        # A script cited beside a declared residue: mechanized in part, and the
        # part that is not says so.
        if cited:
            report.partial += 1
        else:
            report.unmechanized += 1
        return None

    if inherited and not cited:
        report.named += 1
        return None

    if inherited_exemption and not cited:
        report.unmechanized += 1
        return None

    if cited:
        missing = [name for name in cited if Path(name).name not in executables]
        if missing:
            return GateFinding(
                rule_path.name, _excerpt(gate), "fabricated_mechanism",
                f"names {', '.join(missing)}, which does not exist in this repository",
            )
        report.named += 1
        return None

    pointers = _RULE_POINTER_RE.findall(gate)
    if pointers:
        missing = [
            target for target in pointers
            if not (rules_dir / Path(target).name).is_file()
        ]
        if missing:
            return GateFinding(
                rule_path.name, _excerpt(gate), "fabricated_mechanism",
                f"points at {', '.join(missing)}, which does not exist",
            )
        report.named += 1
        return None

    return GateFinding(
        rule_path.name, _excerpt(gate), "gate_without_mechanism",
        "names no script, no owning rule, and no explicit exemption",
    )


def _excerpt(gate: str, limit: int = 110) -> str:
    collapsed = re.sub(r"\s+", " ", gate).strip()
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every declared hard gate names its mechanism.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--max-debt-age", type=int, default=None, metavar="DAYS",
        help="fail when a `debt` or `regression` exemption has stood longer than "
             "DAYS. Off by default: how long a debt may live is the operator's call, "
             "and failing on age by default would fire on every consumer that has not "
             "decided its ceiling",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="accepted for symmetry with the other checkers; this one always fails "
             "on a finding, because a gate nobody can trace is not a warning",
    )
    args = parser.parse_args(argv)

    report = check_gate_mechanisms(args.repo_root, max_debt_age_days=args.max_debt_age)

    # The counts print on every run, pass or fail. A checker that says PASS
    # without saying how much it inspected is the empty gate this ecosystem
    # refuses everywhere else.
    #: The population, stated before the counts. A sweep smaller than the directory
    #: that does not say so reports `0 unresolved` about files it never opened.
    if report.rules_without_gates:
        print(f"  no gate section (not swept, not a defect): "
              f"{', '.join(report.rules_without_gates)}")

    plural = "" if report.total_gates == 1 else "s"
    print(
        f"swept {report.rules_swept} cycle rule(s): {report.total_gates} gate{plural} "
        f"— {report.named} named a mechanism, {report.partial} partially mechanized, "
        f"{report.unmechanized} declared exempt, {len(report.findings)} unresolved"
    )

    # The classes print separately, because summing them says "N gates are not
    # mechanized" and invites the wrong conclusion in both directions: that the kit
    # has N holes, or that N deliberate decisions are equally fine.
    if report.by_class:
        MEANING = {
            "judgement": "permanent by decision — a script would grade language",
            "debt": "missing, and the line says what",
            "regression": "a mechanism EXISTED and was withdrawn — lost coverage",
            "external": "a third-party plugin enforces it",
            "composed": "enforced by reading verdicts other mechanisms emitted",
        }
        print("  exemptions by class:")
        for klass in EXEMPTION_CLASSES:
            n = report.by_class.get(klass, 0)
            if n:
                print(f"    {klass:11} {n:2}  — {MEANING[klass]}")
        if report.oldest_debt:
            age = (_TODAY - _date(report.oldest_debt)).days
            print(f"  oldest debt/regression: {report.oldest_debt} ({age} days). "
                  "Reported, not enforced — see --max-debt-age.")

    for finding in report.findings:
        print(f"  [{finding.kind}] {finding.rule}: {finding.gate}")
        if finding.detail:
            print(f"      {finding.detail}")

    if report.findings:
        print(
            "\nEvery hard gate must name what computes it: an executable in "
            "backticks, a link to the rule that owns it, or "
            "`_(not mechanized: <class> — <reason>)_`, where <class> is one of "
            f"{', '.join(EXEMPTION_CLASSES)} and `debt`/`regression` carry "
            "`since YYYY-MM-DD`."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
import ast
import re
import sys
from dataclasses import dataclass, field
from datetime import date as _date_cls
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _contract import ROOT_FLAG  # sibling module; path set just above

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

#: The OTHER place a hard gate is declared: a phase table whose header carries a
#: `Hard gate` column, under a heading with no "gate" in it. `cycle-plan.md` and
#: `cycle-maintenance.md` each hold one under `## Chain`, and both were reported as
#: "no gate section" while declaring ten gates between them — the same miss the note
#: above records, one shape further along. Matched wherever it sits; rows inside a
#: section the heading regex already found are not swept twice.
_HARD_GATE_TABLE_RE = re.compile(
    r"^\|[^\n]*\|\s*Hard gate\s*\|[^\n]*\n\|[-: |]+\|\n(?:\|[^\n]*\n)+",
    re.MULTILINE | re.IGNORECASE,
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
    #: Rows of a phase table whose `Hard gate` column names no enforcer. Counted apart
    #: from `findings` because the two are different claims: a row in a `## Hard gates`
    #: section is a gate somebody declared as such, and a row in a `| Phase | ... | Hard
    #: gate |` table is a phase's output contract that happens to use the same word.
    #: Swept from 2026-09-17 — 41 of them on this repository, invisible until then — and
    #: reported rather than enforced, so that `--strict-phase-rows` is the decision to
    #: make them blocking rather than this sweep making it silently.
    phase_rows_without_mechanism: list[GateFinding] = field(default_factory=list)
    #: Gates in this directory that do not accept the contract's `--root`.
    #:
    #: `_contract.py` declares one flag for "the tree to sweep" because eight spellings
    #: of that question meant THREE callers each carried the whole name-to-flag table —
    #: `verify_ecosystem`'s adapters, `test_gates_say_what_they_examined`'s 22-entry
    #: `ROOT_FLAG` map, and `run_checks.py` refusing to glob at all and parsing the CI
    #: workflow instead. The map whose own comment records a gate sitting "outside the
    #: empty-sweep protection" for a week because it spells its flag `--ecosystem-dir`.
    #:
    #: Checked HERE because this is already the gate that audits the gates.
    gates_without_root_flag: list[str] = field(default_factory=list)
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


def _invocable(repo_root: Path) -> set[str]:
    """Basenames a reader can actually RUN, as opposed to merely find.

    `_executables` above answers "does this file exist", and its docstring says so:
    it proves reachability, not location. Between that and the question this gate
    refuses — whether a `.py` implements an English sentence, which no text scan
    can decide — sits one that IS decidable and was not asked: can the named thing
    be run at all?

    Measured 2026-09-19 across the nine cycle rules: 22 mechanisms named under
    `## Hard gates`, six of them modules with no `__main__`. Every one is genuinely
    enforced — each is imported by a runner that does have an entry point — but a
    reader who follows the rule to the mechanism and runs it gets no output and
    exit 0, which is what a passing gate looks like. This gate exists so "the
    reader of a rule can reach the mechanism", and reaching a library that exits 0
    is reaching something indistinguishable from a pass.

    A `.sh` is invocable by definition. A `.py` needs the entry point, and the
    string is looked for rather than the file imported: importing 200 modules to
    audit them would make this the slowest gate here, and a module that spells its
    guard differently is rarer than one this would break on.
    """
    names: set[str] = set()
    skip = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.suffix not in (".py", ".sh"):
            continue
        if skip & set(path.relative_to(repo_root).parts):
            continue
        if path.suffix == ".sh" or "__main__" in path.read_text(
                encoding="utf-8", errors="replace"):
            names.add(path.name)
    return names


def _gates_without_root_flag(repo_root: Path) -> list[str]:
    """Every `mechanisms/gates/check_*.py` that does not declare `--root`.

    A DECLARATION check, not an invocation: running 31 gates to audit them would
    make this the slowest gate in the directory, and the contract is about the
    argument being declared. A gate keeping its older name as an alias satisfies
    this — that is what aliases are for.

    Read from the AST rather than from the text. Grepping for `"--root"` called
    `check_produced_files.py` compliant, and it takes no root at all: the string
    is there because it INVOKES other gates with it. Which is this kit's own
    most-found defect — a check that could not see its subject reporting a pass —
    committed by the check meant to enforce the contract against it.
    """
    gates = repo_root / "mechanisms" / "gates"
    if not gates.is_dir():
        return []
    missing: list[str] = []
    for path in sorted(gates.glob("check_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            # Unparseable is not compliant, but it is also not THIS gate's finding:
            # `check_python_syntax` owns that, and reporting it twice under two
            # names makes one broken file look like two problems.
            continue
        if not _declares_root(tree):
            missing.append(path.name)
    return missing


def _declares_root(tree: ast.AST) -> bool:
    """Does any `add_argument` in this module declare `--root`, or delegate to
    `_contract.add_root`, which declares it for them?"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else (
            node.func.id if isinstance(node.func, ast.Name) else "")
        if name == "add_root":
            return True
        if name != "add_argument":
            continue
        if any(isinstance(a, ast.Constant) and a.value == ROOT_FLAG
               for a in node.args):
            return True
    return False


def check_gate_mechanisms(repo_root: Path, *, max_debt_age_days: int | None = None) -> GateReport:
    """Sweep `rules/cycle-*.md` and report every gate with no reachable mechanism."""
    repo_root = Path(repo_root)
    report = GateReport()
    executables = _executables(repo_root)
    invocable = _invocable(repo_root)
    report.gates_without_root_flag = _gates_without_root_flag(repo_root)
    rules_dir = repo_root / "rules"
    if not rules_dir.is_dir():
        return report

    for rule_path in sorted(rules_dir.glob("cycle-*.md")):
        text = rule_path.read_text(encoding="utf-8", errors="replace")
        if rule_path.name in _NOT_A_CYCLE:
            continue
        heading_spans = [(m.start(), m.end()) for m in _SECTION_RE.finditer(text)]
        sections = _SECTION_RE.findall(text)
        # Computed once per rule: the gate ids this file declares AND backs with a
        # mechanism, so a phase-contract row citing one is covered by it.
        mechanised_ids = frozenset(
            _mechanised_gate_ids(text, rules_dir, executables))
        phase_tables: list[tuple[str, str]] = []
        # A `Hard gate` COLUMN declares gates as surely as a `## Hard gates` heading.
        # The table is swept WITH the prose of the section it lives in, because that is
        # already how a table inside a gate heading behaves: "a table specifies the
        # output contract of a mechanism the section's prose already named". Harvesting
        # it prose-less would report every row as naming no enforcer while the paragraph
        # two lines above it names one.
        for m in _HARD_GATE_TABLE_RE.finditer(text):
            if any(start <= m.start() < end for start, end in heading_spans):
                continue
            phase_tables.append(("", _enclosing_prose(text, m.start()) + "\n" + m.group(0)))
        if not sections and not phase_tables:
            #: Named, not skipped. A rule with no gate section is a fact about the
            #: population — `check_prose_write_paths.py` sets the precedent of printing
            #: what was swept so CLEAN can never mean "nothing read".
            report.rules_without_gates.append(rule_path.name)
            continue
        report.rules_swept += 1

        for _hashes, body in sections + phase_tables:
            is_phase_table = (_hashes, body) in phase_tables
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
                    rule_path, gate, executables, invocable, rules_dir, report,
                    inherited=inherited if is_row else [],
                    inherited_exemption=inherited_exemption and is_row,
                    max_debt_age_days=max_debt_age_days,
                    mechanised_ids=mechanised_ids,
                )
                if finding is not None:
                    if is_phase_table:
                        report.phase_rows_without_mechanism.append(finding)
                    else:
                        report.findings.append(finding)
    return report


def _enclosing_prose(text: str, at: int) -> str:
    """The body of the `##` section containing `at`, up to that point.

    What a row inherits: the paragraph a reader meets before the table. Anything after
    the table belongs to the rows below it, not to them.
    """
    start = text.rfind("\n## ", 0, at)
    return text[start + 1:at] if start != -1 else text[:at]


def _prose_of(section_body: str) -> str:
    """Everything in the section that is neither a bullet nor a table row."""
    return "\n".join(
        line for line in section_body.splitlines()
        if not line.lstrip().startswith("|") and not re.match(r"^\s*[-*]\s+\S", line)
    )


#: A gate id as a phase-contract row cites it: `(G-B2)`, `(G-B4, G-B5)`, `G1–G5`.
#: Matched against the ids the SAME RULE declares, never against a shape, so a row
#: citing something nobody defined is still a row with no enforcer.
_GATE_ID_RE = re.compile(r"\bG-?[A-Z]{0,2}\d*\b")


def _mechanised_gate_ids(text: str, rules_dir: Path, executables: set[str]) -> set[str]:
    """The ids this rule declares in a `## Hard gates` table AND backs with a mechanism.

    A phase-contract table is a SUMMARY — one line per phase — and the gate itself is
    declared below with an id and an executor. `cycle-brainstorm.md` is the clearest
    case: G-B1 to G-B5 each name `score_product_alignment.py`, and the five summary rows
    above cite `(G-B1)` … `(G-B4, G-B5)`. The executor is named once, where the gate is
    defined, and this follows the reference rather than reporting the summary as
    unenforced.

    Measured 2026-09-21: 42 phase rows were reported as naming no enforcer, and most of
    them cited a gate that does. Burying the rows that really have none among rows that
    do is what made `--strict-phase-rows` unusable — a flag that fails the build on 42
    findings, most of them false, is a flag nobody turns on.

    Laundering is what this must not do, so the id has to be declared here AND the gate
    carrying it has to pass on its own terms.
    """
    ids: set[str] = set()
    for match in _SECTION_RE.finditer(text):
        for line in _gate_lines(match.group(2)):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not cells:
                continue
            candidate = cells[0].strip("` ")
            if not _GATE_ID_RE.fullmatch(candidate):
                continue
            names_executable = any(
                Path(name).name in executables for name in _EXECUTABLE_RE.findall(line))
            points_at_rule = any(
                (rules_dir / Path(target).name).is_file()
                for target in _RULE_POINTER_RE.findall(line))
            exempt = _UNMECHANIZED_RE.search(line)
            if names_executable or points_at_rule or exempt:
                ids.add(candidate)
    return ids


def _classify(
    rule_path: Path,
    gate: str,
    executables: set[str],
    invocable: set[str] | None,
    rules_dir: Path,
    report: GateReport,
    inherited: list[str],
    inherited_exemption: bool = False,
    max_debt_age_days: int | None = None,
    mechanised_ids: frozenset[str] = frozenset(),
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
        # Exists is not the same as runnable. Reported per LINE and not per script,
        # because a line naming a library ALONGSIDE its runner has told the reader
        # what to run; one naming only libraries has sent them to a file that
        # prints nothing and exits 0.
        if invocable is not None and not any(
                Path(name).name in invocable for name in cited):
            return GateFinding(
                rule_path.name, _excerpt(gate), "not_runnable",
                f"names only {', '.join(cited)}, and none of them has an entry "
                f"point. Running one prints nothing and exits 0, which is what a "
                f"passing gate looks like. Name the runner that composes it too",
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

    # A summary row may cite the gate that owns it. Following the reference is the
    # difference between "this phase's gate is declared below" and "nothing computes
    # this" — see `_mechanised_gate_ids`.
    if gate.startswith("|") and mechanised_ids:
        for token in _GATE_ID_RE.findall(gate):
            if token in mechanised_ids:
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
    parser.add_argument(
        "--root", "--repo-root", dest="root", type=Path, default=Path(__file__).resolve().parents[2])
    # The decision to make the newly-swept population blocking, made by a person rather
    # than made silently by widening the sweep. 41 rows joined on 2026-09-17; turning
    # them into a red build the same day would be this gate deciding a backlog.
    parser.add_argument(
        "--strict-phase-rows", action="store_true",
        help="fail when a phase table's `Hard gate` column names no enforcer")
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

    report = check_gate_mechanisms(args.root, max_debt_age_days=args.max_debt_age)

    # The counts print on every run, pass or fail. A checker that says PASS
    # without saying how much it inspected is the empty gate this ecosystem
    # refuses everywhere else.
    #: The population, stated before the counts. A sweep smaller than the directory
    #: that does not say so reports `0 unresolved` about files it never opened.
    if report.rules_without_gates:
        # Wording changed 2026-09-17. This said "not swept, not a defect", which decided
        # in the reader's place that nothing was lost. A rule this sweep did not read is
        # a rule this sweep cannot speak for, and whether that is a defect is not a
        # question the sweep is in a position to answer.
        print(f"  NOT READ ({len(report.rules_without_gates)} rule(s)): "
              f"{', '.join(report.rules_without_gates)} — no gate section and no "
              f"`Hard gate` column, so nothing here was measured against them")
    # The contract, said out loud in both directions. Reported rather than made
    # blocking: adding a gate is already an ordinary change, and a build failing on a
    # missing flag is how the flag gets added without the contract being read.
    if report.gates_without_root_flag:
        print(f"  {len(report.gates_without_root_flag)} gate(s) do not accept `--root` "
              f"(mechanisms/gates/_contract.py): "
              f"{', '.join(report.gates_without_root_flag)}. A caller that does not "
              f"know which gate it is talking to cannot point them at a tree.")
    else:
        print("  every gate accepts `--root` (mechanisms/gates/_contract.py)")

    if report.phase_rows_without_mechanism:
        rows = report.phase_rows_without_mechanism
        print(f"  {len(rows)} phase-table row(s) with a `Hard gate` column name no "
              f"enforcer. Swept from 2026-09-17; before that the column was outside "
              f"the sweep entirely and these read as clean.")
        for finding in rows[:5]:
            print(f"    {finding.rule}: {_excerpt(finding.gate, 90)}")
        if len(rows) > 5:
            print(f"    ... and {len(rows) - 5} more (use --json for all)")

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

    if args.strict_phase_rows and report.phase_rows_without_mechanism:
        report.findings.extend(report.phase_rows_without_mechanism)

    if report.findings:
        print(
            "\nEvery hard gate must name what computes it: an executable in "
            "backticks, a link to the rule that owns it, or "
            "`_(not mechanized: <class> — <reason>)_`, where <class> is one of "
            f"{', '.join(EXEMPTION_CLASSES)} and `debt`/`regression` carry "
            "`since YYYY-MM-DD`."
        )
        return 1
    # A sweep that read NOTHING is not a sweep that found nothing. `rules_swept == 0`
    # happens two ways — no `rules/` at all, or a `rules/` holding no `cycle-*.md` — and
    # both used to reach `return 1 if report.findings else 0`, which is 0 over an empty
    # population. The gate printed "swept 0 cycle rule(s)" and exited like a clean run.
    if report.rules_swept == 0:
        rules_dir = args.root / "rules"
        why = ("there is no `rules/` directory" if not rules_dir.is_dir()
               else f"`{rules_dir}` holds no cycle-*.md")
        print(f"UNCHECKED: no cycle rule was swept — {why}. Nothing here measured "
              f"anything, which is not the same as every gate being named.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

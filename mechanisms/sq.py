#!/usr/bin/env python3
"""`sq` — one entry point for the artifacts of this cycle.

    python3 mechanisms/sq.py contract alignment
    python3 mechanisms/sq.py check .squad/records/alignment/x-alignment.md
    python3 mechanisms/sq.py show  .squad/records/plans/x-plan.md
    python3 mechanisms/sq.py new   alignment my-slug

## Why this exists

Measured 2026-09-23: **143 scripts** under `skills/*/scripts` and **38 gates** under
`mechanisms/gates`, each with its own flags, and no CLI. The count is not the cost. The cost is
that a contract lives only inside a checker's source, so an author learns it one failed run at a
time. A consumer discovered **six exact heading literals by trial and error in one day**:

    check_criterion_executability   wanted `#### Definition of Done`; the author wrote `#### DoD`
    check_baseline_context          wanted `### Current callers / dependents`
    check_drawbacks_section         wanted a bullet not opening in bold
    check_adr_completeness          wanted `### D1` while every plan writes `### ADR-N`

Each of those was a defect on the kit's side, fixed the same day. `sq contract` exists so the next
one is a question an author can ASK instead of a run they have to fail.

## The constraint that shapes every verb: DERIVE, never restate

A hand-written table of headings inside this file would become the seventh place they drift, and
this day is a record of what that costs. So:

  - `KINDS` is the ONE declaration of kind → template, directory, checkers. Nothing restates it.
  - `contract` reads what a checker requires FROM THE CHECKER, through the constants it exposes.
  - A checker that declares nothing is **named as not declaring**, not skipped. Four of seventeen
    declare today; a gap named is a gap somebody can close, and silence reads as "nothing
    required".

## What it does not do

It runs no gate it was not asked for, writes nothing outside the project's records root, and
never guesses a kind. Guessing is how a report says something confident about the wrong contract,
which is the failure this whole file is a response to.

Exit codes: 0 the verb answered · 1 the artifact has findings · 2 the request could not be served
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

OK, FINDINGS, UNSERVED = 0, 1, 2

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent

sys.path.insert(0, str(_ROOT))
from squad.paths import write_records_dir as _write_records_dir  # noqa: E402 — post-bootstrap


@dataclass(frozen=True)
class Kind:
    """One artifact kind, declared once."""

    #: Where a new one is written, relative to the project's records root.
    directory: str
    #: The template it starts from, relative to the kit root. Empty when none ships.
    template: str
    #: Checkers that apply, as `<skill>/scripts/<module>` relative to `skills/`.
    checkers: tuple[str, ...]
    #: How a path announces this kind. Matched against the file NAME, never guessed.
    suffix: str
    #: Constants a checker may expose that say what it requires, in the order tried.
    declares: tuple[str, ...] = ("REQUIRED_SUBSECTIONS", "MANDATORY_SECTIONS",
                                 "REQUIRED_SECTIONS", "SECTION_HEADER_RE")


#: THE declaration. A second place that names a template or a checker is a second place they
#: drift; `tests/test_sq_knows_every_artifact_the_kit_templates.py` keeps it honest by requiring
#: every shipped template to be here or in `NOT_AN_ARTIFACT` with a reason.
KINDS: dict[str, Kind] = {
    "alignment": Kind(
        directory="alignment",
        template="skills/brainstorm-pieces/templates/alignment.template.md",
        checkers=("plan-alignment/scripts/score_alignment",),
        suffix="-alignment.md",
    ),
    "plan": Kind(
        directory="plans",
        template="skills/plan-write/templates/plan-template.md",
        checkers=(
            "plan-confidence/scripts/check_criterion_executability",
            "plan-confidence/scripts/check_baseline_context",
            "plan-confidence/scripts/check_drawbacks_section",
            "plan-confidence/scripts/check_adr_completeness",
            "plan-confidence/scripts/check_concurrency_tests",
            "plan-confidence/scripts/check_coverage_matrix",
        ),
        suffix="-plan.md",
    ),
    "opportunity": Kind(
        directory="discoveries/opportunities",
        template="",
        checkers=("discover-confidence/scripts/check_opportunity_completeness",),
        suffix="-opportunity.md",
    ),
    "measurement-plan": Kind(
        directory="discoveries/opportunities",
        template="skills/discover-plan/templates/measurement-plan-template.md",
        checkers=("discover-plan-confidence/scripts/check_plan_completeness",),
        suffix="-measurement-plan.md",
    ),
}

#: Template shapes that are not a cycle artifact, each with why.
#:
#: BY PATTERN rather than by path, because the alternative measured 24 entries and a list that
#: long is one nobody reads. A pattern still forces the decision — at the level of the shape
#: rather than the file — and a template that fits none of them fails the registry test until
#: somebody classifies it.
NOT_AN_ARTIFACT_PATTERNS: dict[str, str] = {
    "skills/pipeline/templates/stage-*.md": "a prompt for a stage, not an artifact",
    "skills/*/templates/rubric-*.md": "the scoring sheet, not a scored artifact",
    "skills/*/templates/*golden-rule.example.md": "an example of a contract",
    "skills/review/templates/agent-*.md": "an agent's prompt",
    "skills/review/templates/skill-*.md": "a knowledge pack handed to a reviewer",
    "skills/*/templates/*report*.md": "the shape of a report a checker WRITES",
    "skills/brainstorm-*/templates/*.template.md": "a wiki page under wiki/product",
}

#: Exact paths that fit no pattern above, each with why.
NOT_AN_ARTIFACT: dict[str, str] = {
    "skills/design/templates/sign-off.template.md": "a signature block, pasted into a document",
    "skills/discover-execute/templates/opportunity-template.md":
        "the `opportunity` kind's template; the kind registers no template because "
        "`/discover-execute` writes it rather than copying it",
    "skills/implement/templates/implementation-task-template.md":
        "a task block inside a plan, not a document of its own",
    "skills/plan-confidence/templates/holdout-entry-template.md": "one line of a holdout register",
    "skills/plan-write/templates/plan-template-lite.md":
        "the Bounded path's form of the `plan` kind, scored by the same checkers",
    "skills/plan-write/templates/progress.md": "an implementation log, written by /implement",
}


def _load(relative: str):
    """Import a checker by path, without requiring the skill to be a package."""
    path = _ROOT / "skills" / f"{relative}.py"
    if not path.is_file():
        return None, f"{path.relative_to(_ROOT)} is not on disk"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    # REGISTERED before execution, because `@dataclass` resolves its own module through
    # `sys.modules[cls.__module__].__dict__`. Without this every checker holding a dataclass —
    # which is most of them — died on `AttributeError: 'NoneType' object has no attribute
    # '__dict__'` from inside `dataclasses`, and the report said UNREADABLE about a module that
    # reads fine. The kit's own tests already do this (`sys.modules["_oc"] = mod`).
    sys.modules[path.stem] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — a checker that cannot load is reported, not hidden
        return None, f"{path.stem} did not import: {type(exc).__name__}: {exc}"
    return module, ""


def kind_of(path: Path) -> tuple[str, str]:
    """`(kind, why_not)`. Never guesses: a name either announces a kind or it does not."""
    name = path.name
    for label, kind in KINDS.items():
        if name.endswith(kind.suffix):
            return label, ""
    known = ", ".join(sorted(k.suffix for k in KINDS.values()))
    return "", (f"cannot tell the kind of `{name}`. A kind is read from the file name, never "
                f"guessed — guessing is how a report says something confident about the wrong "
                f"contract. Expected one of: {known}")


def _requirements(module, kind: Kind) -> tuple[str, list[str]]:
    """`(constant_name, values)` for what this checker declares, or `("", [])`."""
    for name in kind.declares:
        value = getattr(module, name, None)
        if value is None:
            continue
        if isinstance(value, re.Pattern):
            return name, [value.pattern]
        if isinstance(value, (tuple, list, frozenset, set)):
            items = []
            for entry in value:
                items.append(entry if isinstance(entry, str) else str(entry[0]))
            return name, sorted(items)
    return "", []


def cmd_contract(args) -> int:
    kind = KINDS.get(args.kind)
    if kind is None:
        print(f"unknown kind `{args.kind}`. Known: {', '.join(sorted(KINDS))}", file=sys.stderr)
        return UNSERVED

    print(f"{args.kind} — written to <records>/{kind.directory}/, named `<slug>{kind.suffix}`")
    if kind.template:
        print(f"  template: {kind.template}")
    print()
    undeclared = []
    for relative in kind.checkers:
        module, why = _load(relative)
        name = relative.rsplit("/", 1)[-1]
        if module is None:
            print(f"  {name}: UNREADABLE — {why}")
            continue
        constant, values = _requirements(module, kind)
        if not values:
            undeclared.append(name)
            continue
        print(f"  {name} requires: ({constant})")
        for value in values:
            print(f"      {value}")
    if undeclared:
        print()
        print("  These apply and DO NOT DECLARE what they require, so this cannot print it:")
        for name in undeclared:
            print(f"      {name}")
        print("  Read the module. A gap named is a gap somebody can close; printing nothing")
        print("  would read as `nothing required`, which is how six literals were found by")
        print("  trial and error in one day.")
    return OK


def cmd_check(args) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"{path} is not a file", file=sys.stderr)
        return UNSERVED
    label, why = kind_of(path)
    if not label:
        print(why, file=sys.stderr)
        return UNSERVED

    kind = KINDS[label]
    print(f"{path.name} — kind `{label}`")
    findings = 0
    for relative in kind.checkers:
        module, load_error = _load(relative)
        name = relative.rsplit("/", 1)[-1]
        if module is None:
            print(f"  {name}: UNREADABLE — {load_error}")
            findings += 1
            continue
        entry = getattr(module, name, None) or getattr(module, "check", None)
        if entry is None:
            print(f"  {name}: no callable named `{name}` or `check` — nothing was run")
            findings += 1
            continue
        try:
            report = entry(path)
        except Exception as exc:  # noqa: BLE001 — a checker that raised measured nothing
            print(f"  {name}: RAISED {type(exc).__name__}: {exc} — this measured NOTHING")
            findings += 1
            continue
        print(f"  {name}: {_summarise(report)}")
    return FINDINGS if findings else OK


def _summarise(report) -> str:
    """One line per checker, from whatever shape it returns."""
    if isinstance(report, dict):
        keys = ("verdict", "score", "is_complete", "reasons")
        parts = [f"{k}={report[k]}" for k in keys if k in report]
        return " ".join(parts) or f"{len(report)} field(s)"
    # DERIVED from the report's own fields rather than from a list of attribute names.
    #
    # A hand-written list printed `DrawbacksReport` and nothing else for a checker whose report
    # carries ten fields, because none of them happened to be named in it — the same shape as a
    # frozen parenthetical naming six signals while the matcher held thirty-nine. A summary that
    # names the type is a summary that measured nothing.
    #
    # Booleans and counts are what a reader acts on; a list of reasons is shown by LENGTH, because
    # printing ten reasons per checker turns one line into a wall and `sq show <path>` is where
    # the detail belongs.
    import dataclasses

    if dataclasses.is_dataclass(report):
        parts = []
        for field_ in dataclasses.fields(report):
            value = getattr(report, field_.name)
            if isinstance(value, bool) or isinstance(value, int):
                parts.append(f"{field_.name}={value}")
            elif isinstance(value, str) and value:
                parts.append(f"{field_.name}={value}")
            elif isinstance(value, (tuple, list)) and value:
                parts.append(f"{field_.name}={len(value)}")
        return " ".join(parts) or f"{type(report).__name__} (all fields empty)"

    parts = []
    for attribute in ("verdict", "score", "is_complete", "soft_cap_triggered"):
        if hasattr(report, attribute):
            parts.append(f"{attribute}={getattr(report, attribute)}")
    return " ".join(parts) or type(report).__name__


def cmd_show(args) -> int:
    return cmd_check(args)


def cmd_new(args) -> int:
    kind = KINDS.get(args.kind)
    if kind is None:
        print(f"unknown kind `{args.kind}`. Known: {', '.join(sorted(KINDS))}", file=sys.stderr)
        return UNSERVED
    if not kind.template:
        print(f"`{args.kind}` ships no template; its skill writes it from scratch", file=sys.stderr)
        return UNSERVED
    source = _ROOT / kind.template
    if not source.is_file():
        print(f"{kind.template} is not on disk", file=sys.stderr)
        return UNSERVED

    # `squad.paths` spells the root, never this file. `check_write_containment` caught a
    # hardcoded `".squad/records"` here on the first run — in the module whose whole docstring
    # argues "derive, never restate", which is the defect arriving by the door it was written to
    # guard. The gate's own words: "a second module that can spell a root is how six lists in
    # four different orders happened".
    base = Path(args.into) if args.into else _write_records_dir(Path.cwd())
    target = base / kind.directory / f"{args.slug}{kind.suffix}"
    if target.exists():
        print(f"{target} exists; refusing to overwrite", file=sys.stderr)
        return UNSERVED
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {target}")
    print(f"next: python3 mechanisms/sq.py contract {args.kind}")
    return OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sq", description="One entry point for this cycle's artifacts.")
    sub = parser.add_subparsers(dest="verb", required=True)

    p = sub.add_parser("new", help="scaffold an artifact from its template")
    p.add_argument("kind"); p.add_argument("slug"); p.add_argument("--into", default="")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("check", help="run every checker that applies to this artifact")
    p.add_argument("path"); p.set_defaults(func=cmd_check)

    p = sub.add_parser("show", help="the artifact's current state, as its checkers see it")
    p.add_argument("path"); p.set_defaults(func=cmd_show)

    p = sub.add_parser("contract", help="what the checkers for this kind require")
    p.add_argument("kind"); p.set_defaults(func=cmd_contract)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

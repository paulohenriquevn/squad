#!/usr/bin/env python3
"""Attack the cause of a halt instead of stepping over it.

    python3 skills/backlog-review/scripts/squad_boss.py ~/dev/theo

## The signal this exists for

Measured on 2026-08-31. `/implement` halted on B-033 and wrote a BLOCKED report
naming three pre-existing test failures it could not fix, and naming the items it had
just registered for them: B-168, B-169, B-170. The report then offered a sponsor
three paths — fix them first, accept the failure with a caveat, or change the gate.

The queue sat still for 85 minutes. Not because the answer was hard, but because
every route out of a halt was modelled as a DECISION, and decisions wait for people.

One of those routes is not a decision. B-033 fails its gate because three named items
are unfinished; finishing them makes it pass. Nobody has to choose that — it is what
the report measured. What needs choosing is only whether to SKIP the gate, and that
stays with a person, permanently.

## What it does, and the line it does not cross

It reads the BLOCKED reports on disk, takes the item ids they cite, keeps the ones
still open, and hands the selector an order: work that unblocks a halted item goes
first. That is the whole mechanism.

It does NOT decide anything about the halted item. It does not write `blocked_by`
(that is the report's "Path B", a path nobody chose), does not mark the item blocked,
does not touch its status, and never relaxes the gate that halted it. The halted item
stays exactly where the phase left it, waiting for the person the report addresses —
while the causes it named get built.

## Where it lives

Beside the selector and the board, not in `scripts/`: they are its only callers, and
the registry parsing it leans on lives here too. `scripts/` may not import `skills/`,
so putting it there would have meant duplicating the parse.

## Why this is code and not an agent

Extracting `B-\\d{3,}` from a file and sorting a list needs no judgement, and
`squad_lead.py` already records what a second agent costs: the supervisor that shipped
a NameError on the day it supervised. Every decision this thing does not make is a
decision it cannot get wrong.

The one place judgement could enter — "which of the ids in this prose is really the
cause?" — is answered by measurement instead: an id counts when the registry says it
is still open. A finished item cannot be what holds anything, whatever the prose
around it says. Over-including costs a reordering of the queue; under-including costs
the halt staying put, so the rule leans the cheap way.

Exit codes: 0 reported · 1 the project or its registry is unreadable
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path
from pathlib import Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import (  # noqa: E402 — post-bootstrap import
    DATA_DIRNAME,
    LEGACY_RECORDS_ROOTS,
)

#: Phase output directory -> the phase that writes there. A BLOCKED report is named
#: `{slug}-BLOCKED.md` and lives beside the phase's other artefacts.
#: Declared phases that write NO halt report, each with why. Named rather than omitted, because
#: an omission is indistinguishable from an oversight — and this set has now dropped two phases
#: that way. `test_the_halt_map_covers_every_phase_that_writes_a_record` requires every phase in
#: `rules/cycle-phases.txt` to be in one list or the other.
PHASES_WITHOUT_A_HALT_REPORT = {
    "brainstorm": "writes the four product documents to wiki/product and halts by an UNSIGNED "
                  "sign-off rather than by a report file",
    "design": "writes the five drawings to wiki/design; same signature halt as brainstorm",
    "backlog": "writes the registry itself — a halted item is `blocked_by` in its own block, "
               "which `select_backlog_item` already reads",
    "code-quality": "nested-in implement for the VERDICT; a blocking audit reaches the queue "
                    "through implement's own report",
    "acceptance": "halts the MILESTONE rather than an item — `cycle-acceptance.md` writes "
                  "`BLOCKED — there is nothing released to validate`, which no item's queue "
                  "position depends on",
    # DECLARED AS A GAP rather than mapped, because the honest answer is that nobody measured it.
    # `cycle-discover.md:210` promises "an honest BLOCKED report over a false PASS" for its
    # halt-loop phases and names no directory for it, and inventing one here would be the opposite
    # of deriving — the defect this entry sits beside was a literal set somebody extended from
    # memory. Whoever measures where that report lands moves this line into `HALT_DIRS`.
    "discover": "declares a BLOCKED report in cycle-discover.md and names no directory for it; "
                "UNMEASURED, and mapping it from a guess is how this set acquired its first two "
                "omissions",
}

HALT_DIRS = {
    "implementations": "implement",
    "reviews": "review",
    "releases": "release",
    # `plans` was missing, so a BLOCKED report from the PLAN phase halted nothing while two
    # contracts said it did — `cycle-plan.md` ("a BLOCKED report blocks downstream") and
    # `cycle-maintenance.md` ("SELECT holds the item until the file is gone"). Both true for the
    # directories above and false for this one. Measured by a consumer with one real file moved
    # between two directories: in `plans/` it was not found and SELECT re-offered the halted item;
    # in `maintenance-runs/` the same file, same name, was found and withheld it (#189).
    #
    # SECOND omission in this set — see `maintenance-runs` below — which is why
    # `tests/test_a_halt_in_any_phase_reaches_the_queue.py` now holds the set against
    # `rules/cycle-phases.txt` rather than against a reader's memory.
    "plans": "plan",
    # `cycle-maintenance` declares ITEM_BLOCKED and writes to `maintenance-runs/`,
    # and it was missing here — so a BLOCKED report from the cycle that ORCHESTRATES
    # the queue was invisible to the reader of that queue. A consumer measured it
    # from the inside on 2026-08-31: "meus BLOCKED reports desta data ficam
    # invisíveis ao SELECT até isso", filed as its own blocker and then waiting on a  # english-only: verbatim quotation from a measured item
    # kit fix nobody upstream knew was needed.
    "maintenance-runs": "maintenance",
}

#: Statuses that mean an item is still work. A shipped or killed cause cannot be what
#: holds anything, however the report's prose reads.
#:
#: `approved` belongs here and was missing from 2026-09-04, when the status entered
#: the contract, until 2026-09-05. The effect was the worst direction for this
#: function: a halt whose cause had been APPROVED — committed to, by somebody with
#: the authority — read as no longer live, so the halt was reported as resolvable
#: while the thing holding it was still open. An approved cause is more owned than
#: a triaged one, not less.
OPEN_STATUS = ("raw", "triaged", "approved", "planned")

_ITEM_RE = re.compile(r"\bB-(\d{3,})\b")
_SLUG_ITEM_RE = re.compile(r"\bb-?(\d{3,})\b", re.IGNORECASE)


def _records_dir(project_root: Path) -> Path | None:
    for relative in (f"{DATA_DIRNAME}/records", *LEGACY_RECORDS_ROOTS):
        candidate = project_root / relative
        if candidate.is_dir():
            return candidate
    return None


def _item_of(name: str) -> str:
    """`b033-prometheus-url-dev-public-BLOCKED.md` -> `B-033`."""
    match = _SLUG_ITEM_RE.search(name)
    return f"B-{match.group(1)}" if match else ""


#: A halt whose report carries this in its FILENAME is over.
#:
#: Adopted from a consumer 2026-09-16, where it had been in use and inert. A lane had
#: renamed `B-069-BLOCKED.md` to `B-069-BLOCKED.withdrawn.md` to record that the halt no
#: longer stood — and nothing in this kit read the marker, so the glob below matched it
#: anyway and the item stayed halted on every board and in every selection. A convention
#: a tool does not know is a convention that does nothing, and the person using it has
#: no way to tell.
#:
#: The FILENAME rather than a line inside the file, deliberately. It shows in `ls`,
#: survives a grep, needs no parse, and cannot disagree with itself — a marker in the
#: body would be a second mechanism for one fact, which is the shape this kit keeps
#: removing. A report declaring its own withdrawal in prose is therefore still a live
#: halt here: the fix is to rename the file, and that is one command.
WITHDRAWN_MARKER = ".withdrawn"


#: Item id -> the record of `kind` on disk, for every item that has one.
#:
#: THE reader of "does this item have a record", for the same reason `halt_reports` is
#: the reader of halt files: two scans of one directory drift, and these two already had.
#:
#: Two spellings are in use and each reader knew one. `board_state._slug_for` matched
#: `b022-descriptive-words-plan.md` and missed `B-022-plan.md`; `select_backlog_item`
#: took the filename prefix and matched `B-022-plan.md` while missing the descriptive
#: form. Measured 2026-09-16: the first reported `phases: []` for all 35 items holding a
#: plan and drew a list of empty blocks; the second reported an item with a plan on disk
#: as `awaiting_plan`, which sends a reader to write one that exists.
#:
#: Matching on the FILENAME rather than constructing a slug, because only the phase that
#: wrote the artefact knows the words after the number.
#:
#: And a THIRD spelling, which carries no id in the filename at all: the title slug that
#: `plan-write` itself prescribes ("slug derived from the plan title"). Such a record
#: names its item in its own content, and it was keyed by the bare stem — linked to no
#: item. Measured on a consumer 2026-09-24: `the-nonce-is-minted-and-unreachable-plan.md`,
#: 67229 bytes, frontmatter `milestone_id: B-270`, and `--check B-270` answered "no plan
#: exists yet; run /plan-write to produce it" (#209).
def records_by_item(records: Path, sub: str, suffix: str) -> dict[str, Path]:
    """`{item_id: path}` for every `*{suffix}` in `records/{sub}`, all three spellings."""
    directory = records / sub
    if not directory.is_dir():
        return {}
    found: dict[str, Path] = {}
    for entry in sorted(directory.iterdir()):
        name = entry.name.lstrip(".")
        if not name.endswith(suffix):
            continue
        stem = name[: -len(suffix)]
        item = _item_of(name) or _item_declared_in(entry)
        if item:
            found.setdefault(item, entry)
        elif stem:
            found.setdefault(stem, entry)
    return found


def _item_declared_in(record: Path) -> str:
    """The item a record whose filename names none declares in its content, or ''.

    Through the alignment gate's `_committed_work_id`, not a local reading, because that
    gate grades the SAME plan against the item this returns: two readings of "which item
    is this plan for" would let the selector file a plan under one item while the gate
    grades it against another — the drift `records_by_item` exists to end. Its order is
    declarations first (frontmatter `milestone_id`), then exactly one id in the body, and
    otherwise nothing: several candidates and no declaration are not guessed.

    An ImportError propagates. The two skills ship together, and falling back to a local
    reading whenever the import fails is how the two filename readers above diverged.
    """
    gate_scripts = Path(__file__).resolve().parents[2] / "plan-confidence" / "scripts"
    if str(gate_scripts) not in sys.path:
        sys.path.insert(0, str(gate_scripts))
    from check_alignment_gate import _committed_work_id

    try:
        content = record.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise OSError(f"cannot read record {record} to find the item it declares: "
                      f"{error}") from error
    return _committed_work_id(content) or ""


def halt_reports(project_root: Path) -> dict[str, Path]:
    """Item id -> the BLOCKED report a phase left for it.

    The single reader of these files. `board_state.halted_items`, the selector and
    `mechanisms/fleet/squad_lead.py` all come through here, because two scans of the same
    directory drift the way two copies of a blocking-verdict list already did in this
    repository.

    That was a claim before it was a fact. `squad_lead` carried its own glob until
    2026-09-16 — `*{item[2:]}*-BLOCKED.md`, anchoring BLOCKED to the end, which is the
    exact form the comment below records as wrong. It told a lane "not blocked" for an
    item whose halt report was a lane's second, while the board and the selector said
    blocked: one registry answering two ways depending on which mechanism asked.

    A claim of singleness is a claim nothing checks. The test beside this one now does.
    """
    records = _records_dir(project_root)
    if records is None:
        return {}
    found: dict[str, Path] = {}
    for base in HALT_DIRS:
        directory = records / base
        if not directory.is_dir():
            continue
        # `*BLOCKED*.md`, not `*-BLOCKED.md`: the reports are named by lanes, and a
        # lane writing its second report for one item adds a descriptive suffix.
        # Anchoring BLOCKED to the end of the name dropped those files silently,
        # and a dropped halt is re-offered forever — measured 2026-09-04 (kit#29),
        # B-079 had two halt reports on disk and this function returned neither.
        # `_item_of` decides whether a name carries an id; that is its job, and it
        # already handles both the `B-079-...` and `b165-...` forms.
        for entry in sorted(directory.glob("*BLOCKED*.md")):
            if WITHDRAWN_MARKER in entry.name:
                continue
            item = _item_of(entry.name)
            if item:
                found.setdefault(item, entry)
    return found


def causes_named(report: Path, halted_item: str) -> list[str]:
    """Item ids the report cites, minus the item it is about.

    Prose, read with a regex, because that is what the reports are: `/implement` writes
    them for a person. A stricter parser would need the reports to carry a machine
    section, and inventing that format would leave every report already on disk
    unreadable — including the one that revealed this gap.
    """
    try:
        body = report.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    seen: list[str] = []
    for match in _ITEM_RE.finditer(body):
        item = f"B-{match.group(1)}"
        if item != halted_item and item not in seen:
            seen.append(item)
    return seen


def attack_plan(project_root: Path, statuses: dict[str, str]) -> dict[str, list[str]]:
    """Halted item -> the OPEN items its report names as the cause.

    An entry survives only when at least one cause is still open. A halt whose causes
    all shipped is not something to attack; it is something to re-run, and deciding
    that is the person's.
    """
    plan: dict[str, list[str]] = {}
    for item, report in halt_reports(project_root).items():
        live = [c for c in causes_named(report, item)
                if statuses.get(c, "") in OPEN_STATUS]
        if live:
            plan[item] = live
    return plan


def unblocking_ids(project_root: Path, statuses: dict[str, str]) -> set[str]:
    """Every open item that some halted item's report names as its cause.

    This is the whole contribution to the selector: membership in this set moves an
    item to the front of the queue. It changes ORDER, never eligibility — an item here
    that is blocked or halted is still held by the rules that hold it.
    """
    return {cause for causes in attack_plan(project_root, statuses).values()
            for cause in causes}


def _statuses_from(backlog: Path) -> dict[str, str]:
    """Read `status:` per item, for the CLI only.

    The library path takes statuses from its caller — the selector already parsed the
    registry and re-parsing it here would be a second reading of one file, free to
    disagree with the first.
    """
    body = backlog.read_text(encoding="utf-8-sig", errors="replace")
    out: dict[str, str] = {}
    for block in re.split(r"^(?=## B-\d)", body, flags=re.MULTILINE)[1:]:
        header = re.match(r"## (B-\d+)", block)
        status = re.search(r"^status:\s*(\S+)\s*$", block, re.MULTILINE)
        if header:
            out[header.group(1)] = status.group(1) if status else ""
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", type=Path, nargs="?", default=Path("."),
                        help="project whose records and BACKLOG.md to read")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project = args.project.expanduser().resolve()
    backlog = project / "BACKLOG.md"
    if not backlog.is_file():
        print(f"FATAL: no BACKLOG.md under {project}", file=sys.stderr)
        return 1

    statuses = _statuses_from(backlog)
    reports = halt_reports(project)
    plan = attack_plan(project, statuses)

    if args.json:
        print(json.dumps({
            "halted": sorted(reports),
            "attack_plan": {k: v for k, v in sorted(plan.items())},
            "unblocking": sorted(unblocking_ids(project, statuses)),
        }, indent=2))
        return 0

    if not reports:
        print("No phase has halted. Nothing to attack.")
        return 0

    for item in sorted(reports):
        causes = plan.get(item, [])
        print(f"{item} — halted, report at {reports[item].name}")
        if not causes:
            # Said plainly, because this is the case a person must still resolve and
            # the one most easily read as "handled".
            print("  names no open item as its cause — only a person can move this")
            continue
        print(f"  unblocked by: {', '.join(causes)}")
        for cause in causes:
            print(f"    {cause} is {statuses.get(cause, '?')}")
    unblocking = sorted(unblocking_ids(project, statuses))
    if unblocking:
        print()
        print(f"{len(unblocking)} item(s) move to the front of the queue: "
              f"{', '.join(unblocking)}")
        print("Order only. Nothing here decides anything about the halted item, and "
              "the gate that halted it is untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Assemble what the machine already knows needs a person, before the session starts.

    python3 build_agenda.py [--root .] [--json]

WHY THIS RUNS FIRST
-------------------
`cycle-brainstorm` is the only cycle where a human participates. That decision has
a consequence the pipeline has to honour: **everything that stalled for want of a
human has exactly one place to go**, and if nothing carries it there, it stalls
forever while the queue reports itself healthy.

`rules/autonomy-envelope.md` already names the shape. Its last clause — *"nothing
here fits"* — says to record the impediment and take the next item, so one hard
item never stops the queue. It then says the uncovered case *"goes back to the
human, not as a question to answer now, but as a gap to close later."* This is
what makes "later" a real time rather than a hope.

WHAT IT COLLECTS, AND WHY EACH ONE IS A PERSON'S
------------------------------------------------
  halts            a phase wrote a BLOCKED report; SELECT holds the item out of the
                   queue until it is gone (`cycle-maintenance.md § ITEM_HALTED`)
  unroutable       `repo` belongs to no domain — gate G1. The routing table or the
                   checkout is missing, and neither is the loop's to create
  prose blockers   `blocked_by` naming no `B-NNN`: a sponsor decision, a
                   ratification, an action outside the repository. Measured in
                   `cycle-backlog.md § Impediments`: seven of eight were this
  recent kills     hypotheses measurement refuted. A successful outcome, and the
                   pattern across several is a signal about where hunches come from
  unswept domains  no item has ever cited them, so `BACKLOG_EMPTY` there means
                   nobody looked rather than nothing is wrong
  orphan objectives  an `OBJ-N` no backlog item serves — promised and unworked
  purposeless work   a `shipped` item tracing to no objective

The last two are the pair that make `rules/current-constraint.md`'s admission
cheaper to live with. That file states the kit cannot detect local optimisation
because it does not instrument flow, and that a gate asking the question against
data that does not exist *"would be answered by assertion"*. These two ask a
smaller question that the registry can actually answer.

IT REPORTS AND NEVER DECIDES
----------------------------
No status is written, no item is reprioritised, nothing is created. An agenda that
could act would be a second writer racing `backlog_status.py`, and one writer
owning the status line is what makes a transition refusable at all.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import (  # noqa: E402  # noqa: E402
    DATA_DIRNAME,
    WIKI,
    write_records_dir,
    write_wiki_dir,
)

#: Where `/brainstorm-objectives` writes what the work is for. Same literal
#: `check_objective_coverage.py` uses, built from the same constants.
OBJECTIVES_REL = f"{DATA_DIRNAME}/{WIKI}/product/objectives.md"

_HERE = Path(__file__).resolve()
for _candidate in (_HERE.parents[3] / "skills" / "backlog-review" / "scripts",):
    if _candidate.is_dir():
        sys.path.insert(0, str(_candidate))

OBJ_RE = re.compile(r"^##\s+(OBJ-\d+)\s*(?:—|-)\s*(.+)$", re.MULTILINE)
TRACES_RE = re.compile(r"OBJ-\d+")


@dataclass
class Agenda:
    halts: list[dict] = field(default_factory=list)
    unroutable: list[dict] = field(default_factory=list)
    prose_blockers: list[dict] = field(default_factory=list)
    recent_kills: list[dict] = field(default_factory=list)
    unswept_domains: list[str] = field(default_factory=list)
    orphan_objectives: list[dict] = field(default_factory=list)
    purposeless_shipped: list[dict] = field(default_factory=list)
    #: A field this agenda READS that nothing in the kit WRITES. Reported once, about
    #: the kit, rather than once per item — the items are not where the gap is.
    schema_gaps: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(
            len(x) for x in (
                self.halts, self.unroutable, self.prose_blockers, self.recent_kills,
                self.orphan_objectives, self.purposeless_shipped, self.schema_gaps,
            )
        ) + len(self.unswept_domains)


def _records_root(root: Path) -> Path:
    """`.claude/records/` is canonical; the kit's own repo is the one exception.

    `rules/records-location.md` measured what happens when a reader picks the wrong
    one: an audit reported a repository as having zero implementations, reviews and
    releases when it had six, twelve and eight.
    """
    return write_records_dir(root)


def _load_items(root: Path):
    backlog = root / "BACKLOG.md"
    if not backlog.is_file():
        return None, "no BACKLOG.md — run /backlog-init after this session"
    try:
        from check_backlog_structure import _parse_items, parse_blocked_by
    except ImportError:
        return None, "backlog-review scripts not importable; item signals skipped"
    items = _parse_items(backlog.read_text(encoding="utf-8"))
    return (items, parse_blocked_by), None


def _objectives(root: Path) -> list[tuple[str, str]]:
    path = write_wiki_dir(root, "product") / "objectives.md"
    if not path.is_file():
        return []
    return [(m.group(1), m.group(2).strip()) for m in OBJ_RE.finditer(path.read_text(encoding="utf-8"))]


def _known_domains(root: Path) -> set[str]:
    try:
        sys.path.insert(0, str(_HERE.parents[3] / "mechanisms" / "cycle"))
        from route_domain import _routing_table_path, parse_routing_table
    except ImportError:
        return set()
    table_path = _routing_table_path(root)
    if table_path is None:
        return set()
    try:
        return set(parse_routing_table(table_path))
    except (ValueError, OSError):
        return set()


def _halt_reports(root: Path) -> dict:
    """Items a phase stopped on -> the report, from the one reader of those files.

    Empty on ImportError rather than falling back to a glob: a second implementation
    appearing whenever an import fails is how readers diverge, and a missing halt in an
    agenda is a line the reader adds by hand.
    """
    here = Path(__file__).resolve()
    for up in here.parents:
        scripts = up / "skills" / "backlog-review" / "scripts"
        if (scripts / "squad_boss.py").is_file():
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            break
    try:
        from squad_boss import halt_reports  # noqa: PLC0415
    except ImportError:
        return {}
    return halt_reports(root)


def build(root: Path) -> Agenda:
    ag = Agenda()

    # --- halts: a BLOCKED report on disk holds its item out of the queue --------
    records = _records_root(root)
    if records.is_dir():
        # Through `squad_boss.halt_reports`, not a glob of our own. This listed
        # `*-BLOCKED.md` itself until 2026-09-16, which anchors BLOCKED to the end of
        # the name — the form that reader documents as wrong, because a lane writing a
        # second report for one item adds a descriptive suffix and the anchor misses it
        # (measured 2026-09-04: B-079 had two reports on disk and the anchored glob
        # returned neither). It also counted a halt marked `.withdrawn` in its filename,
        # which that reader now skips.
        #
        # Third reader of these files found in one sweep. The first called itself "the
        # single reader", and a claim of singleness is a claim nothing checks — so a
        # test checks it now.
        for item, report in sorted(_halt_reports(root).items()):
            ag.halts.append({
                "report": str(report.relative_to(root)),
                "item": item,
            })
    else:
        ag.notes.append(f"no records directory at {records.relative_to(root)} — halt signals skipped")

    loaded, note = _load_items(root)
    if note:
        ag.notes.append(note)
    if loaded is None:
        ag.orphan_objectives = [
            {"id": oid, "title": title, "why": "no registry to serve it yet"}
            for oid, title in _objectives(root)
        ]
        return ag

    items, parse_blocked_by = loaded
    domains = _known_domains(root)
    cited_domains: set[str] = set()
    served: set[str] = set()

    for it in items:
        status = it.fields.get("status", "")
        domain = it.fields.get("domain", "")
        if domain:
            cited_domains.add(domain)

        traces = TRACES_RE.findall(it.fields.get("traces_to", ""))
        served.update(traces)

        if domain and domains and domain not in domains:
            ag.unroutable.append({
                "item": it.item_id, "title": it.title, "domain": domain,
                "repo": it.fields.get("repo", ""),
            })

        raw = it.fields.get("blocked_by", "").strip()
        if raw and raw.lower() != "none" and status not in {"shipped", "killed"}:
            if not parse_blocked_by(raw):
                ag.prose_blockers.append({"item": it.item_id, "title": it.title, "blocked_by": raw})

        if status == "killed":
            ag.recent_kills.append({
                "item": it.item_id, "title": it.title,
                "kill_reason": it.fields.get("kill_reason", "(none recorded)"),
            })

        if status == "shipped" and not traces:
            ag.purposeless_shipped.append({"item": it.item_id, "title": it.title})

    #: A FIELD NOBODY WRITES IS NOT A GAP IN EVERY ITEM — it is one gap, in the schema.
    #:
    #: `traces_to` was read here and written by nothing: `cycle-backlog.md` declared
    #: itself the item schema's source of truth and listed twelve fields, none of them
    #: this one, and `/backlog-item`'s grill never asked. So `not traces` was
    #: unconditionally true and this section printed one row per shipped item.
    #:
    #: Measured on a consumer: 243 rows, in a registry where no item COULD have traced.
    #: And it lands in the one cycle a person attends — `cycle-brainstorm.md` promises
    #: them "what the machine already knows needs you", and handed them a list as long
    #: as their shipped history.
    #:
    #: The producer landed on 2026-09-11 — the field is in the schema table and Q5 of
    #: the intake grill asks for it — so the old message ("nothing in the kit writes
    #: it") became false the moment it was fixed, and a stale explanation is the same
    #: defect one layer up. What an empty field means now depends on one thing this
    #: function can check: whether the project HAS objectives to trace to.
    #:
    #: no objectives document → nothing to trace to; not a gap in any item
    #: objectives declared     → the link was skipped, and that IS a finding
    #:
    #: When SOME items carry the field, the ones without it are a real gap and are
    #: reported item by item, which is what this section was written for.
    if not any(it.fields.get("traces_to", "").strip() for it in items):
        ag.purposeless_shipped = []
        objectives = root / OBJECTIVES_REL
        if objectives.is_file():
            ag.schema_gaps.append({
                "field": "traces_to",
                "read_by": "build_agenda.py",
                "written_by": "/backlog-item Q5",
                "why": (
                    f"`{OBJECTIVES_REL}` declares objectives and no item in this "
                    "registry cites one. The field is in the schema and the intake "
                    "grill asks for it, so every item here predates that or skipped "
                    "the question — and until they are linked, nothing can say which "
                    "objective this backlog leaves uncovered"),
            })
        else:
            ag.schema_gaps.append({
                "field": "traces_to",
                "read_by": "build_agenda.py",
                "written_by": "/backlog-item Q5, when objectives exist",
                "why": (
                    f"this project has no `{OBJECTIVES_REL}`, so there is nothing for "
                    "an item to trace to and no item carrying the field is correct. "
                    "Reporting every shipped item as tracing to no objective would "
                    "assert a gap against a standard this project never adopted; "
                    "`/brainstorm-objectives` is what makes the question answerable"),
            })

    ag.unswept_domains = sorted(domains - cited_domains)

    for oid, title in _objectives(root):
        if oid not in served:
            ag.orphan_objectives.append({
                "id": oid, "title": title, "why": "no backlog item traces to it",
            })

    # Kills are informative in bulk, not individually. Newest first, capped, and the
    # cap is REPORTED — a silent truncation reads as "that was all of them".
    if len(ag.recent_kills) > 10:
        dropped = len(ag.recent_kills) - 10
        ag.recent_kills = ag.recent_kills[-10:]
        ag.notes.append(f"{dropped} older kill(s) not listed — read BACKLOG.md for the full set")

    return ag


def render(ag: Agenda) -> str:
    out = ["# Brainstorm agenda", ""]
    if ag.total == 0:
        out += [
            "Nothing is waiting on you.",
            "",
            "That is not the same as nothing being wrong — it means no phase stalled for",
            "want of a person since the last session. Bring what you want to bring.",
            "",
        ]

    def block(title: str, rows: list, fmt) -> None:
        if not rows:
            return
        # `extend`, not `+=`: augmented assignment to a closed-over name makes it
        # local to this function, and every call raises UnboundLocalError.
        out.append(f"## {title} ({len(rows)})")
        out.append("")
        out.extend(f"- {fmt(r)}" for r in rows)
        out.append("")

    block("Halted — a phase stopped and left a report", ag.halts,
          lambda r: f"`{r['item']}` — {r['report']}")
    block("Unroutable — the repo belongs to no domain (gate G1)", ag.unroutable,
          lambda r: f"`{r['item']}` {r['title']} — domain `{r['domain']}`, repo `{r['repo']}`")
    block("Waiting on a decision only a person can make", ag.prose_blockers,
          lambda r: f"`{r['item']}` {r['title']} — {r['blocked_by']}")
    block("Objectives nothing serves", ag.orphan_objectives,
          lambda r: f"`{r['id']}` {r['title']} — {r['why']}")
    block("Shipped, tracing to no objective", ag.purposeless_shipped,
          lambda r: f"`{r['item']}` {r['title']}")
    block("A field this agenda reads and nothing writes", ag.schema_gaps,
          lambda r: f"`{r['field']}` — read by {r['read_by']}, written by "
                    f"{r['written_by']}. {r['why']}")
    block("Killed since you last looked (a successful outcome)", ag.recent_kills,
          lambda r: f"`{r['item']}` {r['title']} — {r['kill_reason']}")
    if ag.unswept_domains:
        out.append(f"## Domains no item has ever cited ({len(ag.unswept_domains)})")
        out.append("")
        out.append("`BACKLOG_EMPTY` here means nobody looked, not that nothing is wrong.")
        out.append("")
        out += [f"- `{d}`" for d in ag.unswept_domains]
        out.append("")
    if ag.notes:
        out += ["## What could not be read", ""] + [f"- {n}" for n in ag.notes] + [""]
    out += ["---", "", "This agenda reports. It changes nothing, and it is not a priority order."]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    ag = build(args.root.resolve())
    print(json.dumps(ag.__dict__, indent=2) if args.json else render(ag))
    return 0


if __name__ == "__main__":
    sys.exit(main())

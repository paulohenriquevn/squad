#!/usr/bin/env python3
"""The plan's declared impediment and the registry's must be the same edge.

THE DEFECT THIS CLOSES
----------------------
`cycle-backlog.md` puts the edge on the BLOCKED side: an item held by another carries
`blocked_by` in its own registry block, and every reader — `select_backlog_item`,
`board_state`, `pipeline_orchestrator`, `backlog_index` — resolves it from there.

A plan also declares one, in its frontmatter. **Nothing compared the two.** Measured on a
consumer 2026-09-16: TEN plans declare `blocked_by` that their registry block does not
carry, nine of them naming the same blocker. Every scheduler read the registry, saw no
impediment, and treated those items as free to start — while the plan that describes the
work says they are not.

The direction of the error is the dangerous one. A missing edge does not stop anything: it
lets an item be picked, planned against and dispatched, and the impediment surfaces when
the work hits it. An edge declared in a document nobody joins is an impediment that costs
its discovery twice.

WHY THE PLAN IS NOT SIMPLY TRUSTED
----------------------------------
It is reported, never written. The registry is one person's record of what holds what, and
a script that edited it from a plan's frontmatter would be a second writer — the shape
`backlog_status.py` exists to be the only one of. `board_state` and every queue resolve the
registry; this says when the two disagree and leaves the decision where it belongs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: `blocked_by: B-034`, `blocked_by: none`, `blocked_by: "access — ..."`. Only the ids
#: matter; prose after them is the reason and travels with whichever side carries it.
_ID = re.compile(r"\b[A-Z]{1,4}-\d+\b")
_FIELD = re.compile(r"^blocked_by:\s*(?P<value>.*)$", re.MULTILINE)


@dataclass
class ImpedimentReport:
    plan_declares: tuple[str, ...] = ()
    registry_declares: tuple[str, ...] = ()
    missing_in_registry: tuple[str, ...] = ()
    missing_in_plan: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @property
    def applies(self) -> bool:
        return bool(self.plan_declares or self.registry_declares)

    @property
    def soft_floor(self) -> bool:
        """Neither direction caps. This reports a disagreement it cannot adjudicate.

        The first version capped the missing-in-registry direction at 89, on the reasoning
        that a plan saying an item is held while the registry says it is free is the
        dangerous half. A consumer session refuted it before it ran on their tree, and the
        refutation is the reason this property returns False:

        Seven of their plans declared `blocked_by: B-034` for a cap — `no_languages_audited`
        — that `code-quality-languages.txt` CURED on 2026-09-14, after all seven were
        written. Five of them score 100.0 with zero caps, which is the proof: **a plan
        cannot score 100.0 if the cap it declares as blocking were live.** Capping them
        would have held five structurally perfect plans on a reason that no longer exists,
        and writing the seven edges would have held seven items on it.

        So the asymmetry pointed the wrong way for the case that produced it. A plan may
        predate an IMPEDIMENT — the original reasoning — and it may equally predate a
        CURE. Both are the plan being out of date with the registry, and nothing in either
        document says which.

        What would decide it is whether the CONDITION the edge names still holds, and that
        is decidable for this class because the plan states it in prose and names a file.
        It is not decidable in general. Widening the check until it guesses is what this
        property refuses to do; a reader with both lines in front of them decides.
        """
        return False

    @property
    def stable_id(self) -> str:
        return "soft_floor_impediment_not_in_registry"


def _ids_from(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    value = text.strip().strip('"\'')
    if value.lower() in ("none", "-", "n/a", ""):
        return ()
    # The ids come BEFORE the reason. `blocked_by: B-034 — declared in the plan since it
    # was written; found by the B-018 panel` names one blocker and mentions another item
    # in its prose, and reading the whole line made B-018 block itself. The reason is
    # separated by an em dash, a colon or a semicolon, and everything after it is
    # narrative — which is where a second id is a citation rather than an edge.
    head = re.split(r"\s+[—–]\s+|\s*[;:]\s+", value, maxsplit=1)[0]
    return tuple(sorted(set(_ID.findall(head))))


def _registry_block(backlog: Path, item: str) -> str | None:
    try:
        body = backlog.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    parts = re.split(rf"^##\s+{re.escape(item)}\b", body, flags=re.MULTILINE)
    return parts[1].split("\n## ")[0] if len(parts) > 1 else None


def check_impediment_agrees(plan_path: Path, backlog: Path | None = None,
                            item: str | None = None) -> ImpedimentReport:
    try:
        head = "\n".join(plan_path.read_text(encoding="utf-8-sig").splitlines()[:30])
    except OSError:
        return ImpedimentReport()

    item = item or plan_path.stem.removesuffix("-plan")
    plan_ids = _ids_from((_FIELD.search(head) or {}).group("value")
                         if _FIELD.search(head) else None)

    # Walk UP for it rather than assuming a depth. `parents[3]` was the first version and
    # it is the same defect as `convene_panel.py`'s `parents[2]`, fixed an hour earlier in
    # this same session: a fixed index is correct for one layout and wrong for the next,
    # and here it raised IndexError on any plan closer to the root than the consumer's.
    if backlog is None:
        for parent in plan_path.resolve().parents:
            if (parent / "BACKLOG.md").is_file():
                backlog = parent / "BACKLOG.md"
                break
    block = _registry_block(backlog, item) if backlog and backlog.is_file() else None
    if block is None:
        where = backlog if backlog else "any BACKLOG.md above the plan"
        return ImpedimentReport(plan_ids, (), (), (), (
            f"no `## {item}` block in {where} — the plan's impediment cannot be "
            f"compared with a registry entry that is not there",) if plan_ids else ())

    registry_ids = _ids_from((_FIELD.search(block) or {}).group("value")
                             if _FIELD.search(block) else None)
    missing_registry = tuple(i for i in plan_ids if i not in registry_ids)
    missing_plan = tuple(i for i in registry_ids if i not in plan_ids)

    reasons: list[str] = []
    if missing_registry:
        reasons.append(
            f"the plan declares `blocked_by: {', '.join(missing_registry)}` and the "
            f"`## {item}` block in {backlog.name} does not carry it. Every scheduler "
            f"resolves the impediment from the REGISTRY — `select_backlog_item`, "
            f"`board_state`, `pipeline_orchestrator` — so this item reads as free to "
            f"start while the plan describing the work says it is held. Record the edge "
            f"on the blocked side with `backlog_status.py --block-on`, which is the only "
            f"writer of that line — OR correct the plan, if the condition the edge names "
            f"has since been cured. This check cannot tell those apart: a plan may predate "
            f"an impediment and it may equally predate its cure. A score of 100.0 with "
            f"zero caps is strong evidence for the second, because a plan cannot reach it "
            f"while the cap it names as blocking is live.")
    if missing_plan:
        reasons.append(
            f"the registry holds `{', '.join(missing_plan)}` and the plan's frontmatter "
            f"does not repeat it — reported, not charged: the registry is authoritative "
            f"and the plan may predate the impediment.")
    return ImpedimentReport(plan_ids, registry_ids, missing_registry, missing_plan,
                            tuple(reasons))


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--backlog", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = check_impediment_agrees(args.plan, args.backlog)
    if args.json:
        print(json.dumps({
            "plan_declares": list(report.plan_declares),
            "registry_declares": list(report.registry_declares),
            "missing_in_registry": list(report.missing_in_registry),
            "soft_floor": report.soft_floor,
            "reasons": list(report.reasons),
        }, indent=2))
    else:
        print(f"plan: {report.plan_declares or '—'}   registry: {report.registry_declares or '—'}")
        for reason in report.reasons:
            print(f"\n  {reason}")
    return 1 if report.soft_floor else 0


if __name__ == "__main__":
    raise SystemExit(main())

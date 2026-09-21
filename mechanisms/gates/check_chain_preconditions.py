#!/usr/bin/env python3
"""Can this installation finish the chain? Asked before it starts, not at the gate.

    python3 mechanisms/gates/check_chain_preconditions.py [project] [--json]

    0  every precondition holds — the chain can reach RELEASE
    1  a precondition fails — starting now produces work that cannot land
    2  could not measure

## The night this exists because of

A consumer ran the chain for hours on 2026-09-13. It produced 85 backlog items, 57
measured opportunities, 39 panels and 13 plans scoring 89-100 structurally — and **zero**
implemented, because every plan hit `no_languages_audited` at the quality gate. The
cause was one unconfigured file: the shipped language template, 83 lines, every one a
commented example, never filled in for that project.

Nothing was wrong with the work. Each phase did its job and the gate was right to refuse.
The defect is WHEN the refusal arrived: at the end, after the effort, on an item-by-item
basis that made it look like a property of each item rather than of the installation.

The owner's rule, written after reading that run:

    it is better to run nothing than to have unresolved conditions that block the system

That is what this implements. These are conditions on the INSTALLATION, knowable in
milliseconds before any work starts, that decide whether work started now can ever land.

## What belongs here, and what does not

A precondition is a fact about the installation that **no amount of good work can
overcome**. An empty language config is one: every plan will be INVALID regardless of
how good the plan is.

A judgement is not a precondition. Whether Go's deferred mutation cap should be
dismissed by ADR, which languages a repository wants audited, whether a baseline should
be recorded — those are decisions with defensible answers on both sides, and a gate that
refused to start until someone made them would be a gate that refuses to start.

The test is: **would this stop every item, whatever anyone does to the item?** If yes it
belongs here. If it stops some items, or is arguable, it belongs to the phase that meets
it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import routing_table, rules_dir  # noqa: E402 — post-bootstrap import


@dataclass
class Check:
    name: str
    ok: bool | None                 # None: could not measure
    detail: str
    fix: str = ""

    @property
    def mark(self) -> str:
        return {True: "ok  ", False: "FAIL", None: "  ? "}[self.ok]


@dataclass
class Report:
    checks: list = field(default_factory=list)

    @property
    def failed(self) -> list:
        return [c for c in self.checks if c.ok is False]

    @property
    def unmeasured(self) -> list:
        return [c for c in self.checks if c.ok is None]


def _rules_dir(project: Path) -> Path | None:
    """Delegated. Nine sites resolved this pair by hand and six used the other order."""
    return rules_dir(project)


def _data_rows(path: Path) -> list[str]:
    """Non-comment, non-blank lines. The shape every rule table in this kit uses."""
    return [ln for ln in path.read_text(encoding="utf-8-sig").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def check_languages(project: Path) -> list[Check]:
    """The one that cost the night, and the follow-up it would still have hidden."""
    rules = _rules_dir(project)
    if rules is None:
        return [Check("code-quality languages", None,
                      "no rules directory found — is the kit installed here?",
                      "bash mechanisms/distribution/install.sh <project>")]
    path = rules / "code-quality-languages.txt"
    if not path.is_file():
        return [Check("code-quality languages", None, f"{path} does not exist",
                      "reinstall, or write the file")]

    rows = _data_rows(path)
    enabled = [r for r in rows if "ENABLED" in r]
    if not enabled:
        return [Check(
            "code-quality languages", False,
            f"{len(rows)} data row(s), none ENABLED — the quality gate will audit "
            "nothing and every plan will be INVALID on `no_languages_audited`",
            f"add one row per language this repository holds to {path}, e.g. "
            "`go | api/go.mod | ENABLED |`")]

    # Second question, and the one an enablement check alone would hide. Measured on the
    # same consumer: `go | go.mod | ENABLED` was accepted by every structural check and
    # audited NOTHING, because the repository is a `go.work` workspace whose modules live
    # in `api/`, `pkg/` and `operators/` — there is no `go.mod` at the root. The row was
    # present, well formed, and pointed at a file that does not exist.
    out = [Check("code-quality languages", True,
                 f"{len(enabled)} language(s) enabled")]
    missing = []
    for row in enabled:
        parts = [p.strip() for p in row.split("|")]
        if len(parts) < 2:
            continue
        language, manifest = parts[0], parts[1]
        if manifest and not (project / manifest).exists():
            missing.append(f"{language} -> {manifest}")
    if missing:
        out.append(Check(
            "language manifests", False,
            "enabled language(s) point at a manifest that is not here: "
            + "; ".join(missing)
            + " — the gate skips them and audits nothing, which reads as INVALID",
            "point each row at a manifest that exists (a workspace member, not the "
            "workspace root)"))
    else:
        out.append(Check("language manifests", True,
                         "every enabled language's manifest is present"))
    return out


def is_the_kit_itself(project: Path) -> bool:
    """Is this the kit's own checkout rather than a project that installed it?

    The two preconditions below are the CONSUMER's to satisfy, and the kit ships
    both deliberately unmet: `BACKLOG.md` is never versioned (it is the maintainer's
    own register, not the product's), and `rules/domain-routing.txt` ships with no
    rows because the table describes repositories the kit does not have.

    So this gate refused the kit's own tree on every run, permanently, for the state
    the kit is supposed to be in — and a gate that always refuses is a gate whose
    refusal carries no information. Told apart by the manifest: only the kit's own
    checkout carries `.claude-plugin/plugin.json` beside `skills/` and `mechanisms/`.
    """
    manifest = project / ".claude-plugin" / "plugin.json"
    return (manifest.is_file()
            and (project / "skills").is_dir()
            and (project / "mechanisms" / "gates").is_dir())


def check_routing(project: Path) -> Check:
    """Without a routing row, gate G1 refuses every item at intake."""
    table = routing_table(project)
    if table is None:
        return Check("domain routing", False,
                     "no domain-routing.txt anywhere — gate G1 refuses every item "
                     "with `unroutable_repo`, so nothing can be filed",
                     "run /backlog-init, or write the table by hand")
    rows = _data_rows(table)
    if not rows:
        if is_the_kit_itself(project):
            return Check("domain routing", None,
                         f"{table.name} ships with no rows ON PURPOSE — the table "
                         "describes a consumer's repositories, and this is the kit. "
                         "Not measurable here, and not a failure of this tree.")
        return Check("domain routing", False,
                     f"{table} has no routing row — every item is unroutable (G1)",
                     "add one row per repository: `<domain> | <repos> | <agent file>`")
    return Check("domain routing", True, f"{len(rows)} routing row(s) in {table.name}")


def check_backlog(project: Path) -> Check:
    path = project / "BACKLOG.md"
    if not path.is_file():
        if is_the_kit_itself(project):
            return Check("backlog", None,
                         "no BACKLOG.md, and this is the kit — the register is the "
                         "maintainer's and is never versioned. Not measurable here, "
                         "and not a failure of this tree.")
        return Check("backlog", False, "no BACKLOG.md — there is nothing to work on",
                     "run /backlog-init")
    items = len(re.findall(r"^## B-\d+", path.read_text(encoding="utf-8-sig"), re.M))
    return Check("backlog", True, f"{items} item(s) registered")


def check_approved(project: Path) -> Check:
    """Has anyone decided what the run is FOR?

    This is the precondition the owner added after watching a run produce 85 items and
    zero implemented: **the system never starts on a backlog nobody approved.**

    It belongs here and not in the item loop because it has the shape every other check
    here has — it is a fact about the installation that no amount of good work overcomes.
    An unapproved registry is not a queue of work; it is a queue of hypotheses. Starting
    on it spends hours deciding, item by item and by inference, the one question
    `cycle-backlog.md` reserves for a person: *is this the work you want done?*

    Measured on a consumer before this existed: 85 items at `triaged`, zero at
    `approved`, and a night of execution against a list nobody had said yes to.

    It is satisfied by ONE approved item, not by all of them. A backlog is approved
    incrementally and a run works one item at a time; demanding the whole registry be
    decided before anything starts would make the gate the thing it refuses — a gate
    that never lets you begin.
    """
    path = project / "BACKLOG.md"
    if not path.is_file():
        return Check("approved work", None,
                     "no BACKLOG.md, so nothing can be approved either", "")
    text = path.read_text(encoding="utf-8-sig")
    # B-197 — both sides of the subtraction counted over the SAME blocks.
    #
    # The first version counted the population as `^status: approved` and the attributions as
    # every `^approved_by:` line in the FILE. Different domains, so the moment a registry
    # advanced past `approved` the remainder went negative: measured on a consumer
    # 2026-09-21, `11 approved · 41 by the loop · -30 unattributed`, printed as `[ok]`.
    #
    # Widening the population to the committed statuses was a HALF-MEASURE, recorded here
    # because the number proved it: the same registry then read `-3`, since a `killed` item
    # approved before it died still carries the field. Widening one side of a subtraction does
    # not make two populations the same population; counting both over one set of blocks does.
    #
    # The committed set is the honest population for the question the split answers — "has
    # anyone read this registry?" — because an item that shipped was read by whoever committed
    # to it. Same set `check_backlog_structure.py` fires `approval_unattributed` over, so the
    # two instruments agree about who owes an attribution.
    _committed_re = re.compile(r"^status:\s*(?:approved|planned|shipped)\s*$", re.M)
    _blocks = [b for b in re.split(r"(?m)^(?=## B-\d{3} )", text) if _committed_re.search(b)]
    approved = len(_blocks)
    committed_by_human = sum(1 for b in _blocks if re.search(r"^approved_by:\s*human/", b, re.M))
    committed_by_system = sum(1 for b in _blocks if re.search(r"^approved_by:\s*system/", b, re.M))
    triaged = len(re.findall(r"^status:\s*triaged\s*$", text, re.M))
    if approved:
        # WHO approved, not just how many. Since 2026-09-14 a sweep finding is born
        # `approved` under a standing authorisation, so a count alone stopped being able
        # to answer "has anyone read this registry?" — and a loop that approves its own
        # findings can feed itself. The split is reported at the one moment it can still
        # change a decision: before the next run starts.
        by_human, by_system = committed_by_human, committed_by_system
        unattributed = approved - by_human - by_system
        parts = [f"{approved} item(s) approved"]
        if by_human or by_system:
            parts.append(f"{by_human} by a person, {by_system} by the loop itself")
        if unattributed:
            parts.append(f"{unattributed} with no attribution — those predate "
                         "`approved_by` and are not evidence a person decided")
        detail = " · ".join(parts)
        # Not a failure: a registry nobody has read is a legitimate state to be in, and
        # an illegitimate one to be in unknowingly. The gate makes it known.
        return Check("approved work", True, detail)
    return Check(
        "approved work", False,
        f"no item is `approved` ({triaged} sit at `triaged`) — the registry holds "
        "hypotheses nobody has committed to, and a run over it decides by inference "
        "what only a person may decide",
        "render the page, tick what you want done, sign, and apply:\n"
        "         python3 <kit>/skills/backlog-approve/scripts/build_approval_brief.py .\n"
        "         /sign <the brief it names> --as <your name>\n"
        "         python3 <kit>/skills/backlog-approve/scripts/apply_approval.py . <brief>")


def measure(project: Path) -> Report:
    rep = Report()
    rep.checks.append(check_backlog(project))
    rep.checks.append(check_approved(project))
    rep.checks.append(check_routing(project))
    rep.checks.extend(check_languages(project))
    return rep


def render(rep: Report, project: Path) -> str:
    lines = [f"chain preconditions — {project.name}", ""]
    for c in rep.checks:
        lines.append(f"  [{c.mark}] {c.name}: {c.detail}")
        if c.ok is not True and c.fix:
            lines.append(f"         fix: {c.fix}")
    lines.append("")
    if rep.failed:
        lines += [
            f"REFUSED: {len(rep.failed)} precondition(s) fail.",
            "",
            "  Work started now cannot reach RELEASE. Every item would pass through the",
            "  phases and stop at the same gate, and the refusal would arrive after the",
            "  effort rather than before it — which is what happened to one consumer:",
            "  85 items, 13 plans scoring 89-100, zero implemented, one unconfigured file.",
            "",
            "  Fix the lines above, then start.",
        ]
    elif rep.unmeasured:
        lines.append(f"NOT MEASURED: {len(rep.unmeasured)} check(s) could not run. "
                     "That is not a pass.")
    else:
        lines.append("The chain can complete. Nothing here blocks an item from reaching "
                     "RELEASE.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refuse to start a chain that cannot finish.")
    # `--root` beside the positional, per `_contract.py`. The positional stays: a
    # consumer already types it, and the contract is about what a caller can rely
    # on, never about taking something away.
    #
    # Separate dests, resolved here. Sharing one `dest` silently broke the flag:
    # argparse applies the absent positional's default AFTER parsing the option, so
    # `--root /elsewhere` was overwritten by `.` and this gate reported on the
    # directory the shell stood in, under a heading naming the other tree.
    parser.add_argument("positional_project", nargs="?", metavar="project",
                        type=Path, default=None)
    parser.add_argument("--root", dest="project", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project = (args.project or args.positional_project or Path(".")).resolve()
    rep = measure(project)
    if args.json:
        print(json.dumps({"checks": [
            {"name": c.name, "ok": c.ok, "detail": c.detail, "fix": c.fix}
            for c in rep.checks]}, indent=2, ensure_ascii=False))
    else:
        print(render(rep, project), end="")
    if rep.failed:
        return 1
    if rep.unmeasured:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

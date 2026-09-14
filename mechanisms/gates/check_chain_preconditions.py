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
from squad.paths import routing_table  # noqa: E402


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
    for candidate in (project / ".claude" / "rules", project / "rules"):
        if candidate.is_dir():
            return candidate
    return None


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
        return Check("domain routing", False,
                     f"{table} has no routing row — every item is unroutable (G1)",
                     "add one row per repository: `<domain> | <repos> | <agent file>`")
    return Check("domain routing", True, f"{len(rows)} routing row(s) in {table.name}")


def check_backlog(project: Path) -> Check:
    path = project / "BACKLOG.md"
    if not path.is_file():
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
    approved = len(re.findall(r"^status:\s*approved\s*$", text, re.M))
    triaged = len(re.findall(r"^status:\s*triaged\s*$", text, re.M))
    if approved:
        return Check("approved work", True,
                     f"{approved} item(s) approved and ready to run")
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
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
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

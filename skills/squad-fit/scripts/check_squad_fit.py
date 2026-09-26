#!/usr/bin/env python3
"""Can this project actually run the squad? Asked of the whole install, once.

    python3 skills/squad-fit/scripts/check_squad_fit.py
    python3 skills/squad-fit/scripts/check_squad_fit.py /path/to/project --json

## The premise

The kit ships fourteen squad agents and thirty-odd skills. It ships
`agents/<domain>.md` EMPTY on purpose — a specialist describes repositories that
exist in one ecosystem, so shipping someone else's makes gate G1 refuse every item
a consumer files. `agents/README.md` records what that cost on an adopter in
2026-08-18: 88 items carrying real `file:line` evidence, all `BLOCKER/unroutable_repo`.

So every consumer has a gap on the day it installs, and the gap is not a defect —
it is the design. What was missing is anything that MEASURES the gap. The kit could
say *this one item is unroutable* (`route_domain.py`, exit 3) and *this one seat
cannot be filled* (`check_panel_capability.py`), item by item and seat by seat,
after the work had already been selected. Nothing answered the question a person
asks BEFORE adopting: what do I have to write, and what breaks until I do.

## What it is not

It is NOT a second opinion about routing, panels or skill structure. Every check
below delegates to the mechanism that already owns that judgement —
`parse_routing_table`, `agents_dir`, `check_panel_capability`, `check_sop_structure`.
A second implementation would disagree with the first, and the disagreement would
surface as a project passing one and failing the other with nothing changed.

What this adds is the SET: the same questions asked of everything at once, so the
answer is a list of work rather than a wall met one item at a time.

## What it does NOT check, named rather than left to be discovered

  - WHETHER AN AGENT IS ANY GOOD. `agent_thin` counts the four things
    `agents/README.md` requires a specialist to carry. A file with all four,
    every one of them wrong, reads as complete here. Judging a specialist means
    knowing the domain, which is exactly what the specialist exists to hold.
  - WHETHER A BUILD COMMAND WORKS. The README requires commands "verified on disk
    rather than copied from a table". This reports whether the command's script or
    manifest EXISTS, never whether running it succeeds — running a consumer's build
    from a read-only diagnostic is a side effect nobody asked for.
  - WHETHER A SKILL DOES WHAT IT SAYS. Structure only: frontmatter parses, an SOP
    exists, the map names it. A skill whose body contradicts its description passes.

## Verdicts

Tokens come from `rules/verdict-bands.txt` and are never invented here.

  SHIPPABLE               no findings — the squad can run on this project as installed
  SHIPPABLE_WITH_CAVEATS  minors only
  NEEDS_REVISION          a major — writing the missing file closes it
  INVALID                 a blocker — the chain cannot route or cannot form a panel

Exit codes, matching the rest of the kit:
  0  SHIPPABLE or SHIPPABLE_WITH_CAVEATS
  1  INVALID
  2  a section could not be measured; NO verdict is reported for it
  3  NEEDS_REVISION
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

for _up in Path(__file__).resolve().parents:
    if (_up / "mechanisms" / "cycle" / "route_domain.py").is_file():
        sys.path.insert(0, str(_up / "mechanisms" / "cycle"))
        sys.path.insert(0, str(_up / "mechanisms" / "gates"))
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import (  # noqa: E402 — post-bootstrap import
    routing_table,
    write_routing_table,
)

#: The fourteen roles `agents/README.md` calls "mechanism": each describes a DECISION
#: rather than a repository, which is why they may be versioned in the kit when a
#: domain specialist may not. Read from disk rather than listed here — a hardcoded
#: roster is the defect `board_state.py` records against itself, where a literal tuple
#: of eight phase names survived the file that declares them gaining a ninth.
KIT_AGENT_MARKER = "## The squad"

#: A fenced block, which is how every specialist in the kit's own tree writes a
#: build command. `agents/README.md` requires commands "verified on disk rather
#: than copied from a table"; whether they were verified is not observable from
#: here, but their ABSENCE is.
CODE_FENCE = re.compile(r"^```", re.MULTILINE)

SEVERITY_ORDER = {"blocker": 0, "major": 1, "minor": 2}


@dataclass(frozen=True)
class Finding:
    """One thing wrong, and whether the machine is sure about it."""

    code: str
    severity: str          # blocker | major | minor
    kind: str              # deterministic | heuristic
    subject: str           # the file, domain or seat the finding is about
    detail: str


@dataclass
class Section:
    """One area of the diagnosis, and whether it could be measured at all."""

    name: str
    measured: bool
    findings: list[Finding] = field(default_factory=list)
    #: Why nothing was measured. Required when `measured` is False, because a
    #: section that reports no findings and no reason reads as a clean section.
    unmeasured_because: str = ""
    facts: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.measured and not self.unmeasured_because:
            raise ValueError(
                f"section `{self.name}` was not measured and does not say why — "
                "an unmeasured section with no reason is indistinguishable from a "
                "clean one, which is the failure this whole kit is written against")


def eco_dir(project: Path) -> Path:
    """Where the kit is installed inside this project.

    A plugin install nests it under `.claude/`; a standalone copy is the project
    itself. Probed by `skills/`, which both layouts have and which nothing else
    in a consumer tree is called.
    """
    nested = project / ".claude"
    return nested if (nested / "skills").is_dir() else project


def agents_dir(project: Path) -> Path:
    """Where this project keeps its specialists — `convene_panel.agents_dir`'s answer.

    Imported when the mechanism is reachable so the two can never drift; the local
    body is the fallback for a consumer install that copied skills without mechanisms.
    """
    try:
        # Optional sibling: absent in a skills-only install,
        # which is what the ImportError below handles.
        from convene_panel import agents_dir  # type: ignore[import-not-found]

        _canonical = agents_dir
    except ImportError:
        nested = project / ".claude" / "agents"
        return nested if nested.is_dir() else project / "agents"
    return _canonical(project)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


# --------------------------------------------------------------------------- agents


def diagnose_agents(project: Path) -> Section:
    """Which domains have a specialist, which specialists nobody routes to.

    The blocker here is `route_domain.py`'s exit 3 asked of every domain at once
    instead of one item at a time. Its wording is deliberately the same, so a person
    who hits BROKEN ROUTE later recognises what this told them earlier.
    """
    agents = agents_dir(project)

    #: Asked of the path owner, not resolved here. This check carried its own
    #: `eco / "rules" / "domain-routing.txt"` and kept it through the 2026-09-10 move
    #: to the write root — so it reported NOT MEASURED against a project whose table
    #: was on disk the whole time. It failed honestly, which is why the defect was
    #: visible at all, but a second resolver is how two mechanisms come to disagree
    #: about where a project keeps its routing.
    table_path = routing_table(project)

    if table_path is None:
        return Section(
            "agents", measured=False,
            unmeasured_because=(
                f"no routing table under {write_routing_table(project)} or the "
                "locations installs used before it — derive one with "
                "`skills/backlog-init/scripts/detect_domains.py --root . --write`. "
                "Reporting every domain as uncovered from a missing table would "
                "assert a violation the evidence does not support"))

    try:
        # Optional sibling: absent in a skills-only install,
        # which is what the ImportError below handles.
        from route_domain import parse_routing_table  # type: ignore[import-not-found]
        table = parse_routing_table(table_path)
    except ImportError:
        return Section(
            "agents", measured=False,
            unmeasured_because=(
                "`mechanisms/cycle/route_domain.py` is not reachable from here, and "
                "this check refuses to parse the routing table with a second parser — "
                "two parsers disagreeing about what the table says is worse than one "
                "check not running"))
    except (ValueError, OSError) as exc:
        return Section(
            "agents", measured=False,
            unmeasured_because=(
                f"the routing table exists and did not parse: {exc}. A file that does "
                "not parse tested nothing; reporting it as a pass would produce "
                "confidence where there was no verification"))

    findings: list[Finding] = []
    routed: set[str] = set()

    for domain, row in sorted(table.items()):
        #: `parse_routing_table` returns the cell as written, and the canonical format
        #: (`domain | repo | agents/x.md`) has no backticks while every example in the
        #: kit's own files does. Left unnormalised, `Path(declared).name` carries a
        #: trailing backtick and every specialist on disk reads as missing — a table
        #: written the documented way would have produced a blocker per domain.
        declared = (row.get("agent") or "").strip().strip("`")
        if not declared:
            findings.append(Finding(
                "domain_names_no_agent", "blocker", "deterministic", domain,
                f"domain `{domain}` covers {len(row.get('repos') or [])} repo(s) and "
                "names no specialist. Every item routed here stops at BROKEN ROUTE"))
            continue

        routed.add(Path(declared).name)
        target = (agents / Path(declared).name)
        if not target.is_file():
            findings.append(Finding(
                "domain_without_agent", "blocker", "deterministic", domain,
                f"domain `{domain}` routes to `{declared}`, which is not on disk. "
                f"`route_domain.py` exits 3 (BROKEN ROUTE) for every item whose repo "
                f"is one of: {', '.join(row.get('repos') or []) or '(none listed)'}"))
            continue

        body = _read(target).lower()
        repos = [r for r in (row.get("repos") or []) if r]
        #: DETERMINISTIC, and the strongest signal here: a specialist that never
        #: names a repository it owns does not know its own scope. Compared against
        #: the routing table rather than against a word list — the first version of
        #: this check asked whether the file contained the word "repository" and
        #: reported six of six hand-written specialists as thin, every one of them
        #: false. A check that fires on everything teaches people to ignore it,
        #: which `rules/auxiliary-skills.txt` records as a real cost.
        unnamed = [r for r in repos if Path(r).name.lower() not in body and r.lower() not in body]
        if repos and len(unnamed) == len(repos):
            findings.append(Finding(
                "agent_names_none_of_its_repos", "major", "deterministic", declared,
                f"`{declared}` owns {', '.join(repos)} and names none of them. The "
                "routing table sends those repos here; the specialist reading this "
                "file cannot tell which code it is responsible for"))
        elif unnamed:
            findings.append(Finding(
                "agent_omits_a_repo", "minor", "deterministic", declared,
                f"`{declared}` does not name {', '.join(unnamed)}, which the routing "
                f"table assigns to `{domain}`. Either the file predates the repo or "
                "the table sends work somewhere nobody documented"))

        if not CODE_FENCE.search(body):
            findings.append(Finding(
                "agent_carries_no_commands", "minor", "heuristic", declared,
                f"`{declared}` contains no fenced code block, so it likely carries no "
                "build or test command. `agents/README.md` requires commands verified "
                "on disk — a specialist without them sends every measurement to guess "
                "how the domain builds"))

    for present in sorted(p.name for p in agents.glob("*.md")):
        if present == "README.md" or present in routed:
            continue
        if _is_kit_agent(present, agents):
            continue
        findings.append(Finding(
            "agent_unrouted", "minor", "deterministic", present,
            f"`{present}` exists and no domain in the routing table names it. It will "
            "never be reached by `route_domain.py`; either a domain should name it or "
            "it is a leftover from a topology that changed"))

    return Section("agents", measured=True, findings=findings, facts={
        "domains": len(table),
        "domains_covered": len(table) - sum(
            1 for f in findings if f.severity == "blocker"),
        "specialists_on_disk": len([p for p in agents.glob("*.md")
                                    if p.name != "README.md"]),
        "agents_dir": str(agents),
    })


def _is_kit_agent(filename: str, agents: Path) -> bool:
    """Is this one of the fourteen the kit ships, rather than a domain specialist?

    Read from `agents/README.md`'s own table instead of a hardcoded roster, so the
    roster and the reader cannot drift. When the README is absent the answer is
    False — treating an unknown file as a kit agent would silence `agent_unrouted`
    for exactly the files it exists to surface.
    """
    readme = _read(agents / "README.md")
    if KIT_AGENT_MARKER not in readme:
        return False
    stem = filename[:-3] if filename.endswith(".md") else filename
    return bool(re.search(rf"`{re.escape(stem)}`", readme))


# --------------------------------------------------------------------------- skills


def diagnose_skills(project: Path) -> Section:
    """The project's OWN skills — structure only, and only the ones it wrote.

    Kit skills are excluded by construction: they are versioned with the kit and a
    finding against one is a defect in the kit, not in this project. What the
    consumer wrote is what nothing else looks at.
    """
    eco = eco_dir(project)
    skills_root = eco / "skills"
    if not skills_root.is_dir():
        return Section(
            "skills", measured=False,
            unmeasured_because=(
                f"no skills directory at {skills_root} — the kit does not appear to "
                "be installed here, so there is nothing to diagnose and nothing to "
                "report as clean"))

    kit_names = _kit_skill_names(project)
    if kit_names is None:
        return Section(
            "skills", measured=False,
            unmeasured_because=(
                f"neither `{eco}/.kit-manifest.txt` nor `{eco}/skills/map.md` is "
                "readable, so a skill the kit shipped cannot be told apart from one "
                "this project wrote. Every finding below would have been against a "
                "kit skill — a defect in the kit, reported against the wrong project. "
                "Re-run the installer to regenerate the manifest"))

    declared_aux = _declared_auxiliary(eco)
    findings: list[Finding] = []
    own: list[str] = []
    generated = 0

    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name in kit_names or name.startswith("_"):
            continue
        own.append(name)

        front = _frontmatter(_read(skill_md))
        if front is None:
            findings.append(Finding(
                "skill_frontmatter_broken", "blocker", "deterministic", name,
                f"`skills/{name}/SKILL.md` has no parseable frontmatter block. Claude "
                "Code will not surface the skill at all — it is installed and unreachable"))
            continue
        for required in ("name", "description"):
            if not front.get(required):
                findings.append(Finding(
                    "skill_missing_field", "major", "deterministic", name,
                    f"`skills/{name}/SKILL.md` frontmatter has no `{required}`. "
                    "Without a description nothing can decide when to reach for it"))

        #: A skill nobody invokes has no operating procedure to write. `/review`
        #: generates one knowledge skill per reviewer per plan, each carrying
        #: `user-invocable: false` and saying in its own body "not invoked
        #: directly" — five of them in one measured consumer. Demanding an SOP
        #: from those is demanding a procedure for an act nobody performs.
        operable = front.get("user-invocable", "true").lower() != "false"
        if not operable:
            generated += 1

        if operable and not (skill_md.parent / "SOP.md").is_file():
            findings.append(Finding(
                "skill_without_sop", "major", "deterministic", name,
                f"`skills/{name}` has no SOP.md. `SKILL.md` is the contract the agent "
                "executes; the SOP is what a person needs to operate it and act on "
                "what comes back. Every kit skill carries both"))

        if operable and name not in declared_aux and not _names_a_cycle(_read(skill_md)):
            findings.append(Finding(
                "skill_undeclared_auxiliary", "minor", "deterministic", name,
                f"`{name}` is a phase of no cycle and is not listed in "
                "`rules/auxiliary-skills.txt`, so `check_xrefs.py` warns about it on "
                "every run. That file exists precisely so a project can declare its "
                "own skills without editing the validator's body"))

    return Section("skills", measured=True, findings=findings, facts={
        "own_skills": len(own),
        "own_generated": generated,
        "own_skill_names": own,
        "kit_skills": len(kit_names),
        "declared_auxiliary": sorted(declared_aux),
    })


def _kit_skill_names(project: Path) -> set[str] | None:
    """Which skills came with the kit. None when that cannot be established.

    `.kit-manifest.txt` is the authoritative answer and says so in its own header:
    *"One path per line, relative to .claude/. Anything not here is the project's."*
    It is written by the installer on every install, which is exactly the event that
    decides the question.

    `skills/map.md` is the fallback for a standalone kit checkout, which has a map
    and no manifest.

    RETURNING None IS THE THIRD OUTCOME, and it is why this is not a bool. With
    neither file, kit skills and project skills are indistinguishable — and the first
    version of this function returned an empty set there, "over-reporting rather than
    under-reporting". Measured against a real consumer install with no map: 51 major
    findings, every one of them against a kit skill, none actionable. Over-reporting
    is not the safe direction; it is the same substitution as under-reporting, made
    against a different column.
    """
    eco = eco_dir(project)
    manifest = _read(eco / ".kit-manifest.txt")
    if manifest:
        names = {Path(line.strip()).name for line in manifest.splitlines()
                 if line.strip().startswith("skills/") and not line.lstrip().startswith("#")}
        if names:
            return names

    mapped = _map_rows(_read(eco / "skills" / "map.md"))
    return mapped or None


def _map_rows(content: str) -> set[str]:
    """Skill names in the first cell of every table row — `check_skill_map.py`'s rule."""
    found: set[str] = set()
    for line in content.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        first = line.strip().strip("|").split("|")[0]
        for match in re.finditer(r"[`/]([a-z][a-z0-9-]{2,})[`\s]|\[`?/?([a-z][a-z0-9-]{2,})", first):
            found.add(match.group(1) or match.group(2))
    return found


def _declared_auxiliary(eco: Path) -> set[str]:
    """Skills the project declares as belonging to no cycle."""
    content = _read(eco / "rules" / "auxiliary-skills.txt")
    return {line.strip() for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith("#")}


def _names_a_cycle(content: str) -> bool:
    """Does this skill claim a place in a cycle? `check_xrefs.py`'s second test."""
    return bool(re.search(r"^##\s+Cycle contract\b", content, re.MULTILINE))


def _frontmatter(content: str) -> dict[str, str] | None:
    """The `key: value` pairs of a leading `---` block, or None when there is none.

    Deliberately not a YAML parse: this runs in consumer installs where PyYAML may
    not be present, and the question asked here is whether the fields exist, not
    whether a nested structure is well formed.
    """
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    fields: dict[str, str] = {}
    for line in content[3:end].splitlines():
        if line[:1].isspace() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("'\"")
    return fields


# --------------------------------------------------------------------------- panel


def diagnose_panel(project: Path,
                   runner: Callable[..., Any] | None = None) -> Section:
    """Can a review panel be formed here at all? Delegated, never re-decided.

    `check_panel_capability.py` owns this question and states why it must be asked
    at intake: every item measured, planned, and then stopped at a panel that was
    never formable — item by item, for a cause knowable before the first one was
    selected.

    ITS FOUR VALUES STAY FOUR. That gate collapsed `VIOLATED` and `UNREACHABLE` into
    one value until 2026-09-08, and the conflation had a measured cost: a PATH with
    no `codex` reported VIOLATED, which would have failed CI for a repository with
    nothing wrong with it. So a declaration that can form no panel anywhere is a
    blocker on the project, and a reviewer missing on THIS machine is a major on
    this machine — different findings, for different readers, with different fixes.
    """
    if runner is None:
        try:
            # Optional sibling: absent in a skills-only install,
            # which is what the ImportError below handles.
            from check_panel_capability import (  # type: ignore[import-not-found]
                check_panel_capability,
            )
            runner = check_panel_capability
        except ImportError:
            return Section(
                "panel", measured=False,
                unmeasured_because=(
                    "`mechanisms/gates/check_panel_capability.py` is not reachable "
                    "from here. That gate owns the question; answering it with a "
                    "second implementation is how two gates come to disagree"))

    eco = eco_dir(project)
    panel_path = eco / "rules" / "review-panel.txt"

    #: ABSENT AND INVALID TAKE OPPOSITE ACTIONS, so they are not one finding.
    #: `check_panel_capability` correctly reports both as VIOLATED — from its seat
    #: the fact is the same, a project that cannot form a panel. But the person
    #: reading THIS is deciding what to do next, and the two next steps do not
    #: overlap: a missing file is an install that predates the declaration and is
    #: closed by copying the kit's template; a present one that forms no panel is a
    #: roster somebody has to edit. Measured across three real consumer installs:
    #: all three had no file at all, and a report saying "edit your roster" would
    #: have sent three people to open a file that was not there.
    if not panel_path.is_file():
        return Section("panel", measured=True, facts={"capability": "absent"}, findings=[
            Finding("panel_not_declared", "blocker", "deterministic", str(panel_path),
                    "no panel declaration in this project, so DISCOVER and PLAN cannot "
                    "be gated and every item reaching either phase returns as an "
                    "`access` impediment. This is what an install predating the "
                    "declaration looks like — copy `rules/review-panel.txt` from the "
                    "kit and edit the seats, rather than authoring a roster from scratch")])

    try:
        result = runner(panel_path, project=project)
    except Exception as exc:  # noqa: BLE001 — a gate that raised measured nothing
        # Deliberately broad. This calls into another module, and the ONLY outcome
        # that must never happen is an unexpected exception becoming a clean panel.
        # Narrowing this to the exceptions known today means tomorrow's raises past
        # it, and the caller reads a section nothing looked at as a section that
        # passed. The failure is reported as unmeasured, never swallowed.
        return Section("panel", measured=False,
                       unmeasured_because=f"the panel gate raised {type(exc).__name__}: {exc}")

    value = getattr(result, "value", str(result))

    if value == "unchecked":
        return Section("panel", measured=False, unmeasured_because=(
            f"`{panel_path}` exists and did not parse, so no seat was tested. A gate "
            "that looks, sees nothing and approves produces confidence where there "
            "was no verification"))

    findings: list[Finding] = []
    if value == "violated":
        findings.append(Finding(
            "panel_not_formable", "blocker", "deterministic", "rules/review-panel.txt",
            "the declaration cannot form a panel for every gated phase — a phase "
            "without three seats, or three seats from one family. DISCOVER and PLAN "
            "are gated on a 2-of-3 majority, so every item reaching either phase "
            "returns as an `access` impediment. This fails on every machine, CI included"))
    elif value == "unreachable":
        findings.append(Finding(
            "panel_reviewer_unreachable", "major", "deterministic", "rules/review-panel.txt",
            "the declaration is valid and a declared reviewer cannot be reached HERE — "
            "no such agent in this project, or no such binary on PATH. This is an "
            "impediment on this machine, NOT a defect in the declaration. Run "
            "`check_panel_capability.py` for which seat"))

    return Section("panel", measured=True, findings=findings,
                   facts={"capability": value, "panel_declaration": str(panel_path)})


# --------------------------------------------------------------------------- verdict


def verdict_of(sections: list[Section]) -> str:
    """Derived from the findings, never asserted — the discipline every scorer follows."""
    severities = {f.severity for s in sections if s.measured for f in s.findings}
    if "blocker" in severities:
        return "INVALID"
    if "major" in severities:
        return "NEEDS_REVISION"
    if "minor" in severities:
        return "SHIPPABLE_WITH_CAVEATS"
    return "SHIPPABLE"


EXIT = {"SHIPPABLE": 0, "SHIPPABLE_WITH_CAVEATS": 0, "NEEDS_REVISION": 3, "INVALID": 1}


def diagnose(project: Path) -> dict[str, Any]:
    sections = [diagnose_agents(project), diagnose_skills(project), diagnose_panel(project)]
    unmeasured = [s.name for s in sections if not s.measured]
    verdict = verdict_of(sections)
    return {
        "project": str(project),
        "verdict": verdict,
        #: Present and true whenever any section could not be measured. The verdict
        #: covers ONLY the sections that ran, and a reader must never take a clean
        #: token as a statement about a section nothing looked at.
        "partial": bool(unmeasured),
        "unmeasured_sections": unmeasured,
        "sections": [
            {**{k: v for k, v in asdict(s).items() if k != "findings"},
             "findings": [asdict(f) for f in sorted(
                 s.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.code, f.subject))]}
            for s in sections
        ],
    }


def render(report: dict[str, Any]) -> str:
    out: list[str] = [f"SQUAD FIT — {report['project']}", ""]
    for section in report["sections"]:
        if not section["measured"]:
            out.append(f"  {section['name']:<10} NOT MEASURED")
            out.append(f"             {section['unmeasured_because']}")
            out.append("")
            continue
        counts: dict[str, int] = {}
        for finding in section["findings"]:
            counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
        summary = ", ".join(f"{n} {sev}" for sev, n in sorted(
            counts.items(), key=lambda kv: SEVERITY_ORDER[kv[0]])) or "clean"
        out.append(f"  {section['name']:<10} {summary}")
        for finding in section["findings"]:
            mark = "?" if finding["kind"] == "heuristic" else "!"
            out.append(f"    {mark} [{finding['severity']}] {finding['code']} — {finding['subject']}")
            out.append(f"        {finding['detail']}")
        out.append("")

    out.append(f"  verdict: {report['verdict']}")
    if report["partial"]:
        out.append(f"  PARTIAL — nothing was measured for: {', '.join(report['unmeasured_sections'])}.")
        out.append("  The verdict above covers only the sections that ran.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", nargs="?", default=".",
                        help="the project the squad will run in (default: cwd)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    report = diagnose(Path(args.project).resolve())
    print(json.dumps(report, indent=2) if args.json else render(report))

    #: An unmeasured section outranks a clean verdict. Exiting 0 because the sections
    #: that ran were clean would report "the squad fits here" about an install where
    #: nothing looked at routing — the exact substitution this kit forbids.
    if report["partial"] and EXIT[report["verdict"]] == 0:
        return 2
    return EXIT[report["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())

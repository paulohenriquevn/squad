#!/usr/bin/env python3
"""Cross-reference validator for the planning ecosystem.

Supports dual-mode layouts:
  - Standalone — running from inside the ecosystem repo itself (the directory
    contains skills/ + rules/ + hooks/ directly, no .claude/ wrapper).
  - User config — installed as <home>/.claude/.
  - Plugin install — installed as <root>/.claude/plugins/cycle/.

Validates that:
  1. Each cycle-*.md references SKILL.md files that exist
  2. Each SKILL.md "Cycle contract" section points to a cycle-*.md that exists
  3. Each cycle rule's Cross-references section lists files that exist
  4. No orphan skills (skills not in any cycle, except documented auxiliary)
  5. No orphan cycle phases (cycle rule mentions a skill that doesn't exist)
  6. Each cycle rule template-cited script exists at the cited path
  7. SKILL.md bodies and Python scripts do not reference rules/*.md|*.txt that do not exist
     (catches fabricated rule references — the gap that hid code-quality-golden-rule
     before this check existed). The match pattern is `[.claude/]rules/<name>.(md|txt)`.

Usage:
    python3 scripts/check_xrefs.py                  # standalone
    python3 .claude/scripts/check_xrefs.py          # plugin install
    python3 scripts/check_xrefs.py --strict         # exit 1 on warnings too

Exit codes:
  0 — All cross-references valid
  1 — At least one broken reference (or warning in --strict)
  2 — Error (ecosystem directory not found, etc.)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Ensure scripts/ is on sys.path for shared module imports
sys.path.insert(0, str(Path(__file__).resolve().parent))


# Skills documented as "auxiliary" (not bound to any cycle)
# - ast-grep: structural search utility
# - slide-deck, marp-slide, excalidraw: presentation skills, project-agnostic
# - honesty-gate: honesty gate consumed transversally (README/CHANGELOG edits, release decisions)
# - roadmap-init: single-shot bootstrap at project inception; intentionally isolated
#   (its ARTIFACTS — ROADMAP.md + records/references/ — are consumed by cycle-roadmap
#   and cycle-discover; the SKILL itself is never invoked mid-cycle)
# - roadmap-feature: sister of roadmap-init for adding one milestone to an existing roadmap
#   (same isolation contract; opposite pre-condition — refuses if ROADMAP.md is missing)
# - quality-init: one-shot rigorous initializer (same isolation contract as roadmap-init);
#   walks a target codebase and emits calibrated quality-gate hooks. Leaves no state behind,
#   is invoked BEFORE a coding session, and is intentionally absent from every cycle-*.md.
# - skill-creator: standalone skill-authoring tool (the official Anthropic skill-creator);
#   invoked on demand to create/improve any skill at skills/{purpose}/. Deliberately decoupled
#   from every cycle (replaced the retired skill-writer/validator/register discover tail).
AUXILIARY_SKILLS = {"ast-grep", "slide-deck", "marp-slide", "excalidraw", "honesty-gate", "backlog-init", "backlog-review", "session-goal", "commands-help", "quality-init", "skill-creator", "frontend-design", "cap-theorem-specialist", "backpressure-specialist", "resilience-specialist", "arch-check", "sop-author", "sop-run", "sop-review"}


def _declared_auxiliary_skills(ecosystem_dir: Path) -> set[str]:
    """Skills the PROJECT declares as auxiliary, in `rules/auxiliary-skills.txt`.

    `AUXILIARY_SKILLS` above is the kit's list. A consumer with domain skills of
    its own had exactly one way out: editing this constant — and an edit inside
    the validator's body is what the kit's next sync overwrites. One adopter did
    exactly that, and the edit survived only because someone compared file by file
    before copying.

    Measured on `speculative` (2026-08-20): 9 own skills, 18 WARN — 100% of the
    checker's warnings — and since `install.sh` invokes it with `--strict`, the
    whole installation was reported as a failure because of the consumer's own
    design.

    Format: one name per line; `#` comments. A name that does not exist on disk
    is ignored silently on purpose: the list is a declaration of intent, not an
    inventory, and a skill removed from the project must not break the validator.
    """
    rule = ecosystem_dir / "rules" / "auxiliary-skills.txt"
    if not rule.is_file():
        return set()
    declared: set[str] = set()
    for raw_line in rule.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            declared.add(line)
    return declared


def _kit_owned_skills(ecosystem_dir: Path) -> set[str] | None:
    """Skills the install manifest says the KIT brought, or None in the kit's own repo.

    `.kit-manifest.txt` states the rule in its own header: *anything not here is the
    project's*. Reading it turns the project/kit distinction from a list somebody has
    to maintain into a fact the installer already wrote.

    This closes the hole that `rules/auxiliary-skills.txt` left half-open. That file
    is the right idea — a consumer declaring which of its skills are auxiliary — but
    it SHIPS EMPTY, so every consumer starts with every one of its own skills flagged.
    Measured on 2026-08-31 across two live installs: `theo` had the file, empty, and
    13 WARN; `theokit` had 102 skills of which 66 are its own, no file at all, and
    119 WARN — every single warning the checker produced. `install.sh` runs this with
    `--strict`, so both installations reported failure over the consumers' own design,
    and a validation that always fails is one nobody reads.

    Returning None where the manifest is absent is deliberate: in the kit's own
    repository there is no consumer, every skill IS the kit's, and the existing
    checks must keep applying in full.
    """
    manifest = ecosystem_dir / ".kit-manifest.txt"
    if not manifest.is_file():
        return None
    owned: set[str] = set()
    for raw_line in manifest.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line.startswith("skills/"):
            owned.add(line[len("skills/"):].split("/", 1)[0])
    return owned or None



def _is_auto_generated(skill: str) -> bool:
    """Skills the cycles THEMSELVES write, not phases anyone maintains.

    `/review` emits `review-{slug}-{dimension}-knowledge` and discover emits
    `*-sepa-knowledge`: these are run artifacts. Demanding a cycle contract or a
    reference in some cycle-*.md asks the output to behave like an input.

    It lives here rather than inline in a check because the first version exempted
    only `no_orphan_skills` and left `skill_has_cycle_contract` still charging — a half
    exemption that traded 26 WARN for 3 and looked like a fix. One definition, two
    consumers: that is what stops the next half from escaping.
    """
    return skill.endswith("-knowledge") and (skill.startswith("review-") or "-sepa-" in skill)


# Patterns to detect file references in markdown
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BACKTICK_PATH_RE = re.compile(r"`(\.?[a-zA-Z0-9_./\-]+\.(?:md|py|sh|json|txt|yml|yaml))`")
# `[a-z]+(?:-[a-z]+)*` and not `[a-z]+`: three of the kit's twelve cycle rules
# are multi-hyphen (cycle-code-quality, cycle-idea-to-release, cycle-judge-codex), and a
# group without the hyphen truncated them to cycle-code / cycle-auto /
# cycle-judge — names that do not exist. The validator then reported a present
# file as missing.
# `(?<![a-z0-9-])`, or the name of any skill ending in `-lifecycle-engineer`
# contains a cycle reference. Measured on 2026-08-31: a consumer's
# `middleware-lifecycle-engineer` was reported as referencing `cycle-engineer.md`,
# a rule nobody wrote — a hard FAIL, on a skill that names no cycle at all. The
# fallback below makes it reachable: with no `## Cycle contract` section the
# whole SKILL.md is scanned, and the file always contains its own name.
CYCLE_REF_RE = re.compile(r"`?(?<![a-z0-9-])cycle-([a-z]+(?:-[a-z]+)*)`?")
# Backticked spans — where a citation of a cycle is a reference, not prose.
BACKTICK_SPAN_RE = re.compile(r"`([^`\n]+)`")
# Kept in sync with detect_domains.UNREVIEWED_MARKER — duplicating the string is
# acceptable here: importing cross-slice would couple the validator to a skill.
UNREVIEWED_MARKER = "<!-- TO BE FILLED IN: only a human knows this -->"
# `cycle-<name>` inside a code span, with the .md suffix optional.
#
# The trailing lookahead excludes a NON-.md extension. `records/cycle-events.jsonl` is
# a data file whose name happens to start with the prefix, and without this it was
# reported as a reference to a cycle rule nobody wrote. `.md` stays allowed because
# `cycle-plan.md` IS a reference to the rule.
#
# Narrow on purpose: the previous time this pattern was widened — accepting `/` so
# paths would match — it made `records/maintenance-runs/` parse as a skill. A
# lookahead that only refuses a foreign extension cannot reach anything else.
CYCLE_NAME_RE = re.compile(
    r"\bcycle-([a-z][a-z0-9]*(?:-[a-z0-9]+)*)"
    r"(?![a-z0-9-])"          # the name ends here — without this the group
                              # backtracks to `cycle-event` so the next lookahead
                              # passes, and `cycle-events.jsonl` matches anyway
    r"(?!\.(?!md\b)[a-z0-9]+)"  # ...and is not the stem of a non-.md filename
)
SKILL_REF_RE = re.compile(r"`?(?:\.claude/)?skills/([a-z0-9\-]+)/SKILL\.md`?")
# Detect rules references in SKILL bodies and Python scripts.
# Examples matched:
#   `rules/code-quality-golden-rule.md`
#   `.claude/rules/code-quality-thresholds.txt`
#   "rules/discover-web-allowlist.txt"
# Examples NOT matched (intentionally):
#   records/rules/...  (different directory tree)
#   project-rules/...         (different prefix)
RULES_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_/-])(?:\.claude/)?rules/([A-Za-z0-9._-]+\.(?:md|txt))"
)


from ecosystem_utils import find_ecosystem_dir as _find_ecosystem_dir_impl  # noqa: E402


def _find_ecosystem_dir(start: Path) -> Path | None:
    """Locate the ecosystem directory (delegates to shared module)."""
    return _find_ecosystem_dir_impl(start, require=False)


def _list_existing_skills(ecosystem_dir: Path) -> set[str]:
    skills_dir = ecosystem_dir / "skills"
    if not skills_dir.exists():
        return set()
    return {
        d.name
        for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    }


def _list_cycle_rules(ecosystem_dir: Path) -> dict[str, Path]:
    rules_dir = ecosystem_dir / "rules"
    if not rules_dir.exists():
        return {}
    # `cycle-rule-schema.md` is meta-documentation about cycle rules, not a cycle itself.
    return {
        p.stem: p
        for p in rules_dir.glob("cycle-*.md")
        if p.stem != "cycle-rule-schema"
    }


def _extract_referenced_paths(content: str, base: Path) -> set[Path]:
    """Extract paths referenced in markdown (backtick + markdown link)."""
    paths: set[str] = set()

    for match in LINK_RE.finditer(content):
        url = match.group(2).strip()
        if url.startswith(("http://", "https://", "#")):
            continue
        paths.add(url)

    for match in BACKTICK_PATH_RE.finditer(content):
        paths.add(match.group(1))

    resolved: set[Path] = set()
    for p in paths:
        candidate = (base / p).resolve() if not Path(p).is_absolute() else Path(p)
        resolved.add(candidate)
    return resolved


def _extract_cycle_phases(cycle_rule_content: str,
                          skills_root: Path | None = None) -> set[str]:
    """Extract skill names mentioned in a cycle rule's `phases:` frontmatter list AND in the chain section."""
    skills: set[str] = set()

    # Frontmatter phases: section
    fm_match = re.match(r"^---\n(.*?)\n---", cycle_rule_content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        phases_match = re.search(r"^phases:\s*\n((?:\s+-\s+[a-z0-9\-]+(?:\s+\([^)]+\))?\s*\n)*)", fm, re.MULTILINE)
        if phases_match:
            for line in phases_match.group(1).splitlines():
                m = re.match(r"\s+-\s+([a-z0-9\-]+)", line)
                if m:
                    skills.add(m.group(1))

    # Chain section: looks for `/skill-name` patterns
    chain_match = re.search(r"## Chain.*?\n```(.*?)```", cycle_rule_content, re.DOTALL)
    if chain_match:
        chain = chain_match.group(1)
        # Match /skill-name in the chain. A kebab-case name is a skill by shape.
        # A SINGLE word is a skill when `skills/<name>/` exists — asked of the
        # filesystem rather than matched against a literal list.
        #
        # The list was `to-plan|implement|review|release|trajectory-review|
        # acceptance`, so a new single-word skill stayed invisible to the orphan
        # check until somebody remembered to edit this regex, and the symptom was
        # a WARN claiming a skill is unreferenced while the cycle rule names it.
        # Same shape as the preservation rules and the layout-blind paths this
        # kit spent the week fixing: implemented for the cases its author listed.
        #
        # Asking the filesystem cannot go stale, and cannot admit a word that is
        # not a skill — `/usr/bin/x` in a chain block stays a path.
        root = skills_root if skills_root is not None else (
            Path(__file__).resolve().parent.parent / "skills")
        # The terminator stays `[\s{]` and never `/`: widening it to accept a
        # slash made `records/maintenance-runs/` parse as a skill reference, and
        # the checker reported a missing skill for a directory path. A checker
        # that cries wolf in a consumer is one somebody disables.
        for m in re.finditer(r"(?<![a-z0-9/])/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)[\s{]", chain):
            name = m.group(1)
            if "-" in name or (root / name).is_dir():
                skills.add(name)

    return skills


def _extract_cycle_contract_ref(
    skill_md_content: str, skill_names: set[str] | None = None
) -> str | None:
    """Find `cycle-{name}` referenced in a SKILL.md's Cycle contract section.

    `skill_names` disambiguates a namespace collision: a SKILL directory may itself
    be named with the cycle- prefix (skills/session-goal/ is the one in this kit), and
    then every mention of that command in prose looks exactly like a reference to a
    cycle rule file that was never meant to exist. Names are written unbackticked
    throughout this docstring precisely because backticks are what the sibling
    `rules_reference_resolves` check reads as a real path. Left unhandled the collision
    produced a FAIL the moment any document listed the command — which is how a
    validator teaches people to ignore it.

    A `cycle-X` token where `X` names an existing skill is therefore read as the skill,
    never as a cycle rule. A skill that genuinely belongs to a cycle says so in a
    `## Cycle contract` section, which is matched first and is unambiguous.
    """
    contract_match = re.search(r"## Cycle contract.*?(?=^##\s+|\Z)", skill_md_content, re.MULTILINE | re.DOTALL)
    body = contract_match.group(0) if contract_match else skill_md_content
    for cycle_match in CYCLE_REF_RE.finditer(body):
        name = cycle_match.group(1)
        if skill_names and f"cycle-{name}" in skill_names:
            continue
        return name
    return None


def validate_xrefs(ecosystem_dir: Path, strict: bool = False) -> dict[str, Any]:
    # In standalone layout, the "project root" IS the ecosystem dir; in plugin
    # layout it is the parent. Use ecosystem_dir for path display so the report
    # is unambiguous regardless of layout.
    existing_skills = _list_existing_skills(ecosystem_dir)
    cycle_rules = _list_cycle_rules(ecosystem_dir)

    findings: list[dict[str, Any]] = []

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(ecosystem_dir))
        except ValueError:
            return str(p)

    # Check 1: each cycle rule references skills that exist
    cycle_to_skills: dict[str, set[str]] = {}
    for cycle_name, cycle_path in cycle_rules.items():
        content = cycle_path.read_text(encoding="utf-8-sig")
        skills_mentioned = _extract_cycle_phases(content)
        cycle_to_skills[cycle_name] = skills_mentioned

        for skill in skills_mentioned:
            if skill not in existing_skills:
                findings.append({
                    "severity": "WARN",
                    "check": "cycle_rule_references_existing_skill",
                    "cycle": cycle_name,
                    "missing_skill": skill,
                    "message": f"{_rel(cycle_path)} references skill `{skill}` which does not exist at skills/{skill}/",
                })

    # Check 2: each SKILL.md points to an existing cycle
    # The exemption applies to BOTH checks. `_is_auto_generated`'s docstring records
    # why: the first version exempted only `no_orphan_skills` and left this one
    # enforcing — half an exemption, which traded 26 WARN for 3 and looked like a fix.
    project_auxiliary = _declared_auxiliary_skills(ecosystem_dir)

    # A skill the install manifest does not claim is the project's, and the kit has no
    # standing to demand a cycle contract from it. Folded into the SAME variable both
    # checks already read, for the reason the comment above records: the last time an
    # exemption reached one check and not the other, it traded 26 WARN for 3 and looked
    # like a fix.
    kit_owned = _kit_owned_skills(ecosystem_dir)
    if kit_owned is not None:
        project_auxiliary = project_auxiliary | (existing_skills - kit_owned)

    skill_to_cycle: dict[str, str | None] = {}
    for skill in existing_skills:
        skill_md = ecosystem_dir / "skills" / skill / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8-sig")
        cycle_ref = _extract_cycle_contract_ref(content, existing_skills)
        skill_to_cycle[skill] = cycle_ref

        if (cycle_ref is None and skill not in AUXILIARY_SKILLS
                and skill not in project_auxiliary and not _is_auto_generated(skill)):
            findings.append({
                "severity": "WARN",
                "check": "skill_has_cycle_contract",
                "skill": skill,
                "message": f"skills/{skill}/SKILL.md has no `Cycle contract` section pointing to a cycle-*.md",
            })
        elif cycle_ref is not None:
            expected_cycle = f"cycle-{cycle_ref}"
            if expected_cycle not in cycle_rules:
                findings.append({
                    "severity": "FAIL",
                    "check": "skill_cycle_contract_resolves",
                    "skill": skill,
                    "cycle_referenced": expected_cycle,
                    "message": f"skills/{skill}/SKILL.md references cycle-{cycle_ref}.md but it does not exist",
                })

    # Check 3: cycle rule cross-references point to existing files
    for cycle_name, cycle_path in cycle_rules.items():
        content = cycle_path.read_text(encoding="utf-8-sig")
        # Cross-references section
        xref_match = re.search(r"## Cross-references.*?(?=^##\s+|\Z)", content, re.MULTILINE | re.DOTALL)
        if not xref_match:
            findings.append({
                "severity": "WARN",
                "check": "cycle_has_xref_section",
                "cycle": cycle_name,
                "message": f"{_rel(cycle_path)} has no `Cross-references` section",
            })
            continue

        xref_body = xref_match.group(0)
        # Extract referenced files — only validate REAL paths (with / or starting with .)
        # Bare filenames in prose (e.g., `testing.md`) are likely conceptual references, skip
        for match in BACKTICK_PATH_RE.finditer(xref_body):
            ref = match.group(1)
            # Skip references that are clearly placeholders or relative-to-skill paths
            if "{" in ref or ref.startswith("../"):
                continue
            # Skip bare filenames without path separators — these are nominal mentions in prose
            if "/" not in ref and not ref.startswith("."):
                continue
            # Try resolution against multiple search roots — accept both standalone
            # (skills/...) and plugin-style (.claude/skills/...) reference paths.
            candidates_to_try: list[Path] = []
            if Path(ref).is_absolute():
                candidates_to_try.append(Path(ref))
            else:
                # Strip a leading .claude/ if present (plugin-style citation)
                normalized = ref.removeprefix(".claude/")
                candidates_to_try.append(ecosystem_dir / normalized)
                # If path starts with a skill name (e.g., plan-confidence/templates/...), try skills/
                first_segment = normalized.split("/", 1)[0]
                if (ecosystem_dir / "skills" / first_segment).exists():
                    candidates_to_try.append(ecosystem_dir / "skills" / normalized)

            if not any(c.exists() for c in candidates_to_try):
                findings.append({
                    "severity": "WARN",
                    "check": "cycle_xref_file_exists",
                    "cycle": cycle_name,
                    "broken_ref": ref,
                    "message": f"{_rel(cycle_path)} references `{ref}` which does not exist",
                })

    # Check 7: rules referenced from SKILL.md bodies + scripts must exist on disk.
    rules_dir = ecosystem_dir / "rules"
    existing_rule_files: set[str] = {p.name for p in rules_dir.glob("*")} if rules_dir.exists() else set()

    def _scan_for_rule_refs(path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return
        for m in RULES_REF_RE.finditer(content):
            rule_name = m.group(1)
            if rule_name in existing_rule_files:
                continue
            findings.append({
                "severity": "FAIL",
                "check": "rules_reference_resolves",
                "source": _rel(path),
                "missing_rule": rule_name,
                "message": f"{_rel(path)} references `rules/{rule_name}` which does not exist",
            })

    for skill_md in (ecosystem_dir / "skills").rglob("SKILL.md"):
        if skill_md.is_file():
            _scan_for_rule_refs(skill_md)
    # Uma regra citando outra regra era o ponto cego: o scan cobria skills e
    # scripts and skipped all of `rules/`, which is where the normative anchors live.
    for rule_md in rules_dir.glob("*.md") if rules_dir.exists() else []:
        if rule_md.is_file():
            _scan_for_rule_refs(rule_md)
    for py in (ecosystem_dir / "skills").rglob("*.py"):
        if py.is_file() and "__pycache__" not in py.parts:
            _scan_for_rule_refs(py)
    for py in (ecosystem_dir / "scripts").rglob("*.py"):
        if py.is_file() and "__pycache__" not in py.parts:
            _scan_for_rule_refs(py)

    # Check 8: `cycle-<name>` cited in code/rules must resolve to a cycle rule
    # (`rules/cycle-<name>.md`) or to a skill (`skills/cycle-<name>/`).
    # Why: `rules/cycle-acceptance.md` and `rules/cycle-release.md` anchored the
    # single-flip invariant at "cycle-roadmap § Hard gates" AFTER cycle-roadmap had
    # become cycle-maintenance. No check saw it: Check 7 matches paths shaped like
    # rules/<file>.md, and a citation by name is not a path. Only backticked text
    # counts — loose prose ("a cycle-level decision") would produce noise while
    # naming nothing.
    # Existence on disk, not the cycle list: `cycle-rule-schema.md` is meta
    # documentation and stays OUT of `cycle_rules` on purpose — but citing it is
    # legitimate, the file is there.
    cycle_skill_names = {s for s in existing_skills if s.startswith("cycle-")}

    def _scan_for_cycle_refs(path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return
        for code_span in BACKTICK_SPAN_RE.findall(content):
            for name in CYCLE_NAME_RE.findall(code_span):
                cycle_id = f"cycle-{name}"
                if (rules_dir / f"{cycle_id}.md").exists() or cycle_id in cycle_skill_names:
                    continue
                findings.append({
                    "severity": "FAIL",
                    "check": "cycle_reference_resolves",
                    "source": _rel(path),
                    "broken_ref": cycle_id,
                    "message": f"{_rel(path)} references `{cycle_id}` — no rules/{cycle_id}.md "
                               f"and no skills/{cycle_id}/ exists",
                })

    for rule_md in rules_dir.glob("*.md") if rules_dir.exists() else []:
        if rule_md.is_file():
            _scan_for_cycle_refs(rule_md)
    for skill_md in (ecosystem_dir / "skills").rglob("SKILL.md"):
        if skill_md.is_file():
            _scan_for_cycle_refs(skill_md)

    # Check 9: a DERIVED specialist nobody reviewed.
    # `detect_domains.py` generates a skeleton so the route stops being BROKEN, with
    # the judgement sections (commands, real findings, false positives, invariants)
    # empty and marked. A silent skeleton is worse than a broken route: the broken
    # route warns, and this one looks like a finished specialist. WARN while the
    # marker exists — it disappears on its own when someone fills it in.
    agents_dir = ecosystem_dir / "agents"
    if agents_dir.is_dir():
        for agent_md in sorted(agents_dir.glob("*.md")):
            try:
                body = agent_md.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            if UNREVIEWED_MARKER not in body:
                continue
            pending = body.count(UNREVIEWED_MARKER)
            findings.append({
                "severity": "WARN",
                "check": "specialist_unreviewed",
                "agent": agent_md.stem,
                "message": f"agents/{agent_md.name} is a derived skeleton with {pending} "
                           "section(s) left to fill — the routing works, the judgement does not",
            })

    # Check 4: orphan skills (not in any cycle, not auxiliary)
    skills_in_cycles: set[str] = set()
    for skills_set in cycle_to_skills.values():
        skills_in_cycles.update(skills_set)

    # Skills AUTO-GENERATED by the cycles themselves are phases of no cycle: they are
    # ARTEFATOS de uma execucao. `/review` escreve `review-{slug}-{dimensao}-knowledge`
    # e o discover escreve `*-sepa-knowledge`. O patch_install ja as trata como tal
    # ("Auto-generated skills (SEPA-knowledge, review-*-knowledge) preserved"), mas
    # this validator reported them as orphans -- so every consumer that ran /review
    # passava a falhar --strict, e a falha aparecia longe da causa.
    # Medido em 2026-08-03: os tres consumidores monitorados falharam exatamente assim
    # after running review, with 26 WARN and no real defect.
    auto_generated = {s for s in existing_skills if _is_auto_generated(s)}
    orphan_skills = (existing_skills - skills_in_cycles - AUXILIARY_SKILLS
                     - project_auxiliary - auto_generated)
    for skill in sorted(orphan_skills):
        findings.append({
            "severity": "WARN",
            "check": "no_orphan_skills",
            "skill": skill,
            "message": f"Skill `{skill}` is not referenced by any cycle-*.md and is not in AUXILIARY_SKILLS",
        })

    # Aggregate
    severity_counts = defaultdict(int)
    for f in findings:
        severity_counts[f["severity"]] += 1

    overall = "PASS"
    if severity_counts.get("FAIL", 0) > 0 or severity_counts.get("WARN", 0) > 0 and strict:
        overall = "FAIL"

    return {
        "ecosystem_dir": str(ecosystem_dir),
        "skills_total": len(existing_skills),
        "skills_auxiliary": sorted(AUXILIARY_SKILLS & existing_skills),
        "skills_orphan": sorted(orphan_skills),
        "cycle_rules": sorted(cycle_rules.keys()),
        "skill_to_cycle": skill_to_cycle,
        "findings": findings,
        "severity_counts": dict(severity_counts),
        "overall": overall,
    }


def _render_summary(result: dict[str, Any]) -> str:
    lines = [
        "=== Cross-reference validator ===",
        f"Ecosystem dir: {result['ecosystem_dir']}",
        f"Skills total: {result['skills_total']}",
        f"Cycle rules: {result['cycle_rules']}",
        f"Skills auxiliary: {result['skills_auxiliary']}",
        f"Skills orphan: {result['skills_orphan']}",
        "",
        f"=== Findings ({len(result['findings'])}) ===",
    ]
    for f in result["findings"]:
        lines.append(f"  [{f['severity']}] {f['check']}: {f['message']}")
    lines.append("")
    lines.append(f"Severity counts: {result['severity_counts']}")
    lines.append(f"Overall: {result['overall']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cross-references in the planning ecosystem.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on WARN too (default: exit 1 only on FAIL)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable summary")
    parser.add_argument("--ecosystem-dir", type=Path, default=None, help="Override ecosystem directory detection")
    parser.add_argument("--claude-dir", type=Path, default=None, help="(deprecated alias for --ecosystem-dir)")
    args = parser.parse_args()

    override = args.ecosystem_dir or args.claude_dir
    if override:
        ecosystem_dir = override.resolve()
    else:
        # The root comes from WHERE THE SCRIPT LIVES, not from the cwd. The previous
        # version started at Path.cwd(), and the effect was a validator that lies:
        # running
        # `python3 <outro-projeto>/.claude/scripts/check_xrefs.py` de um cwd qualquer
        # auditava silenciosamente o ecossistema DO CWD e imprimia o veredito dele.
        # Medido em 2026-08-03: tres consumidores reportados PASS estavam, na verdade,
        # com 3, 0 e 11 findings -- o PASS era o repo do kit se auto-validando.
        # A validator that audits the wrong target is worse than none, because it
        # produces unfounded confidence. The script's own path is the only anchor
        # that does not
        # depende de quem chamou.
        ecosystem_dir = _find_ecosystem_dir(Path(__file__).resolve().parent)
        if ecosystem_dir is None:
            ecosystem_dir = _find_ecosystem_dir(Path.cwd())

    if ecosystem_dir is None or not ecosystem_dir.exists():
        print(json.dumps({
            "error": "ecosystem directory not found",
            "hint": "expected one of: <cwd>/{skills,rules,hooks}, <cwd>/.claude/{skills,rules,hooks}, or <cwd>/.claude/plugins/cycle/{skills,rules,hooks}",
        }), file=sys.stderr)
        return 2

    result = validate_xrefs(ecosystem_dir, strict=args.strict)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(_render_summary(result))

    return 0 if result["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

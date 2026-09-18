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
    python3 mechanisms/gates/check_xrefs.py                  # standalone
    python3 .claude/mechanisms/gates/check_xrefs.py          # plugin install
    python3 mechanisms/gates/check_xrefs.py --strict         # exit 1 on warnings too

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

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from pathlib import Path as _Path_bootstrap
from typing import Any

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break


# The family this file lives in, plus `lib/` — the import namespace stayed flat
# when `scripts/` became `mechanisms/<family>/`, so a sibling family is reached
# by path rather than by package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "conventions"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from ecosystem_utils import find_ecosystem_dir as _find_ecosystem_dir_impl  # noqa: E402

from squad.paths import (  # noqa: E402 — post-bootstrap import
    DATA_DIRNAME,
    wiki_dir,
)
from squad.paths import WIKI as WIKI_FALLBACK  # noqa: E402 — post-bootstrap import

# Skills documented as "auxiliary" (not bound to any cycle)
# - ast-grep: structural search utility
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
# - as-is-to-be: read-only projection of the registry into current state vs future state,
#   invoked on demand by whoever has to explain what a quarter buys. Same shape as
#   backlog-review: it reads the registry a cycle owns and is a phase of none.
AUXILIARY_SKILLS = {"ast-grep", "honesty-gate", "backlog-init", "backlog-review", "quality-init", "skill-creator", "arch-check", "squad-fit", "sign", "panel", "issue-confidence", "critic", "as-is-to-be"}


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


def _kit_manifest_paths(ecosystem_dir: Path) -> set[str] | None:
    """Every path the manifest lists, verbatim. None when there is no manifest.

    `_kit_owned_skills` answers for skills, where the manifest lists one entry per
    SKILL. `rules/`, `hooks/`, `commands/` and `scripts/` are listed per FILE, and
    answering those needs the raw paths — without them a consumer's own
    `rules/*.md` reads as the kit's and its broken references fail the kit's install.
    """
    manifest = ecosystem_dir / ".kit-manifest.txt"
    if not manifest.is_file():
        return None
    paths = {
        line.split("#", 1)[0].strip()
        for line in manifest.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        if line.split("#", 1)[0].strip()
    }
    return paths or None


def _kit_owned_skills(ecosystem_dir: Path) -> set[str] | None:
    """Skills the install manifest says the KIT brought, or None in the kit's own repo.

    `.kit-manifest.txt` states the rule in its own header: *anything not here is the
    project's*. Reading it turns the project/kit distinction from a list somebody has
    to maintain into a fact the installer already wrote.

    This closes the hole that `rules/auxiliary-skills.txt` left half-open. That file
    is the right idea — a consumer declaring which of its skills are auxiliary — but
    it SHIPS EMPTY, so every consumer starts with every one of its own skills flagged.
    Measured on 2026-08-31 across two live installs: `theo` had the file, empty, and
    13 WARN; an adopter had 102 skills of which 66 are its own, no file at all, and
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



def _kit_shipped_paths(ecosystem_dir: Path) -> set[str] | None:
    """Every path the install manifest says the KIT brought, or None in the kit's repo.

    Sibling of `_kit_owned_skills`, reading the same file for a wider question: not
    "which skills are ours" but "did we ship this exact path". The manifest states the
    rule in its own header — *anything not here is the project's* — and the installer
    writes it on every install, which is the event that decides the answer.

    None in the kit's own checkout, where there is no manifest and the whole tree is the
    kit's. A caller must read None as "cannot tell" rather than as "nothing is ours":
    the second would make every collision look like a consumer's and silence the check.
    """
    manifest = ecosystem_dir / ".kit-manifest.txt"
    if not manifest.is_file():
        return None
    shipped = {line.split("#", 1)[0].strip()
               for line in manifest.read_text(encoding="utf-8-sig").splitlines()}
    shipped.discard("")
    return shipped or None


def _is_auto_generated(skill: str) -> bool:
    """Skills the cycles THEMSELVES write, not phases anyone maintains.

    `/review` emits `review-{slug}-{dimension}-knowledge`: these are run artifacts.
    Demanding a cycle contract or a reference in some cycle-*.md asks the output to
    behave like an input.

    `*-sepa-knowledge` is kept as BACKWARD COMPATIBILITY and has no producer any more.
    `/implement` used to generate one per plan; on 2026-09-01 it stopped generating
    agents and skills entirely and now routes to the project's own domain specialist.
    The pattern stays because consumers still hold what was already written to their
    disk, and dropping it would turn those files into orphans and fail the check in
    repositories that did nothing wrong. Remove it once no consumer carries one.

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
#: How a DERIVED specialist declares the sections a person still owes.
#:
#: This was `<!-- TO BE FILLED IN: only a human knows this -->`, kept "in sync with
#: detect_domains.UNREVIEWED_MARKER" — and `detect_domains.render_specialist`, the only
#: producer of that marker, was a second template reachable from nothing but its own
#: tests. The LIVE renderer is `scaffold_specialists.render`, which marks the same three
#: sections with a trailing `— OPEN` heading. So this gate keyed on a string no shipped
#: writer emitted, and every derived specialist passed it by not being detectable.
UNREVIEWED_SECTION = "— OPEN"
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

#: A path under `skills/` cited in prose or code. The extension anchors the end so
#: a sentence following the reference is not swallowed into the path.
SKILLS_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_/-])(?:\.claude/)?skills/([A-Za-z0-9_][A-Za-z0-9._/-]*\.(?:md|txt|py|sh|json))"
)




#: A path under `skills/` cited in prose or code. The extension anchors the end so
#: a sentence following the reference is not swallowed into the path.
SKILLS_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_/-])(?:\.claude/)?skills/([A-Za-z0-9_][A-Za-z0-9._/-]*\.(?:md|txt|py|sh|json))"
)




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


#: Link targets that are not paths into this repository.
_NOT_A_REPO_PATH = ("http://", "https://", "#", "mailto:", "file://", "~")

#: Documents that live in the KIT's repository and are deliberately not installed
#: into a consumer — `install.sh` copies skills, rules, hooks, commands,
#: mechanisms and squad, and none of these. A link to one is correct where it is
#: written and unresolvable where the kit is installed, so reporting it would put
#: nine identical WARNs in front of every consumer, forever, for something no
#: consumer can fix. Measured on a fresh install on 2026-09-02, which is how this
#: distinction was found: the gate's first run against one produced exactly that.
_NOT_INSTALLED_INTO_CONSUMERS = (
    "README.md", "CONTRIBUTING.md", "SECURITY.md", "LICENSE", "CHANGELOG.md",
    "HOW-TO-USE.md", f"{DATA_DIRNAME}/", f"{WIKI_FALLBACK}/",
    "study-material/", "images/", "tests/",
)


def _is_kit_repo_only(target: str) -> bool:
    """Is this link's target a document the kit keeps and does not ship?"""
    # NOT `lstrip("./")`: that strips CHARACTERS, so `.squad/wiki/x.md` came back as
    # `squad/wiki/x.md` and matched neither the write root nor the package. The same
    # trap turned `.claude-plugin/plugin.json` into `claude-plugin/plugin.json`
    # elsewhere in this kit.
    bare = target.replace("../", "")
    while bare.startswith("./"):
        bare = bare[2:]
    return bare.startswith(_NOT_INSTALLED_INTO_CONSUMERS) or bare in _NOT_INSTALLED_INTO_CONSUMERS


def broken_markdown_links(ecosystem_dir: Path) -> list[tuple[str, str]]:
    """`(file, target)` for every `[text](path)` pointing at nothing.

    ONLY markdown links. This function replaces one that also resolved every
    backtick-quoted token that looked like a path, and that function was never
    called by anything — a checker that existed and did not run, which is the
    defect this kit keeps finding. Measured before deleting it: run as written it
    reported **1451** broken references, nearly all of them a bare filename in
    backticks (`alignment_judge.py`) resolved against whichever directory happened
    to be citing it. A gate with that signal-to-noise gets switched off, and the
    silence that follows is indistinguishable from a clean repository.

    A markdown link is unambiguous about its target, so it is checkable. Measured
    on the same tree: 234 relative links, 21 broken, every one of them real.

    `wiki/` is resolved from its own root: its links are written `/sops/index.md`
    because the wiki is served from that directory, and reading them as filesystem
    paths reports ten false positives at once.
    """
    broken: list[tuple[str, str]] = []
    wiki_root = wiki_dir(ecosystem_dir) or (ecosystem_dir / WIKI_FALLBACK)
    for md in sorted(ecosystem_dir.rglob("*.md")):
        rel = str(md.relative_to(ecosystem_dir))
        # `.install-backups/` holds the PREVIOUS install, snapshotted by `install.sh
        # --force` before it replaced anything. Its links point at a tree that has since
        # moved, so walking it reports broken cross-references in files nothing reads and
        # nobody can fix — and under `--strict` that failed the post-install validation of
        # a perfectly good install. A backup of an old ecosystem is not this ecosystem.
        if any(part in rel for part in (".git/", "study-material/", "__pycache__/",
                                        ".install-backups/", ".patch-backups/")):
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in LINK_RE.finditer(text):
            url = match.group(2).strip()
            if url.startswith(_NOT_A_REPO_PATH) or not url:
                continue
            target = url.split("#")[0]
            if not target:
                continue
            if target.startswith("/"):
                # Absolute inside the wiki means "from the wiki root"; elsewhere
                # it is a filesystem path and this gate does not police those.
                if not md.is_relative_to(wiki_root):
                    continue
                resolved = wiki_root / target.lstrip("/")
            else:
                resolved = md.parent / target
            if resolved.exists():
                continue
            # In the kit's own repository these resolve; in an install they are
            # absent by design, and a finding nobody can act on is how a gate
            # loses its reader.
            if _is_kit_repo_only(target) and not (ecosystem_dir / target.lstrip("./")).exists():
                continue
            broken.append((rel, url))
    return broken


#: A `file.md § Section` citation. The section name runs to the first delimiter that
#: cannot appear in a heading — a backtick, a full stop, a comma, a bracket, a quote.
_ANCHOR_RE = re.compile(r"`?([a-z0-9][a-z0-9./-]*\.md)`?\s*§\s*([^`.,;)\]\"\n]+"
                        r"(?:\n\s+[^`.,;)\]\"\n]+)?)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)

#: Section names that are not names. A template placeholder and a range of two
#: sections are both legitimate prose, and reporting them is how a checker earns
#: the reputation that gets it switched off.
_NOT_A_SECTION = re.compile(r"[{}]|^\d+\s*[–-]\s*\d+")


def _headings(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return {h.strip().lower() for h in _HEADING_RE.findall(text)}


def _resolve_cited_doc(name: str, citing: Path, ecosystem_dir: Path) -> Path | None:
    """The document a `§` citation points at, or None when it is not unambiguous.

    Ambiguity is answered with None rather than a guess. Two files named
    `improvement-prompt.md` live in this kit, and picking the first match reported a
    section as missing from a file that never contained it — a finding about the
    wrong document reads exactly like a real one.
    """
    leaf = name.split("/")[-1]
    for candidate in (citing.parent / name, ecosystem_dir / name,
                      ecosystem_dir / "rules" / leaf, citing.parent / leaf):
        if candidate.is_file():
            return candidate
    matches = [m for m in ecosystem_dir.rglob(leaf) if m.is_file()]
    return matches[0] if len(matches) == 1 else None


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
            Path(__file__).resolve().parents[2] / "skills")
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
    be named with the cycle- prefix, and
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


@dataclass
class _Xrefs:
    """What the nine checks share: the inventories, the manifest, the auxiliary set.

    A MUTABLE record on purpose. Two of the checks build fields the later ones read —
    `_check_skills_name_an_existing_cycle` fills `skill_to_cycle` and widens
    `project_auxiliary` from the install manifest, and the summary reads both. In the
    single 493-line function that happened through a shared scope, invisibly; here the
    dependency is a field with a name, and the order the driver runs them in is the
    order the fields become true.
    """

    ecosystem_dir: Path
    existing_skills: set[str]
    cycle_rules: dict
    project_auxiliary: set[str]
    kit_owned: set[str] | None
    kit_paths: set[str] | None
    cycle_to_skills: dict
    skill_to_cycle: dict
    rules_dir: Path
    #: Filled by `_check_referenced_rules_exist` and read by
    #: `_check_bare_filenames_are_here`. Two checks, one listing of `rules/`.
    existing_rule_files: set[str]
    #: Filled by `_check_no_orphan_skills` and read by the summary. The summary
    #: reported it as a fact about the run, and it is a result of one check.
    orphan_skills: set[str]

    def rel(self, path: Path) -> str:
        """`path` relative to the ecosystem, or unchanged when it lies outside."""
        try:
            return str(path.relative_to(self.ecosystem_dir))
        except ValueError:
            return str(path)


    def kit_owns(self, path: Path) -> bool:
        """True when the manifest claims this file, or when there is no manifest.

        The guard is on `kit_paths` — does a manifest exist at all — and NOT on
        `kit_owned`, which answers a narrower question: does the manifest list any
        SKILLS. Guarding on the narrow one made a manifest without skill entries read
        as no manifest, so every file in it came back as the kit's. Caught by a test
        whose fixture happened to list only a rule.

        A closure inside check 8 until check 11 turned out to need it too — which it
        already did, by reading a name check 8 happened to leave in scope.
        """
        if self.kit_paths is None:
            return True
        relative = self.rel(path)
        if relative.startswith("skills/"):
            return relative.split("/")[1] in (self.kit_owned or set())
        # `rules/` and the rest are listed per file, so the raw paths answer directly.
        # Without this a consumer's own `rules/*.md` read as the kit's, and its broken
        # references kept failing the kit's own install — measured on three of them.
        return relative in self.kit_paths


def _check_cycle_rules_name_existing_skills(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 1: each cycle rule references skills that exist

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 1: each cycle rule references skills that exist
    # `ctx.cycle_to_skills` is filled in place below: `_check_no_orphan_skills`
    # reads it, and in the single function it read it by being in the same scope.
    for cycle_name, cycle_path in ctx.cycle_rules.items():
        content = cycle_path.read_text(encoding="utf-8-sig")
        skills_mentioned = _extract_cycle_phases(content)
        ctx.cycle_to_skills[cycle_name] = skills_mentioned

        for skill in skills_mentioned:
            if skill not in ctx.existing_skills:
                findings.append({
                    "severity": "WARN",
                    "check": "cycle_rule_references_existing_skill",
                    "cycle": cycle_name,
                    "missing_skill": skill,
                    "message": f"{ctx.rel(cycle_path)} references skill `{skill}` which does not exist at skills/{skill}/",
                })
    return findings


def _check_skills_name_an_existing_cycle(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 2: each SKILL.md points to an existing cycle

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 2: each SKILL.md points to an existing cycle
    # The exemption applies to BOTH checks. `_is_auto_generated`'s docstring records
    # why: the first version exempted only `no_orphan_skills` and left this one
    # enforcing — half an exemption, which traded 26 WARN for 3 and looked like a fix.
    # The auxiliary set is read once, when the record is built. This re-read it and
    # threw the answer away; the widening below is what has to survive, and it does
    # by landing on the record both this check and the orphan check consult. Half an
    # exemption is how this went wrong before.

    # A skill the install manifest does not claim is the project's, and the kit has no
    # standing to demand a cycle contract from it. Folded into the SAME variable both
    # checks already read, for the reason the comment above records: the last time an
    # exemption reached one check and not the other, it traded 26 WARN for 3 and looked
    # like a fix.
    # The manifest is read ONCE, when the record is built. These two lines re-read it
    # and threw the answer away; the widening below is the part that had to survive,
    # and it survives by landing on the record both this check and the orphan check
    # read. Half an exemption is how this went wrong before.
    if ctx.kit_owned is not None:
        ctx.project_auxiliary = ctx.project_auxiliary | (ctx.existing_skills - ctx.kit_owned)

    for skill in ctx.existing_skills:
        skill_md = ctx.ecosystem_dir / "skills" / skill / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8-sig")
        cycle_ref = _extract_cycle_contract_ref(content, ctx.existing_skills)
        ctx.skill_to_cycle[skill] = cycle_ref

        if (cycle_ref is None and skill not in AUXILIARY_SKILLS
                and skill not in ctx.project_auxiliary and not _is_auto_generated(skill)):
            findings.append({
                "severity": "WARN",
                "check": "skill_has_cycle_contract",
                "skill": skill,
                "message": f"skills/{skill}/SKILL.md has no `Cycle contract` section pointing to a cycle-*.md",
            })
        elif cycle_ref is not None:
            expected_cycle = f"cycle-{cycle_ref}"
            if expected_cycle not in ctx.cycle_rules:
                findings.append({
                    "severity": "FAIL",
                    "check": "skill_cycle_contract_resolves",
                    "skill": skill,
                    "cycle_referenced": expected_cycle,
                    "message": f"skills/{skill}/SKILL.md references cycle-{cycle_ref}.md but it does not exist",
                })
    return findings


def _check_cross_references_resolve(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 3: cycle rule cross-references point to existing files

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 3: cycle rule cross-references point to existing files
    for cycle_name, cycle_path in ctx.cycle_rules.items():
        content = cycle_path.read_text(encoding="utf-8-sig")
        # Cross-references section
        xref_match = re.search(r"## Cross-references.*?(?=^##\s+|\Z)", content, re.MULTILINE | re.DOTALL)
        if not xref_match:
            findings.append({
                "severity": "WARN",
                "check": "cycle_has_xref_section",
                "cycle": cycle_name,
                "message": f"{ctx.rel(cycle_path)} has no `Cross-references` section",
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
                candidates_to_try.append(ctx.ecosystem_dir / normalized)
                # If path starts with a skill name (e.g., plan-confidence/templates/...), try skills/
                first_segment = normalized.split("/", 1)[0]
                if (ctx.ecosystem_dir / "skills" / first_segment).exists():
                    candidates_to_try.append(ctx.ecosystem_dir / "skills" / normalized)

            if not any(c.exists() for c in candidates_to_try):
                findings.append({
                    "severity": "WARN",
                    "check": "cycle_xref_file_exists",
                    "cycle": cycle_name,
                    "broken_ref": ref,
                    "message": f"{ctx.rel(cycle_path)} references `{ref}` which does not exist",
                })
    return findings


def _check_referenced_rules_exist(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 7: rules referenced from SKILL.md bodies + scripts must exist on disk.

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 7: rules referenced from SKILL.md bodies + scripts must exist on disk.
    #
    # `rules/` was the only rooted path this check knew, and on 2026-09-01 that
    # became a hole: six kit-owned rules moved to `skills/_kit-rules/`, and every
    # reference to their new home was unvalidated. Forty-four references pointed
    # at a directory that did not yet exist and this validator reported PASS.
    #
    # Check 3 does resolve arbitrary paths — but only inside a cycle rule's
    # `## Cross-references` section. A path named anywhere else, in any SKILL.md,
    # was nobody's job.
    ctx.rules_dir = ctx.ecosystem_dir / "rules"
    ctx.existing_rule_files = ({p.name for p in ctx.rules_dir.glob("*")}
                               if ctx.rules_dir.exists() else set())

    def _scan_for_rule_refs(path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return
        for m in RULES_REF_RE.finditer(content):
            rule_name = m.group(1)
            if rule_name in ctx.existing_rule_files:
                continue
            findings.append({
                "severity": "FAIL",
                "check": "rules_reference_resolves",
                "source": ctx.rel(path),
                "missing_rule": rule_name,
                "message": f"{ctx.rel(path)} references `rules/{rule_name}` which does not exist",
            })
        for m in SKILLS_REF_RE.finditer(content):
            target = ctx.ecosystem_dir / "skills" / m.group(1)
            if target.exists():
                continue
            findings.append({
                "severity": "FAIL",
                "check": "skills_reference_resolves",
                "source": ctx.rel(path),
                "missing_path": f"skills/{m.group(1)}",
                "message": (f"{ctx.rel(path)} references `skills/{m.group(1)}` "
                            f"which does not exist"),
            })

    for skill_md in (ctx.ecosystem_dir / "skills").rglob("SKILL.md"):
        if skill_md.is_file():
            _scan_for_rule_refs(skill_md)
    # A rule citing another rule was the blind spot: the scan covered skills and
    # scripts and skipped all of `rules/`, which is where the normative anchors live.
    for rule_md in ctx.rules_dir.glob("*.md") if ctx.rules_dir.exists() else []:
        if rule_md.is_file():
            _scan_for_rule_refs(rule_md)
    for py in (ctx.ecosystem_dir / "skills").rglob("*.py"):
        if py.is_file() and "__pycache__" not in py.parts:
            _scan_for_rule_refs(py)
    for py in (ctx.ecosystem_dir / "mechanisms").rglob("*.py"):
        if py.is_file() and "__pycache__" not in py.parts:
            _scan_for_rule_refs(py)
    return findings


def _check_cited_cycles_resolve(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 8: `cycle-<name>` cited in code/rules must resolve to a cycle rule

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 8: `cycle-<name>` cited in code/rules must resolve to a cycle rule
    # (`rules/cycle-<name>.md`) or to a skill (`skills/cycle-<name>/`).
    # Why: `rules/cycle-acceptance.md` and `rules/cycle-release.md` anchored the
    # single-flip invariant at "cycle-roadmap § Hard gates" AFTER cycle-roadmap had
    # become cycle-maintenance. No check saw it: Check 7 matches paths shaped like
    # rules/<file>.md, and a citation by name is not a path. Only backticked text
    # counts — loose prose ("a cycle-level decision") would produce noise while
    # naming nothing.
    # Existence on disk, not the cycle list: `cycle-rule-schema.md` is meta
    # documentation and stays OUT of `ctx.cycle_rules` on purpose — but citing it is
    # legitimate, the file is there.
    cycle_skill_names = {s for s in ctx.existing_skills if s.startswith("cycle-")}

    def _scan_for_cycle_refs(path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return
        for code_span in BACKTICK_SPAN_RE.findall(content):
            for name in CYCLE_NAME_RE.findall(code_span):
                cycle_id = f"cycle-{name}"
                if (ctx.rules_dir / f"{cycle_id}.md").exists() or cycle_id in cycle_skill_names:
                    continue
                # A broken reference is a real defect wherever it sits, so it is
                # always reported. But its SEVERITY depends on who wrote the file:
                # the kit cannot fail its own installation over a line it did not
                # write, and `install.sh` runs this `--strict`.
                #
                # Measured on 2026-08-31 across three consumers: each carried two
                # skills and one golden-rule file of its own, all citing a cycle rule
                # the SIBLING kit ships. They are repositories holding one kit's
                # artefacts while installed with the other, which is worth telling
                # them, and is not a reason to call the install broken.
                #
                # (The paths are described rather than quoted: this checker also
                # verifies that a backticked path exists, and citing a consumer's
                # file here would fail the kit's own sweep.)
                own = ctx.kit_owns(path)
                findings.append({
                    "severity": "FAIL" if own else "WARN",
                    "owner": "kit" if own else "project",
                    "check": "cycle_reference_resolves",
                    "source": ctx.rel(path),
                    "broken_ref": cycle_id,
                    "message": (f"{ctx.rel(path)} references `{cycle_id}` — no rules/{cycle_id}.md "
                                f"and no skills/{cycle_id}/ exists"
                                + ("" if own else ". This file is the project's, not the kit's; "
                                   "the reference may belong to the sibling kit")),
                })

    for rule_md in ctx.rules_dir.glob("*.md") if ctx.rules_dir.exists() else []:
        if rule_md.is_file():
            _scan_for_cycle_refs(rule_md)
    for skill_md in (ctx.ecosystem_dir / "skills").rglob("SKILL.md"):
        if skill_md.is_file():
            _scan_for_cycle_refs(skill_md)
    return findings


def _check_derived_specialists_are_reviewed(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 9: a DERIVED specialist nobody reviewed.

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 9: a DERIVED specialist nobody reviewed.
    # `detect_domains.py` generates a skeleton so the route stops being BROKEN, with
    # the judgement sections (commands, real findings, false positives, invariants)
    # empty and marked. A silent skeleton is worse than a broken route: the broken
    # route warns, and this one looks like a finished specialist. WARN while the
    # marker exists — it disappears on its own when someone fills it in.
    agents_dir = ctx.ecosystem_dir / "agents"
    if agents_dir.is_dir():
        for agent_md in sorted(agents_dir.glob("*.md")):
            try:
                body = agent_md.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            if UNREVIEWED_SECTION not in body:
                continue
            pending = body.count(UNREVIEWED_SECTION)
            findings.append({
                "severity": "WARN",
                "check": "specialist_unreviewed",
                "agent": agent_md.stem,
                "message": f"agents/{agent_md.name} is a derived skeleton with {pending} "
                           "section(s) left to fill — the routing works, the judgement does not",
            })
    return findings


def _check_section_citations_resolve(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 10: a `file.md § Section` citation resolves to a heading that exists.

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 10: a `file.md § Section` citation resolves to a heading that exists.
    #
    # Checks 3 and 7 answer "does the FILE exist". Nothing asked whether the SECTION
    # does, and a section is what a reader is actually sent to. Measured 2026-08-31,
    # by hand: **14 dead anchors across 10 files.** Three classes, and the third is
    # the one worth the check:
    #
    #   renamed   `architecture.md § Module hygiene` in four files; the heading has
    #             read `§ 3 — Module cohesion` for as long as git remembers
    #   misquoted `§ What it requires` for `§ 2 — What the rule requires`
    #   never written  three skills opened their loop step with "Read
    #             `loop-engine-convention.md § How to invoke ralph-loop:ralph-loop
    #             safely` BEFORE this step", and that section did not exist. Each
    #             then restated the fact in its own words — one piece of knowledge
    #             in three copies, with its named home empty.
    #
    # A citation that survives the rename of what it points at is worse than a
    # missing one: the reader goes looking, finds a document that plainly exists,
    # and concludes the section was removed on purpose.
    for doc in sorted(list(ctx.ecosystem_dir.glob("skills/**/*.md"))
                      + list(ctx.ecosystem_dir.glob("rules/*.md"))):
        try:
            content = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for cited_name, cited_section in _ANCHOR_RE.findall(content):
            section = " ".join(cited_section.split()).strip().lower()
            if not section or len(section) < 3 or _NOT_A_SECTION.search(section):
                continue
            target = _resolve_cited_doc(cited_name, doc, ctx.ecosystem_dir)
            if target is None:
                continue
            headings = _headings(target)
            if any(section == h or section in h or h in section for h in headings):
                continue
            findings.append({
                "severity": "WARN",
                "check": "cited_section_does_not_exist",
                "document": ctx.rel(doc),
                "target": cited_name,
                "section": cited_section.strip(),
                "message": (f"{ctx.rel(doc)} cites `{cited_name} § {cited_section.strip()}` "
                            f"and that document has no such heading"),
            })
    return findings


def _check_bare_filenames_are_here(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 11: inside `rules/`, a bare filename is a claim that the file is HERE.

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 11: inside `rules/`, a bare filename is a claim that the file is HERE.
    #
    # Check 7 needs the literal `rules/` prefix, and the one document that never uses
    # it is `rules/README.md` — an inventory written for a reader already standing in
    # the directory, so every cell of every table cites by bare name. Check 3 does
    # accept a bare leaf, but it resolves with `rglob` across the whole tree (a file
    # that MOVED OUT of `rules/` still resolves) and it only reads the
    # `## Cross-references` section of `cycle-*.md`, never the README.
    #
    # Measured 2026-09-07: four names in those tables did not resolve to `rules/`.
    # `discover-plan-golden-rule.md`, `review-model-routing.txt` and
    # `audit-trail-rotation.md` had moved to `skills/_kit-rules/` on 2026-09-01 and
    # the tables did not follow; `dogfood-golden-rule.md` existed nowhere. PASS on
    # all four.
    #
    # TWO ARMS, AND WHY NEITHER IS WIDER
    # ----------------------------------
    # (a) EVERYWHERE in `rules/*.md`: a bare name whose file lives elsewhere in the
    #     kit. That is the misdirection worth failing on — the reader is sent to a
    #     directory the file has left, and finds a plausible absence rather than an
    #     error. A document that ALSO cites the real path is exempt: it has already
    #     told the reader where to go (`alignment-threshold.md`, cited bare and
    #     located in the same breath by `cycle-brainstorm.md` and `cycle-plan.md`).
    #
    # (b) `rules/README.md` ONLY: a bare name that resolves nowhere. The inventory's
    #     rows are the claim "this is a file in rules/", so a row naming nothing is
    #     a defect there and nowhere else.
    #
    # Arm (a) deliberately cannot reach a name that exists nowhere, which is what
    # keeps the eleven legitimate bare cites in `rules/*.md` silent: the four
    # documents a consumer produces (`product-vision.md` and siblings), an external
    # plugin's state file (`ralph-loop.local.md`), and the golden rule
    # `cycle-judge-codex.md` names in a sentence saying it never existed here.
    _BARE_RULE_NAME_RE = re.compile(r"`([a-z0-9][a-z0-9._-]*\.(?:md|txt))`")
    #: What the installer says it brought. None in the kit's own checkout, where the
    #: whole tree is the kit's and a collision cannot be the consumer's.
    kit_files = _kit_shipped_paths(ctx.ecosystem_dir)
    if ctx.rules_dir.is_dir():
        for rule_md in sorted(ctx.rules_dir.glob("*.md")):
            try:
                body = rule_md.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            is_inventory = rule_md.name == "README.md"
            for m in _BARE_RULE_NAME_RE.finditer(body):
                name = m.group(1)
                if name == rule_md.name or name in ctx.existing_rule_files:
                    continue
                # The document located it itself — no reader was misdirected.
                if re.search(rf"[A-Za-z0-9_/-]+/{re.escape(name)}", body):
                    continue
                elsewhere = [p for p in ctx.ecosystem_dir.rglob(name)
                             if p.is_file() and "__pycache__" not in p.parts]
                if not elsewhere and not is_inventory:
                    continue
                # Same split as Check 8, for the reason measured there: a consumer may
                # add rules of its own, and one of them citing a file the kit does not
                # ship is worth reporting without calling the install broken.
                own = ctx.kit_owns(rule_md)

                #: A NAME COLLISION IS NOT A MISDIRECTION, and a consumer's filename
                #: must not fail a kit gate.
                #:
                #: This check asks "does any file anywhere have this name?" and treats a
                #: hit as proof the citation pointed at the wrong place. Two different
                #: things can share a filename. Measured on a consumer install: the kit's
                #: own `cycle-design.md` cites `trust.md` meaning drawing D2, the
                #: consumer had a repository called `*-trust`, and `scaffold_specialists.py`
                #: — also the kit's — wrote `agents/trust.md` for it. The gate then FAILED
                #: with `owner: kit`, on a name the consumer had every right to choose and
                #: in a file the consumer could not edit.
                #:
                #: The drawing slots are especially exposed: domain names come from
                #: repository names, which the kit does not control.
                #:
                #: So when every match is a file the KIT DID NOT SHIP, this is the
                #: consumer's tree colliding with the kit's vocabulary — reported, and
                #: reported as theirs, never as a failure of the install.
                if elsewhere and own and kit_files is not None:
                    if not any(ctx.rel(match) in kit_files for match in elsewhere):
                        own = False
                message = (
                    f"{ctx.rel(rule_md)} cites `{name}` as if it were in rules/; "
                    f"the file is in {(ctx.rel(elsewhere[0].parent) or '.')}/"
                    if elsewhere else
                    f"{ctx.rel(rule_md)} inventories `{name}`, which exists nowhere "
                    "in the ecosystem"
                )
                findings.append({
                    "severity": "FAIL" if own else "WARN",
                    "owner": "kit" if own else "project",
                    "check": "bare_rule_name_resolves",
                    "source": ctx.rel(rule_md),
                    "missing_rule": name,
                    "message": message,
                })
    return findings


def _check_no_orphan_skills(ctx: "_Xrefs") -> list[dict[str, Any]]:
    """Check 4: orphan skills (not in any cycle, not auxiliary)

    Extracted from `validate_xrefs`, which measured cyclomatic complexity 91 across
    493 lines holding nine independent checks. Pure code movement: the block below is
    the block that was there.

    `ctx` is what the checks SHARE — the skill and rule inventories, the install
    manifest, the auxiliary set. They shared it by being in one scope, which is also
    why the function could not be split; naming it makes the sharing visible and lets
    each check say in its signature that it reads nothing else.
    """
    findings: list[dict[str, Any]] = []
    # Check 4: orphan skills (not in any cycle, not auxiliary)
    skills_in_cycles: set[str] = set()
    for skills_set in ctx.cycle_to_skills.values():
        skills_in_cycles.update(skills_set)

    # Skills AUTO-GENERATED by the cycles themselves are phases of no cycle: they are
    # ARTEFACTS of one execution. `/review` writes `review-{slug}-{dimension}-knowledge`
    # and discover writes `*-sepa-knowledge`. patch_install already treats them as such
    # ("Auto-generated skills (SEPA-knowledge, review-*-knowledge) preserved"), but
    # this validator reported them as orphans -- so every consumer that ran /review
    # started failing --strict, and the failure surfaced far from its cause.
    # Measured 2026-08-03: the three monitored consumers failed in exactly this way
    # after running review, with 26 WARN and no real defect.
    auto_generated = {s for s in ctx.existing_skills if _is_auto_generated(s)}
    ctx.orphan_skills = (ctx.existing_skills - skills_in_cycles - AUXILIARY_SKILLS
                         - ctx.project_auxiliary - auto_generated)
    for skill in sorted(ctx.orphan_skills):
        findings.append({
            "severity": "WARN",
            "check": "no_orphan_skills",
            "skill": skill,
            "message": f"Skill `{skill}` is not referenced by any cycle-*.md and is not in AUXILIARY_SKILLS",
        })

    # Aggregate
    return findings


def validate_xrefs(ecosystem_dir: Path, strict: bool = False) -> dict[str, Any]:
    # In standalone layout, the "project root" IS the ecosystem dir; in plugin
    # layout it is the parent. Use ecosystem_dir for path display so the report
    # is unambiguous regardless of layout.
    existing_skills = _list_existing_skills(ecosystem_dir)
    cycle_rules = _list_cycle_rules(ecosystem_dir)

    findings: list[dict[str, Any]] = []

    # Markdown links, which this gate carried the machinery for and never ran.
    # WARN rather than FAIL: a broken link misleads a reader and breaks nothing
    # that executes, and a gate that blocks a release over a moved document is a
    # gate somebody routes around.
    for citing, target in broken_markdown_links(ecosystem_dir):
        findings.append({
            "severity": "WARN",
            "check": "markdown_link_resolves",
            "file": citing,
            "target": target,
            "message": f"{citing} links to `{target}`, which does not exist",
        })

    ctx = _Xrefs(
        ecosystem_dir=ecosystem_dir,
        existing_skills=existing_skills,
        cycle_rules=cycle_rules,
        project_auxiliary=_declared_auxiliary_skills(ecosystem_dir),
        kit_owned=_kit_owned_skills(ecosystem_dir),
        kit_paths=_kit_manifest_paths(ecosystem_dir),
        cycle_to_skills={},
        skill_to_cycle={},
        rules_dir=ecosystem_dir / "rules",
        existing_rule_files=set(),
        orphan_skills=set(),
    )

    findings.extend(_check_cycle_rules_name_existing_skills(ctx))
    findings.extend(_check_skills_name_an_existing_cycle(ctx))
    findings.extend(_check_cross_references_resolve(ctx))
    findings.extend(_check_referenced_rules_exist(ctx))
    findings.extend(_check_cited_cycles_resolve(ctx))
    findings.extend(_check_derived_specialists_are_reviewed(ctx))
    findings.extend(_check_section_citations_resolve(ctx))
    findings.extend(_check_bare_filenames_are_here(ctx))
    findings.extend(_check_no_orphan_skills(ctx))
    severity_counts = defaultdict(int)
    for f in findings:
        severity_counts[f["severity"]] += 1

    # `--strict` is rigour about the KIT. A finding tagged `owner: project` describes
    # a file the kit did not write, and promoting it to a failure means the kit refuses
    # to install over someone else's content — which is the shape this whole check was
    # just corrected for. Measured after the severity fix: three consumers reported
    # zero FAIL and five WARN, and `install.sh --strict` still called every one of them
    # broken.
    #
    # The finding is unchanged and still printed. What changes is who it can fail.
    strict_warnings = sum(
        1 for f in findings
        if f["severity"] == "WARN" and f.get("owner", "kit") != "project"
    )
    overall = "PASS"
    if severity_counts.get("FAIL", 0) > 0 or (strict and strict_warnings > 0):
        overall = "FAIL"

    return {
        "ecosystem_dir": str(ecosystem_dir),
        "skills_total": len(existing_skills),
        #: The other half of the population. `skills_total` alone cannot tell a tree with
        #: no rules from one whose rules all resolve.
        "cycle_rules_total": len(cycle_rules),
        "skills_auxiliary": sorted(AUXILIARY_SKILLS & ctx.existing_skills),
        "skills_orphan": sorted(ctx.orphan_skills),
        "cycle_rules": sorted(cycle_rules.keys()),
        "skill_to_cycle": ctx.skill_to_cycle,
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
    parser.add_argument(
        "--root", "--ecosystem-dir", dest="root", type=Path, default=None, help="Override ecosystem directory detection")
    parser.add_argument("--claude-dir", type=Path, default=None, help="(deprecated alias for --ecosystem-dir)")
    args = parser.parse_args()

    override = args.root or args.claude_dir
    if override:
        ecosystem_dir = override.resolve()
    else:
        # The root comes from WHERE THE SCRIPT LIVES, not from the cwd. The previous
        # version started at Path.cwd(), and the effect was a validator that lies:
        # running
        # `python3 <another-project>/.claude/mechanisms/gates/check_xrefs.py` from an arbitrary cwd
        # silently audited the ecosystem OF THE CWD and printed that one's verdict.
        # Measured 2026-08-03: three consumers reported as PASS actually carried
        # 3, 0 and 11 findings -- the PASS was the kit's own repo validating itself.
        # A validator that audits the wrong target is worse than none, because it
        # produces unfounded confidence. The script's own path is the only anchor
        # that does not depend on who called it.
        ecosystem_dir = _find_ecosystem_dir(Path(__file__).resolve().parents[2])
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

    # `_list_existing_skills` returns an empty set when `skills/` is absent and
    # `_list_cycle_rules` an empty dict when `rules/` is. Every check in `validate_xrefs`
    # then iterates an empty population, `severity_counts` stays empty, `overall` computes
    # to PASS and this returned 0 — a cross-reference validator reporting that every
    # reference resolves, over a tree holding no references at all.
    if not result["skills_total"] and not result.get("cycle_rules_total"):
        print("UNCHECKED: this tree has no skills/ and no rules/, so there was nothing "
              "to cross-reference. An ecosystem this validator cannot see is not an "
              "ecosystem it can vouch for.", file=sys.stderr)
        return 2

    return 0 if result["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

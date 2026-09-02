#!/usr/bin/env python3
"""End-to-end smoke test for the planning ecosystem.

Supports dual-mode layouts:
  - Standalone — the ecosystem repo itself (skills/+rules/+hooks/ directly).
  - User config — <home>/.claude/.
  - Plugin install — <root>/.claude/plugins/cycle/.

Validates:
  1. All Python scripts have valid syntax (compiled in memory — nothing is written)
  2. All shell hooks have valid bash syntax
  3. settings.json is valid JSON
  4. Cross-reference validator passes
  5. Each cycle rule exists + has required sections
  6. Each first-class skill has a valid SKILL.md frontmatter
  7. Smoke chain: detect_domain → spawn_reviewers → consolidate_findings works in sequence

Run from any directory inside the layout:
    python3 mechanisms/gates/verify_ecosystem.py                # standalone
    python3 .claude/mechanisms/gates/verify_ecosystem.py        # plugin install

Exit codes:
  0 — All checks passed
  1 — At least one check failed
  2 — Error (ecosystem dir not found, etc.)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# The family this file lives in, plus `lib/` — the import namespace stayed flat
# when `scripts/` became `mechanisms/<family>/`, so a sibling family is reached
# by path rather than by package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "conventions"))

from ecosystem_utils import find_ecosystem_dir


def _find_ecosystem_dir() -> Path:
    """Locate ecosystem directory (delegates to shared module)."""
    return find_ecosystem_dir(require=True)  # type: ignore[return-value]


_SYNTAX_SKIP_DIRS = frozenset({
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".hypothesis",
    ".git", "node_modules", ".venv", "venv",
})


def check_python_syntax(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Compiles in memory — nothing is written to the target.

    `py_compile.compile` WRITES the `.pyc` as a side effect, and that cost both
    things: 267 ms of this script's 693 ms (measured 2026-08-26, 259 files) and
    the reintroduction of the cache `install.sh` had just excluded from the copy
    — the reason `prune_caches` exists. Checking syntax does not require writing
    bytecode: `compile()` answers the same question without touching disk.

    The pruning happens DURING the walk; an `rglob` with a later filter descends
    into all of `.git` and `node_modules` before discarding them.
    """
    issues: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ecosystem_dir):
        dirnames[:] = [d for d in dirnames if d not in _SYNTAX_SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            py = Path(dirpath) / name
            try:
                compile(py.read_text(encoding="utf-8"), str(py), "exec")
            except SyntaxError as exc:
                issues.append(f"  syntax error in {py.relative_to(ecosystem_dir)}: {exc}")
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                issues.append(f"  unreadable source {py.relative_to(ecosystem_dir)}: {exc}")
    return len(issues) == 0, issues


def check_shell_syntax(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    issues: list[str] = []
    sh_files = list((ecosystem_dir / "hooks").glob("*.sh"))
    sh_files.extend((ecosystem_dir / "skills").rglob("*.sh"))
    sh_files.extend((ecosystem_dir / "mechanisms").rglob("*.sh"))
    for sh in sh_files:
        result = subprocess.run(  # noqa: PLW1510
            ["bash", "-n", str(sh)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            issues.append(f"  shell syntax error in {sh.relative_to(ecosystem_dir)}: {result.stderr.strip()}")
    return len(issues) == 0, issues


def check_settings_json(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    issues: list[str] = []
    for json_file in ("settings.json", "settings.local.json", "settings.local.json.example"):
        path = ecosystem_dir / json_file
        if not path.exists():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            issues.append(f"  invalid JSON in {json_file}: {exc}")
    return len(issues) == 0, issues


def check_xrefs(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    validator = ecosystem_dir / "mechanisms" / "gates" / "check_xrefs.py"
    if not validator.exists():
        return True, ["  check_xrefs.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(validator), "--ecosystem-dir", str(ecosystem_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, [f"  check_xrefs.py returned {result.returncode}", "  " + result.stdout[-200:]]
    return True, []


def check_skill_map(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does `skills/map.md` still list every skill on disk, and only those?

    The index it replaced drifted twice, and the second drift left four skills
    reachable by nobody: on disk, passing every validator, mentioned in no entry
    point. An index is the one document nothing forces you to open when you add a
    file, so it goes stale by default and reads as complete while it does.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_skill_map.py"
    if not checker.exists():
        return True, ["  check_skill_map.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), "--root", str(ecosystem_dir), "--json"],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, [f"  check_skill_map.py produced no usable JSON "
                       f"(exit {result.returncode})"]
    findings = payload.get("findings", [])
    return not findings, [f"  {f}" for f in findings]


def check_squad_map(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does `rules/squad-map.md` still describe the system that is on disk?

    Same lesson as `check_skill_map`, one level up and with a sharper cost: this map
    is injected at SessionStart, so a stale one is not a document somebody might
    open — it is a false premise in the agent's opening context, which every later
    decision rests on.

    It checks the four things only this map claims — phases, cycles, kit agents,
    hooks — and deliberately leaves the skill inventory to `check_skill_map.py`,
    because two checkers over one fact can disagree about it.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_squad_map.py"
    if not checker.exists():
        return True, ["  check_squad_map.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), "--root", str(ecosystem_dir), "--json"],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, [f"  check_squad_map.py produced no usable JSON "
                       f"(exit {result.returncode})"]
    findings = payload.get("findings", [])
    return not findings, [f"  {f['message']}" for f in findings]


def check_mechanisms_inventory(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does `mechanisms/README.md` still list what `mechanisms/` holds?

    The README this directory replaced declared *"Every new script in this
    directory MUST be added to the inventory above"* and inventoried 5 of 36
    files: the rule was real, nothing computed it, and the list decayed to a
    sample while still reading as complete. Same lesson as the two maps above,
    one directory over.

    A file with no row is a mechanism nobody can learn about; a row with no file
    sends the reader somewhere gone; a row under the wrong family is the worst of
    the three, because it is present and therefore trusted.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_mechanisms_inventory.py"
    if not checker.exists():
        return True, ["  check_mechanisms_inventory.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), "--root", str(ecosystem_dir), "--json"],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, [f"  check_mechanisms_inventory.py produced no usable JSON "
                       f"(exit {result.returncode})"]
    if payload.get("verdict") == "INVENTORY_UNREADABLE":
        return False, [f"  {payload.get('detail', 'the inventory could not be read')}"]
    rows = (payload.get("undocumented", []) + payload.get("phantom", [])
            + payload.get("misfiled", []) + payload.get("undeclared_families", []))
    return not rows, [f"  {r}" for r in rows]


def check_phase_numbering(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Do the skills of a cycle agree with each other about their own order?

    Third of the phase sweeps and the only one that looks inside a cycle. A number
    claimed by two skills is a contract that answers differently depending on which
    file the reader opened, and the kit shipped exactly that to every consumer for
    five days after `/deps-audit` was inserted into `cycle-plan`.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_phase_numbering.py"
    if not checker.exists():
        return True, ["  check_phase_numbering.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), "--root", str(ecosystem_dir), "--json"],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, [f"  check_phase_numbering.py produced no usable JSON "
                       f"(exit {result.returncode})"]
    findings = payload.get("findings", [])
    if findings:
        return False, [f"  {f['cycle']}: {f['detail']}" for f in findings]
    return True, []


def check_wiki_migration(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Is this project still reading its durable knowledge from the old root?

    Two states, two severities, and the difference is the point.

    `UNMIGRATED` is a transition in progress, not a defect: the fallback exists
    because the kit cannot run a migration inside a project it does not own, and
    failing every consumer on the day the split was declared would produce a
    gate somebody switches off. It is reported as a NOTE — visible, which is the
    whole promise, and not blocking.

    `SPLIT` fails. Both roots holding the same kind of document is the state
    `records-location.md` was written about: the reader resolves the bundle and
    the old copy becomes unreachable, so it cannot be seen to be stale, and
    nothing errors while the two drift.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_wiki_migration.py"
    if not checker.exists():
        return True, ["  check_wiki_migration.py not installed — skipping"]
    project_root = (ecosystem_dir.parent if ecosystem_dir.name == ".claude"
                    else ecosystem_dir)
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), "--root", str(project_root), "--json"],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, [f"  check_wiki_migration.py produced no usable JSON "
                       f"(exit {result.returncode})"]
    split = [leaf for leaf in payload["leaves"] if leaf["state"] == "SPLIT"]
    unmigrated = [leaf for leaf in payload["leaves"] if leaf["state"] == "UNMIGRATED"]
    if split:
        return False, [f"  SPLIT: `{leaf['leaf']}` — {leaf['detail']}" for leaf in split]
    if unmigrated:
        return True, [f"  note: `{leaf['leaf']}` — {leaf['detail']}"
                      for leaf in unmigrated]
    return True, []


def check_cycle_rules(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    issues: list[str] = []
    required_sections = ("## Purpose", "## Chain", "## Anti-patterns")
    for cycle_name in ("discover", "plan", "implement", "review", "code-quality", "idea-to-release"):
        rule = ecosystem_dir / "rules" / f"cycle-{cycle_name}.md"
        if not rule.exists():
            issues.append(f"  missing cycle rule: cycle-{cycle_name}.md")
            continue
        content = rule.read_text(encoding="utf-8-sig")
        for section in required_sections:
            if section not in content:
                issues.append(f"  cycle-{cycle_name}.md missing section `{section}`")
    return len(issues) == 0, issues


def check_skill_frontmatter(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Validate every SKILL.md has a parseable YAML frontmatter with required fields.

    The earlier substring check (`"name:" in fm`) silently passed `roadmap-feature/SKILL.md`
    when the description contained an unquoted colon that made YAML parsing fail —
    Claude Code aborts skill discovery for an entire tree on a single invalid frontmatter,
    so the gap caused 'skills do not load on consumers'. This function now validates the
    YAML structurally with PyYAML and requires the canonical fields.
    """
    issues: list[str] = []
    required_fields = ("name", "description")
    try:
        import yaml  # PyYAML — listed as a setup pre-condition in README
    except ImportError:
        issues.append("  PyYAML not available — install via `pip install pyyaml`")
        return False, issues

    for skill_dir in (ecosystem_dir / "skills").iterdir():
        # A leading underscore marks a directory under `skills/` that is NOT a
        # skill — `_kit-rules/` holds rules two or more skills read. Every other
        # enumerator in the kit finds skills by the presence of `SKILL.md` and so
        # never sees it; this one enumerated directories and demanded the file,
        # which turned a deliberate non-skill into a missing one.
        # A dot-directory under `skills/` is a tool artifact, never a skill:
        # pytest-benchmark drops `.benchmarks/` here on any run that measures, and
        # this check then reported the tool's own output as a broken skill.
        if not skill_dir.is_dir() or skill_dir.name == "generated" \
                or skill_dir.name.startswith(("_", ".")):
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            issues.append(f"  skill {skill_dir.name} missing SKILL.md")
            continue
        content = skill_md.read_text(encoding="utf-8-sig")
        if not content.startswith("---\n"):
            issues.append(f"  {skill_dir.name}/SKILL.md missing opening frontmatter")
            continue
        end = content.find("\n---\n", 4)
        if end == -1:
            issues.append(f"  {skill_dir.name}/SKILL.md missing closing frontmatter")
            continue
        fm_raw = content[4:end]
        try:
            fm = yaml.safe_load(fm_raw)
        except yaml.YAMLError as e:
            # Compact the YAML error to a single line so the report stays readable.
            err = str(e).splitlines()[0] if str(e) else "unknown YAML error"
            issues.append(
                f"  {skill_dir.name}/SKILL.md YAML frontmatter is invalid: {err}"
            )
            continue
        if not isinstance(fm, dict):
            issues.append(
                f"  {skill_dir.name}/SKILL.md frontmatter is not a YAML mapping"
            )
            continue
        for field in required_fields:
            if not fm.get(field):
                issues.append(f"  {skill_dir.name}/SKILL.md missing field `{field}`")
    return len(issues) == 0, issues


def check_smoke_chain(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Exercise detect_domain → spawn_reviewers → consolidate_findings in sequence."""
    issues: list[str] = []
    review_skill = ecosystem_dir / "skills" / "review"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 1. Create a sample plan
        plan = tmp / "smoke-plan.md"
        plan.write_text(
            "# Plan: Smoke\n\n## Context\n\nPgvector schema with Alembic migrations.\n\n## ADRs\n\n### D1 — adopt pgvector\n\nReason.\n",
            encoding="utf-8",
        )

        # 2. detect_domain
        detect = review_skill / "scripts" / "detect_domain.py"
        r1 = subprocess.run(  # noqa: PLW1510
            [sys.executable, str(detect), "--plan", str(plan)],
            capture_output=True, text=True,
        )
        if r1.returncode not in (0, 1):
            issues.append(f"  detect_domain exit {r1.returncode}: {r1.stderr[:200]}")
            return False, issues

        domain_data = json.loads(r1.stdout)
        primary = domain_data.get("primary_domain", "unknown")

        # 3. spawn_reviewers
        # NOTE: pass --skills-dir <tmp_skills> isolated from the real .claude/skills/.
        # Without this override, spawn_reviewers writes the paired knowledge skills
        # into the real registry and pollutes the project's skill autocomplete with
        # `review-smoke-*-knowledge` entries (regression observed pre-2026-05-30).
        agents_out = tmp / "agents"
        tmp_skills = tmp / "skills"
        tmp_skills.mkdir(parents=True, exist_ok=True)
        spawn = review_skill / "scripts" / "spawn_reviewers.py"
        r2 = subprocess.run(  # noqa: PLW1510
            [sys.executable, str(spawn),
             "--plan", str(plan),
             "--slug", "smoke",
             "--primary-domain", primary if primary != "unknown" else "memory-layer",
             "--output-dir", str(agents_out),
             "--skill-dir", str(review_skill),
             "--skills-dir", str(tmp_skills)],
            capture_output=True, text=True,
        )
        if r2.returncode != 0:
            issues.append(f"  spawn_reviewers exit {r2.returncode}: {r2.stderr[:200]}")
            return False, issues

        # 4. Write one synthetic findings file
        findings_dir = agents_out / "findings"
        findings_dir.mkdir(parents=True, exist_ok=True)
        (findings_dir / "smoke.yml").write_text(
            "agent: smoke\nfindings: []\n",
            encoding="utf-8",
        )

        # 5. consolidate_findings
        #
        # The consolidator injects `/review`'s upstream pre-condition
        # (`check_upstream_gate`): with no admissible `/code-quality` audit for the
        # slug, the verdict is BLOCKER and the process exits 1. The chain this
        # smoke exercises is detect_domain → spawn_reviewers → consolidate, so the
        # upstream context is declared here — the same way a real `/review` finds
        # it after a green `/code-quality`.
        audits = findings_dir.parent.parent / "records" / "audits"
        audits.mkdir(parents=True, exist_ok=True)
        (audits / "smoke-code-quality-2026-01-01.md").write_text(
            "**Verdict:** PASS\n**Hard caps triggered:** _none_\n"
            "**Soft caps triggered:** _none_\n",
            encoding="utf-8",
        )

        report = tmp / "report.md"
        consolidate = review_skill / "scripts" / "consolidate_findings.py"
        r3 = subprocess.run(  # noqa: PLW1510
            [sys.executable, str(consolidate),
             "--findings-dir", str(findings_dir),
             "--output", str(report),
             "--slug", "smoke",
             "--edge-case-coverage-ratio", "1.0"],
            capture_output=True, text=True,
        )
        if r3.returncode != 0:
            issues.append(f"  consolidate_findings exit {r3.returncode}: {r3.stderr[:200]}")
            return False, issues

        if not report.exists():
            issues.append("  consolidated report not written")
            return False, issues

    return True, []


def main() -> int:
    try:
        ecosystem_dir = _find_ecosystem_dir()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    checks = [
        ("Python syntax", check_python_syntax),
        ("Shell hooks syntax", check_shell_syntax),
        ("settings.json validity", check_settings_json),
        ("Cross-references", check_xrefs),
        ("Cycle rules schema", check_cycle_rules),
        ("Phase numbering", check_phase_numbering),
        ("Skill map", check_skill_map),
        ("Squad map", check_squad_map),
        ("Mechanisms inventory", check_mechanisms_inventory),
        ("Durable knowledge root", check_wiki_migration),
        ("Skill frontmatter", check_skill_frontmatter),
        ("Smoke chain (detect_domain → spawn_reviewers → consolidate)", check_smoke_chain),
    ]

    print(f"=== E2E smoke test — ecosystem: {ecosystem_dir} ===\n")

    all_pass = True
    for name, check in checks:
        try:
            ok, issues = check(ecosystem_dir)
        except Exception as exc:  # noqa: BLE001
            ok, issues = False, [f"  exception: {exc}"]
        if ok:
            print(f"✓ {name}")
            # A passing check may still have something to say — a skipped
            # validator, a migration in progress. Printing only on failure meant
            # `check_xrefs.py not installed — skipping` had never once been seen.
            for note in issues[:5]:
                print(note)
            if len(issues) > 5:
                print(f"  ... and {len(issues) - 5} more")
        else:
            all_pass = False
            print(f"✗ {name}")
            for issue in issues[:5]:
                print(issue)
            if len(issues) > 5:
                print(f"  ... and {len(issues) - 5} more")

    print()
    if all_pass:
        print("=== ALL CHECKS PASSED ===")
        return 0
    print("=== SOME CHECKS FAILED ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())

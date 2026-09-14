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

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

from ecosystem_utils import find_ecosystem_dir

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import write_records_dir  # noqa: E402


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


class _NotRun:
    """Neither a pass nor a failure: the check could not look at its subject.

    Eight checks here delegate to a gate script, and skip when that script is not on
    disk. The skip is deliberate and stays — a consumer with a partial install must
    not fail over a gate it never installed. What changes is that the skip stops
    being spelled `True`, because `True` is what a check returns when it looked and
    found nothing wrong, and the two were printed with the same tick:

        ✓ Cross-references
          check_xrefs.py not installed — skipping

    Truthy on purpose. Every caller writes `if ok:`, and a falsy sentinel would turn
    every partial install red — trading a misleading tick for a broken gate, which is
    the worse of the two. `is NOT_RUN` is how a caller that cares tells them apart.
    """

    __slots__ = ()

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return "NOT_RUN"


#: Returned in place of `True` by a check whose gate script is absent.
NOT_RUN = _NotRun()


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
        return NOT_RUN, ["  check_xrefs.py not installed — skipping"]
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
        return NOT_RUN, ["  check_skill_map.py not installed — skipping"]
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


def check_readme_advisory_skills(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does README.md and HOW-TO-USE.md list only skills that exist on disk?

    Regression test for commit e5527e6, which deleted three skills but never
    updated the README. This gate ensures README and disk stay in sync.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_readme_advisory_skills.py"
    if not checker.exists():
        return NOT_RUN, ["  check_readme_advisory_skills.py not installed — skipping"]
    # The `try` used to sit BELOW this call and wrap only the two lines that read
    # `result.returncode` and `result.stdout` — neither of which can raise. It was a
    # guard that could not fire, and its handler referenced `result.returncode`, which
    # is what gives away that the invocation was meant to be inside it (kit#59).
    try:
        result = subprocess.run(
            [sys.executable, str(checker), "--root", str(ecosystem_dir)],
            capture_output=True, text=True, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # Narrow on purpose: this is "the checker could not be run", which is an
        # inability to measure and must not be reported as a passing measurement.
        return False, [f"  check_readme_advisory_skills.py could not be run: {exc}"]

    if result.returncode == 0:
        return True, []
    return False, [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


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
        return NOT_RUN, ["  check_squad_map.py not installed — skipping"]
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


def check_verdict_bands(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does every declared verdict say which band it is in?

    Sibling of `check_orphan_verdicts`: that one asks whether anything can EMIT a
    verdict, this one whether anything knows what it MEANS for the flow.

    Measured 2026-09-08, before `rules/verdict-bands.txt` existed: 23 of 47 verdicts
    were classified nowhere, and `check_phase_drift` fell back to not-clean for every
    one of them — so its out-of-order check switched itself off for half the
    vocabulary, including three success verdicts, with nothing in the output to
    notice.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_verdict_bands.py"
    if not checker.exists():
        return NOT_RUN, ["  check_verdict_bands.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), "--root", str(ecosystem_dir), "--json"],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, [f"  check_verdict_bands.py produced no usable JSON "
                       f"(exit {result.returncode})"]
    coverage = payload.get("coverage")
    if coverage == "unreadable":
        return False, [f"  rules/verdict-bands.txt could not be read: "
                       f"{payload.get('detail', 'no detail')}"]
    rows = payload.get("unclassified", []) + payload.get("blocking_unclassified", [])
    if rows:
        return False, [f"  {v} is declared and names no band" for v in rows]
    return True, []


def check_data_root(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Is anything still outside `<project>/.squad/`?

    The empirical half of the write-root guarantee: containment proves no MODULE can
    spell another root, and this proves no DATA is sitting in one. The kit's own
    repository is checked like any other, because a rule the kit does not follow is a
    rule its consumers read as optional.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_data_root import check_project

    project = ecosystem_dir.parent if ecosystem_dir.name == ".claude" else ecosystem_dir
    stale = [r for r in check_project(project) if r.state in ("UNMIGRATED", "SPLIT")]
    if not stale:
        return True, []
    return False, [f"{r.state} {r.relative} ({r.files} file(s)) — {r.detail}"
                   for r in stale]


def check_write_containment(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Can any module outside the owner spell a data root?

    The structural half of the guarantee that everything this system writes lands
    under `<project>/.squad/`. If no other module can name a root, every path a writer
    builds came from `squad/paths.py`, and that module produces one root.

    Running it HERE matters: the scan is what makes the guarantee re-runnable, and a
    guarantee nobody re-runs decays into a sentence in a rule.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_write_containment import scan

    findings = scan(ecosystem_dir)
    if not findings:
        return True, []
    return False, [f"{f['file']}:{f['line']}  {f['literal']}" for f in findings[:10]]


def check_prose_write_paths(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does executable prose instruct a write outside `<project>/.squad/`?

    The third half of the same guarantee, and the one neither sibling can see. The
    structural scan reads code and strips prose; the runtime scan watches what the
    mechanisms produce. Neither watches a `SKILL.md`, and an agent following
    `Persist to records/brainstorms/{date}-session.md` creates a legacy root without
    importing the owner or running a mechanism.

    Measured 2026-09-10, when a live session did exactly that: 164 legacy-root
    instructions across 49 files.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_prose_write_paths import scan

    findings = scan(ecosystem_dir)
    if not findings:
        return True, []
    return False, [f"{f['file']}:{f['line']}  {f['path']}" for f in findings[:10]]


def check_emitted_verdicts(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does a skill instruct a verdict its cycle does not declare?

    `check_orphan_verdicts` asks the other direction. This one matters because the
    failure is silent in the worst way: `cycle_events.py` refuses the emission, so the
    phase records NOTHING, and an unrecorded phase is indistinguishable from one nobody
    ran — the board draws it as underived and a watchdog restarts it.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_emitted_verdicts import scan

    findings = scan(ecosystem_dir)
    if not findings:
        return True, []
    return False, [f"{f['file']}:{f['line']}  --verdict {f['verdict']}  ({f['reason']})"
                   for f in findings[:10]]


def check_contribution_conventions(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Do the recent commits follow the conventions this project declares?

    Runs HERE because a convention nobody checks is a preference. This repository's own
    `CONTRIBUTING.md` told contributors to add a co-authorship trailer while zero of the
    last 200 commits carried one — the document and the practice disagreed for long
    enough that nobody noticed.

    Scoped to the last 40 commits: the whole history predates the conventions, and a
    gate that fails on work done before the rule existed is a gate people disable.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_contribution_conventions import check

    report = check(ecosystem_dir, "-40")
    if report.unmeasured_because:
        return False, [f"not measured: {report.unmeasured_because}"]
    detail = [f"{report.commits_checked} commit(s) against {report.conventions.source}"]
    if not report.findings:
        return True, detail
    return False, detail + [f"{f.sha} {f.code}" for f in report.findings[:8]]


def check_chain_preconditions(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Could a chain started in THIS tree reach RELEASE?

    Reported here rather than left to the operator to remember, because the failure it
    catches is invisible until the end: a consumer ran the loop for hours and produced
    85 items, 13 plans scoring 89-100 structurally, and zero implemented — every plan
    INVALID on one unconfigured file that was readable in milliseconds beforehand.

    In the KIT's own checkout the answer is usually "not measured": the kit is not a
    project with a backlog, and reporting that as a failure would make its own
    verification red for a condition that does not apply to it. `cycle-maintenance.md`
    runs the same gate in a consumer, where the question is real.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_chain_preconditions import measure

    # A tree with no registry runs no chain, so the question does not apply to it. That
    # is the kit's own checkout: it ships the mechanisms and is not a project that uses
    # them. Reporting it as a failure would make the kit's verification red for a
    # condition it cannot have — and a gate that cries wolf about itself is one people
    # learn to skip, which is the opposite of what this one is for.
    if not (ecosystem_dir / "BACKLOG.md").is_file():
        return True, ["not applicable: no BACKLOG.md, so no chain runs here. "
                      "`cycle-maintenance.md` runs this gate in a consumer, where the "
                      "question is real"]

    rep = measure(ecosystem_dir)
    lines = [f"{c.mark} {c.name}: {c.detail}" for c in rep.checks]
    if rep.failed:
        return False, lines
    if rep.unmeasured:
        # Not a pass and not a failure: the kit's own tree has no backlog to run a
        # chain against, and calling that green would be the shape this whole gate
        # exists to refuse.
        return True, lines + ["not applicable here — the kit is not a project with a "
                              "chain; this gate is run by cycle-maintenance in a consumer"]
    return True, lines


def check_produced_files(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does anything the mechanisms PRODUCE land outside `<project>/.squad/`?

    The runtime half, and it exists because the structural half above cannot see a
    writer whose destination never passes through `squad.paths` — one taken from argv,
    joined onto the installed kit's directory, or handed down by a caller. Tracing
    those statically left 64 of 135 call sites UNKNOWN; running the mechanisms and
    looking at the disk answers it whatever the code path was.

    Reports its own coverage. A green run over four probes is worth four probes, and
    the count travels so nobody reads it as a sweep of everything.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_produced_files import check

    r = check(ecosystem_dir)
    if r.unmeasured_because:
        return False, [f"not measured: {r.unmeasured_because}"]
    detail = [f"{r.probes_run}/{r.probes_total} probe(s) exercised, "
              f"{len(r.produced)} file(s) produced, {len(r.exempted)} exempt"]
    if r.contained:
        return True, detail
    return False, detail + [f"escaped: {e['path']}" for e in r.escaped[:10]]


def check_panel_capability(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Can a DISCOVER/PLAN review panel be formed from what the project declared?

    Same argument as `check_merge_autonomy` at the other end of the chain: without
    this, every item is measured, planned, and then returned to the registry at a
    panel that was never formable — one `access` impediment per item, for a cause
    knowable before the first item was selected.

    An absent declaration is a VIOLATION rather than a skip: a project that never
    configured a panel cannot form one, and that is determinable from disk.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_panel_capability.py"
    if not checker.exists():
        return NOT_RUN, ["  check_panel_capability.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), "--json"],
        capture_output=True, text=True, cwd=str(ecosystem_dir),
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return NOT_RUN, [f"  check_panel_capability.py produced no usable JSON "
                         f"(exit {result.returncode})"]
    verdict = payload.get("result")
    if verdict in ("violated", "unchecked"):
        # Both are the repository's: a declaration that cannot form a panel on any
        # machine, or one that does not parse. Either fails everywhere, CI included.
        return False, ["  " + line for line in str(payload.get("message", "")).splitlines()]
    if verdict == "unreachable":
        # A declared binary is missing on THIS machine. The operator about to run the
        # chain needs to know; a CI runner checking the repository does not, and
        # failing there would go red for a repository with nothing wrong with it.
        return NOT_RUN, ["  a declared reviewer is not on PATH here — the declaration "
                         "is valid, this machine is short a tool"]
    return True, []


def check_merge_autonomy(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """May the system merge its own passing PRs to the trunk?

    `rules/autonomy-envelope.md` floor 2 makes that a PREMISE of running the kit rather
    than a capability a project may withhold. A remote requiring a human approving review
    does not narrow the envelope — it parks every item at an open PR at the end of its
    chain, and the queue drains into branches nobody merges.

    Asked here because this is the check that runs before anything else does. Discovering
    it per-item costs the run; discovering it here costs one API call.

    **A remote that cannot be reached is NOT_RUN, not a pass.** The gate reports its three
    states separately for exactly this reason, and collapsing UNCHECKED into success would
    make a partial install read as a verified premise.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / "check_merge_autonomy.py"
    if not checker.exists():
        return NOT_RUN, ["  check_merge_autonomy.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), "--json"],
        capture_output=True, text=True, cwd=str(ecosystem_dir),
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return NOT_RUN, [f"  check_merge_autonomy.py produced no usable JSON "
                         f"(exit {result.returncode}) — the premise was not tested"]
    verdict = payload.get("result")
    if verdict == "violated":
        return False, ["  " + line for line in str(payload.get("message", "")).splitlines()]
    if verdict == "unchecked":
        return NOT_RUN, ["  the merge premise was not tested (gh absent, unauthenticated, "
                         "or unparseable) — this is not a pass"]
    return True, []


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
        return NOT_RUN, ["  check_mechanisms_inventory.py not installed — skipping"]
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
        return NOT_RUN, ["  check_phase_numbering.py not installed — skipping"]
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


def _run_gate(ecosystem_dir: Path, gate: str, flag: str = "--repo") -> tuple[bool, list[str]]:
    """Run a gate that reports by exit code, and relay what it said.

    Both gates wired through this were, until 2026-09-02, executed by nothing at
    all: not the CI, not a hook, not `verify_ecosystem`. `check_orphan_verdicts`
    appeared exactly once outside its own tests — inside a COMMENT in
    `check_phase_emitters.py`. Measured that day, both passed clean, so nothing
    was hiding behind them. That is luck rather than protection: a gate nobody
    runs reports its first real failure to nobody.
    """
    checker = ecosystem_dir / "mechanisms" / "gates" / f"{gate}.py"
    if not checker.exists():
        return NOT_RUN, [f"  {gate}.py not installed — skipping"]
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(checker), flag, str(ecosystem_dir)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, []
    lines = (result.stdout + result.stderr).strip().splitlines()
    return False, [f"  {line}" for line in lines[:12]]


def check_orphan_verdicts(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Can anything actually emit each verdict a cycle rule declares?

    A verdict named in a rule and emitted by nothing is a state the chain can
    never enter, and a reader planning around it plans around a state that does
    not exist. `NEEDS_SPLIT` lived that way once — documented in SKILL.md's table
    and implemented nowhere — so briefs needing a split were squeezed into
    BLOCKED, which tells the reader to close gaps no rewrite can close.
    """
    return _run_gate(ecosystem_dir, "check_orphan_verdicts")


def check_phase_emitters(ecosystem_dir: Path) -> tuple[bool, list[str]]:
    """Does every declared phase have something that can emit its verdict?

    The other direction of the same question, and the one that catches a phase
    added to a chain with no mechanism behind it — silent by construction, and
    indistinguishable from a phase that ran and found nothing.
    """
    return _run_gate(ecosystem_dir, "check_phase_emitters")


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
        return NOT_RUN, ["  check_wiki_migration.py not installed — skipping"]
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
        audits = write_records_dir(findings_dir.parent.parent, "audits")
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


def main(argv: list[str] | None = None) -> int:
    """`--ecosystem-dir` names the tree to verify; without it, the tree is found.

    The flag is parsed rather than ignored, and an unrecognised argument is an
    error. Until 2026-09-05 this function took no arguments at all and read none:
    `verify_ecosystem.py --ecosystem-dir /somewhere/else` printed a full green report
    for the tree the finder happened to locate, headed with THAT tree's path. The
    header was the only signal, and it is easy to read as confirmation when the path
    is one you also expect. A verifier pointed at the wrong subject must say so.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    requested: str | None = None
    while argv:
        arg = argv.pop(0)
        if arg == "--ecosystem-dir":
            if not argv:
                print("ERROR: --ecosystem-dir needs a path", file=sys.stderr)
                return 2
            requested = argv.pop(0)
        elif arg.startswith("--ecosystem-dir="):
            requested = arg.split("=", 1)[1]
        else:
            print(f"ERROR: unrecognised argument {arg!r}", file=sys.stderr)
            return 2

    if requested is not None:
        ecosystem_dir = Path(requested).resolve()
        if not ecosystem_dir.is_dir():
            print(f"ERROR: {ecosystem_dir} is not a directory", file=sys.stderr)
            return 2
    else:
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
        ("README advisory skills", check_readme_advisory_skills),
        ("Mechanisms inventory", check_mechanisms_inventory),
        ("Merge autonomy (envelope floor 2)", check_merge_autonomy),
        ("Review panel can be formed", check_panel_capability),
        ("Write containment (.squad)", check_write_containment),
        ("Write paths in prose", check_prose_write_paths),
        ("Emitted verdicts declared", check_emitted_verdicts),
        ("Produced-file containment (runtime)", check_produced_files),
        ("Chain preconditions", check_chain_preconditions),
        ("Contribution conventions (last 40 commits)", check_contribution_conventions),
        ("Data root (.squad)", check_data_root),
        ("Verdict bands", check_verdict_bands),
        ("Orphan verdicts", check_orphan_verdicts),
        ("Phase emitters", check_phase_emitters),
        ("Durable knowledge root", check_wiki_migration),
        ("Skill frontmatter", check_skill_frontmatter),
        ("Smoke chain (detect_domain → spawn_reviewers → consolidate)", check_smoke_chain),
    ]

    print(f"=== E2E smoke test — ecosystem: {ecosystem_dir} ===\n")

    all_pass = True
    not_run = 0
    for name, check in checks:
        try:
            ok, issues = check(ecosystem_dir)
        except Exception as exc:  # noqa: BLE001
            ok, issues = False, [f"  exception: {exc}"]
        if ok is NOT_RUN:
            # Not a failure, and not a pass either. Drawing it as a tick told a
            # reader scanning the marks that a gate had checked something when the
            # gate was not on disk.
            not_run += 1
            print(f"⊘ {name}")
            for note in issues[:5]:
                print(note)
            if len(issues) > 5:
                print(f"  ... and {len(issues) - 5} more")
        elif ok:
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
    # Said on every run, pass or fail. A count that only appears when something is
    # wrong is a count nobody calibrates against, and the number that matters here
    # is how much of the suite did not execute.
    if not_run:
        print(f"({not_run} not run — the gate script was not installed)")
    if all_pass:
        print("=== ALL CHECKS PASSED ===")
        return 0
    print("=== SOME CHECKS FAILED ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())

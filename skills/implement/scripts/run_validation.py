#!/usr/bin/env python3
"""Final validation gate for /implement halt-loop.

Runs (and gates on):
  - the test suite of every language whose manifest is at the repo root:
    npm test (package.json), pytest/unittest (pyproject.toml/setup.py),
    go test (go.mod), cargo test (Cargo.toml) — see suite_runners.py
  - test_execution — FAILs when a manifest exists and NO suite executed. Before
    this gate, a non-npm repo skipped every executive check, landed on PARTIAL,
    and PARTIAL exits 0: the completion promise could be emitted with no test run.
  - npm run typecheck
  - npm run lint
  - npm run test:coverage (≥ 90% on changed files; 100% on critical paths)
  - Wiring summary — aggregates check_wiring.py per changed symbol
  - Code-quality (per ADR 0002): invokes /code-quality and gates on verdict.
    FAIL_HARD/INVALID → validation FAIL (exit 1).
    FAIL_SOFT/PASS_WITH_CAVEATS → WARN, not blocking.
    PASS → no impact.
    Override with --no-code-quality (escape for pre-code / CI without the skill).

Outputs JSON validation report. Saves a markdown summary at:
  .claude/records/reviews/{slug}-implement-validate-{date}.md

Exit codes:
  0 — All gates PASS or N/A
  1 — At least one gate FAIL (do NOT handoff to cycle-review)
  2 — Error (project root not found, slug missing, etc.)
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from datetime import datetime, timezone
from pathlib import Path
from pathlib import Path as _Path_bootstrap
from typing import Any

from coverage_gate import evaluate as coverage_evaluate
from diff_symbols import added_symbols_from_shas, shas_from_progress
from suite_runners import (
    check_go_tests,
    check_lint,
    check_python_tests,
    check_rust_tests,
    check_test_execution,
    check_typecheck,
    run_command,
    scope_suite_to_change,
)
from wiring_recheck import recheck_pillar_a

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
    write_records_dir,
)


def _find_project_root(start: Path) -> Path | None:
    """The project root above `start`, or None when there is none.

    It used to fall back to `start.resolve()`, which cannot fail and therefore cannot
    report failure. A run launched outside any project validated the caller's working
    directory instead, SKIPped every check it could not find a subject for, and exited
    0 — which SKILL.md reads as "proceed directly to Step 6". None is the honest
    answer, and `main` turns it into the exit 2 three documents already promise.
    """
    current = start.resolve()
    for _ in range(20):
        if (current / ".claude").exists() or (current / ".git").exists():
            return current
        if current == current.parent:
            break
        current = current.parent
    return None


def _has_package_json(project_root: Path) -> bool:
    return (project_root / "package.json").exists()


def _has_npm_script(project_root: Path, script: str) -> bool:
    pkg = project_root / "package.json"
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return False
    return script in data.get("scripts", {})


def _run_command(cmd: list[str], cwd: Path, timeout: int = 300) -> dict[str, Any]:
    """Kept as the in-module name; the single implementation lives in suite_runners."""
    return run_command(cmd, cwd, timeout)


def check_npm_test(project_root: Path) -> dict[str, Any]:
    if not _has_package_json(project_root):
        return {"name": "npm test", "status": "SKIP", "reason": "no package.json at the repo root — this check is for javascript"}
    if not _has_npm_script(project_root, "test"):
        return {"name": "npm test", "status": "SKIP", "reason": "no 'test' script in package.json"}
    result = _run_command(["npm", "test", "--silent"], project_root, timeout=600)
    if result.get("exit_code") == 0:
        return {"name": "npm test", "status": "PASS"}
    return {
        "name": "npm test",
        "status": "FAIL",
        "exit_code": result.get("exit_code"),
        "stderr_tail": result.get("stderr_tail", result.get("error", "")),
    }


def check_npm_typecheck(project_root: Path) -> dict[str, Any]:
    if not _has_package_json(project_root):
        return {"name": "npm run typecheck", "status": "SKIP", "reason": "no package.json at the repo root — this check is for javascript"}
    if not _has_npm_script(project_root, "typecheck"):
        # Fallback: run tsc --noEmit
        if (project_root / "tsconfig.json").exists():
            result = _run_command(["npx", "--no", "tsc", "--noEmit"], project_root, timeout=300)
            if result.get("exit_code") == 0:
                return {"name": "tsc --noEmit (fallback)", "status": "PASS"}
            return {
                "name": "tsc --noEmit (fallback)",
                "status": "FAIL",
                "exit_code": result.get("exit_code"),
                "stderr_tail": result.get("stderr_tail", "")[:500],
            }
        return {"name": "typecheck", "status": "SKIP", "reason": "no 'typecheck' script AND no tsconfig.json"}
    result = _run_command(["npm", "run", "typecheck", "--silent"], project_root, timeout=300)
    if result.get("exit_code") == 0:
        return {"name": "npm run typecheck", "status": "PASS"}
    return {
        "name": "npm run typecheck",
        "status": "FAIL",
        "exit_code": result.get("exit_code"),
        "stderr_tail": result.get("stderr_tail", result.get("error", "")),
    }


def check_npm_lint(project_root: Path) -> dict[str, Any]:
    if not _has_package_json(project_root):
        return {"name": "npm run lint", "status": "SKIP", "reason": "no package.json at the repo root — this check is for javascript"}
    if not _has_npm_script(project_root, "lint"):
        return {"name": "npm run lint", "status": "SKIP", "reason": "no 'lint' script in package.json"}
    result = _run_command(["npm", "run", "lint", "--silent"], project_root, timeout=180)
    if result.get("exit_code") == 0:
        return {"name": "npm run lint", "status": "PASS"}
    return {
        "name": "npm run lint",
        "status": "FAIL",
        "exit_code": result.get("exit_code"),
        "stderr_tail": result.get("stderr_tail", result.get("error", "")),
    }


def check_project_gates(project_root: Path) -> dict[str, Any]:
    """Run the REPOSITORY's own definition of ready, rather than a subset chosen here.

    B-051. This gate used to run `eslint` and `tsc --noEmit` directly and never the project's own
    `gates` script, so two definitions of "ready" drifted apart and only the weaker one was
    enforced. That is not hypothetical: `pnpm gates` was red from v0.54.0 through v0.62.0 — ten
    releases, none of which reached npm — while every slice in between passed this validation.
    Three of the files that made it red were written by slices that ran this script and passed.

    A missing `gates` script SKIPs with the reason. It must never PASS: reporting success for a
    standard that was never checked is the defect B-019 and B-048 record elsewhere in this
    repository, and this function exists because of it.

    The timeout is generous because `gates` runs the whole suite. A timeout is reported as FAIL
    with the reason rather than swallowed — a gate that times out has not passed.
    """
    if not _has_package_json(project_root):
        return {
            "name": "project gates",
            "status": "SKIP",
            "reason": "no package.json at the repo root — this check is for javascript",
        }
    if not _has_npm_script(project_root, "gates"):
        return {
            "name": "project gates",
            "status": "SKIP",
            "reason": "no 'gates' script in package.json — this project declares no composite gate, "
                      "so the checks above are all that ran",
        }
    result = _run_command(["npm", "run", "gates", "--silent"], project_root, timeout=1800)
    if result.get("exit_code") == 0:
        return {"name": "project gates", "status": "PASS"}
    return {
        "name": "project gates",
        "status": "FAIL",
        "exit_code": result.get("exit_code"),
        "stderr_tail": result.get("stderr_tail", result.get("error", "")),
    }


def check_coverage(project_root: Path) -> dict[str, Any]:
    """Run the coverage command when there is one, then READ the report.

    The verdict lives in coverage_gate.py; this function only decides whether a
    coverage command exists and runs it. Before that split, the check returned
    PASS on the command's exit code and never opened a report — see that
    module's docstring.
    """
    command_ran = False
    command_failed = False
    if _has_package_json(project_root) and _has_npm_script(project_root, "test:coverage"):
        result = _run_command(["npm", "run", "test:coverage", "--silent"], project_root, timeout=600)
        command_ran = True
        command_failed = result.get("exit_code") != 0

    return coverage_evaluate(
        project_root, command_ran=command_ran, command_failed=command_failed
    )


def _read_progress(project_root: Path, slug: str) -> dict[str, Any] | None:
    path = _find_progress(project_root, slug)
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None


def wiring_summary(project_root: Path, slug: str) -> dict[str, Any]:
    """Re-verify wiring pillar (a) INDEPENDENTLY — never trust the progress file.

    The pillar (a) status is computed by deriving the public symbols actually added
    in the committed diffs (`diff_symbols`) and RE-RUNNING `check_wiring.py` on each
    (`wiring_recheck`). The `wiring` field the halt-loop wrote into the progress file
    is treated as a CLAIM to be audited, not as evidence: a task self-reporting
    `wiring.a == "pass"` while the recheck finds a real pillar (a) FAIL is flagged as
    fabricated evidence (Unbreakable Rule 3 — the skill must never fabricate wiring).
    """
    progress = _read_progress(project_root, slug)
    if progress is None:
        return {
            "name": "wiring_triad",
            "status": "SKIP",
            "reason": "no progress file found — implement may not have been invoked",
            "skip_kind": _checkpoint_skip_kind(project_root, slug),
        }

    tasks = progress.get("tasks", []) if isinstance(progress, dict) else progress
    if not isinstance(tasks, list):
        tasks = []

    # Self-reported claims (audited below, never trusted as the verdict source).
    self_reported_a_pass = sum(
        1 for t in tasks if isinstance(t, dict) and t.get("wiring", {}).get("a") == "pass"
    )

    # Independent verification: derive symbols from the real diff, re-run the checker.
    shas = shas_from_progress(progress) if isinstance(progress, dict) else []
    symbols = added_symbols_from_shas(project_root, shas)
    recheck = recheck_pillar_a(project_root, symbols)

    base = {
        "name": "wiring_triad",
        "total_tasks": len(tasks),
        "self_reported_pillar_a_pass": self_reported_a_pass,
        "verification": "independent_recheck",
        "symbols_derived": recheck.symbols_checked,
        "symbols_resolved": recheck.symbols_resolved,
        "pillar_a_fails": recheck.pillar_a_fails,
        "pillar_a_fail_symbols": list(recheck.fail_symbols),
    }

    if recheck.pillar_a_fails > 0:
        result = {**base, "status": "FAIL"}
        if self_reported_a_pass > 0:
            # The progress file claims pillar (a) passed, yet an independent recheck
            # found uncalled symbols. That gap IS the fabrication this gate exists to
            # catch — surface it loudly so it cannot be waved through as a flake.
            result["fabricated_wiring_evidence"] = True
            result["reason"] = (
                f"Progress self-reports {self_reported_a_pass} task(s) with pillar (a) "
                f"pass, but independent recheck found {recheck.pillar_a_fails} uncalled "
                f"symbol(s): {', '.join(recheck.fail_symbols)}. Self-reported wiring "
                "evidence is not trustworthy."
            )
        else:
            result["reason"] = (
                f"Independent recheck found {recheck.pillar_a_fails} uncalled "
                f"symbol(s): {', '.join(recheck.fail_symbols)}"
            )
        return result

    if recheck.symbols_resolved == 0:
        # Nothing could be independently verified (pre-code phase, no SHAs, or
        # symbols not resolvable in the tree). Do NOT report PASS off self-claims —
        # report N/A honestly so the gate never launders an unverified claim.
        return {
            **base,
            "status": "N/A",
            "reason": (
                "No public symbols could be independently re-verified from the "
                "committed diffs (no SHAs, git unavailable, or derived names not "
                "found in the source tree). Pillar (a) NOT independently confirmed."
            ),
        }

    return {**base, "status": "PASS"}


def check_code_quality(project_root: Path, plan_slug: str, *, skip: bool = False) -> dict[str, Any]:
    """Invoke /code-quality and translate its verdict into a validation check.

    Per ADR 0002 (cq-gate-in-validate):
      - PASS              → check.status = PASS
      - PASS_WITH_CAVEATS → check.status = WARN (not blocking)
      - FAIL_SOFT         → check.status = WARN (not blocking)
      - FAIL_HARD         → check.status = FAIL (blocks IMPLEMENTATION_COMPLETE)
      - INVALID           → check.status = FAIL
      - script missing / parse error → SKIP (graceful — do NOT block when CQ is
        not installed)
    """
    if skip:
        return {
            "name": "code_quality",
            "status": "SKIP",
            "reason": "--no-code-quality flag set",
        }

    # cq_invoke is a sibling skill helper — import it from this skill's neighbor in
    # the `plan` repo, NOT from the consumer project_root (which may have neither).
    # Sibling layout: skills/implement/scripts/run_validation.py
    #              ↳ skills/code-quality/scripts/cq_invoke.py
    cq_invoke_dir = Path(__file__).resolve().parent.parent.parent / "code-quality" / "scripts"
    sys.path.insert(0, str(cq_invoke_dir))
    try:
        import cq_invoke  # type: ignore[import-not-found] — sibling skill, resolved by the sys.path line above
    except ImportError:
        return {
            "name": "code_quality",
            "status": "SKIP",
            "reason": "cq_invoke helper not importable",
        }
    finally:
        # Don't leak the helper dir into sys.path for the rest of the process.
        if sys.path and sys.path[0] == str(cq_invoke_dir):
            sys.path.pop(0)

    # invoke() may itself fail (CQ skill not installed, runtime error). Per ADR 0002
    # the CQ gate degrades to SKIP when unavailable — it must never crash validation.
    try:
        summary = cq_invoke.invoke(plan_slug, project_root)
    except Exception as exc:  # noqa: BLE001 — graceful-degrade boundary, reason is reported
        return {
            "name": "code_quality",
            "status": "SKIP",
            "reason": f"/code-quality invocation raised: {type(exc).__name__}: {exc}",
        }
    if summary is None:
        why, detail = cq_invoke.last_failure()
        # SKIP means "there was nothing to run". A gate that RAN and fell over is a
        # failure, and folding the two together is what let ORCHESTRATOR_CRASH (exit 2)
        # arrive here as SKIP, become PARTIAL and exit 0 — delivery proceeding on a
        # quality gate that crashed.
        ran_and_failed = why in (cq_invoke.Unavailable.CRASHED,
                                 cq_invoke.Unavailable.TIMEOUT,
                                 cq_invoke.Unavailable.UNPARSEABLE)
        return {
            "name": "code_quality",
            "status": "FAIL" if ran_and_failed else "SKIP",
            "reason": (f"/code-quality {why.value if why else 'unavailable'}: {detail}"
                       if why else "/code-quality script unavailable"),
        }

    verdict = summary.get("verdict", "UNKNOWN")
    score_cap = summary.get("score_cap", 100)
    hard_caps = summary.get("hard_caps_triggered", [])

    if verdict in ("FAIL_HARD", "INVALID"):
        status = "FAIL"
    elif verdict in ("FAIL_SOFT", "PASS_WITH_CAVEATS"):
        status = "WARN"
    elif verdict == "PASS":
        status = "PASS"
    else:
        status = "PARTIAL"

    return {
        "name": "code_quality",
        "status": status,
        "verdict": verdict,
        "score_cap": score_cap,
        "hard_caps_triggered": list(hard_caps),
        "languages_audited": summary.get("languages_audited", []),
    }


#: Every root a consumer may keep its audit trail under, most specific first.
#:
#: The kit ships `records/` in two layouts. A consumer measured on 2026-08-29 uses
#: neither: `platform` declares `<project>/.claude/knowledge-base/` canonical
#: in a rule of its own, written after an audit read the wrong directory and
#: reported a repository as having "0 implementations, 0 reviews, 0 releases" when
#: it had 6, 12 and 8. That repository holds **32 plans in `knowledge-base/plans/`
#: and zero in `records/plans/`**, so all nine `_find_plan` call sites answered
#: SKIP there — including an alignment gate installed minutes earlier, inert on
#: arrival for the third time in this family of defects.
#:
#: Widening the search cannot produce a false finding. It can only stop a false
#: SKIP, and a SKIP caused by looking in the wrong place is indistinguishable in
#: the report from one that legitimately had nothing to check.
_ARTEFACT_ROOTS = tuple(
    tuple(r.split("/")) for r in (f"{DATA_DIRNAME}/records", *LEGACY_RECORDS_ROOTS)
)


def _artefact_dirs(project_root: Path, kind: str):
    """Every directory a `kind` of artefact could live in, in precedence order."""
    for parts in _ARTEFACT_ROOTS:
        yield project_root.joinpath(*parts, kind)


def _find_artefact(project_root: Path, kind: str, filename: str) -> Path | None:
    for base in _artefact_dirs(project_root, kind):
        candidate = base / filename
        if candidate.exists():
            return candidate
    return None


def _artefact_write_dir(project_root: Path, kind: str) -> Path:
    """Where to WRITE a new artefact: the one write root, always.

    This used to pick the root the project already used, and the reasoning was sound
    for its time — *"an audit trail split across two directories is worse than none: a
    reader who checks the wrong one reports absence where evidence exists"*, written
    after exactly that happened across three repositories.

    Following the project answers it the wrong way round. A writer that follows keeps
    every project on its old root forever, so the split it avoids is replaced by a
    migration that never happens. Writers go to `<project>/.squad/`; READERS still fall
    back, which is what keeps an unmigrated consumer working, and
    `check_wiki_migration.py` reports the trail that has not moved.
    """
    return write_records_dir(project_root, kind)


def _find_plan(project_root: Path, slug: str) -> Path | None:
    """Locate the plan file in whichever layout this consumer keeps."""
    return _find_artefact(project_root, "plans", f"{slug}-plan.md")


def _find_progress(project_root: Path, slug: str) -> Path | None:
    """The checkpoint, in either layout — the companion `_find_plan` always had and this did not.

    Three call sites hardcoded `.claude/records/implementations/` while `_find_plan`,
    written directly above them, already handled both. `rules/records-location.md` makes
    the standalone layout (`<repo>/records/`) canonical for the kit's own repository —
    which is where the kit dogfoods itself. There, all three answered SKIP: `_read_progress`
    returned None, and the schema and checkpoint-consistency gates reported
    "no progress checkpoint — implement may not have run" for a checkpoint sitting on disk.

    A gate that reports SKIP because it looked in the wrong directory is indistinguishable in
    the report from one that legitimately had nothing to check, which is why this survived.
    """
    for base in _artefact_dirs(project_root, "implementations"):
        candidate = base / f".progress-{slug}.json"
        if candidate.exists():
            return candidate
    return None


def check_implementation_log(project_root: Path, slug: str) -> dict[str, Any]:
    """`records/implementations/{slug}-implementation.md` exists and carries something.

    `rules/cycle-implement.md § Output` declares this file a deliverable of the cycle. Nothing
    read it. Measured in a consumer on 2026-08-28: six logs for eight completed slugs, and the
    log for one of them opens by recording that `/review` had to ask for it, that the same gap
    had appeared one item earlier, and — in those words — that it would not recur. It recurred
    twice more.

    FAIL rather than SKIP when absent, and the distinction is the whole gate. SKIP is what a
    check says when it had nothing to look at; here the cycle declares there is something, so
    absence is the finding rather than the reason to stay quiet. This is the shape the
    `deps-audit` gate took on 2026-08-26, for the same reason: a gate believed to be automatic
    is one nobody runs, and a deliverable nobody checks is one that goes missing three times
    while everyone believes the process covers it.

    Emptiness counts as absence. A `touch` satisfies the letter and defeats the reason — the
    log carries what a diff cannot: what was measured, what lied, and what was rejected.
    """
    # No plan for this slug means the cycle never ran, so there is no log to be missing. That is a
    # genuine SKIP — the one shape of "nothing to check" this gate accepts, and it is why the
    # pre-code-phase path stays quiet rather than being loosened for it.
    if _find_plan(project_root, slug) is None:
        return {"name": "implementation_log", "status": "SKIP",
                "reason": f"no plan for {slug} — implement did not run"}

    for base in _artefact_dirs(project_root, "implementations"):
        candidate = base / f"{slug}-implementation.md"
        if candidate.exists():
            try:
                body = candidate.read_text(encoding="utf-8")
            except OSError as e:
                return {"name": "implementation_log", "status": "FAIL",
                        "reason": f"{candidate} exists but could not be read: {e}"}
            if not body.strip():
                return {"name": "implementation_log", "status": "FAIL",
                        "reason": f"{candidate} is empty — a touched file is not a log"}
            return {"name": "implementation_log", "status": "PASS",
                    "detail": str(candidate.relative_to(project_root))}
    return {
        "name": "implementation_log",
        "status": "FAIL",
        "reason": (
            f"no records/implementations/{slug}-implementation.md — "
            "cycle-implement declares it a deliverable, and it has gone missing three times"
        ),
    }


def check_alignment_gate(project_root: Path, slug: str) -> dict[str, Any]:
    """The item this slug implements reached 90% shared understanding, and a human said so.

    `skills/_kit-rules/alignment-threshold.md` says an item below the threshold is not built, and
    `cycle-implement.md § Pre-conditions` repeats it. Both were prose: nothing in this
    suite read `records/alignment/`, so the rule held exactly as long as somebody
    remembered it — the same shape as the implementation log above, which went missing
    three times while everyone believed the process covered it.

    This is the LAST line, not the first. `plan-confidence` caps an unaligned plan at 49
    and `cycle-plan` requires >= 70 to enter this cycle, so by the time this runs the code
    already exists. It fires when somebody reached `/implement` without passing through
    that gate — which is precisely the path a rule written only in prose leaves open.

    FAIL rather than SKIP when the brief is absent, for the reason `check_implementation_log`
    gives: SKIP is what a check says when it had nothing to look at, and here the cycle
    declares there is. The one genuine SKIP is no plan for the slug — then the cycle never
    ran and there is nothing to be missing.
    """
    plan = _find_plan(project_root, slug)
    if plan is None:
        return {"name": "alignment_gate", "status": "SKIP",
                "reason": f"no plan for {slug} — implement did not run"}

    scripts = Path(__file__).resolve().parents[2] / "plan-confidence" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from check_alignment_gate import check_alignment_gate as _gate
        report = _gate(plan)
    except Exception as exc:  # noqa: BLE001 — a gate that cannot run is not a gate that passed
        return {"name": "alignment_gate", "status": "FAIL",
                "reason": f"the alignment gate could not run ({exc.__class__.__name__}: {exc})"}

    if report.verdict == "ALIGNED":
        return {"name": "alignment_gate", "status": "PASS", "detail": report.reason}
    if not report.applies:
        # No backlog item and no brief: the boundary no check can decide. WARN, so it is
        # visible without failing every legitimate ad-hoc fix.
        return {"name": "alignment_gate", "status": "WARN", "reason": report.reason}
    return {"name": "alignment_gate", "status": "FAIL",
            "reason": f"{report.verdict}: {report.reason}"}


_PATTERNS_SKILL_RE = re.compile(r"\b([A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*-patterns)\b")


def check_patterns_advisory(project_root: Path, slug: str) -> dict[str, Any]:
    """SOFT advisory (ADR D3) — never FAIL.

    Surfaces plan-cited `*-patterns` skills that do NOT appear in the
    implementation's changed files, so the implementer can confirm the pattern
    was actually applied. The BINDING guarantee lives at the plan layer
    (`check_patterns_consumption` hard cap); this gate is visibility only, so a
    miss returns WARN (which `main` never folds into a FAIL) — verifying "the
    code applied the pattern" semantically is not mechanizable.
    """
    name = "patterns_consumption"
    plan = _find_plan(project_root, slug)
    if plan is None:
        return {"name": name, "status": "N/A", "reason": "plan not found"}
    cited = sorted(set(_PATTERNS_SKILL_RE.findall(
        plan.read_text(encoding="utf-8-sig", errors="ignore"))))
    if not cited:
        return {"name": name, "status": "N/A", "reason": "plan cites no *-patterns skill"}
    progress = _read_progress(project_root, slug)
    files: list[str] = []
    if progress:
        for task in progress.get("tasks", []):
            files.extend(task.get("files", []) or [])
    if not files:
        return {"name": name, "status": "N/A", "cited": cited,
                "reason": "no implementation files recorded yet — cannot verify consumption"}
    blob = ""
    for rel in files:
        fpath = project_root / rel
        if fpath.is_file():
            blob += fpath.read_text(encoding="utf-8-sig", errors="ignore")
    not_found = [c for c in cited if c not in blob]
    if not_found:
        return {"name": name, "status": "WARN", "cited": cited, "not_found": not_found,
                "reason": (f"plan cites {not_found} but it does not appear in the changed "
                           "implementation files — confirm the pattern was applied (advisory, non-blocking)")}
    return {"name": name, "status": "PASS", "cited": cited}


def check_progress_schema_gate(project_root: Path, slug: str) -> dict[str, Any]:
    """Fail-fast validation of the checkpoint itself, BEFORE the gates that read it.

    A malformed `.progress-{slug}.json` (missing `tasks` envelope, `task_id` instead
    of `id`, missing `phase`) makes every phase-scoped gate degrade silently. This
    gate turns that into a loud, early failure (Unbreakable Rule 8)."""
    # Falls back to the plugin path when neither layout holds a checkpoint, so the schema
    # check still reports "missing" against a concrete path rather than crashing on None.
    path = _find_progress(project_root, slug) or (
        _artefact_write_dir(project_root, "implementations") / f".progress-{slug}.json"
    )
    from check_progress_schema import check_progress_schema

    report = check_progress_schema(path)
    return {
        "name": "progress_schema",
        "status": report.status,
        "task_count": report.task_count,
        "findings": [{"severity": f.severity, "code": f.code, "message": f.message}
                     for f in report.findings],
    }


def check_checkpoint_consistency_gate(project_root: Path, slug: str) -> dict[str, Any]:
    """Cross-check the checkpoint against git in both directions: every committed
    task points at a real commit, and every plan task referenced by a real commit is
    recorded as committed. Catches a checkpoint that drifted out of sync with reality
    (e.g. a task finished + committed but the .progress update was skipped)."""
    path = _find_progress(project_root, slug)
    plan = _find_plan(project_root, slug)
    if path is None:
        return {"name": "checkpoint_consistency", "status": "SKIP",
                "reason": "no progress checkpoint — implement may not have run",
                "skip_kind": _checkpoint_skip_kind(project_root, slug)}
    if plan is None:
        return {"name": "checkpoint_consistency", "status": "SKIP",
                "reason": f"plan not found for slug '{slug}' — cannot map task ids"}

    import json as _json

    from check_checkpoint_consistency import (
        check_checkpoint_consistency,
        plan_task_ids_from_text,
    )

    try:
        progress = _json.loads(path.read_text(encoding="utf-8-sig"))
    except _json.JSONDecodeError:
        # The schema gate already reports malformed JSON loudly; don't double-fail.
        return {"name": "checkpoint_consistency", "status": "SKIP",
                "reason": "checkpoint is malformed JSON (see progress_schema gate)"}

    plan_ids = plan_task_ids_from_text(plan.read_text(encoding="utf-8-sig"))
    report = check_checkpoint_consistency(progress, project_root, plan_ids)
    return {
        "name": "checkpoint_consistency",
        "status": report.status,
        "committed_in_progress": report.committed_in_progress,
        "findings": [{"severity": f.severity, "code": f.code, "message": f.message}
                     for f in report.findings],
    }


def check_tdd_shape_gate(project_root: Path, slug: str) -> dict[str, Any]:
    """Re-assert the Step 2 pre-loop gate at the end of the run.

    `check_tdd_shape.py` was invoked from SKILL.md prose only. Nothing downstream
    ever asked whether it had run, so a halt-loop driven from a prose-only plan
    left no trace — the exact gap `rules/cycle-implement.md § Hard gates
    (pre-loop, at Step 2)` describes as blocking.
    """
    plan = _find_plan(project_root, slug)
    if plan is None:
        return {"name": "tdd_shape", "status": "SKIP",
                "reason": f"plan not found for slug '{slug}' — cannot audit TDD shapes"}
    from check_tdd_shape import check_tdd_shape

    report = check_tdd_shape(plan)
    if report.total_tasks == 0:
        # FAIL, not SKIP. The plan FILE exists — `_find_plan` returned it — so zero task
        # blocks is a fact about what this checker could read, not a fact about the plan.
        # As a SKIP it counted into `skips`, `overall` became PARTIAL, and PARTIAL exits
        # 0, so IMPLEMENTATION_COMPLETE could be emitted with the TDD shape never
        # verified. `rules/cycle-implement.md § Hard gates` calls this gate blocking.
        return {"name": "tdd_shape", "status": "FAIL",
                "reason": (f"{plan.name} parsed to zero `### T{{n}}.{{m}}` task blocks. "
                           f"The plan is on disk, so this is what the checker could read "
                           f"— not a plan that declares no tasks. A shape that could not "
                           f"be audited is not a shape that passed."),
                "findings": [{"severity": "HIGH", "code": "tdd_shape_unreadable",
                              "message": f"no task block parsed from {plan}"}]}
    without = [t.task_id for t in report.tasks if not t.has_executable_shape]
    return {
        "name": "tdd_shape",
        "status": "FAIL" if without else "PASS",
        "total_tasks": report.total_tasks,
        "tasks_with_shape": report.tasks_with_shape,
        "tasks_without_shape": without,
        "findings": [
            {"severity": "HIGH", "code": "tdd_shape_missing",
             "message": f"{tid}: no executable RED-test shape (assertion / GWT / test_fn) "
                        "— the halt-loop should have been BLOCKED at Step 2."}
            for tid in without
        ],
    }


def check_phase_review_gate(project_root: Path, slug: str) -> dict[str, Any]:
    """Did the Step 4.7 mini review actually run at every phase boundary it closed?"""
    plan = _find_plan(project_root, slug)
    if plan is None:
        return {"name": "phase_review", "status": "SKIP",
                "reason": f"plan not found for slug '{slug}' — cannot audit phase boundaries"}
    progress = _read_progress(project_root, slug)
    if progress is None:
        return {"name": "phase_review", "status": "SKIP",
                "reason": "no progress checkpoint — implement may not have run",
                "skip_kind": _checkpoint_skip_kind(project_root, slug)}
    from check_phase_review import check_phase_review

    review_dirs = [
        *_artefact_dirs(project_root, "mini-reviews"),
    ]
    # `repo_root` is what `_check_ordering` needs to compare the review's recorded head
    # against the phase's last commit. Both production call sites omitted it, so
    # `_is_ancestor` ran only in tests and the HIGH `retroactive_review` finding — a
    # review signed off before the code it reviews existed — could never be produced
    # outside the suite. The value was already in hand here.
    report = check_phase_review(plan, progress, slug, review_dirs, repo_root=project_root)
    return {
        "name": "phase_review",
        "status": report.status,
        "phases_declared": report.phases_declared,
        "phases_closed": report.phases_closed,
        "phases_reviewed": report.phases_reviewed,
        "findings": [{"severity": f.severity, "code": f.code, "message": f.message}
                     for f in report.findings],
    }


def _files_touched_by_this_change(project_root: Path, slug: str) -> list[str]:
    """The files this item's own commits wrote, or [] when that cannot be established.

    Empty is the honest answer when the progress file carries no SHAs — and `check_lint`
    reads it as "do not scope", reporting the whole failure rather than a guess at which
    part of it belongs here.
    """
    from check_acceptance_criteria import _changed_files

    progress = _read_progress(project_root, slug)
    shas = shas_from_progress(progress) if isinstance(progress, dict) else []
    if not shas:
        return []
    return _changed_files(project_root, shas)


def check_acceptance_criteria_gate(project_root: Path, slug: str) -> dict[str, Any]:
    """Enforce the plan's AC/DoD obligations that run_validation does not otherwise
    cover (file-size budget, CHANGELOG-updated) and surface the non-mechanizable
    ones, instead of trusting the LLM's self-ticked checkboxes (GAP 1+2)."""
    plan = _find_plan(project_root, slug)
    if plan is None:
        return {"name": "acceptance_criteria", "status": "SKIP",
                "reason": f"plan not found for slug '{slug}' — cannot audit criteria"}
    from check_acceptance_criteria import check_acceptance_criteria

    progress = _read_progress(project_root, slug)
    shas = shas_from_progress(progress) if isinstance(progress, dict) else []
    report = check_acceptance_criteria(plan, repo_root=project_root, shas=shas)
    return {
        "name": "acceptance_criteria",
        "status": report.status,
        "total_criteria": report.total_criteria,
        "by_category": report.by_category,
        "findings": [{"severity": f.severity, "code": f.code, "message": f.message}
                     for f in report.findings],
    }


def check_test_obligations_gate(project_root: Path, slug: str) -> dict[str, Any]:
    """Confirm declared concurrency/failure tests actually exist in the tree, instead
    of relying on a generic green test run that never exercised them (GAP 6)."""
    plan = _find_plan(project_root, slug)
    if plan is None:
        return {"name": "test_obligations", "status": "SKIP",
                "reason": f"plan not found for slug '{slug}' — cannot audit test obligations"}
    from check_test_obligations import check_test_obligations

    report = check_test_obligations(plan, repo_root=project_root)
    return {
        "name": "test_obligations",
        "status": report.status,
        "obligations": [{"kind": o.kind, "detail": o.detail} for o in report.obligations],
        "findings": [{"severity": f.severity, "code": f.code, "message": f.message}
                     for f in report.findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Final validation gate for /implement.")
    parser.add_argument("slug", help="Plan slug (matches .claude/records/implementations/{slug}-implementation.md)")
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--no-write-report", action="store_true", help="don't save a markdown report")
    parser.add_argument(
        "--no-code-quality",
        action="store_true",
        help="skip the /code-quality gate (per ADR 0002; escape hatch for pre-code phase)",
    )
    args = parser.parse_args()

    project_root = args.project_root if args.project_root else _find_project_root(Path.cwd())
    if project_root is None:
        print(f"UNCHECKED: no project root at or above {Path.cwd()} — no `.claude/` and "
              f"no `.git/` within 20 levels. Pass --project-root if that is deliberate.",
              file=sys.stderr)
        return 2

    # Every language whose suite the gate knows how to run. The npm check stays
    # first for report stability; test_execution consolidates all of them and is
    # what turns "nothing ran" into a FAIL instead of a silent PARTIAL.
    _emit_phase_start(project_root, cycle="implement", slug=args.slug)

    touched = _files_touched_by_this_change(project_root, args.slug)
    suite_checks = [
        scope_suite_to_change(check_npm_test(project_root), touched),
        scope_suite_to_change(check_python_tests(project_root), touched),
        scope_suite_to_change(check_go_tests(project_root), touched),
        scope_suite_to_change(check_rust_tests(project_root), touched),
    ]

    checks = [
        check_progress_schema_gate(project_root, args.slug),
        check_checkpoint_consistency_gate(project_root, args.slug),
        *suite_checks,
        check_test_execution(project_root, suite_checks),
        check_npm_typecheck(project_root),
        *check_typecheck(project_root),
        check_npm_lint(project_root),
        *check_lint(project_root, touched),
        check_project_gates(project_root),
        check_coverage(project_root),
        wiring_summary(project_root, args.slug),
        check_tdd_shape_gate(project_root, args.slug),
        check_phase_review_gate(project_root, args.slug),
        check_acceptance_criteria_gate(project_root, args.slug),
        check_test_obligations_gate(project_root, args.slug),
        check_alignment_gate(project_root, args.slug),
        check_implementation_log(project_root, args.slug),
        check_patterns_advisory(project_root, args.slug),
        check_code_quality(project_root, args.slug, skip=args.no_code_quality),
    ]

    # A SKIP that names no kind is `not_applicable`: the checks that KNOW they are
    # missing a precondition say so, and silence means the check simply has no subject
    # here. Defaulting the other way would turn every honest SKIP into a failure on the
    # day this landed.
    for check in checks:
        if check.get("status") == "SKIP":
            check.setdefault("skip_kind", SKIP_NOT_APPLICABLE)

    fails = [c for c in checks if c.get("status") == "FAIL"]
    #: A precondition that is absent is not a check that does not apply. Counted with
    #: the failures, because "the work did not happen" and "this gate has no subject
    #: here" reached the same verdict and the same exit code — and the first one is the
    #: thing this gate exists to catch.
    blocked = [c for c in checks
               if c.get("status") == "SKIP"
               and c.get("skip_kind") == SKIP_PRECONDITION_MISSING]
    # Every SKIP, for the summary buckets — `test_summary_buckets_account_for_every_check`
    # asserts they sum to the total, and pulling the blocked ones out of this list made
    # two checks vanish from the arithmetic. The distinction belongs to the VERDICT, not
    # to the census.
    skips = [c for c in checks if c.get("status") == "SKIP"]
    overall = "FAIL" if (fails or blocked) else ("PARTIAL" if skips else "PASS")

    report: dict[str, Any] = {
        "slug": args.slug,
        "project_root": str(project_root),
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        #: Named separately from `fails` so a reader can tell a gate that FAILED from a
        #: gate that could not run at all.
        "preconditions_missing": [c["name"] for c in blocked],
        "checks": checks,
        "summary": {
            # Every status bucket is counted so pass+fail+skip+warn+partial+n_a == total.
            "total": len(checks),
            "pass": sum(1 for c in checks if c.get("status") == "PASS"),
            "fail": len(fails),
            "skip": len(skips),
            "warn": sum(1 for c in checks if c.get("status") == "WARN"),
            "partial": sum(1 for c in checks if c.get("status") == "PARTIAL"),
            "n_a": sum(1 for c in checks if c.get("status") == "N/A"),
        },
    }

    print(json.dumps(report, indent=2))

    if not args.no_write_report:
        review_dir = _artefact_write_dir(project_root, "reviews")
        review_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        md_path = review_dir / f"{args.slug}-implement-validate-{today}.md"
        md = f"""# Implementation Validation: {args.slug}

**Date:** {today}
**Overall:** {overall}
**Total checks:** {len(checks)} (PASS: {report['summary']['pass']}, FAIL: {len(fails)}, SKIP: {len(skips)})

## Checks

"""
        for c in checks:
            md += f"### {c.get('name', 'unknown')} — `{c.get('status')}`\n\n"
            if "reason" in c:
                md += f"- Reason: {c['reason']}\n"
            if c.get("name") == "wiring_triad" and c.get("status") != "SKIP":
                md += f"- Total tasks: {c.get('total_tasks')}\n"
                md += "- Verification: independent recheck of `check_wiring.py`\n"
                md += f"- Symbols derived from diff: {c.get('symbols_derived')}\n"
                md += f"- Symbols independently resolved: {c.get('symbols_resolved')}\n"
                md += f"- Pillar (a) fails (uncalled symbols): {c.get('pillar_a_fails')}\n"
                if c.get("pillar_a_fail_symbols"):
                    md += f"- Failing symbols: {', '.join(c['pillar_a_fail_symbols'])}\n"
                md += f"- Self-reported pillar (a) pass (claim, audited): {c.get('self_reported_pillar_a_pass')}\n"
                if c.get("fabricated_wiring_evidence"):
                    md += "- ⚠️ **Fabricated wiring evidence detected** — self-report contradicts recheck\n"
            for finding in c.get("findings", []):
                md += f"- [{finding['severity']}] {finding['code']}: {finding['message']}\n"
            if c.get("status") == "FAIL" and "stderr_tail" in c:
                md += f"\n```\n{c['stderr_tail'][:500]}\n```\n"
            md += "\n"
        md += """## Handoff decision

"""
        if overall == "PASS":
            md += "Implementation PASSes all gates. Ready for `cycle-review` (when built).\n"
        elif overall == "FAIL":
            md += "Implementation FAILS at least one gate. Loop back to /implement to address.\n"
        else:
            md += "Implementation PARTIAL — some gates were SKIPped because pre-conditions absent (e.g., package.json). Decide whether SKIPs are acceptable for this phase.\n"
        md_path.write_text(md, encoding="utf-8")
        print(f"\nReport saved: {md_path}", file=sys.stderr)

    # `PARTIAL` is the interesting one to have in the stream: it exits 0, so a
    # reader of exit codes alone cannot tell a full pass from a run where gates
    # SKIPped for want of a manifest.
    _emit_phase_end(project_root, cycle="implement", slug=args.slug, verdict=overall)

    return 0 if overall in ("PASS", "PARTIAL") else 1


#: Why a check did not run. The two are opposite facts and were one status.
#:
#: `not_applicable` — the check has no subject here: `npm test` in a Go repository.
#: `precondition_missing` — the check has a subject and the thing it reads is absent,
#: which is a fact about the WORK rather than about the repository.
#:
#: Measured 2026-09-21 on a repository holding a plan and no checkpoint: 16 SKIPs,
#: `overall_status: PARTIAL`, exit 0 — "proceed" — while four of those SKIPs said, in
#: their own reason strings, that `/implement` may not have run. The kit had already
#: argued the correct shape twice, in the comments of `tdd_shape` and `test_execution`,
#: and fixed it one check at a time. This is the general form.
SKIP_NOT_APPLICABLE = "not_applicable"
SKIP_PRECONDITION_MISSING = "precondition_missing"


def _checkpoint_skip_kind(project_root: Path, slug: str) -> str:
    """Is a missing checkpoint a fact about the WORK, or about the phase?

    Only when a plan exists for this slug. Without one, `/implement` was never supposed
    to run and its absent checkpoint is the honest state of a pre-code tree — the first
    cut ignored that and turned `test_pre_code_phase_all_skip` red, which was the test
    saying so.

    With a plan on disk the reading flips: the work was planned, the gate that closes it
    is running, and the record it reads is not there. That is the fact the four
    checkpoint-dependent checks were reporting in prose while returning SKIP, and SKIP
    exits 0.
    """
    return (SKIP_PRECONDITION_MISSING if _find_plan(project_root, slug) is not None
            else SKIP_NOT_APPLICABLE)


def _emit_phase_start(project_root, *, cycle: str, slug: str) -> None:
    """Record that the phase began, so the pair can be timed.

    Emitted before the gates run: a validation that dies mid-way leaves a start with no
    end, which is what an interrupted phase is. Recording it only on success would draw
    the stream as though nothing had been attempted, and 37 ends against 1 start is the
    state that made WIP incomputable on one consumer.
    """
    tooling = Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    try:
        from cycle_events import emit_phase_start
    except ImportError as error:
        print(f"cycle-events: emitter unavailable ({error})", file=sys.stderr)
        return
    emit_phase_start(project_root, cycle=cycle, slug=slug)


def _emit_phase_end(project_root, *, cycle: str, slug: str, verdict) -> None:
    """Record the phase transition; never let bookkeeping fail the gate.

    `scripts/` resolves against THIS FILE, not the validated project: in a plugin
    install the kit lives under `.claude/` while the project is elsewhere.
    `ImportError` is caught alone — a bare `except Exception` would swallow a
    real emitter bug into a silence indistinguishable from a phase that never
    ran, which is the defect the stream exists to remove.
    """
    tooling = Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    try:
        from cycle_events import emit_phase_end
    except ImportError as error:
        print(f"cycle-events: emitter unavailable ({error})", file=sys.stderr)
        return
    emit_phase_end(project_root, cycle=cycle, slug=slug, verdict=verdict)


if __name__ == "__main__":
    sys.exit(main())

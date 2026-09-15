"""Tests for run_validation.py — verifies graceful pre-code SKIP + integration."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "run_validation.py"

from run_validation import (  # noqa: E402
    wiring_summary,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo: Path, rel: str, content: str, msg: str = "feat") -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD").strip()


def _write_progress(project_root: Path, tasks: list[dict], slug: str = "wsg") -> None:
    impl_dir = project_root / ".claude" / "records" / "implementations"
    impl_dir.mkdir(parents=True, exist_ok=True)
    (impl_dir / f".progress-{slug}.json").write_text(
        json.dumps({"slug": slug, "tasks": tasks}), encoding="utf-8"
    )


def test_wiring_summary_detects_fabricated_evidence(tmp_path: Path) -> None:
    """GAP 3: self-reported pillar (a) pass + an actually-uncalled symbol = fabrication.

    The final gate must NOT trust the progress file: it re-derives symbols from the
    committed diff and re-runs check_wiring. A dishonest `wiring.a=pass` over an
    orphan symbol is caught as fabricated evidence, status FAIL.
    """
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "src/orphan.py", "def orphan_fn(x):\n    return x\n")
    _write_progress(repo, [
        {"id": "T1.1", "phase": "1", "commit_sha": sha, "wiring": {"a": "pass"}},
    ])
    result = wiring_summary(repo, "wsg")
    assert result["status"] == "FAIL"
    assert result["fabricated_wiring_evidence"] is True
    assert "orphan_fn" in result["pillar_a_fail_symbols"]


def test_wiring_summary_passes_when_recheck_confirms_caller(tmp_path: Path) -> None:
    """A genuinely-wired symbol (real production caller) passes the independent recheck."""
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "src/order.py", "def compute_total(x):\n    return x\n")
    _commit(repo, "src/app.py", "from order import compute_total\nprint(compute_total(1))\n")
    _write_progress(repo, [
        {"id": "T1.1", "phase": "1", "commit_sha": sha, "wiring": {"a": "pass"}},
    ])
    result = wiring_summary(repo, "wsg")
    assert result["status"] == "PASS"
    assert result["pillar_a_fails"] == 0


def test_wiring_summary_na_when_nothing_verifiable(tmp_path: Path) -> None:
    """No SHAs / no git → cannot re-verify → N/A, NOT a PASS laundered from a claim."""
    _write_progress(tmp_path, [
        {"id": "T1.1", "phase": "1", "wiring": {"a": "pass"}},  # no commit_sha
    ])
    result = wiring_summary(tmp_path, "wsg")
    assert result["status"] == "N/A"
    assert result["symbols_resolved"] == 0
    # The claim is preserved for audit but did NOT produce a PASS.
    assert result["self_reported_pillar_a_pass"] == 1


def _run_validation(slug: str, project_root: Path) -> tuple[int, dict]:
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(SCRIPT), slug, "--project-root", str(project_root), "--no-write-report"],
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw": result.stdout, "stderr": result.stderr}
    return result.returncode, data


def test_pre_code_phase_all_skip(fake_project: Path) -> None:
    """No package.json → all npm-based gates SKIP gracefully; overall=PARTIAL."""
    rc, data = _run_validation("test-slug", fake_project)
    assert rc == 0  # PARTIAL is exit 0 (no failures, just skips)
    assert data["overall_status"] == "PARTIAL"
    skips = [c for c in data["checks"] if c.get("status") == "SKIP"]
    assert len(skips) >= 4


def test_with_package_json_and_passing_scripts(fake_project: Path) -> None:
    """Package.json with test/typecheck/lint that exit 0 → all PASS (or some SKIP)."""
    (fake_project / "package.json").write_text(
        json.dumps({
            "name": "fake",
            "scripts": {
                "test": "true",  # exit 0
                "typecheck": "true",
                "lint": "true",
            }
        }),
        encoding="utf-8",
    )
    _rc, data = _run_validation("test-slug", fake_project)
    # No FAILs expected; PASS or SKIP only
    fails = [c for c in data["checks"] if c.get("status") == "FAIL"]
    assert len(fails) == 0


def test_with_failing_test_script(fake_project: Path) -> None:
    """Package.json with `test` that exits 1 → npm test FAIL → overall=FAIL."""
    (fake_project / "package.json").write_text(
        json.dumps({
            "name": "fake",
            "scripts": {
                "test": "false",  # exit 1
            }
        }),
        encoding="utf-8",
    )
    rc, data = _run_validation("test-slug", fake_project)
    assert rc == 1
    assert data["overall_status"] == "FAIL"
    test_check = next(c for c in data["checks"] if c.get("name") == "npm test")
    assert test_check["status"] == "FAIL"


def test_new_gates_are_wired_into_validation(fake_project: Path) -> None:
    """GAP 1+2 / GAP 6: the acceptance-criteria and test-obligation gates must run as
    part of the final validation, not exist as orphan scripts."""
    plan_dir = fake_project / ".claude" / "records" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "test-slug-plan.md").write_text(
        "# Plan\n\n### T1.1 — X\n\n#### Acceptance Criteria\n"
        "- [ ] Backward compatibility preserved across public API\n",
        encoding="utf-8",
    )
    _, data = _run_validation("test-slug", fake_project)
    names = [c["name"] for c in data["checks"]]
    assert "acceptance_criteria" in names
    assert "test_obligations" in names
    ac = next(c for c in data["checks"] if c["name"] == "acceptance_criteria")
    assert ac["status"] != "SKIP"  # plan found → criteria actually audited


def test_checkpoint_consistency_gate_catches_unrecorded_task(tmp_path: Path) -> None:
    """End-to-end: a task committed in git but missing from the checkpoint fails the
    checkpoint_consistency gate inside run_validation."""
    repo = _init_repo(tmp_path)
    sha1 = _commit(repo, "src/a.py", "x = 1\n", "feat: a\n\nT1.1: foo")
    _commit(repo, "src/b.py", "y = 2\n", "feat: b\n\nT1.2: bar")  # committed, but not in checkpoint
    plan_dir = repo / ".claude" / "records" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "ck-plan.md").write_text(
        "## Phase 1\n### T1.1 — Foo\nbody\n### T1.2 — Bar\nbody\n", encoding="utf-8")
    _write_progress(repo, [
        {"id": "T1.1", "phase": "1", "status": "committed", "commit_sha": sha1},
    ], slug="ck")

    rc, data = _run_validation("ck", repo)
    cc = next(c for c in data["checks"] if c["name"] == "checkpoint_consistency")
    assert cc["status"] == "FAIL"
    assert "task_committed_in_git_not_in_progress" in [f["code"] for f in cc["findings"]]
    assert rc == 1


def test_malformed_checkpoint_fails_validation(fake_project: Path) -> None:
    """The progress-schema gate must catch a malformed checkpoint (the prompt's old
    bare-object shape) and FAIL the whole validation, not let gates degrade silently."""
    impl = fake_project / ".claude" / "records" / "implementations"
    impl.mkdir(parents=True, exist_ok=True)
    (impl / ".progress-test-slug.json").write_text(
        json.dumps({"task_id": "T1.1", "status": "committed"}),  # no 'tasks' envelope
        encoding="utf-8",
    )
    rc, data = _run_validation("test-slug", fake_project)
    ps = next(c for c in data["checks"] if c["name"] == "progress_schema")
    assert ps["status"] == "FAIL"
    assert "progress_missing_tasks" in [f["code"] for f in ps["findings"]]
    assert rc == 1
    assert data["overall_status"] == "FAIL"


def test_summary_buckets_account_for_every_check(fake_project: Path) -> None:
    """Regression: pass+fail+skip+warn+partial+n_a must equal total — WARN and
    PARTIAL statuses (from the code-quality gate) used to be dropped from the summary."""
    _, data = _run_validation("test-slug", fake_project)
    s = data["summary"]
    for bucket in ("pass", "fail", "skip", "warn", "partial", "n_a"):
        assert bucket in s, f"summary missing bucket '{bucket}'"
    assert s["pass"] + s["fail"] + s["skip"] + s["warn"] + s["partial"] + s["n_a"] == s["total"]


# T2.1 — patterns-consumption advisory (patterns-consumption-gate-plan, ADR D3)

from run_validation import check_patterns_advisory  # noqa: E402


def test_patterns_advisory_never_fails(tmp_path: Path) -> None:
    plans = tmp_path / ".claude" / "records" / "plans"
    plans.mkdir(parents=True)
    (plans / "demo-plan.md").write_text(
        "# Plan: demo\n## Prior Art & Related Work\n- Patterns skills: `foo-patterns` Pattern P1.\n"
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "impl.py").write_text("print('no skill mention here')\n")
    impl = tmp_path / ".claude" / "records" / "implementations"
    impl.mkdir(parents=True)
    (impl / ".progress-demo.json").write_text(json.dumps({
        "slug": "demo",
        "tasks": [{"id": "T1.1", "phase": "1", "status": "committed", "files": ["src/impl.py"]}],
    }))
    r = check_patterns_advisory(tmp_path, "demo")
    assert r["status"] == "WARN"           # advisory, surfaced
    assert r["status"] != "FAIL"           # never blocks handoff (ADR D3)
    assert "foo-patterns" in r["not_found"]


def test_patterns_advisory_absent_when_no_citation(tmp_path: Path) -> None:
    plans = tmp_path / ".claude" / "records" / "plans"
    plans.mkdir(parents=True)
    (plans / "demo-plan.md").write_text("# Plan: demo\n## Goal\nNothing special here.\n")
    r = check_patterns_advisory(tmp_path, "demo")
    assert r["status"] == "N/A"


def _standalone_project(tmp_path: Path, *, tasks: list[dict]) -> Path:
    """A project in the STANDALONE layout — records at the root, no `.claude/` wrapper.

    `rules/records-location.md` makes this canonical for the kit's own repository, which
    is exactly where the kit dogfoods itself.
    """
    (tmp_path / "records" / "plans").mkdir(parents=True)
    (tmp_path / "records" / "implementations").mkdir(parents=True)
    (tmp_path / "records" / "plans" / "s-plan.md").write_text(
        "## Phase 1 — core\n\n### T1.1 — first\n### T1.2 — skipped\n", encoding="utf-8"
    )
    (tmp_path / "records" / "implementations" / ".progress-s.json").write_text(
        json.dumps({"tasks": tasks}), encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_find_progress_reads_the_standalone_layout(tmp_path: Path) -> None:
    """Three call sites hardcoded `.claude/`, while `_find_plan` beside them handled both.

    In the standalone layout every one of them answered SKIP — "no progress checkpoint,
    implement may not have run" — for a checkpoint sitting on disk. A gate that skips because
    it looked in the wrong directory is indistinguishable in the report from one that
    legitimately had nothing to check, which is why it survived.
    """
    from run_validation import _find_progress

    root = _standalone_project(tmp_path, tasks=[{"id": "T1.1", "phase": 1, "status": "committed"}])
    found = _find_progress(root, "s")
    assert found is not None
    assert found == root / "records" / "implementations" / ".progress-s.json"


def test_find_progress_still_prefers_the_plugin_layout(tmp_path: Path) -> None:
    """The plugin layout is canonical for every consumer; standalone is the single exception."""
    from run_validation import _find_progress

    root = _standalone_project(tmp_path, tasks=[])
    plugin = root / ".claude" / "records" / "implementations"
    plugin.mkdir(parents=True)
    (plugin / ".progress-s.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")
    assert _find_progress(root, "s") == plugin / ".progress-s.json"


def test_checkpoint_gate_catches_a_skipped_task_in_the_standalone_layout(tmp_path: Path) -> None:
    """End-to-end: the two defects compounded — the gate could not find the checkpoint, and
    even when it did it could not see an omitted task."""
    from run_validation import check_checkpoint_consistency_gate

    root = _standalone_project(tmp_path, tasks=[{"id": "T1.1", "phase": 1, "status": "committed"}])
    result = check_checkpoint_consistency_gate(root, "s")
    assert result["status"] == "FAIL"
    assert [f["code"] for f in result["findings"] if f.get("severity") != "INFO"] == ["plan_task_absent_from_progress"]


# ---------------------------------------------------------------------------
# Test-execution gate (multi-language). The npm-only checks answered SKIP on a
# Python/Go/Rust repo, overall became PARTIAL and PARTIAL exits 0 — so
# VALIDATION_GATE_PASSED could be emitted without a single test having run.
# ---------------------------------------------------------------------------

def _check(data: dict, name: str) -> dict:
    return next(c for c in data["checks"] if c.get("name") == name)


def test_python_manifest_with_passing_tests_runs_the_suite(fake_project: Path) -> None:
    """A Python project's tests actually execute — not SKIP for lack of package.json."""
    (fake_project / "pyproject.toml").write_text("[project]\nname='fake'\n", encoding="utf-8")
    (fake_project / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    _rc, data = _run_validation("test-slug", fake_project)
    suite = _check(data, "python tests")
    assert suite["status"] == "PASS", suite
    assert _check(data, "test_execution")["status"] == "PASS"


def test_python_failing_tests_fail_the_validation(fake_project: Path) -> None:
    """A red Python suite blocks the gate exactly like a red npm suite does."""
    (fake_project / "pyproject.toml").write_text("[project]\nname='fake'\n", encoding="utf-8")
    (fake_project / "tests" / "test_red.py").write_text(
        "def test_red():\n    assert False\n", encoding="utf-8"
    )
    rc, data = _run_validation("test-slug", fake_project)
    assert rc == 1
    assert data["overall_status"] == "FAIL"
    assert _check(data, "python tests")["status"] == "FAIL"


def test_manifest_present_but_no_suite_ran_is_a_fail(fake_project: Path) -> None:
    """The load-bearing case: a language manifest exists and nothing executed.

    SKIP here is indistinguishable from 'legitimately nothing to check', which is
    how a green validation could mean no test ever ran. It must FAIL instead.
    """
    (fake_project / "pyproject.toml").write_text("[project]\nname='fake'\n", encoding="utf-8")
    rc, data = _run_validation("test-slug", fake_project)
    assert rc == 1
    gate = _check(data, "test_execution")
    assert gate["status"] == "FAIL"
    assert "python" in gate["languages_detected"]


def test_package_json_without_test_script_is_a_fail(fake_project: Path) -> None:
    """A JS project that cannot run tests at all is not a pass."""
    (fake_project / "package.json").write_text(
        json.dumps({"name": "fake", "scripts": {"lint": "true"}}), encoding="utf-8"
    )
    rc, data = _run_validation("test-slug", fake_project)
    assert rc == 1
    assert _check(data, "test_execution")["status"] == "FAIL"


def test_no_manifest_at_all_still_skips_gracefully(fake_project: Path) -> None:
    """Pre-code phase is a legitimate SKIP — the gate must not punish an empty repo."""
    rc, data = _run_validation("test-slug", fake_project)
    gate = _check(data, "test_execution")
    assert gate["status"] == "SKIP"
    assert rc == 0


# ---------------------------------------------------------------------------
# Coverage gate. It used to run `npm run test:coverage` and call exit 0 a PASS
# without ever reading a coverage report — a gate named after a number it never
# looked at.
# ---------------------------------------------------------------------------

def _coverage_project(root: Path, script: str = "true") -> None:
    (root / "package.json").write_text(
        json.dumps({"name": "fake", "scripts": {"test:coverage": script}}), encoding="utf-8"
    )


def test_coverage_reads_the_json_summary_and_passes_above_threshold(fake_project: Path) -> None:
    _coverage_project(fake_project)
    summary = fake_project / "coverage" / "coverage-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps({"total": {"lines": {"pct": 95.5}}}), encoding="utf-8")
    _rc, data = _run_validation("test-slug", fake_project)
    check = _check(data, "coverage")
    assert check["status"] == "PASS"
    assert check["coverage_pct"] == 95.5


def test_coverage_below_threshold_fails(fake_project: Path) -> None:
    """The whole point of the gate: a measured number under the floor blocks."""
    _coverage_project(fake_project)
    summary = fake_project / "coverage" / "coverage-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps({"total": {"lines": {"pct": 41.0}}}), encoding="utf-8")
    rc, data = _run_validation("test-slug", fake_project)
    assert rc == 1
    check = _check(data, "coverage")
    assert check["status"] == "FAIL"
    assert check["coverage_pct"] == 41.0


def test_coverage_without_a_parseable_report_is_not_a_pass(fake_project: Path) -> None:
    """Exit 0 with no report means the threshold was never verified — WARN, not PASS."""
    _coverage_project(fake_project)
    _rc, data = _run_validation("test-slug", fake_project)
    check = _check(data, "coverage")
    assert check["status"] == "WARN"
    assert "not verified" in check["reason"].lower()


def test_coverage_reads_cobertura_xml(fake_project: Path) -> None:
    """coverage.py / Cobertura XML is the Python-side artifact."""
    _coverage_project(fake_project)
    (fake_project / "coverage.xml").write_text(
        '<?xml version="1.0" ?><coverage line-rate="0.873"></coverage>', encoding="utf-8"
    )
    _rc, data = _run_validation("test-slug", fake_project)
    check = _check(data, "coverage")
    assert check["status"] == "PASS"
    assert check["coverage_pct"] == 87.3


def test_coverage_threshold_comes_from_the_project_rules_file(fake_project: Path) -> None:
    """A project may raise the floor; the report says where the number came from."""
    _coverage_project(fake_project)
    rules_dir = fake_project / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "code-quality-thresholds.txt").write_text(
        "coverage.min_percent = 90\n", encoding="utf-8"
    )
    summary = fake_project / "coverage" / "coverage-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps({"total": {"lines": {"pct": 85.0}}}), encoding="utf-8")
    _rc, data = _run_validation("test-slug", fake_project)
    check = _check(data, "coverage")
    assert check["status"] == "FAIL"
    assert check["threshold"] == 90
    assert check["threshold_source"] == "project"


# ---------------------------------------------------------------------------
# Gates the agent ran on its own honour. check_tdd_shape.py and mini_review.py
# were invoked from SKILL.md prose only; the final gate never asked whether
# either had run, so skipping them left no trace.
# ---------------------------------------------------------------------------

_PHASED_PLAN = """# Plan

## Phase 1 — foundation

### T1.1 — first
#### TDD
assert add(1, 2) == 3
"""


def _write_plan(project_root: Path, slug: str, body: str) -> None:
    plans = project_root / "records" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    (plans / f"{slug}-plan.md").write_text(body, encoding="utf-8")


def _write_standalone_progress(project_root: Path, slug: str, tasks: list[dict]) -> None:
    impl = project_root / "records" / "implementations"
    impl.mkdir(parents=True, exist_ok=True)
    (impl / f".progress-{slug}.json").write_text(
        json.dumps({"slug": slug, "tasks": tasks}), encoding="utf-8"
    )


def test_skipped_phase_boundary_review_is_caught_by_the_final_gate(fake_project: Path) -> None:
    """A fully committed phase with no mini-review report must FAIL the validation."""
    _write_plan(fake_project, "phased", _PHASED_PLAN)
    _write_standalone_progress(fake_project, "phased", [
        {"id": "T1.1", "phase": "1", "status": "committed", "commit_sha": "abc", "files": ["src/a.py"]},
    ])
    _rc, data = _run_validation("phased", fake_project)
    gate = _check(data, "phase_review")
    assert gate["status"] == "FAIL"
    assert gate["phases_closed"] == ["1"]


def test_phase_boundary_review_present_passes(fake_project: Path) -> None:
    _write_plan(fake_project, "phased", _PHASED_PLAN)
    _write_standalone_progress(fake_project, "phased", [
        {"id": "T1.1", "phase": "1", "status": "committed", "commit_sha": "abc", "files": ["src/a.py"]},
    ])
    reviews = fake_project / "records" / "mini-reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    (reviews / "phased-phase1-review-2026-08-18.md").write_text("ok", encoding="utf-8")
    _rc, data = _run_validation("phased", fake_project)
    assert _check(data, "phase_review")["status"] == "PASS"


def test_plan_task_without_an_executable_tdd_shape_fails(fake_project: Path) -> None:
    """The Step 2 pre-loop gate is re-asserted at the end: a prose-only TDD block
    means the halt-loop should never have started."""
    _write_plan(fake_project, "vague", """# Plan

### T1.1 — do the thing
#### TDD
We should test that it works well.
""")
    _write_standalone_progress(fake_project, "vague", [
        {"id": "T1.1", "phase": "1", "status": "committed", "commit_sha": "abc", "files": ["src/a.py"]},
    ])
    rc, data = _run_validation("vague", fake_project)
    assert rc == 1
    gate = _check(data, "tdd_shape")
    assert gate["status"] == "FAIL"
    assert gate["tasks_without_shape"] == ["T1.1"]


def test_executable_tdd_shape_passes(fake_project: Path) -> None:
    _write_plan(fake_project, "sharp", _PHASED_PLAN)
    _write_standalone_progress(fake_project, "sharp", [
        {"id": "T1.1", "phase": "1", "status": "committed", "commit_sha": "abc", "files": ["src/a.py"]},
    ])
    _rc, data = _run_validation("sharp", fake_project)
    assert _check(data, "tdd_shape")["status"] == "PASS"


def test_go_workspace_is_detected_as_go(fake_project: Path) -> None:
    """A Go workspace has `go.work` and no root `go.mod`.

    Measured on `theo` while updating its install: the repo is Go, and
    detect_languages returned [] — so test_execution would have SKIPped the
    biggest Go repo in the ecosystem. The same silence the gate exists to break,
    reintroduced by a manifest list that only knew `go.mod`.
    """
    from suite_runners import detect_languages
    (fake_project / "go.work").write_text("go 1.22\n\nuse (\n\t./svc\n)\n", encoding="utf-8")
    assert "go" in detect_languages(fake_project)


def test_go_workspace_runs_each_module_not_the_root(fake_project: Path) -> None:
    """`go test ./...` at a workspace root fails with 'directory prefix . does not
    contain modules listed in go.work' — the kit already hit this in /arch-check."""
    from suite_runners import go_workspace_modules
    (fake_project / "go.work").write_text(
        "go 1.22\n\nuse (\n\t./svc\n\t./tools\n\t../sibling-repo\n)\n", encoding="utf-8"
    )
    (fake_project / "svc").mkdir()
    (fake_project / "tools").mkdir()
    modules = go_workspace_modules(fake_project)
    assert modules == ["svc", "tools"], modules  # '../sibling-repo' is another repo's problem


# ── a JS probe was answering a question about the project ───────────────────

from suite_runners import (  # noqa: E402
    TYPECHECK_COMMANDS,
    _scope_to_change,
    check_lint,
    check_typecheck,
)


def _go_repo(root: Path, *, tidy: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "go.mod").write_text("module example.com/x\n\ngo 1.22\n", encoding="utf-8")
    body = "package x\n\nfunc F() int { return 1 }\n" if tidy else \
        "package x\n\nfunc  F()  int  {return 1}\n"
    (root / "x.go").write_text(body, encoding="utf-8")
    return root


def test_a_missing_package_json_is_not_a_statement_about_the_project(tmp_path: Path) -> None:
    """`package.json absent — pre-code phase` reads as a claim about the repository.

    What was observed is that one ecosystem's manifest is not at the root, which says
    nothing about whether code exists. Measured on a consumer 2026-09-15: a Go workspace
    with 8 modules and 1918 lines of new Go carried that line on four of seven reviews
    — for typecheck, lint and project gates at once.
    """
    source = (Path(__file__).resolve().parents[1] / "scripts" / "run_validation.py"
              ).read_text(encoding="utf-8")
    assert "pre-code phase" not in source.split("def main")[0] or \
        "package.json absent — pre-code phase" not in source, \
        "the skip reason still states a project phase derived from a JS probe"
    assert "no package.json at the repo root — this check is for javascript" in source


def test_typecheck_runs_for_the_languages_whose_tests_already_run(tmp_path: Path) -> None:
    """The test half of the gate was made language-aware in August; typecheck and lint
    stayed npm-only, so on a Go repo the whole non-test half of the gate went quiet."""
    assert "go" in TYPECHECK_COMMANDS and "rust" in TYPECHECK_COMMANDS
    results = check_typecheck(_go_repo(tmp_path / "repo"))
    assert [r["name"] for r in results] == ["go typecheck"]
    assert results[0]["status"] in {"PASS", "FAIL"}, results[0]


def test_a_language_that_is_absent_is_not_reported_at_all(tmp_path: Path) -> None:
    """A Rust result on a repo with no Cargo.toml is noise, not coverage."""
    assert [r["name"] for r in check_typecheck(_go_repo(tmp_path / "repo"))] == \
        ["go typecheck"]


def test_lint_debt_that_predates_the_change_does_not_block_the_change(tmp_path: Path) -> None:
    """A tree carries lint debt older than the item, and blocking on it stops every item
    for somebody else's file. The consumer had already reached this by hand: "`task lint`
    is red at HEAD on an unrelated tracked file, so it is run and DIFFED, never asserted
    absolute." Measured there: 48 tracked Go files fail `gofmt -l`, none touched by the
    item under validation.
    """
    dirty = {"name": "go lint", "status": "FAIL", "runner": "gofmt",
             "flagged_files": ["a/old.go", "b/older.go"]}
    scoped = _scope_to_change(dirty, ["CHANGELOG.md"])
    assert scoped["status"] == "PASS"
    assert scoped["pre_existing"] == 2


def test_pre_existing_lint_debt_is_reported_rather_than_hidden(tmp_path: Path) -> None:
    """Not charging for it is not the same as not saying it. Silence about a dirty tree
    is the other way this gate could lie."""
    scoped = _scope_to_change(
        {"name": "go lint", "status": "FAIL", "runner": "gofmt",
         "flagged_files": ["a/old.go"]}, ["CHANGELOG.md"])
    assert scoped["pre_existing"] == 1
    assert "reported, not charged" in scoped["reason"]


def test_a_file_this_change_touched_is_still_charged(tmp_path: Path) -> None:
    scoped = _scope_to_change(
        {"name": "go lint", "status": "FAIL", "runner": "gofmt",
         "flagged_files": ["a/old.go", "mine.go"]}, ["mine.go"])
    assert scoped["status"] == "FAIL"
    assert scoped["flagged_by_this_change"] == ["mine.go"]
    assert scoped["pre_existing"] == 1


def test_with_no_changed_file_list_the_whole_failure_is_reported(tmp_path: Path) -> None:
    """Every finding is surfaced. An empty list means "cannot scope", never "nothing to
    scope" — what changed is that it surfaces as WARN rather than as a charge."""
    whole = {"name": "go lint", "status": "FAIL", "runner": "gofmt",
             "flagged_files": ["a/old.go"]}
    # Superseded the same day: reporting everything was right, charging the item for it
    # was not. See `test_a_changed_set_that_cannot_be_derived_is_neither_a_pass_nor_a_charge`.
    assert _scope_to_change(whole, [])["status"] == "WARN"
    assert _scope_to_change(whole, None)["status"] == "WARN"


def test_the_finding_list_is_not_read_from_a_truncated_tail() -> None:
    """`run_command` keeps a 500-character tail, and `gofmt -l` names one file per line.
    Scoping against the tail would compare the change against the last few findings and
    silently pass on the rest — 48 findings would have been read as 1."""
    many = [f"pkg/file{i:03d}.go" for i in range(200)]
    tail = "\n".join(many)[-500:]
    outcome = {"name": "go lint", "status": "FAIL", "runner": "gofmt",
               "flagged_files": many, "stderr_tail": tail}
    assert _scope_to_change(outcome, ["CHANGELOG.md"])["pre_existing"] == 200


def test_a_changed_set_that_cannot_be_derived_is_neither_a_pass_nor_a_charge(
        tmp_path: Path) -> None:
    """The first version had two states and returned the whole failure when it could not
    scope, reasoning that reporting everything beats guessing.

    Measured on a consumer 2026-09-15: an item whose work sits on a lane branch has no
    checkpoint to read SHAs from, so the changed set came back empty and the gate FAILED
    it over 48 files it never touched — the exact harm the scoping exists to prevent,
    arriving through the fix for it. Reporting everything was right; charging the item
    for it was not.

    WARN is not folded into FAIL by `main`, so the findings are surfaced without being
    attributed to an item that may not own them.
    """
    whole = {"name": "go lint", "status": "FAIL", "runner": "gofmt",
             "flagged_files": ["a/old.go", "b/older.go"]}
    for cannot_derive in ([], None):
        scoped = _scope_to_change(whole, cannot_derive)
        assert scoped["status"] == "WARN", cannot_derive
        assert scoped["pre_existing"] == 2
        assert "attributed to nobody" in scoped["reason"]
        assert ".progress-" in scoped["reason"], \
            "the reader is not told what would make this a real verdict"


def test_a_failing_suite_reports_what_failed_not_the_tail_of_its_logs() -> None:
    """`go test` prints failing test names to STDOUT and reserves stderr for build
    errors, so a runner reading only `stderr_tail` reports FAIL with an empty
    diagnostic. Measured on a consumer 2026-09-15: 5 of 8 Go modules failing and the
    gate's report named none of them — the reader learned that something broke and
    nothing else.

    Falling back to the stdout TAIL is not enough either: a chatty suite fills 500
    characters with INFO lines from tests that passed, and the failing names sit above
    the cut. The finding is extracted, not tailed.
    """
    from suite_runners import _diagnostic  # noqa: PLC0415

    noisy = (
        "--- FAIL: TestAuditReadFailureIsObservable (0.00s)\n"
        "--- FAIL: TestAuditWindowTruncationIsSignalled (0.01s)\n"
        + "2026/09/15 INFO status_sse: client disconnected\n" * 40
        + "FAIL\tgithub.com/example/api/internal/release\t6.2s\n")
    out = _diagnostic({"exit_code": 1, "stderr_tail": "",
                       "stdout_tail": noisy[-500:], "stdout_full": noisy})
    assert "TestAuditReadFailureIsObservable" in out
    assert "TestAuditWindowTruncationIsSignalled" in out
    assert "INFO status_sse" not in out, "log noise crowded out the finding"


def test_a_build_error_on_stderr_still_wins() -> None:
    """When a build fails, stderr IS the finding — falling through to stdout would
    report a suite that never ran as a suite with no failures."""
    from suite_runners import _diagnostic  # noqa: PLC0415

    out = _diagnostic({"exit_code": 2, "stderr_tail": "cannot find module for path x",
                       "stdout_tail": "", "stdout_full": ""})
    assert "cannot find module" in out


def test_no_skip_reason_states_a_project_phase_it_did_not_observe() -> None:
    """"pre-code phase" is a claim about the repository. What these checks observe is a
    missing manifest, a missing coverage command, a missing report — none of which says
    whether code exists. A Go workspace with 8 modules and 1918 lines of new Go read
    "pre-code phase" on four separate gates.

    A skip reason names what was looked for and not found. It does not conclude.
    """
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    offenders = [
        f"{path.name}:{n}"
        for path in scripts.glob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if '"reason"' in line and "pre-code phase" in line
    ]
    assert not offenders, f"skip reasons still conclude a project phase: {offenders}"


def test_an_annotated_files_to_edit_bullet_still_declares_its_file() -> None:
    """`FILE_LINE_RE` anchored at `$`, so only a bare path on a line by itself matched.

    Every plan in a real registry annotates its scope — `- \x60api/x.go\x60 — add the
    error branch`, `(new)`, `: the discard` — and an annotated list parsed as ZERO
    declared files, raising HIGH `no_declared_scope` against a plan that declares its
    scope precisely. Measured on a consumer 2026-09-15: three phases of one plan, all
    correct.

    A gate that reports correct work as a defect spends the reviewer's attention and
    returns nothing — the same shape as 19 false phase divergences the same day.
    """
    from check_diff_cohesion import FILE_LINE_RE  # noqa: PLC0415

    for line, expected in (
        ("- `api/internal/x.go`", "api/internal/x.go"),
        ("- `api/internal/x.go` — add the error branch", "api/internal/x.go"),
        ("- `api/internal/x.go` (new)", "api/internal/x.go"),
        ("* `pkg/y.go`: the discard", "pkg/y.go"),
        ("- api/internal/z.go", "api/internal/z.go"),
    ):
        match = FILE_LINE_RE.match(line)
        assert match and match.group(1) == expected, line


def test_a_sentence_mentioning_a_filename_declares_nothing() -> None:
    """The path must be the FIRST thing on the bullet. Widening the tail must not turn
    every prose line containing a filename into a declaration of scope."""
    from check_diff_cohesion import FILE_LINE_RE  # noqa: PLC0415

    assert FILE_LINE_RE.match("the plan touches `api/x.go` in passing") is None
    assert FILE_LINE_RE.match("- see the note about main.go below and why") is None


def test_a_failing_package_the_change_did_not_touch_is_reported_not_charged() -> None:
    """A red test in a package the change never edited is debt, not a regression.

    Measured on a consumer 2026-09-15: an item whose work sits entirely in
    `api/internal/services/build` was blocked by a test in `api/tests/unit`, verified
    failing at the commit BEFORE that item's first by building the pre-change tree. With
    no way to say so, every item in that repository is blocked by the same unrelated
    test until somebody fixes it.

    This never turns a failure into a pass — a red suite stays visibly red. It turns a
    charge into a WARN that names the packages and says the change did not touch them.
    """
    from suite_runners import scope_suite_to_change  # noqa: PLC0415

    red = {"name": "go tests", "status": "FAIL", "runner": "go test",
           "stderr_tail": ("--- FAIL: TestMigrationReferencesADR (0.00s)\n"
                           "FAIL\nFAIL\tgithub.com/example/api/tests/unit\t6.1s\n")}
    elsewhere = scope_suite_to_change(red, ["api/internal/services/build/x.go"])
    assert elsewhere["status"] == "WARN"
    assert "touched none of them" in elsewhere["reason"]

    inside = scope_suite_to_change(red, ["api/tests/unit/migration_test.go"])
    assert inside["status"] == "FAIL"
    assert inside["failing_packages_this_change_touched"]

    assert scope_suite_to_change(red, [])["status"] == "FAIL"


def test_the_failing_package_is_not_swallowed_by_a_bare_FAIL_line() -> None:
    """`^FAIL\\s+(\\S+)` let `\\s` cross the newline, so a bare `FAIL` line captured the
    NEXT line's package name and the real one was never seen. The scoping then found no
    packages and passed the failure through unchanged — a fix that silently did nothing,
    which is the shape it exists to prevent."""
    from suite_runners import _FAILING_PACKAGE_RE  # noqa: PLC0415

    found = _FAILING_PACKAGE_RE.findall("FAIL\nFAIL\tgithub.com/example/api/tests/unit\t6s\n")
    assert "github.com/example/api/tests/unit" in found


def test_a_scoped_suite_still_counts_as_having_executed() -> None:
    """Turning one FAIL into a WARN made `check_test_execution` report "no test suite
    executed" about a suite whose failing test names it had just printed."""
    from suite_runners import check_test_execution  # noqa: PLC0415
    import suite_runners  # noqa: PLC0415

    scoped = [{"name": "go tests", "status": "WARN", "runner": "go test"}]
    original = suite_runners.detect_languages
    suite_runners.detect_languages = lambda _root: ["go"]
    try:
        assert check_test_execution(Path("."), scoped)["status"] != "FAIL"
    finally:
        suite_runners.detect_languages = original


def _git_repo(tmp_path: Path):
    """A real repository. A temp directory is not one, and `diff_source` correctly
    reports `none` there — a fixture that forgets this tests the failure path while
    claiming to test the success path."""
    import subprocess  # noqa: PLC0415

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "seed.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "seed"], check=True)
    return subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def _cohesion(tmp_path: Path, files_block: str, sha: str):
    import json as _json  # noqa: PLC0415
    from check_diff_cohesion import check_diff_cohesion  # noqa: PLC0415

    plan = tmp_path / "p.md"
    plan.write_text(f"## Tasks\n\n### T1.1 — a task\n\n#### Files to edit\n\n"
                    f"{files_block}\n\n#### TDD\n\nassert a == b\n", encoding="utf-8")
    prog = tmp_path / ".progress-x.json"
    prog.write_text(_json.dumps({"tasks": [
        {"id": "T1.1", "phase": "1", "status": "committed", "commit_sha": sha}]}),
        encoding="utf-8")
    report = check_diff_cohesion(plan, prog, "1", repo_root=tmp_path)
    return [f.code for f in report.findings if f.severity in ("HIGH", "MEDIUM")]


def test_an_explicit_none_in_files_to_edit_is_a_declaration(tmp_path: Path) -> None:
    """A task whose `#### Files to edit` reads `None.` DECLARES that it edits nothing.
    The gate read that as an absent declaration and raised HIGH `no_declared_scope` —
    the same defect as the deps-audit `(none)` that discarded a whole section, and the
    same as `committed` with no SHA: an honest statement of nothing with no state to
    hold it.

    Three instances in one consumer item, on the same day.
    """
    sha = _git_repo(tmp_path)
    assert "no_declared_scope" not in _cohesion(
        tmp_path, "None. This task writes one scratch artifact and edits no tracked file.", sha)


def test_declaring_nothing_and_touching_source_is_drift_not_absence() -> None:
    """The declaration makes this the STRONGEST form of the check, not the weakest: the
    plan said none and the diff says otherwise."""
    from check_diff_cohesion import _EXPLICIT_NO_FILES_RE  # noqa: PLC0415

    assert _EXPLICIT_NO_FILES_RE.search("None.")
    assert _EXPLICIT_NO_FILES_RE.search("None. This task writes no tracked file.")
    assert _EXPLICIT_NO_FILES_RE.search("(none)")
    assert not _EXPLICIT_NO_FILES_RE.search("- `api/x.go` — the fix")


def test_declaring_a_file_and_never_touching_it_is_also_drift(tmp_path: Path) -> None:
    """The other half of scope drift. Five adversarial cases covered touching something
    undeclared; none covered declaring something untouched — the consumer session found
    it by mutating a plan and getting no finding at all.

    A plan that declares five files and edits two has a scope claim that is wrong, and
    today's lesson is that a wrong claim with a right conclusion is the hardest kind to
    catch. MEDIUM, not HIGH: nothing unreviewed reached the tree.
    """
    sha = _git_repo(tmp_path)
    codes = _cohesion(tmp_path, "- `api/never_touched.go` — planned but not written", sha)
    assert "declared_but_untouched" in codes

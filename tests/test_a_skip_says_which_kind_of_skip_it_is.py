"""A gate that did not run says whether it COULD not or NEED not.

THE DEFECT THIS CLOSES
----------------------
`run_validation.py` consolidates twenty checks with
`overall = "FAIL" if fails else ("PARTIAL" if skips else "PASS")`, and `PARTIAL` exits
0 — "proceed". Every SKIP counted the same, and SKIPs have two opposite natures:

    not applicable        `npm test` in a Go repository        SKIP is honest
    precondition missing  `wiring_triad: no progress file`     the work did not happen

Measured 2026-09-21 on a repository holding a plan and no checkpoint:

    overall_status: PARTIAL   exit 0
    2 pass · 16 skip · 1 warn · 0 fail
    SKIP checkpoint_consistency: no progress checkpoint — implement may not have run
    SKIP wiring_triad:           no progress file found — implement may not have been invoked

The check writes the suspicion and returns SKIP. The final gate of IMPLEMENT said
"proceed" about a repository where `/implement` had not run.

The kit already argues the correct shape twice, in the comments of the two checks it
fixed one at a time — `tdd_shape`: *"FAIL, not SKIP. The plan FILE exists… As a SKIP it
counted into `skips`, `overall` became PARTIAL, and PARTIAL exits 0, so
IMPLEMENTATION_COMPLETE could be emitted with the TDD shape never verified."* This
generalises it: a SKIP declares its kind, and a missing precondition is a failure.

AND THE SECOND HALF: "PRE-CODE" MEANT "NO MANIFEST"
---------------------------------------------------
`test_execution` SKIPs only for "a repo with no language manifest at all (genuine
pre-code phase)". Measured with `src/thing.py` committed and no `pyproject.toml`:

    SKIP test_execution: no language manifest at the repo root      PARTIAL, exit 0

Adding a two-line `pyproject.toml`, touching no code:

    FAIL test_execution: manifest(s) for python present but no suite executed   exit 1

What separated proceed from refuse was a metadata file, not the existence of the code.
A repository with sources and no manifest is not in a pre-code phase — the kit itself
ships "loose scripts" — so sources without a suite is a missing precondition too.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / "skills" / "implement" / "scripts" / "run_validation.py"


def _project(tmp_path: Path, *, with_sources: bool = False,
             with_manifest: bool = False) -> Path:
    records = tmp_path / ".squad" / "records"
    (records / "plans").mkdir(parents=True)
    (records / "implementations").mkdir(parents=True)
    (records / "plans" / "demo-plan.md").write_text(
        "# Plan: demo\n\n## Phase 1 — Do it\n\n### T1.1 — Add it\n\n"
        "#### TDD\n- test_thing_returns_value: assert thing() == 42\n", encoding="utf-8")
    (records / "implementations" / "demo-implementation.md").write_text(
        "# Implementation: demo\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    if with_sources:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "thing.py").write_text("def thing():\n    return 42\n",
                                                   encoding="utf-8")
    if with_manifest:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    for cmd in (["git", "init", "-q", "."], ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"], ["git", "add", "-A"],
                ["git", "commit", "-qm", "chore: seed"]):
        subprocess.run(cmd, cwd=tmp_path, capture_output=True, check=False)
    return tmp_path


def _validate(root: Path) -> tuple[dict, int]:
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), "demo", "--project-root", str(root),
         "--no-write-report", "--no-code-quality"],
        capture_output=True, text=True, check=False)
    return json.loads(proc.stdout[proc.stdout.index("{"):]), proc.returncode


def _check(report: dict, name: str) -> dict:
    return next(c for c in report["checks"] if c["name"] == name)


def test_a_missing_checkpoint_is_not_a_reason_to_proceed(tmp_path: Path) -> None:
    report, code = _validate(_project(tmp_path))

    assert report["overall_status"] == "FAIL", (
        "four checks report that /implement may not have run, and the gate said proceed")
    assert code == 1


def test_the_checkpoint_checks_declare_why_they_did_not_run(tmp_path: Path) -> None:
    report, _ = _validate(_project(tmp_path))

    for name in ("checkpoint_consistency", "wiring_triad", "phase_review"):
        assert _check(report, name).get("skip_kind") == "precondition_missing", (
            f"{name} skipped because the work did not happen, which is not the same "
            f"fact as a check that does not apply here")


def test_a_check_that_does_not_apply_is_still_an_honest_skip(tmp_path: Path) -> None:
    """`npm test` in a repository with no package.json is not a defect."""
    report, _ = _validate(_project(tmp_path))

    assert _check(report, "npm test")["status"] == "SKIP"
    assert _check(report, "npm test").get("skip_kind") == "not_applicable"


def test_sources_with_no_manifest_are_not_a_pre_code_phase(tmp_path: Path) -> None:
    report, code = _validate(_project(tmp_path, with_sources=True))

    execution = _check(report, "test_execution")
    assert execution["status"] == "FAIL" or execution.get("skip_kind") == "precondition_missing", (
        "src/thing.py is committed; what separated proceed from refuse was a metadata "
        "file, not the existence of the code")
    assert code == 1


def test_a_manifest_with_no_suite_still_fails(tmp_path: Path) -> None:
    """The half the kit had already closed must stay closed."""
    report, code = _validate(_project(tmp_path, with_sources=True, with_manifest=True))

    assert _check(report, "test_execution")["status"] == "FAIL"
    assert code == 1

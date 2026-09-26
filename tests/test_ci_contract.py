"""CI must fail what the gates fail.

THE DEFECT THIS FIXES
---------------------
`check_xrefs.py` has two modes. Without `--strict`, a WARN-severity finding is
printed and the process exits 0 — the literal output carries the WARN line and,
right
below it, `Overall: PASS`. With `--strict`, the same finding exits 1.

`mechanisms/distribution/install.sh` always called it with `--strict`. The workflow called it
without. The result, measured 2026-08-26: an installation from a clean clone was
born with `rules/cycle-maintenance.md` pointing at an `agents/README.md`
that did not exist, the installer said `check_xrefs.py: FAIL`, and the CI of the
same commit went green. The gate looked, saw, and approved.

WHY THE TEST READS THE WORKFLOW'S COMMAND INSTEAD OF LOOKING FOR THE FLAG
--------------------------------------------------------------------------
A test doing `assert "--strict" in ci_yml` would match the flag written anywhere
in the file — in a comment, in a disabled step, in a job that does not run. It
would assert about the workflow's TEXT, not about what the
workflow faz.

So this module extracts each step's exact command and RUNS it against a
deliberately corrupted tree. What is asserted is behaviour: given a real defect,
the command CI runs must exit non-zero. That keeps holding if someone replaces
`--strict` with another mechanism — which is exactly what a behaviour test should
allow.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def _steps() -> list[dict]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    out: list[dict] = []
    for job in doc.get("jobs", {}).values():
        out.extend(job.get("steps", []) or [])
    return out


def _step_running(fragment: str) -> dict:
    matches = [s for s in _steps() if fragment in (s.get("run") or "")]
    assert matches, f"no CI step runs {fragment!r} — the gate left the workflow"
    assert len(matches) == 1, f"{fragment!r} appears in {len(matches)} steps; expected 1"
    return matches[0]


@pytest.fixture()
def broken_kit(versioned_kit: Path, tmp_path: Path) -> Path:
    """A copy of the kit with exactly the defect that passed green.

    `agents/README.md` is cited by `rules/cycle-maintenance.md`. Removing it
    reproduces the state every clean clone was born in before the fix.
    """
    kit = tmp_path / "broken-kit"
    shutil.copytree(versioned_kit, kit)
    readme = kit / "agents" / "README.md"
    assert readme.is_file(), (
        "agents/README.md is not versioned — this test cannot reproduce the "
        "defect, and the kit is already broken for another reason."
    )
    readme.unlink()
    return kit


def test_ci_xref_step_rejects_a_broken_reference(broken_kit: Path):
    """CI's cross-reference command, run against a broken tree, must fail."""
    run = _step_running("check_xrefs.py")["run"].strip()
    proc = subprocess.run(run, shell=True, cwd=broken_kit, capture_output=True, text=True, check=False)
    assert proc.returncode != 0, (
        "CI's cross-reference step approved a broken reference.\n"
        f"command: {run}\n"
        f"output:\n{proc.stdout}\n{proc.stderr}"
    )


def test_ci_xref_step_accepts_the_healthy_kit(versioned_kit: Path):
    """And it must approve the intact tree — otherwise the test above would pass by accident."""
    run = _step_running("check_xrefs.py")["run"].strip()
    proc = subprocess.run(run, shell=True, cwd=versioned_kit, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, (
        f"CI fails the intact kit:\n{proc.stdout}\n{proc.stderr}"
    )


def test_ci_runs_the_install_contract(_broken: None = None):
    """The clean-install regression must be in the workflow, not only on disk.

    `tests/test_clean_install.py` is the only test that sees what another machine
    would receive. If it does not run in CI, it goes back to being a file that
    passed once.
    """
    runs = " ".join((s.get("run") or "") for s in _steps())
    assert "run_slice_tests.sh" in runs or "test_clean_install" in runs, (
        "no CI step runs the suite containing the installation contract"
    )


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")).get("jobs", {})


def test_the_root_suite_is_not_run_twice_in_the_same_job():
    """Running the same suite twice measures nothing more — it only costs double.

    The main job ran `run_slice_tests.sh` (which already runs `tests`) and, in the
    next step, `pytest tests` again with coverage. Measured 2026-08-26: 45s
    duplicated per run. Coverage is now computed in the single run, with the same
    threshold enforced.
    """
    for name, job in _jobs().items():
        runs = [(s.get("run") or "") for s in (job.get("steps") or [])]
        slice_runner = [r for r in runs if "run_slice_tests.sh" in r]
        if not slice_runner:
            continue
        standalone_root = [
            r for r in runs
            if "run_slice_tests.sh" not in r
            and "pytest" in r
            and " tests" in r
        ]
        assert not standalone_root, (
            f"job {name!r} runs the root suite twice: {standalone_root}"
        )


def test_coverage_threshold_survives_the_deduplication():
    """The de-duplication must not have taken the coverage threshold with it."""
    runs = " ".join((s.get("run") or "") for s in _steps())
    env = " ".join(
        f"{k}={v}"
        for job in _jobs().values()
        for step in (job.get("steps") or [])
        for k, v in (step.get("env") or {}).items()
    )
    assert "cov-fail-under" in runs or "ROOT_SUITE_COV" in runs + env, (
        "no CI step enforces a coverage threshold"
    )


def test_python_setup_caches_dependencies():
    """Four jobs reinstalling the same dependencies on every run is pure cost."""
    missing = []
    for name, job in _jobs().items():
        for step in job.get("steps") or []:
            if str(step.get("uses", "")).startswith("actions/setup-python"):
                if not (step.get("with") or {}).get("cache"):
                    missing.append(name)
    assert not missing, f"setup-python without dependency cache in jobs: {missing}"


def test_the_documented_dispatch_passes_what_the_scheduler_can_use() -> None:
    """A fix that lands in code and not in the procedure that invokes it is half a fix,
    and the missing half is the one a new reader follows.

    `skills/pipeline/SKILL.md` Step 2 said to pass `args: {queue: <the "queue" array>}`
    until 2026-09-15, while SELECT had grown two more keys carrying items a stage can act
    on. Measured on a consumer registry of 102 items: the whole selection builds 71 items
    with 56 approved entering at PLAN; the `queue` array alone builds 13, none approved.

    An operator following the documented procedure exactly reproduced a defect the code
    no longer had. Found by a consumer session which noticed it had been unable to
    reproduce the documented path all day, because every dispatch it made passed the full
    object rather than the array the skill named.
    """
    skill = (Path(__file__).resolve().parents[1] / "skills" / "pipeline"
             / "SKILL.md").read_text(encoding="utf-8")
    workflow = (Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
                / "pipeline_workflow.js").read_text(encoding="utf-8")

    assert "args: {selection:" in skill, (  # prose-test: an operator copies this dispatch verbatim; the literal IS what ships
        "the documented dispatch still names a single key of the selection")
    for key in ("awaiting_plan", "in_flight"):
        assert key in workflow, f"the workflow cannot read {key}, so nothing can pass it"
        assert key in skill, f"the procedure does not mention {key}"


def test_the_dispatch_does_not_promise_a_file_it_cannot_check() -> None:
    """The stage prompt told every agent its instruction file was "written to disk before
    this run and versioned so a wrong finding can be traced to the prompt that produced
    it". Neither half was true.

    Materialising is the CALLER's Step 1 and a workflow script has no filesystem access,
    so nothing enforced the first claim — on a consumer 8 of 99 items had been
    materialised and four dispatched items ran with no instruction file at all. And
    `.squad/*` is gitignored, so `git ls-files .squad` returns 0: the prompt is on one
    disk and the traceability the sentence promised does not exist.

    Promising a guarantee that is absent is worse than its absence, because a reader stops
    looking for it. What replaces it is an instruction the agent can act on, since the
    script cannot: stop and report, rather than reconstruct the contract from siblings.
    """
    workflow = (Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
                / "pipeline_workflow.js").read_text(encoding="utf-8")
    dispatch = workflow.split("const stagePrompt")[1].split("const BRIEF")[0]
    assert "versioned so a wrong" not in dispatch, \
        "the dispatch still promises traceability that gitignore removes"
    assert "written to disk before this run and" not in dispatch, \
        "the dispatch still asserts a file nothing checked"
    assert "STOP and report" in dispatch, \
        "the agent is not told what to do when the file is absent"


# ── the jobs that answer a question the others do not ────────────────────────
#
# Three findings, one shape: the pipeline ran analysis and never asked a security
# question, never checked formatting, and produced nothing a machine could read.
# `ruff check` with this repository's rule set and `shellcheck --severity=warning`
# are correctness tools — neither looks for a hardcoded credential, an unpinned
# action or a dependency with a known CVE.


def _jobs() -> dict:
    import yaml
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _job_text(job: str) -> str:
    """Every `run:` and `uses:` in ONE job, as one searchable string.

    Named apart from `_steps()` above, which returns the steps of the whole workflow.
    """
    parts: list[str] = []
    for step in _jobs()[job].get("steps", []):
        parts.append(str(step.get("run", "")))
        parts.append(str(step.get("uses", "")))
        parts.append(str(step.get("name", "")))
    return "\n".join(parts)


def test_a_dedicated_security_job_exists() -> None:
    assert "security" in _jobs(), (
        "no job asks a security question; the analysis steps check correctness")


def test_the_security_job_scans_code_and_dependencies() -> None:
    steps = _job_text("security")

    assert "bandit" in steps, "no static security review"
    assert "pip-audit" in steps, "no dependency audit"
    assert "--select S" in steps, "ruff's security rule family is not run on its own"


def test_the_security_job_can_see_history() -> None:
    """A credential removed in the last commit is still in the pack."""
    checkout = next(s for s in _jobs()["security"]["steps"]
                    if str(s.get("uses", "")).startswith("actions/checkout"))

    assert checkout.get("with", {}).get("fetch-depth") == 0


def test_the_pipeline_produces_a_machine_readable_report() -> None:
    steps = _job_text("security")

    assert "upload-artifact" in steps, (
        "every question of the form 'did the finding count go up' means re-reading a "
        "log by eye")


def test_formatting_is_checked_separately_from_the_lint() -> None:
    """A job failing for an import order and one failing for a missing space are
    different problems and should be different lines in the summary."""
    assert "formatting" in _jobs()

    steps = _job_text("formatting")
    assert "ruff format" in steps
    assert "--diff" in steps, "CI must not rewrite the tree it is measuring"


def test_the_rule_set_declares_an_owner() -> None:
    """A change to `rules/` changes every consumer's behaviour without touching a line
    of their code, and nothing named who reviews it."""
    codeowners = REPO / ".github" / "CODEOWNERS"

    assert codeowners.is_file(), "no CODEOWNERS anywhere in this repository"

    body = codeowners.read_text(encoding="utf-8")
    owned = {line.split()[0] for line in body.splitlines()
             if line.strip() and not line.lstrip().startswith("#")}

    for path in ("/rules/", "/mechanisms/gates/", "/hooks/", "/.github/"):
        assert path in owned, f"{path} has no declared owner"

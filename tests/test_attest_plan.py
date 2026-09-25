"""Plan attestation: the writer and the readers must resolve the same root.

WHY THIS FILE EXISTS
--------------------
`attest_plan.sh` had no test, and the thing it needed a test for is not what it
computes — a SHA256 is hard to get wrong — but WHERE it puts the answer.

It resolved the ecosystem itself, by probing for `skills/+rules/+hooks/` under
`.`, `.claude/` and `.claude/plugins/cycle/`. In the plugin-native layout the kit
lives outside the project, so none of the three matched and it fell back to `.`,
writing to `<project>/.attestations/` and reading plans from
`<project>/records/plans/`. The three hooks that consume the attestation go
through `squad/plan.py`, anchored at `squad/layout.py`'s `eco`, which is
`<project>/.claude` whenever that directory exists.

Two roots, and the consequences were silent in both directions (#36):

  - with the plan where `rules/records-location.md` mandates it
    (`<project>/.claude/records/plans/`), `/plan-attest` exited 1 with
    "plan file not found" — attestation was impossible;
  - with the plan at the project root, the script wrote an attestation the hook
    would never read, and `Attestation.tampered` is False when `expected` is
    None, so an edited plan was injected every turn with no warning.

These tests assert the property that was missing: whatever the layout, the file
`attest_plan.sh` writes is the file `squad.plan.attestation` reads.
"""
from __future__ import annotations

import os
import subprocess
import sys as _s
from pathlib import Path

_s.path.insert(0, str(Path(__file__).resolve().parents[1]))
from squad.layout import resolve
from squad.paths import ATTESTATIONS, write_state_dir
from squad.plan import attestation, resolve as resolve_plan

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "mechanisms" / "cycle" / "attest_plan.sh"

_PLAN = "# Plan: demo\n\n## Goal\n\n> ship the thing\n"


def _run(project: Path, *args: str, plugin: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    if plugin:
        env["CLAUDE_PLUGIN_ROOT"] = str(_REPO)
    else:
        env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run(  # noqa: PLW1510 — the returncode is the assertion
        ["bash", str(_SCRIPT), *args],
        capture_output=True, text=True, cwd=str(project), env=env,
    )


def _plugin_project(tmp_path: Path) -> Path:
    """A consumer in the plugin-native layout: `.claude/` present, kit outside it."""
    project = tmp_path / "proj"
    (project / ".squad" / "records" / "plans").mkdir(parents=True)
    (project / ".squad" / "records" / "plans" / "demo-plan.md").write_text(
        _PLAN, encoding="utf-8"
    )
    return project


def _eco_of(project: Path, *, plugin: bool = True) -> Path:
    env_project = os.environ.get("CLAUDE_PROJECT_DIR")
    env_plugin = os.environ.get("CLAUDE_PLUGIN_ROOT")
    try:
        os.environ["CLAUDE_PROJECT_DIR"] = str(project)
        if plugin:
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(_REPO)
        else:
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
        layout = resolve(project)
        assert layout is not None
        return layout.eco
    finally:
        for key, value in (("CLAUDE_PROJECT_DIR", env_project),
                           ("CLAUDE_PLUGIN_ROOT", env_plugin)):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# ── the plugin-native layout ──────────────────────────────────────────────────

def test_it_attests_a_plan_where_the_canonical_records_are(tmp_path: Path) -> None:
    """`rules/records-location.md`: "<project>/.claude/records/ is canonical. Always."

    The script looked in `<project>/records/plans/` and exited 1.
    """
    project = _plugin_project(tmp_path)

    done = _run(project, "demo")

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"


def test_the_attestation_lands_where_the_hooks_read_it(tmp_path: Path) -> None:
    """The whole point. Writer and reader, one root."""
    project = _plugin_project(tmp_path)
    _run(project, "demo")

    eco = _eco_of(project)
    plan = resolve_plan(eco)
    assert plan is not None, "the hooks cannot even see the plan"

    report = attestation(eco, plan)
    assert report.expected is not None, "nothing was written where the hooks look"
    assert report.expected == report.actual
    assert not report.tampered


def test_an_edited_plan_is_reported_as_tampered(tmp_path: Path) -> None:
    """The guarantee SECURITY.md advertises, exercised end to end.

    While the roots disagreed this could not fire at all: `expected` was None, and
    `tampered` is False when there is nothing to compare against — correct in
    isolation, and it is what made the defect silent.
    """
    project = _plugin_project(tmp_path)
    _run(project, "demo")

    eco = _eco_of(project)
    plan = resolve_plan(eco)
    assert plan is not None
    plan.path.write_text(_PLAN + "\n## Smuggled\n\nsomething nobody approved\n",
                         encoding="utf-8")

    assert attestation(eco, plan).tampered


def test_verify_agrees_with_the_hooks_about_the_same_plan(tmp_path: Path) -> None:
    project = _plugin_project(tmp_path)
    _run(project, "demo")

    done = _run(project, "--verify", "demo")

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert "OK" in done.stdout


def test_verify_reports_the_tamper_it_is_there_to_catch(tmp_path: Path) -> None:
    project = _plugin_project(tmp_path)
    _run(project, "demo")
    plan = project / ".squad" / "records" / "plans" / "demo-plan.md"
    plan.write_text(_PLAN + "\nedited\n", encoding="utf-8")

    done = _run(project, "--verify", "demo")

    assert done.returncode == 4
    assert "TAMPERED" in done.stdout


# ── the standalone layout has no exception left ───────────────────────────────

def test_the_standalone_layout_uses_the_same_write_root(tmp_path: Path) -> None:
    """`records-location.md` used to carve out one exception: the kit's own repository,
    where `skills/`, `rules/` and `hooks/` sit at the root and the trail was
    `<repo>/records/` rather than `<repo>/.claude/records/`.

    Two answers meant two ways to be wrong, and the exception is what the first
    instrumented run tripped over. There is one write root now, in every layout, so
    this test asserts the absence of the exception rather than its shape.
    """
    project = tmp_path / "kit"
    for tree in ("skills", "rules", "hooks"):
        (project / tree).mkdir(parents=True)
    plans = project / ".squad" / "records" / "plans"
    plans.mkdir(parents=True)
    (plans / "demo-plan.md").write_text(_PLAN, encoding="utf-8")

    done = _run(project, "demo", plugin=False)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert (write_state_dir(project, ATTESTATIONS) / "demo.sha256").is_file()
    assert not (project / ".claude").exists(), "a standalone repo grew a .claude/"

    eco = _eco_of(project, plugin=False)
    plan = resolve_plan(eco)
    assert plan is not None
    assert not attestation(eco, plan).tampered


# ── refusals ──────────────────────────────────────────────────────────────────

def test_a_plan_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    project = _plugin_project(tmp_path)

    done = _run(project, "no-such-plan")

    assert done.returncode != 0
    assert "not found" in (done.stdout + done.stderr).lower()


def test_a_project_with_no_kit_says_so_instead_of_writing_somewhere(
    tmp_path: Path,
) -> None:
    """No layout resolves: the old code silently fell back to `.` and wrote there.

    An attestation in a directory no reader consults is worse than no attestation,
    because `--verify` then reports OK about a file nothing else will ever open.
    """
    project = tmp_path / "bare"
    (project / "records" / "plans").mkdir(parents=True)
    (project / "records" / "plans" / "demo-plan.md").write_text(_PLAN, encoding="utf-8")
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project),
           "CLAUDE_PLUGIN_ROOT": str(tmp_path / "nowhere")}
    done = subprocess.run(
        ["bash", str(_SCRIPT), "demo"],
        capture_output=True, text=True, cwd=str(project), env=env,
     check=False)

    assert done.returncode != 0
    assert not write_state_dir(project, ATTESTATIONS).exists()

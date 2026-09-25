"""A criterion is read in three states, and the third is the one that catches a NAME.

The single-state run asks only "does it already pass?". The method the consumer measured
with has three states and a control:

    current tree       the criterion must FAIL — something is left to prove
    intended state     the criterion must PASS — the finished work satisfies it
    a wrong build      the criterion must FAIL — it rejects an implementation that is wrong
    reconstruction     a baseline rebuilt the same way must answer as the current tree does,
                       or "the change moved this" cannot be told from "my rebuild is broken"

The fixture is a function whose NAME is right and whose BODY is wrong. A criterion that
greps for the name turns green on it, and that is exactly what a reviewer's formulation
predicts: the minimal artefact that satisfies a criterion says what it is sensitive to.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import check_criteria_discriminate as ccd  # noqa: E402 — post-bootstrap import

_SCRIPT = SKILL_ROOT / "scripts" / "check_criteria_discriminate.py"

_BEHAVIOUR = '- AC-001 `grep -c "return a + b" calc.py` prints 1'
_NAME_ONLY = '- AC-002 `grep -c "def add" calc.py` prints 1'
_UNREACHABLE = '- AC-003 `grep -c "return a \\* b" calc.py` prints 1'


def _brief(tmp_path: Path, *criteria: str) -> Path:
    brief = tmp_path / "brief.md"
    brief.write_text("# Alignment\n\n## Acceptance Criteria\n" + "\n".join(criteria) + "\n",
                     encoding="utf-8")
    return brief


def _tree(tmp_path: Path, name: str, source: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / "calc.py").write_text(source, encoding="utf-8")
    return root


def _states(tmp_path: Path) -> dict[str, Path]:
    return {
        "current": _tree(tmp_path, "current", "def total():\n    return 0\n"),
        "intended": _tree(tmp_path, "intended", "def add(a, b):\n    return a + b\n"),
        "wrong": _tree(tmp_path, "wrong", "def add(a, b):\n    return a - b\n"),
    }


def _verdicts(report) -> list[str]:
    return [v.verdict for v in report.verdicts]


def test_a_criterion_that_tells_all_three_states_apart_discriminates(tmp_path: Path) -> None:
    trees = _states(tmp_path)

    report = ccd.run_states(_brief(tmp_path, _BEHAVIOUR), trees["current"],
                            intended_root=trees["intended"], wrong_roots=[trees["wrong"]])

    assert _verdicts(report) == ["discriminates"]


def test_a_criterion_that_accepts_the_wrong_build_is_non_discriminating(tmp_path: Path) -> None:
    """Fails today, passes when built — and passes on a build that is wrong, too."""
    trees = _states(tmp_path)

    report = ccd.run_states(_brief(tmp_path, _NAME_ONLY), trees["current"],
                            intended_root=trees["intended"], wrong_roots=[trees["wrong"]])

    assert _verdicts(report) == ["non_discriminating"]


def test_a_criterion_the_intended_state_cannot_pass_is_named(tmp_path: Path) -> None:
    trees = _states(tmp_path)

    report = ccd.run_states(_brief(tmp_path, _UNREACHABLE), trees["current"],
                            intended_root=trees["intended"], wrong_roots=[trees["wrong"]])

    assert _verdicts(report) == ["fails_when_built"]


def test_a_baseline_that_reproduces_the_current_tree_passes_the_control(tmp_path: Path) -> None:
    trees = _states(tmp_path)
    baseline = _tree(tmp_path, "baseline", "def total():\n    return 0\n")

    report = ccd.run_states(_brief(tmp_path, _BEHAVIOUR), trees["current"],
                            intended_root=trees["intended"], wrong_roots=[trees["wrong"]],
                            baseline_root=baseline)

    assert report.control_reproduced is True


def test_a_baseline_that_answers_differently_fails_the_control(tmp_path: Path) -> None:
    """A rebuild that already carries the change cannot attribute anything to the change."""
    trees = _states(tmp_path)
    broken = _tree(tmp_path, "baseline", "def add(a, b):\n    return a + b\n")

    report = ccd.run_states(_brief(tmp_path, _BEHAVIOUR), trees["current"],
                            intended_root=trees["intended"], wrong_roots=[trees["wrong"]],
                            baseline_root=broken)

    assert report.control_reproduced is False


def _cli(tmp_path: Path, brief: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_SCRIPT), str(brief), *extra],
                          capture_output=True, text=True, cwd=tmp_path, check=False)


def test_the_command_line_refuses_a_criterion_that_accepts_the_wrong_build(tmp_path: Path) -> None:
    trees = _states(tmp_path)
    brief = _brief(tmp_path, _BEHAVIOUR, _NAME_ONLY)

    done = _cli(tmp_path, brief, "--repo-root", str(trees["current"]),
                "--intended", str(trees["intended"]), "--wrong", str(trees["wrong"]))

    assert done.returncode == 1, done.stdout + done.stderr
    assert "AC-002" in done.stdout
    assert "wrong" in done.stdout


def test_the_command_line_passes_when_every_criterion_discriminates(tmp_path: Path) -> None:
    trees = _states(tmp_path)

    done = _cli(tmp_path, _brief(tmp_path, _BEHAVIOUR), "--repo-root", str(trees["current"]),
                "--intended", str(trees["intended"]), "--wrong", str(trees["wrong"]), "--json")

    assert done.returncode == 0, done.stdout + done.stderr
    assert [v["verdict"] for v in json.loads(done.stdout)["verdicts"]] == ["discriminates"]


def test_a_failed_control_is_not_a_measurement(tmp_path: Path) -> None:
    """Exit 2: every other answer in the run is unattributable."""
    trees = _states(tmp_path)
    broken = _tree(tmp_path, "baseline", "def add(a, b):\n    return a + b\n")

    done = _cli(tmp_path, _brief(tmp_path, _BEHAVIOUR), "--repo-root", str(trees["current"]),
                "--intended", str(trees["intended"]), "--wrong", str(trees["wrong"]),
                "--baseline", str(broken))

    assert done.returncode == 2, done.stdout + done.stderr
    assert "control" in done.stdout.lower()


def test_without_the_extra_states_the_single_state_run_is_unchanged(tmp_path: Path) -> None:
    trees = _states(tmp_path)

    done = _cli(tmp_path, _brief(tmp_path, _BEHAVIOUR), "--repo-root", str(trees["current"]))

    assert done.returncode == 0, done.stdout + done.stderr
    assert "fail today" in done.stdout

"""Tests for check_wiring.py — verifies the triad enforcement."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parent.parent / "scripts" / "check_wiring.py"


def _run_wiring(symbol: str, project_root: Path, metric: str | None = None) -> tuple[int, dict]:
    args = [sys.executable, str(SCRIPT), "--symbol", symbol, "--project-root", str(project_root)]
    if metric:
        args.extend(["--metric", metric])
    result = subprocess.run(args, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw": result.stdout, "stderr": result.stderr}
    return result.returncode, data


def test_pillar_a_fail_when_zero_callers(fake_project: Path) -> None:
    """Symbol with no callers in src/ → pillar (a) FAIL → verdict HALT."""
    rc, data = _run_wiring("nonExistentSymbol123", fake_project)
    assert rc == 1
    assert data["verdict"] == "HALT"
    pillar_a = next(p for p in data["pillars"] if p["pillar"] == "a_static_caller")
    assert pillar_a["status"] == "FAIL"


def test_pillar_a_pass_with_real_caller(fake_project: Path) -> None:
    """Symbol referenced in a production file → pillar (a) PASS."""
    (fake_project / "src" / "uses-it.ts").write_text(
        "export function myCaller() { rememberFact('hello'); }\n",
        encoding="utf-8",
    )
    rc, data = _run_wiring("rememberFact", fake_project)
    pillar_a = next(p for p in data["pillars"] if p["pillar"] == "a_static_caller")
    # rc=1 because pillar b will fail (no integration test), but pillar a should PASS
    assert pillar_a["status"] == "PASS"


def test_pillar_b_fail_when_no_integration_test(fake_project: Path) -> None:
    """No file in tests/integration/ references symbol → pillar (b) FAIL."""
    (fake_project / "src" / "uses-it.ts").write_text(
        "export function caller() { mySymbol(); }\n", encoding="utf-8"
    )
    rc, data = _run_wiring("mySymbol", fake_project)
    pillar_b = next(p for p in data["pillars"] if p["pillar"] == "b_integration_test")
    assert pillar_b["status"] == "FAIL"


def test_pillar_b_pass_when_integration_test_exists(fake_project: Path) -> None:
    """File in tests/integration/ references symbol → pillar (b) PASS."""
    (fake_project / "src" / "uses-it.ts").write_text(
        "export function caller() { mySymbol(); }\n", encoding="utf-8"
    )
    (fake_project / "tests" / "integration" / "test.ts").write_text(
        "test('uses mySymbol', () => { mySymbol(); });\n", encoding="utf-8"
    )
    rc, data = _run_wiring("mySymbol", fake_project)
    pillar_b = next(p for p in data["pillars"] if p["pillar"] == "b_integration_test")
    assert pillar_b["status"] == "PASS"


def test_pillar_c_na_when_no_metric(fake_project: Path) -> None:
    """No metric declared → pillar (c) is N/A."""
    rc, data = _run_wiring("anySymbol", fake_project)
    pillar_c = next(p for p in data["pillars"] if p["pillar"] == "c_runtime_metric")
    assert pillar_c["status"] == "N/A"


def test_pillar_c_fail_when_metric_declared_but_evidence_missing(fake_project: Path) -> None:
    """Metric declared but no .wiring-evidence.json → pillar (c) FAIL."""
    rc, data = _run_wiring("anySymbol", fake_project, metric="memory.add.count")
    pillar_c = next(p for p in data["pillars"] if p["pillar"] == "c_runtime_metric")
    assert pillar_c["status"] == "FAIL"


def test_pillar_c_pass_with_evidence(fake_project: Path) -> None:
    """Metric declared and observed > 0 in .wiring-evidence.json → pillar (c) PASS."""
    evidence = fake_project / ".wiring-evidence.json"
    evidence.write_text(json.dumps({"memory.add.count": 12}), encoding="utf-8")
    rc, data = _run_wiring("anySymbol", fake_project, metric="memory.add.count")
    pillar_c = next(p for p in data["pillars"] if p["pillar"] == "c_runtime_metric")
    assert pillar_c["status"] == "PASS"
    assert pillar_c["count_observed"] == 12


# ---------------------------------------------------------------------------
# B-081 — a duplicate checkout inside the repository is not a second caller.
#
# MEASURED BEFORE THESE WERE WRITTEN, against theokit-tui@adf4cbf:
#
#     clean tree                                    SlashMenuList -> 5 callers
#     `.claude/worktrees/probe` present (ignored)                 -> 5
#     `probe-wt-b081/` also present (NOT ignored)                 -> 10
#
# With both present, all three entries of `callers_sample` were under `probe-wt-b081/` and none
# under `src/`. Pillar (a) is the non-negotiable one, so this is a false PASS in the gate that
# decides whether a symbol is wired into production at all.
#
# The upstream fix — `.claude` added to `exclude_dirs` — is the middle row. It cannot reach the
# bottom one, because `--exclude-dir` matches a NAME and a duplicate checkout can be called
# anything. That is why these tests use a worktree with an arbitrary name.
#
# DETECTION POWER, measured after the fix rather than predicted: making `_nested_worktree_paths`
# return `[]` gives **1 failed, 10 passed**; restored, 11 passed.
#
# ONE, not two, and the reason is the useful part. The `.claude/worktrees/` test survives the
# mutant because `exclude_dirs` already carries `.claude` — that test is a REGRESSION GUARD for
# the upstream fix, not a driver for this one. Only the arbitrarily-named checkout exercises what
# was added here, which is the same asymmetry the measurement on the real repository showed.


def _caller_count(symbol: str, root: Path) -> int:
    _, data = _run_wiring(symbol, root)
    pillar_a = next(p for p in data["pillars"] if p["pillar"] == "a_static_caller")
    return int(pillar_a["callers_count"])


def _add_worktree(root: Path, relative: str) -> None:
    subprocess.run(
        ["git", "worktree", "add", "--detach", "-q", relative, "HEAD"],
        cwd=root, check=True, capture_output=True,
    )


def test_a_caller_inside_a_nested_worktree_is_not_counted(git_project: Path) -> None:
    """A duplicate checkout with an ARBITRARY name — the case a name-based exclusion misses."""
    before = _caller_count("targetSymbol", git_project)
    _add_worktree(git_project, "some-scratch-copy")

    assert _caller_count("targetSymbol", git_project) == before


def test_a_nested_worktree_under_a_gitignored_path_is_not_counted(git_project: Path) -> None:
    """The case the upstream `.claude` exclusion already covers — pinned so it cannot regress."""
    before = _caller_count("targetSymbol", git_project)
    (git_project / ".claude" / "worktrees").mkdir(parents=True)
    _add_worktree(git_project, ".claude/worktrees/agent-1")

    assert _caller_count("targetSymbol", git_project) == before


def test_a_clean_project_still_counts_its_real_caller(git_project: Path) -> None:
    """A filter that also removes real callers has replaced one wrong answer with another."""
    assert _caller_count("targetSymbol", git_project) >= 1


def test_a_project_that_is_not_a_git_repository_still_counts_callers(fake_project: Path) -> None:
    """`git worktree list` fails outside a repository; the gate must degrade, not die.

    Over-counting is the defect being fixed, but a gate that raises where it used to answer is a
    worse trade — it turns an inflated number into no number at all.
    """
    (fake_project / "src" / "uses-it.ts").write_text(
        "export function caller() { return targetSymbol(1); }\n", encoding="utf-8"
    )
    assert _caller_count("targetSymbol", fake_project) >= 1


def test_a_caller_inside_a_nested_CLONE_is_not_counted(git_project: Path) -> None:
    """B-104 — found by reviewing B-081's fix, which this case defeats.

    `git worktree list` is authoritative for worktrees and knows nothing about a CLONE: a clone is
    a separate repository, so it is absent from the register B-081's fix consults. Measured on
    theokit-tui with `git clone --local . ./nested-clone`: pillar (a) went 5 -> 10 and all three
    sampled callers were inside the clone — the exact symptom B-081 exists to prevent, through a
    door its fix does not close.

    The signal that covers both is git's own layout convention: a checkout carries a `.git` entry
    at its root — a FILE for a linked worktree, a DIRECTORY for a clone. Either way, a directory
    holding one is a different checkout and its files are not this project's callers.
    """
    before = _caller_count("targetSymbol", git_project)
    subprocess.run(
        ["git", "clone", "-q", "--local", "--no-hardlinks", ".", "vendored-copy"],
        cwd=git_project, check=True, capture_output=True,
    )

    assert _caller_count("targetSymbol", git_project) == before

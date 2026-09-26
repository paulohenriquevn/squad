"""A wiring summary that could not locate some of its symbols does not read PASS.

Measured on a consumer: `{"symbols_resolved": 17, "pillar_a_fails": 0, "status": "PASS"}`, where the
four exports of the file under review were among 11 symbols the checker never located — the module
lives in `scripts/`, and the search covers `src/`, `lib/` and `packages/` when any of them exists.
Naming the unresolved symbols (`symbols_unresolved`) made them visible; the status still said PASS.

The status is now `INCONCLUSIVE`: not FAIL, because nothing was found unwired, and not PASS, because
part of the subject was never looked at. It does not block — a derived or dynamic name legitimately
does not resolve, and a gate that fires on ordinary work is one somebody switches off — and the
report names the directories that were searched, so a consumer whose source lives in `apps/` or
`scripts/` can see why nothing there resolved.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mini_review import _aggregate_wiring
from run_validation import check_census, overall_status, wiring_summary


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout


def _repo_with_a_module_outside_the_searched_dirs(tmp_path: Path) -> tuple[Path, str]:
    """`src/` holds a wired symbol; `scripts/tool.py` holds an export the search never reaches."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "scripts").mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    (repo / "src" / "order.py").write_text("def compute_total(x):\n    return x\n", encoding="utf-8")
    (repo / "scripts" / "tool.py").write_text("def tool_export(x):\n    return x\n",
                                              encoding="utf-8")
    _git(repo, "add", "src/order.py", "scripts/tool.py")
    _git(repo, "commit", "-q", "-m", "feat: add both")
    sha = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "src" / "app.py").write_text(
        "from order import compute_total\nprint(compute_total(1))\n", encoding="utf-8")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-q", "-m", "feat: call it")
    return repo, sha


def _write_progress(repo: Path, sha: str, slug: str = "wsg") -> Path:
    impl_dir = repo / ".claude" / "records" / "implementations"
    impl_dir.mkdir(parents=True, exist_ok=True)
    path = impl_dir / f".progress-{slug}.json"
    path.write_text(json.dumps({"slug": slug, "tasks": [
        {"id": "T1.1", "phase": "1", "status": "committed", "commit_sha": sha},
    ]}), encoding="utf-8")
    return path


def test_the_final_gate_does_not_pass_over_an_unlocated_symbol(tmp_path: Path) -> None:
    repo, sha = _repo_with_a_module_outside_the_searched_dirs(tmp_path)
    _write_progress(repo, sha)

    result = wiring_summary(repo, "wsg")

    assert result["status"] == "INCONCLUSIVE"
    assert result["symbols_unresolved"] == ["tool_export"]
    assert result["searched_roots"] == ["src"]
    assert "tool_export" in result["reason"] and "src" in result["reason"]


def test_the_phase_boundary_does_not_pass_over_an_unlocated_symbol(tmp_path: Path) -> None:
    repo, sha = _repo_with_a_module_outside_the_searched_dirs(tmp_path)
    progress = _write_progress(repo, sha)

    result = _aggregate_wiring(progress, "1", repo)

    assert result["status"] == "INCONCLUSIVE"
    assert result["searched_roots"] == ["src"]
    # Named in a finding, and not a blocking one: nothing was found unwired.
    unresolved = [f for f in result["findings"] if f["code"] == "wiring_symbols_unresolved"]
    assert len(unresolved) == 1 and unresolved[0]["severity"] == "MEDIUM"
    assert "tool_export" in unresolved[0]["message"]


def test_a_run_with_an_inconclusive_check_is_partial_not_pass() -> None:
    census = check_census([{"name": "a", "status": "PASS"},
                           {"name": "wiring_triad", "status": "INCONCLUSIVE"}])

    assert overall_status(census) == "PARTIAL"


def test_an_inconclusive_check_does_not_outrank_a_failure() -> None:
    census = check_census([{"name": "a", "status": "FAIL"},
                           {"name": "wiring_triad", "status": "INCONCLUSIVE"}])

    assert overall_status(census) == "FAIL"

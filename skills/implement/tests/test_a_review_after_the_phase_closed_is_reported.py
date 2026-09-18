"""The HIGH finding this check exists for could not be produced outside the tests.

`check_phase_review(..., repo_root=None)` defaults the argument `_check_ordering` needs
to compare the review's recorded head against the phase's last commit. Both production
call sites omitted it — `run_validation.py` and this module's own `main` — so
`_is_ancestor` never ran in production, every phase came back `ordering_not_checkable`
(INFO), and `retroactive_review` (HIGH) was unreachable outside the suite.

A mini-review that ran after its phase closed gated nothing. That is the finding.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "implement" / "scripts"))

from check_phase_review import _check_ordering  # noqa: E402 — post-bootstrap import


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True,  # noqa: E731
                                    capture_output=True)
    run("init", "-q")
    env = ("-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false")
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    run("add", "-A")
    subprocess.run(["git", "-C", str(repo), *env, "commit", "-qm", "phase 1"], check=True)
    first = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    run("add", "-A")
    subprocess.run(["git", "-C", str(repo), *env, "commit", "-qm", "later"], check=True)
    later = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()
    return repo, first, later


def _ordering(tmp_path: Path, repo: Path | None, phase_last: str, reviewed_at: str) -> list:
    """The two artefacts as they are on disk: a report FILE and a progress dict."""
    report = tmp_path / "a-slug-phase-1-review.md"
    report.write_text(f"# Mini review\n\nReviewed at head: `{reviewed_at}`\n",
                      encoding="utf-8")
    progress = {"tasks": [{"phase": "1", "commit_sha": phase_last}]}
    return _check_ordering(report, progress, "1", repo)


def test_a_review_at_a_descendant_commit_is_reported_high(tmp_path: Path) -> None:
    repo, first, later = _repo(tmp_path)

    findings = _ordering(tmp_path, repo, phase_last=first, reviewed_at=later)

    assert [f.code for f in findings] == ["retroactive_review"], findings
    assert findings[0].severity == "HIGH"


def test_a_review_at_the_phase_head_is_clean(tmp_path: Path) -> None:
    repo, first, _ = _repo(tmp_path)

    assert _ordering(tmp_path, repo, phase_last=first, reviewed_at=first) == []


def test_without_a_repo_root_the_check_says_it_could_not_run(tmp_path: Path) -> None:
    """The state both production callers used to be in, permanently."""
    _, first, later = _repo(tmp_path)

    findings = _ordering(tmp_path, None, phase_last=first, reviewed_at=later)

    assert [f.code for f in findings] == ["ordering_not_checkable"]

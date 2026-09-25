"""The base a review diffs against is resolved from the repository, never assumed.

`/review` told the agent to run `detect_domain.py --diff-base main` and the auditors
with `--diff-base main`. Measured on this kit's own repository on 2026-09-23: it has
neither `main` nor `origin/main` — its integration branch is `develop`
(`git-safety.md` § 1). Every plugin refused the ref, and `detect_domain.py` hit the
identical git error, swallowed it and returned an empty file list, so the domains
came from the plan alone and the review looked routed.

Three behaviours are pinned here:

- a base that does not resolve is a loud error (exit 2, naming the ref), never an
  empty domain list;
- with no base named, the integration branch is resolved and reported, so the same
  ref can be handed on to the auditors and the reviewers;
- the changed files are the THREE-dot set (`base...HEAD`), the one the plugins audit.
  Two dots also count every commit that landed on the base since the fork, so once
  the branches diverge the domains were derived from files the change never touched.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
DETECT = SCRIPTS / "detect_domain.py"
SPAWN = SCRIPTS / "spawn_reviewers.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def _commit(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"add {rel}")


@pytest.fixture
def diverged_repo(tmp_path: Path) -> Path:
    """`develop` and `workspace` forked, then both moved on. HEAD is `workspace`.

    The change under review touches only `src/auth/login.py`. `develop` meanwhile
    gained `deploy/Dockerfile`, which a two-dot diff attributes to the change.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "develop")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _commit(repo, "README.md", "seed\n")
    _git(repo, "switch", "-q", "-c", "workspace")
    _commit(repo, "src/auth/login.py", "def login(): ...\n")
    _git(repo, "switch", "-q", "develop")
    _commit(repo, "deploy/Dockerfile", "FROM scratch\n")
    _git(repo, "switch", "-q", "workspace")
    return repo


@pytest.fixture
def plan(tmp_path: Path) -> Path:
    p = tmp_path / "plan.md"
    p.write_text("# Plan\n\nAdd authentication with a JWT on login and RBAC permission.\n",
                 encoding="utf-8")
    return p


def _detect(plan: Path, repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DETECT), "--plan", str(plan), "--project-root", str(repo), *extra],
        capture_output=True, text=True, check=False)


def test_an_unresolvable_base_fails_loudly_instead_of_returning_no_files(
        diverged_repo: Path, plan: Path) -> None:
    result = _detect(plan, diverged_repo, "--diff-base", "main")

    assert result.returncode == 2, result.stdout
    assert "'main'" in result.stderr
    assert result.stdout == ""


def test_with_no_base_named_the_integration_branch_is_resolved_and_reported(
        diverged_repo: Path, plan: Path) -> None:
    result = _detect(plan, diverged_repo)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["diff_base"] == "develop"


def test_a_base_present_only_on_the_remote_resolves_to_the_remote_ref(
        diverged_repo: Path, plan: Path, tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "-b", "workspace", str(diverged_repo), str(clone)],
                   check=True, capture_output=True)

    result = _detect(plan, clone)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["diff_base"] == "origin/develop"


def test_the_files_counted_are_the_three_dot_set_the_auditors_see(
        diverged_repo: Path, plan: Path) -> None:
    three_dot = _git(diverged_repo, "diff", "--name-only", "develop...HEAD").splitlines()

    result = _detect(plan, diverged_repo, "--diff-base", "develop")

    assert result.returncode == 0, result.stderr
    assert three_dot == ["src/auth/login.py"]
    assert json.loads(result.stdout)["files_in_diff"] == len(three_dot)


def test_the_reviewers_are_not_briefed_against_a_base_that_does_not_exist(
        diverged_repo: Path, plan: Path, tmp_path: Path) -> None:
    out = tmp_path / "agents"
    result = subprocess.run(
        [sys.executable, str(SPAWN), "--plan", str(plan), "--slug", "demo",
         "--primary-domain", "auth", "--output-dir", str(out), "--no-skills",
         "--skill-dir", str(SCRIPTS.parent),
         "--project-root", str(diverged_repo)],
        capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    brief = (out / "architecture.md").read_text(encoding="utf-8")
    assert "git diff develop...HEAD" in brief
    assert "main..HEAD" not in brief

"""`gh` refuses an SSH host alias, and a GitHub repository is still a GitHub repository.

A remote spelled `github-usetheo:usetheoai/theo.git` — a `Host` entry in
`~/.ssh/config` — makes `gh repo view` answer *"none of the git remotes point to a known
GitHub host"*. Measured on a consumer 2026-09-16: the board's entire issues panel was
dark for that reason, and the tracker held **124 issues** the whole time.

The failure printed a real remedy — pass `OWNER/NAME` explicitly — which works and asks
the operator to read the remote and retype what is already there. Derived is better than
demanded when the answer is on disk.

The parse is the one `mechanisms/cycle/promote_to_develop.py` already does for `gh -R`,
for the same alias, found the same week. Both URL shapes carry the slug in the same
place, so it reads the tail and never the host.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_issues import _owner_repo_from_remote  # noqa: E402


def _repo_with_remote(tmp_path: Path, url: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["remote", "add", "origin", url]):
        subprocess.run(["git", *args], cwd=repo, check=True, timeout=120,
                       capture_output=True)
    return repo


def test_an_ssh_host_alias_resolves(tmp_path: Path) -> None:
    repo = _repo_with_remote(tmp_path, "github-usetheo:usetheoai/theo.git")
    assert _owner_repo_from_remote(repo) == "usetheoai/theo"


def test_the_ordinary_ssh_form_resolves(tmp_path: Path) -> None:
    repo = _repo_with_remote(tmp_path, "git@github.com:owner/name.git")
    assert _owner_repo_from_remote(repo) == "owner/name"


def test_the_https_form_resolves(tmp_path: Path) -> None:
    """The scheme carries a `:` too, so it is stripped before the host is split — or the
    parse would start after `//` and produce a different repository."""
    repo = _repo_with_remote(tmp_path, "https://github.com/owner/name.git")
    assert _owner_repo_from_remote(repo) == "owner/name"


def test_a_remote_shaped_like_neither_answers_nothing(tmp_path: Path) -> None:
    """An empty string leaves the call unscoped and the behaviour exactly as it was. A
    guessed repository would query someone else's tracker."""
    repo = _repo_with_remote(tmp_path, "/srv/git/bare.git")
    assert _owner_repo_from_remote(repo) == ""


def test_no_remote_at_all_answers_nothing(tmp_path: Path) -> None:
    repo = tmp_path / "solo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, timeout=120,
                   capture_output=True)
    assert _owner_repo_from_remote(repo) == ""

"""Behavioural tests for hooks/stop-validation.sh.

The gate decides whether a session may end, so its false positives are as
expensive as its misses: a gate that blocks a read-only session teaches people
to pass STOP_VALIDATION_WARN_ONLY=1 by reflex, and then it stops protecting
anything.

Each test builds a throwaway git repository and runs the real hook against it.
Exit codes are the contract: 0 = clean or advisory, 2 = hard-gate violation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "stop-validation.sh"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def make_repo(tmp_path: Path, *, with_remote: bool) -> Path:
    """A repo the hook recognises as an ecosystem, with one baseline commit."""
    repo = tmp_path / "repo"
    # Standalone layout: detect-layout.sh looks for skills/ rules/ hooks/ at the
    # root. A plugin-install fixture would be filtered out by the `.claude/`
    # exclusion this hook applies, and the gates would see an empty file set.
    for sub in ("skills", "rules", "hooks"):
        (repo / sub).mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "workspace")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n")
    (repo / "rules" / "keep").write_text("")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "baseline")

    if with_remote:
        bare = tmp_path / "origin.git"
        git(repo, "init", "-q", "--bare", str(bare))
        git(repo, "remote", "add", "origin", str(bare))
        git(repo, "push", "-q", "-u", "origin", "workspace")
    return repo


def commit_source(repo: Path, path: str = "src/thing.ts") -> None:
    """A commit that touches production source and no changelog."""
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("export const thing = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "feat: thing")


class HookRun:
    """The hook writes advisories to stdout and hard-gate blocks to stderr."""

    def __init__(self, proc: subprocess.CompletedProcess[str]) -> None:
        self.returncode = proc.returncode
        self.output = proc.stdout + proc.stderr


def run_hook(repo: Path) -> HookRun:
    return HookRun(
        subprocess.run(
            ["bash", str(HOOK)],
            cwd=repo,
            capture_output=True,
            text=True,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "CLAUDE_PROJECT_DIR": str(repo),
            },
        )
    )


# --- Defect 1: an already-published commit is not this session's work -------


def test_read_only_session_does_not_inherit_a_pushed_commits_verdict(tmp_path):
    """Nothing changed this session; the last commit is already on the remote."""
    repo = make_repo(tmp_path, with_remote=True)
    commit_source(repo)
    git(repo, "push", "-q", "origin", "workspace")

    result = run_hook(repo)

    assert result.returncode == 0, result.output
    assert "CHANGELOG.md not updated" not in result.output


def test_unpushed_commit_without_changelog_still_blocks(tmp_path):
    """The gate's real purpose: the session committed source and is stopping."""
    repo = make_repo(tmp_path, with_remote=True)
    commit_source(repo)  # committed, never pushed

    result = run_hook(repo)

    assert result.returncode == 2, result.output
    assert "CHANGELOG.md not updated" in result.output


def test_without_an_upstream_the_last_commit_is_still_graded(tmp_path):
    """No upstream means no way to tell published from local — stay strict."""
    repo = make_repo(tmp_path, with_remote=False)
    commit_source(repo)

    result = run_hook(repo)

    assert result.returncode == 2, result.output
    assert "CHANGELOG.md not updated" in result.output


def test_uncommitted_source_without_changelog_blocks(tmp_path):
    """Working-tree changes are always this session's, pushed or not."""
    repo = make_repo(tmp_path, with_remote=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "thing.ts").write_text("export const thing = 1\n")
    git(repo, "add", "-A")

    result = run_hook(repo)

    assert result.returncode == 2, result.output


# --- Defect 2: a changeset is a changelog record ----------------------------


def test_a_changeset_satisfies_the_changelog_gate(tmp_path):
    """Six packages here publish through .changeset/, not the root CHANGELOG."""
    repo = make_repo(tmp_path, with_remote=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "thing.ts").write_text("export const thing = 1\n")
    (repo / ".changeset").mkdir(parents=True, exist_ok=True)
    (repo / ".changeset" / "brave-pans-sing.md").write_text(
        "---\n'pkg': minor\n---\n\nthing\n"
    )
    git(repo, "add", "-A")

    result = run_hook(repo)

    assert result.returncode == 0, result.output
    assert "CHANGELOG.md not updated" not in result.output


def test_a_package_changelog_satisfies_the_gate(tmp_path):
    """Per-package CHANGELOG.md is the documented home for package changes."""
    repo = make_repo(tmp_path, with_remote=True)
    pkg = repo / "packages" / "thing"
    (pkg / "src").mkdir(parents=True, exist_ok=True)
    (pkg / "src" / "thing.ts").write_text("export const thing = 1\n")
    (pkg / "CHANGELOG.md").write_text("# thing\n\n## 1.0.1\n")
    git(repo, "add", "-A")

    result = run_hook(repo)

    assert result.returncode == 0, result.output


def test_changeset_scaffolding_is_not_a_record(tmp_path):
    """.changeset/README.md and config.json ship with the tool; they record nothing."""
    repo = make_repo(tmp_path, with_remote=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "thing.ts").write_text("export const thing = 1\n")
    (repo / ".changeset").mkdir(parents=True, exist_ok=True)
    (repo / ".changeset" / "README.md").write_text("# Changesets\n")
    (repo / ".changeset" / "config.json").write_text("{}\n")
    git(repo, "add", "-A")

    result = run_hook(repo)

    assert result.returncode == 2, result.output
    assert "CHANGELOG.md not updated" in result.output


# --- Defect 4: a new file is invisible to `git diff` -------------------------


def test_an_untracked_changeset_satisfies_the_gate(tmp_path):
    """Every changeset is a brand-new file, so untracked must count.

    `git diff` lists tracked modifications only. Without this the changeset
    branch of the gate can never be satisfied by the artifact it names.
    """
    repo = make_repo(tmp_path, with_remote=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "thing.ts").write_text("export const thing = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "wip")  # source is committed but unpushed
    (repo / ".changeset").mkdir(parents=True, exist_ok=True)
    (repo / ".changeset" / "new-entry.md").write_text("---\n'pkg': patch\n---\n\nx\n")
    # deliberately NOT `git add`ed

    result = run_hook(repo)

    assert result.returncode == 0, result.output


def test_an_untracked_source_file_is_still_graded(tmp_path):
    """A new .ts nobody staged is still this session's production change."""
    repo = make_repo(tmp_path, with_remote=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "brand-new.ts").write_text("export const x = 1\n")

    result = run_hook(repo)

    assert result.returncode == 2, result.output
    assert "CHANGELOG.md not updated" in result.output


def test_gitignored_files_are_not_graded(tmp_path):
    """Ignored output is not the session's work — --exclude-standard honours that."""
    repo = make_repo(tmp_path, with_remote=True)
    (repo / ".gitignore").write_text("dist/\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "ignore dist")
    git(repo, "push", "-q", "origin", "workspace")
    (repo / "dist").mkdir(parents=True, exist_ok=True)
    (repo / "dist" / "bundle.ts").write_text("export const x = 1\n")

    result = run_hook(repo)

    assert result.returncode == 0, result.output


# --- Defect 5: "no obtainable diff" is not "no change" -----------------------


def test_a_brand_new_source_file_full_of_code_is_graded(tmp_path):
    """The comment-only filter must not swallow a file that has no prior version.

    `git diff HEAD~1 -- <new file>` is empty, which reads identically to "the
    diff carried only comments". Treating the two the same lets an entire new
    module skip the gate — a false negative, in the one direction the filter's
    own rationale claims is impossible.
    """
    repo = make_repo(tmp_path, with_remote=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "payments.ts").write_text(
        "export function charge(cents: number): number {\n"
        "  if (cents < 0) throw new Error('negative')\n"
        "  return Math.round(cents * 1.05)\n"
        "}\n"
    )

    result = run_hook(repo)

    assert result.returncode == 2, result.output
    assert "CHANGELOG.md not updated" in result.output


def test_a_new_file_of_pure_comments_is_not_graded(tmp_path):
    """The filter's real purpose survives: a comment-only file announces nothing."""
    repo = make_repo(tmp_path, with_remote=True)
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "notes.ts").write_text("// a note\n// another note\n")

    result = run_hook(repo)

    assert result.returncode == 0, result.output


# --- Defect 3: tests live in a per-package tree, not only beside the source --


def test_a_test_in_the_packages_test_tree_counts_as_paired(tmp_path):
    """packages/<p>/tests/unit/<name>.test.ts is this repository's convention."""
    repo = make_repo(tmp_path, with_remote=True)
    pkg = repo / "packages" / "thing"
    (pkg / "src").mkdir(parents=True, exist_ok=True)
    (pkg / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (pkg / "package.json").write_text('{"name":"thing"}\n')
    (pkg / "src" / "bot-preset.ts").write_text("export const p = 1\n")
    (pkg / "tests" / "unit" / "bot-preset.test.ts").write_text("test('x', () => {})\n")
    (repo / ".changeset").mkdir(parents=True, exist_ok=True)
    (repo / ".changeset" / "x.md").write_text("---\n'thing': patch\n---\n\nx\n")
    git(repo, "add", "-A")

    result = run_hook(repo)

    assert "bot-preset.ts" not in result.output, result.output


def test_source_with_no_test_anywhere_still_warns(tmp_path):
    """The gate must keep catching genuinely untested source."""
    repo = make_repo(tmp_path, with_remote=True)
    pkg = repo / "packages" / "thing"
    (pkg / "src").mkdir(parents=True, exist_ok=True)
    (pkg / "package.json").write_text('{"name":"thing"}\n')
    (pkg / "src" / "lonely.ts").write_text("export const p = 1\n")
    (repo / ".changeset").mkdir(parents=True, exist_ok=True)
    (repo / ".changeset" / "x.md").write_text("---\n'thing': patch\n---\n\nx\n")
    git(repo, "add", "-A")

    result = run_hook(repo)

    assert "lonely.ts" in result.output, result.output


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

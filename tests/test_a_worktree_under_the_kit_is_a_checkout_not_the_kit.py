"""A reviewer's worktree landed inside `.claude/`, and the boundary hook refused its writes.

Measured 2026-09-20 during a `/review`. `git worktree list` placed every spawned reviewer
at `.claude/worktrees/agent-<id>`, which is where the harness puts them. The architecture
reviewer then found both paths to its findings file closed: the shared checkout by the
worktree isolation the brief asks for, and its own worktree by `boundary-check.py`, whose
docstring refuses writes *"into an installed kit"* — and a path under `.claude/` resolves
to exactly that. It got its 14120-byte findings file onto disk by staging in `/tmp` and
copying. Nothing in the brief tells it to; it improvised, and the next reviewer who does
not improvise loses its findings at the last step, after the whole review ran. An absent
findings file is indistinguishable from a reviewer that found nothing.

NEITHER SIDE HAD TO MOVE, and the reason is worth recording. Re-measured 2026-09-22
against that consumer's own installed hooks, with `CLAUDE_PROJECT_DIR` set so the layout
resolves as it does in a session:

    .claude/worktrees/agent-7f3a/.squad/.../findings/a.yml   boundary-check    exit 0
    .claude/mechanisms/cycle/cast_vote.py                    boundary-check    exit 2
    a heredoc, a tee and a python -c at the worktree path    validate-command  exit 0

The refusal does not reproduce. `is_project_owned` asks whether the install MANIFEST claims
a path rather than whether it sits under `.claude/`, and no manifest claims `worktrees/` —
so a worktree was already the project's. What this file pins is that it stays that way: the
behaviour is correct, was never asserted anywhere, and a later tightening of the boundary
would silently take it away again.

What DID need fixing was the brief, and it was a contradiction rather than a mechanism. The
same template says *"never in the shared tree"* and *"scratch files go under /tmp, never
under the repository"*, and then *"save to {FINDINGS_DIR}"* — an absolute path in the shared
checkout. A reviewer reading all three has no legal way to deliver its findings, which is
why one of them staged in `/tmp` and copied. The templates now name the findings file as the
one expected write into the shared tree.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from squad.boundaries import Layout, violation  # noqa: E402


def _installed(tmp_path: Path) -> Layout:
    project = tmp_path / "consumer"
    kit = project / ".claude"
    (kit / "mechanisms").mkdir(parents=True)
    (kit / ".kit-manifest.txt").write_text("mechanisms\nrules/cycle-review.md\n",
                                           encoding="utf-8")
    return Layout(kit_dir=kit, eco=kit, project_dir=project, kind="copy")


def test_a_findings_file_in_an_agent_worktree_is_writable(tmp_path: Path) -> None:
    layout = _installed(tmp_path)
    target = (layout.kit_dir / "worktrees" / "agent-7f3a" / ".squad" / "records"
              / "reviews" / "review-a-slug" / "findings" / "architecture.yml")

    assert violation(target, layout) is None, (
        "the reviewer's own worktree is the one place its brief tells it to write"
    )


def test_source_inside_a_worktree_is_writable_too(tmp_path: Path) -> None:
    """A worktree is a checkout. Half-opening it would send the reviewer back to /tmp."""
    layout = _installed(tmp_path)
    target = layout.kit_dir / "worktrees" / "agent-7f3a" / "src" / "thing.ts"

    assert violation(target, layout) is None


def test_the_kit_itself_is_still_refused(tmp_path: Path) -> None:
    """THE CONTROL. The boundary moved by one directory, not by a principle."""
    layout = _installed(tmp_path)

    refusal = violation(layout.kit_dir / "mechanisms" / "cycle" / "cast_vote.py", layout)

    assert refusal is not None
    assert "BOUNDARY VIOLATION" in refusal


def test_the_brief_names_the_findings_file_as_the_expected_write(tmp_path: Path) -> None:
    """The half that WAS broken: a brief a reviewer cannot obey without improvising.

    One template told the reviewer never to write in the shared tree, never to put files
    under the repository, and to save its findings to an absolute path in the shared tree.
    All three at once. The reviewer that noticed staged in `/tmp` and copied; the one that
    does not notice loses its file at the last step, after the whole review has run.
    """
    templates = sorted((_ROOT / "skills" / "review" / "templates").glob("agent-*-reviewer.md"))
    assert templates
    for path in templates:
        text = path.read_text(encoding="utf-8")
        assert "one exception, and it is expected" in text, (
            f"{path.name} forbids the write it also requires"
        )


def test_the_kit_ships_no_worktrees_directory() -> None:
    """The premise the hole rests on, asserted rather than assumed.

    If the kit ever shipped `worktrees/`, everything in it would become writable in every
    consumer — and the exemption would have widened silently, which is the failure mode
    this kit keeps finding in its own gates.
    """
    assert not (_ROOT / "worktrees").exists()
    manifest = (_ROOT / ".kit-manifest.txt")
    if manifest.is_file():
        assert "worktrees" not in manifest.read_text(encoding="utf-8")

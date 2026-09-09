"""What produced an answer, printed beside the answer.

A command can be perfectly deterministic and still mislead: sweeping zero files and
reporting PASS is deterministic. `tests/test_gates_say_what_they_examined.py` records
what that cost — five of six root-taking gates said what they had swept, and the sixth
printed "Overall: PASS — every cycle's declared numbering is unique and in chain order"
after examining zero cycles.

So the header carries the state the answer depends on: which interpreter, which
commit, whether the tree was dirty. Without it a reader cannot tell two runs apart,
and "the same input gives the same output" is unverifiable because the input was
never stated.
"""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def _git(root: Path, *args: str) -> str | None:
    """A git fact, or None. Never raises: git is context here, not the subject."""
    try:
        done = subprocess.run(  # noqa: PLW1510
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def describe(root: Path) -> list[str]:
    """The environment facts every verb prints, most specific first."""
    facts = [f"python {platform.python_version()}"]

    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    head = _git(root, "rev-parse", "--short", "HEAD")
    if branch and head:
        dirty = _git(root, "status", "--porcelain")
        state = "clean" if dirty == "" else f"{len(dirty.splitlines())} file(s) dirty"
        facts.append(f"{branch} @ {head} ({state})")
    else:
        # Not a git repository, or git is absent. Say which rather than omitting the
        # line: a missing fact reads as an unasked question.
        facts.append("no git context")

    return facts

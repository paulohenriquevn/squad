"""The usage block advertised `<path-or-slug>`; only a path resolved.

A slug was resolved as `./<slug>` relative to the caller's working directory, `load()`
returned None, and the user got "NOT SIGNABLE: /cwd/<slug> — no `## Sign-off` section"
with exit 2. That reads as a problem with the document rather than with the argument
form the docstring told them to use — and `waiting()` already knows how to sweep every
directory where the document actually lives.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "sign" / "scripts" / "sign_document.py"

sys.path.insert(0, str(_SCRIPT.parent))
import sign_document  # noqa: E402 — post-bootstrap import


def _document(project: Path, relative: str) -> Path:
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# A design\n\n## Sign-off\n\n- [ ] Reviewed by:\n", encoding="utf-8")
    return path


def test_a_slug_finds_the_document_the_list_would_have_shown(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    target = _document(project, ".squad/records/plans/my-feature-plan.md")

    assert sign_document.resolve_target("my-feature-plan", project) == target


def test_a_path_still_wins_over_a_slug(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    explicit = _document(project, "elsewhere/notes.md")

    assert sign_document.resolve_target(str(explicit), project) == explicit


def test_an_unknown_slug_says_it_is_an_unknown_slug(tmp_path: Path) -> None:
    """Not "this document has no sign-off section" — that sends the reader to the file."""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)

    result = subprocess.run([sys.executable, str(_SCRIPT), "no-such-slug", "--as", "someone"],
                            cwd=project, capture_output=True, text=True, timeout=120, check=False)

    assert result.returncode == 2
    assert "no-such-slug" in result.stderr + result.stdout
    combined = (result.stderr + result.stdout).lower()
    assert "slug" in combined or "no document" in combined, combined

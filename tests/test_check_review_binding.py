"""An approval must be bound to the revision it approved.

A review verdict says the work was examined. It did not say WHICH work: nothing
recorded the revision the reviewers read, so a commit landing after consolidation could
travel to `develop` carrying an approval that never saw it.

An external reviewer named the general shape — every approval bound to the exact
revision — and it is the same defect the panel had about its artifact, one layer up: the
approval was bound to a NAME rather than to a CONTENT.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))
sys.path.insert(0, str(_REPO))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_review_binding import (  # noqa: E402 — post-bootstrap import
    BOUND,
    DRIFTED,
    UNCHECKED,
    check,
)

from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@t"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    # Run records are not versioned, here as in a real project. Without this the
    # fixture commits the very record under test and it shows up as a moved file.
    (root / ".gitignore").write_text(".squad/\n", encoding="utf-8")
    return root


def _commit(root: Path, name: str, body: str) -> str:
    (root / name).write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", name], cwd=root, check=True,
                   capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


def _record(root: Path, sha: str, examined: list[str] | None = None) -> None:
    d = write_records_dir(root, "reviews")
    d.mkdir(parents=True, exist_ok=True)
    body = {"slug": "B-014", "verdict": "READY_TO_MERGE", "reviewed_sha": sha}
    if examined is not None:
        body["examined_files"] = examined
    (d / "B-014-review-2026-09-10.json").write_text(json.dumps(body), encoding="utf-8")


def test_a_review_bound_to_the_tip_is_clean(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    sha = _commit(root, "a.py", "x = 1\n")
    _record(root, sha, ["a.py"])

    code, result = check("B-014", project=root)

    assert code == BOUND
    assert result["status"] == "bound"


def test_a_commit_touching_reviewed_files_breaks_the_binding(tmp_path: Path) -> None:
    """The defect: work that landed after the review travels on its approval."""
    root = _repo(tmp_path)
    sha = _commit(root, "a.py", "x = 1\n")
    _record(root, sha, ["a.py"])
    _commit(root, "a.py", "x = 2  # nobody reviewed this\n")

    code, result = check("B-014", project=root)

    assert code == DRIFTED
    assert result["overlap"] == ["a.py"]


def test_a_commit_elsewhere_does_not_block(tmp_path: Path) -> None:
    """A gate that blocked on ANY movement would be bypassed within a week, and a
    bypassed gate protects nothing. It reports what moved and refuses on overlap."""
    root = _repo(tmp_path)
    sha = _commit(root, "a.py", "x = 1\n")
    _record(root, sha, ["a.py"])
    _commit(root, "README.md", "docs\n")

    code, result = check("B-014", project=root)

    assert code == BOUND
    assert result["status"] == "moved_elsewhere"
    assert result["moved"] == ["README.md"]


def test_a_record_listing_no_files_treats_every_move_as_overlap(tmp_path: Path) -> None:
    """Fail-safe direction: unknown scope widens, never narrows."""
    root = _repo(tmp_path)
    sha = _commit(root, "a.py", "x = 1\n")
    _record(root, sha, examined=None)
    _commit(root, "README.md", "docs\n")

    code, result = check("B-014", project=root)

    assert code == DRIFTED
    assert any("WHICH FILES THE REVIEW EXAMINED" in n for n in result["not_checked"])


def test_a_review_naming_no_revision_is_not_a_pass(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _commit(root, "a.py", "x = 1\n")
    d = write_records_dir(root, "reviews")
    d.mkdir(parents=True, exist_ok=True)
    (d / "B-014-review-2026-09-10.json").write_text(
        json.dumps({"slug": "B-014", "verdict": "READY_TO_MERGE"}), encoding="utf-8")

    code, result = check("B-014", project=root)

    assert code == UNCHECKED
    assert result["status"] == "unbound"


def test_an_unresolvable_revision_is_not_a_pass(tmp_path: Path) -> None:
    """A commit nobody can produce is not a binding."""
    root = _repo(tmp_path)
    _commit(root, "a.py", "x = 1\n")
    _record(root, "0" * 40, ["a.py"])

    code, _ = check("B-014", project=root)

    assert code == UNCHECKED


def test_the_gate_states_what_it_cannot_see(tmp_path: Path) -> None:
    """Two branches that pass alone and fail together is a property of the
    integration, not of this branch."""
    root = _repo(tmp_path)
    sha = _commit(root, "a.py", "x = 1\n")
    _record(root, sha, ["a.py"])
    _commit(root, "README.md", "docs\n")

    _, result = check("B-014", project=root)

    assert any("FAIL TOGETHER" in n for n in result["not_checked"])
    assert any("WAS RIGHT" in n for n in result["not_checked"])

"""The review-drift gate read the process working directory, not the repository.

`promote(root, ...)` threads `root` into both subprocess runners (`cwd=root`) and
refuses on branch, tree state and commits-ahead for THAT repository. The drift gate —
the one the comment above it calls the reason promotion is the right place to catch
this — was invoked as `_reviews_that_drifted(Path.cwd())`.

`squad.paths.records_dir` anchors at its argument and performs no upward walk, so
running the promotion from anywhere other than the repository root meant the gate swept
a records directory belonging to a different project, or to none — and reported no
drift either way. A gate that swept the wrong tree and said "clean" is the failure this
whole kit is organised against.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))

import promote_to_develop  # noqa: E402 — post-bootstrap import


def test_the_gate_is_given_the_promoted_root() -> None:
    """The gate moved into `_refuse_on_review_drift`; the question did not."""
    body = inspect.getsource(promote_to_develop._refuse_on_review_drift)

    assert "_reviews_that_drifted(Path.cwd())" not in body, (
        "the gate sweeps the caller's working directory, not the repository being "
        "promoted")
    assert "_reviews_that_drifted(root)" in body, body[-400:]
    assert "_refuse_on_review_drift(root," in inspect.getsource(promote_to_develop.promote)


def test_no_check_in_promote_reads_the_process_directory() -> None:
    """Every other check is anchored on `root`; this one must not be the exception."""
    code = "\n".join(line for line in inspect.getsource(promote_to_develop.promote).splitlines()
                     if not line.strip().startswith("#"))

    assert "Path.cwd()" not in code, (
        "a promotion decided partly by where the operator happened to be standing")

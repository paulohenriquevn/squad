"""A JSON document of the wrong shape is not malformed JSON.

`compute_acceptance_verdict --criteria <a JSON list>` raised
`AttributeError: 'list' object has no attribute 'get'`. A traceback reads as "this tool
is broken" when the honest answer is "your file is a list and this expects an object" —
and the two need different actions from whoever runs the phase.

This kit has met the same failure before and wrote it down: `select_backlog_item`
answered every `--check` against an approved item with a KeyError, and the comment there
says it exactly — a traceback is the wrong silence.

Found by executing ACCEPTANCE against real inputs. It was the only defect the sweep
found: zero criteria already returns `NOT_VALIDATED ... no criteria to validate`, which
is the honest answer to an empty grading.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
           / "compute_acceptance_verdict.py")


def _run(tmp_path: Path, criteria, evidence) -> subprocess.CompletedProcess:
    c, e = tmp_path / "criteria.json", tmp_path / "evidence.json"
    c.write_text(json.dumps(criteria), encoding="utf-8")
    e.write_text(json.dumps(evidence), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--criteria", str(c), "--evidence", str(e),
         "--milestone", "M-999"],
        capture_output=True, text=True, timeout=180,
     check=False)


def test_a_list_where_an_object_belongs_names_the_shape(tmp_path: Path) -> None:
    result = _run(tmp_path, [], {"results": []})
    assert result.returncode == 2, "a wrong-shaped document should not grade anything"
    assert "Traceback" not in result.stderr
    assert "expected a JSON object" in result.stderr
    assert "got list" in result.stderr, "the message does not say what was given"


def test_the_evidence_document_is_checked_too(tmp_path: Path) -> None:
    result = _run(tmp_path, {"criteria": []}, [])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "--evidence" in result.stderr


def test_zero_criteria_is_still_the_honest_verdict(tmp_path: Path) -> None:
    """The shape check must not swallow the empty-grading answer, which was already
    right: an empty criteria list is NOT_VALIDATED, not a crash and not a pass."""
    result = _run(tmp_path, {"criteria": []}, {"results": []})
    assert result.returncode == 1
    assert "NOT_VALIDATED" in result.stderr

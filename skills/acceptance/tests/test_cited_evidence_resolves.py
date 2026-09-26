r"""A cited evidence file that does not exist is not evidence.

`rules/cycle-acceptance.md` puts it in the phase-contract table — the `record` phase's
hard gate is *"evidence files exist at the cited paths"* — and `skills/acceptance/SKILL.md`
repeats it: *"Cite evidence by path; the paths must resolve."* Nothing resolved anything.
`_has_evidence` asked whether the list held a non-empty STRING. Measured:

    evidence=[""]          ->  NOT_VALIDATED
    evidence=["   "]       ->  NOT_VALIDATED
    evidence=["e/x.png"]   ->  ACCEPTED         <- no such file

So the one gate the rule says the whole cycle rests on — *"with the human sign-off
deliberately out of scope, recorded evidence is the only thing standing between a real
validation and a confident sentence"* — was satisfied by typing a plausible filename.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compute_acceptance_verdict.py"

CRITERIA = {"milestone_id": "M1", "criteria": [{"id": "AC1", "text": "tokens stream"}]}


def _run(tmp_path: Path, evidence: list[str], *args: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "criteria.json").write_text(json.dumps(CRITERIA), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps({
        "milestone_id": "M1",
        "target": {"kind": "web", "url": "https://x"},
        "results": [{"id": "AC1", "status": "passed", "evidence": evidence}],
        "defects": [],
    }), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT),
         "--criteria", str(tmp_path / "criteria.json"),
         "--evidence", str(tmp_path / "evidence.json"), *args],
        capture_output=True, text=True, cwd=tmp_path,
        check=False,
    )


def test_a_cited_file_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    result = _run(tmp_path, ["evidence/AC1-stream.png"])

    assert result.returncode == 1, result.stdout
    assert "NOT_VALIDATED" in result.stdout
    assert "evidence/AC1-stream.png" in result.stdout + result.stderr, (
        "the refusal must name the path that did not resolve"
    )


def test_a_cited_file_that_exists_is_accepted(tmp_path: Path) -> None:
    shot = tmp_path / "evidence" / "AC1-stream.png"
    shot.parent.mkdir(parents=True)
    shot.write_bytes(b"\x89PNG\r\n")

    result = _run(tmp_path, ["evidence/AC1-stream.png"])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ACCEPTED" in result.stdout


def test_an_empty_file_is_not_evidence(tmp_path: Path) -> None:
    """A zero-byte screenshot is a failed capture, and it reads as a successful one."""
    shot = tmp_path / "evidence" / "AC1-stream.png"
    shot.parent.mkdir(parents=True)
    shot.write_bytes(b"")

    result = _run(tmp_path, ["evidence/AC1-stream.png"])

    assert result.returncode == 1, result.stdout
    assert "empty" in (result.stdout + result.stderr).lower()


def test_the_evidence_root_can_be_pointed_elsewhere(tmp_path: Path) -> None:
    """Paths are cited relative to the record, which need not be the cwd."""
    root = tmp_path / "records" / "acceptance"
    (root / "evidence").mkdir(parents=True)
    (root / "evidence" / "AC1.png").write_bytes(b"\x89PNG")

    result = _run(tmp_path, ["evidence/AC1.png"], "--evidence-root", str(root))

    assert result.returncode == 0, result.stdout + result.stderr


def test_a_run_that_cannot_check_paths_says_so_rather_than_passing(tmp_path: Path) -> None:
    """`--evidence-root` pointing at nothing is an inability to measure, not a pass."""
    result = _run(tmp_path, ["evidence/AC1.png"],
                  "--evidence-root", str(tmp_path / "nowhere"))

    assert result.returncode != 0, result.stdout
    assert "NOT_VALIDATED" in result.stdout + result.stderr


def test_a_failed_criterion_is_still_rejected_not_not_validated(tmp_path: Path) -> None:
    """Checking paths must not reclassify a real failure. "We could not check" and
    "we checked and it is broken" stay different facts."""
    (tmp_path / "criteria.json").write_text(json.dumps(CRITERIA), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps({
        "milestone_id": "M1",
        "target": {"kind": "web", "url": "https://x"},
        "results": [{"id": "AC1", "status": "failed", "evidence": ["gone.png"]}],
        "defects": [],
    }), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--criteria", str(tmp_path / "criteria.json"),
         "--evidence", str(tmp_path / "evidence.json")],
        capture_output=True, text=True, cwd=tmp_path,
        check=False,
    )

    assert "REJECTED" in result.stdout, result.stdout

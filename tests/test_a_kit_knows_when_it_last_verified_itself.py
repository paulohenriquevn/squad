"""Nothing said when the suite last ran, so "is it green?" cost fifteen minutes to ask.

`run_slice_tests.sh` printed its verdict and exited. On 2026-09-22 one session ran it four
times in one day to answer that one question, and two of the four answered about a tree that
had moved. The record it now writes closes half of that; this gate is the other half — the
thing that READS the record and says whether the answer still applies.

FOUR STATES, and the last two are the reason it exists:

    verified      the record's head is HEAD, and nothing failed
    stale         the record is real and describes a commit this tree has moved past
    failing       the record is current and something failed
    never         no record at all — the suite has not run here since this gate existed

`never` is not `failing`. A fresh clone has never verified itself and is not broken; a tree
whose last recorded run failed is a different fact and a different action. Collapsing them
would make the gate fire on every new checkout, and a signal that always fires is the same
as no signal.

IT DOES NOT RUN THE SUITE. A gate that verifies by verifying takes fifteen minutes and
cannot be asked casually — which is the property that made the question go unasked. This
reads a file and answers in milliseconds.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
GATE = _ROOT / "mechanisms" / "gates" / "check_verification_freshness.py"

sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@e.com"),
                 ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True,
                   capture_output=True)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    return root, head


def _record(root: Path, **fields) -> None:
    d = root / ".squad" / "records" / "verification"
    d.mkdir(parents=True, exist_ok=True)
    body = {"at": "2026-09-22T02:36:45Z", "suites": 31, "failed_suites": 0,
            "passed": 5850, "failed": 0, "tree_moved": False, "tree": str(root)}
    body.update(fields)
    (d / "last-run.json").write_text(json.dumps(body) + "\n", encoding="utf-8")


def _check(root: Path):
    from check_verification_freshness import check

    return check(root)


def test_a_record_at_head_with_no_failures_is_verified(tmp_path: Path) -> None:
    root, head = _repo(tmp_path)
    _record(root, head=head)

    code, report = _check(root)

    assert report["state"] == "verified"
    assert code == 0


def test_a_record_describing_an_older_commit_is_stale(tmp_path: Path) -> None:
    root, _head = _repo(tmp_path)
    _record(root, head="0" * 40)

    code, report = _check(root)

    assert report["state"] == "stale"
    assert code == 1


def test_no_record_is_never_and_not_failing(tmp_path: Path) -> None:
    """A fresh clone has not verified itself and is not broken.

    Reporting it as a failure would fire on every new checkout, and a signal that always
    fires is the same as no signal.
    """
    root, _ = _repo(tmp_path)

    code, report = _check(root)

    assert report["state"] == "never"
    assert code == 2, "not measured is not passing, and it is not failing either"


def test_a_current_record_with_failures_is_failing(tmp_path: Path) -> None:
    root, head = _repo(tmp_path)
    _record(root, head=head, failed=3, failed_suites=1)

    code, report = _check(root)

    assert report["state"] == "failing"
    assert report["failed"] == 3
    assert code == 1


def test_a_record_taken_over_a_moving_tree_is_not_verified(tmp_path: Path) -> None:
    """`tree_moved` is the runner saying its own result is unattributable.

    Reading it as green would launder exactly the thing that flag exists to prevent.
    """
    root, head = _repo(tmp_path)
    _record(root, head=head, tree_moved=True)

    code, report = _check(root)

    assert report["state"] == "unattributable"
    assert code == 1


def test_an_unreadable_record_is_not_a_passing_one(tmp_path: Path) -> None:
    root, _ = _repo(tmp_path)
    d = root / ".squad" / "records" / "verification"
    d.mkdir(parents=True)
    (d / "last-run.json").write_text("{not json", encoding="utf-8")

    code, report = _check(root)

    assert report["state"] == "unreadable"
    assert code == 2


def test_the_gate_runs_from_the_command_line(tmp_path: Path) -> None:
    """A mechanism nothing invokes is a capability that does not run."""
    root, head = _repo(tmp_path)
    _record(root, head=head)

    out = subprocess.run([sys.executable, str(GATE), "--root", str(root)],
                         capture_output=True, text=True, check=False)

    assert out.returncode == 0, out.stdout + out.stderr
    assert "verified" in out.stdout.lower()

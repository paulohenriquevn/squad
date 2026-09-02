"""`fleet_status.sh` — seeing every session at once, from outside them.

`/squad-status` answers "why is the queue in this state" from INSIDE a Claude
session. This answers "what are the sessions doing", from the shell, and never
attaches: reading a pane must not steal it from whoever is watching.

Written after two days of a stalled fleet where the only way to know anything was
`tmux capture-pane` by hand, session by session, plus `tail` on a jsonl whose
useful fields are buried in a `reason` string.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "mechanisms" / "fleet" / "fleet_status.sh"
QUEUE_LINE = REPO / "mechanisms" / "fleet" / "fleet_queue_line.py"


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    base = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp"), "TERM": "dumb"}
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True,  # noqa: PLW1510
                          text=True, env={**base, **(env or {})})


def test_it_is_executable_and_parses() -> None:
    assert os.access(SCRIPT, os.X_OK), "a status script nobody can run is a file"
    check = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)  # noqa: PLW1510
    assert check.returncode == 0, check.stderr


def test_it_says_the_fleet_is_down_rather_than_printing_nothing(tmp_path: Path) -> None:
    """Silence and "no fleet" look identical on a terminal, and one of them is a
    question the reader still has."""
    result = _run(env={"TMUX_TMPDIR": str(tmp_path)})

    assert result.returncode == 0
    assert "no tmux server running" in result.stdout
    assert "start_fleet.sh" in result.stdout, "it must say how to start one"


def test_the_start_hint_points_at_a_script_that_exists(tmp_path: Path) -> None:
    """The hint names a path; a path that resolves nowhere is worse than no hint."""
    result = _run(env={"TMUX_TMPDIR": str(tmp_path)})

    hinted = [w for w in result.stdout.split() if w.endswith("start_fleet.sh")]
    assert hinted, result.stdout
    assert Path(hinted[0]).is_file(), f"{hinted[0]} does not exist"


def test_help_describes_every_mode_it_accepts() -> None:
    result = _run("--help")

    for mode in ("-f", "-l", "squad2"):
        assert mode in result.stdout, f"{mode} is accepted and undocumented"


def test_the_queue_line_reports_a_selection(tmp_path: Path) -> None:
    report = tmp_path / "q.json"
    report.write_text(json.dumps({"verdict": "ITEM_SELECTED", "item_id": "B-060"}),
                      encoding="utf-8")

    out = subprocess.run([sys.executable, str(QUEUE_LINE), str(report)],  # noqa: PLW1510
                         capture_output=True, text=True).stdout

    assert "ITEM_SELECTED" in out and "B-060" in out


def test_the_queue_line_explains_a_refusal(tmp_path: Path) -> None:
    """A verdict without its reason sends the reader back to the selector."""
    report = tmp_path / "q.json"
    report.write_text(json.dumps({"verdict": "BACKLOG_BLOCKED",
                                  "reason": "every item is held"}), encoding="utf-8")

    out = subprocess.run([sys.executable, str(QUEUE_LINE), str(report)],  # noqa: PLW1510
                         capture_output=True, text=True).stdout

    assert "BACKLOG_BLOCKED" in out
    assert "every item is held" in out


def test_an_unreadable_report_says_so_instead_of_printing_a_verdict(tmp_path: Path) -> None:
    """The failure this whole kit keeps finding: absence rendered as a clean answer."""
    out = subprocess.run([sys.executable, str(QUEUE_LINE), str(tmp_path / "missing.json")],  # noqa: PLW1510
                         capture_output=True, text=True).stdout

    assert "could not be read" in out
    assert "ITEM_SELECTED" not in out

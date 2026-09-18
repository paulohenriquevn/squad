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
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "mechanisms" / "fleet" / "fleet_status.sh"
QUEUE_LINE = REPO / "mechanisms" / "fleet" / "fleet_queue_line.py"


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    base = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp"), "TERM": "dumb"}
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True,
                          text=True, env={**base, **(env or {})}, check=False)


def test_it_is_executable_and_parses() -> None:
    assert os.access(SCRIPT, os.X_OK), "a status script nobody can run is a file"
    check = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
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

    out = subprocess.run([sys.executable, str(QUEUE_LINE), str(report)],
                         capture_output=True, text=True, check=False).stdout

    assert "ITEM_SELECTED" in out and "B-060" in out


def test_the_queue_line_explains_a_refusal(tmp_path: Path) -> None:
    """A verdict without its reason sends the reader back to the selector."""
    report = tmp_path / "q.json"
    report.write_text(json.dumps({"verdict": "BACKLOG_BLOCKED",
                                  "reason": "every item is held"}), encoding="utf-8")

    out = subprocess.run([sys.executable, str(QUEUE_LINE), str(report)],
                         capture_output=True, text=True, check=False).stdout

    assert "BACKLOG_BLOCKED" in out
    assert "every item is held" in out


def test_an_unreadable_report_says_so_instead_of_printing_a_verdict(tmp_path: Path) -> None:
    """The failure this whole kit keeps finding: absence rendered as a clean answer."""
    out = subprocess.run([sys.executable, str(QUEUE_LINE), str(tmp_path / "missing.json")],
                         capture_output=True, text=True, check=False).stdout

    assert "could not be read" in out
    assert "ITEM_SELECTED" not in out


# ── fleet_wall.sh ─────────────────────────────────────────────────────────────

WALL = REPO / "mechanisms" / "fleet" / "fleet_wall.sh"


def _wall(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    base = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp"), "TERM": "dumb"}
    return subprocess.run(["bash", str(WALL), *args], capture_output=True,
                          text=True, env={**base, **(env or {})}, check=False)


def test_the_wall_is_executable_and_parses() -> None:
    assert os.access(WALL, os.X_OK)
    check = subprocess.run(["bash", "-n", str(WALL)], capture_output=True, text=True, check=False)
    assert check.returncode == 0, check.stderr


def test_the_wall_refuses_when_there_is_no_server(tmp_path: Path) -> None:
    """And says how to start one, rather than exiting quietly on a blank screen."""
    result = _wall("-d", env={"TMUX_TMPDIR": str(tmp_path)})

    assert result.returncode == 1
    assert "no tmux server" in result.stderr
    assert "start_fleet.sh" in result.stderr


def test_the_wall_is_read_only_unless_asked_otherwise() -> None:
    """The default cannot type into a session. A fleet session is being driven by
    the watchdog, and a stray keystroke answers — as the operator — a question the
    agent asked someone else."""
    source = WALL.read_text(encoding="utf-8")

    assert 'MODE="-r"' in source, "read-only must be the default"
    assert '-w|--writable' in source, "and there must be a deliberate way out of it"


def test_the_wall_matches_only_fleet_sessions() -> None:
    """A wall built from every tmux session shows whatever else the machine is
    doing. Measured while building this: a throwaway session created two commands
    earlier appeared as a fleet member."""
    source = WALL.read_text(encoding="utf-8")

    assert "FLEET_PATTERN" in source, "the set must be a pattern, not everything running"

    default = re.search(r'PATTERN="\$\{FLEET_PATTERN:-([^}]+)\}"', source)
    assert default, "the default pattern is not readable from the script"
    pattern = re.compile(default.group(1))

    # What start_fleet.sh names, and what it must not sweep up beside them.
    assert pattern.search("squad1") and pattern.search("squad12")
    assert not pattern.search("lead"), "the lead's pane is raw jsonl; the status pane replaces it"
    assert not pattern.search("wall")
    assert not pattern.search("my-other-work"), "a stray session is not a fleet member"


def test_the_report_asks_tmux_how_wide_the_pane_is() -> None:
    """`tput` needs a terminal and COLUMNS is not exported through a subshell, so
    inside the wall's status pane both answered for the wrong thing: a 110-column
    pane formatted for 100, and every other line wrapped. tmux sets `TMUX_PANE`
    for the process it runs, and tmux is the one that knows."""
    source = SCRIPT.read_text(encoding="utf-8")

    assert "TMUX_PANE" in source
    assert "pane_width" in source, "it must ask tmux, not guess"
    assert "tput cols" in source, "and still work outside tmux"


def test_the_wall_does_not_run_the_report_through_watch() -> None:
    """`watch` runs the command in its own environment, which drops TMUX_PANE —
    the report then measures the wrong pane. A plain loop keeps it."""
    source = WALL.read_text(encoding="utf-8")

    # Only the lines that RUN something — a comment explaining why `watch` is
    # avoided, and the word "watchdog", must not fail this.
    commands = [ln for ln in source.splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")]
    running = "\n".join(commands)

    assert "fleet_status.sh" in running, "the wall shows the report somewhere"
    for line in commands:
        assert not line.lstrip().startswith("watch "), line
        assert '"watch ' not in line and "'watch " not in line, line


def test_the_status_report_excludes_the_wall_itself() -> None:
    """Run inside the wall, a report listing every session lists the wall — whose
    pane is this report. The reader sees the report inside the report."""
    source = SCRIPT.read_text(encoding="utf-8")

    assert "FLEET_PATTERN" in source, "the report must filter, not list everything"

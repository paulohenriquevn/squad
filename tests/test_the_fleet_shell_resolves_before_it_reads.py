"""Three shell scripts that read a value before, or instead of, resolving it.

* `fleet_status.sh` consumed `${PROJECT:-.}` on line 23 and assigned `PROJECT` on line
  29. Unless the caller exported it, the substitution took `.` and
  `lead_log_path(".")` returned the RELATIVE `.squad/lead.jsonl` — resolved against
  whatever directory the reader happened to be standing in. The comment above it says
  the path is "derived from the single owner"; it was derived from the wrong argument.
* `workflow_watch.sh` searched `${CLAUDE_PROJECT_DIR:-$HOME/.claude/projects}`. Those
  two are never the same tree — one is the project, the other the CLI's transcript
  store — and the `wf_*` run directories live in the second. So inside a Claude Code
  session, which is the documented use, it searched the tree its own fallback says is
  wrong and exited 1 with "no workflow run found".
* `start_lead_session.sh` sent text and Enter in one `send-keys`. `dispatch_to_lane.sh`
  documents, with a date and a measurement, that this leaves the line in the composer
  on all three lanes. This script appeared to work only because its second send-keys
  submitted the first as a side effect — and the `/loop` line has no successor.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_FLEET = _ROOT / "mechanisms" / "fleet"


def _line_of(path: Path, needle: str) -> int:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return number
    return -1


def test_fleet_status_assigns_the_project_before_it_reads_it() -> None:
    script = _FLEET / "fleet_status.sh"

    assigned = _line_of(script, 'PROJECT="${PROJECT:-$(cd "$_here/../.." && pwd)}"')
    consumed = _line_of(script, '"${PROJECT:-.}"')

    assert assigned > 0, "the assignment moved; this test lost its subject"
    assert consumed == -1 or assigned < consumed, (
        f"PROJECT is read at line {consumed} and assigned at line {assigned}")


def test_the_lead_log_is_absolute() -> None:
    script = _FLEET / "fleet_status.sh"
    result = subprocess.run(["bash", "-c", f'set -e; . /dev/stdin <<"EOF"\n'
                                           f'{script.read_text(encoding="utf-8").split("LINES=6")[0]}\n'
                                           f'echo "$LOG"\nEOF'],
                            cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False)
    printed = (result.stdout or "").strip().splitlines()[-1] if result.stdout.strip() else ""

    assert printed.startswith("/"), (
        f"a relative log path resolves against the reader's cwd: {printed!r}")


def test_workflow_watch_searches_the_transcript_store() -> None:
    """`wf_*` run directories live under the CLI's store, never in the project."""
    source = (_FLEET / "workflow_watch.sh").read_text(encoding="utf-8")

    assert '"${CLAUDE_PROJECT_DIR:-$HOME/.claude/projects}"' not in source, (
        "the two roots are never the same tree, and only one holds the runs")


def test_the_lead_brief_and_its_enter_go_as_two_calls() -> None:
    source = (_FLEET / "start_lead_session.sh").read_text(encoding="utf-8")

    # A lone `send-keys ... C-m` is the CORRECT second call. What this catches is a
    # call carrying BOTH a payload and the Enter.
    inline = re.findall(r'^\s*tmux send-keys\s+-t\s+\S+\s+"[^"]+"\s+C-m\s*$',
                        source, re.MULTILINE)

    assert inline == [], (
        "text and C-m in one send-keys leaves the line in the composer — measured "
        f"2026-09-02 on all three lanes: {inline}")

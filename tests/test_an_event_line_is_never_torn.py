"""An append of one event is not one write once the line exceeds the buffer.

`_append_line` opened the file in `"a"` mode and wrote. `O_APPEND` is atomic only up to
PIPE_BUF (4 KiB on Linux), and beyond the stream's own 8 KiB buffer it is not even one
write syscall — so two cycles emitting concurrently interleave halves of two JSON
objects into one line.

The stream is append-only and never rewritten, so a torn line is PERMANENT: every later
reader skips it as unparseable, and what it recorded is gone. `squad.shared_file` owns
this serialisation and every other shared-file writer in the kit already goes through it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT))

import cycle_events  # noqa: E402 — post-bootstrap import


def test_the_append_goes_through_the_serialisation_owner(tmp_path: Path, monkeypatch) -> None:
    """The structural half: `_append_line` must not open the file itself.

    A spawn race is not the test for this. Measured: sixteen subprocesses each writing
    a 16 KiB line never actually overlapped — process start-up costs more than the
    write — so a race-shaped test passed against the unlocked version and proved
    nothing. What can be asserted deterministically is that the write goes through the
    owner that holds the lock, and (below) that the lock is really held.
    """
    seen: list[tuple] = []
    monkeypatch.setattr(cycle_events.shared_file, "append_line",
                        lambda target, line, **kw: seen.append((target, line)))

    cycle_events._append_line(tmp_path / "cycle-events.jsonl", '{"event": "one"}')

    assert seen == [(tmp_path / "cycle-events.jsonl", '{"event": "one"}')], seen


def test_a_second_writer_waits_for_the_lock(tmp_path: Path) -> None:
    """The behavioural half, made deterministic by HOLDING the lock.

    No timing window to lose: the lock is taken here and the writer is given a short
    timeout, so it must fail rather than write beside us. Without the lock it would
    succeed immediately — which is exactly the interleaving this guards.
    """
    stream = tmp_path / "cycle-events.jsonl"
    stream.parent.mkdir(parents=True, exist_ok=True)
    stream.touch()

    with cycle_events.shared_file.locked(stream, timeout_seconds=5.0):
        script = tmp_path / "writer.py"
        script.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(_ROOT)!r})\n"
            "from pathlib import Path\n"
            "from squad import shared_file\n"
            "shared_file.append_line(Path(sys.argv[1]), 'from the other process',\n"
            "                        timeout_seconds=1.0)\n",
            encoding="utf-8")

        done = subprocess.run([sys.executable, str(script), str(stream)],
                              capture_output=True, text=True, timeout=120, check=False)

    assert done.returncode != 0, (
        "a second writer appended while the lock was held by this test")
    assert "TimeoutError" in done.stderr, done.stderr
    assert "from the other process" not in stream.read_text(encoding="utf-8")


def test_one_append_writes_one_line(tmp_path: Path) -> None:
    stream = tmp_path / "cycle-events.jsonl"

    cycle_events._append_line(stream, json.dumps({"event": "one"}))

    assert stream.read_text(encoding="utf-8") == '{"event": "one"}\n'

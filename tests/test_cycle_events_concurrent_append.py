"""Many lanes, one event stream, and no lock. Measured rather than assumed.

kit#28 gave every consumer lane its own git worktree, which fixed lanes dirtying each
other's checkouts. Its scope note left one hazard open and unmeasured:

    `cycle-events.jsonl` is a separate hazard worth its own item: it is one file,
    appended by every lane, and no locking was observed.

The observation is correct — there is no lock. Measured on 2026-09-05, the absence is
not a defect: eight concurrent processes writing 40 events each, with payloads of
12 KB, 200 KB and 1 MB, produced 320 parseable lines and lost nothing, every time.
`O_APPEND` makes the seek-and-write one operation, and `_append_line` hands the text
layer ONE string per event.

Both halves of that sentence are load-bearing, and neither is guaranteed by the
language. What this file pins is the second: that an event still reaches the stream as
a single write. Splitting it — `write(line)` then `write("\\n")`, or a seek before the
write — lets another lane land between the two, and the corruption is silent: a
half-line that json.loads rejects, in a file nobody reads until something has already
gone wrong.

Deliberately not a stress test. Four writers and a payload just past the 8 KiB buffer
is enough to expose a split writer, and a test that takes a minute is a test somebody
eventually marks slow.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "cycle"))

WRITERS = 4
PER_WRITER = 15
#: Past the text layer's 8 KiB buffer, so the write cannot stay inside it.
PAYLOAD = "x" * 20_000


def _writer(target: str, idx: int, barrier) -> None:
    """Runs in a separate PROCESS: threads would share one file object and prove
    nothing about two lanes, which are separate processes.

    The barrier is what makes this a race. Without it the processes start staggered
    by however long `spawn` takes to boot an interpreter — tens of milliseconds, more
    than enough for each to finish before the next begins. Measured: the same four
    writers and the same payload corrupt every run when they start together and pass
    every run when they do not. A concurrency test whose processes never overlap is
    green for the same reason an empty test is.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "cycle"))
    from cycle_events import _append_line

    barrier.wait(timeout=60)
    for n in range(PER_WRITER):
        _append_line(Path(target), json.dumps(
            {"type": "phase", "cycle": "implement", "slug": f"b-{idx:03d}",
             "writer": idx, "n": n, "note": PAYLOAD},
            separators=(",", ":")))


@pytest.mark.skipif(sys.platform == "win32",
                    reason="O_APPEND atomicity is the POSIX guarantee this rests on")
def test_concurrent_lanes_do_not_interleave_one_event_stream(tmp_path: Path) -> None:
    target = tmp_path / "records" / "cycle-events.jsonl"

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(WRITERS)
    procs = [ctx.Process(target=_writer, args=(str(target), i, barrier))
             for i in range(WRITERS)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)

    assert target.is_file(), "no stream was written at all"
    lines = target.read_text(encoding="utf-8").splitlines()

    unparseable = []
    seen = set()
    for ln in lines:
        try:
            event = json.loads(ln)
        except json.JSONDecodeError:
            unparseable.append(ln[:80])
            continue
        seen.add((event["writer"], event["n"]))

    expected = WRITERS * PER_WRITER
    assert not unparseable, (
        f"{len(unparseable)} line(s) are not JSON, so two lanes interleaved inside "
        f"one event. First: {unparseable[0]!r}"
    )
    assert len(seen) == expected, (
        f"{expected - len(seen)} event(s) were lost. An append that is not one write "
        f"loses whatever the other writer landed on top of."
    )
    assert len(lines) == expected, (
        f"{len(lines)} lines for {expected} events — an event was split across lines"
    )


def test_the_appender_hands_the_stream_one_string_per_event() -> None:
    """The property above, asserted where it is decided rather than only observed.

    The concurrency test can pass on a split writer if the race does not happen to
    lose, which is exactly how a flaky guarantee reads as a solid one. This reads the
    source: one `write` call inside the handle's scope.

    Read from `squad.shared_file.append_line_unlocked`, which is where the write moved.
    `cycle_events._append_line` now delegates, and the delegation is the point: an
    `O_APPEND` write is atomic only up to PIPE_BUF, and beyond the stream's own 8 KiB
    buffer it is not even one syscall — so the lock, not the mode, is what makes an
    event arrive whole. The append-mode assertion below stays because a seek-and-write
    would be wrong under the lock too.
    """
    src = (Path(__file__).resolve().parents[1]
           / "squad" / "shared_file.py").read_text(encoding="utf-8")
    body = src[src.index("def append_line_unlocked("):]
    body = body[:body.index("\ndef ", 1)] if "\ndef " in body[1:] else body

    assert body.count(".write(") == 1, (
        "an event must reach the stream in ONE write; two writes let another lane "
        f"land between them:\n{body}"
    )
    assert '"a"' in body or "'a'" in body, (
        "the handle must be opened in append mode"
    )
    assert ".seek(" not in body, (
        "a seek before the write reintroduces the race O_APPEND removes"
    )


def test_the_event_stream_writes_through_the_serialisation_owner() -> None:
    """`cycle_events` must not open the file itself.

    The append it used to do directly is correct only up to PIPE_BUF; an event carrying
    a long `detail` crosses that, and two cycles emitting concurrently interleaved
    halves of two JSON objects into one permanent line.
    """
    src = (Path(__file__).resolve().parents[1]
           / "mechanisms" / "cycle" / "cycle_events.py").read_text(encoding="utf-8")
    body = src[src.index("def _append_line("):]
    body = body[:body.index("\ndef ", 1)]

    assert "shared_file.append_line(" in body, body
    assert ".open(" not in body, "the stream is opened outside the lock's owner"


# ── the `--once` window, which the append guarantee above does NOT cover ──────
#
# `--once` READS the stream, inspects the last event, and then appends. Two callers can
# both read a stream whose last line is not yet the other's, both conclude "no identical
# last event", and both write — so the refusal `--once` exists for holds only when
# nothing overlaps. The three existing `--once` tests are sequential and cannot see it.
#
# `O_APPEND` does not help here: the hazard is not a torn line, it is a decision taken
# from a state that changed before the write.
#
# NOT tested by racing two processes. That was tried first and it is worth recording why
# it was discarded: with the lock REMOVED the two-process version still passed, because
# `spawn` plus argparse plus the import puts more between the barrier and the read than
# the window is wide. A concurrency test that passes without the fix proves nothing and
# reads as if it proved something — the same defect this whole review keeps finding.
#
# So the lock is pinned DIRECTLY: hold it, and assert the `--once` caller cannot write
# while it is held. That is deterministic, and it fails the moment the lock is removed.


def _once_caller(project: str, ready, done) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "cycle"))
    from cycle_events import main

    ready.set()
    try:
        main(["end", "--cycle", "implement", "--slug", "B-014",
              "--verdict", "IMPLEMENTATION_COMPLETE", "--project-root", project,
              "--once"])
    except TimeoutError:
        pass
    done.set()


@pytest.mark.skipif(sys.platform == "win32", reason="flock is the POSIX guarantee here")
def test_a_once_caller_cannot_read_and_append_while_the_stream_is_held(
        tmp_path: Path) -> None:
    """The read and the append are ONE transaction, and this is what proves it."""
    import time

    from squad.paths import write_records_dir
    from squad.shared_file import locked

    project = tmp_path / "project"
    (project / ".squad" / "records").mkdir(parents=True)
    stream = write_records_dir(project, "") / "cycle-events.jsonl"
    stream.parent.mkdir(parents=True, exist_ok=True)

    ctx = mp.get_context("spawn")
    ready, done = ctx.Event(), ctx.Event()
    proc = ctx.Process(target=_once_caller, args=(str(project), ready, done))

    with locked(stream):
        proc.start()
        assert ready.wait(timeout=60), "the caller never started"
        # It must be BLOCKED on the lock, not writing behind it.
        time.sleep(2)
        wrote_while_held = stream.is_file() and stream.read_text(encoding="utf-8").strip()
        assert not wrote_while_held, (
            "a `--once` caller read and appended while the stream was held by another "
            "process; the read-decide-append span is not serialised")

    proc.join(timeout=120)
    assert done.is_set(), "the caller never finished after the lock was released"

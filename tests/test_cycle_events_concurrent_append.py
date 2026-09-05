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
    """
    src = (Path(__file__).resolve().parents[1]
           / "mechanisms" / "cycle" / "cycle_events.py").read_text(encoding="utf-8")
    body = src[src.index("def _append_line("):]
    body = body[:body.index("\ndef ", 1)]

    assert body.count(".write(") == 1, (
        "an event must reach the stream in ONE write; two writes let another lane "
        f"land between them:\n{body}"
    )
    assert '"a"' in body or "'a'" in body, (
        "the handle must be opened in append mode — O_APPEND is what makes the "
        "seek-and-write atomic, and it is the only reason no lock is needed"
    )
    assert ".seek(" not in body, (
        "a seek before the write reintroduces the race O_APPEND removes"
    )

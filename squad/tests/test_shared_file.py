"""A file two processes write must not lose one of them, and must never be seen half-written."""
from __future__ import annotations

import multiprocessing as mp
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from squad.shared_file import append_line, locked, update, write_atomic


def _increment(path_str: str, rounds: int) -> None:
    path = Path(path_str)
    for _ in range(rounds):
        update(path, lambda text: str(int(text or "0") + 1), default="0")


def test_concurrent_read_modify_writes_do_not_lose_an_update(tmp_path: Path) -> None:
    """The defect the module exists for, measured rather than argued.

    Eight processes each adding one, fifty times, over a counter every one of them reads
    before it writes. Without the lock the total lands well under 400 — the classic lost
    update, and exactly the shape of two lanes rewriting BACKLOG.md.
    """
    counter = tmp_path / "counter.txt"
    counter.write_text("0", encoding="utf-8")

    workers = [mp.Process(target=_increment, args=(str(counter), 50)) for _ in range(8)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=120)

    assert counter.read_text(encoding="utf-8") == "400"


def test_a_replace_is_never_observed_half_written(tmp_path: Path) -> None:
    """`write_text` truncates first. A reader between the two sees a shorter file."""
    target = tmp_path / "registry.md"
    target.write_text("old" * 5000, encoding="utf-8")

    write_atomic(target, "new" * 5000)

    assert target.read_text(encoding="utf-8") == "new" * 5000
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")], \
        "the temporary file survived the replace"


def test_a_transform_that_changes_nothing_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "registry.md"
    target.write_text("same", encoding="utf-8")
    before = target.stat().st_mtime_ns
    time.sleep(0.01)

    assert update(target, lambda text: text) is False
    assert target.stat().st_mtime_ns == before


def test_a_transform_returning_none_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "registry.md"
    target.write_text("same", encoding="utf-8")

    assert update(target, lambda _text: None) is False
    assert target.read_text(encoding="utf-8") == "same"


def test_a_missing_target_starts_from_the_declared_default(tmp_path: Path) -> None:
    target = tmp_path / "new.md"

    assert update(target, lambda text: text + "written", default="seed:") is True
    assert target.read_text(encoding="utf-8") == "seed:written"


def _hold(path_str: str, seconds: float) -> None:
    with locked(Path(path_str)):
        time.sleep(seconds)


def test_a_writer_that_cannot_take_the_lock_raises_rather_than_writing(tmp_path: Path) -> None:
    """A write that could not be serialised is not a write that may happen anyway."""
    target = tmp_path / "held.md"
    target.write_text("original", encoding="utf-8")

    holder = mp.Process(target=_hold, args=(str(target), 3.0))
    holder.start()
    time.sleep(0.5)
    try:
        with pytest.raises(TimeoutError):
            update(target, lambda _t: "clobbered", timeout_seconds=0.5)
    finally:
        holder.join(timeout=30)

    assert target.read_text(encoding="utf-8") == "original"


def test_the_lock_is_a_sidecar_so_a_replace_does_not_drop_it(tmp_path: Path) -> None:
    """Locking the target and then `os.replace`-ing it releases a lock on a dead inode."""
    target = tmp_path / "registry.md"
    update(target, lambda text: text + "x")

    assert (tmp_path / ".registry.md.lock").is_file()


def _append(path_str: str, tag: str, rounds: int) -> None:
    for i in range(rounds):
        append_line(Path(path_str), f"{tag}-{i}")


def test_concurrent_appends_keep_every_line_whole(tmp_path: Path) -> None:
    stream = tmp_path / "events.jsonl"
    workers = [mp.Process(target=_append, args=(str(stream), f"w{n}", 40)) for n in range(6)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=120)

    lines = stream.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 240
    assert len(set(lines)) == 240, "a line was interleaved with another"


def test_the_lock_is_released_when_the_block_raises(tmp_path: Path) -> None:
    target = tmp_path / "registry.md"
    with pytest.raises(ValueError, match="boom"):
        with locked(target):
            raise ValueError("boom")

    # Still takeable, in this process and from another.
    with locked(target, timeout_seconds=1.0):
        pass
    assert os.path.exists(tmp_path / ".registry.md.lock")


# ── the lock does not queue a process behind itself ──────────────────────────
#
# `flock` is per open-file-description, so taking the lock a second time from the
# same process on a second descriptor does NOT nest. A caller holding it over a
# read-decide-write span and then calling a helper that locks again is an ordinary
# shape — `cycle_events`' `--once` path is exactly that — and it deadlocked or
# re-locked depending on the platform. Between PROCESSES nothing changed.


def test_the_lock_is_reentrant_within_one_process(tmp_path: Path) -> None:
    target = tmp_path / "registry.md"
    target.write_text("one\n", encoding="utf-8")

    with locked(target, timeout_seconds=5.0):
        with locked(target, timeout_seconds=1.0):
            append_line(target, "two")

    assert target.read_text(encoding="utf-8") == "one\ntwo\n"


def test_the_inner_release_does_not_free_the_outer_hold(tmp_path: Path) -> None:
    """The failure a naive reentrant flag introduces: the nested exit unlocking."""
    target = tmp_path / "registry.md"
    target.write_text("one\n", encoding="utf-8")
    script = tmp_path / "writer.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parents[2])!r})\n"
        "from pathlib import Path\n"
        "from squad import shared_file\n"
        "append_line(Path(sys.argv[1]), 'other', timeout_seconds=1.0)\n",
        encoding="utf-8")

    with locked(target, timeout_seconds=5.0):
        with locked(target, timeout_seconds=1.0):
            pass
        # Still inside the OUTER hold. Another process must still be shut out.
        done = subprocess.run([sys.executable, str(script), str(target)],
                              capture_output=True, text=True, timeout=120, check=False)

    assert done.returncode != 0, "the nested exit released the outer hold"
    assert "other" not in target.read_text(encoding="utf-8")

"""Read-modify-write of a file more than one process writes.

WHY THIS EXISTS
===============
Five places in this kit read a shared file into memory, changed it and wrote the whole
thing back, with no lock across the span and no atomic replace at the end:

    mechanisms/cycle/backlog_status.py        BACKLOG.md, the registry
    mechanisms/cycle/advance_items.py         the same file, from another entry point
    mechanisms/cycle/apply_delegated_decisions.py   again
    mechanisms/fleet/pipeline_orchestrator.py the same file, from the fleet
    mechanisms/cycle/cycle_events.py          the event stream
    mechanisms/fleet/fleet_router.py          the assignment log

Concurrency is not hypothetical here: `mechanisms/fleet` dispatches lanes in parallel and
the briefs it writes tell every lane to run the cycle commands that hold these files. Two
writers that read the same bytes and write back lose whichever finishes first, silently,
and a writer interrupted mid-`write_text` leaves a truncated registry that the next reader
parses as a shorter one.

WHAT THIS GIVES
===============
`locked(path)`        an exclusive advisory lock held across a whole read-decide-write.
`write_atomic(path)`  a replace no reader can observe half of.
`update(path, fn)`    both at once, which is what every call site above actually wanted.

The lock is `fcntl.flock` on a sidecar `.lock` file, not on the target: locking the target
and then replacing it via `os.replace` would release the lock on an inode nobody holds any
more. Advisory means it binds the processes that ASK — every writer in this kit goes
through here, and an editor opening BACKLOG.md by hand is deliberately not blocked.
"""
from __future__ import annotations

import fcntl
import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path


def lock_path(target: Path) -> Path:
    """The sidecar this module locks for `target`."""
    return target.parent / f".{target.name}.lock"


#: Lock files this PROCESS currently holds, keyed by resolved sidecar path. Not
#: thread-safe by design: the kit's writers are processes, and a set that pretended
#: to serialise threads as well would be a claim nothing here tests.
_HELD: set[str] = set()


@contextmanager
def locked(target: Path, *, timeout_seconds: float = 30.0) -> Iterator[None]:
    """Hold an exclusive advisory lock for `target` over the whole block.

    Blocking with a timeout rather than a spin: a lane waiting on the registry should
    wait, and a lane waiting forever is a hang nobody can see. On timeout this raises
    `TimeoutError` rather than proceeding — a write that could not be serialised is not
    a write that may be done anyway.
    """
    sidecar = lock_path(target)
    # REENTRANT within one process. `flock` is per open-file-description, so taking the
    # lock a second time from the same process on a second descriptor does NOT nest —
    # it either blocks against itself or silently re-locks, depending on the platform.
    # A caller holding the lock over a read-decide-write span and then calling a helper
    # that locks again is an ordinary shape, not a mistake: `cycle_events`' `--once`
    # path does exactly that. Between processes nothing changes; this only stops a
    # process from queueing behind itself.
    key = str(sidecar.resolve()) if sidecar.exists() else str(sidecar)
    if key in _HELD:
        yield
        return

    sidecar.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(sidecar, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        _acquire(handle, sidecar, timeout_seconds)
        _HELD.add(key)
        try:
            yield
        finally:
            _HELD.discard(key)
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


def _acquire(handle: int, sidecar: Path, timeout_seconds: float) -> None:
    import time

    deadline = time.monotonic() + timeout_seconds
    delay = 0.01
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"another process has held {sidecar} for more than "
                    f"{timeout_seconds:g}s; refusing to write without the lock") from None
            time.sleep(delay)
            delay = min(delay * 2, 0.25)


def write_atomic(target: Path, content: str) -> None:
    """Replace `target` with `content` in one step no reader can observe half of.

    POSIX guarantees `os.replace` within a filesystem, which is why the temporary file is
    created in the target's OWN directory rather than in the system temp tree.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            "w", dir=str(target.parent), delete=False, encoding="utf-8",
            prefix=f".{target.name}.", suffix=".tmp") as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target)


def update(target: Path, transform: Callable[[str], str | None],
           *, timeout_seconds: float = 30.0, default: str = "") -> bool:
    """Read `target`, apply `transform`, write the result back. Returns whether it wrote.

    `transform` returning `None` — or the text unchanged — writes nothing. A registry
    rewritten with identical bytes still races another writer for no gain, and skipping
    the write is the cheapest way not to.
    """
    with locked(target, timeout_seconds=timeout_seconds):
        before = target.read_text(encoding="utf-8") if target.is_file() else default
        after = transform(before)
        if after is None or after == before:
            return False
        write_atomic(target, after)
        return True


def append_line(target: Path, line: str, *, timeout_seconds: float = 30.0) -> None:
    """Append one line under the lock, so a concurrent appender cannot interleave.

    An append is atomic for small writes on POSIX, but the callers here DECIDE from the
    file's contents and then append; the lock exists to cover that span, not the write.
    """
    with locked(target, timeout_seconds=timeout_seconds):
        append_line_unlocked(target, line)


def append_line_unlocked(target: Path, line: str) -> None:
    """The append itself, for a caller already holding the lock over a wider span."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line if line.endswith("\n") else line + "\n")

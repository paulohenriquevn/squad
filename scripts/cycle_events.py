#!/usr/bin/env python3
"""The cycle's phase transitions, as a stream instead of an excavation.

WHY THIS EXISTS
---------------
The only proof that a phase ran was a file appearing in one of the 15 record
directories under `knowledge-base/`, reconstructed afterwards by
`phase_coverage.py`. That reconstruction cannot separate two states this
ecosystem cares about a great deal:

    "the ecosystem could not tell 'the phase was skipped' from 'the phase ran
    and left nothing'"

— recorded when `phase_coverage.py` measured `code-quality` at 15%. A missing
file is evidence of nothing in particular. An event written at the moment of
transition is: it is in the stream, or it is not.

WHAT IT IS NOT
--------------
It is not a judge. Whether a phase *should* have run is
`check_phase_drift.py`'s question, deliberately kept in a separate artefact —
folding the record and its judge together is the exact shape that lets a
declared plan and its execution drift with nobody noticing, which is the defect
this whole movement is about.

It is also not a replacement for the records. A `code-quality` audit is still
the audit; the event says the phase happened and what it concluded, and points
at nothing it does not know.

TWO DELIBERATE ABSENCES
-----------------------
**No sequence number.** Line order in an append-only file already is the
sequence. A `seq` derived from a line count races under concurrent writers and
hands the reader a number that looks authoritative and is not.

**No raising.** A phase that did real work must not fail because its bookkeeping
could not be written. `emit_*` swallows every environmental error — the same
fail-open discipline `cycle-goal`'s Stop gate applies, and for the same reason:
a gate that jams the session is worse than one that misses a record. A caller
error (an empty cycle name) still raises, because that is a bug at the call
site, not a condition of the machine.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: One file, appended to by every phase. Named alongside the records it
#: complements rather than hidden, because a stream nobody can find is a stream
#: nobody reads.
EVENTS_FILENAME = "cycle-events.jsonl"

#: Canonical first. `rules/knowledge-base-location.md` makes
#: `.claude/knowledge-base/` the location in a plugin install, with the
#: standalone repo as the single exception. A stream written to the wrong half
#: recreates the split knowledge-base that `roadmap-review` reports as MAJOR.
_KB_DIRS = (".claude/knowledge-base", "knowledge-base")

PHASE_START = "cycle:phase:start"
PHASE_END = "cycle:phase:end"


_KIT_PARTS = ("skills", "rules", "hooks")


def _holds_the_kit(directory: Path) -> bool:
    """`hooks/lib/detect-layout.sh`'s `_squad_has_kit`, in Python.

    One definition of "this directory is the kit" already exists and is the one
    every hook resolves against. A second, subtly different one here would be
    the duplicated knowledge this repository has paid for before — so this
    mirrors it deliberately rather than inventing its own test.
    """
    return all((directory / part).is_dir() for part in _KIT_PARTS)


def _is_standalone(project_root: Path) -> bool:
    """The kit's own repository, by the same order the layout detector uses.

    The test is whether `.claude/` HOLDS THE KIT, not whether it exists: this
    repository has a `.claude/` carrying local settings and is still standalone.
    Getting that wrong created `.claude/knowledge-base/` at the root here on the
    very first instrumented run.
    """
    if _holds_the_kit(project_root / ".claude"):
        return False
    return _holds_the_kit(project_root)


def resolve_events_path(project_root: Path) -> Path:
    """Where this project's stream lives, in either install layout."""
    project_root = Path(project_root)
    for relative in _KB_DIRS:
        candidate = project_root / relative
        if candidate.is_dir():
            return candidate / EVENTS_FILENAME

    # Neither exists yet, so the first phase to run decides where the trail
    # begins. Getting this wrong is not a cosmetic error: creating
    # `.claude/knowledge-base/` inside the kit's own repository plants the split
    # knowledge-base that `backlog-review` reports as MAJOR — the defect the
    # CHANGELOG records the test suite having planted on every run. Found
    # exactly that way here, by running the instrumented gate against this repo.
    if _is_standalone(project_root):
        return project_root / "knowledge-base" / EVENTS_FILENAME
    return project_root / _KB_DIRS[0] / EVENTS_FILENAME


def project_root_for(work_path: Path) -> Path:
    """The project a phase acted on, derived from the work it touched.

    A phase records against the project it operated on, never against the
    shell's cwd. Found in a real install: `scripts/install.sh` runs the e2e
    smoke, which exercises `consolidate_findings.py` against a synthetic plan in
    a tmpdir while cwd is the ADOPTER's repository. Taking the root from cwd
    gave a freshly installed project a `review` event for a review it never ran
    — a record asserting a phase happened because a smoke test shared the
    process. Milder than fabricated evidence, and the same shape.

    Walks up from `work_path` to the nearest directory that owns a
    knowledge-base or holds the kit. When nothing above it qualifies — a smoke
    run in a bare tmpdir — the walk stops at the filesystem root and the caller
    gets `work_path` itself, so the event lands inside the throwaway tree
    instead of escaping into whichever repository the shell was sitting in.
    """
    work_path = Path(work_path).resolve()
    # Callers pass what they have: a criteria FILE, a findings DIRECTORY. Walking
    # up from a file would start one level too deep and, with nothing above it
    # qualifying, hand back the file itself as a project root.
    if work_path.is_file():
        work_path = work_path.parent
    candidates = [work_path, *work_path.parents]
    for candidate in candidates:
        for relative in _KB_DIRS:
            if (candidate / relative).is_dir():
                return candidate
        if _holds_the_kit(candidate) or _holds_the_kit(candidate / ".claude"):
            return candidate
    return work_path


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _json_safe(value: Any) -> Any:
    """Coerce rather than drop.

    A value that cannot be serialized is still information; dropping the field
    would leave the reader unable to tell an absent field from an unrepresentable
    one. A stream nobody can parse is worse than no stream, so the coercion
    happens here and never at read time.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _append_line(path: Path, line: str) -> None:
    """Append one line. Isolated so a test can make it fail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _emit(project_root: Path, event_type: str, cycle: str, slug: str,
          **extra: Any) -> dict[str, Any] | None:
    normalized_cycle = (cycle or "").strip()
    if not normalized_cycle:
        raise ValueError("cycle_events: an event must name the cycle it belongs to")

    event: dict[str, Any] = {
        "type": event_type,
        "cycle": normalized_cycle,
        "slug": (slug or "").strip() or None,
        "timestamp": _timestamp(),
    }
    event.update({key: _json_safe(value) for key, value in extra.items()})

    try:
        _append_line(resolve_events_path(project_root), json.dumps(event, ensure_ascii=False))
    except OSError:
        # Fail-open, deliberately and silently: the phase's real work already
        # happened, and a warning on stderr here would land in the middle of a
        # report the caller is composing.
        return None
    return event


def emit_phase_start(project_root: Path, *, cycle: str, slug: str = "",
                     **extra: Any) -> dict[str, Any] | None:
    """Record that a cycle phase began."""
    return _emit(project_root, PHASE_START, cycle, slug, **extra)


def emit_phase_end(project_root: Path, *, cycle: str, slug: str = "",
                   verdict: str | None = None, **extra: Any) -> dict[str, Any] | None:
    """Record that a cycle phase ended, and what it concluded.

    `verdict=None` is written as `null` on purpose. Not every phase computes one,
    and omitting the field would make a verdict-less phase indistinguishable from
    a line whose verdict failed to parse.
    """
    return _emit(project_root, PHASE_END, cycle, slug, verdict=verdict, **extra)


def read_events(project_root: Path) -> list[dict[str, Any]]:
    """Every readable event, in file order.

    A truncated line — a process killed mid-write — is skipped rather than
    raised, so one bad line cannot blind the reader to the events around it.
    """
    path = resolve_events_path(project_root)
    if not path.is_file():
        return []

    events: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit a cycle phase event. Callable from shell hooks.",
    )
    parser.add_argument("transition", choices=("start", "end"))
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--slug", default="")
    parser.add_argument("--verdict", default=None)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    if args.transition == "start":
        event = emit_phase_start(args.project_root, cycle=args.cycle, slug=args.slug)
    else:
        event = emit_phase_end(args.project_root, cycle=args.cycle, slug=args.slug,
                               verdict=args.verdict)

    if event is None:
        # Fail-open reaches the CLI too: a hook must not turn a write failure
        # into a blocked session.
        print("cycle-events: could not write the stream (continuing)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

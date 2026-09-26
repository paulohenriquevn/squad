#!/usr/bin/env python3
"""The cycle's phase transitions, as a stream instead of an excavation.

WHY THIS EXISTS
---------------
The only proof that a phase ran was a file appearing in one of the 15 record
directories under `records/`, reconstructed afterwards by
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
fail-open discipline `session-goal`'s Stop gate applies, and for the same reason:
a gate that jams the session is worse than one that misses a record. A caller
error (an empty cycle name) still raises, because that is a bug at the call
site, not a condition of the machine.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import contextlib
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from squad import shared_file
from squad.paths import (
    DATA_DIRNAME,
    LEGACY_RECORDS_ROOTS,
    RULE_BASES,
    write_records_dir,
)

#: One file, appended to by every phase. Named alongside the records it
#: complements rather than hidden, because a stream nobody can find is a stream
#: nobody reads.
EVENTS_FILENAME = "cycle-events.jsonl"


PHASE_START = "cycle:phase:start"
PHASE_END = "cycle:phase:end"


#: Assigned twice, identically, until 2026-09-17. Harmless while the two agreed, and the
#: shape that produces a real defect the moment one of them is edited: the second wins
#: silently and the reader who changed the first has no way to see why nothing happened.
_KIT_PARTS = ("skills", "rules", "hooks")


def _holds_the_kit(directory: Path) -> bool:
    """What `_squad_has_kit` did in the retired `detect-layout.sh`, in Python.

    One definition of "this directory is the kit" already exists and is the one every
    hook resolves against. A second, subtly different one here would be the duplicated
    knowledge this repository has paid for before.
    """
    return all((directory / part).is_dir() for part in _KIT_PARTS)


def resolve_events_path(project_root: Path) -> Path:
    """Where this project's stream is WRITTEN: `<project>/.squad/records/`.

    One root, no layout special case. This function used to answer differently for a
    plugin install and for the kit's own repository, and getting that wrong once
    planted `.claude/records/` at the root here on the very first instrumented run —
    the split trail `backlog-review` reports as MAJOR.

    A project whose stream is still in a legacy root keeps it until somebody moves it;
    `check_data_root.py` reports that, because a migration this code performed inside
    a consumer's repository would be the kit writing to a project it does not own.
    """
    return write_records_dir(project_root) / EVENTS_FILENAME


#: Directories that hold every throwaway tree on the machine. One `.squad` forgotten in
#: one of them turns every test, smoke run and hand-made `mktemp -d` into one shared
#: project — and nothing reports it, because recording somewhere IS the success path.
#:
#: `/tmp` and `/var/tmp` are named literally because that is where residue accumulates;
#: `tempfile.gettempdir()` covers a consumer whose `TMPDIR` points elsewhere, and is read
#: at call time rather than at import so a test can move it.
# Named to be DETECTED, never written (bandit B108).
_NAMED_TEMP_ROOTS = ("/tmp", "/var/tmp")  # nosec B108


def _is_system_temp_root(candidate: Path) -> bool:
    """Is this the system temp directory ITSELF, rather than something inside it?

    The distinction is the whole of the rule. `pytest`'s `tmp_path` lives UNDER the temp
    directory and the install suite builds real projects there, so refusing everything
    below it would refuse those. `/tmp/.squad` is somebody's leftover;
    `/tmp/pytest-of-x/test_y0/.squad` is a fixture.
    """
    import tempfile

    roots = [*_NAMED_TEMP_ROOTS, tempfile.gettempdir()]
    for root in roots:
        try:
            if candidate.resolve() == Path(root).resolve():
                return True
        except OSError:
            continue
    return False


def project_root_for(work_path: Path) -> Path:
    """The project a phase acted on, derived from the work it touched.

    A phase records against the project it operated on, never against the
    shell's cwd. Found in a real install: `mechanisms/distribution/install.sh` runs the e2e
    smoke, which exercises `consolidate_findings.py` against a synthetic plan in
    a tmpdir while cwd is the ADOPTER's repository. Taking the root from cwd
    gave a freshly installed project a `review` event for a review it never ran
    — a record asserting a phase happened because a smoke test shared the
    process. Milder than fabricated evidence, and the same shape.

    Walks up from `work_path` to the nearest directory that owns a
    records or holds the kit. When nothing above it qualifies — a smoke
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
        # The system temp directory is never a project, whatever is sitting in it. Walking
        # PAST it rather than stopping is deliberate: nothing above `/tmp` qualifies
        # either, so the loop falls through and the caller gets `work_path` — the
        # throwaway tree records inside itself, which is what the docstring above promises
        # for a bare tmpdir and what a stray `.squad` had quietly taken away.
        if _is_system_temp_root(candidate):
            continue
        # The write root is never a project, whatever is under it. It keeps its trail at
        # `records/`, which is also a legacy root name, so without this `.squad` passed the
        # legacy test below and a phase handed a path inside it wrote to `.squad/.squad/`
        # — a stream no reader resolves. Skipping the whole candidate, not just the legacy
        # test, because once that nested copy exists the write-root test fires on it too.
        if candidate.name == DATA_DIRNAME:
            continue
        # The write root first, then the legacy ones a project may not have migrated.
        # This walks UP looking for a project, so it must recognise both — a consumer
        # mid-migration is still one project, not none.
        if (candidate / DATA_DIRNAME).is_dir():
            return candidate
        for relative in LEGACY_RECORDS_ROOTS:
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
        # NaN and the infinities are not JSON. `math.isfinite` says that in one
        # word; the earlier `value == value` NaN idiom reads as a typo.
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _append_line(path: Path, line: str) -> None:
    """Append one line, under the lock. Isolated so a test can make it fail.

    An `O_APPEND` write is atomic only up to PIPE_BUF (4 KiB on Linux) — and beyond the
    stream's own 8 KiB buffer it is not even one write syscall. An event carrying a long
    `detail` or a list of reviewers crosses that, and two cycles emitting concurrently
    then interleave halves of two JSON objects into one line. The stream is append-only
    and never rewritten, so a torn line is permanent: every later reader skips it, and
    what it recorded is gone. `squad.shared_file` already owns this serialisation.

    Nesting is safe: `shared_file.locked` is reentrant within a process, so the
    `--once` path — which holds the lock over its whole read-decide-append span —
    passes straight through here rather than queueing behind itself.
    """
    shared_file.append_line(path, line)


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
                   verdict: str | None = None, artifact: Path | None = None,
                   **extra: Any) -> dict[str, Any] | None:
    """Record that a cycle phase ended, and what it concluded.

    `verdict=None` is written as `null` on purpose. Not every phase computes one,
    and omitting the field would make a verdict-less phase indistinguishable from
    a line whose verdict failed to parse.

    `artifact` is the file the phase judged. Its digest is recorded so a reader can
    tell a gate rerun on an edited artifact from one rerun on the same bytes — see
    `unchanged_repeats`.
    """
    if artifact is not None and Path(artifact).is_file():
        extra["artifact_sha256"] = hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
    return _emit(project_root, PHASE_END, cycle, slug, verdict=verdict, **extra)


#: How many identical verdicts on the same bytes before the CLI says so.
REPEAT_THRESHOLD = 3


def unchanged_repeats(events: list[dict[str, Any]], *, cycle: str, slug: str) -> int:
    """How many of this phase's latest ends share a verdict AND an artifact digest.

    Measured on a consumer session: four identical gate runs in 36 seconds with no
    edit between them, and 16 `FAIL_SOFT` for one slug in 12 minutes. Each refusal was
    honest; nothing said the same bytes had been refused the same way again, which is
    the point at which rerunning stops being work (#139).

    Only this cycle and slug's ends are compared, newest first; the run stops at the
    first one that differs. An end with no digest counts as 0: two unknowns are not
    the same artifact, and calling them equal would report repetition nobody measured.
    """
    ends = [e for e in events
            if e.get("type") == PHASE_END and e.get("cycle") == cycle
            and str(e.get("slug") or "") == str(slug or "")]
    if not ends or not ends[-1].get("artifact_sha256"):
        return 0
    last = ends[-1]
    count = 0
    for event in reversed(ends):
        if (event.get("verdict") != last.get("verdict")
                or event.get("artifact_sha256") != last["artifact_sha256"]):
            break
        count += 1
    return count


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


def declared_phases(project_root: Path) -> set[str]:
    """Phase names `rules/cycle-phases.txt` declares, or empty when it is unreadable.

    Empty means "cannot check", and the caller treats that as permission rather than
    refusal: a consumer whose rules directory has moved must still be able to record
    what ran.
    """
    for rel in ("rules/cycle-phases.txt", ".claude/rules/cycle-phases.txt"):
        path = project_root / rel
        if not path.is_file():
            continue
        names = set()
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "|" in stripped:
                name = stripped.split("|")[0].strip()
                if name:
                    names.add(name)
        if names:
            return names
    return set()


def declared_verdicts(project_root: Path, phase: str) -> set[str]:
    """Verdicts `rules/cycle-<phase>.md` declares, or empty when it declares none.

    Empty is permission, not refusal, and two phases rely on it: `implement` and
    `code-quality` emit real verdicts (`VALIDATED`, `PASS`, `FAIL_HARD`) from rules
    that carry no `## Verdicts` section. Refusing those would break honest emitters to
    catch a dishonest one.
    """
    # `squad.paths.rules_dir` owns the order; see it for which wins and why.
    for base in RULE_BASES:
        rule = project_root / base / f"cycle-{phase}.md"
        if not rule.is_file():
            continue
        body = rule.read_text(encoding="utf-8-sig", errors="replace")
        section = re.search(r"^##+[^\n]*Verdicts?[^\n]*\n(.*?)(?=^##\s|\Z)",
                            body, re.MULTILINE | re.DOTALL)
        if not section:
            return set()
        return set(re.findall(r"`([A-Z][A-Z0-9_]{3,})`", section.group(1)))
    return set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit a cycle phase event. Callable from shell hooks.",
    )
    parser.add_argument("transition", choices=("start", "end"))
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--slug", default="")
    parser.add_argument("--verdict", default=None)
    parser.add_argument("--once", action="store_true",
                        help="refuse if this phase already ended with this verdict for "
                             "this item and nothing has happened since. For a phase that "
                             "CONCLUDES (implementation complete, plan written, released); "
                             "never for a gate that iterates")
    parser.add_argument("--artifact", type=Path, default=None,
                        help="the file this phase judged; its digest lets the stream tell "
                             "a rerun on an edited artifact from a rerun on the same bytes")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    # The CLI normalises the root the same way the Python callers do. It did not,
    # and the two paths disagreed: `consolidate_findings.py` and its three siblings
    # call `project_root_for(...)` before emitting, while this entry point wrote
    # wherever it was pointed. Measured on 2026-08-31 in a replica of a consumer
    # layout — emitting from `api/internal` with `--project-root .` created a SECOND
    # stream at `api/internal/.claude/records/cycle-events.jsonl`, invisible to
    # anything reading the project root.
    #
    # That is worse than a lost event. `cycle-maintenance.md`'s ADVANCE reads the
    # stream to learn a phase ran; a phase whose event landed in an orphan file reads
    # exactly like a phase that was skipped, which is the one distinction this module
    # exists to make. And the four SKILL.md instructions added the day before all use
    # this CLI, from wherever the agent happens to be standing.
    root = project_root_for(args.project_root)

    # A phase name nobody declared is written and then dropped by every reader:
    # `check_phase_drift.py` scores against the declared set, and the board renders a
    # column per declared phase. So the work happens, an event records it, and nothing
    # can see it — the exact failure the stream exists to remove, arriving through the
    # door meant to fix it.
    #
    # Measured on the first autonomous run: the executing session called this CLI with
    # `--cycle deps-audit` and `--cycle idea-to-release`, neither in `cycle-phases.txt`.
    # No static sweep could catch it, because the emitter was an agent at runtime
    # rather than a line of code. Refusing here is the only place it can be caught.
    #
    # Refusing rather than warning, even though this module is otherwise fail-open:
    # a fail-open write puts an invisible event in the stream and reports success,
    # which is worse than no event. The write is lost either way; this way somebody
    # learns of it.
    known = declared_phases(root)
    if known and args.cycle not in known:
        print(f"REFUSED: `{args.cycle}` is not a phase in rules/cycle-phases.txt "
              f"({', '.join(sorted(known))}). An event for an undeclared phase is "
              f"written and then dropped by every reader. Declare the phase, or emit "
              f"under the one that owns this work.", file=sys.stderr)
        return 1

    # A verdict the phase's own contract does not declare is the same defect as an
    # undeclared phase, one level down: it is written, and every reader that switches
    # on the verdict drops it.
    #
    # Measured on the first autonomous run. The plan phase returned `INVALID` — a real
    # verdict, from a real hard cap — and the session recorded `INVALID_AWAITING_HUMAN`,
    # a name in no contract and no skill, invented to express that it was stopping. The
    # stream then said something no reader could act on, about a phase that really ran.
    if args.verdict:
        allowed = declared_verdicts(root, args.cycle)
        if allowed and args.verdict not in allowed:
            print(f"REFUSED: `{args.verdict}` is not a verdict of the `{args.cycle}` phase "
                  f"({', '.join(sorted(allowed))}). Inventing one records a decision no "
                  f"reader can act on. Emit the verdict the contract declares, and put the "
                  f"nuance in the phase's own record.", file=sys.stderr)
            return 1

    # ── a milestone emitted twice is not a milestone that happened twice ──
    #
    # Measured on 2026-08-31: `implement` ended `IMPLEMENTATION_COMPLETE` for B-169 at
    # 20:06:23 and again at 20:06:42. One conclusion, two records.
    #
    # This is DECLARED by the caller, not guessed here, and the reason is in the same
    # stream: `code-quality` ended `INVALID` three times in fourteen seconds for B-033,
    # and every one of those was a real run of the gate. Nineteen seconds apart, a
    # repeat and a duplicate look identical — any window that dropped the second
    # B-169 event would also drop two honest measurements.
    #
    # So the caller says which it is. A phase that CONCLUDES — implementation
    # complete, plan written, released — passes `--once`; a gate that iterates does
    # not. Refusing rather than silently skipping, because a caller that emitted twice
    # by accident should learn of it.
    # The duplicate check reads the stream and the emit below appends to it. Nothing
    # serialised the two, and concurrent writers of one stream are an explicit feature of
    # this kit — `mechanisms/fleet` dispatches lanes in parallel and each runs the phase
    # commands that emit here. Two sessions could both read a stream whose last line was
    # not yet the other's, and both append. The lock spans read AND append.
    #
    # What is NOT changed here: the duplicate test still compares against the LAST
    # event. Scanning backward for a matching end was the other half of the proposal,
    # and it contradicts the semantics this file already carries and the suite pins —
    # "anything since" is how a caller says the phase ran a second time, and
    # `test_once_allows_the_same_verdict_after_something_else_ran` asserts exactly
    # that. A backward scan would refuse a legitimate second run.
    stream = resolve_events_path(root)
    once_guard = shared_file.locked(stream) if args.once and args.transition == "end" \
        else contextlib.nullcontext()
    with once_guard:
        return _emit_under_guard(args, root)


def _emit_under_guard(args: argparse.Namespace, root: Path) -> int:
    if args.once and args.transition == "end":
        previous = read_events(root)
        if previous:
            last = previous[-1]
            same = (last.get("type") == "cycle:phase:end"
                    and last.get("cycle") == args.cycle
                    and str(last.get("slug") or "") == str(args.slug or "")
                    and last.get("verdict") == args.verdict)
            if same:
                print(f"REFUSED: `{args.cycle}` already ended `{args.verdict}` for "
                      f"{args.slug} at {last.get('timestamp')}, with nothing since. "
                      f"`--once` says this phase concludes rather than iterates, so a "
                      f"second identical record would report a milestone that happened "
                      f"twice. Drop the second call, or omit --once if the phase really "
                      f"ran again.", file=sys.stderr)
                return 1

    if args.transition == "start":
        event = emit_phase_start(root, cycle=args.cycle, slug=args.slug)
    else:
        event = emit_phase_end(root, cycle=args.cycle, slug=args.slug,
                               verdict=args.verdict, artifact=args.artifact)
        repeats = unchanged_repeats(read_events(root), cycle=args.cycle, slug=args.slug)
        if event is not None and repeats >= REPEAT_THRESHOLD:
            print(f"NOTE: `{args.cycle}` ended `{args.verdict}` for {args.slug} "
                  f"{repeats} times in a row on an unchanged {args.artifact}. Running it "
                  f"again will answer the same; read what the refusal says it accepts, "
                  f"or change the artifact.", file=sys.stderr)

    if event is None:
        # Fail-open reaches the CLI too: a hook must not turn a write failure
        # into a blocked session.
        print("cycle-events: could not write the stream (continuing)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

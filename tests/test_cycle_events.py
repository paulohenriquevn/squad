"""A phase transition leaves an event, not an archaeological trace.

THE DEFECT THIS CLOSES
----------------------
Today the only proof that a cycle phase ran is a file appearing in one of the
**15 record directories** under `records/`, reconstructed afterwards by
`phase_coverage.py`. That reconstruction cannot separate two very different
states, and this repository has already paid for the confusion:

    "the ecosystem could not tell 'the phase was skipped' from 'the phase ran
    and left nothing'"

— recorded when `phase_coverage.py` measured `code-quality` at 15%. The
measurement was right and the instrument could not explain itself, because a
missing file is evidence of nothing in particular.

An event emitted at the moment of transition has no such ambiguity: it is in the
stream, or it is not.

WHAT THIS MODULE REFUSES TO DO
------------------------------
It does not decide whether a phase *should* have run — that is
`check_phase_drift.py`'s question, and answering it here would fold the record
and its judge into one artefact, which is exactly the shape that lets a plan and
its execution drift without anyone noticing.

It also never raises. A phase that did real work must not fail because its
bookkeeping could not be written; the same fail-open discipline `session-goal`'s
gate applies, and for the same reason.

WHY THERE IS NO SEQUENCE NUMBER
-------------------------------
Line order in an append-only file already is the sequence. A `seq` field derived
from a line count would race under concurrent writers and hand the reader a
number that looks authoritative and is not — a smaller version of the defect
this whole movement is about.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "mechanisms" / "cycle"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from cycle_events import (  # noqa: E402 — post-bootstrap import
    EVENTS_FILENAME,
    emit_phase_end,
    emit_phase_start,
    read_events,
    resolve_events_path,
)


def _events(root: Path) -> list[dict]:
    return read_events(root)


# ---------------------------------------------------------------------------
# Where the stream lives
# ---------------------------------------------------------------------------

def test_the_stream_lands_in_the_one_write_root(tmp_path: Path) -> None:
    """`<project>/.squad/records/` — and nowhere else.

    This used to answer differently per layout, and the layout question is exactly
    what produced the defect this stream exists to reveal: running the instrumented
    `/code-quality` against the kit's own repository created
    `.claude/records/cycle-events.jsonl` at the root, the **split trail** that
    `backlog-review` reports as MAJOR. A stream that plants the defect it was built to
    reveal is worse than no stream.

    One root removes the question rather than answering it more carefully.
    """
    assert resolve_events_path(tmp_path) == (
        tmp_path / ".squad" / "records" / EVENTS_FILENAME
    )


def test_the_standalone_layout_gets_the_same_root(tmp_path: Path) -> None:
    """The kit's own repository is no longer an exception.

    It was: `records/` at the root for standalone, `.claude/records/` for a plugin
    install. Two answers meant two ways to be wrong, and the exception is what the
    first instrumented run tripped over.
    """
    for directory in ("skills", "rules", "hooks"):
        (tmp_path / directory).mkdir()

    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")

    assert (tmp_path / ".squad" / "records" / EVENTS_FILENAME).is_file()
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / "records").exists()


def test_a_plugin_install_gets_the_same_root(tmp_path: Path) -> None:
    """`.claude/` holds the installed kit and receives nothing this system writes."""
    (tmp_path / ".claude" / "skills").mkdir(parents=True)

    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")

    assert (tmp_path / ".squad" / "records" / EVENTS_FILENAME).is_file()
    assert not (tmp_path / ".claude" / "records").exists()


def test_a_legacy_trail_does_not_capture_the_writer(tmp_path: Path) -> None:
    """Writers never fall back, and the old trail is left exactly as it was.

    Readers fall back so an unmigrated consumer keeps working. A writer that fell back
    would keep every project on its old root forever, and the centralisation would be a
    sentence in a rule with nothing behind it. Moving the old trail is a person's job:
    a migration this code performed inside a consumer's repository would be the kit
    writing to a project it does not own.
    """
    legacy = tmp_path / ".claude" / "records"
    legacy.mkdir(parents=True)
    (legacy / EVENTS_FILENAME).write_text('{"old": true}\n', encoding="utf-8")

    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")

    assert (tmp_path / ".squad" / "records" / EVENTS_FILENAME).is_file()
    assert (legacy / EVENTS_FILENAME).read_text(encoding="utf-8") == '{"old": true}\n'


def test_a_fresh_adopter_does_not_lose_its_first_phase(tmp_path: Path) -> None:
    """No root on disk yet, and the first phase to run must not be the one that
    leaves no record."""
    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")

    assert (tmp_path / ".squad" / "records" / EVENTS_FILENAME).is_file()


# ---------------------------------------------------------------------------
# What an event carries
# ---------------------------------------------------------------------------

def test_a_start_event_names_the_cycle_and_the_slug(tmp_path: Path) -> None:
    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")

    events = _events(tmp_path)

    assert len(events) == 1
    assert events[0]["type"] == "cycle:phase:start"
    assert events[0]["cycle"] == "code-quality"
    assert events[0]["slug"] == "demo"
    assert events[0]["timestamp"].endswith("Z")


def test_an_end_event_carries_the_verdict(tmp_path: Path) -> None:
    """The verdict is what a downstream gate reads. `/review` refusing to run on
    a `FAIL_HARD` audit is the existing case; the stream makes that answerable
    without opening the report."""
    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")
    emit_phase_end(tmp_path, cycle="code-quality", slug="demo", verdict="FAIL_SOFT")

    end = _events(tmp_path)[-1]

    assert end["type"] == "cycle:phase:end"
    assert end["verdict"] == "FAIL_SOFT"


def test_an_end_event_without_a_verdict_says_so_rather_than_inventing_one(tmp_path: Path) -> None:
    """Not every phase computes a verdict. `null` is the honest field; omitting
    it would make a verdict-less phase indistinguishable from an unparsed one."""
    emit_phase_end(tmp_path, cycle="discover", slug="demo")

    assert _events(tmp_path)[-1]["verdict"] is None


def test_events_are_appended_in_order(tmp_path: Path) -> None:
    for cycle in ("plan", "implement", "code-quality"):
        emit_phase_start(tmp_path, cycle=cycle, slug="demo")

    assert [e["cycle"] for e in _events(tmp_path)] == ["plan", "implement", "code-quality"]


def test_each_event_is_one_json_line(tmp_path: Path) -> None:
    """The stream is consumed by `jq`, by a tail, and by scripts that read a line
    at a time. A pretty-printed object would break all three."""
    emit_phase_start(tmp_path, cycle="plan", slug="demo")
    emit_phase_end(tmp_path, cycle="plan", slug="demo", verdict="PASS")

    raw = resolve_events_path(tmp_path).read_text(encoding="utf-8").splitlines()

    assert len(raw) == 2
    for line in raw:
        assert json.loads(line)


def test_extra_fields_travel_when_given(tmp_path: Path) -> None:
    emit_phase_end(tmp_path, cycle="code-quality", slug="demo",
                   verdict="PASS", languages=["python"], findings=0)

    end = _events(tmp_path)[-1]

    assert end["languages"] == ["python"]
    assert end["findings"] == 0


def test_a_non_json_safe_extra_is_refused_at_the_boundary(tmp_path: Path) -> None:
    """A stream that cannot be parsed is worse than no stream: every reader
    downstream fails on a line nobody can fix without the original process."""
    emit_phase_end(tmp_path, cycle="demo", slug="demo", verdict="PASS", when=object())

    end = _events(tmp_path)[-1]

    assert isinstance(end["when"], str), "an unserializable value is coerced, not dropped"
    assert "object" in end["when"]


# ---------------------------------------------------------------------------
# Fail-open
# ---------------------------------------------------------------------------

def test_an_unwritable_destination_does_not_raise(tmp_path: Path, monkeypatch) -> None:
    """A phase that did real work must not fail because its bookkeeping could
    not be written. Same discipline as `session-goal`'s gate, same reason."""
    def _boom(*_args, **_kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr("cycle_events._append_line", _boom)

    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")  # must not raise


def test_reading_a_corrupt_stream_skips_the_bad_line(tmp_path: Path) -> None:
    """One truncated line — a killed process mid-write — must not blind the
    reader to every event around it."""
    emit_phase_start(tmp_path, cycle="plan", slug="demo")
    path = resolve_events_path(tmp_path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"type": "cycle:phase:st\n')
    emit_phase_end(tmp_path, cycle="plan", slug="demo", verdict="PASS")

    events = read_events(tmp_path)

    assert [e["type"] for e in events] == ["cycle:phase:start", "cycle:phase:end"]


def test_reading_an_absent_stream_returns_empty_not_an_error(tmp_path: Path) -> None:
    assert read_events(tmp_path) == []


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["", "   "])
def test_an_empty_cycle_name_is_refused(tmp_path: Path, bad: str) -> None:
    """An event that does not say which phase it belongs to records nothing.

    This one raises rather than failing open: a caller passing an empty cycle is
    a coding error at the call site, not a runtime condition of the environment.
    """
    with pytest.raises(ValueError):
        emit_phase_start(tmp_path, cycle=bad, slug="demo")


def test_the_cli_emits_from_a_shell_hook(tmp_path: Path) -> None:
    """Hooks are shell. A phase boundary that only Python can record would leave
    the hook layer — the part that runs on every session — unable to emit."""
    import subprocess

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "mechanisms" / "cycle" / "cycle_events.py"),
         "start", "--cycle", "review", "--slug", "demo",
         "--project-root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert _events(tmp_path)[0]["cycle"] == "review"


# ---------------------------------------------------------------------------
# Where the event lands when the phase runs somewhere else
# ---------------------------------------------------------------------------

def test_the_project_root_is_derived_from_the_work_not_from_cwd(tmp_path: Path) -> None:
    """A phase records against the project it acted on, not the shell's cwd.

    Found in a real install: `mechanisms/distribution/install.sh` runs the e2e smoke, which
    exercises `consolidate_findings.py` against a synthetic plan in a tmpdir
    while cwd is the ADOPTER's repository. With the root taken from cwd, a
    freshly installed project got a `review` event for a review it never ran —
    a record asserting a phase happened because a smoke test used the same
    process. Milder than fabricated evidence, and the same shape.
    """
    from cycle_events import project_root_for

    work = tmp_path / "elsewhere" / "records" / "reviews" / "demo"
    work.mkdir(parents=True)
    (tmp_path / "elsewhere" / ".claude" / "records").mkdir(parents=True)

    assert project_root_for(work) == tmp_path / "elsewhere"


def test_a_work_path_with_no_knowledge_base_above_it_falls_back_to_its_own_tree(
    tmp_path: Path,
) -> None:
    """A smoke run in a bare tmpdir must land its event there — inside the
    throwaway tree — rather than escaping into whatever repository the shell
    happened to be sitting in."""
    from cycle_events import project_root_for

    work = tmp_path / "tmpwork" / "findings"
    work.mkdir(parents=True)

    root = project_root_for(work)

    assert tmp_path in root.parents or root == tmp_path / "tmpwork" / "findings" or root.is_relative_to(tmp_path)


def test_a_file_is_resolved_from_its_directory(tmp_path: Path) -> None:
    """Callers pass what they have: a criteria FILE, a findings DIRECTORY.

    Treating a file as a directory made the walk start one level too deep and
    return the file itself as the project root, so the stream would have been
    written under `criteria.json/.claude/`. Caught by the acceptance `main()`
    test written two steps earlier — which is the whole reason it was written.
    """
    from cycle_events import project_root_for

    (tmp_path / ".claude" / "records").mkdir(parents=True)
    criteria = tmp_path / "criteria.json"
    criteria.write_text("{}", encoding="utf-8")

    assert project_root_for(criteria) == tmp_path


# ── the CLI normalises the root, like every Python caller does ────────────────
#
# It did not, and the two paths disagreed. Measured on 2026-08-31 in a replica of a
# consumer layout: emitting from a deep subdirectory with `--project-root .` created a
# SECOND stream under that subdirectory, invisible to anything reading the project
# root — and a phase whose event lands in an orphan file reads exactly like a phase
# that was skipped, which is the one distinction this module exists to make.


def _consumer(tmp_path):
    """A project with the kit installed under `.claude/`, as consumers have it."""
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / "records").mkdir()
    deep = tmp_path / "api" / "internal"
    deep.mkdir(parents=True)
    return tmp_path, deep


def test_the_cli_emits_to_the_project_root_from_a_deep_subdirectory(tmp_path):
    from cycle_events import main

    root, deep = _consumer(tmp_path)
    assert main(["end", "--cycle", "plan", "--slug", "B-014",
                 "--verdict", "PLAN_WRITTEN", "--project-root", str(deep)]) == 0

    streams = sorted(p.relative_to(root).as_posix() for p in root.rglob("cycle-events.jsonl"))
    assert streams == [".squad/records/cycle-events.jsonl"], streams


def test_the_cli_and_the_python_caller_write_to_the_same_place(tmp_path):
    """Two entry points writing to two files is the defect, whatever each one does."""
    from cycle_events import emit_phase_end, main, project_root_for

    root, deep = _consumer(tmp_path)
    main(["end", "--cycle", "plan", "--verdict", "PLAN_WRITTEN", "--project-root", str(deep)])
    emit_phase_end(project_root_for(deep), cycle="release", slug="", verdict="RELEASED")

    streams = list(root.rglob("cycle-events.jsonl"))
    assert len(streams) == 1, [p.as_posix() for p in streams]
    assert streams[0].read_text(encoding="utf-8").count("\n") == 2


def test_an_event_emitted_deep_is_readable_from_the_root(tmp_path):
    """What ADVANCE does: read the project's stream and find the phase that ran."""
    from cycle_events import main, read_events

    root, deep = _consumer(tmp_path)
    main(["end", "--cycle", "release", "--slug", "B-014",
          "--verdict", "RELEASED", "--project-root", str(deep)])

    released = [e for e in read_events(root)
                if e.get("cycle") == "release" and e.get("verdict") == "RELEASED"]
    assert len(released) == 1
    assert released[0]["slug"] == "B-014"


# ── a phase nobody declared is written and then dropped ───────────────────────
#
# Measured on the first autonomous run: the executing session called this CLI with
# `--cycle deps-audit` and `--cycle idea-to-release`, neither in cycle-phases.txt. No
# static sweep could catch it — the emitter was an agent at runtime, not a line of
# code — so the write is the only place it can be caught.


def _with_phases(tmp_path, *names):
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "records").mkdir(exist_ok=True)
    (tmp_path / "rules" / "cycle-phases.txt").write_text(
        "# a comment\n" + "".join(f"{n} | conditional | what it does\n" for n in names),
        encoding="utf-8")
    return tmp_path


def test_a_declared_phase_is_written(tmp_path):
    from cycle_events import main

    root = _with_phases(tmp_path, "backlog", "plan")
    assert main(["end", "--cycle", "plan", "--verdict", "OK", "--project-root", str(root)]) == 0
    assert list(root.rglob("cycle-events.jsonl"))


def test_an_undeclared_phase_is_refused_and_writes_nothing(tmp_path):
    """Fail-open here would put an invisible event in the stream and report success."""
    from cycle_events import main

    root = _with_phases(tmp_path, "backlog", "plan")
    assert main(["end", "--cycle", "deps-audit", "--verdict", "PASS",
                 "--project-root", str(root)]) == 1
    assert not list(root.rglob("cycle-events.jsonl"))


def test_an_unreadable_declaration_permits_rather_than_blocks(tmp_path):
    """"Cannot check" must not become "cannot record" — the stream is the point."""
    from cycle_events import main

    (tmp_path / "records").mkdir(parents=True)
    assert main(["end", "--cycle", "anything", "--verdict", "OK",
                 "--project-root", str(tmp_path)]) == 0


def test_the_declaration_is_found_under_dot_claude_too(tmp_path):
    """In an installed consumer the rules live under `.claude/`."""
    from cycle_events import declared_phases

    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "cycle-phases.txt").write_text(
        "review | conditional | x\n", encoding="utf-8")
    assert declared_phases(tmp_path) == {"review"}


# ── a verdict the phase does not declare ──────────────────────────────────────
#
# Measured on the first autonomous run: the plan phase returned INVALID — a real
# verdict from a real hard cap — and the session recorded `INVALID_AWAITING_HUMAN`, a
# name in no contract and no skill, invented to express that it was stopping. The
# stream then said something no reader could act on, about a phase that really ran.


def _with_rule(tmp_path, phase: str, verdicts: list[str] | None):
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "records").mkdir(exist_ok=True)
    body = f"# Cycle: {phase}\n\n"
    if verdicts is not None:
        body += "## Verdicts\n\n" + "".join(f"- `{v}` — meaning\n" for v in verdicts)
    (tmp_path / "rules" / f"cycle-{phase}.md").write_text(body, encoding="utf-8")
    (tmp_path / "rules" / "cycle-phases.txt").write_text(
        f"{phase} | conditional | x\n", encoding="utf-8")
    return tmp_path


def test_an_invented_verdict_is_refused(tmp_path):
    from cycle_events import main

    root = _with_rule(tmp_path, "plan", ["INVALID", "SHIPPABLE"])
    assert main(["end", "--cycle", "plan", "--verdict", "INVALID_AWAITING_HUMAN",
                 "--project-root", str(root)]) == 1
    assert not list(root.rglob("cycle-events.jsonl"))


def test_a_declared_verdict_is_written(tmp_path):
    from cycle_events import main

    root = _with_rule(tmp_path, "plan", ["INVALID", "SHIPPABLE"])
    assert main(["end", "--cycle", "plan", "--verdict", "INVALID",
                 "--project-root", str(root)]) == 0


def test_a_phase_declaring_no_verdicts_accepts_any(tmp_path):
    """`implement` and `code-quality` emit real verdicts from rules with no section.

    Refusing those would break honest emitters in order to catch a dishonest one.
    """
    from cycle_events import main

    root = _with_rule(tmp_path, "implement", None)
    assert main(["end", "--cycle", "implement", "--verdict", "VALIDATED",
                 "--project-root", str(root)]) == 0


def test_an_event_without_a_verdict_is_unaffected(tmp_path):
    from cycle_events import main

    root = _with_rule(tmp_path, "plan", ["INVALID"])
    assert main(["start", "--cycle", "plan", "--project-root", str(root)]) == 0


# ── a milestone emitted twice is not a milestone that happened twice ─────────


def test_once_refuses_an_identical_end_with_nothing_since(tmp_path):
    """Measured on 2026-08-31: `implement` ended `IMPLEMENTATION_COMPLETE` for B-169 at
    20:06:23 and again at 20:06:42. One conclusion, two records."""
    from cycle_events import main

    root, deep = _consumer(tmp_path)
    args = ["end", "--cycle", "implement", "--slug", "B-169",
            "--verdict", "IMPLEMENTATION_COMPLETE", "--project-root", str(deep)]
    assert main(args + ["--once"]) == 0
    assert main(args + ["--once"]) == 1
    stream = (root / ".squad" / "records" / "cycle-events.jsonl").read_text(encoding="utf-8")
    assert stream.count("IMPLEMENTATION_COMPLETE") == 1


def test_without_once_a_repeat_is_recorded(tmp_path):
    """`code-quality` ended `INVALID` three times in fourteen seconds for B-033, and
    every one was a real run of the gate. Nineteen seconds apart, a repeat and a
    duplicate look identical — so the caller declares which it is, and the default
    records everything."""
    from cycle_events import main

    root, deep = _consumer(tmp_path)
    args = ["end", "--cycle", "code-quality", "--slug", "b033-x",
            "--verdict", "INVALID", "--project-root", str(deep)]
    assert main(args) == 0
    assert main(args) == 0
    stream = (root / ".squad" / "records" / "cycle-events.jsonl").read_text(encoding="utf-8")
    assert stream.count("INVALID") == 2


def test_once_allows_the_same_verdict_after_something_else_ran(tmp_path):
    """The phase really did run again. `--once` catches a double call, not a second
    execution — which is why it compares against the LAST event, not the whole file."""
    from cycle_events import main

    root, deep = _consumer(tmp_path)
    done = ["end", "--cycle", "implement", "--slug", "B-169",
            "--verdict", "IMPLEMENTATION_COMPLETE", "--project-root", str(deep), "--once"]
    assert main(done) == 0
    assert main(["end", "--cycle", "code-quality", "--slug", "B-169",
                 "--verdict", "FAIL_SOFT", "--project-root", str(deep)]) == 0
    assert main(done) == 0
    stream = (root / ".squad" / "records" / "cycle-events.jsonl").read_text(encoding="utf-8")
    assert stream.count("IMPLEMENTATION_COMPLETE") == 2

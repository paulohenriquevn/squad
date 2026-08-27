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
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from cycle_events import (  # noqa: E402
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

def test_the_stream_lands_in_the_canonical_knowledge_base(tmp_path: Path) -> None:
    """`rules/records-location.md` makes `.claude/records/` canonical
    in a plugin install. A second stream beside the first is the split
    records this ecosystem classifies as MAJOR."""
    (tmp_path / ".claude" / "records").mkdir(parents=True)

    assert resolve_events_path(tmp_path) == (
        tmp_path / ".claude" / "records" / EVENTS_FILENAME
    )


def test_the_standalone_layout_is_served_too(tmp_path: Path) -> None:
    (tmp_path / "records").mkdir()
    assert resolve_events_path(tmp_path) == tmp_path / "records" / EVENTS_FILENAME


def test_a_project_with_no_knowledge_base_gets_the_canonical_one_created(tmp_path: Path) -> None:
    """A fresh adopter has no records yet, and the first phase to run must
    not be the one that loses its record."""
    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")

    assert (tmp_path / ".claude" / "records" / EVENTS_FILENAME).is_file()


def test_the_standalone_repo_never_gets_a_dot_claude_knowledge_base(tmp_path: Path) -> None:
    """The kit's own repository is the one place `.claude/records/` is wrong.

    `rules/records-location.md` states the single exception: in the
    standalone layout — `skills/`, `rules/` and `hooks/` at the root, no
    `.claude/` wrapper — the records is `<repo>/records/`.

    Caught by running the instrumented `/code-quality` against this repository:
    the first emit created `.claude/records/cycle-events.jsonl` at the
    root, which is precisely the **split records** the CHANGELOG records
    the test suite having planted before, and that `backlog-review` reports as
    MAJOR. A stream that plants the defect it was built to reveal is worse than
    no stream.
    """
    for directory in ("skills", "rules", "hooks"):
        (tmp_path / directory).mkdir()

    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")

    assert (tmp_path / "records" / EVENTS_FILENAME).is_file()
    assert not (tmp_path / ".claude").exists(), (
        "the standalone layout must not grow a .claude/ wrapper"
    )


def test_an_existing_dot_claude_still_wins_in_a_consumer(tmp_path: Path) -> None:
    """A consumer that installed by copy has `.claude/skills/` — and its
    records stays canonical. The standalone exception is about the kit's
    own repo, not about any project that happens to own a `skills/` folder."""
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    (tmp_path / "skills").mkdir()

    emit_phase_start(tmp_path, cycle="code-quality", slug="demo")

    assert (tmp_path / ".claude" / "records" / EVENTS_FILENAME).is_file()


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
        [sys.executable, str(REPO_ROOT / "scripts" / "cycle_events.py"),
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

    Found in a real install: `scripts/install.sh` runs the e2e smoke, which
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

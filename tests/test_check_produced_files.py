"""The runtime half of the containment guarantee, and the ways it could lie.

`check_write_containment.py` proves a static property; this one runs the mechanisms
and looks at the disk, because tracing 135 write call sites through the AST left 64 of
them UNKNOWN — the destination arrives as a parameter or is built across functions. A
proof with a 47% hole is not a proof.

The tests that matter are the ones about the gate's own honesty: a probe that errored
must not count as coverage, and an exemption without a reason must not be accepted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "mechanisms" / "gates"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_produced_files import (  # noqa: E402 — post-bootstrap import
    _HOME_CALL,
    ACCEPTED_EXITS,
    HOME_WRITERS,
    Exemption,
    Report,
    _matches,
    parse_exemptions,
    render,
    scan_home_writers,
)

# ------------------------------------------------------------------ exemptions


def test_an_exemption_without_a_reason_is_refused(tmp_path: Path) -> None:
    """"We made an exception" and "the platform gave us no choice" are different
    claims, and only the second survives review — so the row has to say which."""
    f = tmp_path / "ex.txt"
    f.write_text("some/path | platform\n", encoding="utf-8")

    with pytest.raises(ValueError, match="needs `<path> | <class> | <reason>`"):
        parse_exemptions(f)


def test_an_invented_class_is_refused(tmp_path: Path) -> None:
    f = tmp_path / "ex.txt"
    f.write_text("some/path | convenience | it was easier this way honestly\n",
                 encoding="utf-8")

    with pytest.raises(ValueError, match="not one of platform/tool/human"):
        parse_exemptions(f)


def test_a_reason_too_short_to_name_anything_is_refused(tmp_path: Path) -> None:
    """A five-word floor does not make a reason true. It makes "legacy" insufficient."""
    f = tmp_path / "ex.txt"
    f.write_text("some/path | tool | legacy reasons\n", encoding="utf-8")

    with pytest.raises(ValueError, match="word"):
        parse_exemptions(f)


def test_the_kits_own_exemptions_all_parse() -> None:
    exemptions = parse_exemptions(KIT / "rules" / "write-exemptions.txt")

    assert exemptions
    assert all(e.klass in {"platform", "tool", "human"} for e in exemptions)
    assert all(len(e.reason.split()) >= 5 for e in exemptions)


def test_eco_in_a_glob_stands_for_the_install(tmp_path: Path) -> None:
    """A plugin install nests the kit; the same row must cover both layouts."""
    e = Exemption("<eco>/agents/*.md", "platform", "Claude Code resolves it by directory")

    assert _matches(".claude/agents/backend.md", e, ".claude")
    assert not _matches(".squad/agents/backend.md", e, ".claude")


# ------------------------------------------------------------------ honesty


def test_a_probe_that_errored_does_not_count_as_coverage() -> None:
    """The gate committed this defect against itself before this test existed.

    Six probes were added, all six reported as run, and the produced-file count did
    not move — every new one had died on an argparse error. A sweep that reports
    eleven mechanisms and exercises six is exactly the substitution this gate exists
    to prevent.
    """
    assert 2 not in ACCEPTED_EXITS, (
        "2 means `could not measure` across this kit, and a probe that could not "
        "measure did not exercise its writer")
    assert {0, 1, 3} <= ACCEPTED_EXITS, (
        "1 and 3 are verdicts a mechanism REACHES about an artifact — the mechanism "
        "ran. Refusing them would report healthy findings as broken probes")


def test_a_sweep_with_no_probe_is_not_a_pass() -> None:
    r = Report(False, 0, 6, unmeasured_because="no probe ran; nothing was exercised")

    out = render(r)

    assert "NOT MEASURED" in out
    assert "CONTAINED" not in out


def test_the_report_states_its_own_coverage() -> None:
    """A green run over three probes is worth what three probes are worth, and the
    reader must be able to see which number they got."""
    r = Report(True, 4, 11, produced=["a"], exempted=[])

    out = render(r)

    assert "4/11" in out
    assert "A writer no probe reaches was not examined" in out


def test_a_skipped_probe_is_named_in_the_report() -> None:
    r = Report(True, 1, 2, probes_failed=["spawn_reviewers — exit 2: missing --slug"])

    out = render(r)

    assert "spawn_reviewers" in out
    assert "missing --slug" in out


def test_an_escape_is_reported_with_what_to_do() -> None:
    r = Report(False, 3, 3, escaped=[{"path": "stray.json", "why": "route it through squad.paths"}])

    out = render(r)

    assert "ESCAPED" in out
    assert "stray.json" in out


# ------------------------------------------------------------------ the real sweep



def test_the_kit_contains_what_it_produces() -> None:
    """The gate against this repository. It seeds a scratch project and runs
    every probe, which is the only way the question gets a real answer."""
    from check_produced_files import check

    r = check(KIT)

    assert not r.unmeasured_because, r.unmeasured_because
    assert r.probes_run >= 1, r.probes_failed
    assert r.contained, [e["path"] for e in r.escaped]


# ------------------------------------------------------------------ outside the project


def test_normalising_a_user_path_is_not_a_home_write() -> None:
    """`--project ~/repo` has to be expanded, and expanding it writes nothing.

    The first version of this check flagged `.expanduser()` too and reported four
    call sites that only resolve an argument — the shape of a check people learn to
    ignore. `Path.home()` CONSTRUCTS a destination; `x.expanduser()` normalises one.
    """
    assert not _HOME_CALL.search("project = args.project.expanduser().resolve()")
    assert not _HOME_CALL.search("root = Path(target).expanduser()")
    assert _HOME_CALL.search('base = Path.home() / ".claude"')
    assert _HOME_CALL.search('p = os.path.expanduser("~/x")')


def test_an_undeclared_home_writer_is_an_escape(tmp_path: Path) -> None:
    """The runtime sweep snapshots the scratch PROJECT, so a write to `$HOME` lands
    outside it and leaves no trace. This is the only thing that would catch it."""
    (tmp_path / "mechanisms").mkdir()
    (tmp_path / "mechanisms" / "stray.py").write_text(
        'from pathlib import Path\n\nout = Path.home() / ".stray" / "log.jsonl"\n',
        encoding="utf-8")

    findings = scan_home_writers(tmp_path)

    assert [f["file"] for f in findings] == ["mechanisms/stray.py"]


def test_a_declared_home_writer_is_not_an_escape(tmp_path: Path) -> None:
    rel = next(iter(HOME_WRITERS))
    target = tmp_path / rel
    target.parent.mkdir(parents=True)
    target.write_text('from pathlib import Path\n\nx = Path.home()\n', encoding="utf-8")

    assert scan_home_writers(tmp_path) == []


def test_tests_are_not_scanned_for_home_writes(tmp_path: Path) -> None:
    """A fixture may build a fake home; only production code is constrained."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(
        'from pathlib import Path\n\nh = Path.home()\n', encoding="utf-8")

    assert scan_home_writers(tmp_path) == []


def test_every_declared_home_writer_still_exists() -> None:
    """A declaration for a file that moved is an exemption protecting nothing, and
    it would silently stop covering whatever took the path over."""
    missing = [rel for rel in HOME_WRITERS if not (KIT / rel).is_file()]

    assert not missing, missing


def test_every_home_writer_reason_names_something() -> None:
    for rel, reason in HOME_WRITERS.items():
        assert len(reason.split()) >= 10, f"{rel}: {reason}"

"""B-103 — a fix that lands in one tree and not the other must be visible before it is archaeology.

Twenty-two fixes to this kit lived for weeks in a consumer's gitignored `.claude/` install and
nowhere else. Nobody hid them; nothing looked. `sync_consumers.py` propagates kit -> consumer and
answers "is the consumer behind"; this answers the question that went unasked, "have the two
drifted, and which way".

The classification is deliberately line-set based rather than a diff: the question is not "are
these byte-identical" (they never are, once a comment is reworded) but "does one side hold work the
other lacks". A file where BOTH sides hold unique lines is the only case needing a human, and it is
the case a blind copy destroys — measured on `run_code_quality.py`, where copying the install over
the kit would have deleted B-092's zero-detector check.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Annotated as `pytest.MonkeyPatch` below and never imported. It passed only because
# `from __future__ import annotations` makes the annotation a string that is never
# evaluated — remove that line, or evaluate the annotation the way `typing.get_type_hints`
# and several runtime validators do, and it raises NameError (ruff F821, kit#59).
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from check_install_drift import Drift, classify_file, main, scan


def _write(p: Path, body: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_identical_files_are_not_drift(tmp_path: Path) -> None:
    a = _write(tmp_path / "a" / "f.py", "x = 1\ny = 2\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\ny = 2\n")
    assert classify_file(a, b) is Drift.IDENTICAL


def test_whitespace_only_difference_is_not_drift(tmp_path: Path) -> None:
    """Blank lines are not work. Reporting them would train people to ignore the report."""
    a = _write(tmp_path / "a" / "f.py", "x = 1\n\n\ny = 2\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\ny = 2\n")
    assert classify_file(a, b) is Drift.IDENTICAL


def test_install_holding_extra_lines_is_install_ahead(tmp_path: Path) -> None:
    a = _write(tmp_path / "a" / "f.py", "x = 1\ny = 2\nz = 3\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\ny = 2\n")
    assert classify_file(a, b) is Drift.INSTALL_AHEAD


def test_kit_holding_extra_lines_is_kit_ahead(tmp_path: Path) -> None:
    a = _write(tmp_path / "a" / "f.py", "x = 1\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\ny = 2\n")
    assert classify_file(a, b) is Drift.KIT_AHEAD


def test_unique_lines_on_both_sides_is_diverged(tmp_path: Path) -> None:
    """The only class that needs a human — and the one a blind copy destroys."""
    a = _write(tmp_path / "a" / "f.py", "x = 1\nonly_install = True\n")
    b = _write(tmp_path / "b" / "f.py", "x = 1\nonly_kit = True\n")
    assert classify_file(a, b) is Drift.DIVERGED


def test_scan_reports_each_class_and_exits_nonzero_only_on_real_drift(tmp_path: Path) -> None:
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "same.py", "a\n")
    _write(kit / "same.py", "a\n")
    _write(install / "ahead.py", "a\nb\n")
    _write(kit / "ahead.py", "a\n")
    _write(install / "only-here.py", "a\n")

    report = scan(install, kit)

    assert report.counts[Drift.IDENTICAL] == 1
    assert report.counts[Drift.INSTALL_AHEAD] == 1
    assert report.only_in_install == ["only-here.py"]
    assert report.needs_attention is True   # INSTALL_AHEAD is unharvested work


def test_a_tree_that_matches_exactly_needs_no_attention(tmp_path: Path) -> None:
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "same.py", "a\n")
    _write(kit / "same.py", "a\n")

    assert scan(install, kit).needs_attention is False


def test_only_in_kit_is_reported_but_is_not_drift(tmp_path: Path) -> None:
    """A consumer that has not reinstalled is behind, which is sync_consumers' question, not this one."""
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "same.py", "a\n")
    _write(kit / "same.py", "a\n")
    _write(kit / "new-in-kit.py", "a\n")

    report = scan(install, kit)
    assert report.only_in_kit == ["new-in-kit.py"]
    assert report.needs_attention is False


def test_a_file_added_under_a_directory_the_kit_HAS_is_unharvested_work(tmp_path: Path) -> None:
    """B-103's `_layout.py` case: a whole file that existed in one tree only, and mattered."""
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "implement" / "scripts" / "known.py", "a\n")
    _write(kit / "implement" / "scripts" / "known.py", "a\n")
    _write(install / "implement" / "scripts" / "_layout.py", "a\n")

    report = scan(install, kit)
    assert report.unharvested_files == ["implement/scripts/_layout.py"]
    assert report.needs_attention is True


def test_a_directory_the_kit_does_not_have_at_all_is_a_consumer_artifact(tmp_path: Path) -> None:
    """`review-b052-…-knowledge/` is generated per review by the consumer. Thirty-eight of them.

    Failing on those would make the check red forever on any project that runs /review, which is
    every project — and a check that is always red is a check nobody reads.
    """
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "review" / "scripts" / "known.py", "a\n")
    _write(kit / "review" / "scripts" / "known.py", "a\n")
    _write(install / "review-b052-tests-knowledge" / "SKILL.md", "generated\n")

    report = scan(install, kit)
    assert report.unharvested_files == []
    assert report.only_in_install == ["review-b052-tests-knowledge/SKILL.md"]
    assert report.needs_attention is False


# --- ownership, at the moment a cleanup needs it (kit#33) ---------------------


def test_consumer_local_files_are_listable_and_not_just_countable(tmp_path: Path) -> None:
    """The count was printed; the paths were computed and thrown away.

    kit#33: a consumer's own `hooks/delivery-gate.sh` was deleted three times by a
    cleanup of `.claude/`, because nothing put the project's files in front of
    whoever was cleaning. The classification was already correct at that moment —
    it just had nowhere to be read. A number tells you that N files are yours; it
    does not tell you WHICH, which is the only form the answer is usable in.
    """
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "review" / "scripts" / "known.py", "a\n")
    _write(kit / "review" / "scripts" / "known.py", "a\n")
    _write(install / "hooks" / "delivery-gate.sh", "the project's own push gate\n")
    _write(install / "review-b052-tests-knowledge" / "SKILL.md", "generated\n")

    report = scan(install, kit)
    assert report.consumer_local_files == [
        "hooks/delivery-gate.sh",
        "review-b052-tests-knowledge/SKILL.md",
    ]
    # And it stays the complement of the other bucket, so no file is in both or neither.
    assert sorted(report.consumer_local_files + report.unharvested_files) == report.only_in_install


def test_the_consumer_local_flag_prints_each_path(tmp_path: Path, capsys) -> None:
    """`--consumer-local` is the named way to ask before deleting.

    Cheapest of the three shapes kit#33 proposed, and the one that converts an
    answer the kit already had into an answer somebody consults.
    """
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "review" / "scripts" / "known.py", "a\n")
    _write(kit / "review" / "scripts" / "known.py", "a\n")
    _write(install / "hooks" / "delivery-gate.sh", "the project's own push gate\n")

    code = main(["--install", str(install), "--kit", str(kit), "--consumer-local"])
    out = capsys.readouterr().out
    assert "hooks/delivery-gate.sh" in out
    assert code == 0, "listing what a consumer owns is a question, not a violation"


def test_the_consumer_local_flag_says_so_when_the_install_owns_nothing(
    tmp_path: Path, capsys
) -> None:
    """Silence reads as 'the tool did not run'. An empty answer must be spoken.

    This is the shape the kit refuses everywhere else: an inability, or an empty
    result, published as nothing at all. A cleanup reading blank output cannot
    tell it from a crash.
    """
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "review" / "scripts" / "known.py", "a\n")
    _write(kit / "review" / "scripts" / "known.py", "a\n")

    main(["--install", str(install), "--kit", str(kit), "--consumer-local"])
    out = capsys.readouterr().out
    # Both halves, not either: the count alone reads as a header with the list cut
    # off, and the sentence alone leaves nothing to compare against a later run.
    assert "consumer-local: 0" in out
    assert "no files" in out.lower()


# --- the gate can only run if something tells it where the kit came from ------


def test_the_installer_records_its_source_in_the_manifest() -> None:
    """`drift_line()` compares the install against a source it must be given.

    Until 2026-09-05 the only way to give it one was exporting `SQUAD_KIT_SOURCE`
    — a variable named in no README, no rule and no install output, only in the
    hook's own source. So the gate was wired and inert: #23 reported it cited
    nine times in prose and executed by nothing, and wiring it did not change
    that, because a consumer could not learn how to opt in.

    The installer knows the answer without being told. It copies FROM a directory
    and writes `.kit-manifest.txt` INTO the target on every install, so it
    records the source there and the opt-in disappears.
    """
    installer = (Path(__file__).resolve().parents[1]
                 / "mechanisms" / "distribution" / "install.sh").read_text(encoding="utf-8")
    assert '# kit-source: $SRC_DIR' in installer, (
        "install.sh no longer records where it copied from, so drift_line has "
        "nothing to fall back to and the gate returns to being opt-in-only"
    )


def test_the_hook_reads_the_manifest_when_the_variable_is_absent(tmp_path: Path) -> None:
    """The fallback, and the precedence between the two.

    `SQUAD_KIT_SOURCE` must keep winning when it is set: exporting it is an
    explicit choice, usually a second checkout, and a fallback that overrode it
    would be a defect of its own.
    """
    import importlib.util

    hook_path = (Path(__file__).resolve().parents[1]
                 / "hooks" / "sessionstart-context.py")
    spec = importlib.util.spec_from_file_location("_sc", hook_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_sc"] = mod
    spec.loader.exec_module(mod)

    eco = tmp_path / ".claude"
    eco.mkdir()
    (eco / ".kit-manifest.txt").write_text(
        "# Written by install.sh\n"
        "# kit-source: /srv/example/kit\n"
        "skills/backlog-review\n",
        encoding="utf-8",
    )

    class _Layout:
        pass

    layout = _Layout()
    layout.eco = eco

    assert mod._source_from_manifest(layout) == "/srv/example/kit"

    # No line, no answer — and it must not raise on a manifest without one.
    (eco / ".kit-manifest.txt").write_text("skills/backlog-review\n", encoding="utf-8")
    assert mod._source_from_manifest(layout) is None

    # Nor on a manifest that is not there at all.
    (eco / ".kit-manifest.txt").unlink()
    assert mod._source_from_manifest(layout) is None


def test_the_drift_line_names_where_the_source_actually_came_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The message is the reader's only pointer to what to go correct.

    The fallback shipped on 2026-09-05 printed `vs SQUAD_KIT_SOURCE=<path>` for a
    value that came from the manifest, so a reader debugging a wrong path would go
    inspect a variable that is empty and find nothing wrong with it. Found by
    running the hook in a real install rather than by reading it — the unit test
    for the fallback passed throughout, because it only ever called
    `_source_from_manifest` and never looked at what the message said.

    Asserted on the cannot-compare branch: a source that is not a kit returns the
    label without running the checker, which is the cheapest place the provenance
    is visible.
    """
    import importlib.util

    hook_path = (Path(__file__).resolve().parents[1]
                 / "hooks" / "sessionstart-context.py")
    spec = importlib.util.spec_from_file_location("_sc2", hook_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_sc2"] = mod
    spec.loader.exec_module(mod)

    eco = tmp_path / ".claude"
    eco.mkdir()
    not_a_kit = tmp_path / "not-a-kit"
    not_a_kit.mkdir()
    (eco / ".kit-manifest.txt").write_text(
        f"# kit-source: {not_a_kit}\nskills/backlog-review\n", encoding="utf-8")

    class _Layout:
        pass

    layout = _Layout()
    layout.eco = eco
    layout.kit_dir = eco

    monkeypatch.delenv("SQUAD_KIT_SOURCE", raising=False)
    line = mod.drift_line(layout)
    assert line is not None
    assert ".kit-manifest.txt=" in line, (
        "the value came from the manifest; naming the env var sends the reader to "
        f"check something empty. Got: {line}"
    )
    assert "SQUAD_KIT_SOURCE=" not in line

    # And the other way: when the variable IS what answered, it is what is named.
    monkeypatch.setenv("SQUAD_KIT_SOURCE", str(not_a_kit))
    line = mod.drift_line(layout)
    assert line is not None
    assert "SQUAD_KIT_SOURCE=" in line
    assert ".kit-manifest.txt=" not in line


def _printed_label() -> str:
    """The literal the gate prints, read out of the source before interpolation."""
    text = (Path(__file__).resolve().parents[1]
            / "mechanisms" / "gates" / "check_install_drift.py").read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines()
                if "install-only, in a directory the kit" in ln and "print(" in ln)
    start = line.index('"') + 1
    return line[start:line.index("{", start)].rstrip(": ")


def test_the_install_only_line_does_not_assert_whose_file_it_is() -> None:
    """One bucket, two meanings, and a diff cannot tell them apart.

    The label was written for B-103's `_layout.py` and `bump_version.py` — real kit
    work stranded in one consumer, which the kit should indeed harvest. The same
    bucket holds a project's OWN file living in a directory the kit also ships into,
    and for that one "unharvested" is the wrong instruction: harvesting a consumer's
    push gate into the kit would be the mistake.

    Measured 2026-09-05: a consumer's `hooks/delivery-gate.sh` was deleted three times
    and restored twice. The third deletion stood for days, and the cleanup that did it
    described nine shell hooks as kit leftovers — true of eight. This line is what a
    reader consults at that moment, so it must report what was observed and leave the
    reading open, rather than pick one and print it as the answer.

    Asserted on the printed LABEL, not the source line: the line also names
    `report.unharvested_files`, which is the field and may keep its name.
    """
    label = _printed_label()
    assert "unharvested" not in label, (
        f"{label!r} tells the reader the kit should take this file back, which is "
        f"only one of the two things this bucket holds"
    )
    for expected in ("yours", "harvest"):
        assert expected in label, (
            f"the label must state both readings; {expected!r} is missing from {label!r}"
        )


def test_the_session_hook_still_matches_the_line_it_surfaces() -> None:
    """The hook matches by PREFIX. Rewording the gate without the hook is a silence.

    This is the pairing that makes the rename safe: change one and this fails, which
    is what a cross-file string contract needs in place of a convention.
    """
    hook = (Path(__file__).resolve().parents[1]
            / "hooks" / "sessionstart-context.py").read_text(encoding="utf-8")
    label = _printed_label()
    import re

    prefixes = [m.group(1) for ln in hook.splitlines() if "install-only" in ln
                for m in [re.match(r'\s*"([^"]*)"', ln)] if m]
    assert prefixes, "the hook no longer carries a prefix for this line at all"
    for prefix in prefixes:
        assert label.startswith(prefix), (
            f"the gate prints {label!r} and the hook matches {prefix!r}, so the line "
            f"the hook exists to surface would stop being surfaced"
        )


def test_an_older_kit_version_is_still_recognised_through_the_batch_read(tmp_path) -> None:
    """`git show` was spawned once PER REVISION, with no cap and no early exit.

    A file with forty revisions cost forty processes — per file, per consumer. The blobs
    now arrive over one `git cat-file --batch` pipe, and the classification must not
    change: a body that matches an older kit version is STALE, not "needs a human".
    """
    import subprocess as sp

    from check_install_drift import _historical_contents

    kit = tmp_path / "kit"
    kit.mkdir()
    sp.run(["git", "-C", str(kit), "init", "-q"], check=True)
    target = kit / "rules" / "a-rule.md"
    target.parent.mkdir()
    for body in ("first version\n", "second version\n", "third version\n"):
        target.write_text(body, encoding="utf-8")
        sp.run(["git", "-C", str(kit), "add", "-A"], check=True)
        sp.run(["git", "-C", str(kit), "-c", "user.email=t@t", "-c", "user.name=t",
                "-c", "commit.gpgsign=false", "commit", "-qm", body.strip()], check=True)

    history = _historical_contents(kit, "rules/a-rule.md")

    assert history is not None
    assert {"first version\n", "second version\n", "third version\n"} <= history, history


def test_a_history_that_could_not_be_read_is_not_an_empty_history(tmp_path, capsys) -> None:
    """`set()` for a git failure made `body in history` false for every body.

    So a git failure reclassified every stale file as "needs a human" — the exact
    false-positive class this function was written to remove.
    """
    from check_install_drift import _historical_contents

    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    assert _historical_contents(not_a_repo, "rules/a-rule.md") is None
    assert "NOT determined" in capsys.readouterr().err


def test_a_versioned_install_does_not_report_its_own_git_objects() -> None:
    """`.git` was not in `_CONSUMER_LOCAL`.

    When `_installed_scope` returns None the walk covers the whole install root, so a
    consumer that versions its `.claude/` had every object under `.git/` reported as a
    consumer-local file — thousands of rows, with the signal underneath them invisible.
    """
    from check_install_drift import _CONSUMER_LOCAL

    assert ".git" in _CONSUMER_LOCAL

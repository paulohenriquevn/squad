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

sys.path.insert(0, str(Path(__file__).parent))

from check_install_drift import Drift, classify_file, scan


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

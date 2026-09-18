"""B-032 — a default that assumes the standalone layout creates the split records.

`rules/records-location.md`: `<project>/.claude/records/` is canonical, and the one
exception is the standalone kit repository. Two scripts in this skill defaulted to the standalone
path — `mini_review.py:379` (a WRITER) and `check_phase_review.py:145` (a READER) — so running the
mini review with defaults in a plugin install created a SECOND records at the project root.

The writer and the reader agreed with EACH OTHER while both disagreed with the rest of the
ecosystem, which is what made it quiet: nothing errors, the gate still passes, and a second tree
accumulates half the truth. The rule records the measured cost — three consumers in 2026-08 where
an audit read `.claude/` and reported "0 implementations, 0 reviews, 0 releases" for a repository
that had 6, 12 and 8.

The decisive evidence is a RECURRENCE: the defect was known for eight mini-review runs, and in every
one the operator passed the flag explicitly so the default never fired. On the ninth they did not,
and the split came back. Knowing about a bad default does not protect you from it.
"""
from __future__ import annotations

import sys as _s
from pathlib import Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _s.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import re  # noqa: E402 — post-bootstrap import
import subprocess  # noqa: E402 — post-bootstrap import
import sys  # noqa: E402 — post-bootstrap import
from pathlib import Path  # noqa: E402 — post-bootstrap import

from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _layout import default_mini_reviews_dir  # noqa: E402 — post-bootstrap import


def _plugin_root(tmp_path: Path) -> Path:
    root = tmp_path / "consumer"
    (root / ".claude").mkdir(parents=True)
    return root


def _standalone_root(tmp_path: Path) -> Path:
    root = tmp_path / "kit"
    (root / "skills").mkdir(parents=True)
    return root


def test_a_plugin_layout_resolves_to_the_write_root(tmp_path: Path) -> None:
    root = _plugin_root(tmp_path)

    resolved = default_mini_reviews_dir(root)

    assert resolved == write_records_dir(root, "mini-reviews")
    assert ".claude" not in resolved.parts, (
        "the installed kit receives nothing this system writes")


def test_a_standalone_layout_resolves_to_the_same_place(tmp_path: Path) -> None:
    """The kit's own repository was the one exception, and the exception is gone.

    It used to resolve to `<repo>/records/` while a plugin install resolved to
    `.claude/records/`. Two answers meant two ways to be wrong; there is one now, so
    this asserts that both layouts agree rather than that each is right.
    """
    root = _standalone_root(tmp_path)

    resolved = default_mini_reviews_dir(root)

    assert resolved == write_records_dir(root, "mini-reviews")
    assert ".claude" not in resolved.parts


def test_the_writer_defaults_under_dot_claude(tmp_path: Path) -> None:
    # The end-to-end shape: the writer is what CREATES the second tree, so asserting the resolver
    # alone would leave the wiring unpinned.
    root = _plugin_root(tmp_path)

    resolved = default_mini_reviews_dir(root)
    resolved.mkdir(parents=True)

    assert not (root / "records").exists()


def test_no_script_defaults_to_the_standalone_layout() -> None:
    """A survey is a point in time; a scan is the survey repeated on every run.

    Two scripts were found by accident. This fails when a third grows the same default — an
    argparse default, or a bare fallback, naming `records` without `.claude`. A reader that
    lists BOTH layouts is correct and must stay green: that is how `run_validation.py` works.
    """
    offenders: list[str] = []
    files = sorted(SCRIPTS.glob("*.py"))
    assert len(files) > 0

    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith(("#", '"')):
                continue
            # Any `Path("records…)` literal, not only an argparse default. A first pass
            # matched `default=` and `or` alone, and a mutant that hid the same literal in a
            # function's parameter default sailed through — the shape is not what matters, the
            # hardcoded standalone path is.
            if not re.search(r'Path\(\s*["\']records', line):
                continue
            if ".claude" in line:
                continue
            offenders.append(f"{path.name}:{number}: {stripped[:100]}")

    assert offenders == [], (
        "These default to the standalone layout, which creates a second records in every\n"
        "plugin install (rules/records-location.md):\n\n" + "\n".join(offenders)
    )


def test_the_reader_resolves_every_layout_a_consumer_may_keep() -> None:
    """Pins the exemption by BEHAVIOUR, not by a literal in the source.

    The original form grepped `run_validation.py` for the two path expressions.
    It broke on 2026-08-29 when those literals were replaced by a table —
    `_ARTEFACT_ROOTS` — that resolves the same two layouts and a third, and it
    broke while the behaviour it exists to protect got strictly better. A test
    that fails when a refactor preserves its intent is a test that gets deleted,
    which would take the exemption with it.

    The third layout is why the table exists at all: `platform` declares
    `<project>/.claude/knowledge-base/` canonical in a rule of its own and holds
    32 plans there with none in `records/plans/`, so every `_find_plan` call site
    answered SKIP for that repository.
    """
    import run_validation as rv

    resolved = {"/".join(parts) for parts in rv._ARTEFACT_ROOTS}
    for expected in (".claude/records", "records",
                     ".claude/knowledge-base", "knowledge-base"):
        assert expected in resolved, f"{expected} is not a layout this reader resolves"


def test_the_default_is_under_the_write_root(tmp_path: Path) -> None:
    """What this actually measures. It was called `..._an_explicit_output_dir_still_wins`
    and built an `explicit = tmp_path / "elsewhere"` that it never passed to anything —
    then asserted that string was absent from the output. A value the program was never
    given cannot appear in what it prints, so the assertion carrying the test's name
    held for every possible implementation, including one that ignores `--output-dir`
    entirely. The precedence it claimed to check lives in `mini_review.main`, and the
    test below is where it is now checked."""
    root = _plugin_root(tmp_path)

    result = subprocess.run(
        [sys.executable, "-c",
         ("import sys; sys.path.insert(0, sys.argv[1]);"
         "from _layout import default_mini_reviews_dir as d;"
         "print(d(__import__('pathlib').Path(sys.argv[2])))"),
         str(SCRIPTS), str(root)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert ".squad" in result.stdout
    assert ".claude" not in result.stdout, (
        "the installed kit receives nothing this system writes")


def test_an_explicit_output_dir_still_wins(tmp_path: Path) -> None:
    """`--output-dir` is honoured, i.e. the default is NOT computed over it.

    The standalone kit passes its own path, and eight mini-review runs in this
    repository did the same. Breaking that would trade one silent wrong answer for
    another — so the override is exercised by actually passing it.
    """
    root = _plugin_root(tmp_path)
    explicit = tmp_path / "elsewhere"

    result = subprocess.run(
        [sys.executable, "-c",
         ("import sys; sys.path.insert(0, sys.argv[1]);"
          "import pathlib, argparse;"
          "from _layout import default_mini_reviews_dir as d;"
          "p = argparse.ArgumentParser();"
          "p.add_argument('--output-dir', type=pathlib.Path, default=None);"
          "p.add_argument('--project-root', type=pathlib.Path);"
          "a = p.parse_args(sys.argv[2:]);"
          "print(a.output_dir if a.output_dir is not None else d(a.project_root))"),
         str(SCRIPTS), "--project-root", str(root), "--output-dir", str(explicit)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(explicit), result.stdout


def test_the_writer_actually_writes_under_the_write_root(tmp_path: Path) -> None:
    """Runs `mini_review.py` for real.

    A first pass asserted only the RESOLVER, and a mutant that reverted the writer's wiring to the
    literal `Path("records/mini-reviews")` passed every test. The resolver being right is not
    the same as the writer using it.
    """
    root = _plugin_root(tmp_path)
    plan = root / "plan.md"
    plan.write_text("# Plan\n\n## Phase 1\n\n### T1.1 — x\n", encoding="utf-8")
    progress = root / "progress.json"
    progress.write_text('{"tasks": []}', encoding="utf-8")

    subprocess.run(
        [sys.executable, str(SCRIPTS / "mini_review.py"),
         "--slug", "fixture", "--plan", str(plan), "--progress", str(progress),
         "--phase", "1", "--project-root", str(root), "--json"],
        capture_output=True, text=True, check=False,
    )

    assert not (root / "records").exists(), (
        "the writer created a second records at the project root — the exact split "
        "rules/records-location.md forbids"
    )

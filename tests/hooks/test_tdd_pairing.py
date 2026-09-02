"""Which files the TDD gate calls untested, and why the rule had to widen.

`stop-validation` warns about production source with no test. Until 2026-09-01 it
recognised ONE shape: a test named after the file, beside it or somewhere in the
owning unit. This repository files tests by AREA — `tests/hooks/
test_reference_zone.py` covers `hooks/boundary-check.py` — so the gate reported
22 files as untested, among them nine hooks covered by 130 tests and a library
covered by 91.

A warn-first gate emitting 22 lines of noise every session is the one people stop
reading, and the hook's own comment says exactly that about a different case. The
rule now accepts three more signals, all of them evidence that a test REACHES the
file: it imports the module, it imports the package that re-exports it, or it
runs the file by path.

WHAT IS DELIBERATELY NOT A SIGNAL
----------------------------------
A test mentioning a symbol the module defines. Measured the same day: one of the
kit's own modules would be marked covered because it defines `run`, a word present
in every test that calls `subprocess.run`. That trades a visible false positive for
a silent false NEGATIVE, and for a gate the silent one is worse — nobody learns
that a file went unprotected.

This file does not name the uncovered modules in its prose, and the reason is the
subject itself: writing one of those filenames HERE would satisfy the "a test names
the file" signal and mark it covered. The documentation of a blind spot walked into
it on the first attempt.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location("_sv", REPO / "hooks" / "stop-validation.py")
_sv = importlib.util.module_from_spec(_spec)
sys.modules["_sv"] = _sv
_spec.loader.exec_module(_sv)

has_paired_test = _sv.has_paired_test
is_production_source = _sv.is_production_source


def _unit(root: Path) -> Path:
    (root / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    return root


def _src(root: Path, rel: str, body: str = "x = 1\n") -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return rel


def _test(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


# ── the signal that already worked ────────────────────────────────────────────


def test_a_mirrored_name_beside_the_file_counts(tmp_path: Path) -> None:
    _unit(tmp_path)
    src = _src(tmp_path, "pkg/thing.py")
    _test(tmp_path, "pkg/test_thing.py", "def test_x(): pass\n")

    assert has_paired_test(src, tmp_path) is True


# ── the three that were missing ───────────────────────────────────────────────


def test_a_test_that_imports_the_module_counts(tmp_path: Path) -> None:
    """The mapping need not be one file to one file for the file to be covered."""
    _unit(tmp_path)
    src = _src(tmp_path, "pkg/thing.py")
    _test(tmp_path, "tests/test_behaviour.py", "from thing import doit\n\ndef test_x(): pass\n")

    assert has_paired_test(src, tmp_path) is True


def test_a_test_that_imports_the_re_exporting_package_counts(tmp_path: Path) -> None:
    """`squad/contexts.py` is never imported by name: `squad/__init__.py` re-exports
    it and every test writes `from squad import PreToolUseContext`."""
    _unit(tmp_path)
    src = _src(tmp_path, "lib/contexts.py")
    _src(tmp_path, "lib/__init__.py", "from .contexts import Thing\n")
    _test(tmp_path, "tests/test_api.py", "from lib import Thing\n\ndef test_x(): pass\n")

    assert has_paired_test(src, tmp_path) is True


def test_a_package_that_does_not_re_export_the_module_does_not_cover_it(
        tmp_path: Path) -> None:
    """Importing the package cannot vouch for a module it never surfaces —
    otherwise one tested module would cover every untested sibling."""
    _unit(tmp_path)
    src = _src(tmp_path, "lib/hidden.py")
    _src(tmp_path, "lib/__init__.py", "from .other import Thing\n")
    _src(tmp_path, "lib/other.py")
    _test(tmp_path, "tests/test_api.py", "from lib import Thing\n\ndef test_x(): pass\n")

    assert has_paired_test(src, tmp_path) is False


def test_a_test_that_runs_the_file_by_path_counts(tmp_path: Path) -> None:
    """How every hook here is tested: a hyphenated filename cannot be imported,
    so the test invokes it as a subprocess and names it."""
    _unit(tmp_path)
    src = _src(tmp_path, "hooks/boundary-check.py")
    _test(tmp_path, "tests/hooks/test_zone.py",
          'def test_x():\n    run_hook("boundary-check", {})\n')

    assert has_paired_test(src, tmp_path) is True


# ── and the refusals that must survive ────────────────────────────────────────


def test_a_file_no_test_reaches_is_still_reported(tmp_path: Path) -> None:
    """The whole point. Widening the rule must not empty it."""
    _unit(tmp_path)
    src = _src(tmp_path, "pkg/lonely.py")
    _test(tmp_path, "tests/test_other.py", "from elsewhere import x\n\ndef test_y(): pass\n")

    assert has_paired_test(src, tmp_path) is False


def test_a_symbol_the_module_defines_is_not_a_signal(tmp_path: Path) -> None:
    """DELIBERATE. A module defining `run` would be marked covered by any test
    calling `subprocess.run` — a silent false negative, which for a gate is worse
    than the noisy false positive it replaces."""
    _unit(tmp_path)
    src = _src(tmp_path, "pkg/worker.py", "def run():\n    return 1\n")
    _test(tmp_path, "tests/test_other.py",
          "import subprocess\n\ndef test_y():\n    subprocess.run(['ls'])\n")

    assert has_paired_test(src, tmp_path) is False


def test_a_near_miss_name_does_not_count(tmp_path: Path) -> None:
    """`boundary-check-extra` must not vouch for `boundary-check`."""
    _unit(tmp_path)
    src = _src(tmp_path, "hooks/boundary-check.py")
    _test(tmp_path, "tests/test_other.py", 'def test_x():\n    run("boundary-check-extra")\n')

    assert has_paired_test(src, tmp_path) is False


def test_conftest_is_test_infrastructure_not_production_source(tmp_path: Path) -> None:
    """Grading it as production source is a category error: it exists to support
    tests, and asking it to have one of its own says nothing."""
    assert is_production_source("conftest.py") is False
    assert is_production_source("tests/conftest.py") is False


# ── the repository itself ─────────────────────────────────────────────────────


@pytest.mark.parametrize("source", [
    "hooks/boundary-check.py",
    "hooks/validate-command.py",
    "hooks/stop-validation.py",
    "squad/contexts.py",
    "squad/outputs.py",
    "mechanisms/gates/check_xrefs.py",
])
def test_files_this_repository_does_cover_are_not_reported(source: str) -> None:
    """Each of these was in the 22. Each has tests; none had a mirrored name."""
    assert has_paired_test(source, REPO) is True, source


#: Assembled from fragments ON PURPOSE. Naming these files literally would put the
#: mention INTO a test file, and "a test names the file" is one of the signals — so
#: the assertion would create the coverage it is checking for the absence of. The
#: same circularity `check_prose_tests.py` exists to catch, arriving from the other
#: side.
#: The scheduler script left this list on 2026-09-02, and it is worth recording
#: why: it was uncovered because it is JavaScript in a Python project, so it was
#: reviewed by eye and by nothing else — and both of the worst defects this kit
#: has shipped were one line of it. The third, a gate that named what may NOT
#: pass instead of what may, sent five unsigned items to PLAN before an agent
#: caught it. It now has assertions that read its executable lines.
_UNCOVERED = [
    "/".join(("mechanisms", "fleet", "session" + "_catchup.py")),
    "/".join(("skills", "plan-confidence", "scripts", "patterns" + "_match.py")),
]


@pytest.mark.parametrize("source", _UNCOVERED, ids=["catchup", "patterns"])
def test_the_files_that_genuinely_have_no_test_still_are(source: str) -> None:
    """Verified by hand on 2026-09-01: no test imports, names or runs any of these.
    They are what the gate is FOR, and pinning them keeps the widening honest — a
    rule loose enough to clear these would clear anything.

    THE KNOWN FALSE NEGATIVE, stated rather than hidden: "a test names the file" is
    a text match, so ANY test mentioning the filename marks it covered — a TODO
    list, a docstring, a parametrisation like this one. It was accepted because the
    alternative measured worse: name-mirroring alone produced 22 false positives
    here, and 22 lines of noise every session is a gate nobody reads. A gate read
    with one blind spot beats a correct gate nobody reads.
    """
    assert has_paired_test(source, REPO) is False, source

"""Layer 3 of provenance never ran in any consumer.

`rules/reference-provenance.md` names three layers and this is the only one that
catches the RESULT of a paste rather than the act. The gate lives with the KIT
and runs against the PROJECT, and those are different directories in two of the
three layouts `squad.layout` defines: a `copy` install puts the kit at
`<project>/.claude/`, a `plugin` install puts it outside the project entirely.
Only this repository, where the two coincide, ever ran it.

Reproduced on 2026-09-02 in both layouts, with a committed `study-material/ref.md`
and an untracked literal copy: the hook exited 0 with no output, while the same
gate on the same tree printed `SUSPECTED COPY … shares 5 consecutive lines` and
exited 1. "Not installed" and "ran and found nothing" both returned `None`, so
every consumer's session ended looking clean on a check that had never run.

Found by the kit's own self-audit, in the lens for absence reported as an answer,
and it survived an independent attempt to refute it in both layouts.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def hook():
    spec = importlib.util.spec_from_file_location(
        "stop_validation_leakage", _REPO / "hooks" / "stop-validation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._GATE_UNREACHABLE.clear()
    return module


def test_the_gate_is_looked_for_where_the_kit_is_not_where_the_project_is(hook) -> None:
    """The whole defect in one assertion: the argument it probes."""
    import inspect

    source = inspect.getsource(hook.check_leakage)
    assert 'kit_dir / "mechanisms"' in source, \
        "the gate is being looked for under the project again"
    assert "--repo", "and it must still be RUN against the project"


def test_a_copy_install_finds_its_gate(tmp_path: Path, hook, monkeypatch) -> None:
    """The layout every consumer has: kit at `<project>/.claude/`."""
    project = tmp_path / "consumer"
    kit = project / ".claude"
    gate = kit / "mechanisms" / "gates"
    gate.mkdir(parents=True)
    (gate / "check_reference_leakage.py").write_text(
        "import sys; print('no matches'); sys.exit(0)\n", encoding="utf-8")

    result = hook.check_leakage(project, kit)

    assert result is None, "a clean gate reports nothing"
    assert not hook._GATE_UNREACHABLE, (
        f"the gate was there and the hook did not find it: {hook._GATE_UNREACHABLE}")


def test_a_missing_gate_is_recorded_rather_than_read_as_clean(tmp_path: Path, hook) -> None:
    """The two `None`s that were indistinguishable."""
    project = tmp_path / "consumer"
    project.mkdir()

    result = hook.check_leakage(project, project / ".claude")

    assert result is None
    assert hook._GATE_UNREACHABLE, "silence again"
    assert "did not run" in hook._GATE_UNREACHABLE[0]


def test_a_real_match_is_still_reported(tmp_path: Path, hook) -> None:
    """The narrowing must not cost the finding it exists to deliver."""
    project = tmp_path / "consumer"
    kit = project / ".claude"
    gate = kit / "mechanisms" / "gates"
    gate.mkdir(parents=True)
    (gate / "check_reference_leakage.py").write_text(
        "import sys\n"
        "print('SUSPECTED COPY reference-leakage: 1 match(es)')\n"
        "print('  copied.md:1 shares 5 consecutive lines with study-material/ref.md:1')\n"
        "sys.exit(1)\n", encoding="utf-8")

    result = hook.check_leakage(project, kit)

    assert result and "Suspected literal copy" in result
    assert "shares 5 consecutive lines" in result
    assert not hook._GATE_UNREACHABLE


def test_the_hook_says_a_gate_that_did_not_run_is_not_a_pass() -> None:
    """The idiom this function was missing while using it twice elsewhere."""
    source = (_REPO / "hooks" / "stop-validation.py").read_text(encoding="utf-8")

    assert "A STOP GATE DID NOT RUN" in source
    assert "not running is not passing" in source

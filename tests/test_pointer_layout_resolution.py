"""A pointer written in a consumer resolves against the wrong root.

`_resolve_code_pointer` joins the pointer to the project root. In the kit's
standalone repository `rules/` and `skills/` sit at that root and resolve. In a
plugin install they sit under `.claude/`, so every pointer to a kit file comes
back `missing_file` and `check_evidence_pointers` raises `fabricated_evidence`
over paths that exist.

Measured in `platform` on 2026-08-29: the kit's own `good-opportunity.md`
fixture scored `evidence_pointers 0.0`, hard-capped to 49, verdict INVALID —
four pointers, four "missing", all four present on disk one directory down.

The fixture is the visible casualty. The defect is wider: any opportunity a
consumer writes that cites a kit rule or script is called a fabrication.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/discover-confidence/scripts"
sys.path.insert(0, str(SCRIPTS))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_evidence_pointers import _resolve_code_pointer  # noqa: E402 (post-bootstrap)


def test_a_pointer_resolves_in_the_plugin_layout(tmp_path: Path) -> None:
    """`rules/x.md` in a consumer means `.claude/rules/x.md`."""
    root = tmp_path / "consumer"
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "rules" / "cycle-discover.md").write_text(
        "\n".join(f"line {i}" for i in range(1, 60)), encoding="utf-8")

    ok, why = _resolve_code_pointer(root, "rules/cycle-discover.md", 20)
    assert ok, why


def test_a_pointer_still_resolves_in_the_standalone_layout(tmp_path: Path) -> None:
    """The kit's own repository must keep working exactly as before."""
    root = tmp_path / "kit"
    (root / "rules").mkdir(parents=True)
    (root / "rules" / "cycle-discover.md").write_text(
        "\n".join(f"line {i}" for i in range(1, 60)), encoding="utf-8")

    ok, why = _resolve_code_pointer(root, "rules/cycle-discover.md", 20)
    assert ok, why


def test_a_genuinely_absent_pointer_is_still_a_fabrication(tmp_path: Path) -> None:
    """Widening the search must not turn the detector off.

    This is the whole reason the gate exists — a citation to a file nobody wrote.
    """
    root = tmp_path / "consumer"
    (root / ".claude").mkdir(parents=True)
    ok, why = _resolve_code_pointer(root, "rules/invented.md", 3)
    assert not ok and why == "missing_file"


def test_the_line_number_is_still_checked_after_the_fallback(tmp_path: Path) -> None:
    """A file found under `.claude/` must be range-checked like any other."""
    root = tmp_path / "consumer"
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "rules" / "short.md").write_text("one\ntwo\n", encoding="utf-8")

    ok, why = _resolve_code_pointer(root, "rules/short.md", 900)
    assert not ok and "line_out_of_range" in why


def test_a_measurement_target_resolves_in_the_plugin_layout(tmp_path: Path) -> None:
    """The same defect, in the sibling checker — and it already knew the answer.

    `check_measurement_targets.py` resolves `live-target.txt` by trying the root
    and then `.claude/` (lines 97-98). Twenty lines later it checks a measurement
    target with a bare `(project_root / target).exists()` and no fallback, so a
    plan citing a kit path is called unresolvable in every plugin install.

    The fix was already written in the same file. It had not been applied to the
    second site — the shape this kit keeps measuring: a rule stated once and
    implemented on one of two paths.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                           / "skills/discover-plan-confidence/scripts"))
    from check_measurement_targets import _target_exists

    root = tmp_path / "consumer"
    (root / ".claude" / "skills" / "x").mkdir(parents=True)
    (root / ".claude" / "skills" / "x" / "run.py").write_text("pass\n", encoding="utf-8")

    assert _target_exists(root, "skills/x/run.py")
    assert not _target_exists(root, "skills/x/invented.py")

"""A check that could not look at its subject must not be drawn as a tick.

`verify_ecosystem` runs eighteen checks by delegating to gate scripts, and eight of
them return PASS when the script they delegate to is absent. Skipping is deliberate —
a consumer with a partial install must not fail over a gate it never installed — but
the mark printed for it was the same `✓` a real pass gets, with the reason on the
line below:

    ✓ Cross-references
      check_xrefs.py not installed — skipping

Measured on 2026-09-05 by hiding `mechanisms/gates/check_xrefs.py` and running the
verifier: that is the exact output. Nothing broken shipped — "Mechanisms inventory"
failed on the missing file and the run exited 1 — so this is about what the reader is
told, not about a hole in the gate. It is still the principle this repository states
elsewhere and enforces in `test_gates_say_what_they_examined.py`: a gate does not
report a result it did not observe.

The distinction has to survive in the RETURN VALUE and not only in the printed line,
because a caller reading `ok` cannot see prose.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"
    spec = importlib.util.spec_from_file_location("_ve", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_ve"] = mod
    spec.loader.exec_module(mod)
    return mod


#: Each check that delegates, and the gate script it needs on disk.
DELEGATING = [
    ("check_xrefs", "check_xrefs.py"),
    ("check_skill_map", "check_skill_map.py"),
    ("check_readme_advisory_skills", "check_readme_advisory_skills.py"),
    ("check_squad_map", "check_squad_map.py"),
    ("check_mechanisms_inventory", "check_mechanisms_inventory.py"),
    ("check_phase_numbering", "check_phase_numbering.py"),
    ("check_wiki_migration", "check_wiki_migration.py"),
]


@pytest.mark.parametrize("func_name,script", DELEGATING)
def test_an_absent_gate_is_not_run_rather_than_passed(
    func_name: str, script: str, tmp_path: Path
) -> None:
    """An empty tree has none of these scripts, so every one takes its skip branch."""
    mod = _module()
    func = getattr(mod, func_name)
    ok, issues = func(tmp_path)
    assert ok is mod.NOT_RUN, (
        f"{func_name} returned {ok!r} for an absent {script}. A caller reading this "
        f"cannot tell a real pass from a check that never looked."
    )
    assert any("skipping" in note for note in issues), (
        "the reason has to travel with the verdict, not only with the mark"
    )


def test_not_run_is_not_a_failure() -> None:
    """The skip exists so a partial consumer install does not fail. Keep that.

    `NOT_RUN` must stay truthy: every existing caller writes `if ok:` and a sentinel
    that flipped to falsy would turn every partial install red — trading a misleading
    tick for a broken one, which is worse.
    """
    mod = _module()
    assert bool(mod.NOT_RUN) is True
    assert mod.NOT_RUN is not True, "it has to be distinguishable from a real pass"


def test_a_real_pass_is_still_plain_true() -> None:
    """The sentinel must not leak into checks that actually ran."""
    mod = _module()
    ok, _ = mod.check_python_syntax(ROOT)
    assert ok is True, "a check that examined its subject returns True, not the sentinel"


def test_the_runner_draws_a_different_mark_for_what_it_did_not_run(
    tmp_path: Path,
) -> None:
    """The mark is what a reader scans; it is the half that has to change.

    Invoked the way the gate actually runs — as a subprocess — against an empty
    directory, where every delegating check takes its skip branch. Asserting on the
    printed output rather than on an internal, because the printed output IS the
    deliverable here.
    """
    import subprocess

    script = ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(script), "--ecosystem-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=180,
    )
    out = result.stdout
    lines = out.splitlines()
    skips = [i for i, ln in enumerate(lines) if "not installed" in ln]
    assert skips, f"the empty tree should have produced skips. Output:\n{out}"
    for i in skips:
        mark = lines[i - 1]
        assert not mark.startswith("✓"), (
            f"{mark!r} is drawn as a pass, and the line under it says the gate was "
            f"never installed. A reader scanning marks is told this was checked."
        )
    assert "not run" in out.lower(), "the summary has to count what it could not check"


def test_the_verifier_examines_the_tree_it_was_pointed_at(tmp_path: Path) -> None:
    """`--ecosystem-dir` was accepted and read by nothing until 2026-09-05.

    `main()` took no arguments, so the flag fell on the floor and the verifier ran
    against whatever `_find_ecosystem_dir()` located — printing a full green report
    headed with THAT tree's path. Found by pointing it at an empty directory to test
    the skip marks above and getting sixteen ticks for the kit itself.

    The header is asserted because it is the only place the subject is named, and a
    report whose header names one tree and whose findings come from another is the
    worst of the failure modes this file is about.
    """
    import subprocess

    script = ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(script), "--ecosystem-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT),
    )
    assert str(tmp_path) in result.stdout, (
        f"pointed at {tmp_path} and reported on something else:\n{result.stdout[:400]}"
    )
    assert str(ROOT) not in result.stdout.splitlines()[0], (
        "the header names the kit, not the directory the caller asked about"
    )


def test_an_argument_it_does_not_understand_is_an_error(tmp_path: Path) -> None:
    """Silently ignoring a flag is how the one above went unnoticed for so long."""
    import subprocess

    script = ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(script), "--not-a-real-flag"],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT),
    )
    assert result.returncode == 2, (
        f"exited {result.returncode}; an unrecognised argument must not be swallowed"
    )
    assert "unrecognised" in result.stderr.lower()

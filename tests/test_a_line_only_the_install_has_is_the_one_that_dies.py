"""`install_ahead: 3` printed beside `kit_ahead: 38`, and only one of them is a deadline.

`check_install_drift` reports four classes in one voice — `<class>: <count>` and a file
list each — and the summary line gives `DIVERGED` its consequence (*"a copy in either
direction deletes the other's fix"*) while `INSTALL_AHEAD` gets only the fact: *"the install
holds lines the kit does not"*.

True, and it omits the part that matters. `install.sh --force` snapshots `.claude/` into
`.install-backups/` and replaces it, so a line the install has and the kit does not is
**erased by the next upgrade**. It is the only one of the four classes where that is so:
`KIT_AHEAD` is pure gain, `IDENTICAL` is nothing, and `DIVERGED` at least survives on both
sides until somebody chooses.

Measured 2026-09-22 on a real consumer: `install_ahead: 3` — three hooks, carrying the
wiring for a 94-line module that does not exist in the kit at all (#164). The number was
printed on every run of this gate, read twice that day by the session that maintains the
kit, and nobody opened the files. A count in the same voice as a count that loses nothing
is a count that reads as inventory.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
GATE = _ROOT / "mechanisms" / "gates" / "check_install_drift.py"


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _trees(tmp_path: Path, *, install_ahead: bool = True,
           kit_ahead: bool = True) -> tuple[Path, Path]:
    install, kit = tmp_path / "install", tmp_path / "kit"
    _write(install / "same.py", "a\n")
    _write(kit / "same.py", "a\n")
    if install_ahead:
        _write(install / "ahead.py", "a\nonly_install = True\n")
        _write(kit / "ahead.py", "a\n")
    if kit_ahead:
        _write(install / "behind.py", "a\n")
        _write(kit / "behind.py", "a\nonly_kit = True\n")
    return install, kit


def _run(install: Path, kit: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), "--install", str(install), "--kit", str(kit)],
        capture_output=True, text=True, check=False)


def test_the_class_that_dies_says_it_dies(tmp_path: Path) -> None:
    out = _run(*_trees(tmp_path))
    both = out.stdout + out.stderr

    assert "erased by the next install" in both, both


def test_the_class_that_loses_nothing_does_not_claim_a_deadline(tmp_path: Path) -> None:
    """THE CONTROL. A warning on every class is a warning on none."""
    out = _run(*_trees(tmp_path, install_ahead=False))
    both = out.stdout + out.stderr

    assert "kit_ahead" in both, both
    assert "erased by the next install" not in both


def test_the_two_counts_are_not_printed_in_the_same_voice(tmp_path: Path) -> None:
    """`install_ahead: 3` beside `kit_ahead: 38` reads as two sizes of one thing."""
    out = _run(*_trees(tmp_path))
    lines = out.stdout.splitlines()

    ahead = next(row for row in lines if row.startswith("install_ahead:"))
    behind = next(row for row in lines if row.startswith("kit_ahead:"))

    assert ahead != behind.replace("kit_ahead", "install_ahead"), (
        "the two headings differ only by the class name, so a reader compares magnitudes"
    )


def test_the_summary_names_the_consequence_and_not_only_the_fact(tmp_path: Path) -> None:
    out = _run(*_trees(tmp_path))

    assert "the install holds lines the kit does not" in out.stderr, out.stderr
    assert "erased" in out.stderr, (
        "DIVERGED's summary already names what it costs; this one named only what it is"
    )


def test_a_clean_tree_still_says_nothing(tmp_path: Path) -> None:
    """The other control: no drift, no deadline, exit 0."""
    out = _run(*_trees(tmp_path, install_ahead=False, kit_ahead=False))

    assert out.returncode == 0
    assert "erased" not in out.stdout + out.stderr

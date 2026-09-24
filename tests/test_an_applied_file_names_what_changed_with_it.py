"""A file applied alone must say which files changed with it and still lag here.

`--apply-upstream` takes ONE file, and a fix is rarely one file. Reported by a
consumer on 2026-09-24 applying the panel-family fix: `convene_panel.py` arrived,
the installer printed `APPLIED`, the panel kept convening, and the first seat that
reached a plugin raised `AttributeError: 'Plugin' object has no attribute
'agent_model'` — the companion lives in `installed_plugins.py`. A second companion,
`review_panel.py`, was missing too and did NOT raise: it returned `unknown` for a
model it now recognises, which is the fail-safe answer and therefore the silent one.

So the two failure modes of a partial apply are a crash and a wrong answer, and the
wrong answer is the one nobody reports.

The kit's own history answers the question: the commit that last touched the applied
file names the files that moved with it. Anything in that set still differing here is
named. That over-reports when a commit carried unrelated work — the honest direction,
since the alternative under-reports a real break.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = _ROOT / "mechanisms" / "distribution" / "install.sh"

REL = "mechanisms/cycle/thing.py"
MATE = "mechanisms/conventions/mate.py"


def _kit(tmp_path: Path) -> Path:
    kit = tmp_path / "kitrepo"
    for d in ("mechanisms/cycle", "mechanisms/conventions", "skills", "rules", "hooks"):
        (kit / d).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(kit)], check=True)
    run = lambda *a: subprocess.run(["git", "-C", str(kit), *a], check=True,
                                    capture_output=True, text=True)
    run("config", "user.email", "t@t"); run("config", "user.name", "t")
    (kit / REL).write_text("alpha\n", encoding="utf-8")
    (kit / MATE).write_text("def helper():\n    return 1\n", encoding="utf-8")
    run("add", "-A"); run("commit", "-qm", "v1")
    # One commit, two files: the shape of nearly every real fix.
    (kit / REL).write_text("alpha\nbeta\n", encoding="utf-8")
    (kit / MATE).write_text("def helper():\n    return 1\n\n\ndef added():\n    return 2\n",
                            encoding="utf-8")
    run("add", "-A"); run("commit", "-qm", "v2 touches both")
    return kit


def _consumer(tmp_path: Path, kit: Path, *, mate_current: bool) -> Path:
    """An install stuck on v1 of the applied file; its companion may or may not lag."""
    consumer = tmp_path / "consumer"
    for d in ("mechanisms/cycle", "mechanisms/conventions", "skills", "rules", "hooks"):
        (consumer / ".claude" / d).mkdir(parents=True, exist_ok=True)
    (consumer / ".claude" / REL).write_text("alpha\n", encoding="utf-8")
    (consumer / ".claude" / MATE).write_text(
        (kit / MATE).read_text(encoding="utf-8") if mate_current
        else "def helper():\n    return 1\n", encoding="utf-8")
    return consumer


def _apply(consumer: Path, kit: Path, rel: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(INSTALLER), str(consumer), "--apply-upstream", rel,
         "--from", str(kit)],
        capture_output=True, text=True, check=False)


def test_a_lagging_companion_is_named(tmp_path: Path) -> None:
    kit = _kit(tmp_path)
    consumer = _consumer(tmp_path, kit, mate_current=False)
    proc = _apply(consumer, kit, REL)
    out = proc.stdout + proc.stderr
    assert "APPLIED" in out, out
    assert MATE in out, f"the companion that still lags was not named:\n{out}"


def test_a_companion_already_current_is_not_named(tmp_path: Path) -> None:
    """Naming a file that needs nothing trains the reader to skip the line."""
    kit = _kit(tmp_path)
    consumer = _consumer(tmp_path, kit, mate_current=True)
    proc = _apply(consumer, kit, REL)
    out = proc.stdout + proc.stderr
    assert "APPLIED" in out, out
    assert MATE not in out, f"a current companion was reported as lagging:\n{out}"


def test_a_kit_without_history_says_it_could_not_check(tmp_path: Path) -> None:
    """Silence would read as 'no companions'. It means 'nobody asked'."""
    kit = tmp_path / "plainkit"
    for d in ("mechanisms/cycle", "skills", "rules", "hooks"):
        (kit / d).mkdir(parents=True, exist_ok=True)
    (kit / REL).write_text("alpha\nbeta\n", encoding="utf-8")
    consumer = tmp_path / "consumer"
    for d in ("mechanisms/cycle", "skills", "rules", "hooks"):
        (consumer / ".claude" / d).mkdir(parents=True, exist_ok=True)
    (consumer / ".claude" / REL).write_text("alpha\n", encoding="utf-8")
    proc = _apply(consumer, kit, REL)
    out = proc.stdout + proc.stderr
    assert "APPLIED" in out, out
    assert "companion" in out.lower(), f"no statement about companions at all:\n{out}"

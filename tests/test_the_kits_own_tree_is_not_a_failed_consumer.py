"""`check_chain_preconditions` refused the kit's own checkout, permanently.

Two of its preconditions are the CONSUMER's to satisfy, and the kit ships both
deliberately unmet:

  * `BACKLOG.md` is never versioned — it is the maintainer's own register, not the
    product's.
  * `rules/domain-routing.txt` ships with no rows, because the table describes
    repositories the kit does not have.

So the gate reported `REFUSED: 2 precondition(s) fail` on every run against the tree
it lives in, for the state that tree is supposed to be in. A gate that always refuses
carries no information, and the refusal it prints is indistinguishable from a
consumer's real misconfiguration.

Exit 2 — could not measure — rather than 0: not measuring is not passing, and that
distinction is the one this whole kit is organised around.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_GATE = _ROOT / "mechanisms" / "gates" / "check_chain_preconditions.py"


def _run(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_GATE)], cwd=cwd,
                          capture_output=True, text=True, timeout=180, check=False)


def test_the_kits_own_tree_is_not_reported_as_refused() -> None:
    done = _run(_ROOT)

    assert "REFUSED" not in done.stdout, done.stdout
    assert done.returncode == 2, (
        f"expected 2 (could not measure), got {done.returncode}:\n{done.stdout}")


def test_the_two_consumer_preconditions_say_they_are_not_measurable_here() -> None:
    out = _run(_ROOT).stdout

    for name in ("backlog", "domain routing"):
        line = next(ln for ln in out.splitlines() if f" {name}:" in ln)
        assert "[  ? ]" in line, f"{name} is graded rather than declared unmeasurable: {line}"
        assert "this is the kit" in line, line


def test_a_consumer_missing_both_is_still_refused(tmp_path: Path) -> None:
    """The gate's whole subject: a project that cannot reach RELEASE hears so first."""
    for tree in ("skills", "rules", "mechanisms/gates"):
        (tmp_path / tree).mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "domain-routing.txt").write_text("# no rows\n", encoding="utf-8")

    done = _run(tmp_path)

    assert "REFUSED" in done.stdout, done.stdout
    assert done.returncode == 1, done.stdout


def test_the_manifest_is_what_tells_the_two_apart(tmp_path: Path) -> None:
    """A consumer that happens to have `skills/` must not read as the kit."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("chain_preconditions", _GATE)
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE execution: `@dataclass` resolves annotations through
    # `sys.modules[cls.__module__]`, and a module absent from it raises there.
    sys.modules["chain_preconditions"] = module
    spec.loader.exec_module(module)

    for tree in ("skills", "mechanisms/gates"):
        (tmp_path / tree).mkdir(parents=True, exist_ok=True)

    assert not module.is_the_kit_itself(tmp_path), "no manifest, so not the kit"
    assert module.is_the_kit_itself(_ROOT)

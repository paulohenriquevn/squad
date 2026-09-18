"""`mechanisms/gates/_contract.py` declares one spelling. This holds it.

Before the contract there were EIGHT spellings of "the tree to sweep" across 33
gates, and seven gates with none. The cost was not the typing: it was that three
separate callers each had to carry the whole name-to-flag table — the adapters in
`verify_ecosystem.py`, the 22-entry `ROOT_FLAG` map in
`test_gates_say_what_they_examined.py`, and `run_checks.py`, which gave up on
globbing the directory and parsed the CI workflow instead. That map's own comment
records a gate sitting outside the empty-sweep protection for a week because it
spelled its flag `--ecosystem-dir`.

A new gate spelling it some ninth way costs nothing at the moment it is written
and re-creates all of that. So the check lives where it can fire: inside
`check_gate_mechanisms`, the gate that already audits the gates.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "mechanisms" / "gates" / "check_gate_mechanisms.py"


def _report(root: Path):
    sys.path.insert(0, str(REPO / "mechanisms" / "gates"))
    try:
        from check_gate_mechanisms import check_gate_mechanisms
    finally:
        sys.path.pop(0)
    return check_gate_mechanisms(root)


def test_every_gate_in_this_repository_accepts_root() -> None:
    """The contract, stated over the real directory."""
    missing = _report(REPO).gates_without_root_flag

    assert missing == [], (
        "these gates do not declare `--root`: " + ", ".join(missing) + ". "
        "Add it via `_contract.add_root(parser, aliases=(\"--old-name\",))` — the "
        "old spelling survives as an alias, so no caller breaks.")


def test_a_gate_without_root_is_named_not_passed_over(tmp_path: Path) -> None:
    """A gate off the contract is reported. Otherwise the check is decoration."""
    gates = tmp_path / "mechanisms" / "gates"
    gates.mkdir(parents=True)
    (gates / "check_obedient.py").write_text(
        'p.add_argument("--root")\n', encoding="utf-8")
    (gates / "check_wayward.py").write_text(
        'p.add_argument("--ecosystem-dir")\n', encoding="utf-8")

    missing = _report(tmp_path).gates_without_root_flag

    assert missing == ["check_wayward.py"], (
        f"expected the wayward gate alone, got {missing}")


def test_the_run_says_which_way_it_went() -> None:
    """Silence on a clean contract reads the same as never having checked."""
    done = subprocess.run([sys.executable, str(GATE), "--root", str(REPO)],
                          capture_output=True, text=True, timeout=300, check=False)

    assert "`--root`" in done.stdout, (
        "the run never mentioned the contract either way:\n" + done.stdout)


@pytest.mark.parametrize("flag", ["--root", "--repo"])
def test_the_enforcer_itself_answers_to_both_names(flag: str) -> None:
    """It kept `--repo`; the alias is how the contract arrives without a flag day."""
    done = subprocess.run([sys.executable, str(GATE), flag, str(REPO), "--help"],
                          capture_output=True, text=True, timeout=120, check=False)

    assert done.returncode == 0, done.stdout + done.stderr

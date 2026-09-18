"""Every mechanism that reads the panel roster finds it in the same place.

`convene_panel.default_panel_path()` was fixed on the day this was measured, and
its docstring states the defect in full:

    `install.sh` copies `rules/` into `<target>/.claude/`, so in a plugin install
    the roster is at `<project>/.claude/rules/review-panel.txt` and
    `<project>/rules/review-panel.txt` does not exist. Every consumer install
    therefore convened against a roster that was not there.

`check_panel_approval.py` carries a function of the SAME NAME that never got it:

    def default_panel_path() -> Path:
        return repo_root() / "rules" / "review-panel.txt"

Measured by a consumer session 2026-09-18, on a panel that had convened and
voted, with three seats and a unanimous verdict on disk:

    UNCHECKED: cannot read the roster: .../apps/theoclaw/rules/review-panel.txt

`UNCHECKED` reaches the opportunity scorer as `ITEM_IN_FLIGHT` — "the panel could
not convene". It HAD convened. So on every plugin install a panel that ran and
returned is indistinguishable from one that never ran, which is the failure this
kit names most: a checker that could not measure its subject reporting something
other than what is true.

Two functions with one name, one of them fixed, is the shape the kit has paid for
repeatedly — `squad/plan.py`, `_credential_globs`, `_is_auto_generated`. The
resolution lives in one place now, and this test is written against that owner so
a third reader inherits it instead of re-deriving it.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "mechanisms" / "cycle"))
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

from squad.layout import roster_path  # noqa: E402


def _plugin_install(tmp_path: Path) -> Path:
    """A consumer with the kit installed under `.claude/`, as `install.sh` writes it."""
    project = tmp_path / "consumer"
    eco = project / ".claude"
    for d in ("rules", "skills", "hooks", "mechanisms", "agents"):
        (eco / d).mkdir(parents=True, exist_ok=True)
    (eco / "rules" / "review-panel.txt").write_text(
        "reviewer = discover | vera | sonnet | builtin\n", encoding="utf-8")
    return project


def test_the_roster_is_found_in_a_plugin_install(tmp_path: Path) -> None:
    project = _plugin_install(tmp_path)
    found = roster_path(project)
    assert found is not None
    assert found.is_file(), f"{found} — the roster is on disk and the resolver missed it"
    assert found == project / ".claude" / "rules" / "review-panel.txt"


def test_a_standalone_checkout_still_resolves(tmp_path: Path) -> None:
    """The shape where kit and project coincide, which is how the kit tests itself."""
    project = tmp_path / "kit"
    for d in ("rules", "skills", "hooks", "mechanisms", "agents"):
        (project / d).mkdir(parents=True, exist_ok=True)
    (project / "rules" / "review-panel.txt").write_text("# roster\n", encoding="utf-8")
    assert roster_path(project) == project / "rules" / "review-panel.txt"


def test_both_mechanisms_ask_the_owner_rather_than_carrying_a_copy() -> None:
    """The half that escaped did so because each file answered for itself.

    Asserted on the source, not on behaviour: a second implementation that happens
    to be correct today is the one that drifts tomorrow, and drift is the finding
    this test exists for.
    """
    for rel in ("mechanisms/cycle/convene_panel.py",
                "mechanisms/gates/check_panel_approval.py"):
        text = (_REPO / rel).read_text(encoding="utf-8")
        assert "roster_path" in text, f"{rel} does not ask who owns the answer"
        assert 'repo_root() / "rules" / "review-panel.txt"' not in text, (
            f"{rel} resolves the roster against the PROJECT, which is where it is "
            f"not in a plugin install")


def test_the_approval_gate_reads_a_roster_it_can_reach(tmp_path: Path) -> None:
    """End to end: the gate no longer answers UNCHECKED over a roster that is there."""
    from check_panel_approval import default_panel_path  # noqa: PLC0415

    project = _plugin_install(tmp_path)
    found = default_panel_path(project)
    assert found.is_file(), (
        f"{found} — the gate would report UNCHECKED, which the scorer reads as "
        f"ITEM_IN_FLIGHT, over a panel that convened")

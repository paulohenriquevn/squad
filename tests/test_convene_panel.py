"""Who must judge this document, and what happens when nobody can.

`review_panel.py` tallies a record. Until `convene_panel.py` existed nothing produced
one, so `rules/cycle-discover.md` stated that the phase advanced on 2 of 3 signed
approvals while every DISCOVER and PLAN advanced without a panel (issue #65). These
tests hold the deterministic half of the fix: WHO is assigned, and the refusals that
keep an assignment from being a formality.

The distinction under most of them is the one this mechanism exists to preserve: a
seat nobody can fill is an ABSENT reviewer, not a rejected document, and the two take
opposite actions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "cycle"))

from convene_panel import INVALID, OK, UNFILLABLE, UNREADABLE, convene, main

ROSTER = """
reviewer = discover | nemesis | claude-opus-5   | builtin
reviewer = discover | leo     | claude-sonnet-5 | builtin
reviewer = discover | judge   | gpt-5-codex     | codex
panel_phases = discover
"""


def _roster(tmp_path: Path, body: str = ROSTER) -> Path:
    p = tmp_path / "review-panel.txt"
    p.write_text(body, encoding="utf-8")
    return p


def _project(tmp_path: Path, *agents: str) -> Path:
    root = tmp_path / "proj"
    (root / "agents").mkdir(parents=True, exist_ok=True)
    for a in agents:
        (root / "agents" / f"{a}.md").write_text(f"---\nname: {a}\n---\n", encoding="utf-8")
    return root


def _which(*names: str):
    return lambda cmd: f"/usr/bin/{cmd}" if cmd in names else None


def _plugins(tmp_path: Path, **supplied: tuple[str, ...]) -> Path:
    """A fake Claude Code manifest holding exactly these plugins and their agents."""
    cfg = tmp_path / "claude"
    (cfg / "plugins").mkdir(parents=True, exist_ok=True)
    entries = {}
    for name, agents in supplied.items():
        name = name.replace("_", "-")
        tree = tmp_path / "installed" / name
        (tree / "agents").mkdir(parents=True, exist_ok=True)
        for a in agents:
            (tree / "agents" / f"{a}.md").write_text(f"---\nname: {a}\n---\n",
                                                     encoding="utf-8")
        entries[f"{name}@m"] = [{"installPath": str(tree), "version": "1.0.0"}]
    (cfg / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": entries}), encoding="utf-8")
    return cfg


def _convene(tmp_path, *, author="", body=ROSTER, agents=("nemesis", "leo"),
             on_path=("codex",), phase="discover", plugins=None):
    return convene("B-014", phase, author,
                   panel_path=_roster(tmp_path, body),
                   project=_project(tmp_path, *agents),
                   which=_which(*on_path),
                   config_dir=_plugins(tmp_path, **(plugins or {})))


def test_a_complete_roster_assigns_every_seat(tmp_path: Path) -> None:
    code, result = _convene(tmp_path)

    assert code == OK
    assert result["assigned"] == ["nemesis", "leo", "judge"]
    assert result["families"] == ["anthropic", "openai"]


def test_the_author_may_not_hold_a_seat(tmp_path: Path) -> None:
    """An author approving their own work is not a review."""
    code, result = _convene(tmp_path, author="nemesis")

    assert code == INVALID
    assert "author" in result["detail"]


def test_an_author_who_is_not_on_the_panel_is_fine(tmp_path: Path) -> None:
    """The refusal must be about THIS panel, not about being an author at all."""
    code, _ = _convene(tmp_path, author="daedalus-tech-lead")

    assert code == OK


def test_a_missing_agent_is_unfillable_not_a_rejection(tmp_path: Path) -> None:
    """The distinction the whole mechanism turns on.

    A reviewer this project does not have has not judged the document badly — it has
    not judged it at all. Reporting a rejection would send an author to rewrite
    something nobody found fault with; the correct action is an `access` impediment.
    """
    code, result = _convene(tmp_path, agents=("nemesis",))

    assert code == UNFILLABLE
    assert [u["agent"] for u in result["unfilled"]] == ["leo"]
    assert "access" in result["detail"]


def test_an_absent_binary_is_unfillable_too(tmp_path: Path) -> None:
    code, result = _convene(tmp_path, on_path=())

    assert code == UNFILLABLE
    assert result["unfilled"][0]["agent"] == "judge"


PLUGIN_ROSTER = """
reviewer = discover | nemesis           | claude-opus-5   | builtin
reviewer = discover | leo               | claude-sonnet-5 | builtin
reviewer = discover | judge-codex:judge | gpt-5-codex     | builtin
panel_phases = discover
"""


def test_an_installed_plugin_agent_fills_its_seat(tmp_path: Path) -> None:
    """`plugin:agent` is supplied by a plugin, not by this tree — and it is verified
    there, from Claude Code's own manifest."""
    code, _ = _convene(tmp_path, body=PLUGIN_ROSTER, on_path=(),
                       plugins={"judge-codex": ("judge",)})

    assert code == OK


def test_a_seat_naming_an_uninstalled_plugin_is_unfillable(tmp_path: Path) -> None:
    """This seat was accepted WITHOUT verification until 2026-09-09, on the strength of
    its name — in a mechanism that refuses exactly that everywhere else."""
    code, result = _convene(tmp_path, body=PLUGIN_ROSTER, on_path=(), plugins={})

    assert code == UNFILLABLE
    assert "not installed" in result["unfilled"][0]["reason"]


def test_an_installed_plugin_that_lacks_the_agent_is_unfillable(tmp_path: Path) -> None:
    """Installed is not the same as supplies-this-agent, and a typo in the roster must
    not seat somebody who does not exist."""
    code, result = _convene(tmp_path, body=PLUGIN_ROSTER, on_path=(),
                            plugins={"judge-codex": ("some-other-judge",)})

    assert code == UNFILLABLE
    assert "supplies no agent" in result["unfilled"][0]["reason"]


def test_a_short_panel_is_refused(tmp_path: Path) -> None:
    """2 of 3 is a majority of a FULL panel; a short roster cannot reach it."""
    body = """
reviewer = discover | nemesis | claude-opus-5 | builtin
reviewer = discover | judge   | gpt-5-codex   | codex
panel_phases = discover
"""
    code, result = _convene(tmp_path, body=body)

    assert code == INVALID
    assert "seats" in result["detail"]


def test_one_family_is_refused(tmp_path: Path) -> None:
    """Three Claudes asked three times are three correlated opinions."""
    body = """
reviewer = discover | nemesis | claude-opus-5    | builtin
reviewer = discover | leo     | claude-sonnet-5  | builtin
reviewer = discover | vera    | claude-haiku-4-5 | builtin
panel_phases = discover
"""
    code, result = _convene(tmp_path, body=body, agents=("nemesis", "leo", "vera"))

    assert code == INVALID
    assert "share failure modes" in result["detail"]


def test_an_unrecognised_model_supplies_no_diversity(tmp_path: Path) -> None:
    """Otherwise `--model anything` would prove orthogonality by typing."""
    body = """
reviewer = discover | nemesis | claude-opus-5   | builtin
reviewer = discover | leo     | claude-sonnet-5 | builtin
reviewer = discover | vera    | some-model      | builtin
panel_phases = discover
"""
    code, _ = _convene(tmp_path, body=body, agents=("nemesis", "leo", "vera"))

    assert code == INVALID


def test_an_ungated_phase_convenes_nothing_and_does_not_fail(tmp_path: Path) -> None:
    """CODE-QUALITY and RELEASE derive their verdict from a script; a panel voting
    on a decision already made deterministically adds cost and no information."""
    code, result = _convene(tmp_path, phase="release")

    assert code == OK
    assert result["status"] == "not_gated"


def test_an_unparseable_roster_is_not_a_pass(tmp_path: Path) -> None:
    body = "reviewer = discover | nemesis\npanel_phases = discover\n"
    code, result = _convene(tmp_path, body=body)

    assert code == UNREADABLE
    assert result["status"] == "unreadable"


def test_write_persists_the_list_the_record_is_checked_against(tmp_path: Path) -> None:
    """The assignment is written because the votes must be verifiable against it.

    Every seat here is `builtin` on purpose: `main` resolves PATH for real, so a
    roster naming an executable would make this test pass or fail on whether the
    machine happens to have it — and a test whose result depends on the machine is a
    bug, not a measurement.
    """
    body = """
reviewer = discover | nemesis           | claude-opus-5   | builtin
reviewer = discover | leo               | claude-sonnet-5 | builtin
reviewer = discover | judge-codex:judge | gpt-5-codex     | builtin
panel_phases = discover
"""
    project = _project(tmp_path, "nemesis", "leo")
    code = main(["--slug", "B-014", "--phase", "discover",
                 "--panel", str(_roster(tmp_path, body)), "--project", str(project),
                 "--config-dir", str(_plugins(tmp_path, **{"judge-codex": ("judge",)})),
                 "--write", "--json"])

    assert code == OK
    written = (project / ".squad" / "records" / "panels"
               / "B-014-discover.assignment.json")
    assert json.loads(written.read_text())["assigned"] == [
        "nemesis", "leo", "judge-codex:judge"]

"""Can a valid panel be formed at all? Asked at intake, not per item.

`rules/review-panel.txt` declares who sits on the panel. This gate asks whether that
declaration can actually produce one: three seats per gated phase, at least one from a
recognised family outside the kit's own, and every seat reachable — a `builtin` seat
naming an agent this project has, anything else on PATH.

The failure it prevents is the one `check_merge_autonomy.py` prevents at the other end
of the chain: every item measured, planned, and then stopped at a panel that was never
formable. Discovering that per item costs the run.

Four states, and the last two are the ones that matter:

    HOLDS        a panel can be formed
    VIOLATED     it cannot, on any machine — the repository's defect
    UNCHECKED    the declaration could not be read, which is NOT a pass
    UNREACHABLE  the declaration is fine and this project cannot supply a reviewer
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "gates"))

from check_panel_capability import PanelCapability, check_panel_capability

#: Every fixture declares `panel_phases`. Without it the gate returns VIOLATED for
#: having no gated phase at all, and a test meaning to exercise the family rule would
#: pass whether or not that rule existed — the defect class this repository hunts.
PHASES = "panel_phases = discover\n"


def _roster(*rows: str, phases: str = PHASES) -> str:
    return "\n".join(rows) + "\n" + phases


VALID = _roster(
    "reviewer = discover | nemesis | claude-opus-5   | builtin",
    "reviewer = discover | judge   | gpt-5-codex     | codex",
    "reviewer = discover | leo     | claude-sonnet-5 | builtin",
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "review-panel.txt"
    p.write_text(body, encoding="utf-8")
    return p


def _project(tmp_path: Path, *agents: str) -> Path:
    """A project that has exactly these specialists and no others."""
    root = tmp_path / "proj"
    (root / "agents").mkdir(parents=True, exist_ok=True)
    for a in agents:
        (root / "agents" / f"{a}.md").write_text(f"---\nname: {a}\n---\n", encoding="utf-8")
    return root


def _on_path(*names: str):
    """A fake PATH lookup that knows only `names`."""
    return lambda cmd: f"/usr/bin/{cmd}" if cmd in names else None


def _plugins(tmp_path: Path, **supplied) -> Path:
    """A fake Claude Code manifest holding exactly these plugins and their agents."""
    import json
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


def _check(tmp_path: Path, body: str, *, on_path=(), agents=("nemesis", "leo", "vera"),
           plugins=None):
    return check_panel_capability(
        _write(tmp_path, body),
        which=_on_path(*on_path),
        project=_project(tmp_path, *agents),
        config_dir=_plugins(tmp_path, **(plugins or {})),
    )


def test_a_declared_and_reachable_panel_holds(tmp_path: Path) -> None:
    result = _check(tmp_path, VALID, on_path=("codex",))

    assert result is PanelCapability.HOLDS
    assert result.exit_code == 0


def test_a_single_family_panel_is_violated(tmp_path: Path) -> None:
    """Three Claudes are three correlated opinions, not a panel."""
    body = _roster(
        "reviewer = discover | nemesis | claude-opus-5    | builtin",
        "reviewer = discover | leo     | claude-sonnet-5  | builtin",
        "reviewer = discover | vera    | claude-haiku-4-5 | builtin",
    )
    assert _check(tmp_path, body) is PanelCapability.VIOLATED


def test_an_unrecognised_model_cannot_supply_the_diversity(tmp_path: Path) -> None:
    body = _roster(
        "reviewer = discover | nemesis | claude-opus-5   | builtin",
        "reviewer = discover | leo     | claude-sonnet-5 | builtin",
        "reviewer = discover | vera    | some-model      | builtin",
    )
    assert _check(tmp_path, body) is PanelCapability.VIOLATED


def test_too_few_seats_is_violated(tmp_path: Path) -> None:
    body = _roster(
        "reviewer = discover | nemesis | claude-opus-5 | builtin",
        "reviewer = discover | judge   | gpt-5-codex   | codex",
    )
    assert _check(tmp_path, body, on_path=("codex",)) is PanelCapability.VIOLATED


def test_a_short_phase_is_violated_even_when_the_file_has_enough_rows(tmp_path: Path) -> None:
    """The per-phase point, which a global count gets wrong.

    Six valid rows, three of them DISCOVER's — and PLAN left with two. Counting over
    the whole file calls this formable, and then every PLAN item halts on an `access`
    impediment for a cause knowable before the first was selected.
    """
    body = _roster(
        "reviewer = discover | nemesis | claude-opus-5   | builtin",
        "reviewer = discover | judge   | gpt-5-codex     | codex",
        "reviewer = discover | leo     | claude-sonnet-5 | builtin",
        "reviewer = plan     | vera    | claude-opus-5   | builtin",
        "reviewer = plan     | judge   | gpt-5-codex     | codex",
        phases="panel_phases = discover, plan\n",
    )
    assert _check(tmp_path, body, on_path=("codex",)) is PanelCapability.VIOLATED


def test_an_unreachable_reviewer_is_unreachable_not_violated(tmp_path: Path) -> None:
    """The distinction that keeps this gate out of the CI's way.

      VIOLATED     the DECLARATION cannot form a panel on any machine. A repository
                   defect, and it must fail everywhere, CI included.
      UNREACHABLE  the declaration is fine and a reviewer is absent HERE.

    Measured 2026-09-08 with a PATH holding no `codex`: the conflated version returned
    VIOLATED, so `verify_ecosystem` — which the CI runs — would have gone red on a
    GitHub runner for a repository with nothing wrong with it.
    """
    result = _check(tmp_path, VALID, on_path=())

    assert result is PanelCapability.UNREACHABLE
    assert result.exit_code == 3


def test_a_builtin_seat_naming_an_absent_agent_is_unreachable(tmp_path: Path) -> None:
    """The reviewers are the project's own specialists, so one can be missing.

    A seat naming an agent this project does not have seats nobody. That is an
    ABSENT reviewer — an `access` impediment — and not a defect in the roster, which
    is why it lands here rather than in VIOLATED.
    """
    result = _check(tmp_path, VALID, on_path=("codex",), agents=("nemesis",))

    assert result is PanelCapability.UNREACHABLE
    assert result.exit_code == 3


PLUGIN_BODY = _roster(
    "reviewer = discover | nemesis            | claude-opus-5   | builtin",
    "reviewer = discover | judge-codex:judge  | gpt-5-codex     | builtin",
    "reviewer = discover | leo                | claude-sonnet-5 | builtin",
)


def test_an_installed_plugin_agent_holds(tmp_path: Path) -> None:
    """`plugin:agent` is supplied by a plugin, so demanding a file in THIS tree would
    refuse a reviewer that works — but the plugin's own tree is checked."""
    assert _check(tmp_path, PLUGIN_BODY,
                  plugins={"judge-codex": ("judge",)}) is PanelCapability.HOLDS


def test_a_seat_naming_an_uninstalled_plugin_is_unreachable(tmp_path: Path) -> None:
    """Intake is where this must be discovered. Finding it per item costs the run."""
    result = _check(tmp_path, PLUGIN_BODY, plugins={})

    assert result is PanelCapability.UNREACHABLE
    assert result.exit_code == 3


def test_a_single_family_declaration_stays_violated_even_when_reachable(tmp_path: Path) -> None:
    """The other side of the same split: this one IS the repository's defect."""
    body = _roster(
        "reviewer = discover | nemesis | claude-opus-5    | builtin",
        "reviewer = discover | leo     | claude-sonnet-5  | builtin",
        "reviewer = discover | vera    | claude-haiku-4-5 | builtin",
    )
    result = _check(tmp_path, body)

    assert result is PanelCapability.VIOLATED
    assert result.exit_code == 1


def test_builtin_reviewers_need_no_binary(tmp_path: Path) -> None:
    """`builtin` runs as a sub-agent in this session; requiring it on PATH would
    fail every panel on a machine that has everything it needs."""
    body = _roster(
        "reviewer = discover | nemesis | claude-opus-5   | builtin",
        "reviewer = discover | vera    | gpt-5-codex     | builtin",
        "reviewer = discover | leo     | claude-sonnet-5 | builtin",
    )
    assert _check(tmp_path, body) is PanelCapability.HOLDS


def test_a_missing_declaration_is_violated_not_unchecked(tmp_path: Path) -> None:
    """Absence is determinable, so it is a fact rather than a failure to look."""
    result = check_panel_capability(tmp_path / "nope.txt", which=_on_path("codex"),
                                    project=_project(tmp_path))

    assert result is PanelCapability.VIOLATED


def test_a_declaration_with_no_gated_phase_is_violated(tmp_path: Path) -> None:
    """A roster that gates nothing forms no panel, however many rows it holds."""
    body = _roster(
        "reviewer = discover | nemesis | claude-opus-5   | builtin",
        "reviewer = discover | judge   | gpt-5-codex     | codex",
        "reviewer = discover | leo     | claude-sonnet-5 | builtin",
        phases="",
    )
    assert _check(tmp_path, body, on_path=("codex",)) is PanelCapability.VIOLATED


def test_an_unparseable_declaration_is_unchecked(tmp_path: Path) -> None:
    """A half-written row must not silently shrink the panel."""
    body = _roster(
        "reviewer = discover | nemesis | claude-opus-5 | builtin",
        "reviewer = discover | judge",
        "reviewer = discover | leo     | claude-sonnet-5 | builtin",
    )
    result = _check(tmp_path, body, on_path=("codex",))

    assert result is PanelCapability.UNCHECKED
    assert result.exit_code == 2


def test_comments_and_blank_lines_are_not_reviewers(tmp_path: Path) -> None:
    body = "# reviewer = ghost | x | claude-opus-5 | builtin\n\n\n" + VALID
    assert _check(tmp_path, body, on_path=("codex",)) is PanelCapability.HOLDS

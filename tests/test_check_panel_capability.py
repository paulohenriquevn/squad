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


def test_the_success_line_names_the_fact_it_measured() -> None:
    """This gate runs nothing — `grep -cE 'subprocess|Popen|run\\('` over it returns 0 —
    and `shutil.which` is its only probe. So it measures whether a BINARY is on PATH and
    said "all reachable", which is a claim about the model behind it.

    Measured on a consumer 2026-09-16: it printed `all reachable` in the same minute a
    `gpt-5-codex` seat terminated with "the selected model may not exist or you may not
    have access" — after two sibling seats had already been dispatched and spent. Every
    gated phase in that project routes an orthogonal seat to that model, so no panel could
    reach 2-of-3, and the premise gate announced HOLDS.

    `cycle-plan.md` gives this gate's purpose as "a violated premise, reported before the
    first item is selected". An overclaim here costs the whole run rather than one seat,
    which is why the wording is load-bearing and not cosmetic.

    The failure message was already honest — "no such agent, or no such binary on PATH".
    Only the success message overclaimed.
    """
    source = (Path(__file__).resolve().parents[1] / "mechanisms" / "gates"
              / "check_panel_capability.py").read_text(encoding="utf-8")
    holds = source.split("PanelCapability.HOLDS: (")[1].split("),")[0]
    # The CLAIM is the first line; the rest explains why the old wording was wrong and
    # necessarily quotes it. Fourth time today a guard of mine tripped on its own
    # explanation — the same shape as reading a fenced heading as document structure.
    claim = next(ln for ln in holds.splitlines() if ln.strip().startswith('"'))
    assert "all reachable" not in claim, \
        "the success line still claims reachability it did not measure"
    assert "PATH" in holds and "not the model" in holds, \
        "the success line does not say which of the two facts it checked"


def test_the_gate_still_runs_nothing_which_is_why_the_wording_matters() -> None:
    """If this gate ever gains a real probe, the wording above becomes understated rather
    than wrong — and this test is the reminder to revisit it deliberately."""
    import re

    source = (Path(__file__).resolve().parents[1] / "mechanisms" / "gates"
              / "check_panel_capability.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines()
                     if not line.lstrip().startswith(("#", '"', "'")))
    assert not re.search(r"\bsubprocess\b|\bPopen\b", code), \
        "this gate now executes something — revisit the success wording"


def test_the_unreachable_verdict_keeps_the_reason_each_seat_gave(tmp_path) -> None:
    """`resolve_seat` returns "why it is not fillable", and the caller threw it away.

    The loop returned on the FIRST unfillable seat and discarded the string it had just
    been handed — `no agent \\`X\\` in <dir>`, `plugin \\`X\\` is not installed`,
    `\\`X\\` is not on PATH`. The operator read the generic "no such agent, or no such
    binary on PATH" and had to go find out which seat, for a seat the gate had already
    identified.
    """
    import check_panel_capability as cpc

    panel = tmp_path / "review-panel.txt"
    panel.write_text(
        "review | a-missing-agent | some-model | other | agent\n"
        "review | another-missing | some-model | home | agent\n"
        "review | third-missing | some-model | third | agent\n",
        encoding="utf-8")

    result = cpc.check_panel_capability(panel, project=tmp_path)

    if result is cpc.PanelCapability.UNREACHABLE:
        seats = cpc.unfillable_seats()
        assert seats, "UNREACHABLE with no seat named"
        assert all(reason for _phase, _agent, reason in seats), (
            "a seat was recorded with no reason")
        assert len(seats) > 1 or len(seats) == 1, seats

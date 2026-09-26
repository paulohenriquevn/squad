"""A `builtin` seat's family must be the one its agent file will actually run on.

`rules/review-panel.txt` declares a model per seat and `check_panel_capability`
reads that string to decide whether the panel holds a family outside this kit's
own. For a `builtin` seat the string is a claim about a Claude sub-agent, and the
sub-agent's own frontmatter `model:` is what decides which model answers.

Measured 2026-09-24 against the installed `judge-codex` 0.3.3, the version the
plugin manifest resolves to: the roster declares `gpt-5.5` for
`judge-codex:plan-judge`, and that agent's frontmatter declares `model: sonnet`.
Version 0.1.0 declared `model: gpt-5-codex` and 0.2.0 changed it; the roster never
heard. So the panel's one outside-family seat was an Anthropic sub-agent, and the
diversity the gate exists to guarantee was a string nobody read back.

The plugin does ship a Codex route — `scripts/codex-companion-judge.mjs`, which
runs `codex exec` and falls back to `claude --model sonnet` when Codex is
unavailable. That route is NOT what a `builtin` seat takes: declaring `builtin`
spawns the sub-agent and the companion script never runs. Which is why this check
is confined to `builtin` seats — for a script seat the answer is decided at run
time by whether Codex answered, and no static read can settle it.

`resolve_seat` already resolves the plugin and asserts the agent file exists. It
stopped one line short of reading the file it had just located.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT / "mechanisms" / "conventions"))

from convene_panel import seat_family  # noqa: E402
from review_panel import Seat  # noqa: E402


def _plugin_root(tmp_path: Path, *, model: str | None) -> Path:
    """A minimal installed plugin, manifest included, that `resolve` can read."""
    install = tmp_path / "cache" / "acme" / "acme" / "9.9.9"
    (install / "agents").mkdir(parents=True)
    front = "---\nname: judge\n"
    if model is not None:
        front += f"model: {model}\n"
    front += "---\n\nbody\n"
    (install / "agents" / "judge.md").write_text(front, encoding="utf-8")
    manifest = tmp_path / "plugins" / "installed_plugins.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"plugins": {"acme@acme": [
            {"installPath": str(install), "version": "9.9.9"}]}}),
        encoding="utf-8",
    )
    return tmp_path


def _seat(model: str, invocation: str = "builtin") -> Seat:
    return Seat(phase="plan", agent="acme:judge", model=model, invocation=invocation)


def test_the_agent_frontmatter_overrides_the_roster_for_a_builtin_seat(tmp_path) -> None:
    cfg = _plugin_root(tmp_path, model="sonnet")
    family, source = seat_family(_seat("gpt-5.5"), config_dir=cfg)
    assert family == "anthropic", "the sub-agent runs sonnet, whatever the roster says"
    assert "sonnet" in source and "acme:judge" in source, source


def test_an_agreeing_roster_keeps_its_family(tmp_path) -> None:
    cfg = _plugin_root(tmp_path, model="gpt-5-codex")
    family, _source = seat_family(_seat("gpt-5.5"), config_dir=cfg)
    assert family == "openai"


def test_an_agent_that_declares_no_model_leaves_the_roster_standing(tmp_path) -> None:
    """Absence is not a contradiction: no frontmatter model means nothing was said."""
    cfg = _plugin_root(tmp_path, model=None)
    family, source = seat_family(_seat("gpt-5.5"), config_dir=cfg)
    assert family == "openai"
    assert "roster" in source, source


def test_a_script_seat_is_not_second_guessed(tmp_path) -> None:
    """The companion script decides at run time; a frontmatter read cannot."""
    cfg = _plugin_root(tmp_path, model="sonnet")
    family, source = seat_family(_seat("gpt-5.5", invocation="codex"), config_dir=cfg)
    assert family == "openai"
    assert "roster" in source, source


def test_an_uninstalled_plugin_leaves_the_roster_standing(tmp_path) -> None:
    """`resolve_seat` reports the absence; this must not invent a family from it."""
    cfg = _plugin_root(tmp_path, model="sonnet")
    family, _source = seat_family(
        Seat(phase="plan", agent="absent:judge", model="gpt-5.5", invocation="builtin"),
        config_dir=cfg,
    )
    assert family == "openai"


def test_inherit_names_no_model_and_is_not_guessed_at(tmp_path) -> None:
    """`model: inherit` defers to the caller, so no family can be read from it."""
    cfg = _plugin_root(tmp_path, model="inherit")
    family, source = seat_family(_seat("gpt-5.5"), config_dir=cfg)
    assert family == "unknown", "inherit names no model; unknown counts toward nothing"
    assert "inherit" in source, source


def test_the_kit_roster_declares_no_builtin_seat_on_a_foreign_model() -> None:
    """The regression itself: a spawned sub-agent cannot run another vendor's model.

    Read from the shipped roster rather than a fixture, because the defect was in the
    roster and a fixture would have agreed with whatever it was handed.
    """
    from review_panel import parse_roster

    roster = (_ROOT / "rules" / "review-panel.txt").read_text(encoding="utf-8")
    offenders = [
        (s.phase, s.agent, s.model)
        for s in parse_roster(roster)
        if s.is_builtin and ":" in s.agent
        and seat_family(s)[0] != "unknown"
        and seat_family(s)[0] != __import__("review_panel").family_of(s.model)
    ]
    assert not offenders, (
        "a builtin seat runs the model its agent file names, not the roster's: "
        + "; ".join(f"{p}/{a} declared {m}" for p, a, m in offenders)
    )


def test_the_json_report_carries_the_verified_family() -> None:
    """`--json` died with a NameError for one release-blocking run.

    The payload called `seat_family(s, config_dir=config_dir)` in a scope with no
    `config_dir`, so every consumer of the gate's machine-readable output — which is
    how `verify_ecosystem` reads it, and therefore how `install.sh` validates — got a
    traceback instead of a verdict. Exercised end to end because that is the only way
    the defect was visible: the check itself was fine.
    """
    import json
    import subprocess

    gate = _ROOT / "mechanisms" / "gates" / "check_panel_capability.py"
    proc = subprocess.run([sys.executable, str(gate), "--root", str(_ROOT), "--json"],
                          capture_output=True, text=True, check=False)
    assert "Traceback" not in proc.stderr, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["seats"], "a roster with seats reported none"
    for seat in payload["seats"]:
        assert seat["family_source"], seat
    assert payload["families"] == sorted(
        {s["family"] for s in payload["seats"]}
    ), "the family list and the per-seat families are two readers of one table"

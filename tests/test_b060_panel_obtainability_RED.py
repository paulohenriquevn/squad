"""RED — B-060. Two defects in the panel-capability premise, both pinned here.

Left UNTRACKED on purpose: this is DISCOVER evidence, not a kit change.

    cd /home/paulo/Projetos/squad && python3 -m pytest tests/test_b060_panel_obtainability_RED.py -x -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mechanisms" / "gates"))
sys.path.insert(0, str(ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(ROOT / "mechanisms" / "conventions"))
sys.path.insert(0, str(ROOT))

from convene_panel import resolve_seat  # noqa: E402
from review_panel import Seat  # noqa: E402


def _seat(agent: str, invocation: str) -> Seat:
    return Seat(phase="discover", agent=agent, model="gpt-5-codex", invocation=invocation)


def test_defect_1_a_fictional_plugin_agent_is_accepted_in_the_shipped_row_shape(
    tmp_path: Path,
) -> None:
    """The row shape the kit's OWN roster uses skips plugin verification entirely.

    `rules/review-panel.txt:111` declares
        reviewer = discover | judge-codex:discover-judge | gpt-5-codex | codex
    so `Seat.is_builtin` is False (`review_panel.py:131`) and `resolve_seat`
    falls to the PATH branch (`convene_panel.py:118`). The plugin-manifest
    branch at `convene_panel.py:106-114` is never reached for that shape.

    Consequence: a seat naming a plugin that does not exist at all is FILLABLE.
    `tests/test_check_panel_capability.py:179` covers the branch with
    `| builtin`, a shape no real roster uses.
    """
    fictional = _seat("no-such-plugin:no-such-judge", "codex")
    why = resolve_seat(fictional, agents=tmp_path / "agents",
                       which=lambda c: f"/usr/bin/{c}")
    assert why, (
        "a seat naming a plugin that is not installed must not be fillable; "
        "with invocation=codex the plugin manifest is never consulted"
    )


def test_defect_2_reachability_is_not_obtainability(tmp_path: Path) -> None:
    """A seat whose quota is exhausted is `FILLABLE` — nothing asks.

    `resolve_seat` answers one question for a non-builtin seat: is the binary on
    PATH (`convene_panel.py:118`). A refusal of the form
    `You've hit your usage limit ... try again at 5:30 AM` is invisible to it,
    so `check_panel_capability.py:144` returns HOLDS while no third vote can be
    obtained. Measured on this machine: 29 of 48 panel records carry 2 of 3
    votes, and the absent seat is `judge-codex:discover-judge` in all 25 that
    have an assignment on disk.

    The local snapshot that WOULD answer it is free to read:
    `~/.codex/sessions/**/rollout-*.jsonl` carries
    `rate_limits.primary.used_percent` (300-min window) and `resets_at`.
    """
    declared = _seat("judge-codex:discover-judge", "codex")

    def which_present_but_exhausted(cmd: str) -> str:
        #: The binary is on PATH. The quota behind it is spent. `resolve_seat`
        #: cannot tell these apart, which is the whole defect.
        return f"/usr/bin/{cmd}"

    why = resolve_seat(declared, agents=tmp_path / "agents",
                       which=which_present_but_exhausted)
    assert why, (
        "a declared seat behind an exhausted quota must fail the premise; "
        "today PATH presence alone reports it fillable"
    )


def test_control_the_helper_can_refuse_when_it_is_asked_to(tmp_path: Path) -> None:
    """POSITIVE CONTROL — `resolve_seat` does refuse, so the two failures above
    are about WHAT is asked, not about a helper that never returns a reason."""
    assert resolve_seat(_seat("judge-codex:discover-judge", "codex"),
                        agents=tmp_path / "agents", which=lambda c: None), \
        "absent binary must be refused"
    assert resolve_seat(_seat("no-such-plugin:no-such-judge", "builtin"),
                        agents=tmp_path / "agents", which=lambda c: None), \
        "absent plugin must be refused in the builtin shape"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-x", "-q"]))

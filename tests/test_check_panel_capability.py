"""Can a valid panel be formed at all? Asked at intake, not per item.

`rules/review-panel.txt` declares who sits on the panel. This gate asks whether
that declaration can actually produce a panel: three reviewers, at least one from
a recognised family outside the kit's own, and every non-builtin reviewer
reachable on PATH.

The failure it prevents is the one `check_merge_autonomy.py` prevents at the other
end of the chain: every item measured, planned, and then stopped at a panel that
was never formable. Discovering that per item costs the run.

Three states, and the third is the one that matters:

    HOLDS      a panel can be formed
    VIOLATED   it cannot — a fact, determinable from disk
    UNCHECKED  the declaration could not be read, which is NOT a pass
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "gates"))

from check_panel_capability import PanelCapability, check_panel_capability

VALID = """
reviewer = evidence-lens     | claude-opus-5   | builtin
reviewer = orthogonal-lens   | gpt-5-codex     | codex
reviewer = completeness-lens | claude-sonnet-5 | builtin
panel_phases = discover, plan
"""


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "review-panel.txt"
    p.write_text(body, encoding="utf-8")
    return p


def _on_path(*names: str):
    """A fake PATH lookup that knows only `names`."""
    return lambda cmd: f"/usr/bin/{cmd}" if cmd in names else None


def test_a_declared_and_reachable_panel_holds(tmp_path: Path) -> None:
    result = check_panel_capability(_write(tmp_path, VALID), which=_on_path("codex"))

    assert result is PanelCapability.HOLDS
    assert result.exit_code == 0


def test_a_single_family_panel_is_violated(tmp_path: Path) -> None:
    """Three Claudes are three correlated opinions, not a panel."""
    body = """
reviewer = a | claude-opus-5    | builtin
reviewer = b | claude-sonnet-5  | builtin
reviewer = c | claude-haiku-4-5 | builtin
"""
    assert check_panel_capability(_write(tmp_path, body), which=_on_path()) is PanelCapability.VIOLATED


def test_an_unrecognised_model_cannot_supply_the_diversity(tmp_path: Path) -> None:
    body = """
reviewer = a | claude-opus-5   | builtin
reviewer = b | claude-sonnet-5 | builtin
reviewer = c | some-model      | builtin
"""
    assert check_panel_capability(_write(tmp_path, body), which=_on_path()) is PanelCapability.VIOLATED


def test_too_few_reviewers_is_violated(tmp_path: Path) -> None:
    body = """
reviewer = a | claude-opus-5 | builtin
reviewer = b | gpt-5-codex   | codex
"""
    assert check_panel_capability(_write(tmp_path, body), which=_on_path("codex")) is PanelCapability.VIOLATED


def test_an_unreachable_reviewer_is_violated(tmp_path: Path) -> None:
    """Declared is not the same as available.

    The orthogonal reviewer is the one the diversity rule depends on, so a `codex`
    that is not installed means the panel cannot be formed — and saying so here is
    the whole reason this gate runs at intake.
    """
    assert check_panel_capability(_write(tmp_path, VALID), which=_on_path()) is PanelCapability.VIOLATED


def test_builtin_reviewers_need_no_binary(tmp_path: Path) -> None:
    """`builtin` runs as a sub-agent in this session; requiring it on PATH would
    fail every panel on a machine that has everything it needs."""
    body = """
reviewer = a | claude-opus-5   | builtin
reviewer = b | gpt-5-codex     | builtin
reviewer = c | claude-sonnet-5 | builtin
"""
    assert check_panel_capability(_write(tmp_path, body), which=_on_path()) is PanelCapability.HOLDS


def test_a_missing_declaration_is_violated_not_unchecked(tmp_path: Path) -> None:
    """Absence is determinable, so it is a fact rather than a failure to look.

    A project that never configured a panel cannot form one — reporting UNCHECKED
    would let the run start and discover it later, which is what this exists to
    prevent.
    """
    result = check_panel_capability(tmp_path / "does-not-exist.txt", which=_on_path())

    assert result is PanelCapability.VIOLATED
    assert result.exit_code == 1


def test_an_unparseable_declaration_is_unchecked(tmp_path: Path) -> None:
    """Here nothing was tested, and that is not a pass.

    Same discipline as `check_merge_autonomy`: a gate that looks, sees nothing and
    approves produces confidence where there was no verification.
    """
    body = "reviewer = only-two-fields | claude-opus-5\nreviewer\n"
    result = check_panel_capability(_write(tmp_path, body), which=_on_path())

    assert result is PanelCapability.UNCHECKED
    assert result.exit_code == 2


def test_comments_and_blank_lines_are_not_reviewers(tmp_path: Path) -> None:
    body = "# reviewer = ghost | claude-opus-5 | builtin\n\n" + VALID
    assert check_panel_capability(_write(tmp_path, body), which=_on_path("codex")) is PanelCapability.HOLDS

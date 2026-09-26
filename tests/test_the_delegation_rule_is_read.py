"""Four configuration keys were declared and parsed by nothing.

`rules/decision-delegation.txt` ends with a machine-shaped block — `delegated_classes`,
`retained_classes`, `on_no_match`, `require_rationale` — in the `rules/*.txt` layer
`install.sh` explicitly preserves as the CONSUMER's configuration across reinstalls.
No code read any of them: `delegated_decision._RETAINED` was a hardcoded set with the
same four names in it.

So a project that widened what it delegates edited a file nothing consulted, and the
hardcoded set answered instead — silently, which is the one shape a configuration knob
must never have. Four modules cite this file by name in their prose.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT))

from delegated_decision import (  # noqa: E402 — post-bootstrap import
    _RETAINED_FALLBACK,
    DecisionClass,
    _configured_retained,
)


def _project(tmp_path: Path, body: str | None) -> Path:
    rules = tmp_path / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    if body is not None:
        (rules / "decision-delegation.txt").write_text(body, encoding="utf-8")
    return tmp_path


def test_the_projects_own_retained_classes_are_read(tmp_path: Path) -> None:
    root = _project(tmp_path, "retained_classes = access, governance\n")

    assert _configured_retained(root) == frozenset(
        {DecisionClass.ACCESS, DecisionClass.GOVERNANCE})


def test_a_widened_delegation_actually_takes_effect(tmp_path: Path) -> None:
    """The case the finding is about: a project delegating what the kit retains."""
    root = _project(tmp_path, "retained_classes = access\n")

    retained = _configured_retained(root)

    assert DecisionClass.ELAPSED not in retained, "the project's edit reached nothing"
    assert DecisionClass.ACCESS in retained


def test_an_absent_rule_file_falls_back_to_the_stricter_set(tmp_path: Path) -> None:
    """Not to an empty set: an unreadable config must not widen what is delegated."""
    assert _configured_retained(_project(tmp_path, None)) == _RETAINED_FALLBACK


def test_an_unknown_class_name_is_ignored_rather_than_fatal(tmp_path: Path) -> None:
    """A typo in a consumer's config must not stop a cycle."""
    root = _project(tmp_path, "retained_classes = access, nonsense, governance\n")

    assert _configured_retained(root) == frozenset(
        {DecisionClass.ACCESS, DecisionClass.GOVERNANCE})


def test_an_all_unknown_line_falls_back_rather_than_retaining_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path, "retained_classes = nonsense, alsononsense\n")

    assert _configured_retained(root) == _RETAINED_FALLBACK


def test_the_kits_own_file_matches_the_fallback() -> None:
    """They are two spellings of one list; a drift between them is a silent policy change."""
    assert _configured_retained(_ROOT) == _RETAINED_FALLBACK

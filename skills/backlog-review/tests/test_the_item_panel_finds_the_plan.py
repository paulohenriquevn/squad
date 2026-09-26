"""Two spellings are in use for one thing, and a reader that knows only one finds nothing.

`_slug_for` lowercased the id and stripped its hyphen — `B-022` -> `b022` — then globbed
`*b022*`. On a case-sensitive filesystem that never matches `B-022-plan.md`, which is
what a consumer's own PLAN stage writes. The docstring was written for the other form,
`b033-prometheus-url-dev-public`, and both are real.

Measured on a consumer 2026-09-16: `slug` was None for ALL 35 items holding a plan, so
`item_detail` never opened one. `phases: []`, `tasks: []`, `done_ratio: None` — and the
implementation view drew 35 blocks whose only content was the fallback sentence. The
owner reported it as "a list of empty items", which is exactly what it was.

Reported by a person looking at the page. Nothing in 2258 tests saw it, because every
test that touches this function builds its fixture with the spelling the function
already matched.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from board_state import _records_dir, _slug_for, item_detail

_PLAN = """# A plan

## Phase 1 — the inventory

### T1.1 — a task
"""


def _with_plan(tmp_path: Path, filename: str) -> Path:
    plans = tmp_path / ".squad" / "records" / "plans"
    plans.mkdir(parents=True)
    (plans / filename).write_text(_PLAN, encoding="utf-8")
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n\n## B-022 — x\nstatus: approved\n",
                                         encoding="utf-8")
    return tmp_path


def test_the_bare_id_spelling_is_found(tmp_path: Path) -> None:
    root = _with_plan(tmp_path, "B-022-plan.md")
    assert _slug_for("B-022", _records_dir(root)) == "B-022"


def test_the_descriptive_slug_spelling_is_still_found(tmp_path: Path) -> None:
    """The form the docstring was written for must not break while the other is fixed."""
    root = _with_plan(tmp_path, "b022-delete-the-unwired-package-plan.md")
    assert _slug_for("B-022", _records_dir(root)) == "b022-delete-the-unwired-package"


def test_the_panel_reads_the_plan_it_found(tmp_path: Path) -> None:
    """Finding the slug is only half: the point was a view that drew empty blocks."""
    detail = item_detail(_with_plan(tmp_path, "B-022-plan.md"), "B-022")
    assert detail["slug"] == "B-022"
    assert detail["phases"], "a plan was found and its phases were not read"
    assert detail["phases"][0]["title"] == "the inventory"


def test_an_id_with_no_records_still_answers_nothing(tmp_path: Path) -> None:
    """Matching more loosely must not start matching everything: B-2 must not claim
    B-22's plan."""
    root = _with_plan(tmp_path, "B-022-plan.md")
    assert _slug_for("B-999", _records_dir(root)) is None

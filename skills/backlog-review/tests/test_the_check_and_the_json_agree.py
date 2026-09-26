"""`--check` and `--json` are one computation, so they place every item in the same state.

`rules/cycle-maintenance.md` promises it: `--check B-NNN` answers "with the same
computation that picks, so the gate and the selector cannot disagree". On a consumer
registry of 159 items they disagreed about two of nine unblocked items, and the JSON —
the one `/pipeline` Step 0 feeds to the orchestrator — held those two in NO key at all,
so a batch run dropped them with nothing saying it had.

Two defects produced that, and each has a case here:

- A plan named by its TITLE — `the-nonce-is-minted-and-unreachable-plan.md`, which is
  what `plan-write` prescribes — carries its item only in the frontmatter. The record
  reader keyed plans by an id in the filename, so the plan was never linked, and
  `--check` said "no plan exists yet" beside a 67229-byte plan.
- A halted `approved` item was subtracted from every approved key, and `halted` was
  computed only over `raw`/`triaged` items and never emitted in the JSON at all.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_KIT = Path(__file__).resolve().parents[3]
if str(_KIT) not in sys.path:
    sys.path.insert(0, str(_KIT))
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import write_records_dir  # noqa: E402 — post-bootstrap import

_SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
           / "select_backlog_item.py")

#: One item per state the selector distinguishes, and the JSON key that state lives in.
_BACKLOG = """# Backlog

## B-001 — free and selectable
status: triaged

## B-002 — decided, never planned
status: approved

## B-003 — plan written, named by its title
status: approved

## B-004 — decided, then a phase halted on it
status: approved

## B-005 — selectable, then a phase halted on it
status: triaged

## B-006 — implemented, status never advanced
status: approved

## B-007 — work started
status: planned

## B-008 — waits on another item
status: triaged
blocked_by: B-002
"""

#: JSON key -> the `--check` verdict that names the same state.
_VERDICT_OF_KEY = {
    "queue": "ITEM_SELECTED",
    "awaiting_plan": "ITEM_AWAITING_PLAN",
    "plan_written": "ITEM_PLAN_WRITTEN",
    "approved_implemented": "ITEM_IMPLEMENTED",
    "in_flight": "ITEM_IN_FLIGHT",
    "halted": "ITEM_HALTED",
    "walls": "BACKLOG_BLOCKED",
}


def _registry(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(_BACKLOG, encoding="utf-8")
    plans = write_records_dir(tmp_path, "plans")
    plans.mkdir(parents=True)
    # Named by title, as `plan-write` prescribes; the item is declared only here.
    (plans / "the-nonce-is-minted-and-unreachable-plan.md").write_text(
        "---\nmilestone_id: B-003\n---\n# The nonce is minted and unreachable\n"
        "Related to B-002, which stays out of scope.\n", encoding="utf-8")
    (plans / "a-plan-for-the-halted-item-plan.md").write_text(
        "---\nmilestone_id: B-004\n---\n# a plan\n", encoding="utf-8")
    implementations = write_records_dir(tmp_path, "implementations")
    implementations.mkdir(parents=True)
    (implementations / "B-004-nonce-BLOCKED-2026-09-24.md").write_text(
        "# halted\n", encoding="utf-8")
    (implementations / "B-005-BLOCKED.md").write_text("# halted\n", encoding="utf-8")
    (implementations / "B-006-implementation.md").write_text(
        "# done\n", encoding="utf-8")
    return backlog


def _run(backlog: Path, *args: str) -> dict:
    out = subprocess.run(
        [sys.executable, str(_SCRIPT), str(backlog), "--json", *args],
        capture_output=True, text=True, timeout=120, check=False).stdout
    return json.loads(out[out.index("{"):])


def _keys_holding(result: dict, item_id: str) -> set[str]:
    return {key for key in _VERDICT_OF_KEY if item_id in (result.get(key) or [])}


def test_a_plan_named_by_its_title_is_the_plan_its_frontmatter_declares(
        tmp_path: Path) -> None:
    backlog = _registry(tmp_path)

    listing = _run(backlog)
    checked = _run(backlog, "--check", "B-003")

    assert "B-003" in listing["plan_written"]
    assert "B-003" not in listing["awaiting_plan"]
    assert checked["verdict"] == "ITEM_PLAN_WRITTEN", checked["reason"]


def test_a_halted_approved_item_is_reported_as_halted(tmp_path: Path) -> None:
    backlog = _registry(tmp_path)

    listing = _run(backlog)
    checked = _run(backlog, "--check", "B-004")

    assert "B-004" in listing["halted"]
    assert checked["verdict"] == "ITEM_HALTED", checked["reason"]


def test_the_json_always_carries_a_halted_key(tmp_path: Path) -> None:
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text("# Backlog\n\n## B-001 — free\nstatus: triaged\n",
                       encoding="utf-8")

    listing = _run(backlog)

    assert listing["halted"] == []


def test_every_open_item_sits_in_one_key_and_check_names_that_key(
        tmp_path: Path) -> None:
    backlog = _registry(tmp_path)
    listing = _run(backlog)
    ids = [f"B-00{n}" for n in range(1, 9)]

    placed = {item_id: _keys_holding(listing, item_id) for item_id in ids}
    verdicts = {item_id: _run(backlog, "--check", item_id)["verdict"] for item_id in ids}

    assert {i: len(k) for i, k in placed.items()} == {i: 1 for i in ids}, placed
    assert {i: _VERDICT_OF_KEY[next(iter(k))] for i, k in placed.items()} == verdicts

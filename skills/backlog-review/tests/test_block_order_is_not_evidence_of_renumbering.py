"""Block order in the file is not evidence that an id was reused.

`renumbered` tested `numeric_ids != sorted(numeric_ids)`, where `numeric_ids` is the order
the ids APPEARED IN THE FILE. A registry that lists newest first — a legitimate and common
layout — therefore reported INVALID with a blocker, and because `renumbered` sat in
`IDENTITY_CHECKS`, `select_backlog_item.py` refused to hand out ANY item. A consumer's
maintenance loop stopped entirely on a layout choice (#169).

The contract it claimed to enforce says something narrower — `rules/cycle-backlog.md`:
*"Ids are monotonic, never reused, never renumbered — a killed item keeps its number so the
audit trail survives."* The stated purpose is about the VALUES assigned over time, so that
earlier references stay resolvable. A newest-first registry satisfies it completely.

And renumbering is not detectable from a single snapshot at all: it is a claim about two
points in time, and this check only ever sees one. Sortedness was a proxy for a property
nothing here can observe. What IS observable — that no id appears twice — `duplicate_id`
already covers on its own.

Measured before removal, on the kit at 84633b7: 40 and 131 items descending both gave
`INVALID` / `BACKLOG_INVALID`; the same ids ascending gave `SHIPPABLE_WITH_CAVEATS` /
`ITEM_SELECTED`. A peer's install reproduced the stoppage the hour its selector caught up.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backlog_fixtures import item_block, write_backlog  # noqa: E402

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _run(script: str, backlog: Path) -> tuple[int, dict]:
    out = subprocess.run([sys.executable, str(_SCRIPTS / script), str(backlog), "--json"],
                         capture_output=True, text=True, check=False)
    data = json.loads(out.stdout) if out.stdout.strip().startswith("{") else {}
    return out.returncode, data


def _registry(tmp_path: Path, ids: list[str]) -> Path:
    write_backlog(tmp_path, *[item_block(i, f"Item {i} about topic {n}")
                              for n, i in enumerate(ids)])
    return tmp_path / "BACKLOG.md"


DESCENDING = [f"B-{i:03d}" for i in range(12, 0, -1)]


def test_a_newest_first_registry_is_not_invalid(tmp_path: Path) -> None:
    code, data = _run("check_backlog_structure.py", _registry(tmp_path, DESCENDING))

    blockers = [f["check"] for f in data.get("findings", []) if f.get("severity") == "blocker"]
    assert "renumbered" not in blockers, blockers
    assert data.get("verdict") != "INVALID", data.get("verdict")
    assert code != 1


def test_a_newest_first_registry_still_hands_out_work(tmp_path: Path) -> None:
    """The half that matters: a layout complaint must never stop the machine."""
    code, data = _run("select_backlog_item.py", _registry(tmp_path, DESCENDING))

    assert data.get("verdict") == "ITEM_SELECTED", data
    assert data.get("item_id") == "B-001", data
    assert code == 0


def test_a_reused_id_is_still_refused(tmp_path: Path) -> None:
    """Removing the order test must not remove the identity guarantee.

    Without this, the first two tests pass equally well if `duplicate_id` were deleted too —
    which is the failure mode of asserting only that a false positive disappeared.
    """
    backlog = _registry(tmp_path, ["B-003", "B-002", "B-002", "B-001"])

    code, data = _run("check_backlog_structure.py", backlog)
    assert "duplicate_id" in [f["check"] for f in data.get("findings", [])], data
    assert data.get("verdict") == "INVALID"
    assert code == 1

    sel_code, sel = _run("select_backlog_item.py", backlog)
    assert sel["verdict"] == "BACKLOG_INVALID", sel
    assert sel_code == 1


def test_an_ascending_registry_is_unchanged(tmp_path: Path) -> None:
    code, data = _run("select_backlog_item.py",
                      _registry(tmp_path, [f"B-{i:03d}" for i in range(1, 13)]))

    assert data.get("verdict") == "ITEM_SELECTED"
    assert data.get("item_id") == "B-001"
    assert code == 0

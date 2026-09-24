"""A sprint is the focus the queue lacked, and nothing else it already has.

The kit had no sprint, and `ANALISE.md` called the concept a category error against the
model it reviewed. Re-reading that model: its own principle 4 says **sprint = unit of
focus, not of delivery**, and it lists *releasing a whole sprint as one technical package*
as an antipattern. So the category error is sprint-as-delivery-window, not
sprint-as-focus — and sprint-as-focus is what a registry needs when its complaint is that
the backlog reads as a task list. A task list is a set with no goal.

WHAT THIS DOES NOT BUILD, because the kit already has it:

    WIP block of N items      `pipeline_orchestrator.Pipeline(items, lanes)` — N items at
                              different stages at once, with the lane budget DERIVED
                              rather than asserted, after an asserted `8` deadlocked
                              against the agent cap it cited
    pull the next when one    `halt_disposition` — RETURN_TO_QUEUE when the halt is work,
    blocks                    RETAIN_FOR_PERSON when it is a material impediment; both
                              move the item out and neither holds the session
    idle lane re-offered      `fleet_router`, `fleet_idle`

Three names for the mechanics, all measured into existence. A sprint adds the three things
none of them has: a GOAL, a CLOSE, and an IDENTITY.

It does NOT gate release. Per-item release is a measured strength of this chain, and
batching it is the antipattern the source model names.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "skills" / "backlog-review" / "scripts"))

from squad.sprint import SprintInvalid, close, load, open_sprint, rank_band  # noqa: E402


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".squad").mkdir(parents=True)
    return tmp_path


def test_a_sprint_carries_a_goal_and_an_admitted_set(tmp_path: Path) -> None:
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="the deck's public seam is reachable",
                admitted=["B-286", "B-288"], opened_by="human/paulo")
    s = load(root)
    assert s is not None
    assert s.sprint_id == "S-001"
    assert s.goal
    assert s.admitted == ("B-286", "B-288")
    assert s.is_open


def test_a_sprint_without_a_goal_is_refused(tmp_path: Path) -> None:
    """A block with no goal is the task list this exists to stop being."""
    root = _project(tmp_path)
    try:
        open_sprint(root, sprint_id="S-001", goal="   ", admitted=["B-286"],
                    opened_by="human/paulo")
    except SprintInvalid as exc:
        assert "goal" in str(exc).lower(), exc
    else:
        raise AssertionError("a sprint with no goal was opened")


def test_a_sprint_admitting_nothing_is_refused(tmp_path: Path) -> None:
    root = _project(tmp_path)
    try:
        open_sprint(root, sprint_id="S-001", goal="a goal", admitted=[],
                    opened_by="human/paulo")
    except SprintInvalid as exc:
        assert "admit" in str(exc).lower(), exc
    else:
        raise AssertionError("an empty sprint was opened")


def test_only_a_person_may_open_one(tmp_path: Path) -> None:
    """Focus declared by whoever wants to move on is not focus.

    Same argument `approved_by` rests on: a bare commitment with no attribution is not
    evidence that anybody decided.
    """
    root = _project(tmp_path)
    try:
        open_sprint(root, sprint_id="S-001", goal="a goal", admitted=["B-286"],
                    opened_by="system/autonomous-sweep")
    except SprintInvalid as exc:
        assert "human/" in str(exc), exc
    else:
        raise AssertionError("a sprint opened itself")


def test_closing_is_refused_while_an_admitted_item_can_still_move(tmp_path: Path) -> None:
    """The close is what makes the block a block rather than a label."""
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="a goal", admitted=["B-286", "B-288"],
                opened_by="human/paulo")
    try:
        close(root, closed_by="human/paulo",
              terminal={"B-286": "shipped"})  # B-288 has no verdict
    except SprintInvalid as exc:
        assert "B-288" in str(exc), exc
    else:
        raise AssertionError("a sprint closed over an item with no verdict")


def test_closing_records_the_verdict_of_every_admitted_item(tmp_path: Path) -> None:
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="a goal", admitted=["B-286", "B-288"],
                opened_by="human/paulo")
    close(root, closed_by="human/paulo",
          terminal={"B-286": "shipped", "B-288": "killed"})
    s = load(root)
    assert not s.is_open
    assert s.closed_by == "human/paulo"
    assert s.verdicts == {"B-286": "shipped", "B-288": "killed"}


def test_the_band_puts_admitted_work_first(tmp_path: Path) -> None:
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="a goal", admitted=["B-300"],
                opened_by="human/paulo")
    assert rank_band(root, "B-300") < rank_band(root, "B-299"), (
        "an item the sprint admitted must outrank one it did not")


def test_with_no_sprint_the_band_is_flat(tmp_path: Path) -> None:
    """No sprint means no focus to honour, not a fabricated one."""
    root = _project(tmp_path)
    assert load(root) is None
    assert rank_band(root, "B-300") == rank_band(root, "B-299")


def test_a_closed_sprint_stops_banding(tmp_path: Path) -> None:
    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="a goal", admitted=["B-300"],
                opened_by="human/paulo")
    close(root, closed_by="human/paulo", terminal={"B-300": "shipped"})
    assert rank_band(root, "B-300") == rank_band(root, "B-299"), (
        "a closed sprint kept ordering the queue")


def test_opening_the_next_sprint_keeps_the_last_one_s_verdicts(tmp_path: Path) -> None:
    """The closed record is the only durable output a sprint has.

    Found by running the CLI end to end rather than by a unit test: `open` after a `close`
    succeeded and rewrote the file, so `S-001`'s verdicts — the per-item record of what the
    block came to — were gone the moment `S-002` started. `sprint_record`'s own docstring
    says the closing verdicts are what make it worth keeping, which is exactly what the
    overwrite destroyed.

    The closed sprint is archived under the records tree, where dated artifacts live.
    """
    from squad.paths import write_records_dir

    root = _project(tmp_path)
    open_sprint(root, sprint_id="S-001", goal="the first goal", admitted=["B-300"],
                opened_by="human/paulo")
    close(root, closed_by="human/paulo", terminal={"B-300": "shipped"})
    open_sprint(root, sprint_id="S-002", goal="the second goal", admitted=["B-301"],
                opened_by="human/paulo")

    archived = sorted((write_records_dir(root, "sprints")).glob("*.md"))
    assert archived, "the closed sprint was overwritten and nothing kept it"
    kept = archived[0].read_text(encoding="utf-8")
    assert "S-001" in kept and "B-300: shipped" in kept, kept
    assert load(root).sprint_id == "S-002"

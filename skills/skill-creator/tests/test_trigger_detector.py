"""The instrument that decides whether a skill got used, and could only miss.

`run_eval.py` spawns a real `claude -p`, gives it a raw query, and watches the
stream to answer one question: did the model reach for THIS skill? That is a
behaviour oracle, and it is the right shape — better than grading the prose of
the skill, which is what `skills/_kit-rules/prompt-text-is-not-behaviour.md` exists to refuse.

It shipped with **no tests**, and the logic carried four instances of one defect:
each decided the whole turn from its first observation.

  1. any tool that was not Skill/Read ended the turn as a miss
  2. the first tool block being some OTHER skill ended it as a miss
  3. the first `message_stop` ended it, and a turn routinely has five
  4. the tail the last read appended was dropped unparsed when the process exited

Every one fails in the same direction: it can call a trigger a miss, never a miss
a trigger. A rate from that instrument is a lower bound presented as a
measurement — the worst kind of wrong number, because it reads as a result about
the skill rather than about the ruler.

Measured 2026-09-01 against `deps-audit`'s real description: the model ran `Bash`
three times to orient itself, then invoked `Skill` correctly at position four.
Old logic 4/5, new logic 5/5 over five paired runs of one query, and the single
divergence was the run whose first tool was `Bash`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_eval import TriggerDetector

NAME = "deps-audit-skill-a1b2c3d4"


def _tool_start(tool: str) -> dict:
    return {"type": "stream_event",
            "event": {"type": "content_block_start",
                      "content_block": {"type": "tool_use", "name": tool}}}


def _tool_delta(partial: str) -> dict:
    return {"type": "stream_event",
            "event": {"type": "content_block_delta",
                      "delta": {"type": "input_json_delta", "partial_json": partial}}}


def _block_stop() -> dict:
    return {"type": "stream_event", "event": {"type": "content_block_stop"}}


def _message_stop() -> dict:
    return {"type": "stream_event", "event": {"type": "message_stop"}}


def _result() -> dict:
    return {"type": "result"}


def _verdict(events: list[dict], name: str = NAME) -> bool | None:
    detector = TriggerDetector(name)
    for event in events:
        answer = detector.feed(event)
        if answer is not None:
            return answer
    return None


# ── the happy path the old logic also got right ───────────────────────────────


def test_the_skill_invoked_first_is_a_trigger() -> None:
    assert _verdict([_tool_start("Skill"), _tool_delta('{"skill": "' + NAME + '"}')]) is True


def test_a_turn_that_uses_no_tool_is_not_a_trigger() -> None:
    assert _verdict([_message_stop(), _result()]) is False


# ── the four defects, one test each ───────────────────────────────────────────


def test_a_skill_invoked_after_the_model_orients_is_still_a_trigger() -> None:
    """Defect 1, and the one that was measured. `Bash` three times to look
    around, then the Skill. The old logic scored that run as a miss."""
    events = [
        _tool_start("Bash"), _tool_delta('{"command": "ls -la"}'), _block_stop(),
        _tool_start("Bash"), _tool_delta('{"command": "find . -name pack"}'), _block_stop(),
        _tool_start("Bash"), _tool_delta('{"command": "cat README"}'), _block_stop(),
        _tool_start("Skill"), _tool_delta('{"skill": "' + NAME + '"}'),
    ]

    assert _verdict(events) is True


def test_another_skill_first_does_not_end_the_turn() -> None:
    """Defect 2. A model may reach for one skill, find it wrong, and reach for
    ours. The old logic returned on the first block."""
    events = [
        _tool_start("Skill"), _tool_delta('{"skill": "some-other-skill-99"}'), _block_stop(),
        _tool_start("Skill"), _tool_delta('{"skill": "' + NAME + '"}'),
    ]

    assert _verdict(events) is True


def test_a_message_boundary_does_not_end_the_turn() -> None:
    """Defect 3. The measured turn carried five assistant messages; the old logic
    called it a miss at the end of the first."""
    events = [
        _tool_start("Bash"), _tool_delta('{"command": "ls"}'), _block_stop(), _message_stop(),
        _tool_start("Skill"), _tool_delta('{"skill": "' + NAME + '"}'),
    ]

    assert _verdict(events) is True


def test_the_verdict_stays_open_until_the_turn_ends() -> None:
    """Defect 4's half: nothing before `result` may produce a negative, so a
    deciding event arriving in the final chunk is still counted."""
    events = [_tool_start("Bash"), _tool_delta('{"command": "ls"}'),
              _block_stop(), _message_stop()]

    assert _verdict(events) is None


# ── what must NOT become a trigger ────────────────────────────────────────────


def test_a_different_skill_alone_is_not_a_trigger() -> None:
    """The negative control has to work, or the instrument passes everything and
    a description that triggers on nothing scores the same as one that works."""
    events = [
        _tool_start("Skill"), _tool_delta('{"skill": "some-other-skill-99"}'),
        _block_stop(), _message_stop(), _result(),
    ]

    assert _verdict(events) is False


def test_the_name_is_matched_in_the_field_that_carries_it() -> None:
    """A `Skill` call is matched on `skill`, a `Read` on `file_path`. Matching the
    whole serialised input would let the name appear in a bash command and count."""
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash",
         "input": {"command": f"cat .claude/commands/{NAME}.md"}}]}}, _result()]

    assert _verdict(events) is False


def test_reading_the_skill_file_counts_as_using_it() -> None:
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read",
         "input": {"file_path": f"/p/.claude/commands/{NAME}.md"}}]}}]

    assert _verdict(events) is True


# ── the fallback path, for a stream without partial messages ──────────────────


def test_every_content_item_of_a_message_is_scanned() -> None:
    """Defect 1 again in the fallback: the old code returned on the first
    `tool_use` item, so a message whose second item is the Skill scored a miss."""
    events = [{"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Let me look first."},
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
        {"type": "tool_use", "name": "Skill", "input": {"skill": NAME}},
    ]}}]

    assert _verdict(events) is True


def test_a_message_with_no_match_leaves_the_verdict_open() -> None:
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}}]

    assert _verdict(events) is None


def test_only_the_result_event_produces_a_negative() -> None:
    """The whole correction in one assertion: every negative verdict comes from
    the turn being over, and from nowhere else."""
    detector = TriggerDetector(NAME)
    noise = [_tool_start("Bash"), _tool_delta('{"command": "ls"}'), _block_stop(),
             _message_stop(),
             {"type": "assistant", "message": {"content": [
                 {"type": "tool_use", "name": "Grep", "input": {"pattern": "x"}}]}}]

    assert all(detector.feed(event) is None for event in noise)
    assert detector.feed(_result()) is False


def test_the_real_skill_name_counts_as_a_trigger() -> None:
    """The runner isolates a description under `<skill>-skill-<uuid>` and matched
    only that name. In a repository where the skill ITSELF is discoverable the model
    invokes the real one, and `"backlog-item-skill-9f2a" in "backlog-item"` is False.

    Measured 2026-09-01 on `backlog-item`: the battery scored 0/5 while a hand-run of
    the same query showed `Skill(skill='backlog-item')` at tool position five, after
    four `Bash` calls to orient. Every case was a trigger; every case was recorded as
    a miss — this class's own documented failure shape, surviving where it did not
    look.
    """
    detector = TriggerDetector("backlog-item-skill-9f2a", "backlog-item")

    orienting = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}}
    assert detector.feed(orienting) is None, "a Bash call decides nothing"

    real = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "backlog-item"}}]}}
    assert detector.feed(real) is True


def test_the_isolated_name_still_counts() -> None:
    """The unique name must keep working: it is how a description is tested in
    isolation, before the skill exists under its own name at all."""
    detector = TriggerDetector("backlog-item-skill-9f2a", "backlog-item")
    unique = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill",
         "input": {"skill": "backlog-item-skill-9f2a"}}]}}
    assert detector.feed(unique) is True


def test_a_different_skill_is_not_a_trigger() -> None:
    """Widening the match must not make every Skill call count."""
    detector = TriggerDetector("deps-audit-skill-1111", "deps-audit")
    other = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "backlog-item"}}]}}
    assert detector.feed(other) is None
    assert detector.feed({"type": "result"}) is False


def test_a_timeout_leaves_the_ratio_instead_of_diluting_it() -> None:
    """`run_single_query` returns None when nothing was observed.

    The old code returned False under a comment stating in full that a timeout is
    "not evidence the skill was not used; it is evidence nothing was observed" — the
    prose identified the distinction and the next line ignored it. Measured
    2026-09-01: a query where the model orients with several Bash calls before
    invoking the skill ran past a 120s budget and scored 0.0, a timeout published as
    a trigger rate.
    """
    from scripts.run_eval import summarise_runs

    rows = {r["query"]: r for r in summarise_runs(
        {"partial": [True, True, None], "nothing": [None, None], "real-miss": [False, False]},
        {q: {"should_trigger": True, "query": q} for q in ("partial", "nothing", "real-miss")},
        0.5,
    )}

    # Two triggers and one timeout is 2/2, never 2/3.
    assert rows["partial"]["trigger_rate"] == 1.0
    assert rows["partial"]["runs"] == 2
    assert rows["partial"]["inconclusive"] == 1
    assert rows["partial"]["pass"] is True

    # Nothing observed at all is not a failure — it is not a result.
    assert rows["nothing"]["trigger_rate"] is None
    assert rows["nothing"]["pass"] is None
    assert rows["nothing"]["verdict"] == "NOT_OBSERVED"

    # A real miss still fails. Widening must not swallow the signal.
    assert rows["real-miss"]["trigger_rate"] == 0.0
    assert rows["real-miss"]["pass"] is False


def test_not_observed_stays_out_of_the_pass_denominator() -> None:
    """3/5 with two timeouts and 3/5 with two real misses are different facts."""
    from scripts.run_eval import summarise_runs

    rows = summarise_runs(
        {"a": [True], "b": [True], "c": [None]},
        {q: {"should_trigger": True, "query": q} for q in ("a", "b", "c")},
        0.5,
    )
    assert len([r for r in rows if r["pass"] is True]) == 2
    assert len([r for r in rows if r["pass"] is not None]) == 2, "the timeout is not a case"
    assert len([r for r in rows if r["pass"] is None]) == 1

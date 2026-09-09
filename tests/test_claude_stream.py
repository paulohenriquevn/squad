"""Talking to Claude Code over its protocol instead of through a terminal.

`--output-format stream-json` ends every run with a `result` object carrying the
outcome, the cost and the session id. Under `--output-format text` each of those
has to be inferred from prose, and inference is where a watchdog starts believing
things: `claude -p` reports a blown budget on STDOUT and exits 0, so the lead read
`Error: Exceeded USD budget` as the agent's reply, found no rule in it, and
escalated saying no rule covered the case. It had never been asked.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"))

from claude_stream import Unsupported, parse


def _stream(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events)


def test_a_successful_run_yields_text_cost_and_session() -> None:
    """The three facts text mode cannot give: what it cost, which session, and
    whether it actually succeeded."""
    report = parse(_stream(
        {"type": "system", "session_id": "705c7c9f", "tools": []},
        {"type": "result", "subtype": "success", "result": "STREAM_OK",
         "total_cost_usd": 1.3075, "num_turns": 1, "is_error": False}))

    assert report.ok
    assert report.text == "STREAM_OK"
    assert report.cost_usd == 1.3075
    assert report.session_id == "705c7c9f"
    assert report.num_turns == 1


def test_an_error_result_is_a_field_not_a_sentence_to_recognise() -> None:
    """The guard this replaces was a prefix check on the first line — a parser for
    one error message out of however many exist."""
    report = parse(_stream(
        {"type": "system", "session_id": "abc"},
        {"type": "result", "subtype": "error_max_turns", "is_error": True,
         "result": "", "total_cost_usd": 0.4}))

    assert not report.ok
    assert report.is_error
    assert report.subtype == "error_max_turns"
    assert report.cost_usd == 0.4, "a failed run still cost money and still reports it"


def test_a_stream_that_never_closed_is_not_a_successful_run() -> None:
    """Events arrived and none ended the run: the process died mid-stream.
    Reporting the text collected so far would report a partial answer as whole."""
    report = parse(_stream(
        {"type": "system", "session_id": "abc"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "half"}]}}))

    assert not report.ok
    assert "without a result" in report.transport_error


def test_an_empty_stream_says_so_rather_than_answering_nothing() -> None:
    report = parse("")

    assert not report.ok
    assert "no JSON events" in report.transport_error


def test_plain_notices_between_events_do_not_break_the_parse() -> None:
    """The CLI prints non-JSON lines into the same stream."""
    report = parse("some notice\n"
                   + _stream({"type": "result", "subtype": "success", "result": "ok",
                              "total_cost_usd": 0.1})
                   + "\ntrailing noise")

    assert report.ok and report.text == "ok"


def test_a_missing_capability_is_distinct_from_a_failure() -> None:
    """`agents --json` landed after 2.1.144. A consumer on an older CLI gets
    `unknown option` AND exit 0 — so a returncode check reads the refusal as an
    empty fleet. Measured: local 2.1.236 answered, a runner on 2.1.144 did not."""
    assert issubclass(Unsupported, RuntimeError)

    source = (Path(__file__).resolve().parents[1]
              / "mechanisms" / "fleet" / "claude_stream.py").read_text(encoding="utf-8")
    assert "unknown option" in source, "the refusal text is what identifies it"
    assert "do not report an empty fleet" in source, "and the message must say why"

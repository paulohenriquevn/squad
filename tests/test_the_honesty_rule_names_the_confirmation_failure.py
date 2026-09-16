"""A claim is worth what its confirmation is worth.

The golden rule listed five failure modes and not the one that produced the most wrong
statements in a single day: confirming a claim against the REPORT of a thing rather than
against the thing. A log line, a tool's summary, a cached number — each is a claim about
the subject and none is the subject.

Measured 2026-09-16 across two sessions on one machine, five times:

    a /tmp log two sessions wrote   "the push landed"   it was the other session's push
    `$?` after a pipe               "exit 0"            that was `head`'s exit
    `git show ... > /tmp/...`       "the file is empty" the redirect was refused
    `git describe`, no tag in tree  "0 since the tag"   4710
    a domain where a path belongs   "26 unroutable"     1

**Four of the five had the tool answering correctly and the reader constructing the
error.** The rule is not "distrust tools"; it is that a confirmation which reads a
summary has confirmed the summary.

This test exists because the rule is the artefact that travels. The measurement lived in
a conversation, and a conversation reaches one person.
"""
from __future__ import annotations

from pathlib import Path

_RULE = (Path(__file__).resolve().parents[1] / "rules"
         / "honesty-gate-golden-rule.md")


def test_the_failure_mode_is_listed() -> None:
    body = " ".join(_RULE.read_text(encoding="utf-8").split())
    assert "against the REPORT of a thing rather than against the thing" in body, \
        "the rule does not name the failure mode that produced five wrong claims in a day"


def test_it_carries_the_measurement_not_only_the_maxim() -> None:
    """A maxim without a measurement is advice; this kit's rules carry the number that
    made them necessary, which is why they survive being read by someone in a hurry."""
    body = " ".join(_RULE.read_text(encoding="utf-8").split())
    assert "4710" in body, "the git-describe case lost its number"
    assert "Four of the five had the tool answering correctly" in body, \
        "the rule states the maxim without the finding that the INSTRUMENT was right"


def test_it_names_what_ends_it() -> None:
    """A failure mode with no remedy trains a reader to recognise and continue."""
    body = " ".join(_RULE.read_text(encoding="utf-8").split())
    assert "re-ask the authority" in body
    assert "git rev-list --count" in body, "the remedy names no concrete instrument"

"""A review by another session fitted neither category, so it signed nothing.

`squad.signoff` knew two kinds of signer: `human/…`, which an allowlist accepts as a
person, and everything else, which is an agent. Three sessions worked this kit together
on 2026-09-22 — one maintaining the kit, one the consumer, one the plugins — and each
measured defects in the others' work: a gate that passed where its defect could not occur,
a waiver whose reason had never been measured, a status file that outlived the run that
wrote it. None of that could be signed. It reached the record as issue comments and
nothing else, which is the shape of evidence that survives exactly as long as the tracker.

`peer/` is that third kind, and it carries a requirement the other two do not: a peer
signature must say WHAT it verified. A person signing `human/paulo` is accountable by
being a person; a judge signing `judge/alignment-judge` is named by the contract it ran
against. A peer session is neither — it is another agent, with no contract binding it to
this document — so the only thing that makes its signature worth more than a rubber stamp
is the measurement written beside it.

It is NOT a human signature and does not become one. `human_signed` stays false with a
peer signer present, because the weakest signer decides and a peer is an agent. What it
buys is that the record can name a verification that really happened, instead of losing it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from squad.signoff import is_human, is_peer, read  # noqa: E402


def _section(*markers: str) -> str:
    lines = ["## Reviewer sign-off", ""]
    for marker in markers:
        lines.append(f"- [x] Judged by: someone  <!-- signed-by: {marker} -->")
    return "\n".join(lines) + "\n"


PEER = "peer/consumer-session (re-ran check_wired_hooks against this install: 8 of 17 wired .sh)"


def test_a_peer_is_recognised_and_is_not_a_human() -> None:
    assert is_peer(PEER)
    assert not is_human(PEER), (
        "a peer signature counting as a person's would launder the whole trust layer, "
        "which is the refusal `alignment_judge` already makes for judges"
    )


def test_a_peer_signature_does_not_make_a_document_human_signed() -> None:
    signoff = read(_section("human/paulo", PEER))

    assert not signoff.human_signed, "the weakest signer decides"
    assert signoff.peer_signers == [PEER]


def test_a_peer_must_say_what_it_verified() -> None:
    """The requirement that separates this from a rubber stamp.

    A person is accountable by being a person and a judge is named by the contract it
    ran against. A peer is another agent with no contract binding it to this document,
    so the measurement beside the name is the entire value of the signature.
    """
    signoff = read(_section("peer/consumer-session"))

    assert signoff.unqualified_peers == ["peer/consumer-session"]
    assert signoff.peer_signers == []


def test_a_parenthetical_of_nothing_does_not_qualify() -> None:
    for empty in ("peer/consumer-session ()", "peer/consumer-session (   )", "peer/consumer-session (ran it)"):
        signoff = read(_section(empty))
        assert signoff.unqualified_peers == [empty], empty


def test_a_peer_is_still_a_non_human_signer_to_every_existing_gate() -> None:
    """Gates that refuse anything non-human must keep refusing, unchanged.

    Policy is each gate's, as `squad/signoff.py` says of judges. This module widens the
    vocabulary; it does not decide that anyone may now sign anything.
    """
    signoff = read(_section(PEER))

    assert signoff.non_human_signers == [PEER]


def test_a_judge_may_not_sign_as_a_peer(tmp_path: Path) -> None:
    """The same refusal `human/` already carries, for the same reason.

    A judge spelling itself `peer/` would claim an independent session verified the
    document, when what happened is the judge ran its own contract over it.
    """
    sys.path.insert(0, str(_ROOT / "skills" / "plan-alignment" / "scripts"))
    from alignment_judge import sign

    brief = tmp_path / "brief.md"
    brief.write_text(_section().replace("- [x]", "- [ ]") + "- [ ] a box\n",
                     encoding="utf-8")

    with pytest.raises(ValueError, match="peer"):
        sign(brief, "peer/some-judge", "a reason long enough to pass the floor here")


def test_the_two_existing_categories_are_untouched() -> None:
    """THE CONTROL."""
    assert is_human("human/paulo")
    assert is_human("human")
    assert not is_peer("human/paulo")
    assert not is_peer("judge/alignment-judge")
    assert not is_peer("peers/not-this")

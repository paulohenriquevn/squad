"""The signature that lets an unattended loop past the alignment gate.

`AWAITING_REVIEW` is the one halt the chain cannot clear by itself, and for a
consumer running unattended it is permanent — nobody is coming. `alignment_judge.py`
is the answer to that, and it is the single thing standing between the loop and a
stop that never ends.

It shipped with **no tests**, which is the same shape as every other defect this
kit has paid for: the mechanism existed, nothing exercised it, and nothing named
it either — `plan-alignment/SKILL.md` did not mention it once, and
`skills/_kit-rules/alignment-threshold.md` still said the reviewer had to be a human. The
machinery to clear the halt was on disk and unused for days.

What the tests below pin is not that it signs. It is the three properties that
make its signature worth anything:

  - it signs under its OWN name, so `ALIGNED` by a judge and `ALIGNED` by a
    person stay different claims;
  - it refuses to re-sign, so a signed brief cannot be laundered by a second pass;
  - it can REFUSE, and refusing costs what signing costs. A judge that has never
    refused is a judge nobody has tested — and this file is where that stops being
    true of this one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import alignment_judge
from alignment_judge import DEFAULT_JUDGE, NotReady, main, refuse, sign

_REASON = ("Checked the three judgement boxes against the opportunity's evidence "
           "corner and the plan targets it names, all of which resolve on disk.")


def _brief(path: Path, *, ticked: bool = False, section: bool = True) -> Path:
    boxes = "\n".join(
        f"- [{'x' if ticked else ' '}] CHK00{i} Something a script cannot decide."
        for i in (1, 2, 3))
    body = "---\nitem: B-001\n---\n\n# Alignment brief\n\nEvidence: `records/x.md`\n"
    if section:
        body += f"\n## Reviewer sign-off\n\n{boxes}\n"
    path.write_text(body, encoding="utf-8")
    return path


# ── the signature says who signed ─────────────────────────────────────────────


def test_every_box_is_ticked_and_carries_the_judge_name(tmp_path: Path) -> None:
    brief = _brief(tmp_path / "b.md")

    out = sign(brief, DEFAULT_JUDGE, _REASON)

    assert "[ ]" not in out.split("## Reviewer sign-off", 1)[-1]
    assert out.count(f"<!-- signed-by: {DEFAULT_JUDGE} -->") == 3


def test_the_signature_is_not_passed_off_as_a_human(tmp_path: Path) -> None:
    """`score_alignment.py` reads this marker to report the weakest signer. A judge
    signing as `human/` would launder the whole trust layer in one line."""
    out = sign(_brief(tmp_path / "b.md"), DEFAULT_JUDGE, _REASON)

    assert "signed-by: judge/" in out
    assert "signed-by: human" not in out
    assert "not by a person" in out


def test_the_reason_is_written_into_the_brief(tmp_path: Path) -> None:
    """The verdict lives where the next reader meets it, not in a terminal that
    scrolled away."""
    out = sign(_brief(tmp_path / "b.md"), DEFAULT_JUDGE, _REASON)

    assert _REASON in out


def test_a_named_judge_overrides_the_default(tmp_path: Path) -> None:
    out = sign(_brief(tmp_path / "b.md"), "judge/second-opinion", _REASON)

    assert "signed-by: judge/second-opinion" in out


# ── what it must refuse to do ─────────────────────────────────────────────────


def test_it_will_not_re_sign_an_already_signed_brief(tmp_path: Path) -> None:
    """A second pass over a signed brief would let a refusal be overwritten by an
    approval with nothing recording that it happened."""
    with pytest.raises(NotReady):
        sign(_brief(tmp_path / "b.md", ticked=True), DEFAULT_JUDGE, _REASON)


def test_a_brief_with_no_signoff_section_is_not_signable(tmp_path: Path) -> None:
    """An absent gate is not a passed one — `alignment-threshold.md` says so, and
    inventing the section here would be the judge writing its own form."""
    with pytest.raises(NotReady):
        sign(_brief(tmp_path / "b.md", section=False), DEFAULT_JUDGE, _REASON)


@pytest.mark.parametrize("kwargs", [{"ticked": True}, {"section": False}])
def test_a_brief_that_is_not_ready_exits_2_not_1(tmp_path: Path, kwargs, capsys) -> None:
    """The module docstring reserves 1 for a REFUSAL and 2 for "not ready to be judged".

    Both not-ready paths used `raise SystemExit("FATAL: ...")`, which exits 1. The
    contract for exit 1 says "Do not retry a refusal" — so the chain halted the item over
    a structural problem nobody had judged, and told the author their brief was refused.
    """
    brief = _brief(tmp_path / "b.md", **kwargs)

    code = alignment_judge.main([str(brief), "--judge", DEFAULT_JUDGE,
                                 "--model", "a-model",
                                 "--verdict", "signed", "--reason", _REASON])

    assert code == 2, f"a brief that could not be judged exited {code}, the refusal code"
    assert "FATAL" in capsys.readouterr().err


def test_the_cli_refuses_a_verdict_that_does_not_name_its_model() -> None:
    """Added 2026-09-08 with `rules/review-panel.txt`.

    The panel rests on models being distinguishable — the entire argument for an
    orthogonal reviewer is that correlated models share failure modes. A signature
    that cannot name which model produced it cannot be checked for correlation with
    the author, so the CLI will not produce one.

    SystemExit(2) is argparse refusing a missing required argument, which is the
    right layer for this: it is a caller error, not a judgement.
    """
    import pytest as _pytest
    with _pytest.raises(SystemExit):
        main(["brief.md", "--verdict", "signed", "--reason", _REASON])


def test_a_reason_too_short_to_be_a_judgement_is_refused(tmp_path: Path) -> None:
    """A verdict with no reasoning is a tick, and a tick is what this exists to be
    more than."""
    brief = _brief(tmp_path / "b.md")

    assert main([str(brief), "--verdict", "signed", "--reason", "looks fine", "--model", "claude-opus-5"]) == 2
    assert "[ ]" in brief.read_text(encoding="utf-8")


# ── refusing has to work, and to cost the same ────────────────────────────────


def test_a_refusal_leaves_every_box_unticked(tmp_path: Path) -> None:
    brief = _brief(tmp_path / "b.md")

    out = refuse(brief, DEFAULT_JUDGE, _REASON)

    assert out.count("- [ ]") == 3
    assert "REFUSED" in out and _REASON in out


def test_a_refusal_exits_non_zero_and_a_signature_exits_zero(tmp_path: Path) -> None:
    """The caller routes on the exit code, so the two verdicts must be
    distinguishable without parsing prose."""
    signed = _brief(tmp_path / "signed.md")
    refused = _brief(tmp_path / "refused.md")

    assert main([str(signed), "--verdict", "signed", "--reason", _REASON, "--model", "claude-opus-5"]) == 0
    assert main([str(refused), "--verdict", "refused", "--reason", _REASON, "--model", "claude-opus-5"]) == 1


def test_a_refusal_is_written_to_disk_and_survives_the_next_run(tmp_path: Path) -> None:
    """The next run reads the refusal off the file rather than repeating the work
    that produced it."""
    brief = _brief(tmp_path / "b.md")

    main([str(brief), "--verdict", "refused", "--reason", _REASON, "--model", "claude-opus-5"])
    text = brief.read_text(encoding="utf-8")

    assert "REFUSED" in text
    assert "[ ]" in text, "a refused brief must still be unsigned"


def test_a_refused_brief_can_still_be_signed_after_the_gap_closes(tmp_path: Path) -> None:
    """A refusal is not a death sentence for the item — it names what to fix, and
    the boxes are still there to tick once it is fixed."""
    brief = _brief(tmp_path / "b.md")
    main([str(brief), "--verdict", "refused", "--reason", _REASON, "--model", "claude-opus-5"])

    assert main([str(brief), "--verdict", "signed", "--reason", _REASON, "--model", "claude-opus-5"]) == 0
    assert "[ ]" not in brief.read_text(encoding="utf-8").split("## Reviewer sign-off", 1)[-1]

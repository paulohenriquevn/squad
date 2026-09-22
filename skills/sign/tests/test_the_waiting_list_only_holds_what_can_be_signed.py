r"""Everything `--list` names must be something `check` would accept.

Routed by a consumer session, 2026-09-22, with the arithmetic done: `--list` reported
**33 documents waiting for a signature and 30 of them could not be signed at all**. The
honest number was 3.

The two predicates disagree by construction:

    waiting()   lists when  not already_signed
    already_signed  ==  unticked == 0 and bool(signers)
    check()     refuses `nothing_to_tick` when  unticked == 0 and not signers

    unticked  signers │ listed? │ check
           2    no    │  yes    │ accepts
           2    yes   │  yes    │ accepts
           0    yes   │  no     │ already_signed   ← correctly hidden
           0    no    │  YES    │ nothing_to_tick  ← listed AND unsignable

The fourth row is the defect, and it is not a rare shape: a document with no unticked
box and no `signed-by:` marker is what the briefs signed under delegation on 2026-09-10
look like. Thirty of them.

WHY A LIST THAT LIES COSTS MORE THAN A MISSING ONE. `--list` is the queue a person works
through. A queue that is ninety percent impossible teaches the reader that the tool's
output is noise, and the three real signatures are what gets lost in it — the same shape
as a gate that fires on everything and is therefore switched off.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "skills" / "sign" / "scripts"))
sys.path.insert(0, str(REPO))

from sign_document import check, load, waiting  # noqa: E402

_SIGNABLE = "# Doc\n\n## Reviewer sign-off\n\n- [ ] someone checks this\n"
_SIGNED = ("# Doc\n\n## Reviewer sign-off\n\n- [x] someone checked\n\n"
           "<!-- signed-by: human/paulo -->\n")
#: No unticked box and no marker — the shape 30 of 33 documents had.
_NEITHER = "# Doc\n\n## Reviewer sign-off\n\n- [x] someone checked\n"


def _plans(tmp_path: Path) -> Path:
    plans = tmp_path / ".squad" / "records" / "plans"
    plans.mkdir(parents=True)
    return plans


def test_a_document_with_no_box_and_no_marker_is_not_waiting(tmp_path: Path) -> None:
    """The fourth row. It was listed, and signing it was refused."""
    (_plans(tmp_path) / "neither.md").write_text(_NEITHER, encoding="utf-8")

    assert [p.name for p in waiting(tmp_path)] == []


def test_everything_listed_would_be_accepted(tmp_path: Path) -> None:
    """The invariant behind the row, stated so a third predicate cannot drift from it."""
    plans = _plans(tmp_path)
    (plans / "signable.md").write_text(_SIGNABLE, encoding="utf-8")
    (plans / "signed.md").write_text(_SIGNED, encoding="utf-8")
    (plans / "neither.md").write_text(_NEITHER, encoding="utf-8")

    for path in waiting(tmp_path):
        doc = load(path)
        refusal = check(doc, "some-reviewer")
        assert refusal is None or refusal.code not in ("nothing_to_tick", "already_signed"), (
            f"{path.name} is listed as waiting and `check` refuses it: {refusal.code}"
        )


def test_a_signable_document_is_still_listed(tmp_path: Path) -> None:
    """The guard must not empty the queue it was cleaning."""
    (_plans(tmp_path) / "signable.md").write_text(_SIGNABLE, encoding="utf-8")

    assert [p.name for p in waiting(tmp_path)] == ["signable.md"]


def test_a_signed_document_is_still_hidden(tmp_path: Path) -> None:
    (_plans(tmp_path) / "signed.md").write_text(_SIGNED, encoding="utf-8")

    assert waiting(tmp_path) == []

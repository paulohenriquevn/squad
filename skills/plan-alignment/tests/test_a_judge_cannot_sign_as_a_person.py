"""The judge wrote whatever `--judge` named, including the prefix reserved for people.

`sign()` interpolated the value verbatim into `<!-- signed-by: {judge} -->`, and
`score_alignment.signed_by_is_human` treats anything equal to `human` or starting with
`human/` as a person's signature. So

    alignment_judge.py brief.md --verdict signed --judge human/paulo --model x --reason '…'

produced a brief that every downstream reader counts as signed by Paulo — while the
note two lines below it says, in the same file, "not by a person".

A judge signature is worth less than a human one, and the whole design says so out
loud. Letting the judge spell itself as a human erases the only distinction the
alignment gate has.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "plan-alignment" / "scripts"))

from alignment_judge import sign  # noqa: E402 — post-bootstrap import


def _brief(tmp_path: Path) -> Path:
    path = tmp_path / "a-brief.md"
    path.write_text("# A brief\n\n## Reviewer sign-off\n\n- [ ] Judged by:\n",
                    encoding="utf-8")
    return path


@pytest.mark.parametrize("judge", ["human", "human/paulo", "  human/someone  "])
def test_a_judge_claiming_to_be_a_person_is_refused(tmp_path: Path, judge: str) -> None:
    with pytest.raises(ValueError, match="human"):
        sign(_brief(tmp_path), judge, "a reason", model="a-model")


def test_an_ordinary_judge_name_signs(tmp_path: Path) -> None:
    signed = sign(_brief(tmp_path), "alignment-judge", "a reason", model="a-model")

    assert "signed-by: alignment-judge" in signed
    assert "not by a person" in signed

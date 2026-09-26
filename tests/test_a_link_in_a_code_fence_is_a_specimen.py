"""A link inside a fenced block is an example of markup, not a reference.

A skill that teaches a markup language writes its syntax out. `marp-slide/SKILL.md`
shows Marp image syntax four times inside a ```markdown fence:

    ![bg right:40%](image.png)      <!-- Side image -->
    ![bg](image.png)                 <!-- Full background -->

`check_xrefs` resolved all four against the skill's own directory and reported four
broken links in a file that has none. Measured on one consumer install, 2026-09-18:
**44 of 46 findings were specimens**, all of them in the two skills that document a
markup language. The other two were real.

A gate whose output is 96% noise is a gate somebody switches off, and the silence
after that is indistinguishable from a clean repository — which is the failure mode
this whole directory exists to prevent.

`squad/markdown.py` owns the fence regex, and it owns it because five checkers here
saw only backtick fences while six also saw `~~~`: the same document scored
differently depending on which checker asked.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "mechanisms" / "gates"))

from check_xrefs import broken_markdown_links  # noqa: E402 — after the path bootstrap


def _eco(tmp_path: Path, body: str) -> Path:
    skill = tmp_path / "skills" / "teaches-markup"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_a_link_inside_a_fence_is_not_reported(tmp_path: Path) -> None:
    """The four Marp specimens, verbatim from the shape that produced the noise."""
    eco = _eco(tmp_path, "# Teaching Marp\n\n"
                         "Use this syntax:\n\n"
                         "```markdown\n"
                         "![bg right:40%](image.png)\n"
                         "![bg](image.png)\n"
                         "![w:600](image.png)\n"
                         "![bg blur:3px](image.png)\n"
                         "```\n")

    assert broken_markdown_links(eco) == [], (
        "specimens inside a fence were resolved as references")


def test_a_tilde_fence_counts_too(tmp_path: Path) -> None:
    """`~~~` is a fence. Six checkers here already knew that and five did not."""
    eco = _eco(tmp_path, "~~~markdown\n[example](nowhere.md)\n~~~\n")

    assert broken_markdown_links(eco) == [], "a `~~~` fence was read as prose"


def test_a_real_broken_link_outside_a_fence_still_fails(tmp_path: Path) -> None:
    """The point is signal, not silence. Suppressing both kinds would be worse
    than reporting both."""
    eco = _eco(tmp_path, "See [the rule](../../rules/gone.md).\n\n"
                         "```markdown\n![bg](image.png)\n```\n")

    broken = broken_markdown_links(eco)

    assert len(broken) == 1, f"expected the prose link alone, got {broken}"
    assert "gone.md" in broken[0][1]


def test_a_link_after_a_fence_is_still_prose(tmp_path: Path) -> None:
    """A fence that swallowed the rest of the file would hide every later link,
    and the symptom would be a clean report."""
    eco = _eco(tmp_path, "```markdown\n![bg](image.png)\n```\n\n"
                         "Then see [the missing one](also-gone.md).\n")

    broken = broken_markdown_links(eco)

    assert len(broken) == 1, f"a link after the fence was lost: {broken}"
    assert "also-gone.md" in broken[0][1]

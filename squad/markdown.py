"""What a markdown document says, minus what it only quotes.

WHY THIS EXISTS
===============
The fenced-code regex was redefined in eleven scripts, in TWO forms that do not mask
the same input:

    ^```[^\\n]*\\n.*?^```              five scripts — backtick fences only
    ^(```|~~~)[^\\n]*\\n.*?^\\1        six scripts — backticks OR tildes

A plan whose example block is written with `~~~` — valid CommonMark, and what an author
reaches for when the block itself contains backticks — was masked by six of the readers
and read as prose by the other five. So the same document scored differently depending
on which checker asked, and the five that could not see the fence counted every word
inside it: a `should` in a quoted example became a weak imperative, a `SELECT *` in a
sample became a smell.

One definition, the wider one. A reader that masks too little reports findings the
author did not write; a reader that masks too much is the failure this kit refuses
everywhere else, and neither form here does that.
"""
from __future__ import annotations

import re

#: A fenced block: three or more backticks OR tildes, closed by the SAME run.
#:
#: `(?P=fence)` rather than `\1` so the closing run must match the opening one — a
#: four-backtick fence wrapping a three-backtick example closes on the four, not on the
#: three inside it, which is exactly what four backticks are for.
FENCED_CODE_RE = re.compile(
    r"^(?P<fence>```+|~~~+)[^\n]*\n.*?^(?P=fence)\s*$",
    re.MULTILINE | re.DOTALL,
)

#: An inline code span. Separate from the block form because the two mask different
#: things and a caller usually wants one or the other.
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def strip_code(text: str) -> str:
    """`text` with fenced blocks blanked, PRESERVING line count.

    Blanked rather than deleted: every caller reports a line number, and deleting a
    twenty-line example moves every finding below it twenty lines up — onto a line the
    author never wrote.
    """
    return FENCED_CODE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def prose_only(text: str) -> str:
    """`text` with fenced blocks AND inline spans blanked, preserving line count."""
    return INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), strip_code(text))

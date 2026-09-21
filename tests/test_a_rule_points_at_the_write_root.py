r"""A rule must send a reader to the directory the kit actually writes.

`records-location.md` states it in one line — **"`<project>/.squad/` is the one write
root. Always, in every layout"** — and opens by saying why it matters: *"an audit trail
split across two directories is worse than none: a reader who checks the wrong one
reports absence where evidence exists."*

Measured 2026-09-21 across the cycle rules and the skills that implement them:

    rules/cycle-*.md    22 paths written `records/…`      1 written `.squad/records/…`
    the skills          0                                 35

A clean split: what EXECUTES uses the write root, what DOCUMENTS sends the reader to a
directory nothing fills. Same defect as the install message that reported migrating a
routing table to `rules/domain-routing.txt` while writing `.squad/domain-routing.txt`,
at seven times the size.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RULES = Path(__file__).resolve().parents[1] / "rules"

#: A records path NOT already rooted at the write root or a legacy root being named as
#: legacy. `(?<![\w./])` keeps `.squad/records/` and `.claude/records/` from matching.
LEGACY_RECORDS_RE = re.compile(r"(?<![\w./])records/[a-z-]+/")

#: Rules whose subject IS the history of where records used to live. They must be able
#: to write the old path in order to say it is old.
ABOUT_THE_MOVE = {"records-location.md"}


def _offending_lines(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        (n, line.strip())
        for n, line in enumerate(lines, 1)
        if LEGACY_RECORDS_RE.search(line)
    ]


@pytest.mark.parametrize(
    "rule", sorted(p.name for p in RULES.glob("cycle-*.md")),
)
def test_a_cycle_rule_names_the_write_root(rule: str) -> None:
    offenders = _offending_lines(RULES / rule)

    assert offenders == [], (
        f"{rule} points a reader at a records path outside the write root:\n"
        + "\n".join(f"  line {n}: {text[:110]}" for n, text in offenders)
        + "\n`records-location.md`: `<project>/.squad/` is the one write root."
    )


def test_the_rule_about_the_move_may_still_describe_the_old_layout() -> None:
    """The exemption is narrow and it is deliberate.

    `records-location.md` documents the retired layout and two enforcement mechanisms
    that no longer exist. Forbidding the old spelling there would forbid saying it is
    old, which is how the history that explains the current rule gets deleted.
    """
    assert "records-location.md" in ABOUT_THE_MOVE
    assert (RULES / "records-location.md").is_file()

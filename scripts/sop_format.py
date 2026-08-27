#!/usr/bin/env python3
"""The SOP format, parsed in exactly one place.

WHY THIS MODULE EXISTS
----------------------
`check_sop_structure.py` and `check_sop_run.py` both read the same document
shape — frontmatter, `##` sections, bullets that wrap across lines. They were
written with a parser each, and the two had already diverged before either
shipped: one folded continuation lines into their bullet and the other did not,
so an escalation whose `→` landed on the wrapped line was reported as having no
route. The finding was false and the document was correct.

That is the failure this repository has recorded before, in
`backlog_index.py`'s own words — *"the generator shares the item parser with the
validator: a second parser would diverge silently and the two would disagree
about what the record contains"*. The format is one piece of knowledge. It gets
one implementation.

WHAT BELONGS HERE
-----------------
Only the reading. Which findings a malformed document earns is each checker's
judgement, and folding that in would put the structural gate and the execution
gate back into one artifact — the same collapse `rules/sop-schema.md` keeps the
SOP and its run record apart to avoid.
"""
from __future__ import annotations

import re
from pathlib import Path

#: Both install layouts. A checker that sees only one is half a checker.
KB_DIRS = (".claude/knowledge-base", "knowledge-base")


def knowledge_base_dir(project_root: Path, leaf: str) -> Path | None:
    """`<project>/{.claude/,}knowledge-base/<leaf>`, whichever exists."""
    for relative in KB_DIRS:
        candidate = Path(project_root) / relative / leaf
        if candidate.is_dir():
            return candidate
    return None


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split `---`-delimited frontmatter from the body.

    Returns `({}, text)` when there is none, rather than raising: a document
    without frontmatter is a finding for the caller to name, not a crash.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fields: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields, parts[2]


def section(body: str, title: str) -> str | None:
    """The body of one `## <title>` section, or None when absent.

    None and empty-string mean different things and both callers rely on it:
    an absent `## Decisions` is fine (not every procedure branches), an empty
    one is a heading someone left behind.
    """
    match = re.search(
        rf"^##\s+{re.escape(title)}\s*$\n(.*?)(?=^##\s|\Z)",
        body, re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else None


def bullets(text: str) -> list[str]:
    """Bullets, with wrapped lines folded into the bullet they belong to.

    A prose bullet spans lines by nature, and reading only the first physical
    line loses whatever the author put after the wrap. That is not theoretical:
    it produced a false `escalation_without_route` against a correct escalation
    the first time these checkers ran on a real SOP.
    """
    entries: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if re.match(r"^\s*[-*]\s+\S", line):
            entries.append(line.strip())
        elif entries and line[:1].isspace() and line.strip():
            entries[-1] = f"{entries[-1]} {line.strip()}"
        elif not line.strip():
            continue
    return entries


def has_content(text: str | None) -> bool:
    """True when a section carries something a reader can act on.

    A heading with `_To be completed._` under it satisfies a grep and answers
    no one, so placeholders count as absent.
    """
    if text is None:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    return re.fullmatch(
        r"[_*]*(to be completed|tbd|n/?a|todo)[_*.\s]*", stripped, re.IGNORECASE
    ) is None


def excerpt(text: str, limit: int = 90) -> str:
    """One-line excerpt for a finding message."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"

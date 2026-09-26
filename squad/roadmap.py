r"""One reading of `ROADMAP.md`, for every script that parses a milestone.

WHY THIS MODULE EXISTS. `rules/cycle-acceptance.md` claimed "Three scripts parse it and
all three agree". The sentence was wrong twice: the table under it listed TWO, and the
three do not agree.

    select_next_milestone     ^###\s+M(\d+)\s+[—\-]{1,2}\s+\[([x\s\-])\]   — accepts `[-]`
    extract_acceptance_criteria  ^###\s+(M\d+)\s+[—\-]{1,2}\s+\[([ x])\]   — does not
    flip_milestone_checkbox      ^(###\s+{id}\s+[—\-]{1,2}\s+\[)([ x])     — does not

A milestone at `[-]` therefore produced two different falsehoods: `select` answered
`ROADMAP_COMPLETE` — the whole roadmap finished — and `extract` answered "Milestones
present: (none)" with an M1 sitting in the file.

WHAT THE RULE DOCUMENTED, AND WHY IT IS NOT WHAT THIS READS. The rule published a
normative block whose DoD bullets carry no checkbox and whose dependency line reads
`**Depends on:**`. Neither is what any parser has ever accepted, and every fixture in
the repository uses `- [ ]` and `**Dependencies:**`. Measured on the rule's own example:

    extract_acceptance_criteria  ->  NOT_VALIDATED, "no `- [ ]` bullets"
    select_next_milestone        ->  {"dod": [], "depends_on": []}

So somebody writing a roadmap by copying the rule produced a milestone that could never
be accepted. The parsers hold the format — they are what runs — and the rule was
corrected to match them, the same way `code-quality-allowlist.txt` was corrected when
its header documented a four-field shape `load_allowlist` never accepted.

With ONE exception, and the exception is the point: `**Depends on:**` is read too. The
bullet mismatch FAILS LOUDLY — exit 1, naming the missing shape — while the dependency
mismatch failed in SILENCE, returning `[]` for a milestone that declared a prerequisite.
A silent loss is not a format disagreement a reader can find; refusing to read the
spelling the rule taught for months would keep losing it. Both spellings are read, and
`Milestone.dependency_label` says which one the file used, so a caller can report it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    """The three checkbox states a milestone header can carry.

    `CANCELLED` is `select_next_milestone`'s meaning for `[-]`, and it was the only
    meaning anywhere in the kit: that script alone had the character in its class, and
    alone acted on it. The other two parsers could not match the line at all, so a
    cancelled milestone was not "cancelled" to them — it did not exist. `extract`
    answered "Milestones present: (none)" over a file holding one.

    A state one script can read and two cannot is worse than a state nobody supports,
    because the two that cannot each invent their own story about the silence.
    """

    OPEN = " "
    DONE = "x"
    CANCELLED = "-"

    @property
    def is_closed(self) -> bool:
        """Closed to further work — done or cancelled. NOT the same as accepted."""
        return self in (Status.DONE, Status.CANCELLED)

    @property
    def is_acceptable(self) -> bool:
        """Only an OPEN milestone can be exercised and closed by acceptance."""
        return self is Status.OPEN


#: `### M<N> — [<status>] <name>`. Em-dash is U+2014; ASCII `-` and `--` are accepted
#: because roadmaps are hand-authored and both have been written.
HEADER_RE = re.compile(
    r"^###\s+(M\d+)\s+[—\-]{1,2}\s+\[([ x\-])\]\s+(.+?)\s*$", re.MULTILINE
)

#: `**Definition of done (all must hold):**` — the parenthetical is optional.
DOD_HEADING_RE = re.compile(r"^\*\*Definition of done[^*]*:\*\*\s*$", re.MULTILINE)

#: A checkbox bullet inside the DoD block. The checkbox is REQUIRED: it is what
#: separates a promise from the prose around it, and every fixture in the kit has one.
DOD_BULLET_RE = re.compile(r"^-\s+\[([ x])\]\s+(.+?)\s*$", re.MULTILINE)

#: Both spellings of the dependency line — see the module docstring for why the one the
#: rule taught is read rather than refused.
DEPENDS_RE = re.compile(
    r"^\*\*(Dependencies|Depends on):\*\*\s*(.+?)\s*$", re.MULTILINE
)

#: The spelling this kit writes when it writes one itself.
CANONICAL_DEPENDS_LABEL = "Dependencies"

OBJECTIVE_RE = re.compile(r"^\*\*Objective:\*\*\s*(.+?)\s*$", re.MULTILINE)

#: Any other `**Bold label:**` line — marks the end of the DoD block.
NEXT_LABEL_RE = re.compile(r"^\*\*[^*]+:\*\*", re.MULTILINE)

MILESTONE_ID_RE = re.compile(r"^M\d+$")

_DEP_ID_RE = re.compile(r"\bM\d+\b")


@dataclass
class Milestone:
    """One `### M<N>` section, as every consumer of the roadmap sees it."""

    id: str
    status: Status
    name: str
    body: str
    objective: str = ""
    dod: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    #: Which spelling the file used, or None when it declared no dependency line. A
    #: caller that wants to nudge the author toward the canonical one needs to know.
    dependency_label: str | None = None

    @property
    def is_closed(self) -> bool:
        return self.status.is_closed

    @property
    def is_acceptable(self) -> bool:
        return self.status.is_acceptable


def _dod_bullets(body: str) -> tuple[bool, list[str]]:
    """`(heading_present, bullets)` — the two are separate facts.

    A milestone with no Definition-of-done heading and one whose heading has no bullets
    are different errors, and a caller reporting them alike tells an author to add a
    section they already wrote.
    """
    heading = DOD_HEADING_RE.search(body)
    if not heading:
        return False, []
    rest = body[heading.end():]
    next_label = NEXT_LABEL_RE.search(rest)
    block = rest[: next_label.start()] if next_label else rest
    return True, [text for _, text in DOD_BULLET_RE.findall(block)]


def parse(text: str) -> list[Milestone]:
    """Every milestone in the file, in document order."""
    milestones: list[Milestone] = []
    matches = list(HEADER_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end]
        objective = OBJECTIVE_RE.search(body)
        depends = DEPENDS_RE.search(body)
        _, bullets = _dod_bullets(body)
        milestones.append(Milestone(
            id=match.group(1),
            status=Status(match.group(2)),
            name=match.group(3).strip(),
            body=body,
            objective=objective.group(1).strip() if objective else "",
            dod=bullets,
            depends_on=_DEP_ID_RE.findall(depends.group(2)) if depends else [],
            dependency_label=depends.group(1) if depends else None,
        ))
    return milestones


def find(text: str, milestone_id: str) -> Milestone | None:
    """The milestone with this id, or None."""
    for milestone in parse(text):
        if milestone.id == milestone_id:
            return milestone
    return None


def has_dod_heading(body: str) -> bool:
    """Whether the block declares a Definition of done at all."""
    return _dod_bullets(body)[0]

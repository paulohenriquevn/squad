"""`BACKLOG.md` is unversioned by policy, and nothing said what to do when it is absent.

The policy is deliberate and is not in question: the registry is personal maintenance
state, not documentation of the product, so it does not travel in git
(`rules/write-exemptions.txt`, class `human`). What was never written down is the
CONSEQUENCE a checkout meets, and it is not hypothetical.

Observed in a consumer 2026-09-18: a second session registered a finding as `B-016`, an id
that registry had already spent. Measured there 2026-09-21: 93 blocks present against 195
distinct ids cited across the tree — **138 cited with no block**. Of three worktrees on
that machine, one held the file at all; the other two had none. So the colliding id was
allocated in good faith by a checkout that could not see a single spent id, and the
finding itself reached no registry — it survived because somebody happened to read a
message.

Two of that report's three bullets are closed in code: `next_backlog_id.py` computes the
next id from every id ever SPENT rather than from the file's contents, and G2 declares
what it could not search. The third asked for something code cannot be: a procedure,
written where the person who meets the empty checkout will find it.

This pins that the procedure exists and names the mechanism. A recovery procedure that
tells a reader to reconstruct the file by hand would re-introduce the defect it documents.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_RULE = _ROOT / "rules" / "records-location.md"


def test_the_rule_that_makes_the_registry_unversioned_says_what_to_do_about_it() -> None:
    text = _RULE.read_text(encoding="utf-8")

    assert "## A checkout with no registry" in text, (
        "the rule creates the situation and must carry the way out of it — a reader who "
        "meets an empty checkout looks at the policy, not at a skill they do not know to open"
    )


def test_the_procedure_names_the_allocator_rather_than_asking_for_a_rebuild() -> None:
    """The one instruction that must NOT be there is "reconstruct it by hand".

    Rebuilding the file from citations is what produces a registry that looks complete and
    is not, which is the exact state the report measured: 93 blocks, 195 ids cited.
    """
    section = _RULE.read_text(encoding="utf-8").split("## A checkout with no registry", 1)[-1]
    section = section.split("\n## ", 1)[0]

    assert "next_backlog_id.py" in section, (
        "the procedure must point at the allocator that reads git history; an id chosen "
        "from a partial file is the collision this documents"
    )
    assert "check_intake_gates.py" in section, (
        "and at the gate that declares what it could not search"
    )


def test_the_procedure_does_not_resolve_itself_by_versioning_the_registry() -> None:
    """The report's fourth bullet, which is a constraint rather than a task.

    An item that answers "the registry is invisible" with "so version it" has answered a
    different question. The policy stands; what is written is how to work under it.
    """
    section = _RULE.read_text(encoding="utf-8").split("## A checkout with no registry", 1)[-1]
    section = section.split("\n## ", 1)[0]

    assert "stays unversioned" in section or "policy stands" in section, (
        "the procedure must restate the constraint it operates under, or the next reader "
        "will read it as an argument for changing the policy"
    )


def test_the_allocator_the_procedure_names_is_there() -> None:
    """A procedure pointing at a script nobody ships is a dead pointer with instructions."""
    assert (_ROOT / "mechanisms" / "cycle" / "next_backlog_id.py").is_file()
    assert (_ROOT / "skills" / "backlog-item" / "scripts" / "check_intake_gates.py").is_file()

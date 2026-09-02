"""The scheduler script carries decisions, and nothing was reading it.

Two of the worst defects this kit has shipped were single lines in this file: a
hand-written queue that began with an item blocked in the very registry it was
pointed at, and a default repository path naming an author's home directory,
which travelled into an adopter's history and was caught by THEIR hygiene gate.
Both survived review because a `.js` file in a Python project is read by no test.

These assertions read only the lines that execute. An earlier test of mine
asserted a word was absent from a source file and failed on the comment that
explained why it was absent — the prose is where a file argues with itself, and a
test that reads it is testing the argument rather than the code.
"""
from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet" / "pipeline_workflow.js"

_BLOCK = re.compile(r"/\*.*?\*/", re.S)


def _code() -> str:
    """The script with its commentary removed."""
    body = _BLOCK.sub("", WORKFLOW.read_text(encoding="utf-8"))
    return "\n".join(line for line in body.splitlines()
                     if not line.lstrip().startswith("//"))


def test_the_queue_comes_from_the_registry_and_never_from_a_literal() -> None:
    """`select_backlog_item.py` is what knows an item is blocked. A list typed
    here reads `triaged` off disk and cannot know it is waiting on another item."""
    code = _code()

    assert "args?.queue" in code or "args?.items" in code
    assert not re.search(r"=\s*\[\s*['\"]B-\d+['\"]", code), \
        "a literal backlog id in executable code is a queue somebody typed"


def test_there_is_no_default_repository() -> None:
    """The workflow runs against whichever project invoked it. Any path baked in
    is one machine's, and this file ships to every consumer."""
    code = _code()

    assert re.search(r"REPO\s*=\s*args\?\.repo\s*$", code, re.M), \
        "REPO must come from args with no `??` fallback"
    assert "/home/" not in code and "/Users/" not in code


def test_no_stage_asks_for_a_worktree_while_the_cwd_is_a_different_repository() -> None:
    """A worktree isolates the CWD's repository. For a consumer run the CWD is the
    KIT, so the isolation guarded the wrong tree and handed each agent a cwd inside
    this repository while its instruction named an absolute path in another — a
    bare `git log` would have read this history and been reported as the item's.
    It also bought nothing: every generated stage is read-only."""
    assert "isolation" not in _code(), \
        "restore this only alongside a writing stage AND the consumer's repo"


def test_every_stage_is_labelled_and_grouped() -> None:
    """Unlabelled agents in a 21-agent run are indistinguishable in the progress
    tree, which is the only view of a pipeline while it is in flight."""
    code = _code()
    labels = re.findall(r"label:\s*`([a-z]+):\$\{item\}`", code)
    phases = re.findall(r"phase:\s*'([A-Za-z]+)'", code)

    assert labels == ["discover", "align", "plan"]
    assert phases == ["Discover", "Align", "Plan"]
    for phase in phases:
        assert f"title: '{phase}'" in code, f"{phase} has no entry in meta.phases"


def test_the_scheduler_never_decides_a_verdict_it_only_reads_one() -> None:
    """The whole premise: phases keep their own gates. A scheduler that could
    write a verdict would be a way around the gate rather than through it."""
    code = _code()

    assert "scored.verdict === 'BLOCKED'" in code or "scored?.verdict" in code, \
        "the gate result is read"
    assert not re.search(r"verdict\s*=\s*['\"]", code), \
        "and never assigned"

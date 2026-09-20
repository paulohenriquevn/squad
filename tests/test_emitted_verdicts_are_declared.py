"""A verdict a skill tells you to emit is a verdict the contract declares.

`check_orphan_verdicts.py` asks one direction — *every verdict a contract declares must
be reachable by something* — and was built after a sweep found 15 declared verdicts that
no code could emit.

**The mirror was never asked**, and it fails louder: a skill that instructs
`--verdict VISION_WRITTEN` against a contract declaring only `PRODUCT_ALIGNED`,
`AWAITING_REVIEW`, `NEEDS_REVISION` and `INVALID` does not degrade — `cycle_events.py`
REFUSES, and the phase records nothing at all.

Measured 2026-09-10, closing a live `/brainstorm-vision` session: **three of the four
cascade phases** instruct an invented verdict (`VISION_WRITTEN`, `OBJECTIVES_WRITTEN`,
`TRD_WRITTEN`). Only `brainstorm-pieces` names the contract's own. So phases 1-3 of the
one cycle a human attends emit no end event, and `cycle-maintenance.md` already names
what that costs: work left silent "is indistinguishable from one nobody touched" — the
board draws it as underived, the drift checker has nothing to compare, and a watchdog
seeing no event concludes the command never landed.

The refusal is right; the instruction is what is wrong, and nothing read it until a
person ran it.

**Where those three instructions went, 2026-09-20.** Naming the contract's verdict fixed
the refusal and left phases 1-3 each CLOSING a phase that `rules/cycle-phases.txt`
declares once — four ends against the single start `/brainstorm-vision` emits, from which
neither WIP nor lead time can be derived. The three intermediate ends are gone; the start
carries the session instead, and an open start is exactly the "somebody is working on
this" the paragraph above wanted. `/brainstorm-pieces` still closes the phase with the
contract's verdict, `AWAITING_REVIEW` included. See
`tests/test_a_cycle_a_skill_ends_is_a_cycle_a_skill_starts.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_emitted_verdicts import scan  # noqa: E402 — post-bootstrap import


def test_every_instructed_verdict_is_declared_by_its_cycle() -> None:
    findings = scan(_REPO)
    assert not findings, "\n".join(
        f"{f['file']}:{f['line']}  --verdict {f['verdict']}  "
        f"not declared by cycle-{f['cycle']}.md"
        for f in findings
    )


def _skill(tmp_path: Path, body: str) -> Path:
    d = tmp_path / "skills" / "x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body)
    rules = tmp_path / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "cycle-demo.md").write_text(
        "## Verdicts\n\n| `GOOD` | fine |\n| `BAD_NEWS` | not fine |\n"
    )
    return tmp_path


def test_a_declared_verdict_passes(tmp_path: Path) -> None:
    root = _skill(tmp_path, "run `--cycle demo --slug x --verdict GOOD`\n")
    assert scan(root) == []


def test_an_undeclared_verdict_is_a_finding(tmp_path: Path) -> None:
    root = _skill(tmp_path, "run `--cycle demo --slug x --verdict INVENTED`\n")
    found = scan(root)
    assert len(found) == 1 and found[0]["verdict"] == "INVENTED"


def test_a_placeholder_alternation_checks_every_branch(tmp_path: Path) -> None:
    root = _skill(tmp_path, "--cycle demo --slug x --verdict {GOOD|INVENTED}\n")
    found = scan(root)
    assert [f["verdict"] for f in found] == ["INVENTED"]


def test_an_unknown_cycle_is_not_silently_passed(tmp_path: Path) -> None:
    root = _skill(tmp_path, "--cycle nosuch --slug x --verdict GOOD\n")
    found = scan(root)
    assert len(found) == 1 and found[0]["cycle"] == "nosuch"

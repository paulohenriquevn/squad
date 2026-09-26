"""The shallow alignment depth must be able to pass the gate it is scored against.

THE WALL, MEASURED
------------------
`classify_alignment_depth.py` returns `LOCAL` for a small item and names what it
removes in its own output: *"DROPPED: the prose sections and the walkthrough HTML."*
`score_alignment.py` then scores the resulting brief against all seventeen criteria,
five of which grade exactly those dropped sections.

Measured 2026-09-18 on a real item (`B-001` in a consumer registry), by running both
halves of the kit against one brief:

    classify_alignment_depth.py . B-001   ->  LOCAL
    score_alignment.py <brief>            ->  22/34 = 64.7%   (floor: 90%)

Seven criteria were below maximum. Five were the dropped sections at 0/2 — `flows`,
`scenario_classes`, `system_diagram`, `interaction_model`, `interactive_artefact` — and
two were ordinary authoring gaps at 1/2. Closing BOTH authoring gaps reaches **24/34 =
70.6%**, which is **19.4 percentage points below the floor**.

So an author who follows the classifier writes a brief that cannot pass, and the only
way through is the FULL brief the classifier measured as waste: `cycle-plan.md` records
93 items and 2,740 KB of briefs, each 40-50 KB, "longer than the code it described",
signed by a person zero times.

WHY THIS IS NOT FIXED BY LOWERING THE FLOOR
-------------------------------------------
`skills/_kit-rules/alignment-threshold.md` argues the 90% figure and states there is no
`--skip` and no dismissing ADR on the cap, deliberately. The floor is not the defect.
The defect is scoring a document against criteria its own depth removed — the maximum
must come from the criteria IN FORCE, not from a constant.

WHY THE DEPTH IS NOT READ FROM THE BRIEF
----------------------------------------
A brief that declared its own depth would let an author reach the floor by typing
`LOCAL`, which is the "reaching 90% by rewording" anti-pattern the same rule names. The
depth is derived by the classifier from the ITEM, and passed in.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCORER = Path(__file__).resolve().parents[1] / "skills/plan-alignment/scripts/score_alignment.py"

#: A brief complete by the LOCAL contract: every kept criterion satisfied, every dropped
#: one absent. Deliberately carries no flows, no diagrams and no walkthrough.
LOCAL_BRIEF = """# Alignment: B-001 — the streamed document is proved by execution

## Problem

`tests/unit/shell.test.ts:29` asserts `expect(entry).toContain('<head>')` over the
generated source string. Measured 2026-09-18: that literal is present whether or not the
worker forwards the shell at runtime, so the assertion cannot distinguish the two.

## Functional Requirements

- FR-001: The suite shall execute the generated entry against a real `Request` and observe
  the `Response` body, rather than asserting over the entry's source text.
- FR-002: The suite shall assert the renderer was invoked once before asserting the body.

## Non-Functional Requirements

- NFR-001: The file completes in < 30 s on this machine.
- NFR-002: The file stays at < 500 rows.

## Acceptance Criteria

- AC-001 (FR-001): `npm exec vitest run tests/unit/shell.test.ts` gives exit 0.
- AC-002 (FR-002): with the branch unreached, `npm exec vitest run tests/unit/shell.test.ts`
  gives exit 1 naming the invocation count.
- AC-003 (NFR-001): the AC-001 run reports a duration < 30 s.
- AC-004 (NFR-002): `grep -c "" tests/unit/shell.test.ts` gives a count < 500.

## Dependencies

none.

## Out of scope

- The real renderer, which is generated source and belongs to an integration test.
- The other five adapters, which are a separate item.

## Questions answered

### Session 2026-09-18

- Q: Is the production defect still open? -> A: No, closed 2026-08-21 in code.
- Q: Does a test already execute the entry? -> A: Yes, but not on the streaming path.

## Demonstration

Run `npm exec vitest run tests/unit/shell.test.ts` and read the passing cases; then run
the canary and watch it give exit 1 before it is restored.

## Reviewer sign-off

- [ ] CHK001 The stated problem is the one we have. [Judgement]
"""


def _score(tmp_path: Path, brief: str, *extra: str) -> dict:
    path = tmp_path / "b-001-alignment.md"
    path.write_text(brief, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCORER), str(path), "--json", "--machine-only", *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    start = proc.stdout.index("{")
    return json.loads(proc.stdout[start:])


def test_a_complete_local_brief_reaches_the_floor(tmp_path: Path) -> None:
    """The regression. Without --depth this brief scores ~65% and cannot be built."""
    report = _score(tmp_path, LOCAL_BRIEF, "--depth", "LOCAL")
    assert report["machine_ratio"] >= report["threshold"], (
        f"a LOCAL brief complete by its own contract scored "
        f"{report['earned']}/{report['maximum']} = {report['machine_ratio']:.1%}, "
        f"below the {report['threshold']:.0%} floor. The criteria it is missing are the "
        f"ones LOCAL removes, so the shallow path cannot be used at all."
    )


def test_the_maximum_shrinks_with_the_depth(tmp_path: Path) -> None:
    """Scored out of the criteria in force, never out of a constant.

    Awarding the dropped criteria full marks would reach the floor too, and would be a
    lie: the brief would report 34/34 for a document that answered twelve questions.
    """
    full = _score(tmp_path, LOCAL_BRIEF)
    local = _score(tmp_path, LOCAL_BRIEF, "--depth", "LOCAL")
    assert local["maximum"] < full["maximum"], (
        "the LOCAL maximum must be smaller than the FULL one — five criteria are not "
        "asked, so they are not part of the total either"
    )
    assert local["earned"] <= full["earned"] + 0, (
        "LOCAL must not EARN more than FULL on the same text: the dropped criteria are "
        "excluded, not awarded"
    )


def test_declaring_the_depth_inside_the_brief_does_not_lower_the_bar(tmp_path: Path) -> None:
    """The escape hatch this fix must not open.

    An author who can reach the floor by typing `Depth: LOCAL` into the document has
    found the "reaching 90% by rewording" path `alignment-threshold.md` names. The depth
    is derived from the ITEM by the classifier and passed in; the brief's own prose is
    text like any other.
    """
    declared = LOCAL_BRIEF.replace(
        "## Problem", "**Depth: LOCAL**\n\n## Problem", 1
    )
    report = _score(tmp_path, declared)
    assert report["machine_ratio"] < report["threshold"], (
        "a brief that merely SAYS it is LOCAL reached the floor without the caller "
        "deriving the depth — that is a document grading itself"
    )


def test_an_incomplete_local_brief_still_fails(tmp_path: Path) -> None:
    """The fix must not become a way to pass by declaring a depth.

    Removing a KEPT criterion — the acceptance criteria — must still fail at LOCAL.
    """
    gutted = LOCAL_BRIEF.split("## Acceptance Criteria")[0] + "## Dependencies\n\nnone.\n"
    report = _score(tmp_path, gutted, "--depth", "LOCAL")
    assert report["machine_ratio"] < report["threshold"], (
        "a LOCAL brief missing its acceptance criteria passed — LOCAL drops the prose "
        "sections, never the criteria the gates read"
    )

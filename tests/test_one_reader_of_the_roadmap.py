r"""Everything that reads `ROADMAP.md` reads it the same way.

`rules/cycle-acceptance.md` claimed "Three scripts parse it and all three agree". The
table under that sentence listed TWO, and the three did not agree — they disagreed about
the checkbox, which is the field the whole cycle turns on:

    select_next_milestone        \[([x\s\-])\]   — accepts `[-]`
    extract_acceptance_criteria  \[([ x])\]      — does not
    flip_milestone_checkbox      \[([ x])\]      — does not

`[-]` means CANCELLED, and `select_next_milestone` is the only place in the kit that
has ever said so. To the other two it was not a cancelled milestone — it was no
milestone: `extract` answered "Milestones present: (none)" over a file holding one, and
the flip script skipped it with a WARN and exit 0.

A state one script can read and two cannot is worse than a state nobody supports,
because the two that cannot each invent their own story about the silence.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ACCEPTANCE = REPO / "skills" / "acceptance" / "scripts"
IDEA = REPO / "skills" / "idea-to-release" / "scripts"
RELEASE = REPO / "skills" / "release" / "scripts"

ROADMAP = (
    "# Roadmap\n\n"
    "### M0 — [x] Base\n\n**Objective:** base.\n\n"
    "**Definition of done:**\n\n- [x] base works\n\n**Dependencies:** none.\n\n---\n\n"
    "### M1 — [ ] Streaming\n\n**Objective:** sse.\n\n"
    "**Depends on:** M0\n\n"
    "**Definition of done (all must hold):**\n\n"
    "- [ ] tokens arrive incrementally\n- [ ] a dropped connection resumes\n\n---\n\n"
    "### M2 — [-] Quotas\n\n**Objective:** quota.\n\n"
    "**Definition of done:**\n\n- [ ] quotas enforced\n\n---\n"
)


def _roadmap(tmp_path: Path, text: str = ROADMAP) -> Path:
    path = tmp_path / "ROADMAP.md"
    path.write_text(text, encoding="utf-8")
    return path


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, check=False)


def test_every_roadmap_parser_imports_the_shared_reader() -> None:
    """A fourth private regex is how the divergence comes back."""
    readers = [
        ACCEPTANCE / "extract_acceptance_criteria.py",
        IDEA / "select_next_milestone.py",
        RELEASE / "flip_milestone_checkbox.py",
    ]
    private = [
        p.name for p in readers
        if "from squad.roadmap import" not in p.read_text(encoding="utf-8")
        and "from squad import roadmap" not in p.read_text(encoding="utf-8")
    ]

    assert private == [], f"{private} parse the roadmap themselves"


def test_an_open_milestone_is_extracted(tmp_path: Path) -> None:
    result = _run(ACCEPTANCE / "extract_acceptance_criteria.py",
                  "--roadmap", str(_roadmap(tmp_path)), "--milestone", "M1")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "tokens arrive incrementally" in result.stdout


def test_a_cancelled_milestone_is_refused_by_its_own_name(tmp_path: Path) -> None:
    """Not "(none)". A cancelled milestone is a milestone, and saying it is absent
    sends a reader looking for a missing section that is sitting in the file."""
    result = _run(ACCEPTANCE / "extract_acceptance_criteria.py",
                  "--roadmap", str(_roadmap(tmp_path)), "--milestone", "M2")

    assert result.returncode == 1, result.stdout
    output = result.stdout + result.stderr
    assert "cancelled" in output.lower(), output
    assert "(none)" not in output


def test_the_selector_still_skips_a_cancelled_milestone(tmp_path: Path) -> None:
    """The one behaviour that was already right, held while the reader moved."""
    result = _run(IDEA / "select_next_milestone.py",
                  "--roadmap", str(_roadmap(tmp_path)))

    payload = json.loads(result.stdout)
    assert payload.get("milestone_id") == "M1", payload


def test_the_dependency_spelling_the_rule_taught_is_not_lost(tmp_path: Path) -> None:
    """`**Depends on:**` failed SILENTLY, which is why it is read rather than refused.

    The bullet-shape mismatch exits 1 and names what is missing; a reader finds it. A
    dependency returning `[]` looks exactly like a milestone that declared none, so a
    prerequisite nobody delivered reads as no prerequisite at all.
    """
    result = _run(IDEA / "select_next_milestone.py",
                  "--roadmap", str(_roadmap(tmp_path)))

    assert json.loads(result.stdout).get("depends_on") == ["M0"], result.stdout


def test_the_flip_refuses_a_cancelled_milestone_out_loud(tmp_path: Path) -> None:
    """It used to WARN "not found" and exit 0 — a flip that did not happen, reported
    as success to a caller running `flip || exit 1`."""
    roadmap = _roadmap(tmp_path)
    result = _run(RELEASE / "flip_milestone_checkbox.py",
                  "--roadmap", str(roadmap), "--milestone-id", "M2",
                  "--version", "1.0.0", "--verdict", "ACCEPTED")

    assert result.returncode != 0, result.stdout + result.stderr
    assert "### M2 — [-] Quotas" in roadmap.read_text(encoding="utf-8")


def test_the_rule_documents_the_format_the_parsers_accept() -> None:
    """The normative block must be one a roadmap can be written from.

    Copied from the rule verbatim, its example produced NOT_VALIDATED from the
    extractor and an empty DoD from the selector.
    """
    rule = (REPO / "rules" / "cycle-acceptance.md").read_text(encoding="utf-8")
    start = rule.index("**Definition of done (all must hold):**")
    block = rule[start:start + 400]

    assert "- [ ]" in block, (
        "the rule's own example has no checkbox, and every parser requires one"
    )

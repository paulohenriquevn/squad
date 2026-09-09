"""A citation may name a section that does not exist, and nothing looked.

Checks 3 and 7 answer "does the FILE exist". A reader is not sent to a file, they
are sent to a section of one, and until 2026-08-31 nothing compared the two.
Measured by hand that day: **14 dead anchors across 10 files**, in three classes.

The third class is why the check earns its place. Three skills opened their
halt-loop step with *"Read `loop-engine-convention.md § How to invoke
ralph-loop:ralph-loop safely` BEFORE this step"* — and that section had never been
written. Each skill then restated the shell-evaluation fact in its own words, so
one piece of knowledge lived in three copies while its named home was empty.

A citation that survives the rename of what it points at is worse than a missing
one: the reader goes looking, finds a document that plainly exists, and concludes
the section was deleted on purpose.

The negative cases below matter as much. Two of the three false-positive classes
this checker had to learn about came from the by-hand sweep that found the
defects: a section name wrapped across two lines, and a basename that resolves to
two different files.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "mechanisms" / "gates" / "check_xrefs.py"


def _eco(root: Path, target_body: str, citing_body: str,
         target_name: str = "architecture.md") -> Path:
    eco = root / ".claude"
    (eco / "skills" / "review").mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "scripts").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)
    (eco / "rules" / target_name).write_text(target_body, encoding="utf-8")
    (eco / "skills" / "review" / "SKILL.md").write_text(citing_body, encoding="utf-8")
    return eco


def _anchor_findings(eco: Path) -> list[dict]:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True, text=True, check=False)
    payload = json.loads(result.stdout)
    return [f for f in payload["findings"] if f["check"] == "cited_section_does_not_exist"]


def test_a_section_that_does_not_exist_is_reported(tmp_path: Path) -> None:
    """The measured case: `§ Module hygiene` in four files, against a heading that
    has read `§ 3 — Module cohesion` for as long as git remembers."""
    eco = _eco(tmp_path,
               "# Architecture\n\n## § 3 — Module cohesion\n\nText.\n",
               "# Review\n\nPer `architecture.md § Module hygiene`:\n\n- a rule\n")

    findings = _anchor_findings(eco)

    assert len(findings) == 1
    assert "Module hygiene" in findings[0]["message"]


def test_a_section_that_exists_is_not_reported(tmp_path: Path) -> None:
    eco = _eco(tmp_path,
               "# Architecture\n\n## § 3 — Module cohesion\n\nText.\n",
               "# Review\n\nPer `architecture.md § 3 — Module cohesion`:\n\n- a rule\n")

    assert _anchor_findings(eco) == []


def test_a_partial_but_unambiguous_name_matches(tmp_path: Path) -> None:
    """`§ Module cohesion` for `§ 3 — Module cohesion` is a correct citation written
    short. Reporting it would train readers to write the number they do not need."""
    eco = _eco(tmp_path,
               "# Architecture\n\n## § 3 — Module cohesion\n\nText.\n",
               "# Review\n\nPer `architecture.md § Module cohesion`:\n\n- a rule\n")

    assert _anchor_findings(eco) == []


def test_a_section_name_wrapped_across_lines_is_not_a_finding(tmp_path: Path) -> None:
    """Prose wraps. The by-hand sweep reported three of these before it learned to
    normalise whitespace, and every one of them was correct work."""
    eco = _eco(tmp_path,
               "# Backlog\n\n## The index that opens the registry\n\nText.\n",
               "# Review\n\nSee `backlog.md § The index that opens the\nregistry`.\n",
               target_name="backlog.md")

    assert _anchor_findings(eco) == []


def test_a_template_placeholder_is_not_a_section(tmp_path: Path) -> None:
    eco = _eco(tmp_path,
               "# Architecture\n\n## § 1 — Layers\n\nText.\n",
               "# Review\n\nRead `architecture.md § sections related to {DOMAIN}`.\n")

    assert _anchor_findings(eco) == []


def test_a_range_of_two_sections_is_not_a_section(tmp_path: Path) -> None:
    """`§ 1–2` cites two headings that both exist. It is not one name."""
    eco = _eco(tmp_path,
               "# Golden rule\n\n## § 1 — A\n\n## § 2 — B\n",
               "# Review\n\nPer `golden.md § 1–2 (LOCKED)`.\n",
               target_name="golden.md")

    assert _anchor_findings(eco) == []


def test_a_basename_beside_the_citing_file_wins(tmp_path: Path) -> None:
    """Locality resolves what a bare basename means. A citation next to the file it
    names is not ambiguous, whatever else in the tree shares the name."""
    eco = _eco(tmp_path,
               "# Architecture\n\n## § 1 — Layers\n\nText.\n",
               "# Review\n\nPer `prompt.md § Invariants`.\n")
    (eco / "skills" / "review" / "prompt.md").write_text(
        "# Prompt\n\n## Invariants\n", encoding="utf-8")
    (eco / "skills" / "other").mkdir(parents=True, exist_ok=True)
    (eco / "skills" / "other" / "prompt.md").write_text(
        "# Prompt\n\n## Something else\n", encoding="utf-8")

    assert _anchor_findings(eco) == []


def test_an_ambiguous_basename_is_answered_with_silence(tmp_path: Path) -> None:
    """Two copies, neither beside the citing document — the real case, measured:
    `plan-improve/SKILL.md` cites `improvement-prompt.md`, and copies live under
    `plan-improve/prompts/` and `discover-improve/prompts/`. Guessing the first
    match reported a section as missing from a file that never contained it, and a
    finding about the wrong document reads exactly like a real one."""
    eco = _eco(tmp_path,
               "# Architecture\n\n## § 1 — Layers\n\nText.\n",
               "# Review\n\nPer `prompt.md § Invariants`.\n")
    for where in ("skills/review/prompts", "skills/other/prompts"):
        directory = eco / where
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "prompt.md").write_text("# Prompt\n\n## Something else\n",
                                             encoding="utf-8")

    assert _anchor_findings(eco) == []


def test_the_kit_itself_has_no_dead_anchors() -> None:
    """The regression. It failed with 14 findings before the anchors were fixed."""
    assert _anchor_findings(_REPO) == []

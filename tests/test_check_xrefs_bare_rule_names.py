"""A rule cited by bare name reads as local, and the validator could not see it.

`rules/README.md` is the document whose entire job is to say where a rule lives. Its
inventory tables cite by bare name — `code-quality-thresholds.txt`, not
`rules/code-quality-thresholds.txt` — because the reader is already in the directory.
That convention is exactly the form Check 7 cannot match: `RULES_REF_RE` requires the
literal `rules/` prefix, so every cell of every table in that file was unvalidated.

Measured 2026-09-07: four names in those tables did not resolve to `rules/`. Three had
moved to `skills/_kit-rules/` on 2026-09-01 and the tables did not follow
(`discover-plan-golden-rule.md`, `review-model-routing.txt`, `audit-trail-rotation.md`);
one, `dogfood-golden-rule.md`, existed nowhere in the repository. `check_xrefs.py`
reported PASS on all four, for two independent reasons:

  Check 7  needs the `rules/` prefix — a bare name in a table cell has none.
  Check 3  resolves a bare leaf with `rglob` across the whole tree, so a file that
           MOVED OUT of `rules/` still resolves — and it only reads the
           `## Cross-references` section of `cycle-*.md`, never `rules/README.md`.

The second arm is the subtler one and it is what this guards: a name that resolves
somewhere else in the kit is worse than one that resolves nowhere, because the reader
is sent to a directory the file left.

WHY THE SWEEP IS NARROW
-----------------------
Eleven of the fifteen bare names in `rules/*.md` are legitimate and must stay silent:
`product-vision.md` and its three siblings are artifacts the consumer produces,
`ralph-loop.local.md` belongs to an external plugin, and `discover-blueprint-golden-rule.md`
is named by `cycle-judge-codex.md` in a sentence that says it never existed here. None
of them exist in the kit at all, so the "lives elsewhere" arm cannot reach them.

`alignment-threshold.md` is the case that proves the escape hatch is needed rather than
lenient: `cycle-brainstorm.md` and `cycle-plan.md` both cite it bare AND give
`skills/_kit-rules/alignment-threshold.md` in the same document. A document that has
already told the reader where the file is has not misdirected anyone.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "mechanisms" / "gates" / "check_xrefs.py"
_CHECK = "bare_rule_name_resolves"


def _make_ecosystem(root: Path) -> Path:
    eco = root / ".claude"
    (eco / "skills" / "implement").mkdir(parents=True)
    (eco / "skills" / "_kit-rules").mkdir(parents=True)
    (eco / "rules").mkdir(parents=True)
    (eco / "hooks").mkdir(parents=True)
    (eco / "skills" / "implement" / "SKILL.md").write_text(
        "# Skill\n\n## Cycle contract\n\nSee `rules/cycle-implement.md`.\n", encoding="utf-8"
    )
    (eco / "rules" / "cycle-implement.md").write_text(
        "# Cycle: IMPLEMENT\n\n## Cross-references\n\n- `skills/implement/SKILL.md`\n",
        encoding="utf-8",
    )
    (eco / "rules" / "git-safety.md").write_text("# Git safety\n", encoding="utf-8")
    return eco


def _run(eco: Path) -> tuple[int, dict]:
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw": result.stdout, "stderr": result.stderr}
    return result.returncode, data


def _findings(data: dict) -> list[dict]:
    return [f for f in data.get("findings", []) if f.get("check") == _CHECK]


def test_a_bare_name_that_moved_out_of_rules_is_caught(tmp_path: Path) -> None:
    """The measured defect: the file exists, in another directory, and the cite is bare."""
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "_kit-rules" / "audit-trail-rotation.md").write_text("# x\n", encoding="utf-8")
    (eco / "rules" / "README.md").write_text(
        "# Rules\n\n| File | Purpose |\n|---|---|\n"
        "| `audit-trail-rotation.md` | when to archive |\n",
        encoding="utf-8",
    )
    code, data = _run(eco)
    found = _findings(data)
    assert [f["missing_rule"] for f in found] == ["audit-trail-rotation.md"]
    assert "skills/_kit-rules" in found[0]["message"]
    assert code == 1


def test_a_document_that_also_gives_the_real_path_is_silent(tmp_path: Path) -> None:
    """`alignment-threshold.md` — cited bare, and located in the same document."""
    eco = _make_ecosystem(tmp_path)
    (eco / "skills" / "_kit-rules" / "alignment-threshold.md").write_text("# x\n", encoding="utf-8")
    (eco / "rules" / "cycle-plan.md").write_text(
        "# Cycle: PLAN\n\n## Purpose\n\nSee `skills/_kit-rules/alignment-threshold.md`.\n"
        "Later, in passing: `alignment-threshold.md` states the same floor.\n",
        encoding="utf-8",
    )
    _, data = _run(eco)
    assert _findings(data) == []


def test_a_bare_name_that_exists_nowhere_stays_silent_outside_the_inventory(tmp_path: Path) -> None:
    """A consumer artifact or an external plugin's file is not the kit's to resolve."""
    eco = _make_ecosystem(tmp_path)
    (eco / "rules" / "cycle-brainstorm.md").write_text(
        "# Cycle: BRAINSTORM\n\n| 1 | `product-vision.md` | names a user |\n"
        "State lives in `ralph-loop.local.md`.\n",
        encoding="utf-8",
    )
    _, data = _run(eco)
    assert _findings(data) == []


def test_the_inventory_may_not_name_a_file_that_exists_nowhere(tmp_path: Path) -> None:
    """`rules/README.md` claims its rows are in `rules/`. `dogfood-golden-rule.md` was not."""
    eco = _make_ecosystem(tmp_path)
    (eco / "rules" / "README.md").write_text(
        "# Rules\n\n| File | Purpose |\n|---|---|\n"
        "| `dogfood-golden-rule.md` | anchor scenario |\n"
        "| `git-safety.md` | forbidden git commands |\n",
        encoding="utf-8",
    )
    code, data = _run(eco)
    assert [f["missing_rule"] for f in _findings(data)] == ["dogfood-golden-rule.md"]
    assert code == 1


def test_a_consumers_own_rule_warns_instead_of_failing_the_kits_install(tmp_path: Path) -> None:
    """Check 7 was measured breaking installs this way; Check 11 inherits the guard.

    A repository that adopted the kit may add rules of its own, and one of them citing
    a file the kit does not ship is worth telling them — it is not a reason to call the
    install broken. Same FAIL/WARN split as Check 8, keyed on `.kit-manifest.txt`.
    """
    eco = _make_ecosystem(tmp_path)
    (eco / ".kit-manifest.txt").write_text("rules/cycle-implement.md\n", encoding="utf-8")
    (eco / "skills" / "_kit-rules" / "audit-trail-rotation.md").write_text("# x\n", encoding="utf-8")
    (eco / "rules" / "house-style.md").write_text(
        "# Our own rule\n\nSee `audit-trail-rotation.md`.\n", encoding="utf-8")
    code, data = _run(eco)
    found = _findings(data)
    assert [f["severity"] for f in found] == ["WARN"]
    assert found[0]["owner"] == "project"
    assert code == 0


def test_the_live_repository_has_no_unresolved_bare_rule_name() -> None:
    """The regression itself, on the tree that ships."""
    _, data = _run(_REPO)
    assert _findings(data) == [], [f["message"] for f in _findings(data)]

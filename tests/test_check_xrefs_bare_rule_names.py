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
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--ecosystem-dir", str(eco), "--json"],
        capture_output=True, text=True,
     check=False)
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


# ------------------------------------------------------------------ #83


def test_a_consumer_file_colliding_with_a_slot_name_does_not_fail_a_kit_gate(tmp_path) -> None:
    """#83. The check asks "does any file anywhere have this name?" and treated a hit as
    proof the citation pointed somewhere wrong. A name collision is not a misdirection.

    Measured on a consumer install: the kit's `cycle-design.md` cites `trust.md` meaning
    drawing D2; the consumer had a repository called `*-trust`; and the kit's own
    `scaffold_specialists.py` wrote `agents/trust.md` for it. The gate FAILED with
    `owner: kit`, on a name the consumer had every right to choose, in a file the
    consumer could not edit.
    """
    eco = tmp_path
    (eco / "rules").mkdir()
    (eco / "agents").mkdir()
    (eco / "skills").mkdir()
    (eco / "rules" / "cycle-design.md").write_text(
        "# Design\n\n## Chain\n\n```\n/design\n```\n\n| D2 | `trust.md` | flowchart | yes |\n",
        encoding="utf-8")
    # the kit shipped the rule; it did NOT ship the consumer's specialist
    (eco / ".kit-manifest.txt").write_text(
        "# Written by scripts/install.sh\nrules/cycle-design.md\n", encoding="utf-8")
    (eco / "agents" / "trust.md").write_text("# trust specialist\n", encoding="utf-8")

    _code, data = _run(eco)
    findings = _findings(data)

    assert findings, "the collision should still be REPORTED"
    assert findings[0]["severity"] == "WARN", findings[0]
    assert findings[0]["owner"] == "project", (
        "a consumer's filename must not be attributed to the kit — the consumer "
        "cannot edit the file it would have to change")


def test_a_kit_shipped_collision_still_fails(tmp_path) -> None:
    """The check must keep firing where it was right: a kit rule citing a bare name
    that resolves to another KIT file is a genuinely misdirected citation."""
    eco = tmp_path
    (eco / "rules").mkdir()
    (eco / "agents").mkdir()
    (eco / "skills").mkdir()
    (eco / "rules" / "cycle-x.md").write_text(
        "# X\n\n## Chain\n\n```\n/x\n```\n\nsee `moved.md` for the contract\n",
        encoding="utf-8")
    (eco / "agents" / "moved.md").write_text("# moved\n", encoding="utf-8")
    (eco / ".kit-manifest.txt").write_text(
        "rules/cycle-x.md\nagents/moved.md\n", encoding="utf-8")

    _code, data = _run(eco)
    findings = _findings(data)

    assert findings and findings[0]["severity"] == "FAIL", findings


def test_the_kits_own_checkout_still_escalates(tmp_path) -> None:
    """With no manifest the whole tree is the kit's, and a collision cannot be a
    consumer's. Treating None as "nothing is ours" would silence the check entirely."""
    eco = tmp_path
    (eco / "rules").mkdir()
    (eco / "agents").mkdir()
    (eco / "skills").mkdir()
    (eco / "rules" / "cycle-x.md").write_text(
        "# X\n\n## Chain\n\n```\n/x\n```\n\nsee `moved.md`\n", encoding="utf-8")
    (eco / "agents" / "moved.md").write_text("# moved\n", encoding="utf-8")

    _code, data = _run(eco)
    findings = _findings(data)

    assert findings and findings[0]["severity"] == "FAIL"


def test_the_design_slots_name_their_directory() -> None:
    """The other half of the fix, and the one that makes the citation TRUE: a bare
    `trust.md` does not say where the drawing lives, and the resolver already skips a
    citation whose document spells a containing path."""
    repo = Path(__file__).resolve().parents[1]
    body = (repo / "rules" / "cycle-design.md").read_text(encoding="utf-8")

    for slot in ("states", "trust", "sequence", "durability", "system-map", "sign-off"):
        assert f"`design/{slot}.md`" in body, slot
        assert f"| `{slot}.md` |" not in body, f"{slot} is still cited bare"

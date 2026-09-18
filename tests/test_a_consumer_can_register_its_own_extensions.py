"""A consumer that extends the kit had nowhere to record the extension.

The gates require every skill, cycle and verdict to be registered in an index. The only
indexes were the kit's own, and `install.sh` overwrites all three — so a project with
skills, a cycle or verdicts of its own could register them, watch its gates go green, and
have every edit reverted by the next update.

Measured on one consumer, 2026-09-18: 13 skills of its own, one cycle, four verdicts.
Registering them by hand took the ecosystem from 9 failing checks to 1, and the next
`install.sh --merge` restored all three failures verbatim.

`rules/verdict-bands.txt` carries the reasoning in its own source — *"it classifies every
verdict into a band, the consumer never edits it"* — and both halves of that are true at
once, which is the shape of the defect. A consumer must not edit the kit's classification
of the kit's verdicts; a consumer with its own cycle must classify its own. One file
could not say both.

So each index gains a `.local` sibling the installer never touches, on the pattern
`settings.local.json` already set. Three properties this file holds:

  * the kit's file stays authoritative for the kit's own entries — a `.local` entry for a
    name the kit already classifies is a FINDING, not an override, because silently
    overriding is the drift the single-file design was protecting
  * an absent `.local` changes nothing, so every consumer that does not extend the kit
    sees exactly today's behaviour
  * the reports say which file an entry came from, or a reader debugging one has two
    files to search and no hint which
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_GATES = _ROOT / "mechanisms" / "gates"


def _run(gate: str, root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_GATES / gate), "--root", str(root), *extra],
                          capture_output=True, text=True, timeout=300, check=False)


# --------------------------------------------------------------------------- verdicts

_BANDS = ("ACCEPTED                      | clean      | the kit's own\n"
          "PASS                          | clean      | the kit's own\n")


def _verdict_tree(tmp_path: Path, *, local: str | None = None) -> Path:
    rules = tmp_path / "rules"
    rules.mkdir(parents=True)
    (rules / "verdict-bands.txt").write_text(_BANDS, encoding="utf-8")
    (rules / "cycle-demo.md").write_text(
        "# Cycle: DEMO\n\n## Verdicts\n\n- `ACCEPTED`\n- `PROJECT_SPECIFIC`\n",
        encoding="utf-8")
    if local is not None:
        (rules / "verdict-bands.local.txt").write_text(local, encoding="utf-8")
    return tmp_path


def test_a_verdict_the_consumer_declares_can_be_banded_locally(tmp_path: Path) -> None:
    """The case the whole issue is about."""
    root = _verdict_tree(tmp_path, local=(
        "PROJECT_SPECIFIC              | clean      | this project's own cycle\n"))

    done = _run("check_verdict_bands.py", root)

    assert "PROJECT_SPECIFIC" not in done.stdout, (
        "a locally-banded verdict was still reported unclassified:\n" + done.stdout)


def test_without_the_local_file_the_verdict_is_still_unclassified(tmp_path: Path) -> None:
    """The half that must not go quiet: the gate still blocks on a verdict nobody
    banded anywhere."""
    done = _run("check_verdict_bands.py", _verdict_tree(tmp_path))

    assert "PROJECT_SPECIFIC" in done.stdout, (
        "an unbanded verdict passed:\n" + done.stdout)


def test_a_local_entry_for_a_kit_verdict_is_a_finding(tmp_path: Path) -> None:
    """Silently overriding the kit's classification is the drift the single file was
    protecting against, and it stays protected."""
    root = _verdict_tree(tmp_path, local=(
        "PASS                          | redo       | disagreeing with the kit\n"))

    done = _run("check_verdict_bands.py", root)
    out = done.stdout + done.stderr

    assert "PASS" in out and ("already" in out.lower() or "overrid" in out.lower()), (
        "a local file quietly reclassified a kit verdict:\n" + out)
    assert done.returncode != 0, "the override was accepted silently"


def test_an_absent_local_file_changes_nothing(tmp_path: Path) -> None:
    """Every consumer that does not extend the kit must see today's behaviour."""
    with_none = _run("check_verdict_bands.py", _verdict_tree(tmp_path / "a"))
    empty = _verdict_tree(tmp_path / "b", local="")
    with_empty = _run("check_verdict_bands.py", empty)

    assert with_none.returncode == with_empty.returncode


# ------------------------------------------------------------- skills and cycles
#
# The skill map ALREADY had this mechanism — `rules/auxiliary-skills.txt`, read by
# `check_skill_map` and `check_xrefs` since 2026-09-02 — and the first attempt at this
# fix missed it and edited `map.md` instead, which is the kit's file and is overwritten.
# The tests below cover the two indexes on both sides of that: the one where the
# mechanism existed and the one where it did not.


def _skill_tree(tmp_path: Path, *, declared: str | None = None) -> Path:
    skills = tmp_path / "skills"
    for name in ("kit-skill", "project-skill"):
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n---\n\nbody\n",
                                    encoding="utf-8")
        (d / "SOP.md").write_text(
            "---\ntype: SOP\nsop: s\nversion: 1.0.0\nowner: o\nlast_reviewed: 2026-09-18\n"
            "---\n\n## Steps\n\n1. Do the thing.\n\n## Escalation\n\n- it breaks → stop.\n",
            encoding="utf-8")
    (skills / "map.md").write_text(
        "# The skill map\n\n**1 skills.**\n\n| Skill | Does |\n|---|---|\n"
        "| `kit-skill` | the kit's own |\n", encoding="utf-8")
    if declared is not None:
        rules = tmp_path / "rules"
        rules.mkdir(exist_ok=True)
        (rules / "auxiliary-skills.txt").write_text(declared, encoding="utf-8")
    return tmp_path


def test_a_project_skill_declared_as_its_own_owes_the_kit_map_no_row(tmp_path: Path) -> None:
    """`rules/auxiliary-skills.txt` is preserved across installs; `map.md` is not."""
    root = _skill_tree(tmp_path, declared="project-skill\n")

    done = _run("check_skill_map.py", root)

    assert "project-skill" not in done.stdout, (
        "a skill declared in auxiliary-skills.txt was asked for a row in the kit's "
        "map:\n" + done.stdout)


def test_an_undeclared_skill_is_still_missing_from_the_map(tmp_path: Path) -> None:
    done = _run("check_skill_map.py", _skill_tree(tmp_path))

    assert "project-skill" in done.stdout, (
        "an unlisted, undeclared skill passed:\n" + done.stdout)


def _cycle_tree(tmp_path: Path, *, declared: str | None = None) -> Path:
    rules = tmp_path / "rules"
    rules.mkdir(parents=True)
    # The gate reads the phase chain before it sweeps; without it the run is FATAL and
    # the assertion below would pass on an error message rather than on a finding.
    (rules / "cycle-phases.txt").write_text("# no phases declared\n", encoding="utf-8")
    (rules / "cycle-kit.md").write_text("# Cycle: KIT\n", encoding="utf-8")
    (rules / "cycle-project-own.md").write_text("# Cycle: PROJECT OWN\n", encoding="utf-8")
    (rules / "squad-map.md").write_text(
        "# Squad map\n\nThe chain: [`cycle-kit`](cycle-kit.md).\n", encoding="utf-8")
    (tmp_path / "hooks").mkdir(exist_ok=True)
    (tmp_path / "agents").mkdir(exist_ok=True)
    if declared is not None:
        (rules / "auxiliary-cycles.txt").write_text(declared, encoding="utf-8")
    return tmp_path


def test_a_project_cycle_declared_as_its_own_owes_the_squad_map_no_row(tmp_path: Path) -> None:
    """The index that had no mechanism at all. A consumer's only way to satisfy the
    finding was editing the kit's map, and the next install reverted it."""
    root = _cycle_tree(tmp_path, declared="cycle-project-own\n")

    done = _run("check_squad_map.py", root)
    out = done.stdout + done.stderr

    assert "cycle-project-own" not in out, (
        "a cycle declared in auxiliary-cycles.txt was still demanded of the kit's "
        "map:\n" + out)


def test_an_undeclared_cycle_is_still_absent_from_the_map(tmp_path: Path) -> None:
    """The half that must not go quiet: a cycle nobody declared anywhere is a cycle
    the map genuinely omits."""
    done = _run("check_squad_map.py", _cycle_tree(tmp_path))
    out = done.stdout + done.stderr

    assert "cycle-project-own" in out, (
        "an undeclared cycle passed:\n" + out)

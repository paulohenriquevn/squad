"""A gate that examined nothing must not print a verdict about everything.

This kit's most-found defect, by a wide margin, is an inability to measure
published as a measurement: a glob that lost its reach, a matcher pointed at a
renamed directory, a launcher that never looked. Every instance had the same
tell — a clean report over an empty sweep.

Measured on 2026-09-02, running every root-taking gate against an empty tree:
five of six said what they had swept ("swept 0 cycle rule(s)", "0 declared
phase(s)", "study zone absent or empty — nothing to compare against"). One
printed *"Overall: PASS — every cycle's declared numbering is unique and in chain
order"* after examining zero cycles.

This holds all of them to the honest five's standard, and any gate added later
inherits it without anyone remembering to.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_GATES = Path(__file__).resolve().parent.parent / "mechanisms" / "gates"

#: The flag each gate takes for the tree it should look at. A gate absent here
#: takes no root and is skipped — see `test_the_roster_covers_every_gate_that_takes_a_root`.
ROOT_FLAG = {
    # Both joined 2026-09-16, when the roster stopped selecting by filename prefix and
    # by a three-name flag list. `check_xrefs` had been `check_*` all along and was
    # missed only because it spells its flag `--ecosystem-dir`; it had been run by hand
    # dozens of times that week while sitting outside the empty-sweep protection.
    # `validate_skill_frontmatter` was missed twice over — wrong prefix AND wrong flag —
    # and exits 0 on an ecosystem whose `skills/` is present and empty.
    # Joined 2026-09-16, the day it learned to answer `--help`. It aggregates ELEVEN
    # checks, so it was the single largest hole in this roster and the hardest to see:
    # it refused introspection, and a test that skips what it cannot read reports the
    # skip as nothing at all.
    "verify_ecosystem": "--ecosystem-dir",
    "check_xrefs": "--ecosystem-dir",
    "validate_skill_frontmatter": "--ecosystem-dir",
    "check_english_only": "--root",
    "check_install_drift": "--install",
    # Joined 2026-09-11 with `rules/contribution-conventions.md`. It reads the project's
    # overrides and then the repository's own log, so it takes a repo root.
    "check_contribution_conventions": "--repo",
    "check_gate_mechanisms": "--repo",
    "check_mechanisms_inventory": "--root",
    "check_orphan_verdicts": "--repo",
    "check_phase_emitters": "--repo",
    "check_phase_numbering": "--root",
    # Joined the roster on 2026-09-05, the day it gained an entry point. It was
    # registered in `verify_ecosystem` and defined no `__main__`, so it was not a
    # gate that takes a root — it was a module that exited 0. This test noticing it
    # is the roster working: a gate joins the class by becoming runnable.
    "check_readme_advisory_skills": "--root",
    "check_reference_leakage": "--repo",
    # Joined 2026-09-08 with `rules/verdict-bands.txt`. It sweeps the rules tree for
    # declared verdicts, so it takes a root like its sibling `check_orphan_verdicts`.
    "check_verdict_bands": "--root",
    "check_semantic_names": "--repo",
    "check_skill_map": "--root",
    "check_squad_map": "--root",
    # Joined 2026-09-09 with the write root: it reports a project still holding data
    # outside `.squad/`, so it sweeps a tree and takes a root.
    "check_data_root": "--root",
    "check_wiki_migration": "--root",
    # Joined 2026-09-09 with the write root. It scans the kit's own trees for a data
    # root spelled outside `squad/paths.py`, so it takes a root like its siblings.
    "check_write_containment": "--root",
    # Joined 2026-09-10. Its sibling above proves the roots no MODULE spells;
    # this one covers the prose an agent executes, where a recipe creates a
    # legacy root without ever importing the owner.
    "check_prose_write_paths": "--root",
    # Joined 2026-09-10, the mirror of check_orphan_verdicts: that one asks whether
    # every DECLARED verdict is reachable, this one whether every INSTRUCTED verdict
    # is declared. Five skills failed it, and cycle_events.py refuses each.
    "check_emitted_verdicts": "--root",
}

#: Ways a gate can say "there was nothing here". Deliberately generous: the point
#: is that SOMETHING in the output distinguishes an empty sweep from a clean one,
#: not that every gate phrases it alike.
_SAYS_NOTHING_SWEPT = re.compile(
    r"\b0\s+\w|\bnothing\b|\bempty\b|\babsent\b|\bskip\b|\bnot a directory\b|"
    r"\bno \w+ (found|declared|present)\b|\bunreadable\b|FATAL",
    re.IGNORECASE)


@pytest.mark.parametrize("gate,flag", sorted(ROOT_FLAG.items()))
def test_an_empty_tree_produces_a_report_that_says_it_was_empty(
        gate: str, flag: str, tmp_path: Path) -> None:
    """Whatever the verdict, the output must let a reader tell an empty sweep
    from a clean one. A gate silent about its own reach is a gate whose next
    broken glob nobody notices."""
    done = subprocess.run(
        [sys.executable, str(_GATES / f"{gate}.py"), flag, str(tmp_path)],
        capture_output=True, text=True, timeout=120, check=False)
    output = done.stdout + done.stderr

    assert _SAYS_NOTHING_SWEPT.search(output), (
        f"{gate} reported on an empty tree without saying it was empty:\n{output[:600]}")


@pytest.mark.parametrize("gate,flag", sorted(ROOT_FLAG.items()))
def test_no_gate_claims_a_universal_property_over_an_empty_sweep(
        gate: str, flag: str, tmp_path: Path) -> None:
    """"every X is Y" said of zero X is the sentence this test exists for."""
    done = subprocess.run(
        [sys.executable, str(_GATES / f"{gate}.py"), flag, str(tmp_path)],
        capture_output=True, text=True, timeout=120, check=False)
    output = done.stdout + done.stderr

    for line in output.splitlines():
        if re.search(r"\bPASS\b", line) and re.search(r"\bevery\b|\ball\b", line,
                                                      re.IGNORECASE):
            assert re.search(r"\b[1-9]\d*\s+\w", line), (
                f"{gate} claims a universal property with no count behind it "
                f"on an empty tree:\n  {line}")


#: Flags by which a gate accepts a tree to sweep. A LIST, and that is the point: it is
#: checked against every file in `gates/`, so a gate using a spelling absent from this
#: tuple appears in the failure message rather than escaping the roster in silence.
_ROOT_FLAGS = ("root", "repo", "install", "ecosystem-dir", "dir", "path", "target")


def test_the_roster_covers_every_gate_that_takes_a_root() -> None:
    """A gate added later must not opt out of this by being forgotten.

    This globbed `check_*.py` and matched three flag spellings. Both are rules written
    as a list where the thing meant is a property — "it is a gate" — and both leaked:

      `verify_ecosystem.py`          not `check_*`, and aggregates ELEVEN other checks
      `validate_skill_frontmatter.py` not `check_*`, and takes `--ecosystem-dir`

    Measured 2026-09-16: the second exits 0 on an ecosystem whose `skills/` is present
    and empty, printing "Validated 0 skills: 0 errors" — a sweep that found nothing,
    reported as conformance. It sat outside this roster by two independent list-shaped
    rules, which is exactly what this test exists to prevent elsewhere.

    The glob is now every `*.py` in `gates/`, and a gate that cannot answer `--help` is
    named rather than skipped — an uninstrospectable gate is one this roster cannot
    protect, and silence about it reads as coverage.
    """
    missing, opaque = [], []
    for path in sorted(_GATES.glob("*.py")):
        if path.name.startswith("_"):
            continue
        helped = subprocess.run([sys.executable, str(path), "--help"],
                                capture_output=True, text=True, timeout=60, check=False)
        if helped.returncode != 0 or "usage:" not in helped.stdout:
            opaque.append(path.stem)
            continue
        flags = {f for f in _ROOT_FLAGS if f"--{f}" in helped.stdout}
        if flags and path.stem not in ROOT_FLAG:
            missing.append(f"{path.stem} (takes --{sorted(flags)[0]})")

    assert not missing, f"gates taking a root but absent from the roster: {missing}"
    assert not opaque, (
        "gates this roster cannot introspect because they refuse `--help`: "
        f"{opaque} — an unintrospectable gate is one this test cannot protect, and "
        "passing over it in silence reads as coverage")


def test_phase_numbering_finds_the_kit_when_given_a_project_root(tmp_path: Path) -> None:
    """A consumer keeps the kit in `.claude/`, and `--root .` is what someone
    types from a project. That pointed at a directory with no `skills/` and swept
    nothing — which printed a clean PASS until the empty-sweep fix, and prints an
    honest NOTHING_DECLARED after it. Honest is better and still not the answer
    the caller wanted."""
    project = tmp_path / "consumer"
    skill = project / ".claude" / "skills" / "some-phase"
    skill.mkdir(parents=True)
    (project / ".claude" / "rules").mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: some-phase\ndescription: d\n---\n\n"
        "## Cycle contract\n\n"
        "This skill is **phase 1** of [`cycle-demo`](../../rules/cycle-demo.md).\n\n"
        "## Process\n\nsomething\n",
        encoding="utf-8")

    done = subprocess.run(
        [sys.executable, str(_GATES / "check_phase_numbering.py"), "--root", str(project)],
        capture_output=True, text=True, timeout=120, check=False)

    assert "NOTHING_DECLARED" not in done.stdout, (
        f"the kit is in .claude/ and the gate did not look there:\n{done.stdout}")

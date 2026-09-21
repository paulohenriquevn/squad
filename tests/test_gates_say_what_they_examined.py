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

#: Every gate in the directory, discovered. Not a list.
#:
#: This was a hand-kept map of 22 gate names to the flag each one spelled its root
#: with — eight spellings across the directory — and the map's own comments record
#: what that cost: `check_xrefs` sat outside this protection for a week, run by hand
#: dozens of times, because it said `--ecosystem-dir`; `validate_skill_frontmatter`
#: was missed twice over, wrong prefix AND wrong flag, while exiting 0 on an empty
#: `skills/`. Both were found by someone noticing, which is not a mechanism.
#:
#: `mechanisms/gates/_contract.py` now declares ONE spelling and every gate accepts
#: it, so the roster is the glob. A gate added tomorrow is covered by existing, and
#: `check_gate_mechanisms` reports any gate that drifts off the contract.
#: Gates a root alone cannot invoke: each also requires an argument naming the ONE
#: thing it is about. `check_auditor_coverage --slug`, `check_panel_approval --slug
#: --phase` and `check_review_binding --slug` audit a named slice; `check_install_drift
#: --install` compares a kit against one installation. There is no empty sweep to make
#: honest, because there is no sweep — the subject is named or the gate does not run.
#:
#: Named here rather than skipped by a `returncode == 2` rule, which would also skip a
#: gate that crashed. `test_every_named_gate_really_needs_its_argument` holds this list
#: to the reason it gives, so a gate that loses its required argument rejoins the sweep.
NEEDS_MORE_THAN_A_ROOT = {
    "check_auditor_coverage", "check_install_drift",
    "check_panel_approval", "check_review_binding",
    # `check_tag_integrity --tag` inspects ONE git object. A repository holds many tags
    # and only the one being cut is the subject; sweeping them all would report on
    # history nobody is releasing.
    "check_tag_integrity",
}


def _roster() -> list[str]:
    return [p.stem for p in sorted(_GATES.glob("*.py"))
            if not p.name.startswith("_") and p.stem not in NEEDS_MORE_THAN_A_ROOT]


ROOT_FLAG = {gate: "--root" for gate in _roster()}


@pytest.mark.parametrize("gate", sorted(NEEDS_MORE_THAN_A_ROOT))
def test_every_named_gate_really_needs_its_argument(gate: str, tmp_path: Path) -> None:
    """The exemption holds only while the reason does.

    A name left here after its gate stopped requiring an argument is a gate quietly
    outside the empty-sweep protection — the exact failure this file was written for,
    re-created by the list that documents it.
    """
    done = subprocess.run([sys.executable, str(_GATES / f"{gate}.py"),
                           "--root", str(tmp_path)],
                          capture_output=True, text=True, timeout=120, check=False)
    output = done.stdout + done.stderr

    assert "the following arguments are required" in output, (
        f"{gate} runs on a root alone now, so it belongs in the sweep rather than "
        f"in NEEDS_MORE_THAN_A_ROOT:\n{output[:400]}")


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


def test_the_roster_covers_every_gate_that_takes_a_root() -> None:
    """A gate added later must not opt out of this by being forgotten.

    This test has been rewritten twice by the same failure. It began globbing
    `check_*.py` and matching three flag spellings; both are rules written as a list
    where the thing meant is a property — "it is a gate" — and both leaked.
    `verify_ecosystem.py` escaped on the prefix while aggregating ELEVEN other checks.
    `validate_skill_frontmatter.py` escaped on BOTH, and exits 0 on an ecosystem whose
    `skills/` is present and empty: a sweep that found nothing, reported as conformance.
    Widening the flag tuple to seven spellings only moved the leak.

    So the list is gone. `_contract.py` declares one flag, every gate accepts it, and
    the roster is the glob — membership by existing. What remains to check is that the
    two things the glob assumes are true: a gate can be introspected, and it answers to
    the contract's name. A gate that refuses `--help` is one this roster cannot protect,
    and passing over it in silence reads as coverage.
    """
    opaque, off_contract = [], []
    for path in sorted(_GATES.glob("*.py")):
        if path.name.startswith("_"):
            continue
        helped = subprocess.run([sys.executable, str(path), "--help"],
                                capture_output=True, text=True, timeout=60, check=False)
        if helped.returncode != 0 or "usage:" not in helped.stdout:
            opaque.append(path.stem)
        elif "--root" not in helped.stdout:
            off_contract.append(path.stem)

    assert not opaque, (
        "gates this roster cannot introspect because they refuse `--help`: "
        f"{opaque} — an unintrospectable gate is one this test cannot protect, and "
        "passing over it in silence reads as coverage")
    assert not off_contract, (
        f"gates that do not answer to `--root`: {off_contract}. The roster reaches "
        "them by the contract in `mechanisms/gates/_contract.py`; a gate spelling it "
        "otherwise leaves the sweep without anyone deciding that it should.")


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


def test_the_prose_sweep_says_how_many_files_it_parsed(tmp_path: Path) -> None:
    """`check_prose_tests` printed "no test pins the wording of shipped prose" and
    returned 0 whether it parsed 180 test files or none.

    A root with no `tests/` produced exactly the sentence a clean repository produces.
    """
    gate = _GATES / "check_prose_tests.py"

    # The root is POSITIONAL on this gate, not a flag.
    empty = subprocess.run([sys.executable, str(gate), str(tmp_path)],
                           capture_output=True, text=True, timeout=120, check=False)
    real = subprocess.run([sys.executable, str(gate), str(_GATES.parent.parent)],
                          capture_output=True, text=True, timeout=180, check=False)

    assert empty.returncode == 2, f"an unparsed tree exited {empty.returncode}"
    assert real.returncode == 0, real.stdout + real.stderr
    assert "test file(s) parsed" in real.stdout, real.stdout


def test_the_shell_sweep_names_what_it_covers() -> None:
    """The label said "Shell hooks syntax" and `hooks/*.sh` matches zero files.

    The hooks migrated to Python and the glob was never revisited, so a reader went
    looking for hook coverage that is not there — while the check's real subject, the
    shell under `skills/` and `mechanisms/`, went unnamed.
    """
    import verify_ecosystem as ve

    ok, lines = ve.check_shell_syntax(_GATES.parent.parent)

    assert ok is True, lines
    assert any("shell script(s) parsed" in ln for ln in lines), lines

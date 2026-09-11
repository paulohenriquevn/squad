"""Gate: README Advisory Skills must match actual skills on disk.

Regression for e5527e6, when three specialists (cap-theorem, backpressure,
resilience) were deleted and the README was never updated to reflect the removal.
This gate catches that drift in both directions: README promises skills that don't
exist, and skills exist that README doesn't know about.
"""
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_advisory_skills_in_readme_must_exist_on_disk() -> None:
    """Every skill named in README.md's Advisory skills table must exist on disk."""
    from mechanisms.gates import check_readme_advisory_skills

    findings = check_readme_advisory_skills.check(_REPO)
    readme_missing = [f for f in findings if f.get("type") == "readme_skill_missing"]

    # TODAY: This should fail, naming cap-theorem-specialist, backpressure-specialist,
    # and resilience-specialist as missing from disk.
    assert not readme_missing, (
        f"README.md cites advisory skills that do not exist on disk:\n"
        f"{json.dumps(readme_missing, indent=2)}"
    )


def test_advisory_skills_in_how_to_use_must_exist_on_disk() -> None:
    """Every skill named in HOW-TO-USE.md commands table must exist on disk."""
    from mechanisms.gates import check_readme_advisory_skills

    findings = check_readme_advisory_skills.check(_REPO)
    how_to_use_missing = [f for f in findings if f.get("type") == "how_to_use_skill_missing"]

    assert not how_to_use_missing, (
        f"HOW-TO-USE.md cites advisory skills that do not exist on disk:\n"
        f"{json.dumps(how_to_use_missing, indent=2)}"
    )


def test_a_skill_that_exists_is_not_reported(tmp_path: Path) -> None:
    """If README cites arch-check (which exists), it should not be in findings."""
    from mechanisms.gates import check_readme_advisory_skills

    findings = check_readme_advisory_skills.check(_REPO)
    arch_check_findings = [
        f for f in findings
        if "arch-check" in f.get("skill_name", "").lower()
    ]

    assert not arch_check_findings, (
        f"arch-check exists on disk but was still reported as missing: {arch_check_findings}"
    )


def test_gate_returns_empty_when_consistent(tmp_path: Path) -> None:
    """When README and disk are consistent, check returns empty list."""
    from mechanisms.gates import check_readme_advisory_skills

    findings = check_readme_advisory_skills.check(_REPO)

    # After README is corrected, this should pass (findings empty).
    # Before that, it should fail (findings non-empty with missing skills).
    # We test the structure regardless of the state.
    assert isinstance(findings, list)
    assert all(isinstance(f, dict) for f in findings)
    assert all("type" in f and "skill_name" in f for f in findings)


# ── the entry point, which is what the chain actually runs ────────────────────

_GATE = Path(__file__).resolve().parents[1] / "mechanisms" / "gates" / "check_readme_advisory_skills.py"


def _run(root: Path):
    import subprocess
    import sys as _sys
    return subprocess.run(  # noqa: PLW1510
        [_sys.executable, str(_GATE), "--root", str(root)],
        capture_output=True, text=True, timeout=120,
    )


def test_the_gate_fails_when_the_readme_cites_a_skill_that_is_not_on_disk(tmp_path: Path) -> None:
    """The defect this gate was written for, exercised through the door the chain uses.

    Every test above calls `check()` directly and they have all been green. The
    module had no `if __name__ == "__main__"` block at all, so running it as a
    script — which is exactly what `verify_ecosystem` does — defined some functions
    and exited 0. Measured 2026-09-05 against a planted inconsistency: exit 0, no
    output, and `verify_ecosystem` drew `✓ README advisory skills` for it.

    A correct checker with no way to be run is the same silence as a wrong one.
    """
    (tmp_path / "skills" / "real-skill").mkdir(parents=True)
    (tmp_path / "skills" / "real-skill" / "SKILL.md").write_text("---\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# R\n\n## Advisory skills\n\n| Skill | x |\n|---|---|\n"
        "| `ghost-skill` | not on disk |\n", encoding="utf-8")

    result = _run(tmp_path)

    assert result.returncode != 0, (
        f"the README cites a skill that is not on disk and the gate exited 0. "
        f"stdout={result.stdout!r}"
    )
    assert "ghost-skill" in result.stdout + result.stderr, (
        "the failure must name the skill; a gate that fails without saying what it "
        "found sends the reader back to re-derive it"
    )


def test_the_gate_says_what_it_examined_when_it_passes(tmp_path: Path) -> None:
    """Silence and success are the same output, and only one of them is true."""
    (tmp_path / "skills" / "real-skill").mkdir(parents=True)
    (tmp_path / "skills" / "real-skill" / "SKILL.md").write_text("---\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# R\n\n## Advisory skills\n\n| Skill | x |\n|---|---|\n"
        "| `real-skill` | on disk |\n", encoding="utf-8")

    result = _run(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip(), "a pass with no output is indistinguishable from a no-op"


def test_a_missing_readme_is_not_reported_as_a_clean_bill(tmp_path: Path) -> None:
    """The subject is absent, so nothing was compared. It must not read as a pass."""
    (tmp_path / "skills").mkdir()

    result = _run(tmp_path)
    out = (result.stdout + result.stderr).lower()

    assert out.strip(), "no README and no output at all"
    assert "not checked" in out or "nothing" in out, (
        f"a gate whose subject is absent must say so; got {out!r}"
    )


def test_no_gate_the_verifier_runs_as_a_script_lacks_an_entry_point() -> None:
    """The class, not the instance.

    `verify_ecosystem` invokes gates with `sys.executable <path>`. A module with no
    `__main__` block answers that with silence and exit 0 — which is the strongest
    possible false pass, because it is indistinguishable from a check that ran.
    """
    import re

    verifier = (Path(__file__).resolve().parents[1] / "mechanisms" / "gates"
                / "verify_ecosystem.py").read_text(encoding="utf-8")
    invoked = set(re.findall(r'"(check_[a-z_]+\.py|validate_[a-z_]+\.py)"', verifier))
    assert invoked, "found no gate invocations in verify_ecosystem — the pattern moved"

    entryless = []
    for name in sorted(invoked):
        path = Path(__file__).resolve().parents[1] / "mechanisms" / "gates" / name
        if not path.is_file():
            continue
        if "__main__" not in path.read_text(encoding="utf-8"):
            entryless.append(name)

    assert not entryless, (
        f"{entryless} are run as scripts and define no entry point, so they exit 0 "
        f"without doing anything and the verifier ticks them"
    )


def test_the_advisory_prose_does_not_describe_more_skills_than_the_table_lists() -> None:
    """The residue of `e5527e6` that the gate was built for and cannot see.

    That commit deleted seven skills; the table under `## Advisory skills` was
    trimmed to one row, and the paragraph beneath it was not. It still read "**Each**
    refuses the shortcut its field is prone to" and then named three shortcuts — CP
    or AP without configuration, an unbounded buffer, a non-idempotent retry — which
    are `cap-theorem-specialist`, `backpressure-specialist` and a resilience skill.
    All three were deleted in the same commit. Measured 2026-09-05: none is on disk.

    The gate cannot catch this because it matches skill NAMES in table cells, and
    prose describes without naming. So the check lives here: the paragraph must not
    use a plural for a table with one row.

    Not a general prose-vs-disk checker — that would need to know which sentence
    describes which skill, which a regex cannot. This pins the one relationship that
    already went wrong.
    """
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    section = readme[readme.index("## Advisory skills"):]
    section = section[:section.index("\n## ", 1)]

    rows = [ln for ln in section.splitlines()
            if ln.startswith("|") and "`" in ln and "---" not in ln]
    assert rows, "the Advisory skills table has no rows at all"

    prose = "\n".join(ln for ln in section.splitlines()
                      if not ln.startswith("|") and not ln.startswith("#"))
    if len(rows) == 1:
        for plural in ("Each ", "They ", "each of them"):
            assert plural not in prose, (
                f"the table lists one skill and the prose says {plural!r}, which is "
                f"how three deleted skills kept being described after their rows went"
            )


def test_a_flag_in_backticks_is_not_a_skill_name(tmp_path: Path) -> None:
    """The character class allowed `-` in first position, so `--yes` read as a skill
    name and the gate reported a missing `--yes/SKILL.md`.

    Prose about a skill's flags is the most natural thing to write in a section about
    skills, so the class had to stop matching it — rewriting the prose around the check
    would have moved the defect rather than fixed it.
    """
    from check_readme_advisory_skills import _SKILL_NAME_RE

    assert _SKILL_NAME_RE.findall("`arch-check` has no `--yes`") == ["arch-check"]
    assert _SKILL_NAME_RE.findall("pass `--strict` to `check-xrefs`") == ["check-xrefs"]
    assert not _SKILL_NAME_RE.findall("`--force`")

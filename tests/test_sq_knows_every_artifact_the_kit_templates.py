"""`sq` is one entry point for artifacts that had 181.

Measured 2026-09-23: 143 scripts under `skills/*/scripts` plus 38 gates under
`mechanisms/gates`, each with its own flags, and no CLI at all. The cost is not the count — it
is that a contract lives only in a checker's source. A consumer discovered **six exact heading
literals by trial and error in one day**, across three checkers, and each discovery was a failed
run first:

    check_criterion_executability   wanted `#### Definition of Done`, the author wrote `#### DoD`
    check_baseline_context          wanted `### Current callers / dependents`
    check_drawbacks_section         wanted a bullet not opening in bold
    check_adr_completeness          wanted `### D1` while every plan writes `### ADR-N`

THE CONSTRAINT THAT SHAPES IT. `sq contract` must DERIVE what a checker requires from the
checker, never restate it. A hand-written table of headings inside `sq` would be the seventh
place they drift, and this day is a list of what that costs. Where a checker does not declare its
requirements, `sq contract` says so by name rather than printing nothing — a gap named is a gap
somebody can close, and four of seventeen declare today.

This test is the registry's keeper: every template the kit ships is either a kind `sq` knows or is
declared as not being an artifact, with a reason. Adding a template forces the decision instead of
inheriting silence — the same shape as `_NOT_EXERCISED` in
`test_the_template_satisfies_its_own_checkers`, and as `test_every_gate_is_reachable`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
SQ = _ROOT / "mechanisms" / "sq.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SQ), *args],
                          capture_output=True, text=True, check=False, cwd=str(_ROOT))


def test_sq_exists_and_lists_its_verbs() -> None:
    out = _run("--help")
    assert out.returncode == 0, (out.stdout + out.stderr)[-1200:]
    for verb in ("new", "check", "show", "contract"):
        assert verb in out.stdout, f"`{verb}` is not offered: {out.stdout[-600:]}"


def test_the_registry_is_not_empty() -> None:
    """Without this, every assertion below runs over zero kinds and passes."""
    sys.path.insert(0, str(_ROOT / "mechanisms"))
    import sq

    assert sq.KINDS, "no artifact kind registered; this test lost its subject"


def test_every_template_is_a_known_kind_or_declared_otherwise() -> None:
    sys.path.insert(0, str(_ROOT / "mechanisms"))
    import sq

    shipped = {p.resolve() for p in _ROOT.glob("skills/*/templates/*.md")}
    registered = {(_ROOT / k.template).resolve() for k in sq.KINDS.values() if k.template}
    declared = {(_ROOT / rel).resolve() for rel in sq.NOT_AN_ARTIFACT}
    by_pattern = {q.resolve() for pattern in sq.NOT_AN_ARTIFACT_PATTERNS
                  for q in _ROOT.glob(pattern)}

    unaccounted = sorted(str(p.relative_to(_ROOT))
                         for p in shipped - registered - declared - by_pattern)
    assert unaccounted == [], (
        "these templates are neither a kind `sq` knows nor declared in `NOT_AN_ARTIFACT` with a "
        f"reason: {unaccounted}")


def test_no_declaration_names_a_template_that_left() -> None:
    """The other direction: a declaration for a deleted template is a rule that stopped applying."""
    sys.path.insert(0, str(_ROOT / "mechanisms"))
    import sq

    missing = sorted(rel for rel in sq.NOT_AN_ARTIFACT if not (_ROOT / rel).is_file())
    assert missing == [], f"declared as not-an-artifact and no longer on disk: {missing}"

    empty = sorted(pat for pat in sq.NOT_AN_ARTIFACT_PATTERNS if not list(_ROOT.glob(pat)))
    assert empty == [], (
        f"these patterns exclude nothing that exists — a rule that has quietly stopped "
        f"applying, which is the defect this kit records for vacuous architecture rules: {empty}")


@pytest.mark.parametrize("kind", ["alignment", "plan", "opportunity"])
def test_contract_names_the_checkers_and_admits_what_is_undeclared(kind: str) -> None:
    """The verb that kills trial and error — and it must be honest about its own blind spot."""
    sys.path.insert(0, str(_ROOT / "mechanisms"))
    import sq

    out = _run("contract", kind)

    assert out.returncode == 0, (out.stdout + out.stderr)[-1200:]
    # The names come from the registry, not from a `check_` convention: the alignment checker is
    # `score_alignment`, and asserting the prefix would have been a test about naming rather than
    # about whether the contract names its checkers.
    expected = [rel.rsplit("/", 1)[-1] for rel in sq.KINDS[kind].checkers]
    missing = [name for name in expected if name not in out.stdout]
    assert missing == [], f"`contract {kind}` names none of {missing}: {out.stdout[-500:]}"
    # Case-insensitive, because the assertion is about WHICH of the two things the contract
    # says — the requirements, or that a checker does not declare them — and not about how the
    # sentence is capitalised. A test pinned to prose fails on a rewording that changed nothing.
    said = out.stdout.lower()
    assert "not declare" in said or "requires:" in said, (
        "contract says neither what is required nor that a checker fails to declare it: "
        f"{out.stdout[-400:]}")


def test_check_runs_the_applicable_checkers_on_a_real_artifact(tmp_path: Path) -> None:
    brief = tmp_path / "x-alignment.md"
    brief.write_text("# Alignment: X\n\n## Problem\n" + ("word " * 40) + "\n", encoding="utf-8")

    out = _run("check", str(brief))

    combined = out.stdout + out.stderr
    assert "alignment" in combined.lower(), combined[-800:]
    assert "check" in combined or "score" in combined.lower(), combined[-800:]


def test_check_refuses_a_path_whose_kind_it_cannot_tell(tmp_path: Path) -> None:
    """Guessing a kind is how a report says something about the wrong contract."""
    stray = tmp_path / "notes.md"
    stray.write_text("# just notes\n", encoding="utf-8")

    out = _run("check", str(stray))

    assert out.returncode != 0
    assert "kind" in (out.stdout + out.stderr).lower()

# ── every verb is exercised, not merely offered ──────────────────────────────
#
# The first version of this file tested TWO of four verbs and asserted that all four appear in
# `--help`. That is coverage of the MENU, and the same day it was written this kit shipped
# `test_every_verdict_the_installer_can_reach_has_a_test` whose whole argument is that
# flag-level coverage misses an untested OUTCOME of a tested flag.
#
# `new` was the one left out, and it is the only verb that WRITES.
#
# So the list below is read from the parser, not typed: a verb added later fails this until it
# is invoked by a test, whatever it is called.


def _offered_verbs() -> list[str]:
    source = SQ.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'sub\.add_parser\("([a-z-]+)"', source)))


def test_the_parser_offers_verbs() -> None:
    """Without this, the check below runs over an empty list and passes."""
    assert _offered_verbs(), "no verb parsed from sq.py; this test lost its subject"


@pytest.mark.parametrize("verb", _offered_verbs(), ids=lambda v: v)
def test_a_verb_the_cli_offers_is_invoked_by_a_test(verb: str) -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    assert f'_run("{verb}"' in source, (
        f"`sq {verb}` is offered and no test in this file runs it. Appearing in `--help` is "
        f"coverage of the menu, not of the verb.")


def test_new_writes_the_template_into_the_records_root(tmp_path: Path) -> None:
    out = _run("new", "alignment", "my-slug", "--into", str(tmp_path))

    assert out.returncode == 0, (out.stdout + out.stderr)[-1200:]
    written = tmp_path / "alignment" / "my-slug-alignment.md"
    assert written.is_file(), f"nothing written; said: {out.stdout[-400:]}"
    assert written.read_text(encoding="utf-8").strip(), "the file written is empty"


def test_new_refuses_to_overwrite(tmp_path: Path) -> None:
    """The verb that writes must not be the verb that loses somebody's draft."""
    assert _run("new", "alignment", "s", "--into", str(tmp_path)).returncode == 0
    before = (tmp_path / "alignment" / "s-alignment.md").read_text(encoding="utf-8")
    (tmp_path / "alignment" / "s-alignment.md").write_text("MY DRAFT\n", encoding="utf-8")

    out = _run("new", "alignment", "s", "--into", str(tmp_path))

    assert out.returncode != 0
    assert (tmp_path / "alignment" / "s-alignment.md").read_text(encoding="utf-8") == "MY DRAFT\n"
    assert before != "MY DRAFT\n"


def test_new_refuses_a_kind_with_no_template(tmp_path: Path) -> None:
    """`opportunity` is written by its skill rather than copied. Saying so beats writing a stub."""
    out = _run("new", "opportunity", "s", "--into", str(tmp_path))

    assert out.returncode != 0
    assert "template" in (out.stdout + out.stderr).lower()
    assert not list(tmp_path.rglob("*.md"))


def test_show_reports_the_same_state_as_check(tmp_path: Path) -> None:
    """`show` delegates to `check`. If the two ever diverge, a reader has two answers."""
    brief = tmp_path / "x-alignment.md"
    brief.write_text("# Alignment: X\n\n## Problem\n" + ("word " * 40) + "\n", encoding="utf-8")

    shown = _run("show", str(brief))
    checked = _run("check", str(brief))

    assert shown.stdout == checked.stdout
    assert shown.returncode == checked.returncode


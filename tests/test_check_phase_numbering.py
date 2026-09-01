"""A phase number is a fact written in two files, and nothing compared them.

The case this was written from, measured 2026-08-31: `/deps-audit` was inserted into
`cycle-plan` five days earlier and only its own file was renumbered, so `deps-audit`
and `plan-confidence` both claimed phase 3 while `deps-audit`'s own prose said
`plan-confidence` was phase 4. Three versioned contracts, one chain, two answers.

A fourth manifestation turned up in the frontmatter: `plan-confidence` still
declared `requires: [edge-case-plan]`, reaching past the skill inserted in front of
it. That one is machine-readable, which is why the third clause exists.

The tests below pin the three clauses and — just as much — the things that must NOT
be findings. A checker that reports a cycle numbering from 0, a half-step inserted
between two integers, or a conditional skill absent from the diagram is a checker
someone disables, and then the real defect goes unreported with it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_phase_numbering import (  # noqa: E402
    check, chain_order, declared_phase, declared_requires, main,
)


def _kit(root: Path, chain: list[str], claims: dict[str, str],
         cycle: str = "cycle-plan", requires: dict[str, list[str]] | None = None) -> Path:
    (root / "rules").mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"/{name} {{slug}}" for name in chain)
    (root / "rules" / f"{cycle}.md").write_text(
        f"# Cycle\n\n## Chain\n\n```\n{lines}\n```\n\n## Something else\n",
        encoding="utf-8")
    for name, claim in claims.items():
        directory = root / "skills" / name
        directory.mkdir(parents=True, exist_ok=True)
        needs = (requires or {}).get(name, [])
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\nrequires: [{', '.join(needs)}]\n---\n\n"
            f"# {name}\n\n## Cycle contract\n\n"
            f"This skill is **phase {claim}** of [`{cycle}`](../../rules/{cycle}.md).\n\n"
            f"## Elsewhere\n\nSomething mentioning phase 9 that is not a claim.\n",
            encoding="utf-8")
    return root


def test_a_coherent_cycle_produces_nothing(tmp_path: Path) -> None:
    _kit(tmp_path, ["a", "b", "c"], {"a": "1", "b": "2", "c": "3"})

    assert check(tmp_path) == []


def test_two_skills_claiming_one_number_is_a_finding(tmp_path: Path) -> None:
    """The measured defect: an insertion renumbered one file and not the rest."""
    _kit(tmp_path, ["a", "b", "c"], {"a": "1", "b": "2", "c": "2"})

    kinds = [f.kind for f in check(tmp_path)]

    assert "duplicate_phase_number" in kinds


def test_a_number_that_goes_backwards_in_the_chain_is_a_finding(tmp_path: Path) -> None:
    _kit(tmp_path, ["a", "b"], {"a": "3", "b": "1"})

    findings = check(tmp_path)

    assert [f.kind for f in findings] == ["phase_out_of_chain_order"]
    assert "runs before" in findings[0].detail


def test_zero_based_numbering_is_not_a_finding(tmp_path: Path) -> None:
    """`cycle-backlog` starts at 0 and `cycle-discover` at 1. Both are correct, and a
    checker demanding one of them reports the other as broken forever."""
    _kit(tmp_path, ["a", "b", "c"], {"a": "0", "b": "1", "c": "2"})

    assert check(tmp_path) == []


def test_a_half_step_is_not_a_finding(tmp_path: Path) -> None:
    """`shared-understanding` is phase 0.5 precisely so nothing downstream had to
    move. Demanding a dense integer sequence would punish the careful choice."""
    _kit(tmp_path, ["a", "b", "c"], {"a": "0", "b": "0.5", "c": "1"})

    assert check(tmp_path) == []


def test_a_skill_absent_from_the_chain_still_has_to_be_unique(tmp_path: Path) -> None:
    """`/plan-improve` is conditional and appears in no diagram. It cannot be checked
    for order — and its number is still its own."""
    _kit(tmp_path, ["a", "b"], {"a": "1", "b": "2", "conditional": "2"})

    findings = check(tmp_path)

    assert [f.kind for f in findings] == ["duplicate_phase_number"]
    assert "conditional" in findings[0].detail


def test_a_cycle_with_one_numbered_skill_is_never_a_finding(tmp_path: Path) -> None:
    """"The only phase" is how most cycles describe themselves. There is nothing to
    order and nothing to collide with."""
    _kit(tmp_path, ["a"], {"a": "1"})

    assert check(tmp_path) == []


def test_a_number_outside_the_cycle_contract_is_not_a_claim(tmp_path: Path) -> None:
    """A SKILL.md explaining someone else's chain says "phase 2" while declaring
    nothing. Reading that as a declaration is the substring defect this kit has paid
    for more than once."""
    _kit(tmp_path, ["a", "b"], {"a": "1", "b": "2"})
    victim = tmp_path / "skills" / "b" / "SKILL.md"
    victim.write_text(victim.read_text(encoding="utf-8")
                      + "\n`/other` is **phase 1** of another cycle entirely.\n",
                      encoding="utf-8")

    assert check(tmp_path) == []


def test_the_chain_order_is_read_from_the_fenced_block(tmp_path: Path) -> None:
    _kit(tmp_path, ["first", "second"], {})

    assert chain_order(tmp_path / "rules" / "cycle-plan.md") == ["first", "second"]


def test_a_skill_with_no_cycle_contract_declares_nothing(tmp_path: Path) -> None:
    directory = tmp_path / "skills" / "auxiliary"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text("# auxiliary\n\nNo contract here.\n",
                                        encoding="utf-8")

    assert declared_phase(directory / "SKILL.md") is None


def test_exit_code_is_one_on_a_finding(tmp_path: Path) -> None:
    _kit(tmp_path, ["a", "b"], {"a": "2", "b": "2"})

    assert main(["--root", str(tmp_path)]) == 1


def test_the_kit_itself_is_coherent() -> None:
    """The regression this was written for. It failed before the numbers were fixed."""
    assert check(Path(__file__).resolve().parents[1]) == []


# ── the third clause: a requires that reaches past its own predecessor ─────────


def test_requires_reaching_past_the_predecessor_is_a_finding(tmp_path: Path) -> None:
    """The measured shape: `/deps-audit` was inserted between `edge-case-plan` and
    `plan-confidence`, and `plan-confidence` kept requiring what came before it."""
    _kit(tmp_path, ["a", "inserted", "c"], {"a": "1", "inserted": "2", "c": "3"},
         requires={"inserted": ["a"], "c": ["a"]})

    findings = [f for f in check(tmp_path) if f.kind == "requires_skips_a_phase"]

    assert len(findings) == 1
    assert "`c` requires `a`" in findings[0].detail


def test_requiring_the_actual_predecessor_is_clean(tmp_path: Path) -> None:
    _kit(tmp_path, ["a", "inserted", "c"], {"a": "1", "inserted": "2", "c": "3"},
         requires={"inserted": ["a"], "c": ["inserted"]})

    assert [f for f in check(tmp_path) if f.kind == "requires_skips_a_phase"] == []


def test_an_empty_requires_is_never_a_finding(tmp_path: Path) -> None:
    """`shared-understanding` requires nothing because `grill-me` is optional.
    Reading an empty list as a skipped phase would fire on correct work."""
    _kit(tmp_path, ["a", "b"], {"a": "1", "b": "2"}, requires={"b": []})

    assert [f for f in check(tmp_path) if f.kind == "requires_skips_a_phase"] == []


def test_requiring_something_outside_this_chain_is_not_a_finding(tmp_path: Path) -> None:
    """A chain may hand off to a skill of another cycle, whose `requires` speaks
    about that other cycle. Checked naively, five of six real mismatches in this kit
    are correct work."""
    _kit(tmp_path, ["a", "b"], {"a": "1", "b": "2"},
         requires={"b": ["something-from-another-cycle"]})

    assert [f for f in check(tmp_path) if f.kind == "requires_skips_a_phase"] == []


def test_requires_is_read_from_the_frontmatter(tmp_path: Path) -> None:
    _kit(tmp_path, ["a", "b"], {"a": "1", "b": "2"}, requires={"b": ["a"]})

    assert declared_requires(tmp_path / "skills" / "b" / "SKILL.md") == ["a"]

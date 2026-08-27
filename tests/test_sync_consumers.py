"""Updating 42 consumers by hand is how one adopter was nearly regressed.

While updating that adopter, five files had diverged from the kit — and the
divergence was LOCAL improvement (the `ECO=` convention in 9 skills,
check_xrefs's `_is_test_file`, the project's specialist list). Copying over them
would have erased all three. It only did not because the comparison was done file
by file first.

With 42 consumers that care does not scale as manual discipline. This is the
classifier that makes it mechanical: `identical` / `new` / `update` (the target is
on the base version, copying is safe) / `local-change` (the target diverged — do
NOT touch, name it for a human decision).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sync_consumers import Action, classify


def test_absent_target_is_new() -> None:
    assert classify(source="a\n", base="a\n", target=None) is Action.NEW


def test_target_equal_to_source_is_identical() -> None:
    assert classify(source="a\n", base="old\n", target="a\n") is Action.IDENTICAL


def test_target_on_the_base_version_is_a_safe_update() -> None:
    """The common case: the consumer is on the kit's previous version."""
    assert classify(source="novo\n", base="antigo\n", target="antigo\n") is Action.UPDATE


def test_target_that_diverged_from_base_is_a_local_change() -> None:
    """The adopter's lesson: divergence is local improvement until proven otherwise."""
    assert classify(
        source="novo do kit\n", base="antigo\n", target="antigo + correcao local\n"
    ) is Action.LOCAL_CHANGE


def test_file_absent_from_the_base_but_present_in_both_is_compared_by_content() -> None:
    """A file new in the kit that the target already has (written there first) is not
    a blind update: if the content differs, it is a local change."""
    assert classify(source="do kit\n", base=None, target="do kit\n") is Action.IDENTICAL
    assert classify(source="do kit\n", base=None, target="do projeto\n") is Action.LOCAL_CHANGE


# ---------------------------------------------------------------------------
# Lag is not local modification. The first dry-run across 40 consumers marked 231
# files as LOCAL_CHANGE, `scripts/install.sh` in almost all of them — and it was
# not local improvement, it was an install made from an older version. Comparing
# against ONE base only answers well for whoever sits exactly on it.
# ---------------------------------------------------------------------------

from sync_consumers import classify_with_history  # noqa: E402


def test_content_that_matches_any_historical_kit_version_is_stale(tmp_path: Path) -> None:
    """If the target's content is a version the kit once had, it is behind — not
    modified. Updating is safe."""
    action = classify_with_history(
        source="v3\n", base="v2\n", target="v1\n", historical={"v1\n", "v2\n", "v3\n"}
    )
    assert action is Action.STALE


def test_content_in_no_historical_version_is_a_real_local_change(tmp_path: Path) -> None:
    action = classify_with_history(
        source="v3\n", base="v2\n", target="v2 + patch do projeto\n",
        historical={"v1\n", "v2\n", "v3\n"},
    )
    assert action is Action.LOCAL_CHANGE


def test_the_base_version_is_still_a_plain_update() -> None:
    action = classify_with_history(
        source="v3\n", base="v2\n", target="v2\n", historical={"v1\n", "v2\n"}
    )
    assert action is Action.UPDATE


# ---------------------------------------------------------------------------
# A delta tem de ser FECHADA. Os arquivos sincronizados citam outras regras do
# kit; in a lagging consumer those rules may not exist, and the target's
# check_xrefs starts failing on a broken reference — measured: 13 of the 40
# consumers went red after the first application, citing
# `rules/knowledge-base-location.md` e `rules/live-target.txt`.
# ---------------------------------------------------------------------------

from sync_consumers import missing_rule_dependencies  # noqa: E402


def test_rules_cited_by_the_delta_but_absent_in_the_target_are_listed(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    (kit / "rules").mkdir(parents=True)
    (kit / "skills" / "x").mkdir(parents=True)
    (kit / "rules" / "presente.md").write_text("ok", encoding="utf-8")
    (kit / "rules" / "ausente.md").write_text("ok", encoding="utf-8")
    (kit / "skills" / "x" / "SKILL.md").write_text(
        "leia `rules/presente.md` e `rules/ausente.md`\n", encoding="utf-8")

    eco = tmp_path / "alvo" / ".claude"
    (eco / "rules").mkdir(parents=True)
    (eco / "rules" / "presente.md").write_text("ok", encoding="utf-8")

    missing = missing_rule_dependencies(kit, eco, ["skills/x/SKILL.md"])
    assert missing == ["rules/ausente.md"]


def test_a_rule_the_target_already_has_is_never_reported(tmp_path: Path) -> None:
    """Config do projeto vive em rules/*.txt — sobrescrever seria destruir ajuste local.
    Only what is MISSING enters."""
    kit = tmp_path / "kit"
    (kit / "rules").mkdir(parents=True)
    (kit / "skills" / "x").mkdir(parents=True)
    (kit / "rules" / "live-target.txt").write_text("do kit", encoding="utf-8")
    (kit / "skills" / "x" / "SKILL.md").write_text("veja `rules/live-target.txt`", encoding="utf-8")

    eco = tmp_path / "alvo" / ".claude"
    (eco / "rules").mkdir(parents=True)
    (eco / "rules" / "live-target.txt").write_text("CONFIG DO PROJETO", encoding="utf-8")

    assert missing_rule_dependencies(kit, eco, ["skills/x/SKILL.md"]) == []


# ---------------------------------------------------------------------------
# Grill kit-domain-agents-install, decision 5: a domain agent belongs to the
# PROJECT. Neither direction makes sense — neither the kit pushing, nor harvesting.
# ---------------------------------------------------------------------------

def test_agents_are_not_in_the_sync_scope() -> None:
    """Without this, the kit pushes the origin ecosystem's eight specialists back on
    every sync, undoing the cleanup the consumer did."""
    from sync_consumers import delta_prefixes
    assert "agents/" not in delta_prefixes()
    assert "skills/" in delta_prefixes()

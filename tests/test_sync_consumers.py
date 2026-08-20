"""Atualizar 42 consumidores à mão é como o `theo` quase foi regredido.

Ao atualizar o `theo` nesta sessão, cinco arquivos tinham divergido do kit — e a
divergência era melhoria LOCAL (a convenção `ECO=` em 9 skills, o `_is_test_file`
do check_xrefs, a lista de especialistas do projeto). Copiar por cima teria
apagado as três. Só não apagou porque eu comparei arquivo a arquivo antes.

Com 42 consumidores esse cuidado não escala como disciplina manual. Este é o
classificador que o torna mecânico: `identical` / `new` / `update` (o alvo está
na versão base, copiar é seguro) / `local-change` (o alvo divergiu — NÃO tocar,
nomear para decisão humana).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sync_consumers import Action, classify  # noqa: E402


def test_absent_target_is_new() -> None:
    assert classify(source="a\n", base="a\n", target=None) is Action.NEW


def test_target_equal_to_source_is_identical() -> None:
    assert classify(source="a\n", base="old\n", target="a\n") is Action.IDENTICAL


def test_target_on_the_base_version_is_a_safe_update() -> None:
    """O caso comum: o consumidor está na versão anterior do kit."""
    assert classify(source="novo\n", base="antigo\n", target="antigo\n") is Action.UPDATE


def test_target_that_diverged_from_base_is_a_local_change() -> None:
    """A lição do theo: divergência é melhoria local até prova em contrário."""
    assert classify(
        source="novo do kit\n", base="antigo\n", target="antigo + correcao local\n"
    ) is Action.LOCAL_CHANGE


def test_file_absent_from_the_base_but_present_in_both_is_compared_by_content() -> None:
    """Arquivo novo no kit que o alvo já tem (escrito lá primeiro) não é update
    cego: se o conteúdo difere, é mudança local."""
    assert classify(source="do kit\n", base=None, target="do kit\n") is Action.IDENTICAL
    assert classify(source="do kit\n", base=None, target="do projeto\n") is Action.LOCAL_CHANGE


# ---------------------------------------------------------------------------
# Defasagem não é modificação local. O primeiro dry-run sobre 40 consumidores
# marcou 231 arquivos como LOCAL_CHANGE, `scripts/install.sh` em quase todos —
# e não era melhoria local, era instalação feita de uma versão antiga. Comparar
# com UMA base só responde bem para quem está exatamente nela.
# ---------------------------------------------------------------------------

from sync_consumers import classify_with_history  # noqa: E402


def test_content_that_matches_any_historical_kit_version_is_stale(tmp_path: Path) -> None:
    """Se o conteúdo do alvo é uma versão que o kit já teve, ele está atrasado —
    não modificado. Atualizar é seguro."""
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
# kit; num consumidor defasado essas regras podem não existir, e o check_xrefs
# do alvo passa a reprovar por referência quebrada — medido: 13 dos 40
# consumidores ficaram vermelhos após a primeira aplicação, citando
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
    Só o que FALTA entra."""
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
# Grill kit-domain-agents-install, decisão 5: agente de domínio é do PROJETO.
# Nenhuma das duas direções faz sentido — nem o kit empurrar, nem colher.
# ---------------------------------------------------------------------------

def test_agents_are_not_in_the_sync_scope() -> None:
    """Sem isto, o kit empurra os oito especialistas do `theo` de volta a cada sync,
    desfazendo a limpeza que o consumidor fez."""
    from sync_consumers import delta_prefixes
    assert "agents/" not in delta_prefixes()
    assert "skills/" in delta_prefixes()

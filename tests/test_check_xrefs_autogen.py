"""O validador não pode acusar de órfã a skill que o próprio cycle gera.

`/review` escreve `review-{slug}-{dimensão}-knowledge` e o discover escreve
`*-sepa-knowledge`. São ARTEFATOS de execução, não fases de cycle. O
`patch_install.sh` já as trata assim; este validador não tratava, e o efeito
aparecia longe da causa: todo consumidor que rodasse `/review` passava a
falhar `--strict` — medido nos três consumidores em 2026-08-03, 26 WARN e
nenhum defeito real.

Estes testes chamam `_is_auto_generated` do módulo real em vez de reproduzir a
regra. A versão anterior reproduzia, e o preço apareceu: a isenção foi aplicada
a um dos dois checks e a suíte seguiu verde, porque validava a cópia. Um teste
que reimplementa aquilo que deveria proteger não protege nada.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from check_xrefs import AUXILIARY_SKILLS, _is_auto_generated  # noqa: E402


def _orphans(existing: set[str]) -> set[str]:
    auto = {s for s in existing if _is_auto_generated(s)}
    return existing - AUXILIARY_SKILLS - auto


def test_review_knowledge_gerada_nao_e_orfa() -> None:
    assert _orphans({"review-m5-ship-apikey-otel-tests-knowledge"}) == set()


def test_sepa_knowledge_gerada_nao_e_orfa() -> None:
    assert _orphans({"promptly-sepa-knowledge"}) == set()


def test_skill_de_verdade_sem_cycle_continua_orfa() -> None:
    """A isenção não pode virar porta dos fundos para skill real sem cycle."""
    assert _orphans({"skill-writer"}) == {"skill-writer"}


def test_nome_que_so_parece_gerado_continua_orfa() -> None:
    """`knowledge-base-helper` não termina em `-knowledge`; não é isento."""
    assert _orphans({"knowledge-base-helper"}) == {"knowledge-base-helper"}


def test_gerada_tambem_isenta_de_cycle_contract() -> None:
    """Regressão: a isenção valia num check e não no outro.

    A skill que o `/review` escreve não tem seção `Cycle contract` — nem deve
    ter. Isentá-la de `no_orphan_skills` e seguir cobrando
    `skill_has_cycle_contract` trocou 26 WARN por 3 e pareceu conserto; o
    consumidor continuava em FAIL por um defeito que não existia. O predicado é
    um só justamente para que os dois checks não possam divergir.
    """
    assert _is_auto_generated("review-m0-walking-skeleton-tests-knowledge")
    assert _is_auto_generated("promptly-sepa-knowledge")
    assert not _is_auto_generated("skill-writer")
    assert not _is_auto_generated("knowledge-base-helper")

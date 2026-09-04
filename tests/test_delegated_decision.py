"""The delegation boundary, held against the prose that actually walls a backlog.

Every `blocked_by` string below is taken from a real consumer registry on
2026-09-04, where 14 items sat AWAITING_HUMAN. Repository names are replaced with
placeholders — the kit describes any product that adopts it, so a named one would
make every consumer inherit a map of repos they do not have. They are here
because the first attempt at this mechanism was tested against invented text and
reported 6 of these 14 resolvable, including one that asks for a host to be
provisioned. Invented text agrees with whatever matcher you point at it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "cycle"))

from delegated_decision import DecisionClass, classify_wall, rewrite_wall


# ── The prose that must stay walled ────────────────────────────────────────────

B139_HOST = (
    "aguardando (1) operador (você) executar migração de ambiente — não é "
    "trabalho de código; requer provisionamento de /opt/theo ou /srv/theo no "
    "host + instalação de unit files systemd + migração do dashboard + "
    "ownership. (2) Cross-repo: unit files vivem em `<sibling>`, sibling repo."
)

B022_ELAPSED = (
    "decisão T3 do sponsor sobre a fronteira de autenticação do motor (balas 1 e "
    "3 — muda `rules/pre-release-governance.md` T3 → MEET + ADR antes de código; "
    "um loop autônomo escrevendo isto seria o bypass que a governança existe "
    "para impedir) E acumulação de ~75 dias de série do `<service>`"
)

B154_LIVENESS = (
    "aguardando sessão LIVE per cleanroom-up-live-test-mandate.md. Balas 1, 2 e "
    "primeira metade da 3 CLOSED 2026-08-19. Segunda metade da bala 3 (um push "
    "real chega ao construtor com runtime não vazio) explicitamente marcada como "
    "'não é verificável desta sessão: exige o plano de build de pé'"
)

# ── The prose that may be delegated ────────────────────────────────────────────

B165_BINARY = (
    "aguardando decisão binária DoD bala 1: retire standalone-public (alinhando "
    "com rótulo legacy em docs/operations/local-public-dashboard.md:216 — "
    "canonical é dev-public) OU dá borda própria a ele. Se retire: change default "
    "de task infra:install:core-dashboard-only (taskfiles/infra.yml:141) para "
    "dev-public + update do doc. Severity baixa mas decisão pendente."
)

B060_STATUS = (
    "aguardando disposição de status: bala 1 foi refused-with-reason "
    "(arquitetura), bala 2 movida para B-061 (shipped), costura entregue em "
    "5b98a494f. Nenhuma transição canônica encaixa limpa — triaged→planned "
    "produziria plano vazio"
)


def test_provisioning_a_host_is_not_a_decision():
    """The item the first mechanism called 'review, resolvable'."""
    verdict = classify_wall(B139_HOST)
    assert verdict.klass is DecisionClass.ACCESS
    assert verdict.delegated is False


def test_waiting_for_a_data_series_is_not_a_decision():
    """Seventy-five days do not pass because authority was delegated."""
    verdict = classify_wall(B022_ELAPSED)
    assert verdict.delegated is False
    assert verdict.klass in (DecisionClass.ELAPSED, DecisionClass.GOVERNANCE)


def test_an_item_naming_autonomy_as_the_bypass_is_retained():
    """Delegation cannot authorize the thing it would be a bypass of."""
    verdict = classify_wall(B022_ELAPSED)
    assert verdict.delegated is False


def test_needing_a_standing_system_is_not_a_decision():
    verdict = classify_wall(B154_LIVENESS)
    assert verdict.klass is DecisionClass.LIVENESS
    assert verdict.delegated is False


def test_an_explicit_binary_choice_is_delegated():
    verdict = classify_wall(B165_BINARY)
    assert verdict.klass is DecisionClass.BINARY
    assert verdict.delegated is True


def test_a_status_disposition_is_delegated():
    verdict = classify_wall(B060_STATUS)
    assert verdict.klass is DecisionClass.STATUS
    assert verdict.delegated is True


def test_unrecognised_prose_stays_walled():
    """The fail-safe. No match is not consent."""
    verdict = classify_wall("aguardando algo que este mecanismo nunca viu antes")
    assert verdict.delegated is False
    assert verdict.klass is DecisionClass.UNCLASSIFIED


def test_empty_wall_is_not_delegated():
    assert classify_wall("").delegated is False


def test_access_wins_over_a_binary_word_in_the_same_sentence():
    """A wall that is BOTH a choice and an impediment is an impediment.

    B-080 asks for a confirmation AND waits on a commit batch; B-139 mentions a
    migration choice AND needs the host. Reading the delegable half first is how
    the first mechanism cleared a wall that had not moved.
    """
    mixed = "aguardando decisão binária: A OU B; e provisionamento de /opt/theo no host"
    verdict = classify_wall(mixed)
    assert verdict.delegated is False


# ── Walls that delegation DOES move ───────────────────────────────────────────

B137_SPONSOR = (
    "aguardando sponsor decision by design — o próprio item termina 'É decisão "
    "do sponsor, não minha' e a nota de 2026-08-19 delimita: 'O que continua "
    "sendo do sponsor: se 7,4% de jornada é certo para um produto cujo objeto É "
    "implantar'. Medição feita 3x"
)

B126_ENUMERATED = (
    "aguardando (1) MEET T2 e (2) decisão entre implementar canária agora ou "
    "aplicar bala 3 do DoD (defer com gatilho nomeado, padrão B-075)."
)

B146_OPTIONS = (
    "aguardando decisão operacional: prazo ADR-2026-05-12 venceu há 21 dias. "
    "Bala 2 explicitamente bloqueada — provisionar ConfigMap fará gate bloquear "
    "imediatamente. Três opções todas fora de código."
)

B079_REMEASURE = (
    "aguardando (1) commit do batch de kit-sync não commitado (91 arquivos dirty "
    "em .claude/**) e (2) re-medição dos 69 arquivos (services 51 + cmd 18)"
)

B001_MAP = (
    "decisão de sponsor sobre o mapa da metade `cell` (D2 da opportunity). A "
    "medição refutou `<workload>` → `cell-1`: bootstrap-cell-cc.sh:20-22 "
    "mostra que `cell-1` e `cell-2` já existem como ids de cell"
)


def test_sponsor_decision_is_delegated_once_the_sponsor_delegated():
    """B-137 says 'é decisão do sponsor' — and the sponsor handed it over."""
    verdict = classify_wall(B137_SPONSOR)
    assert verdict.delegated is True


def test_choice_between_enumerated_alternatives_is_delegated():
    """B-126: 'decisão entre X ou Y' names both sides, so it is a choice."""
    verdict = classify_wall(B126_ENUMERATED)
    assert verdict.klass is DecisionClass.OPTION
    assert verdict.delegated is True


def test_a_counted_set_of_options_is_delegated():
    """B-146: 'Três opções' — enumerated, therefore choosable."""
    assert classify_wall(B146_OPTIONS).delegated is True


def test_remeasurement_is_work_not_a_decision():
    """B-079 asks for a re-measurement. The system can measure."""
    verdict = classify_wall(B079_REMEASURE)
    assert verdict.klass is DecisionClass.MEASUREMENT
    assert verdict.delegated is True


def test_sponsor_map_decision_is_delegated():
    assert classify_wall(B001_MAP).delegated is True


def test_governance_still_beats_a_sponsor_decision_in_the_same_wall():
    """B-022 is a sponsor decision AND names autonomy as the bypass.

    Delegation cannot authorize the thing it would be a bypass of, so the
    governance clause must win over the sponsor-decision clause.
    """
    assert classify_wall(B022_ELAPSED).delegated is False


def test_rewrite_replaces_the_wall_and_names_the_decider():
    line = rewrite_wall(
        wall=B165_BINARY,
        decision="retire standalone-public",
        rationale="the doc already labels it legacy and names dev-public canonical",
    )
    assert "blocked_by" not in line
    assert "decided_by" in line
    assert "retire standalone-public" in line
    assert "legacy" in line


def test_rewrite_refuses_a_decision_with_no_rationale():
    """A wall removed with no reasoning in its place reads as a wall never written."""
    try:
        rewrite_wall(wall=B165_BINARY, decision="retire it", rationale="")
    except ValueError:
        return
    raise AssertionError("a decision with no rationale must be refused")

"""O gate de CVE deixa de depender de alguém lembrar de honrá-lo.

O DEFEITO QUE ISTO FIXA
-----------------------
`cycle-plan.md § Phase contracts` lista, entre os hard gates da fase, "no critical
CVE on a planned dependency" — e diz, na linha seguinte, o que nenhum outro gate do
ciclo precisa dizer:

    **The `deps-audit` gate is the one gate in this cycle nothing mechanizes.**
    Every other hard gate above is checked by a script that can fail the phase.
    This one is not.

`skills/deps-audit/SKILL.md § 35` repete: "Its gate is human-enforced, not
mechanized. `/plan-confidence` does not read this audit's verdict."

O motivo declarado era procedural: ligar o gate ESTENDE o contrato do
`plan-confidence-golden-rule.md`, e estender contrato exige registro. O registro
está escrito na golden rule (§ "Rules that cannot be bent"), no formato que este
repositório de fato usa — os arquivos sob `knowledge-base/adrs/` são gitignored e
não alcançam quem clona.

O QUE ESTE CHECK ASSEVERA, E O QUE ELE SE RECUSA A ASSEVERAR
-------------------------------------------------------------
Ele NÃO procura CVE: quem faz isso é `/deps-audit`, com os scanners. Ele lê o
VEREDITO que aquele run deixou em disco e o transforma em cap. Três estados:

| Estado                                              | Efeito |
|---|---|
| Plano não declara dependência nova                  | não se aplica |
| Declara, e nenhum relatório existe                  | soft floor (≤ 89) — ninguém verificou |
| Relatório com CVE CRITICAL/HIGH em dep declarada    | hard cap (≤ 49) |

Ausência de auditoria não vira "sem CVE". É a mesma regra do denominador zero em
D4 e do relatório de cobertura ilegível: não medido é não medido, nunca aprovado.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_deps_audit import check_deps_audit  # noqa: E402

_PLAN_WITH_DEPS = """# Plano

## Dependencies

| Package | Version | Why |
|---|---|---|
| `requests` | 2.31.0 | HTTP client for the webhook sender |

## Phase 1
"""

_PLAN_NO_DEPS = """# Plano

## Dependencies

(none — no new dependency)

## Phase 1
"""

_PLAN_WITHOUT_SECTION = """# Plano

## Phase 1

Nada sobre dependências.
"""


def _plan(root: Path, body: str, slug: str = "demo") -> Path:
    plans = root / "knowledge-base" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    path = plans / f"{slug}-plan.md"
    path.write_text(body, encoding="utf-8")
    return path


def _audit(root: Path, verdict: str, slug: str = "demo", caps: str = "") -> Path:
    audits = root / "knowledge-base" / "audits"
    audits.mkdir(parents=True, exist_ok=True)
    path = audits / f"{slug}-deps-audit-2026-08-26.md"
    path.write_text(
        f"# Deps Audit: {slug}\n\n**Date:** 2026-08-26\n**Mode:** plan-bound:{slug}\n"
        f"**Verdict:** {verdict}\n**Hard caps triggered:** {caps or '_none_'}\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Quando o check NÃO se aplica
# ---------------------------------------------------------------------------

def test_a_plan_with_no_dependencies_section_is_untouched(tmp_path: Path) -> None:
    plan = _plan(tmp_path, _PLAN_WITHOUT_SECTION)
    report = check_deps_audit(plan)
    assert report.applies is False
    assert report.hard_cap is False
    assert report.soft_floor is False


def test_an_explicit_none_is_untouched(tmp_path: Path) -> None:
    """`(none — no new dependency)` é uma declaração, e o gate a respeita."""
    plan = _plan(tmp_path, _PLAN_NO_DEPS)
    report = check_deps_audit(plan)
    assert report.applies is False


# ---------------------------------------------------------------------------
# Quando ninguém auditou
# ---------------------------------------------------------------------------

def test_declared_dependencies_without_an_audit_are_a_soft_floor(tmp_path: Path) -> None:
    """Não posso afirmar que há CVE. Posso afirmar que ninguém olhou."""
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    report = check_deps_audit(plan)
    assert report.applies is True
    assert report.soft_floor is True
    assert report.hard_cap is False
    assert report.stable_id == "soft_floor_deps_audit_missing"
    assert "requests" in " ".join(report.reasons)


# ---------------------------------------------------------------------------
# Quando o audit existe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("verdict", ["PASS", "PASS_WITH_CAVEATS"])
def test_a_clean_audit_clears_the_gate(tmp_path: Path, verdict: str) -> None:
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, verdict)
    report = check_deps_audit(plan)
    assert report.applies is True
    assert report.hard_cap is False
    assert report.soft_floor is False


def test_an_insecure_audit_is_a_hard_cap(tmp_path: Path) -> None:
    """O gate que `cycle-plan.md` declarava e nada cobrava."""
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, "FAIL_INSECURE", caps="critical_cve_in_declared_dep")
    report = check_deps_audit(plan)
    assert report.hard_cap is True
    assert report.stable_id == "deps_audit_insecure"
    assert "FAIL_INSECURE" in " ".join(report.reasons)


def test_a_medium_audit_is_a_soft_floor(tmp_path: Path) -> None:
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, "FAIL_MEDIUM")
    report = check_deps_audit(plan)
    assert report.hard_cap is False
    assert report.soft_floor is True
    assert report.stable_id == "soft_floor_deps_audit_medium"


def test_an_invalid_audit_is_a_hard_cap(tmp_path: Path) -> None:
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, "INVALID_PLAN_DEPS")
    assert check_deps_audit(plan).hard_cap is True


def test_an_audit_with_no_verdict_line_does_not_count_as_clean(tmp_path: Path) -> None:
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    audits = tmp_path / "knowledge-base" / "audits"
    audits.mkdir(parents=True, exist_ok=True)
    (audits / "demo-deps-audit-2026-08-26.md").write_text("# vazio\n", encoding="utf-8")

    report = check_deps_audit(plan)

    assert report.soft_floor is True, "relatório ilegível é ausência de veredito"


def test_the_newest_audit_wins(tmp_path: Path) -> None:
    """Auditar de novo depois de bumpar a dependência tem de contar."""
    plan = _plan(tmp_path, _PLAN_WITH_DEPS)
    _audit(tmp_path, "FAIL_INSECURE")
    audits = tmp_path / "knowledge-base" / "audits"
    (audits / "demo-deps-audit-2026-08-27.md").write_text(
        "**Verdict:** PASS\n", encoding="utf-8")

    assert check_deps_audit(plan).hard_cap is False


@pytest.mark.parametrize("layout", ["knowledge-base", ".claude/knowledge-base"])
def test_both_install_layouts_are_searched(tmp_path: Path, layout: str) -> None:
    plans = tmp_path / layout / "plans"
    plans.mkdir(parents=True)
    plan = plans / "demo-plan.md"
    plan.write_text(_PLAN_WITH_DEPS, encoding="utf-8")
    audits = tmp_path / layout / "audits"
    audits.mkdir(parents=True)
    (audits / "demo-deps-audit-2026-08-26.md").write_text("**Verdict:** PASS\n", encoding="utf-8")

    assert check_deps_audit(plan).hard_cap is False
    assert check_deps_audit(plan).soft_floor is False

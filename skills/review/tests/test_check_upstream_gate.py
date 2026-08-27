"""A pré-condição do `/review` deixa de depender de alguém lembrar dela.

O DEFEITO QUE ISTO FIXA
-----------------------
`code-quality-golden-rule.md § 1` diz que `FAIL_SOFT` só avança para o `/review`
com "explicit ADR dismissing each soft cap", e `cycle-review.md § Pre-conditions`
repete a exigência. Grep nos scripts do `/review` em 2026-08-26: zero. A
verificação inteira era prosa em `SKILL.md`:

    # /code-quality audit exists AND verdict ∈ {PASS, PASS_WITH_CAVEATS}
    test -f .claude/knowledge-base/audits/{slug}-code-quality-*.md

Um `test -f` que o agente precisa lembrar de executar não é um gate — é uma nota.
E o ADR, que é a peça que torna um soft cap dispensável, não era procurado por
ninguém: bastava afirmar que existia.

POR QUE ISTO VIVE NO CONSOLIDADOR, E NÃO NUM PASSO À PARTE
-----------------------------------------------------------
Um passo separado tem a mesma fragilidade da prosa: alguém tem de chamá-lo. O
veredito do `/review` já é calculado por `consolidate_findings.py`, então a
pré-condição entra como um BLOCKER sintético no mesmo cálculo. Um veredito que
ignora o upstream deixa de ser possível, em vez de deixar de ser recomendado.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_upstream_gate import check_upstream_gate


def _audit(root: Path, slug: str, verdict: str, soft: str = "_none_", hard: str = "_none_") -> Path:
    audits = root / "knowledge-base" / "audits"
    audits.mkdir(parents=True, exist_ok=True)
    path = audits / f"{slug}-code-quality-2026-08-26.md"
    path.write_text(
        f"# Code-quality audit — {slug}\n\n"
        f"**Verdict:** {verdict}\n"
        f"**Score cap:** 70\n"
        f"**Hard caps triggered:** {hard}\n"
        f"**Soft caps triggered:** {soft}\n",
        encoding="utf-8",
    )
    return path


def _adr(root: Path, name: str, body: str) -> Path:
    adrs = root / "knowledge-base" / "adrs"
    adrs.mkdir(parents=True, exist_ok=True)
    path = adrs / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Os caminhos que precisam BLOQUEAR
# ---------------------------------------------------------------------------

def test_a_missing_audit_blocks(tmp_path: Path) -> None:
    """Sem audit, o `/review` estaria auditando código que ninguém varreu."""
    findings = check_upstream_gate(tmp_path, "demo")
    assert len(findings) == 1
    assert findings[0]["severity"] == "BLOCKER"
    assert "no /code-quality audit" in findings[0]["title"]


def test_fail_hard_blocks(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "FAIL_HARD", hard="dead_code_unallowlisted_python")
    findings = check_upstream_gate(tmp_path, "demo")
    assert len(findings) == 1
    assert findings[0]["severity"] == "BLOCKER"
    assert "FAIL_HARD" in findings[0]["title"]


def test_invalid_blocks(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "INVALID")
    assert check_upstream_gate(tmp_path, "demo")[0]["severity"] == "BLOCKER"


def test_fail_soft_without_any_adr_blocks(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "FAIL_SOFT", soft="soft_cap_orphan_export_python")
    findings = check_upstream_gate(tmp_path, "demo")
    assert len(findings) == 1
    assert findings[0]["severity"] == "BLOCKER"
    assert "soft_cap_orphan_export_python" in findings[0]["evidence"]


def test_an_adr_that_dismisses_only_one_of_two_caps_still_blocks(tmp_path: Path) -> None:
    """"Cada soft cap" é a leitura estrita, e é a que fecha o buraco.

    Com dois caps e um ADR que nomeia um, a leitura frouxa ("existe ADR") aprova —
    e o cap que ninguém examinou passa junto, carona no que foi examinado.
    """
    _audit(tmp_path, "demo", "FAIL_SOFT",
           soft="soft_cap_orphan_export_python, soft_cap_mutation_score_low_python")
    _adr(tmp_path, "0007-orphans", "# ADR: exports órfãos\n\nsoft_cap_orphan_export_python é aceito porque ...\n")

    findings = check_upstream_gate(tmp_path, "demo")

    assert len(findings) == 1
    assert "soft_cap_mutation_score_low_python" in findings[0]["evidence"]
    assert "soft_cap_orphan_export_python" not in findings[0]["evidence"]


# ---------------------------------------------------------------------------
# Os caminhos que precisam PASSAR
# ---------------------------------------------------------------------------

def test_pass_produces_no_finding(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "PASS")
    assert check_upstream_gate(tmp_path, "demo") == []


def test_pass_with_caveats_produces_no_finding(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "PASS_WITH_CAVEATS")
    assert check_upstream_gate(tmp_path, "demo") == []


def test_fail_soft_with_an_adr_per_cap_passes(tmp_path: Path) -> None:
    _audit(tmp_path, "demo", "FAIL_SOFT",
           soft="soft_cap_orphan_export_python, soft_cap_mutation_score_low_python")
    _adr(tmp_path, "0007-caps", "# ADR\n\nDispensamos soft_cap_orphan_export_python e "
                                "soft_cap_mutation_score_low_python porque ...\n")
    assert check_upstream_gate(tmp_path, "demo") == []


def test_the_plans_adr_section_counts_as_the_dismissal(tmp_path: Path) -> None:
    """O ADR pode viver no plano — é onde `/to-plan` os escreve."""
    _audit(tmp_path, "demo", "FAIL_SOFT", soft="soft_cap_orphan_export_python")
    plans = tmp_path / "knowledge-base" / "plans"
    plans.mkdir(parents=True)
    (plans / "demo-plan.md").write_text(
        "# Plano\n\n## ADRs\n\n- soft_cap_orphan_export_python: aceito porque ...\n", encoding="utf-8")

    assert check_upstream_gate(tmp_path, "demo") == []


def test_the_newest_audit_wins(tmp_path: Path) -> None:
    """Reauditar depois de corrigir tem de contar; o audit velho não pode bloquear."""
    _audit(tmp_path, "demo", "FAIL_HARD", hard="dead_code_unallowlisted_python")
    audits = tmp_path / "knowledge-base" / "audits"
    (audits / "demo-code-quality-2026-08-27.md").write_text(
        "**Verdict:** PASS\n**Hard caps triggered:** _none_\n**Soft caps triggered:** _none_\n",
        encoding="utf-8")

    assert check_upstream_gate(tmp_path, "demo") == []


# ---------------------------------------------------------------------------
# Robustez
# ---------------------------------------------------------------------------

def test_an_audit_without_a_verdict_line_blocks(tmp_path: Path) -> None:
    """Um relatório ilegível é ausência de veredito, não veredito favorável."""
    audits = tmp_path / "knowledge-base" / "audits"
    audits.mkdir(parents=True)
    (audits / "demo-code-quality-2026-08-26.md").write_text("# vazio\n", encoding="utf-8")

    findings = check_upstream_gate(tmp_path, "demo")
    assert findings[0]["severity"] == "BLOCKER"
    assert "unreadable" in findings[0]["title"]


@pytest.mark.parametrize("layout", ["knowledge-base", ".claude/knowledge-base"])
def test_both_install_layouts_are_searched(tmp_path: Path, layout: str) -> None:
    """O kit vive em dois layouts, e um gate que só enxerga um deles é meio gate."""
    audits = tmp_path / layout / "audits"
    audits.mkdir(parents=True)
    (audits / "demo-code-quality-2026-08-26.md").write_text(
        "**Verdict:** PASS\n**Hard caps triggered:** _none_\n**Soft caps triggered:** _none_\n",
        encoding="utf-8")

    assert check_upstream_gate(tmp_path, "demo") == []

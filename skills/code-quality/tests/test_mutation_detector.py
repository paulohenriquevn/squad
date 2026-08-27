"""D4 — mutation testing: os testes DETECTAM defeito, ou apenas passam?

O DEFEITO QUE ISTO FIXA
-----------------------
`code-quality-golden-rule.md § 5` lista D4 como contrato LOCKED — mutmut para
Python, Stryker para TypeScript, pisos em 60 e 80. Os quatro detectores
devolviam a mesma coisa:

    return self.unavailable("d4", "mutation_low", "mutmut integration is not configured")

Como `unavailable()` emite SOFT_CAP, `PASS` era inalcançável em qualquer projeto
e o `/implement` convertia o soft cap em WARN. O gate que responde à única
pergunta que cobertura não responde — *os testes detectam defeito?* — estava
declarado, versionado, documentado, e não rodava.

A PROVA DE QUE O GATE VALE
--------------------------
Medido em 2026-08-26 com mutmut 3.5 num módulo de 4 linhas coberto por um teste
tautológico (`assert isinstance(desconto(100, 10), float)`):

    {"killed": 1, "survived": 7, "total": 8, ...}   -> score 12.5%

Cobertura de linha: 100%. É exatamente o teste que passa sem provar nada, e
nenhum outro detector desta pilha o enxerga.

DOIS COMPORTAMENTOS DO MUTMUT QUE O DETECTOR NÃO PODE IGNORAR
-------------------------------------------------------------
1. **Ele sai 0 mesmo quando não rodou nada.** Com os testes fora do padrão que
   ele coleta, a saída traz `failed to collect stats. runner returned 5` e o
   processo encerra com sucesso. Um detector que lesse o exit code registraria
   um run que não aconteceu — o mesmo defeito que o gate de cobertura tinha ao
   transformar exit code em medição.
2. **Ele nem carrega sem `source_paths` configurado.** `mutmut --help` fora de um
   projeto configurado levanta `FileNotFoundError` na importação. A ausência de
   configuração é, portanto, indistinguível de ausência da ferramenta se o
   detector só olhar para a exceção — e as duas exigem ações diferentes de quem
   lê o relatório.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.detectors import _mutation

#: Saída real de `mutmut export-cicd-stats`, capturada 2026-08-26 (mutmut 3.5).
_STATS_STRONG = {"killed": 3, "survived": 0, "total": 3, "no_tests": 0, "skipped": 0,
                 "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}
_STATS_WEAK = {"killed": 1, "survived": 7, "total": 8, "no_tests": 0, "skipped": 0,
               "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}


def _python_project(root: Path, stats: dict | None) -> Path:
    (root / "calc").mkdir(parents=True, exist_ok=True)
    (root / "calc" / "core.py").write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
    (root / "setup.cfg").write_text("[mutmut]\nsource_paths=calc/\n", encoding="utf-8")
    if stats is not None:
        (root / "mutants").mkdir(exist_ok=True)
        (root / "mutants" / "mutmut-cicd-stats.json").write_text(json.dumps(stats), encoding="utf-8")
    return root


def _runner_ok(*_args, **_kwargs) -> tuple[int, str, str]:
    return 0, "", ""


def _runner_missing(*_args, **_kwargs):
    raise FileNotFoundError("mutmut")


# ---------------------------------------------------------------------------
# Score -> severidade
# ---------------------------------------------------------------------------

def test_a_strong_suite_produces_no_capping_finding(tmp_path: Path) -> None:
    _python_project(tmp_path, _STATS_STRONG)
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert [f for f in findings if f.severity in ("SOFT_CAP", "SOFT_FLOOR", "HARD")] == []
    info = [f for f in findings if f.severity == "INFO"]
    assert len(info) == 1, "o score medido tem de aparecer no relatório mesmo quando passa"
    assert "100.0%" in info[0].message


def test_a_tautological_suite_is_capped(tmp_path: Path) -> None:
    """O caso medido: cobertura de linha 100%, score de mutação 12.5%."""
    _python_project(tmp_path, _STATS_WEAK)
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    caps = [f for f in findings if f.severity == "SOFT_CAP"]
    assert len(caps) == 1
    assert "12.5%" in caps[0].message
    assert caps[0].allowlist_key.endswith("soft_cap_mutation_score_low_python")


def test_a_medium_score_is_a_floor_not_a_cap(tmp_path: Path) -> None:
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 7, "survived": 3, "total": 10})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    floors = [f for f in findings if f.severity == "SOFT_FLOOR"]
    assert len(floors) == 1
    assert "70.0%" in floors[0].message


def test_a_timeout_counts_as_detected(tmp_path: Path) -> None:
    """Um mutante que trava o teste FOI detectado — a suíte reagiu à mutação."""
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 6, "timeout": 2, "survived": 2, "total": 10})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert "80.0%" in [f.message for f in findings][0]


def test_skipped_mutants_leave_the_denominator(tmp_path: Path) -> None:
    """`skipped` é exclusão deliberada; mantê-los no denominador puniria a decisão."""
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 5, "survived": 0, "skipped": 5, "total": 10})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert "100.0%" in [f.message for f in findings][0]


def test_uncovered_mutants_stay_in_the_denominator(tmp_path: Path) -> None:
    """`no_tests` é mutante que teste nenhum alcança — não detectado, por definição."""
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 5, "survived": 0, "no_tests": 5, "total": 10})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    caps = [f for f in findings if f.severity == "SOFT_CAP"]
    assert len(caps) == 1
    assert "50.0%" in caps[0].message


# ---------------------------------------------------------------------------
# Os modos de falha que não podem virar verde
# ---------------------------------------------------------------------------

def test_zero_mutants_is_never_a_perfect_score(tmp_path: Path) -> None:
    """Denominador zero é ausência de medição, não medição perfeita.

    100% de zero mutantes é o pior resultado possível: verde absoluto sem que
    nada tenha sido medido.
    """
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 0, "survived": 0, "total": 0})
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "no mutants" in findings[0].message


def test_a_run_that_produced_no_stats_is_unavailable_not_clean(tmp_path: Path) -> None:
    """Medido: mutmut sai 0 mesmo quando o pytest não coletou teste nenhum.

    Sem o arquivo de stats não houve medição — e o detector tem de dizer isso em
    vez de herdar o exit code como veredito.
    """
    _python_project(tmp_path, None)
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)
    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "auditor unavailable" in findings[0].message
    assert "no stats file" in findings[0].message


def test_a_missing_tool_is_reported_as_such(tmp_path: Path) -> None:
    _python_project(tmp_path, None)
    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_missing)
    assert len(findings) == 1
    assert "not found in PATH" in findings[0].message


def test_a_project_without_mutation_config_says_so(tmp_path: Path) -> None:
    """Sem `[mutmut] source_paths`, a ferramenta nem carrega — e a ação de quem lê
    o relatório é configurar, não instalar."""
    (tmp_path / "calc").mkdir()
    (tmp_path / "calc" / "core.py").write_text("def f(x):\n    return x\n", encoding="utf-8")

    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)

    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "no mutation config" in findings[0].message
    assert "source_paths" in findings[0].message


def test_a_corrupt_stats_file_is_unavailable_not_zero(tmp_path: Path) -> None:
    _python_project(tmp_path, None)
    (tmp_path / "mutants").mkdir(exist_ok=True)
    (tmp_path / "mutants" / "mutmut-cicd-stats.json").write_text("{nao é json", encoding="utf-8")

    findings = _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok)

    assert findings[0].severity == "SOFT_CAP"
    assert "auditor unavailable" in findings[0].message


# ---------------------------------------------------------------------------
# TypeScript — schema mutation-testing-elements (Stryker)
# ---------------------------------------------------------------------------

def _stryker_project(root: Path, statuses: list[str] | None) -> Path:
    (root / "package.json").write_text('{"name": "p"}', encoding="utf-8")
    (root / "stryker.config.json").write_text('{"testRunner": "jest"}', encoding="utf-8")
    if statuses is not None:
        report = (root / "reports" / "mutation")
        report.mkdir(parents=True, exist_ok=True)
        (report / "mutation.json").write_text(json.dumps({
            "files": {"src/a.ts": {"mutants": [{"id": str(i), "status": s}
                                                for i, s in enumerate(statuses)]}}
        }), encoding="utf-8")
    return root


def test_typescript_reads_the_stryker_report(tmp_path: Path) -> None:
    _stryker_project(tmp_path, ["Killed", "Killed", "Survived", "Timeout"])
    findings = _mutation.detect_mutation_score("typescript", tmp_path, runner=_runner_ok)
    assert "75.0%" in [f.message for f in findings][0]


def test_typescript_ignored_mutants_leave_the_denominator(tmp_path: Path) -> None:
    _stryker_project(tmp_path, ["Killed", "Ignored", "CompileError"])
    findings = _mutation.detect_mutation_score("typescript", tmp_path, runner=_runner_ok)
    assert "100.0%" in [f.message for f in findings][0]


def test_typescript_without_stryker_config_says_so(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name": "p"}', encoding="utf-8")
    findings = _mutation.detect_mutation_score("typescript", tmp_path, runner=_runner_ok)
    assert "no mutation config" in findings[0].message


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["rust", "go"])
def test_deferred_languages_declare_the_deferral(tmp_path: Path, language: str) -> None:
    """A golden rule § 5 declara Rust e Go adiados. Adiado e declarado é honesto;
    adiado e apresentado como implementado é o defeito que este módulo fecha."""
    findings = _mutation.detect_mutation_score(language, tmp_path, runner=_runner_ok)
    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "deferred" in findings[0].message


def test_floors_come_from_the_caller_not_from_a_constant(tmp_path: Path) -> None:
    """`code-quality-thresholds.txt` documenta `mutation.score_floor_low/high`.
    Um piso hard-coded faria o arquivo mentir sobre ser configurável."""
    _python_project(tmp_path, {**_STATS_STRONG, "killed": 7, "survived": 3, "total": 10})

    strict = _mutation.detect_mutation_score(
        "python", tmp_path, floor_low=75, floor_high=95, runner=_runner_ok)
    lenient = _mutation.detect_mutation_score(
        "python", tmp_path, floor_low=50, floor_high=60, runner=_runner_ok)

    assert [f.severity for f in strict] == ["SOFT_CAP"], "70% abaixo de um piso de 75 é cap"
    assert [f.severity for f in lenient] == ["INFO"], "70% acima de um piso de 60 passa"


def test_findings_carry_a_wellformed_allowlist_key(tmp_path: Path) -> None:
    _python_project(tmp_path, _STATS_WEAK)
    for finding in _mutation.detect_mutation_score("python", tmp_path, runner=_runner_ok):
        assert finding.allowlist_key.count("|") == 3, finding.allowlist_key

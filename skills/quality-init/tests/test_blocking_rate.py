"""A calibração passa a dizer QUANTO do código ela bloquearia.

O DEFEITO QUE ISTO FIXA
-----------------------
`SKILL.md` promete: "calibrates adaptive thresholds ... from the project's actual
p90 metrics — never generic defaults", e § "Why p90 and not p50 or max?" explica
que o p90 existe para o gate não nascer reprovando o código que já está lá.

Ele nasce, e ninguém media. Medido 2026-08-26 rodando `/quality-init` contra este
repositório e depois passando cada arquivo pelo hook gerado:

    limiares: complexity=10, function_lines=29, nesting=3, params=4, file_lines=367
    resultado: 156 de 256 arquivos versionados seriam BLOQUEADOS (61%)

A aritmética é simples e o p90 não a cobre: ele é calculado POR MÉTRICA — o
percentil 90 das funções do projeto — enquanto o gate reprova um ARQUIVO quando
QUALQUER função dele excede QUALQUER limiar. Um arquivo com trinta funções tem
trinta chances independentes de conter uma das 10% piores, e cinco métricas
multiplicam isso. p90 por função não é p90 por arquivo, e a diferença é a distância
entre um gate que nasce verde e um que trava dois terços do repositório.

Um gate que nasce vermelho é desligado na primeira hora, e o que sobra é a pior das
duas situações: o hook no `settings.json`, a confiança de que ele protege alguma
coisa, e uma flag de bypass no dedo de quem trabalha.

Isto não conserta a calibração — conserta o SILÊNCIO sobre ela. Quem liga o gate
passa a saber o que está ligando.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from init_quality_gates import ThresholdCalibration, measure_blocking_rate

_CLEAN = """def soma(a, b):
    return a + b
"""

#: Viola APENAS aninhamento — dois parâmetros, corpo curto. Isolar a métrica é o
#: ponto: um fixture que viola três limiares de uma vez não consegue provar que a
#: taxa reage ao limiar que o teste está variando.
_COMPLEX = """def decide(a, b):
    if a:
        if b:
            if a > b:
                return 1
    return 0
"""


def _calibration(**over) -> ThresholdCalibration:
    values = {
        "max_complexity": 10,
        "max_function_lines": 29,
        "max_nesting_depth": 3,
        "max_parameters": 4,
        "max_file_lines": 367,
        "duplicate_min_lines": 4,
    }
    values.update(over)
    return ThresholdCalibration(**values)


def test_a_clean_project_reports_zero(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text(_CLEAN, encoding="utf-8")
    (tmp_path / "b.py").write_text(_CLEAN, encoding="utf-8")

    rate = measure_blocking_rate(tmp_path, _calibration())

    assert rate.files_measured == 2
    assert rate.files_blocked == 0
    assert rate.percent == 0.0


def test_a_violating_file_is_counted(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text(_CLEAN, encoding="utf-8")
    (tmp_path / "deep.py").write_text(_COMPLEX, encoding="utf-8")

    rate = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=2))

    assert rate.files_measured == 2
    assert rate.files_blocked == 1
    assert rate.percent == 50.0
    assert "deep.py" in " ".join(rate.worst_offenders)


def test_the_rate_reacts_to_the_thresholds(tmp_path: Path) -> None:
    """O ponto do número: ele muda quando a calibração muda."""
    (tmp_path / "deep.py").write_text(_COMPLEX, encoding="utf-8")

    strict = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=2))
    lenient = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=9))

    assert strict.files_blocked == 1
    assert lenient.files_blocked == 0


def test_an_empty_project_is_not_a_perfect_score(tmp_path: Path) -> None:
    """Zero arquivos medidos é ausência de medição — a mesma regra do denominador
    zero em D4 e do relatório de cobertura ilegível."""
    rate = measure_blocking_rate(tmp_path, _calibration())
    assert rate.files_measured == 0
    assert rate.percent is None
    assert rate.verdict == "NOT_MEASURED"


def test_a_low_rate_is_reported_as_ready(tmp_path: Path) -> None:
    for i in range(20):
        (tmp_path / f"f{i}.py").write_text(_CLEAN, encoding="utf-8")
    assert measure_blocking_rate(tmp_path, _calibration()).verdict == "READY"


def test_a_high_rate_refuses_to_call_the_calibration_ready(tmp_path: Path) -> None:
    """O veredito é o que impede o relatório de dizer 'calibrado' sobre um gate
    que reprova a maior parte do código que ele deveria proteger."""
    for i in range(10):
        (tmp_path / f"f{i}.py").write_text(_COMPLEX, encoding="utf-8")

    rate = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=2))

    assert rate.percent == 100.0
    assert rate.verdict == "TOO_STRICT"
    assert "desligado" in rate.advice or "disabled" in rate.advice


def test_test_files_are_excluded_when_asked(tmp_path: Path) -> None:
    """`--skip-tests` já existe na calibração; a taxa mede o mesmo conjunto."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(_CLEAN, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(_COMPLEX, encoding="utf-8")

    rate = measure_blocking_rate(tmp_path, _calibration(max_nesting_depth=2), skip_tests=True)

    assert rate.files_measured == 1
    assert rate.files_blocked == 0

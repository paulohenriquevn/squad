"""Metric calibration — derive thresholds from the project's actual metrics."""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from pathlib import Path

from lib.detect import SKIP_DIRS, _log, _walk_source_files

# ── Constants ─────────────────────────────────────────────────────────

# Minimum floors — thresholds never go below these
FLOOR_COMPLEXITY = 10
FLOOR_FUNCTION_LINES = 20
FLOOR_NESTING_DEPTH = 3
FLOOR_PARAMETERS = 4
FLOOR_FILE_LINES = 300

# Strict mode values (match industry standard recommendations)
STRICT_COMPLEXITY = 10
STRICT_FUNCTION_LINES = 20
STRICT_NESTING_DEPTH = 3
STRICT_PARAMETERS = 4
STRICT_FILE_LINES = 300


# ── Data classes ──────────────────────────────────────────────────────


@dataclass
class ThresholdCalibration:
    max_complexity: int = FLOOR_COMPLEXITY
    max_function_lines: int = FLOOR_FUNCTION_LINES
    max_nesting_depth: int = FLOOR_NESTING_DEPTH
    max_parameters: int = FLOOR_PARAMETERS
    max_file_lines: int = FLOOR_FILE_LINES
    duplicate_min_lines: int = 4
    duplicate_min_occurrences: int = 2

    # Source tracking
    complexity_p90: int | None = None
    function_lines_p90: int | None = None
    nesting_depth_p90: int | None = None
    parameters_p90: int | None = None
    file_lines_p90: int | None = None
    sample_count: int = 0


# ── Utility ───────────────────────────────────────────────────────────


def _percentile(values: list[int | float], pct: int) -> int:
    """Compute the p-th percentile. Returns int (ceiling)."""
    if not values:
        return 0
    sorted_vals = sorted(values)
    idx = math.ceil(len(sorted_vals) * pct / 100) - 1
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return math.ceil(sorted_vals[idx])


# ── Stage 6: calibrate_thresholds ────────────────────────────────────


def _measure_python_metrics(files: list[Path]) -> dict[str, list[int]]:
    """Measure complexity, function length, nesting, and params from Python files."""
    metrics: dict[str, list[int]] = {
        "complexity": [],
        "function_lines": [],
        "nesting_depth": [],
        "parameters": [],
        "file_lines": [],
    }

    for f in files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = source.splitlines()
        metrics["file_lines"].append(len(lines))

        try:
            tree = ast.parse(source, filename=str(f))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Complexity
            complexity = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.Assert)):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1
                elif isinstance(child, ast.comprehension):
                    complexity += 1 + len(child.ifs)
            metrics["complexity"].append(complexity)

            # Function length
            if hasattr(node, "end_lineno") and node.end_lineno is not None:
                length = node.end_lineno - node.lineno + 1
                metrics["function_lines"].append(length)

            # Nesting
            def max_nesting(n: ast.AST, depth: int = 0) -> int:
                md = depth
                nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)
                for c in ast.iter_child_nodes(n):
                    if isinstance(c, nesting_types):
                        md = max(md, max_nesting(c, depth + 1))
                    else:
                        md = max(md, max_nesting(c, depth))
                return md

            metrics["nesting_depth"].append(max_nesting(node))

            # Parameters
            args = node.args
            all_args = args.posonlyargs + args.args + args.kwonlyargs
            count = len(all_args)
            if all_args and all_args[0].arg in ("self", "cls"):
                count -= 1
            if args.vararg:
                count += 1
            if args.kwarg:
                count += 1
            metrics["parameters"].append(count)

    return metrics


def calibrate_thresholds(
    target: str,
    strict: bool = False,
    skip_tests: bool = False,
    verbose: bool = False,
) -> ThresholdCalibration:
    """Calibrate thresholds from actual project metrics."""
    if strict:
        _log("Using strict thresholds (ignoring project metrics)", verbose)
        return ThresholdCalibration(
            max_complexity=STRICT_COMPLEXITY,
            max_function_lines=STRICT_FUNCTION_LINES,
            max_nesting_depth=STRICT_NESTING_DEPTH,
            max_parameters=STRICT_PARAMETERS,
            max_file_lines=STRICT_FILE_LINES,
        )

    files = _walk_source_files(target, SKIP_DIRS, skip_test_dirs=skip_tests)
    py_files = [f for f in files if f.suffix.lower() == ".py"]

    if not py_files:
        # No Python files — measure file lengths only, use floors for the rest
        all_files = files
        file_lines: list[int] = []
        for f in all_files:
            try:
                file_lines.append(len(f.read_text(encoding="utf-8", errors="replace").splitlines()))
            except OSError:
                pass

        p90_file = _percentile(file_lines, 90) if file_lines else 0
        cal = ThresholdCalibration(
            max_file_lines=max(FLOOR_FILE_LINES, p90_file),
            file_lines_p90=p90_file if file_lines else None,
            sample_count=len(all_files),
        )
        _log(f"No Python files — file_lines p90={p90_file}, using floors for function metrics", verbose)
        return cal

    metrics = _measure_python_metrics(py_files)

    p90_complexity = _percentile(metrics["complexity"], 90)
    p90_func_lines = _percentile(metrics["function_lines"], 90)
    p90_nesting = _percentile(metrics["nesting_depth"], 90)
    p90_params = _percentile(metrics["parameters"], 90)
    p90_file_lines = _percentile(metrics["file_lines"], 90)

    cal = ThresholdCalibration(
        max_complexity=max(FLOOR_COMPLEXITY, p90_complexity),
        max_function_lines=max(FLOOR_FUNCTION_LINES, p90_func_lines),
        max_nesting_depth=max(FLOOR_NESTING_DEPTH, p90_nesting),
        max_parameters=max(FLOOR_PARAMETERS, p90_params),
        max_file_lines=max(FLOOR_FILE_LINES, p90_file_lines),
        complexity_p90=p90_complexity,
        function_lines_p90=p90_func_lines,
        nesting_depth_p90=p90_nesting,
        parameters_p90=p90_params,
        file_lines_p90=p90_file_lines,
        sample_count=len(py_files),
    )

    _log(
        f"Calibrated from {len(py_files)} Python files: "
        f"complexity p90={p90_complexity}, func_lines p90={p90_func_lines}, "
        f"nesting p90={p90_nesting}, params p90={p90_params}, "
        f"file_lines p90={p90_file_lines}",
        verbose,
    )

    return cal


# ---------------------------------------------------------------------------
# Taxa de bloqueio — o número que faltava para a calibração ser verificável
# ---------------------------------------------------------------------------

#: Acima disto o gate reprova código demais para ser ligado como está. Não é um
#: percentil observado: é o ponto em que a experiência de quem trabalha vira
#: "todo edit é bloqueado", e um gate assim é desligado — o que deixa o hook no
#: settings, a confiança de que ele protege algo, e um bypass no dedo de quem usa.
BLOCKING_RATE_CEILING = 10.0

#: Abaixo disto o gate nasce praticamente verde e só reage ao que PIORA, que é o
#: comportamento que a calibração p90 promete.
BLOCKING_RATE_READY = 5.0


@dataclass
class BlockingRate:
    """Quanto do código existente o gate calibrado reprovaria, hoje."""

    files_measured: int = 0
    files_blocked: int = 0
    percent: float | None = None
    verdict: str = "NOT_MEASURED"
    advice: str = ""
    worst_offenders: tuple[str, ...] = ()


def _file_violates(path: Path, thresholds: "ThresholdCalibration") -> bool:
    """True quando qualquer métrica do arquivo excede o limiar correspondente.

    Mede com `_measure_python_metrics`, o MESMO instrumento que produziu os p90 da
    calibração — assim a taxa é exata para os números que a calibração usou. O que
    esta conta NÃO cobre é a duplicação, que o hook gerado também checa e a
    calibração nunca mediu: a taxa real pode ser um pouco maior que a reportada, e
    nunca menor.
    """
    metrics = _measure_python_metrics([path])
    checks = (
        ("complexity", thresholds.max_complexity),
        ("function_lines", thresholds.max_function_lines),
        ("nesting_depth", thresholds.max_nesting_depth),
        ("parameters", thresholds.max_parameters),
        ("file_lines", thresholds.max_file_lines),
    )
    for key, limit in checks:
        values = metrics.get(key) or []
        if values and max(values) > limit:
            return True
    return False


def measure_blocking_rate(
    target: str | Path,
    thresholds: "ThresholdCalibration",
    skip_tests: bool = False,
) -> BlockingRate:
    """Measure how much of the EXISTING code the calibrated gate would block.

    `SKILL.md § Why p90 and not p50 or max?` explains that the adaptive calibration
    exists so the gate does not start out rejecting the code already in the repo. It
    was never checked. Measured on this repository 2026-08-26 — thresholds
    complexity=10, function_lines=29, nesting=3, params=4, file_lines=367 — **156 of
    256 tracked files would be blocked**.

    The arithmetic the p90 does not cover: it is computed PER METRIC, over the
    project's functions, while the gate rejects a FILE when ANY of its functions
    exceeds ANY threshold. A file with thirty functions gets thirty independent
    chances of holding one of the worst 10%, and five metrics multiply that. p90 per
    function is not p90 per file.

    This does not fix the calibration. It ends the silence about it: whoever turns
    the gate on now knows what they are turning on.
    """
    files = _walk_source_files(str(target), SKIP_DIRS, skip_test_dirs=skip_tests)
    py_files = [f for f in files if f.suffix.lower() == ".py"]
    if not py_files:
        return BlockingRate(
            verdict="NOT_MEASURED",
            advice="nenhum arquivo Python medido — a taxa de bloqueio é desconhecida, "
                   "que não é o mesmo que zero",
        )

    blocked = [f for f in py_files if _file_violates(f, thresholds)]
    percent = round(len(blocked) * 100 / len(py_files), 1)

    if percent <= BLOCKING_RATE_READY:
        verdict, advice = "READY", (
            "o gate nasce praticamente verde e passa a reagir ao que piorar — que é o "
            "comportamento que a calibração p90 promete"
        )
    elif percent <= BLOCKING_RATE_CEILING:
        verdict, advice = "REVIEW", (
            f"{len(blocked)} arquivos existentes seriam bloqueados. Revise-os antes de "
            "ligar o hook, ou afrouxe o limiar que mais dispara"
        )
    else:
        verdict, advice = "TOO_STRICT", (
            f"{percent}% do código existente seria bloqueado. Um gate que nasce vermelho "
            "é desligado na primeira hora, e o que sobra é pior que gate nenhum: o hook "
            "no settings, a confiança de que ele protege alguma coisa, e um bypass no "
            "dedo de quem trabalha. Afrouxe os limiares ou trate os arquivos primeiro"
        )

    return BlockingRate(
        files_measured=len(py_files),
        files_blocked=len(blocked),
        percent=percent,
        verdict=verdict,
        advice=advice,
        worst_offenders=tuple(str(f) for f in blocked[:10]),
    )

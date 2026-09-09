"""Metric calibration — derive thresholds from the project's actual metrics."""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from pathlib import Path

from gate_authoring.detect import SKIP_DIRS, _log, _walk_source_files

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
# Blocking rate — the number the calibration was missing to be verifiable
# ---------------------------------------------------------------------------

#: Above this the gate rejects too much code to be switched on as calibrated. It is
#: not an observed percentile: it is the point where the experience of working turns
#: into "every edit is blocked", and a gate like that gets switched off — which
#: leaves the hook in settings, the belief that it protects something, and a bypass
#: in the hand of whoever uses it.
BLOCKING_RATE_CEILING = 10.0

#: Below this the gate starts practically green and only reacts to what gets WORSE,
#: which is the behaviour the p90 calibration promises.
BLOCKING_RATE_READY = 5.0


@dataclass
class BlockingRate:
    """How much of the existing code the calibrated gate would reject, today."""

    files_measured: int = 0
    files_blocked: int = 0
    percent: float | None = None
    verdict: str = "NOT_MEASURED"
    advice: str = ""
    worst_offenders: tuple[str, ...] = ()


def _file_violates(path: Path, thresholds: "ThresholdCalibration") -> bool:
    """True when any of the file's metrics exceeds the corresponding threshold.

    Measures with `_measure_python_metrics`, the SAME instrument that produced the
    calibration's p90 — so the rate is exact for the numbers the calibration used.
    What this count does NOT cover is duplication, which the generated hook also
    checks and the calibration never measured: the real rate may be slightly higher
    than reported, and never lower.
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
            advice="no Python file measured — the blocking rate is unknown, "
                   "which is not the same as zero",
        )

    blocked = [f for f in py_files if _file_violates(f, thresholds)]
    percent = round(len(blocked) * 100 / len(py_files), 1)

    if percent <= BLOCKING_RATE_READY:
        verdict, advice = "READY", (
            "the gate starts practically green and reacts to what gets worse — which "
            "is the behaviour the p90 calibration promises"
        )
    elif percent <= BLOCKING_RATE_CEILING:
        verdict, advice = "REVIEW", (
            f"{len(blocked)} existing files would be blocked. Review them before "
            "switching the hook on, or loosen the threshold that fires most"
        )
    else:
        verdict, advice = "TOO_STRICT", (
            f"{percent}% of the existing code would be blocked. A gate that starts red "
            "is switched off within the hour, and what remains is worse than no gate: "
            "the hook in settings, the belief that it protects something, and a bypass "
            "in the hand of whoever works there. Loosen the thresholds or deal with the "
            "files first"
        )

    return BlockingRate(
        files_measured=len(py_files),
        files_blocked=len(blocked),
        percent=percent,
        verdict=verdict,
        advice=advice,
        worst_offenders=tuple(str(f) for f in blocked[:10]),
    )

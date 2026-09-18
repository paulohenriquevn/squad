"""D4 — mutation testing: do the tests DETECT a defect, or merely pass?

Shared by the four language detectors, like `_arch.py` (D5) and `_wiring.py` (D3).

WHY THIS DETECTOR EXISTS AT ALL
-------------------------------
Every other gate in the pile asks whether the code is *shaped* right: symbols
resolve, exports have importers, lines are covered. None of them can tell a suite
that protects behaviour from a suite that merely executes it. Measured with
mutmut 3.5 on 2026-08-26, a four-line function under a tautological test
(`assert isinstance(desconto(100, 10), float)`) reports 100% line coverage and:

    {"killed": 1, "survived": 7, "total": 8}     ->  12.5%

Seven ways to break that function, and the suite noticed one.

THE SCORE
---------
    score = (killed + timeout) / (total - skipped)

`timeout` counts as detected — the suite reacted to the mutation, which is the
whole question. `skipped` leaves the denominator because it is deliberate
exclusion, and punishing a declared exclusion trains people to stop declaring.
`no_tests` (a mutant no test reaches) stays in the denominator: undetected is
undetected, and moving it out is how a suite with holes reports a perfect score.

WHAT THIS MODULE REFUSES TO DO
------------------------------
Report a number it did not read. Two mutmut behaviours make that easy to get
wrong, both measured rather than assumed:

1. **mutmut exits 0 when it ran nothing.** With tests outside the layout it
   collects, stdout carries `failed to collect stats. runner returned 5` and the
   process succeeds. So the stats FILE is the evidence, never the exit code.
2. **mutmut does not load without `source_paths`.** Even `--help` raises
   `FileNotFoundError` outside a configured project — so an unconfigured project
   is indistinguishable from a missing tool unless the config is checked first.
   The two need different actions from whoever reads the report, so they get
   different messages.

A denominator of zero is reported as absence of measurement. A perfect score over
zero mutants is the worst possible output: absolute green, nothing measured.
"""
from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from scripts._detector_contract import Finding

#: Defaults from `rules/code-quality-thresholds.txt`. The CALLER passes
#: the project's values; these exist so a direct call is still well-defined.
DEFAULT_FLOOR_LOW = 60
DEFAULT_FLOOR_HIGH = 80
DEFAULT_TIMEOUT_MINUTES = 5

#: How old a mutation report may be and still be READ instead of re-measured.
#: 24h by default. Mutation testing is a periodic deep check, not a per-invocation
#: gate: measured in a consumer on 2026-08-27, `npx stryker run` took 1347s, and
#: `run_structural.py` invokes /code-quality internally — so every plan gate in that
#: repository cost 22.5 minutes. A 22-minute gate is a gate people bypass, which is
#: the failure this whole kit exists to prevent. Set to 0 to always re-measure.
DEFAULT_MAX_REPORT_AGE_MINUTES = 1440

#: Directories whose mtimes say nothing about the code under test.
_NOT_SOURCE = frozenset({".git", "node_modules", "reports", "mutants", ".mutmut-cache",
                         "__pycache__", ".venv", "dist", "build", ".stryker-tmp"})

#: Stryker mutant states, per the mutation-testing-elements schema.
_STRYKER_DETECTED = frozenset({"Killed", "Timeout"})
_STRYKER_EXCLUDED = frozenset({"Ignored", "CompileError", "RuntimeError"})

Runner = Callable[..., "tuple[int, str, str]"]


def _sources_changed_since(manifest_dir: Path, when: float) -> int:
    """How many source files are newer than `when`.

    Age alone is not freshness: a report can be four minutes old and already grade a
    tree two commits behind. The age bounds how stale a reused score gets; this count
    is what stops it LOOKING current. Reported, never used to invalidate — re-running
    on every edit would restore the 22-minute gate this exists to remove.
    """
    changed = 0
    for path in manifest_dir.rglob("*"):
        if any(part in _NOT_SOURCE or part.startswith(".") for part in path.relative_to(manifest_dir).parts[:-1]):
            continue
        if path.name in _NOT_SOURCE or not path.is_file():
            continue
        try:
            if path.stat().st_mtime > when:
                changed += 1
        except OSError:
            continue
    return changed


def _reuse_report(report_path: Path, manifest_dir: Path, max_age_minutes: int) -> str | None:
    """A provenance sentence when the report may be reused, else None.

    Returning the SENTENCE rather than a boolean is deliberate: a caller cannot reuse
    the report without also carrying the words that say how old it is. The number on
    its own is a claim about now.
    """
    if max_age_minutes <= 0 or not report_path.is_file():
        return None
    try:
        mtime = report_path.stat().st_mtime
    except OSError:
        return None
    age_minutes = (time.time() - mtime) / 60
    if age_minutes > max_age_minutes:
        return None
    age = f"{age_minutes:.0f}m" if age_minutes < 90 else f"{age_minutes / 60:.1f}h"
    changed = _sources_changed_since(manifest_dir, mtime)
    since = f", {changed} source file(s) changed since" if changed else ", no source changed since"
    return f" — read from a report {age} old{since}, not re-measured"


def _run(cmd: list[str], cwd: Path, timeout_seconds: int) -> tuple[int, str, str]:
    result = subprocess.run(  # noqa: S603 — cmd is built by this module from a fixed tool table, never from user text
        cmd, cwd=str(cwd), capture_output=True, text=True,
        timeout=timeout_seconds, check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _finding(language: str, severity: str, symbol: str, message: str, key_suffix: str) -> Finding:
    return Finding(
        detector="d4_mutation" if severity != "INFO" else "d4_mutation_score",
        language=language,
        severity=severity,
        file_path=".",
        symbol_or_line=symbol,
        message=message,
        allowlist_key=f"{language}|.|mutation_low|{key_suffix}",
    )


def _unavailable(language: str, reason: str) -> list[Finding]:
    return [
        Finding(
            detector="d4_unavailable",
            language=language,
            severity="SOFT_CAP",
            file_path=".",
            symbol_or_line="d4",
            message=f"auditor unavailable: {reason}",
            allowlist_key=f"{language}|.|mutation_low|auditor_unavailable_d4",
        )
    ]


def _score_findings(language: str, killed: int, valid: int, floor_low: int, floor_high: int,
                    provenance: str = "") -> list[Finding]:
    if valid <= 0:
        return [
            _finding(
                language, "SOFT_CAP", "d4",
                "mutation run produced no mutants — a perfect score over an empty set is "
                "absolute green with nothing measured, so it is reported as absence of "
                "measurement instead",
                f"soft_cap_mutation_no_mutants_{language}",
            )
        ]
    score = round(killed * 100 / valid, 1)
    detail = f"mutation score {score}% ({killed}/{valid} mutants detected){provenance}"
    if score < floor_low:
        return [
            _finding(language, "SOFT_CAP", "d4",
                     f"{detail} — below the {floor_low}% floor. The suite runs this code without "
                     "noticing when it breaks.",
                     f"soft_cap_mutation_score_low_{language}")
        ]
    if score < floor_high:
        return [
            _finding(language, "SOFT_FLOOR", "d4",
                     f"{detail} — below the {floor_high}% target, above the {floor_low}% floor.",
                     f"soft_floor_mutation_score_medium_{language}")
        ]
    return [
        _finding(language, "INFO", "d4",
                 f"{detail} — at or above the {floor_high}% target.",
                 f"mutation_score_ok_{language}")
    ]


# ---------------------------------------------------------------------------
# Python — mutmut
# ---------------------------------------------------------------------------

_MUTMUT_CONFIG_FILES = ("setup.cfg", "pyproject.toml", "tox.ini", "mutmut_config.py")
_MUTMUT_STATS = Path("mutants") / "mutmut-cicd-stats.json"


def _mutmut_configured(manifest_dir: Path) -> bool:
    for name in _MUTMUT_CONFIG_FILES:
        path = manifest_dir / name
        if not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "mutmut" in body and ("source_paths" in body or "paths_to_mutate" in body):
            return True
    return False


def _python_mutation(manifest_dir: Path, floor_low: int, floor_high: int,
                     timeout_seconds: int, runner: Runner,
                     max_report_age_minutes: int = DEFAULT_MAX_REPORT_AGE_MINUTES) -> list[Finding]:
    if not _mutmut_configured(manifest_dir):
        return [
            _finding(
                "python", "SOFT_CAP", "d4",
                "no mutation config: mutmut needs a `[mutmut]` section declaring `source_paths` "
                "(it raises FileNotFoundError on import without one). Declare what to mutate and "
                "D4 starts measuring.",
                "soft_cap_mutation_unconfigured_python",
            )
        ]

    stats_path = manifest_dir / _MUTMUT_STATS
    provenance = _reuse_report(stats_path, manifest_dir, max_report_age_minutes)
    try:
        if provenance is None:
            runner(["mutmut", "run"], manifest_dir, timeout_seconds)
            runner(["mutmut", "export-cicd-stats"], manifest_dir, timeout_seconds)
    except FileNotFoundError:
        return _unavailable("python", "mutmut not found in PATH")
    except subprocess.TimeoutExpired:
        return _unavailable("python", f"mutmut timed out after {timeout_seconds}s")
    except (subprocess.SubprocessError, OSError) as e:
        return _unavailable("python", f"mutmut invocation failed: {e}")

    # The exit code is deliberately NOT consulted — see the module docstring.
    if not stats_path.is_file():
        return _unavailable(
            "python",
            "mutmut ran but wrote no stats file (mutants/mutmut-cicd-stats.json). It exits 0 "
            "even when the test runner collected nothing, so no file means no measurement.",
        )
    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return _unavailable("python", f"mutmut stats file unreadable: {e}")

    killed = int(stats.get("killed", 0)) + int(stats.get("timeout", 0))
    valid = int(stats.get("total", 0)) - int(stats.get("skipped", 0))
    return _score_findings("python", killed, valid, floor_low, floor_high, provenance or "")


# ---------------------------------------------------------------------------
# TypeScript — Stryker
# ---------------------------------------------------------------------------

_STRYKER_CONFIGS = ("stryker.config.json", "stryker.conf.json", "stryker.config.mjs",
                    "stryker.conf.js", ".stryker.conf.json")
_STRYKER_REPORT = Path("reports") / "mutation" / "mutation.json"


def _typescript_mutation(manifest_dir: Path, floor_low: int, floor_high: int,
                         timeout_seconds: int, runner: Runner,
                         max_report_age_minutes: int = DEFAULT_MAX_REPORT_AGE_MINUTES) -> list[Finding]:
    if not any((manifest_dir / name).is_file() for name in _STRYKER_CONFIGS):
        return [
            _finding(
                "typescript", "SOFT_CAP", "d4",
                "no mutation config: Stryker needs a `stryker.config.json` (or equivalent) "
                "naming the test runner. Declare it and D4 starts measuring.",
                "soft_cap_mutation_unconfigured_typescript",
            )
        ]

    report_path = manifest_dir / _STRYKER_REPORT
    provenance = _reuse_report(report_path, manifest_dir, max_report_age_minutes)
    try:
        if provenance is None:
            runner(["npx", "stryker", "run", "--reporters", "json"], manifest_dir, timeout_seconds)
    except FileNotFoundError:
        return _unavailable("typescript", "npx/stryker not found in PATH")
    except subprocess.TimeoutExpired:
        return _unavailable("typescript", f"stryker timed out after {timeout_seconds}s")
    except (subprocess.SubprocessError, OSError) as e:
        return _unavailable("typescript", f"stryker invocation failed: {e}")

    if not report_path.is_file():
        return _unavailable(
            "typescript",
            f"stryker ran but wrote no report at {_STRYKER_REPORT} — no report, no measurement",
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return _unavailable("typescript", f"stryker report unreadable: {e}")

    killed = valid = 0
    for entry in (report.get("files") or {}).values():
        for mutant in entry.get("mutants", []):
            status = mutant.get("status")
            if status in _STRYKER_EXCLUDED:
                continue
            valid += 1
            if status in _STRYKER_DETECTED:
                killed += 1
    return _score_findings("typescript", killed, valid, floor_low, floor_high, provenance or "")


# ---------------------------------------------------------------------------
# Rust / Go — declared deferrals
# ---------------------------------------------------------------------------

def _deferred(language: str, tool: str) -> list[Finding]:
    return [
        _finding(
            language, "SOFT_CAP", "d4",
            f"{language} mutation testing is deferred — the golden rule § 5 declares D4 as "
            f"Python + TypeScript only. Adopting {tool} requires an ADR extending that table.",
            f"soft_cap_mutation_deferred_{language}",
        )
    ]


_BY_LANGUAGE = {
    "python": _python_mutation,
    "typescript": _typescript_mutation,
}


def detect_mutation_score(
    language: str,
    manifest_dir: Path,
    *,
    floor_low: int = DEFAULT_FLOOR_LOW,
    floor_high: int = DEFAULT_FLOOR_HIGH,
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
    max_report_age_minutes: int = DEFAULT_MAX_REPORT_AGE_MINUTES,
    runner: Runner | None = None,
) -> list[Finding]:
    """Measure the project's mutation score, or say honestly why it could not."""
    if language == "rust":
        return _deferred("rust", "cargo-mutants")
    if language == "go":
        return _deferred("go", "gremlins")

    handler = _BY_LANGUAGE.get(language)
    if handler is None:
        return _unavailable(language, f"no D4 runner for language {language!r}")

    return handler(manifest_dir, floor_low, floor_high,
                   int(timeout_minutes * 60), runner or _run, max_report_age_minutes)

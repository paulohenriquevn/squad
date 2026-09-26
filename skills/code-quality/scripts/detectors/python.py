"""Python detector — wraps vulture (D1) + PyPI registry lookup (D2) + mutmut (D4).

T1.1 implementation: detect_dead_code via vulture subprocess.
T2.2 implementation: detect_symbol_fabrication via tree-sitter + PyPI lookup.
D3/D4 report explicit capability caps until their external runners are integrated.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

from scripts import _registry
from scripts._detector_contract import (
    DEFAULT_SKIP_DIRS,
    Finding,
    sanitize_symbol,
    to_rel_path,
)
from scripts.check_symbol_fab import extract_checked

from . import BaseDetector, _arch

_ARCH_TIMEOUT_SEC = 240
#: import-linter reads the first of these it finds.
_ARCH_CONFIGS = (".importlinter", "setup.cfg", "pyproject.toml", "tox.ini")

_VULTURE_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):\s+(?P<kind>\S+\s+\S+)\s+'(?P<symbol>[^']+)'.*\((?P<confidence>\d+)%\s+confidence\)"
)

_VULTURE_TIMEOUT_SEC = 120


class PythonDetector(BaseDetector):
    language = "python"
    manifest_marker = "pyproject.toml"

    def __init__(self, min_confidence: int = 80) -> None:
        self.min_confidence = min_confidence

    def detect_dead_code(self, manifest_dir: Path) -> list[Finding]:
        """Run vulture against `manifest_dir` and parse stdout into Findings.

        Returns:
            list[Finding] — one per detected dead-code item, severity=HARD.
            If vulture is unavailable, returns a single SOFT_CAP Finding with
            allowlist_key containing `auditor_unavailable_vulture`.
        """
        # vulture is resolved through the interpreter running this detector, not
        # through PATH. It ships as a library plus a console script, and only the
        # console script lands on PATH — where it lands depends on how the install
        # happened, so a host can carry a perfectly importable vulture and no
        # `vulture` executable the gate can reach. Measured on such a host: the
        # bare-name lookup raised FileNotFoundError, D1 degraded to SOFT_CAP, and
        # dead code went unreported.
        #
        # `-m` moves the failure from PATH to the import system, and an import
        # failure is quieter than an exec failure: `python -m vulture` without the
        # module exits 1 with an empty stdout, which parses as zero findings. So
        # the module is checked here rather than inferred from the output.
        if importlib.util.find_spec("vulture") is None:
            return [
                self._auditor_unavailable(
                    f"vulture module not importable by {sys.executable} "
                    "(install it with: python3 -m pip install 'vulture>=2.14')"
                )
            ]
        # `--exclude` rather than the bare directory: vulture walks everything
        # below what it is handed, and `_detector_contract.DEFAULT_SKIP_DIRS` — which
        # `enumerate_source_files` already honours — exists to keep this gate on
        # the PRODUCT. Measured in a fresh install at min_confidence 60: 44
        # findings, 42 of them inside `.claude/` (the kit itself) and 2 in the
        # adopter's code, with the verdict FAIL_HARD on their strength. Same
        # defect the stop-hook had and fixed; never propagated here.
        cmd = [
            sys.executable,
            "-m",
            "vulture",
            "--min-confidence",
            str(self.min_confidence),
            "--exclude",
            ",".join(f"*/{name}/*" for name in sorted(DEFAULT_SKIP_DIRS)),
            str(manifest_dir),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_VULTURE_TIMEOUT_SEC,
                check=False,
            )
        except FileNotFoundError:
            return [self._auditor_unavailable(f"interpreter {sys.executable} not executable")]
        except subprocess.TimeoutExpired:
            return [self._auditor_unavailable(f"vulture timed out after {_VULTURE_TIMEOUT_SEC}s")]
        except (subprocess.SubprocessError, OSError) as e:
            return [self._auditor_unavailable(f"vulture invocation failed: {e}")]

        # The exit code, read BEFORE the output is parsed — the same guard `go.py` has
        # carried since it was written. `result.stdout` used to go straight to the parser
        # and `result.returncode` was never inspected, so any failure that writes to
        # stderr and leaves stdout empty — a bad argument, an internal traceback, an
        # unreadable file — parsed as ZERO dead symbols and D1 reported the language
        # clean. An auditor that did not run is not an auditor that found nothing.
        if not result.stdout.strip() and result.returncode != 0:
            return [self._auditor_unavailable(
                f"vulture exit {result.returncode}: {result.stderr.strip()[:200]}")]

        return self._parse_vulture_output(result.stdout, manifest_dir)

    def detect_symbol_fabrication(self, changed_files: list[Path]) -> list[Finding]:
        """T2.2 — Validate imports against PyPI. Skip stdlib + relative imports (EC-17)."""
        findings: list[Finding] = []
        # Vacuity guard, the same one `rust.py` carries and for the same measured reason:
        # `extract_checked` reports whether the parser RAN, and an empty symbol list from
        # a parse that never happened reads to D2 as "this file imports nothing" — a
        # silent false-green over an audit that did not run. Reported as unavailable,
        # never as clean.
        parsed_any = False
        unparsed = 0
        stdlib_modules = set(sys.stdlib_module_names)
        for src_file in changed_files:
            if not src_file.exists():
                continue
            rel = to_rel_path(src_file)
            symbols, parsed = extract_checked(src_file, "python")
            parsed_any = parsed_any or parsed
            unparsed += 0 if parsed else 1
            for sym in symbols:
                if sym.kind != "import":
                    continue
                module = sym.module
                if not module or module.startswith("."):
                    continue  # EC-17 — relative imports skipped
                top_level = module.split(".")[0]
                if top_level in stdlib_modules:
                    continue
                exists = _registry.package_exists_on_pypi(top_level)
                if exists is True:
                    continue
                if exists is False:
                    sanitized = sanitize_symbol(top_level)
                    findings.append(
                        Finding(
                            detector="d2_symbol_fab",
                            language="python",
                            severity="HARD",
                            file_path=rel,
                            symbol_or_line=f"import {module}",
                            message=f"Fabricated PyPI package '{top_level}' (not found on registry)",
                            allowlist_key=f"python|{rel}|symbol_fab|{sanitized}",
                        )
                    )
                else:
                    # EC-2 — registry returned None (HTML / timeout). Conservative SOFT_FLOOR.
                    sanitized = sanitize_symbol(top_level)
                    findings.append(
                        Finding(
                            detector="d2_symbol_fab",
                            language="python",
                            severity="SOFT_FLOOR",
                            file_path=rel,
                            symbol_or_line=f"import {module}",
                            message=f"Could not verify PyPI package '{top_level}' (ambiguous response)",
                            allowlist_key=f"python|{rel}|symbol_fab|symbol_fab_unverifiable_{sanitized}",
                        )
                    )
        if unparsed and not parsed_any:
            return [
                Finding(
                    detector="d2_symbol_fab",
                    language="python",
                    severity="SOFT_CAP",
                    file_path=".",
                    symbol_or_line="tree-sitter",
                    message=(
                        f"D2 parsed none of the {unparsed} Python source(s) it was "
                        f"given — the tree-sitter grammar is unavailable or failed to "
                        f"load. The audit did not run; this is NOT evidence that no "
                        f"symbol is fabricated."
                    ),
                    allowlist_key="python|.|symbol_fab|auditor_unavailable_tree-sitter",
                )
            ]

        return findings

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _parse_vulture_output(self, stdout: str, repo_root: Path) -> list[Finding]:
        findings: list[Finding] = []
        for line in stdout.splitlines():
            match = _VULTURE_LINE_RE.match(line.strip())
            if not match:
                continue
            try:
                file_rel = self._relativize(Path(match["path"]), repo_root)
            except ValueError:
                continue
            symbol = sanitize_symbol(match["symbol"])
            findings.append(
                Finding(
                    detector="d1_dead_code",
                    language="python",
                    severity="HARD",
                    file_path=file_rel,
                    symbol_or_line=f"{match['symbol']} (line {match['line']})",
                    message=f"Unused {match['kind']} '{match['symbol']}' "
                    f"({match['confidence']}% confidence)",
                    allowlist_key=f"python|{file_rel}|dead_code|{symbol}",
                )
            )
        return findings

    @staticmethod
    def _relativize(path: Path, repo_root: Path) -> str:
        resolved = path.resolve() if path.is_absolute() else (repo_root / path).resolve()
        return resolved.relative_to(repo_root.resolve()).as_posix()

    def _auditor_unavailable(self, reason: str) -> Finding:
        return Finding(
            detector="d1_dead_code",
            language="python",
            severity="SOFT_CAP",
            file_path=".",
            symbol_or_line="vulture",
            message=f"Vulture auditor unavailable: {reason}",
            allowlist_key="python|.|dead_code|auditor_unavailable_vulture",
        )

    # ── D5 — architecture ───────────────────────────────────────────────────────────────────────

    def detect_architecture_violations(self, manifest_dir: Path) -> list[Finding]:
        """Run `lint-imports` against the contracts the project declares.

        import-linter is the Python member of the ArchUnit family: the project writes contracts
        (`forbidden`, `layers`, `independence`) in its own config, and the tool checks them
        against the real import graph.

        The meta-gate here is cheaper than in the other languages because import-linter already
        does it: a contract naming a module that does not exist fails with
        `ModuleNotFoundError`-style output rather than passing quietly. So D5 forwards the verdict
        and does not re-derive it — the failure mode this detector exists to catch is one this
        particular tool already refuses to have.
        """
        config = next((manifest_dir / name for name in _ARCH_CONFIGS if (manifest_dir / name).is_file()), None)
        if config is None:
            return [_arch.no_config("python", tool="import-linter", looked_for=list(_ARCH_CONFIGS))]

        try:
            raw = config.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return [_arch.auditor_unavailable("python", tool="import-linter", reason=f"unreadable config: {e}")]
        if "importlinter" not in raw:
            return [
                _arch.no_config(
                    "python", tool="import-linter", looked_for=[f"an [importlinter] section in {config.name}"]
                )
            ]

        try:
            result = subprocess.run(
                ["lint-imports", "--config", str(config)],
                cwd=str(manifest_dir),
                capture_output=True,
                text=True,
                timeout=_ARCH_TIMEOUT_SEC,
                check=False,
            )
        except FileNotFoundError:
            return [
                _arch.auditor_unavailable(
                    "python",
                    tool="import-linter",
                    reason="lint-imports not found (install via `pip install import-linter`)",
                )
            ]
        except subprocess.TimeoutExpired:
            return [
                _arch.auditor_unavailable(
                    "python", tool="import-linter", reason=f"timed out after {_ARCH_TIMEOUT_SEC}s"
                )
            ]
        except (subprocess.SubprocessError, OSError) as e:
            return [_arch.auditor_unavailable("python", tool="import-linter", reason=f"invocation failed: {e}")]

        if result.returncode == 0:
            return []

        output = f"{result.stdout}\n{result.stderr}"
        broken = [ln.strip() for ln in output.splitlines() if ln.strip().startswith("BROKEN")]
        if not broken:
            return [
                _arch.auditor_unavailable(
                    "python",
                    tool="import-linter",
                    reason=f"exit {result.returncode} without a BROKEN contract: {output.strip()[-300:]}",
                )
            ]
        return [
            _arch.violation(
                "python",
                tool="import-linter",
                rule=line.replace("BROKEN", "").strip() or "contract",
                file_path=config.name,
                symbol_or_line="contract",
                message="contract broken — see `lint-imports` output for the offending import chain",
            )
            for line in broken
        ]

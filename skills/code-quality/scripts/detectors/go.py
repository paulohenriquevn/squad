"""Go detector — wraps deadcode (D1) + Go proxy registry lookup (D2).

T1.4 implementation: detect_dead_code via deadcode subprocess.
T2.5 implementation: detect_symbol_fabrication via tree-sitter + Go proxy.
D3 and deferred mutation testing report explicit capability caps.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import _registry
from scripts._detector_contract import Finding, safe_parse_json, sanitize_symbol, to_rel_path
from scripts.check_symbol_fab import extract_imports_and_calls

from . import BaseDetector, _arch, _mutation, _wiring

_DEADCODE_TIMEOUT_SEC = 180
_ARCH_TIMEOUT_SEC = 240
_ARCH_CONFIG = ".go-arch-lint.yml"


class GoDetector(BaseDetector):
    language = "go"
    manifest_marker = "go.mod"

    def detect_dead_code(self, manifest_dir: Path) -> list[Finding]:
        """Run `deadcode -test -tags=e2e,chaos -json ./...` and parse JSON list into Findings."""
        # `-test` and `-tags` are not tuning: without them this detector reports
        # live code as dead. Measured in a consumer on 2026-06-04 and fixed there,
        # inside its own `.claude/`, where it protected exactly one machine for
        # three months — found on 2026-08-31 while propagating the kit to it.
        #
        # -test          makes test executables analysis entry points. Without it a
        #                function whose only callers live in `*_test.go` is reported
        #                dead; the consumer saw this for CanonicalAlerts and
        #                RenderPrometheusRule, both of them live.
        # -tags=e2e,chaos  includes build-tagged packages. Without it, helpers called
        #                only from `//go:build e2e` tests read as dead too.
        cmd = ["deadcode", "-test", "-tags=e2e,chaos", "-json", "./..."]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(manifest_dir),
                capture_output=True,
                text=True,
                timeout=_DEADCODE_TIMEOUT_SEC,
                check=False,
            )
        except FileNotFoundError:
            return [
                self._auditor_unavailable(
                    "deadcode binary not found (install via "
                    "`go install golang.org/x/tools/cmd/deadcode@v0.45.0`)"
                )
            ]
        except subprocess.TimeoutExpired:
            return [self._auditor_unavailable(f"deadcode timed out after {_DEADCODE_TIMEOUT_SEC}s")]
        except (subprocess.SubprocessError, OSError) as e:
            return [self._auditor_unavailable(f"deadcode invocation failed: {e}")]

        if not result.stdout.strip():
            if result.returncode != 0:
                return [
                    self._auditor_unavailable(
                        f"deadcode exit {result.returncode}: {result.stderr.strip()[:200]}"
                    )
                ]
            return []

        data, parse_finding = safe_parse_json(result.stdout, "deadcode")
        if parse_finding is not None:
            return [
                Finding(
                    detector="d1_dead_code",
                    language="go",
                    severity="SOFT_CAP",
                    file_path=".",
                    symbol_or_line="deadcode",
                    message=f"deadcode JSON output failed to parse: {parse_finding.message}",
                    allowlist_key="go|.|dead_code|auditor_output_malformed_deadcode",
                )
            ]
        return self._parse_deadcode_json(data)

    def detect_symbol_fabrication(self, changed_files: list[Path]) -> list[Finding]:
        """T2.5 — Validate Go imports against Go proxy. Skip self-module + vendored (EC-17 analog, EC-18).

        Reads `go.mod#module` from the repo root (passed as parent of first changed file)
        to identify the self-module prefix. Imports starting with that prefix are skipped.
        Imports under `vendor/` are also skipped (vendored deps).
        """
        findings: list[Finding] = []
        own_modules = self._workspace_modules(changed_files)
        #: Imports the proxy could not answer for. Reported ONCE, at the end.
        unresolved: set[str] = set()
        for src_file in changed_files:
            if not src_file.exists():
                continue
            rel = to_rel_path(src_file)
            # Skip files under vendor/
            if "/vendor/" in rel or rel.startswith("vendor/"):
                continue
            for sym in extract_imports_and_calls(src_file, "go"):
                if sym.kind != "import":
                    continue
                module = sym.module
                if not module:
                    continue
                if any(module == own or module.startswith(f"{own}/") for own in own_modules):
                    continue  # EC-17 analog — this workspace's own modules
                exists = _registry.module_exists_on_go_proxy(module)
                if exists is True:
                    continue
                sanitized = sanitize_symbol(module)
                if exists is False:
                    findings.append(
                        Finding(
                            detector="d2_symbol_fab",
                            language="go",
                            severity="HARD",
                            file_path=rel,
                            symbol_or_line=f'import "{module}"',
                            message=f"Fabricated Go module '{module}' (not found on Go proxy)",
                            allowlist_key=f"go|{rel}|symbol_fab|{sanitized}",
                        )
                    )
                else:
                    # Collected, not emitted. See the aggregate below.
                    unresolved.add(module)

        # One finding for every module the proxy could not answer for, instead of one
        # per import. The old shape scaled with the repository rather than with the
        # problem: measured on a real one, an unreachable proxy produced 4777 findings
        # where the honest statement is a single "could not verify N modules".
        #
        # It also made the detector non-deterministic in a way a baseline cannot
        # absorb. Two consecutive runs reported 4818 and then 4777, because each import
        # is a separate query and the set that fails depends on what the proxy answered
        # that second — so every run produces findings the previous baseline does not
        # cover. Aggregated, the finding is stable: same key, whatever the count.
        if unresolved:
            findings.append(
                Finding(
                    detector="d2_symbol_fab",
                    language="go",
                    severity="SOFT_FLOOR",
                    file_path=".",
                    symbol_or_line=f"{len(unresolved)} module(s)",
                    message=(f"Could not verify {len(unresolved)} Go module(s) against the "
                             f"proxy (ambiguous or unreachable). Verification did not run; "
                             f"this is not evidence of fabrication. First: "
                             f"{', '.join(sorted(unresolved)[:3])}"),
                    allowlist_key="go|.|symbol_fab|symbol_fab_unverifiable",
                )
            )
        return findings

    @staticmethod
    def _module_of(go_mod: Path) -> str | None:
        try:
            for line in go_mod.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("module "):
                    return stripped.removeprefix("module ").strip()
        except OSError:
            return None
        return None

    @staticmethod
    def _workspace_modules(changed_files: list[Path]) -> set[str]:
        """Every module path this workspace owns — all of them, not the nearest one.

        A multi-module repository is the normal shape for Go, and reading only the
        nearest `go.mod` makes every SIBLING module look like a third-party import. The
        proxy answers 404 for those, `false_statuses` turns 404 into "does not exist",
        and the detector reports a HARD fabrication for code that lives in the same
        checkout.

        Measured on a real repository on 2026-08-31: three `go.mod` files (api, pkg,
        operators) plus a `go.work` naming a fourth outside the tree, and the run
        produced 2459 HARD findings. The note in that project's own config had named
        the shape a year earlier — *sibling modules of the go.work treated as external*
        — and the fix had only reached the nearest-module case.

        `go.work` is read when present, because it names modules that live OUTSIDE the
        repository root and no upward walk can find those.
        """
        modules: set[str] = set()
        roots: set[Path] = set()

        for src in changed_files:
            current = src.resolve().parent if src.is_file() else src.resolve()
            for _ in range(10):
                if (current / "go.mod").is_file():
                    roots.add(current)
                if (current / "go.work").is_file():
                    roots.add(current)
                    for line in (current / "go.work").read_text(
                            encoding="utf-8", errors="replace").splitlines():
                        entry = line.strip().strip("()").strip()
                        if entry.startswith("./") or entry.startswith("../"):
                            roots.add((current / entry).resolve())
                if current == current.parent:
                    break
                current = current.parent

        for root in roots:
            go_mod = root / "go.mod"
            if go_mod.is_file():
                name = GoDetector._module_of(go_mod)
                if name:
                    modules.add(name)
            # A workspace root usually has no `go.mod` of its own; its members do.
            for nested in sorted(root.glob("*/go.mod")):
                name = GoDetector._module_of(nested)
                if name:
                    modules.add(name)
        return modules

    def detect_orphan_exports(self, repo_root: Path) -> list[Finding]:
        return _wiring.detect_orphan_exports(self.language, repo_root, repo_root)

    def detect_mutation_score(self, manifest_dir: Path) -> list[Finding]:
        return _mutation.detect_mutation_score(
            self.language,
            manifest_dir,
            floor_low=self.threshold("mutation.score_floor_low", _mutation.DEFAULT_FLOOR_LOW),
            floor_high=self.threshold("mutation.score_floor_high", _mutation.DEFAULT_FLOOR_HIGH),
            timeout_minutes=self.threshold(
                "mutation.timeout_minutes", _mutation.DEFAULT_TIMEOUT_MINUTES),
            max_report_age_minutes=self.threshold(
                "mutation.max_report_age_minutes", _mutation.DEFAULT_MAX_REPORT_AGE_MINUTES),
        )

    # ------------------------------------------------------------------

    def _parse_deadcode_json(self, data) -> list[Finding]:
        """Turn `deadcode -json` output into one finding per unreachable function.

        The shape the tool actually emits is a list of PACKAGES, each with a `Funcs`
        list, and every key capitalised:

            [{"Name": "...", "Path": "...", "Funcs": [
                {"Name": "Reader.ID",
                 "Position": {"File": "internal/x.go", "Line": 42, "Col": 7},
                 "Generated": false, "Marker": false}]}]

        This read `entry["position"]` and `entry["name"]` — lower case, and flat. Both
        missed, so every entry defaulted to `<unknown>`: one finding per PACKAGE
        instead of per function, each naming no file. Measured on a real repository on
        2026-08-31, that produced five findings with `file_path` of `<unknown>`, which
        no baseline can record and no reader can act on — the gate said "dead code
        here" and could not say where.

        The flat shape is still accepted, because some version emitted it and a
        detector that only reads today's output breaks on the day the tool changes
        again.
        """
        findings: list[Finding] = []
        if not isinstance(data, list):
            return findings

        def _emit(name: str, position: str) -> None:
            file_part = position.split(":", 1)[0] if ":" in position else position
            findings.append(
                Finding(
                    detector="d1_dead_code",
                    language="go",
                    severity="HARD",
                    file_path=file_part,
                    symbol_or_line=f"{name} @ {position}",
                    message=f"Unreachable Go symbol '{name}' at {position}",
                    allowlist_key=f"go|{file_part}|dead_code|{sanitize_symbol(name)}",
                )
            )

        for entry in data:
            if not isinstance(entry, dict):
                continue
            funcs = entry.get("Funcs") or entry.get("funcs")
            if isinstance(funcs, list):
                for fn in funcs:
                    if not isinstance(fn, dict):
                        continue
                    # `Generated` marks compiler-written code: reporting it as dead
                    # asks someone to delete a file they do not own.
                    if fn.get("Generated") or fn.get("generated"):
                        continue
                    pos = fn.get("Position") or fn.get("position") or {}
                    if isinstance(pos, dict):
                        where = f"{pos.get('File', '<unknown>')}:{pos.get('Line', 0)}:{pos.get('Col', 0)}"
                    else:
                        where = str(pos)
                    _emit(str(fn.get("Name") or fn.get("name") or "<unknown>"), where)
                continue
            # The flat shape, kept for older output.
            _emit(str(entry.get("name", "<unknown>")),
                  str(entry.get("position", "<unknown>:0:0")))
        return findings

    def _auditor_unavailable(self, reason: str) -> Finding:
        return Finding(
            detector="d1_dead_code",
            language="go",
            severity="SOFT_CAP",
            file_path=".",
            symbol_or_line="deadcode",
            message=f"deadcode auditor unavailable: {reason}",
            allowlist_key="go|.|dead_code|auditor_unavailable_deadcode",
        )

    # ── D5 — architecture ───────────────────────────────────────────────────────────────────────

    def detect_architecture_violations(self, manifest_dir: Path) -> list[Finding]:
        """Run `go-arch-lint check --json` against the repo's own `.go-arch-lint.yml`.

        The linter is the authority on its own format — D5 never re-parses the YAML to decide
        what a rule means. Raw text is read for exactly one thing the JSON cannot tell us: whether
        the config disabled the linter's built-in protection against ghost components.
        """
        config = manifest_dir / _ARCH_CONFIG
        if not config.is_file():
            return [_arch.no_config("go", tool="go-arch-lint", looked_for=[_ARCH_CONFIG])]

        findings = self._arch_config_selfcheck(config)

        try:
            result = subprocess.run(
                ["go-arch-lint", "check", "--json", "--project-path", str(manifest_dir)],
                cwd=str(manifest_dir),
                capture_output=True,
                text=True,
                timeout=_ARCH_TIMEOUT_SEC,
                check=False,
            )
        except FileNotFoundError:
            return findings + [
                _arch.auditor_unavailable(
                    "go",
                    tool="go-arch-lint",
                    reason=(
                        "binary not found (install via "
                        "`go install github.com/fe3dback/go-arch-lint@latest`)"
                    ),
                )
            ]
        except subprocess.TimeoutExpired:
            return findings + [
                _arch.auditor_unavailable(
                    "go", tool="go-arch-lint", reason=f"timed out after {_ARCH_TIMEOUT_SEC}s"
                )
            ]
        except (subprocess.SubprocessError, OSError) as e:
            return findings + [
                _arch.auditor_unavailable("go", tool="go-arch-lint", reason=f"invocation failed: {e}")
            ]

        if not result.stdout.strip():
            return findings + [
                _arch.auditor_unavailable(
                    "go",
                    tool="go-arch-lint",
                    reason=f"exit {result.returncode} with no output: {result.stderr.strip()[:200]}",
                )
            ]

        data, parse_finding = safe_parse_json(result.stdout, "go-arch-lint")
        if parse_finding is not None:
            return findings + [
                _arch.auditor_unavailable(
                    "go", tool="go-arch-lint", reason=f"JSON output failed to parse: {parse_finding.message}"
                )
            ]

        return findings + self._parse_arch_json(data)

    def _arch_config_selfcheck(self, config: Path) -> list[Finding]:
        """The one thing the linter's JSON cannot report: its own safety net being switched off.

        `allow.ignoreNotFoundComponents` makes go-arch-lint skip a component whose glob matches
        nothing — which is precisely the failure this detector exists to catch, made silent by
        configuration. Default is disabled; turning it on is a decision, and it should be a loud one.
        """
        try:
            raw = config.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return [
                _arch.auditor_unavailable(
                    "go", tool="go-arch-lint", reason=f"could not read {_ARCH_CONFIG}: {e}"
                )
            ]

        findings: list[Finding] = []
        for line in raw.splitlines():
            stripped = line.split("#", 1)[0].strip()
            if stripped.startswith("ignoreNotFoundComponents:") and stripped.endswith("true"):
                findings.append(
                    Finding(
                        detector=_arch.D5,
                        language="go",
                        severity="HARD",
                        file_path=_ARCH_CONFIG,
                        symbol_or_line="allow.ignoreNotFoundComponents",
                        message=(
                            "`ignoreNotFoundComponents: true` disables the linter's own guard "
                            "against a component whose glob matches nothing. With it on, a "
                            "directory rename silently retires the rule and the check still "
                            "passes — measured on theo-contracts 2026-08-06, where a ghost "
                            "component reported ArchHasWarnings: false."
                        ),
                        allowlist_key="go|.go-arch-lint.yml|architecture|ignore_not_found_components",
                    )
                )
        return findings

    def _parse_arch_json(self, data: object) -> list[Finding]:
        """Map go-arch-lint's payload onto the D5 vocabulary."""
        if not isinstance(data, dict):
            return [
                _arch.auditor_unavailable(
                    "go", tool="go-arch-lint", reason="payload was not an object"
                )
            ]
        payload = data.get("Payload")
        if not isinstance(payload, dict):
            return [
                _arch.auditor_unavailable(
                    "go", tool="go-arch-lint", reason="payload had no 'Payload' object"
                )
            ]

        findings: list[Finding] = []

        # A component whose directory is gone. go-arch-lint files this under ExecutionWarnings and
        # still answers ArchHasWarnings: false — green. This is the whole reason D5 reads the
        # payload instead of trusting the exit code.
        for warning in payload.get("ExecutionWarnings") or []:
            if not isinstance(warning, dict):
                continue
            text = str(warning.get("Text", ""))
            if "not found directories" in text:
                findings.append(
                    _arch.vacuous_rule(
                        "go",
                        tool="go-arch-lint",
                        rule=_component_of(text),
                        config_path=_ARCH_CONFIG,
                        detail=text,
                    )
                )
            else:
                findings.append(
                    _arch.auditor_unavailable("go", tool="go-arch-lint", reason=text[:200])
                )

        for key in ("ArchWarningsDeps", "ArchWarningsDeepScan"):
            for warning in payload.get(key) or []:
                if not isinstance(warning, dict):
                    continue
                rel = str(warning.get("FileRelativePath", "")).lstrip("/") or "."
                line = (warning.get("Reference") or {}).get("Line", "?")
                findings.append(
                    _arch.violation(
                        "go",
                        tool="go-arch-lint",
                        rule=str(warning.get("ComponentName", "?")),
                        file_path=rel,
                        symbol_or_line=f"line {line}",
                        message=(
                            f"imports {warning.get('ResolvedImportName', '?')}, which its component "
                            "is not allowed to depend on"
                        ),
                    )
                )

        # Code no component claims. Not a violation — the rules simply do not reach it, and a
        # boundary that covers half the tree protects half the tree. SOFT_FLOOR so it is visible
        # without blocking, mirroring how the journeys registry treats an unclassified module.
        not_matched = payload.get("ArchWarningsNotMatched") or []
        if not_matched:
            findings.append(
                Finding(
                    detector=_arch.D5,
                    language="go",
                    severity="SOFT_FLOOR",
                    file_path=_ARCH_CONFIG,
                    symbol_or_line="coverage",
                    message=(
                        f"{len(not_matched)} package(s) belong to no component, so no rule reaches "
                        "them. Add them to a component or say why they are out of scope."
                    ),
                    allowlist_key="go|.go-arch-lint.yml|architecture|packages_not_matched",
                )
            )
        return findings


def _component_of(warning_text: str) -> str:
    """Pull the component name out of `not found directories for 'X' in '...'`."""
    marker = "not found directories for '"
    start = warning_text.find(marker)
    if start == -1:
        return "?"
    rest = warning_text[start + len(marker) :]
    end = rest.find("'")
    return rest[:end] if end != -1 else "?"

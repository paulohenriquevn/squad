"""TypeScript detector — wraps knip (D1) + npm registry lookup (D2) + stryker (D4).

T1.2 implementation: detect_dead_code via knip subprocess.
T2.3 implementation: detect_symbol_fabrication via tree-sitter + npm lookup.
D3/D4 report explicit capability caps until their external runners are integrated.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from scripts import _registry

from ._workspace import declared, find_workspace_roots, manifests_under, read_workspace_declaration
from scripts._detector_contract import Finding, safe_parse_json, sanitize_symbol, to_rel_path
from scripts.check_symbol_fab import extract_checked

from . import BaseDetector, _arch

_TS_NODE_BUILTINS = frozenset(
    {
        "fs", "path", "os", "util", "crypto", "http", "https", "url", "stream",
        "events", "buffer", "child_process", "cluster", "dgram", "dns", "net",
        "querystring", "readline", "tls", "tty", "vm", "zlib", "assert",
        "string_decoder", "process", "module", "perf_hooks", "worker_threads",
        "console", "timers", "domain", "punycode", "v8", "inspector",
    }
)

_KNIP_TIMEOUT_SEC = 120
_ARCH_TIMEOUT_SEC = 300

#: Path-ish token inside a dependency-cruiser regex: at least one `/`, no regex metacharacters.
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_.@-]+(?:/[A-Za-z0-9_.@-]+)+")


class TypescriptDetector(BaseDetector):
    language = "typescript"
    manifest_marker = "package.json"

    def detect_dead_code(self, manifest_dir: Path) -> list[Finding]:
        """Run knip against `manifest_dir` and parse JSON into Findings.

        knip emits exit code 0 (no findings) or 1 (findings). Exit code > 1
        signals tool error and is treated as `auditor_unavailable_knip`.
        """
        cmd = ["npx", "--yes", "knip", "--reporter", "json"]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(manifest_dir),
                capture_output=True,
                text=True,
                timeout=_KNIP_TIMEOUT_SEC,
                check=False,
            )
        except FileNotFoundError:
            return [self._auditor_unavailable("knip not found in PATH (install via npm i -g knip)")]
        except subprocess.TimeoutExpired:
            return [self._auditor_unavailable(f"knip timed out after {_KNIP_TIMEOUT_SEC}s")]
        except (subprocess.SubprocessError, OSError) as e:
            return [self._auditor_unavailable(f"knip invocation failed: {e}")]

        if result.returncode > 1:
            return [
                self._auditor_unavailable(
                    f"knip exit code {result.returncode}: {result.stderr.strip()[:200]}"
                )
            ]

        data, parse_finding = safe_parse_json(result.stdout, "knip")
        if parse_finding is not None:
            # Re-emit with TypeScript-specific language metadata + safe allowlist_key.
            return [
                Finding(
                    detector="d1_dead_code",
                    language="typescript",
                    severity="SOFT_CAP",
                    file_path=".",
                    symbol_or_line="knip",
                    message=f"knip JSON output failed to parse: {parse_finding.message}",
                    allowlist_key="typescript|.|dead_code|auditor_output_malformed_knip",
                )
            ]
        return self._parse_knip_json(data, manifest_dir)

    def _find_self_package_name(self, changed_files: list[Path]) -> str | None:
        """Walk up from any changed file to find the repo's package.json#name.

        Used to skip self-reference imports (`@scope/pkg-name` and its subpaths) when the
        codebase is the package being imported — pre-publication code legitimately self-references
        via workspace links (file:..) before the package ships to the npm registry. Cached on
        the detector instance after first lookup.
        """
        if hasattr(self, "_cached_self_name"):
            return self._cached_self_name
        self._cached_self_name = None
        for src_file in changed_files:
            try:
                cur = src_file.resolve().parent if src_file.exists() else Path.cwd()
            except OSError:
                continue
            for parent in [cur, *cur.parents]:
                pkg_json = parent / "package.json"
                if pkg_json.is_file():
                    try:
                        data = json.loads(pkg_json.read_text(encoding="utf-8"))
                        name = data.get("name")
                        # We want the OUTERMOST (root) name when nested workspaces exist —
                        # keep walking up after finding a name. A demo subdir's package name
                        # is shadowed by the root package's name.
                        if isinstance(name, str) and name:
                            self._cached_self_name = name
                    except (json.JSONDecodeError, OSError):
                        pass
            if self._cached_self_name:
                break
        return self._cached_self_name

    def _find_workspace_package_names(self, changed_files: list[Path]) -> frozenset[str]:
        """Every package name the project DECLARES as a workspace member.

        A workspace dependency declared `workspace:*` resolves perfectly; it is simply not
        published, by design. Reported as a fabricated npm import it produces a HARD finding
        on a repository whose build and tests are green — 98 of them in one consumer, measured
        2026-09-19, one message shape, none of them in the change being audited. A gate that
        returns the same verdict whatever the change does has stopped measuring.

        WHY THE DECLARATION AND NOT A DEPTH
        -----------------------------------
        This collected names with two fixed globs — `*/package.json` and `*/*/package.json` —
        while its own docstring claimed to walk "the declared workspace globs". It read no
        globs. A consumer declaring `apps/*/packages/*` keeps its manifests at depth 4, so
        every one of them fell through to the registry; and a `package.json` at depth 2 that
        NO pattern names was collected anyway, so a genuinely fabricated import from such a
        directory would never have been reported either. Wrong in both directions, from the
        same cause.

        `typescript.py`'s own note on three OTHER false-positive families in this file states
        the rule: they shared the root of resolving names "without consulting what the project
        itself declares (workspaces, exports, paths)", and the fix "reads the declaration
        instead of guessing". Workspaces were named there and were the family still guessing.

        THE DIALECT, AND WHY THE STANDARD LIBRARY CANNOT BE HANDED THESE PATTERNS
        ------------------------------------------------------------------------
        Measured on Python 3.10.12 against pnpm's four documented example patterns:

            Path.glob("!**/test/**/package.json")  ValueError, uncaught -> the detector CRASHES
            Path.glob("components/**/package.json")  descends node_modules
            fnmatch("packages/a/node_modules/dep", "packages/*")  True — `*` crosses `/`
            any negation, either matcher  a silent no-op

        And negation is a property of the SET, so no per-pattern loop can express it whatever
        it does per call. `pathspec` implements the dialect — and the GITIGNORE one,
        last-match-wins, under which two of the four documented rows re-include; adopting it
        would swap a matcher that crashes for one that silently disagrees, and it is not a
        declared dependency of this kit besides.

        So: one walk, pruning `node_modules`, then the collected set filtered by the declared
        patterns — positives include, negations exclude, evaluated as a set. Order-independent,
        which is what "as a set" means, verified against `tinyglobby` 0.2.17, the matcher the
        `@manypkg/tools` resolver behind `changesets` actually uses.
        """
        if hasattr(self, "_cached_ws_names"):
            return self._cached_ws_names
        names: set[str] = set()
        for root in find_workspace_roots(changed_files):
            patterns = read_workspace_declaration(root)
            if patterns is None:
                # No declaration here: the pre-2026-09 behaviour, and the ONLY path that keeps
                # it. A repository that declares nothing is not a repository we may guess about
                # more confidently than before.
                for pkg_json in root.glob("*/*/package.json"):
                    self._read_pkg_name(pkg_json, names)
                for pkg_json in root.glob("*/package.json"):
                    self._read_pkg_name(pkg_json, names)
                continue
            for pkg_json in manifests_under(root):
                if declared(pkg_json.parent.relative_to(root).as_posix(), patterns):
                    self._read_pkg_name(pkg_json, names)
        self._cached_ws_names = frozenset(names)
        return self._cached_ws_names

    @staticmethod
    def _read_pkg_name(pkg_json: Path, sink: set[str]) -> None:
        try:
            name = json.loads(pkg_json.read_text(encoding="utf-8")).get("name")
        except (json.JSONDecodeError, OSError):
            return
        if isinstance(name, str) and name:
            sink.add(name)

    @staticmethod
    def _is_self_reference(module: str, self_name: str | None) -> bool:
        if not self_name:
            return False
        return module == self_name or module.startswith(self_name + "/")

    @staticmethod
    def _is_workspace_reference(module: str, ws_names: frozenset[str]) -> bool:
        return any(module == n or module.startswith(n + "/") for n in ws_names)


    def _find_path_aliases(self, changed_files: list[Path]) -> tuple[str, ...]:
        """Prefixes declared as tsconfig `compilerOptions.paths` — local, never npm.

        Patch 2026-08-03, third false-positive family in this detector. `@/components/Button`
        is a PATH ALIAS, not a scoped package: the leading `@` is a convention, and the module
        resolves through tsconfig, not the registry. Treating every `@`-prefixed specifier as a
        scope produced 986 HARD findings in one dashboard, every one of them false.

        The three families share a single root — the detector resolved module names against the
        public registry without consulting what the project itself declares (workspaces,
        exports, paths). This reads the declaration instead of guessing.
        """
        if hasattr(self, "_cached_aliases"):
            return self._cached_aliases
        aliases: set[str] = set()
        seen_roots: set[Path] = set()
        for src_file in changed_files:
            try:
                cur = src_file.resolve().parent if src_file.exists() else Path.cwd()
            except OSError:
                continue
            for _ in range(8):  # bounded walk to the repo root
                if cur in seen_roots:
                    break
                seen_roots.add(cur)
                for name in ("tsconfig.json", "tsconfig.base.json", "jsconfig.json"):
                    cfg = cur / name
                    if not cfg.exists():
                        continue
                    try:
                        raw = cfg.read_text(encoding="utf-8", errors="replace")
                        # tsconfig admite comentarios; JSON estrito falharia
                        raw = re.sub(r"//[^\n]*", "", raw)
                        raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
                        raw = re.sub(r",(\s*[}\]])", r"\1", raw)
                        data = json.loads(raw)
                    except (OSError, ValueError):
                        continue
                    paths = (data.get("compilerOptions") or {}).get("paths") or {}
                    for pattern in paths:
                        aliases.add(pattern.split("*")[0].rstrip("/"))
                if (cur / ".git").exists() or cur.parent == cur:
                    break
                cur = cur.parent
        self._cached_aliases = tuple(sorted(a for a in aliases if a))
        return self._cached_aliases

    @staticmethod
    def _is_path_alias(module: str, aliases: tuple[str, ...]) -> bool:
        """True when the specifier matches a declared tsconfig path alias."""
        return any(module == a or module.startswith(a + "/") for a in aliases)

    def detect_symbol_fabrication(self, changed_files: list[Path]) -> list[Finding]:
        """T2.3 — Validate imports against npm. Skip relative + node: builtins + monorepo subpath (EC-16) + self-references (patch 2026-05-30)."""
        findings: list[Finding] = []
        # Vacuity guard, the same one `rust.py` carries and for the same measured reason:
        # `extract_checked` reports whether the parser RAN, and an empty symbol list from
        # a parse that never happened reads to D2 as "this file imports nothing" — a
        # silent false-green over an audit that did not run. Reported as unavailable,
        # never as clean.
        parsed_any = False
        unparsed = 0
        self_name = self._find_self_package_name(changed_files)
        ws_names = self._find_workspace_package_names(changed_files)
        aliases = self._find_path_aliases(changed_files)
        for src_file in changed_files:
            if not src_file.exists():
                continue
            rel = to_rel_path(src_file)
            symbols, parsed = extract_checked(src_file, "typescript")
            parsed_any = parsed_any or parsed
            unparsed += 0 if parsed else 1
            for sym in symbols:
                if sym.kind != "import":
                    continue
                module = sym.module
                if not module:
                    continue
                # Relative imports
                if module.startswith("./") or module.startswith("../") or module == "." or module == "..":
                    continue
                # Node builtins
                if module.startswith("node:"):
                    continue
                top = module.split("/")[0] if not module.startswith("@") else "/".join(module.split("/")[:2])
                if top in _TS_NODE_BUILTINS:
                    continue
                # Patch 2026-05-30 — Self-reference (the workspace IS the package being imported)
                if self._is_self_reference(module, self_name):
                    continue
                # Patch 2026-08-03 — Sibling workspace package (declared `workspace:*`, unpublished by design)
                if self._is_workspace_reference(module, ws_names):
                    continue
                # Patch 2026-08-03 — tsconfig path alias (`@/components/...`), not an npm package
                if self._is_path_alias(module, aliases):
                    continue
                # Package name for npm lookup. `top` already collapses a scoped module to
                # `@scope/name`; using `module` here sent the whole SUBPATH to the registry
                # (`@modelcontextprotocol/sdk/server/mcp.js` is not a package name), which is
                # what produced 52 `ambiguous response` findings against a real, installed SDK.
                pkg = top if module.startswith("@") else module.split("/")[0]
                exists = _registry.package_exists_on_npm(pkg)
                if exists is True:
                    continue
                sanitized = sanitize_symbol(pkg)
                if exists is False:
                    findings.append(
                        Finding(
                            detector="d2_symbol_fab",
                            language="typescript",
                            severity="HARD",
                            file_path=rel,
                            symbol_or_line=f"import from '{module}'",
                            message=f"Fabricated npm package '{pkg}' (not found on registry)",
                            allowlist_key=f"typescript|{rel}|symbol_fab|{sanitized}",
                        )
                    )
                else:
                    findings.append(
                        Finding(
                            detector="d2_symbol_fab",
                            language="typescript",
                            severity="SOFT_FLOOR",
                            file_path=rel,
                            symbol_or_line=f"import from '{module}'",
                            message=f"Could not verify npm package '{pkg}' (ambiguous response)",
                            allowlist_key=f"typescript|{rel}|symbol_fab|symbol_fab_unverifiable_{sanitized}",
                        )
                    )
        if unparsed and not parsed_any:
            return [
                Finding(
                    detector="d2_symbol_fab",
                    language="typescript",
                    severity="SOFT_CAP",
                    file_path=".",
                    symbol_or_line="tree-sitter",
                    message=(
                        f"D2 parsed none of the {unparsed} TypeScript source(s) it was "
                        f"given — the tree-sitter grammar is unavailable or failed to "
                        f"load. The audit did not run; this is NOT evidence that no "
                        f"symbol is fabricated."
                    ),
                    allowlist_key="typescript|.|symbol_fab|auditor_unavailable_tree-sitter",
                )
            ]

        return findings

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _parse_knip_json(self, data: dict, repo_root: Path) -> list[Finding]:
        findings: list[Finding] = []

        for file_path in data.get("files", []) or []:
            findings.append(self._make_finding(file_path, "unimported file", "file", repo_root))

        for export in data.get("exports", []) or []:
            file_path = export.get("file", "<unknown>")
            name = export.get("name", "<unknown>")
            findings.append(
                self._make_finding(file_path, f"unused export '{name}'", name, repo_root)
            )

        for dep in data.get("dependencies", []) or []:
            name = dep.get("name") if isinstance(dep, dict) else str(dep)
            findings.append(
                self._make_finding("package.json", f"unused dependency '{name}'", name, repo_root)
            )

        for dep in data.get("devDependencies", []) or []:
            name = dep.get("name") if isinstance(dep, dict) else str(dep)
            findings.append(
                self._make_finding(
                    "package.json", f"unused devDependency '{name}'", name, repo_root
                )
            )

        return findings

    def _make_finding(
        self, file_path: str, message: str, symbol: str, repo_root: Path
    ) -> Finding:
        rel = self._safe_relative(file_path, repo_root)
        sanitized = sanitize_symbol(symbol)
        return Finding(
            detector="d1_dead_code",
            language="typescript",
            severity="HARD",
            file_path=rel,
            symbol_or_line=f"{symbol} @ {rel}",
            message=message,
            allowlist_key=f"typescript|{rel}|dead_code|{sanitized}",
        )

    @staticmethod
    def _safe_relative(file_path: str, repo_root: Path) -> str:
        path = Path(file_path)
        if path.is_absolute():
            try:
                return path.relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                return path.as_posix().lstrip("/")
        return path.as_posix()

    def _auditor_unavailable(self, reason: str) -> Finding:
        return Finding(
            detector="d1_dead_code",
            language="typescript",
            severity="SOFT_CAP",
            file_path=".",
            symbol_or_line="knip",
            message=f"Knip auditor unavailable: {reason}",
            allowlist_key="typescript|.|dead_code|auditor_unavailable_knip",
        )

    # ── D5 — architecture ───────────────────────────────────────────────────────────────────────

    def detect_architecture_violations(self, manifest_dir: Path) -> list[Finding]:
        """Run the repo's OWN dependency-cruiser script, plus the meta-gate on its rules.

        D5 invokes the npm script the repo declares rather than guessing which directories to
        cruise. Two reasons, both measured. The paths a cruise covers ARE an architectural
        decision — choosing them here would be Squad deciding what counts as the codebase. And
        `npm run` resolves the LOCAL binary: a TypeScript monorepo measured the global
        `depcruise` cruising **0 modules** against a config the local one cruised 279 with. A
        global binary runs without the project's transpilers, so it silently sees nothing.

        That second failure is why `totalCruised == 0` is treated as a vacuous run and not as a
        clean one. A cruise that reached no modules reports zero violations — green — having
        verified nothing.
        """
        pkg = manifest_dir / "package.json"
        if not pkg.is_file():
            return [_arch.no_config("typescript", tool="dependency-cruiser", looked_for=["package.json"])]

        findings = self._tsarch_selfcheck(manifest_dir, pkg)

        script = _depcruise_script(pkg)
        if script is None:
            return findings + [
                _arch.no_config(
                    "typescript",
                    tool="dependency-cruiser",
                    looked_for=["a package.json script running `depcruise`"],
                )
            ]

        try:
            result = subprocess.run(
                ["npm", "run", "--silent", script, "--", "--output-type", "json"],
                cwd=str(manifest_dir),
                capture_output=True,
                text=True,
                timeout=_ARCH_TIMEOUT_SEC,
                check=False,
            )
        except FileNotFoundError:
            return findings + [
                _arch.auditor_unavailable("typescript", tool="dependency-cruiser", reason="npm not found")
            ]
        except subprocess.TimeoutExpired:
            return findings + [
                _arch.auditor_unavailable(
                    "typescript", tool="dependency-cruiser", reason=f"timed out after {_ARCH_TIMEOUT_SEC}s"
                )
            ]
        except (subprocess.SubprocessError, OSError) as e:
            return findings + [
                _arch.auditor_unavailable(
                    "typescript", tool="dependency-cruiser", reason=f"invocation failed: {e}"
                )
            ]

        if not result.stdout.strip():
            return findings + [
                _arch.auditor_unavailable(
                    "typescript",
                    tool="dependency-cruiser",
                    reason=(
                        f"`npm run {script}` exit {result.returncode} produced no output: "
                        f"{result.stderr.strip()[:200]}"
                    ),
                )
            ]

        data, parse_finding = safe_parse_json(result.stdout, "dependency-cruiser")
        if parse_finding is not None:
            return findings + [
                _arch.auditor_unavailable(
                    "typescript",
                    tool="dependency-cruiser",
                    reason=(
                        f"JSON output failed to parse — is `{script}` printing anything before the "
                        f"payload? ({parse_finding.message})"
                    ),
                )
            ]
        return findings + self._parse_depcruise_json(data, script)

    def _parse_depcruise_json(self, data: object, script: str) -> list[Finding]:
        if not isinstance(data, dict) or not isinstance(data.get("summary"), dict):
            return [
                _arch.auditor_unavailable(
                    "typescript", tool="dependency-cruiser", reason="payload had no 'summary' object"
                )
            ]
        summary = data["summary"]
        findings: list[Finding] = []

        cruised = summary.get("totalCruised") or 0
        if cruised == 0:
            return [
                _arch.vacuous_rule(
                    "typescript",
                    tool="dependency-cruiser",
                    rule=f"npm run {script}",
                    config_path="package.json",
                    detail=(
                        "the cruise reached 0 modules, so every rule passed without inspecting "
                        "anything. Usually a global binary running without the project's "
                        "transpilers, or paths that no longer exist"
                    ),
                )
            ]

        for violation in summary.get("violations") or []:
            if not isinstance(violation, dict):
                continue
            rule = (violation.get("rule") or {}).get("name", "?")
            severity = "HARD" if (violation.get("rule") or {}).get("severity") == "error" else "SOFT_FLOOR"
            source = str(violation.get("from", "?"))
            target = str(violation.get("to", "?"))
            findings.append(
                Finding(
                    detector=_arch.D5,
                    language="typescript",
                    severity=severity,
                    file_path=source,
                    symbol_or_line=rule,
                    message=f"[dependency-cruiser] {rule}: {source} -> {target}",
                    allowlist_key=f"typescript|{source}|architecture|{sanitize_symbol(rule)}",
                )
            )

        sources = {str(m.get("source", "")) for m in (data.get("modules") or []) if isinstance(m, dict)}
        findings.extend(_rule_selfcheck(summary.get("ruleSetUsed") or {}, sources))
        return findings

    def _tsarch_selfcheck(self, manifest_dir: Path, pkg: Path) -> list[Finding]:
        """`tsarch` declared but never imported is an auditor that never runs.

        tsarch asserts from inside the test framework, so D5 cannot invoke it — the repo's own
        suite does. What D5 can establish is that the suite actually uses it. A devDependency no
        test imports is the shape theo's #255 catalogued nine times over: a gate implemented,
        registered, and never executed, whose presence reads as coverage.
        """
        try:
            declared = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        deps = {**(declared.get("dependencies") or {}), **(declared.get("devDependencies") or {})}
        if "tsarch" not in deps:
            return []

        for path in manifest_dir.rglob("*.ts"):
            if "node_modules" in path.parts:
                continue
            try:
                if "tsarch" in path.read_text(encoding="utf-8", errors="replace"):
                    return []
            except OSError:
                continue
        return [
            Finding(
                detector=_arch.D5,
                language="typescript",
                severity="SOFT_FLOOR",
                file_path="package.json",
                symbol_or_line="tsarch",
                message=(
                    "`tsarch` is declared as a dependency and no source file imports it. An "
                    "architecture auditor that never runs still reads as coverage to anyone "
                    "scanning package.json — either write the assertions or drop the dependency."
                ),
                allowlist_key="typescript|package.json|architecture|tsarch_declared_unused",
            )
        ]


def _depcruise_script(pkg: Path) -> str | None:
    """The npm script that runs dependency-cruiser, if the repo declares one."""
    try:
        declared = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    matches = [
        str(name)
        for name, command in (declared.get("scripts") or {}).items()
        if "depcruise" in command or "dependency-cruiser" in command
    ]
    if not matches:
        return None
    # B-166 (an adopter) — prefer a script that runs ONLY the cruise. Returning the first match picks
    # whatever `package.json` happens to list first, and in a real repository that is the lint chain:
    # a `lint` that ends in `npm run depcruise` contains the token and usually sorts before the
    # dedicated script. Measured on an adopter: matches were `['lint', 'depcruise']`, first won, so the
    # detector ran eslint, knip and seven checkers instead of the cruise — and reported
    # `auditor_unavailable_dependency-cruiser` whenever any unrelated link failed, while `depcruise`
    # was on PATH and cruised 278 modules clean.
    #
    # "Only the cruise" is read as: no shell chaining, and no delegation back through the package
    # manager. Both are what make a script a chain rather than a command.
    for name in matches:
        command = str((declared.get("scripts") or {})[name])
        chained = any(token in command for token in ("&&", "||", ";", "|"))
        delegates = any(token in command for token in ("npm run", "pnpm run", "yarn run", "npm-run-all"))
        if not chained and not delegates:
            return name
    # Every match is a chain. Running one is worse than running the cruise directly and better than
    # reporting no auditor at all, so the first is still used — the previous behaviour, now reached
    # deliberately rather than by ordering.
    return matches[0]


def _rule_selfcheck(rule_set: dict, sources: set[str]) -> list[Finding]:
    """Every directory a rule names must still be in the cruised tree.

    Split by which side of the rule the name sits on, because the two mean different things:

    - `from` selects the code the rule GOVERNS. If it matches nothing, the rule governs nothing
      and can never fire — the invariant evaporated. HARD.
    - `to` and `pathNot` may legitimately match nothing: `no-sdk-direto` forbids importing a
      package precisely so that nobody imports it, and demanding a match there would force every
      preventive rule to be violated once before it is believed. SOFT_FLOOR, and external
      (`node_modules/…`) targets are skipped entirely.
    """
    findings: list[Finding] = []
    for rule in rule_set.get("forbidden") or []:
        if not isinstance(rule, dict):
            continue
        name = str(rule.get("name", "?"))

        if not _arch.reason_has_substance(rule.get("comment")):
            findings.append(
                _arch.rule_without_reason(
                    "typescript", tool="dependency-cruiser", rule=name, config_path="package.json"
                )
            )

        for side, pattern, severity in (
            ("from", (rule.get("from") or {}).get("path"), "HARD"),
            ("to", (rule.get("to") or {}).get("path"), "SOFT_FLOOR"),
        ):
            for token in _path_tokens(pattern):
                if token.startswith("node_modules"):
                    continue
                if any(s.startswith(token) for s in sources):
                    continue
                detail = f"its `{side}` names `{token}`, which no cruised module is under"
                if severity == "HARD":
                    findings.append(
                        _arch.vacuous_rule(
                            "typescript",
                            tool="dependency-cruiser",
                            rule=name,
                            config_path="package.json",
                            detail=detail,
                        )
                    )
                else:
                    findings.append(
                        Finding(
                            detector=_arch.D5,
                            language="typescript",
                            severity="SOFT_FLOOR",
                            file_path="package.json",
                            symbol_or_line=name,
                            message=(
                                f"[dependency-cruiser] rule '{name}': {detail}. Fine for a rule "
                                "that forbids something nobody does — stale if the directory was "
                                "renamed."
                            ),
                            allowlist_key=f"typescript|package.json|architecture|stale_{sanitize_symbol(name)}",
                        )
                    )
    return findings


def _path_tokens(pattern: object) -> list[str]:
    """Directory-shaped literals inside a regex. Single words are skipped on purpose.

    `index` in `(?!index)` is a filename fragment, not a directory, and flagging it would make the
    meta-gate noisy — which is how a gate earns being switched off.
    """
    if not isinstance(pattern, str):
        return []
    return sorted({m.group(0).rstrip("/") for m in _PATH_TOKEN_RE.finditer(pattern)})

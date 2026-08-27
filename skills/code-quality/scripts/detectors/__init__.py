"""Detector interface contract for the `/code-quality` skill.

The `BaseDetector` abstract class defines the per-language detection surface.
Each language adapter (python.py, typescript.py, rust.py, go.py) subclasses
this base and implements the four detection methods.

Concrete adapters whose external auditor is unavailable return an explicit verdict-capping
Finding; missing work is never represented as an empty successful result.
"""
from __future__ import annotations

from pathlib import Path

from scripts._shared import Finding


class BaseDetector:
    """Abstract per-language detector contract.

    Concrete subclasses set `language` + `manifest_marker` class attributes
    and override the four detection methods. The orchestrator (T5.1) builds
    one Detector instance per language enabled in `code-quality-languages.txt`
    that has its manifest present at repo root.

    All detection methods return `list[Finding]`. Empty list = no findings.
    Detectors NEVER raise for "expected" failure modes (missing binary,
    timeout, malformed output) — they emit `auditor_unavailable_{tool}`
    Findings instead, per the golden rule.
    """

    language: str = ""
    manifest_marker: str = ""

    #: Per-project knobs from `code-quality-thresholds.txt`, injected by the
    #: orchestrator. Empty means "use the shipped defaults" — never "no gate".
    thresholds: dict = {}

    def threshold(self, key: str, default):
        """Read one knob, falling back to the shipped default.

        `load_thresholds()` was called for its parse side-effect and its result
        discarded, with the orchestrator noting that "detectors use hardcoded
        defaults in v0.1" — so every documented key in the rules file was inert.
        A configuration file that cannot change behaviour is worse than none: it
        reads as a control that exists.
        """
        value = self.thresholds.get(key, default)
        return type(default)(value) if default is not None and value is not None else value

    def unavailable(self, detector: str, finding_type: str, message: str) -> list[Finding]:
        """Represent a detector capability that could not run without failing open."""
        return [
            Finding(
                detector=f"{detector}_unavailable",
                language=self.language,
                severity="SOFT_CAP",
                file_path=".",
                symbol_or_line=detector,
                message=f"auditor unavailable: {message}",
                allowlist_key=f"{self.language}|.|{finding_type}|auditor_unavailable_{detector}",
            )
        ]

    def detect_dead_code(self, manifest_dir: Path) -> list:
        """Run D1 — language-specific dead code detector.

        Wraps external CLI (vulture / knip / cargo-udeps / deadcode).
        Emits `Finding(detector="d1_dead_code", severity="HARD", ...)`
        per unallowlisted item.
        """
        raise NotImplementedError

    def detect_symbol_fabrication(self, changed_files: list[Path]) -> list:
        """Run D2 — fabricated package/API detection via tree-sitter + registry lookup.

        Skips module-local imports (relative / crate:: / self-module),
        stdlib modules, and monorepo internal subpath exports.
        """
        raise NotImplementedError

    def detect_orphan_exports(self, repo_root: Path) -> list:
        """Run D3 — cross-package wiring (orphan exports detection).

        SOFT_CAP per golden rule. Skips test files, barrel files, declared
        entry points.
        """
        raise NotImplementedError

    def detect_mutation_score(self, manifest_dir: Path) -> list:
        """Run D4 — mutation testing, scoped by the project's own mutation config.

        Wraps mutmut (Python) / Stryker (TypeScript); Rust and Go are declared
        deferrals per golden rule § 5.

        The parameter used to be `critical_paths: list[Path]` and the orchestrator
        passed every source file in the language. Neither runner accepts an
        arbitrary file list as scope — both read what the project declared
        (`[mutmut] source_paths`, `stryker.config.json`) — so the list was built,
        passed, and dropped. Handing the runner the directory it actually resolves
        from removes a parameter that documented a scoping that never happened.
        """
        raise NotImplementedError

    def detect_architecture_violations(self, manifest_dir: Path) -> list:
        """Run D5 — declared architecture rules, plus the meta-gate on the rules themselves.

        Wraps the language's architecture linter against the config the REPO
        declares (`.dependency-cruiser.cjs` / `.go-arch-lint.yml` /
        `Layerfile.toml`). Squad ships no layer model of its own: a rule
        asserting an architecture nobody declared would report violations that
        are evidence of nothing. A repo with no config emits INFO and is
        skipped — the honest state, not a failure.

        Beyond forwarding the tool's verdict, D5 asserts the rules are not
        VACUOUS. Measured on 2026-08-06 against `theo-contracts`: a
        `.go-arch-lint.yml` naming a directory that does not exist reports
        `ArchHasWarnings: false` — green — while the invariant it encoded can
        no longer fire. The same class was measured in usetheo-labs/agent-builder,
        where dissolving `tui/lib` would have left rules written against the old
        name matching nothing, and `npm run boundaries` reporting success.

        A rule that cannot fail is worse than no rule: it transfers confidence
        to a mechanism that stopped existing.
        """
        raise NotImplementedError

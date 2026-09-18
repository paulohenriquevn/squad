"""D3 — cross-package wiring: a public export nobody imports.

Shared by the four language detectors, the way `_arch.py` is shared by D5. The
question is one question in every language — *does anything consume what this
package publishes?* — and only the shape of "publishes" changes.

WHY THE PUBLIC SURFACE IS DECLARED, NEVER INFERRED
--------------------------------------------------
The tempting definition of "public export" is every name without a leading
underscore. Applied to a repository of scripts it produces hundreds of findings:
a function called only inside its own file is internal in fact, and reporting it
as an orphan turns the detector into noise — the most efficient way to disable a
gate without removing it.

So D3 audits what the project DECLARED:

| Language   | Declared surface                                                  |
|---|---|
| Python     | `__all__`, plus names re-exported from `__init__.py`              |
| TypeScript | the files `package.json` points at (`main`/`module`/`types`/`exports`) |
| Rust       | `pub` items in `src/lib.rs` — the crate's own surface              |
| Go         | exported identifiers outside `internal/` (which the compiler seals) |

A project that declares no surface gets an INFO saying exactly that. The wrong
answer would be to infer one and emit SOFT_CAP against it — a verdict about a
contract nobody wrote.

WHY A TEST IS NOT A CONSUMER
----------------------------
The same reasoning as pillar (a) of the wiring triad: a test proves the code
WORKS, not that anything USES it. Counting the test as an importer is how the
coverage gate used to count a runner's exit code as a measurement.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts._detector_contract import (
    Finding,
    enumerate_source_files,
    make_relative,
    sanitize_symbol,
)

#: Directory names whose contents exercise code rather than consume it.
_TEST_DIR_NAMES = frozenset({"test", "tests", "__tests__", "spec", "testdata", "e2e"})

#: Filename shapes that mark a test across the four ecosystems.
_TEST_FILE_RE = re.compile(r"(^test_|_test\.|\.test\.|\.spec\.|_test$)")

_PY_ALL_RE = re.compile(r"^__all__\s*=\s*\[(?P<body>.*?)\]", re.MULTILINE | re.DOTALL)
_PY_STRING_RE = re.compile(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")
#: A re-export in an `__init__.py`: a name the package republishes from ITS OWN
#: modules. The module part is captured so the caller can tell that apart from a
#: dependency — `from typing import TypeVar` used to land three typing primitives on
#: the kit's public surface, and `TypeVar` was then reported as an orphan export whose
#: only available fix would have been to stop importing `typing` (kit#63).
_PY_INIT_IMPORT_RE = re.compile(
    r"^from\s+(?P<module>[.\w]+)\s+import\s+(?P<names>[^#\n(]+)", re.MULTILINE
)

_TS_EXPORT_RE = re.compile(
    r"^export\s+(?:declare\s+)?(?:async\s+)?"
    r"(?:function|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
_RS_PUB_RE = re.compile(
    r"^pub(?:\s*\([^)]*\))?\s+(?:async\s+)?(?:fn|struct|enum|trait|const|static|type)\s+"
    r"([A-Za-z_][\w]*)",
    re.MULTILINE,
)
_GO_EXPORTED_RE = re.compile(
    r"^func\s+(?:\([^)]*\)\s*)?([A-Z]\w*)|^(?:type|var|const)\s+([A-Z]\w*)",
    re.MULTILINE,
)


def _is_test_path(path: Path) -> bool:
    if any(part in _TEST_DIR_NAMES for part in path.parts):
        return True
    return bool(_TEST_FILE_RE.search(path.name))


def _unavailable(language: str, reason: str) -> list[Finding]:
    return [
        Finding(
            detector="d3_unavailable",
            language=language,
            severity="SOFT_CAP",
            file_path=".",
            symbol_or_line="d3",
            message=f"auditor unavailable: {reason}",
            allowlist_key=f"{language}|.|orphan_export|auditor_unavailable_d3",
        )
    ]


def _no_surface(language: str, looked_for: str) -> list[Finding]:
    return [
        Finding(
            detector="d3_orphan_export_skipped",
            language=language,
            severity="INFO",
            file_path=".",
            symbol_or_line="d3",
            message=(
                f"no declared public surface to audit ({looked_for}) — D3 has nothing to "
                "assert here, which is the honest result, not a pass"
            ),
            allowlist_key=f"{language}|.|orphan_export|d3_no_public_surface",
        )
    ]


def _orphan(language: str, symbol: str, path: Path, repo_root: Path) -> Finding:
    rel = make_relative(path, repo_root)
    return Finding(
        detector="d3_orphan_export",
        language=language,
        severity="SOFT_CAP",
        file_path=rel,
        symbol_or_line=symbol,
        message=(
            f"`{symbol}` is published by {rel} and no production file imports it — "
            "an export nobody consumes is surface that costs maintenance and buys nothing"
        ),
        allowlist_key=f"{language}|{rel}|orphan_export|{sanitize_symbol(symbol)}",
    )


# ---------------------------------------------------------------------------
# Declared surface, per language
# ---------------------------------------------------------------------------

def _python_surface(manifest_dir: Path) -> list[tuple[str, Path]]:
    surface: list[tuple[str, Path]] = []
    for path in enumerate_source_files(manifest_dir, "python"):
        if _is_test_path(path):
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _PY_ALL_RE.finditer(body):
            surface.extend((name, path) for name in _PY_STRING_RE.findall(match.group("body")))
        if path.name == "__init__.py":
            package = path.parent.name
            for match in _PY_INIT_IMPORT_RE.finditer(body):
                module = match.group("module")
                # Relative (`from .engine import x`) or same-package
                # (`from mypkg.helpers import x`) is a re-export. An absolute import of
                # anything else is a dependency this module happens to need, and
                # publishing it as this package's surface makes the finding unactionable.
                if not (module.startswith(".") or module.split(".")[0] == package):
                    continue
                for raw in match.group("names").split(","):
                    name = raw.strip().split(" as ")[-1].strip()
                    if name and name != "*" and not name.startswith("_"):
                        surface.append((name, path))
    return surface


def _typescript_entrypoints(manifest_dir: Path) -> list[Path]:
    manifest = manifest_dir / "package.json"
    if not manifest.is_file():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    candidates: list[str] = []
    for key in ("main", "module", "types", "typings"):
        value = data.get(key)
        if isinstance(value, str):
            candidates.append(value)
    exports = data.get("exports")
    if isinstance(exports, str):
        candidates.append(exports)
    elif isinstance(exports, dict):
        for value in exports.values():
            if isinstance(value, str):
                candidates.append(value)
            elif isinstance(value, dict):
                candidates.extend(v for v in value.values() if isinstance(v, str))

    resolved: list[Path] = []
    for candidate in candidates:
        path = manifest_dir / candidate.lstrip("./")
        if path.is_file():
            resolved.append(path)
            continue
        # `main: dist/index.js` is the BUILD output. The source that produced it is what
        # a reviewer can read and what an importer names, so map the compiled path back.
        for ext in (".ts", ".tsx"):
            for base in (path.with_suffix(ext), manifest_dir / "src" / (Path(candidate).stem + ext)):
                if base.is_file() and base not in resolved:
                    resolved.append(base)
    return resolved


def _typescript_surface(manifest_dir: Path) -> list[tuple[str, Path]]:
    surface: list[tuple[str, Path]] = []
    for path in _typescript_entrypoints(manifest_dir):
        if _is_test_path(path):
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        surface.extend((name, path) for name in _TS_EXPORT_RE.findall(body))
    return surface


def _rust_surface(manifest_dir: Path) -> list[tuple[str, Path]]:
    lib = manifest_dir / "src" / "lib.rs"
    if not lib.is_file():
        return []
    try:
        body = lib.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [(name, lib) for name in _RS_PUB_RE.findall(body)]


def _go_surface(manifest_dir: Path) -> list[tuple[str, Path]]:
    surface: list[tuple[str, Path]] = []
    for path in enumerate_source_files(manifest_dir, "go"):
        if _is_test_path(path) or "internal" in path.parts:
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"^package\s+main\b", body, re.MULTILINE):
            continue
        for func_name, decl_name in _GO_EXPORTED_RE.findall(body):
            name = func_name or decl_name
            if name:
                surface.append((name, path))
    return surface


_SURFACE_BY_LANGUAGE = {
    "python": (_python_surface, "`__all__` or `__init__.py` re-exports"),
    "typescript": (_typescript_surface, "`package.json` main/module/types/exports"),
    "rust": (_rust_surface, "`pub` items in src/lib.rs"),
    "go": (_go_surface, "exported identifiers outside internal/"),
}


# ---------------------------------------------------------------------------
# Consumption
# ---------------------------------------------------------------------------

#: Lines that DEFINE a symbol rather than CONSUME it. A file whose only occurrences
#: of the symbol match these shapes is the definition site, not a consumer — and
#: without this distinction a re-export in `__init__.py` always finds a "consumer":
#: the very module where the function is written.
#:
#: Same knowledge `skills/implement/scripts/check_wiring.py` encodes for pillar (a)
#: of the triad. The two copies exist because one skill importing another's scripts
#: would create a cycle between packages the installer treats as independent; the
#: duplication is of PATTERN (definition syntax), not of business rule, and each
#: side has its own tests.
_DEFINITION_PATTERNS = (
    r"^\s*(?:async\s+)?def\s+{sym}\b",
    r"^\s*class\s+{sym}\b",
    r"^\s*(?:export\s+)?(?:declare\s+)?(?:async\s+)?function\s+{sym}\b",
    r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+{sym}\b",
    r"^\s*(?:export\s+)?(?:interface|type|enum)\s+{sym}\b",
    r"^\s*(?:export\s+)?(?:const|let|var)\s+{sym}\b",
    r"^\s*pub(?:\s*\([^)]*\))?\s+(?:async\s+)?(?:fn|struct|enum|trait|const|static|type)\s+{sym}\b",
    r"^\s*func\s+(?:\([^)]*\)\s*)?{sym}\b",
    r"^\s*(?:type|var|const)\s+{sym}\b",
    r"^__all__\s*=",
)


def _is_definition_only(body: str, symbol: str) -> bool:
    """True when every mention of the symbol in this text is its definition."""
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    definitions = [re.compile(p.format(sym=re.escape(symbol))) for p in _DEFINITION_PATTERNS]
    saw_mention = False
    for line in body.splitlines():
        if not pattern.search(line):
            continue
        saw_mention = True
        if not any(d.search(line) for d in definitions):
            return False
    return saw_mention


#: Public export signatures, per language. A symbol named in one of them is
#: reachable by whoever calls that export — it lives through it, even without an
#: importer of its own.
_PUBLIC_SIGNATURE_RE = re.compile(
    r"^(?:export\s+)?(?:pub(?:\s*\([^)]*\))?\s+)?(?:async\s+)?"
    r"(?:def|function|func|fn)\s+(?P<name>[A-Za-z_$][\w$]*)\s*(?P<sig>\([^\n]*\)[^\n:{]*)",
    re.MULTILINE,
)


def _reachable_through_a_public_signature(symbol: str, body: str, surface_names: set[str]) -> bool:
    """True when another export of the same module names the symbol in its signature.

    Measured on the kit itself: `AllowlistEntry` is `load_allowlist`'s return type
    and no file imports it by name — whoever calls the function receives the
    instance. Calling it an orphan would push the project to remove it from the
    surface, breaking anyone who wanted to annotate the return. A false positive at
    SOFT_CAP costs the same as at HARD: it generates a spurious allowlist entry and
    teaches people to ignore the gate.

    The rule requires the signature to belong to ANOTHER EXPORT. If any function in
    the module were enough, an internal helper annotating the type would erase it
    from the report, and the gate would stop seeing dead surface.
    """
    mention = re.compile(rf"\b{re.escape(symbol)}\b")
    for match in _PUBLIC_SIGNATURE_RE.finditer(body):
        name = match.group("name")
        if name == symbol or name not in surface_names:
            continue
        if mention.search(match.group("sig")):
            return True
    return False


#: File bodies read during one audit, keyed by path. The whole tree used to be re-read
#: from disk ONCE PER EXPORTED SYMBOL — on a surface of 400 exports over 900 files that
#: is 360,000 reads of the same bytes, and the audit's own runtime is what decides
#: whether anyone runs it before pushing. Bounded by the audit: `reset_source_cache()`
#: is called at the top of a run so a long-lived process never serves a stale body.
_SOURCE_CACHE: dict[Path, str | None] = {}


def reset_source_cache() -> None:
    """Forget every cached body. Called when an audit begins."""
    _SOURCE_CACHE.clear()


def _body_of(path: Path) -> str | None:
    if path not in _SOURCE_CACHE:
        try:
            _SOURCE_CACHE[path] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            _SOURCE_CACHE[path] = None
    return _SOURCE_CACHE[path]


def _has_consumer(symbol: str, defining: Path, sources: list[Path]) -> bool:
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    for path in sources:
        if path == defining or _is_test_path(path):
            continue
        body = _body_of(path)
        if body is None:
            continue
        if not pattern.search(body):
            continue
        if _is_definition_only(body, symbol):
            continue
        return True
    return False


def detect_orphan_exports(language: str, manifest_dir: Path, repo_root: Path) -> list[Finding]:
    """Return one SOFT_CAP Finding per declared export that nothing consumes."""
    # Bounded to THIS audit. The cache below turns the per-symbol re-read of the whole
    # tree into one read per file; clearing it here means a long-lived process auditing
    # twice never serves a body from before an edit.
    reset_source_cache()
    entry = _SURFACE_BY_LANGUAGE.get(language)
    if entry is None:
        return _unavailable(language, f"no D3 surface model for language {language!r}")
    build_surface, looked_for = entry

    surface = build_surface(manifest_dir)
    if not surface:
        return _no_surface(language, looked_for)

    sources = list(enumerate_source_files(repo_root, language))
    surface_by_file: dict[Path, set[str]] = {}
    for symbol, defining in surface:
        surface_by_file.setdefault(defining, set()).add(symbol)

    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for symbol, defining in surface:
        key = (symbol, str(defining))
        if key in seen:
            continue
        seen.add(key)
        if _has_consumer(symbol, defining, sources):
            continue
        body = _body_of(defining) or ""
        if _reachable_through_a_public_signature(symbol, body, surface_by_file.get(defining, set())):
            continue
        findings.append(_orphan(language, symbol, defining, repo_root))
    return findings

"""Shared registry-lookup cache for D2 (symbol fabrication) detection.

Provides per-ecosystem `package_exists_*` functions that hit the respective
registry (PyPI / npm / crates.io / Go proxy) and cache results for 24h
(per `code-quality-thresholds.txt:symbol_fab.cache_ttl_hours`).

Per ADR D5: deterministic; never falls back to LLM-as-judge.
Per EC-2: HTML-response ambiguity returns None (not False) — prevents
false-positive HARD findings during registry outages.
Per EC-3: corrupted cache file is detected + discarded + re-fetched.
Per EC-9: cache writes use `write_atomic` for crash-safe concurrent CI runs.
"""
from __future__ import annotations

import atexit
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from scripts._detector_contract import write_atomic

_CACHE_DIR_ENV = "CODE_QUALITY_CACHE_DIR"
_CACHE_TTL_SECONDS = 24 * 3600  # 24h per thresholds default
_HTTP_TIMEOUT_SECONDS = 5
_USER_AGENT = "code-quality-skill/0.1 (audit only)"

# --- NETWORK BUDGET FOR THE WHOLE RUN ----------------------------------------
# Each query has a 5s timeout, they are serial, and an ambiguous result is not
# cached — correctly: a network failure is not proof that the package does not
# exist. What was missing was a bound for the SET. On an offline machine or
# behind a proxy, 100 unknown imports cost 500s of waiting that never became an
# answer, on every run, indefinitely.
#
# After _MAX_CONSECUTIVE_FAILURES consecutive failures, D2 declares the network
# unavailable and returns None immediately — the SAME ambiguous verdict as
# before, without the wait. A single hit resets the counter, so a blip does not
# switch the detector off for the rest of the run.
_MAX_CONSECUTIVE_FAILURES = 3
_NETWORK_BUDGET_SECONDS = 30.0

_consecutive_failures = 0
_network_seconds_spent = 0.0
_network_unavailable = False

# In-memory cache per ecosystem, written to disk ONCE (see flush_caches).
_memory_cache: dict[str, dict[str, Any]] = {}
_dirty_ecosystems: set[str] = set()


def reset_network_state() -> None:
    """Resets breaker, budget and in-memory cache. For tests and re-runs."""
    global _consecutive_failures, _network_seconds_spent, _network_unavailable
    _consecutive_failures = 0
    _network_seconds_spent = 0.0
    _network_unavailable = False
    _memory_cache.clear()
    _dirty_ecosystems.clear()


def network_is_available() -> bool:
    """False when the breaker has opened or the run's budget is exhausted."""
    if _network_unavailable:
        return False
    return _network_seconds_spent < _NETWORK_BUDGET_SECONDS


def _cache_dir() -> Path:
    override = os.environ.get(_CACHE_DIR_ENV)
    if override:
        return Path(override)
    return Path.home() / ".cache" / "code-quality" / "registry"


def _cache_path(ecosystem: str) -> Path:
    base = _cache_dir() / f"{ecosystem}.json"
    base.parent.mkdir(parents=True, exist_ok=True)
    return base


def _load_cache(ecosystem: str) -> dict[str, Any]:
    """Load the ecosystem cache. Returns empty dict on missing or corrupted (EC-3).

    Memoized per run: `_cache_set` re-read and rewrote the whole file on every
    result, which is quadratic I/O in the number of packages queried.
    """
    if ecosystem in _memory_cache:
        return _memory_cache[ecosystem]
    loaded = _read_cache_file(ecosystem)
    _memory_cache[ecosystem] = loaded
    return loaded


def flush_caches() -> None:
    """Writes the ecosystems that changed to disk. One write per ecosystem.

    Registered with `atexit` so a script that only calls `package_exists_*` does
    not need to know this step exists. EC-9 (atomic write) preserved.
    """
    for ecosystem in sorted(_dirty_ecosystems):
        _save_cache(ecosystem, _memory_cache.get(ecosystem, {}))
    _dirty_ecosystems.clear()


def _read_cache_file(ecosystem: str) -> dict[str, Any]:
    path = _cache_path(ecosystem)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        # EC-3 — corrupted cache; discard silently and re-fetch on next lookup.
        try:
            path.unlink()
        except OSError:
            pass
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save_cache(ecosystem: str, cache: dict[str, Any]) -> None:
    """Atomic cache write (EC-9)."""
    write_atomic(_cache_path(ecosystem), json.dumps(cache, ensure_ascii=False))


def _now() -> float:
    return time.time()


def _cache_get(ecosystem: str, key: str) -> bool | None:
    cache = _load_cache(ecosystem)
    entry = cache.get(key)
    if not entry:
        return None
    try:
        ts = float(entry.get("ts", 0))
        exists = entry.get("exists")
    except (TypeError, ValueError):
        return None
    if _now() - ts > _CACHE_TTL_SECONDS:
        return None
    if isinstance(exists, bool):
        return exists
    return None


def _cache_set(ecosystem: str, key: str, exists: bool | None) -> None:
    """Persist a lookup result. `None` results are NOT cached (ambiguous)."""
    if exists is None:
        return
    cache = _load_cache(ecosystem)
    cache[key] = {"exists": exists, "ts": _now()}
    _dirty_ecosystems.add(ecosystem)


# ---------------------------------------------------------------------------
# Per-ecosystem lookups
# ---------------------------------------------------------------------------


def _lookup(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    false_statuses: tuple[int, ...] = (404,),
    require_json: bool = True,
) -> bool | None:
    """Query with a breaker. None = ambiguous — the same verdict as always.

    `require_json=False` exists for the Go proxy, whose `@v/list` answers 200 with
    a plain-text list: demanding JSON there would turn every successful query into
    ambiguity, and three of those in a row would switch the detector off.

    One behaviour difference worth declaring: an unexpected status (500, say) is
    now ambiguous instead of "does not exist". Before, on the crates.io path, a
    500 sent the candidate on to the next one and ended the search at False — a
    HARD finding derived from a registry outage, which is exactly what EC-2 exists
    to prevent.
    """
    global _consecutive_failures, _network_unavailable
    if not network_is_available():
        return None
    data, status = _http_get_json(url, headers=headers)
    if status == 200 and (not require_json or isinstance(data, dict)):
        _consecutive_failures = 0
        return True
    if status in false_statuses:
        _consecutive_failures = 0
        return False
    _consecutive_failures += 1
    if _consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
        _network_unavailable = True
    return None


def _http_get_json(url: str, *, headers: dict[str, str] | None = None) -> tuple[Any | None, int | None]:
    """Return (json_data, status_code). On non-200 OR HTML response OR network
    failure, return (None, status_code|None) — ambiguous, NEVER False (EC-2).
    """
    try:
        import requests
    except ImportError:
        return (None, None)
    h = {"User-Agent": _USER_AGENT}
    if headers:
        h.update(headers)
    global _network_seconds_spent
    started = _now()
    try:
        resp = requests.get(url, headers=h, timeout=_HTTP_TIMEOUT_SECONDS)
    except Exception:  # noqa: BLE001 — any network failure -> ambiguous
        _network_seconds_spent += _now() - started
        return (None, None)
    _network_seconds_spent += _now() - started
    if resp.status_code != 200:
        return (None, resp.status_code)
    content_type = resp.headers.get("Content-Type", "")
    if "html" in content_type.lower():
        # EC-2 — HTML response is ambiguous (likely outage page); do NOT classify as missing.
        return (None, resp.status_code)
    try:
        return (resp.json(), 200)
    except ValueError:
        return (None, resp.status_code)


def package_exists_on_pypi(name: str) -> bool | None:
    """True/False if PyPI returns 200/404. None if ambiguous (timeout, HTML, etc.)."""
    cached = _cache_get("python", name)
    if cached is not None:
        return cached
    result = _lookup(f"https://pypi.org/pypi/{quote(name, safe='-_.')}/json")
    if result is None:
        return None
    _cache_set("python", name, result)
    return result


def package_exists_on_npm(name: str) -> bool | None:
    """npm registry. Scoped packages (`@scope/name`) are URL-encoded."""
    cached = _cache_get("typescript", name)
    if cached is not None:
        return cached
    encoded = quote(name, safe="@/")
    encoded = encoded.replace("/", "%2F") if name.startswith("@") else encoded
    result = _lookup(f"https://registry.npmjs.org/{encoded}")
    if result is None:
        return None
    _cache_set("typescript", name, result)
    return result


def crate_exists_on_crates_io(name: str) -> bool | None:
    """crates.io. Handles `_` ↔ `-` ambiguity by trying both forms."""
    cached = _cache_get("rust", name)
    if cached is not None:
        return cached
    # crates.io stores names case-insensitively but underscores vs dashes can differ
    for candidate in {name, name.replace("_", "-"), name.replace("-", "_")}:
        result = _lookup(f"https://crates.io/api/v1/crates/{quote(candidate, safe='-_')}")
        if result is True:
            _cache_set("rust", name, True)
            return True
        if result is None:
            # Network ambiguity on first try → bail out as None (don't keep guessing)
            return None
    _cache_set("rust", name, False)
    return False


def _go_proxy_encode(module: str) -> str:
    """Go proxy encodes uppercase via `!` prefix (e.g., gopkg.in/Yaml.v2 -> gopkg.in/!yaml.v2)."""
    out = []
    for ch in module:
        if ch.isupper():
            out.append("!" + ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def module_exists_on_go_proxy(import_path: str) -> bool | None:
    """Go proxy. Returns None for stdlib paths (no slash) since stdlib isn't in proxy."""
    cached = _cache_get("go", import_path)
    if cached is not None:
        return cached
    # Go's own rule for telling the standard library from a module: if the FIRST path
    # element contains no dot, it is stdlib. The dot is what makes the element a domain,
    # and every module path starts with one.
    #
    # The old test was `"/" not in import_path`, which is true of `fmt` and `os` and
    # false of most of the library: `net/http`, `encoding/json`, `log/slog`,
    # `path/filepath`, `net/http/httptest`. Those all went to the proxy, which answered
    # 404 — it does not index stdlib — and 404 is `false_statuses`, so the detector
    # called the Go standard library fabricated.
    #
    # Measured on a real repository on 2026-08-31, over 400 files: 88 findings for
    # `net/http`, 72 for `encoding/json`, 69 for `log/slog`. Whole-repository run: 1739
    # HARD findings, the gate reporting FAIL_HARD, and the language kept off for a year
    # partly on the strength of it.
    first = import_path.split("/", 1)[0]
    if "." not in first:
        _cache_set("go", import_path, True)
        return True
    # The proxy indexes MODULES; an import names a PACKAGE, which usually sits inside
    # one. `github.com/jackc/pgx/v5/pgxpool` is a package of the module
    # `github.com/jackc/pgx/v5`, and asking for the package path returns 404 — which
    # `false_statuses` reads as "does not exist".
    #
    # So a 404 on the full path is not an answer yet. Trim one element at a time down
    # to the domain and ask again; only when no prefix resolves is the import
    # unaccounted for. A found prefix caches the FULL path, because it is the full path
    # the next call will ask about.
    candidates = [import_path]
    parts = import_path.split("/")
    while len(parts) > 2:
        parts = parts[:-1]
        candidates.append("/".join(parts))

    result: bool | None = None
    for candidate in candidates:
        answer = _lookup(
            f"https://proxy.golang.org/{_go_proxy_encode(candidate)}/@v/list",
            false_statuses=(404, 410),
            require_json=False,
        )
        if answer is True:
            _cache_set("go", import_path, True)
            return True
        if answer is None:
            # Ambiguity anywhere in the chain makes the whole question ambiguous: a
            # later 404 would otherwise be reported as absence on incomplete evidence.
            return None
        result = False
    if result is None:
        return None
    _cache_set("go", import_path, False)
    return False


# This module's public surface is the four registry queries. The state helpers
# (`network_is_available`, `reset_network_state`) are internal: one is used right
# here, the other exists so tests can reset global state between cases. They were
# declared as public API and D3 flagged them as exports with no consumer —
# correctly. `__all__` goes back to describing what other modules use; the tests
# keep importing by name, which `__all__` does not restrict.
__all__ = [
    "flush_caches",
    "package_exists_on_pypi",
    "package_exists_on_npm",
    "crate_exists_on_crates_io",
    "module_exists_on_go_proxy",
]


atexit.register(flush_caches)

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

from scripts._shared import write_atomic

_CACHE_DIR_ENV = "CODE_QUALITY_CACHE_DIR"
_CACHE_TTL_SECONDS = 24 * 3600  # 24h per thresholds default
_HTTP_TIMEOUT_SECONDS = 5
_USER_AGENT = "code-quality-skill/0.1 (audit only)"

# --- ORÇAMENTO DE REDE PARA A EXECUÇÃO INTEIRA ------------------------------
# Cada consulta tem timeout de 5 s, elas são seriais, e um resultado ambíguo
# não é cacheado — corretamente: falha de rede não é prova de que o pacote não
# existe. O que faltava era um limite para o CONJUNTO. Numa máquina offline ou
# atrás de proxy, 100 imports desconhecidos custavam 500 s de espera que nunca
# viravam resposta, em toda execução, indefinidamente.
#
# Depois de _MAX_CONSECUTIVE_FAILURES falhas seguidas, D2 declara a rede
# indisponível e devolve None de imediato — o MESMO veredito ambíguo de antes,
# sem a espera. Um único acerto zera o contador, para que um blip não desligue
# o detector pelo resto da execução.
_MAX_CONSECUTIVE_FAILURES = 3
_NETWORK_BUDGET_SECONDS = 30.0

_consecutive_failures = 0
_network_seconds_spent = 0.0
_network_unavailable = False

# Cache em memória por ecossistema, escrito no disco UMA vez (ver flush_caches).
_memory_cache: dict[str, dict[str, Any]] = {}
_dirty_ecosystems: set[str] = set()


def reset_network_state() -> None:
    """Zera breaker, orçamento e cache em memória. Para testes e re-execução."""
    global _consecutive_failures, _network_seconds_spent, _network_unavailable
    _consecutive_failures = 0
    _network_seconds_spent = 0.0
    _network_unavailable = False
    _memory_cache.clear()
    _dirty_ecosystems.clear()


def network_is_available() -> bool:
    """False quando o breaker abriu ou o orçamento da execução acabou."""
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

    Memoizado por execução: `_cache_set` relia e reescrevia o arquivo inteiro a
    cada resultado, o que é I/O quadrático no número de pacotes consultados.
    """
    if ecosystem in _memory_cache:
        return _memory_cache[ecosystem]
    loaded = _read_cache_file(ecosystem)
    _memory_cache[ecosystem] = loaded
    return loaded


def flush_caches() -> None:
    """Escreve no disco os ecossistemas que mudaram. Uma escrita por ecossistema.

    Registrado em `atexit` para que um script que só chama `package_exists_*`
    não precise saber que este passo existe. EC-9 (escrita atômica) preservado.
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
    """Consulta com breaker. None = ambíguo — o mesmo veredito de sempre.

    `require_json=False` existe para o proxy Go, cujo `@v/list` responde 200 com
    uma lista em texto puro: exigir JSON ali transformaria toda consulta bem
    sucedida em ambiguidade, e três delas seguidas desligariam o detector.

    Uma diferença de comportamento que vale declarar: um status inesperado (500,
    por exemplo) agora é ambíguo em vez de "não existe". Antes, no caminho do
    crates.io, um 500 fazia o candidato seguir para o próximo e a busca terminar
    em False — um HARD finding a partir de uma indisponibilidade do registry, que
    é exatamente o que EC-2 existe para impedir.
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
    if "/" not in import_path:
        # stdlib package — proxy doesn't index it. Treat as True (exists) to avoid FP.
        _cache_set("go", import_path, True)
        return True
    encoded = _go_proxy_encode(import_path)
    result = _lookup(
        f"https://proxy.golang.org/{encoded}/@v/list",
        false_statuses=(404, 410),
        require_json=False,
    )
    if result is None:
        return None
    _cache_set("go", import_path, result)
    return result


# A superfície pública deste módulo são as quatro consultas de registro. As
# helpers de estado (`network_is_available`, `reset_network_state`) são internas:
# uma é usada aqui mesmo, a outra existe para o teste reiniciar estado global entre
# casos. Estavam declaradas como API pública e D3 as apontou como exports sem
# consumidor — corretamente. `__all__` volta a descrever o que outros módulos usam;
# os testes seguem importando por nome, que `__all__` não restringe.
__all__ = [
    "flush_caches",
    "package_exists_on_pypi",
    "package_exists_on_npm",
    "crate_exists_on_crates_io",
    "module_exists_on_go_proxy",
]


atexit.register(flush_caches)

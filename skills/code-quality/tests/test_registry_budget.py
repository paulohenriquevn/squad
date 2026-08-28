"""D2 gives up on the network instead of paying N x timeout per run.

The registry queries are serial, 5s timeout each, and an ambiguous result
(timeout, HTML, network down) is NOT cached — by a correct decision: a network
failure is not proof that the package does not exist. The side effect is that an
offline machine or one behind a proxy paid 5s per unknown package, on every run,
forever: 100 imports = 500s of waiting that never becomes
resposta.

What gets fixed is not each query's timeout — it is the absence of a bound for
the set of them. After N consecutive failures, D2 declares the network
unavailable and returns None immediately, which is the same ambiguous verdict as
before, without the wait.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import _registry


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(_registry._CACHE_DIR_ENV, str(tmp_path / "cache"))
    _registry.reset_network_state()
    yield
    _registry.reset_network_state()


def test_gives_up_after_consecutive_failures(monkeypatch):
    attempts = []

    def always_fails(url, *, headers=None):
        attempts.append(url)
        return (None, None)

    monkeypatch.setattr(_registry, "_http_get_json", always_fails)

    results = [_registry.package_exists_on_pypi(f"pkg{i}") for i in range(30)]

    assert all(r is None for r in results), "falha de rede virou veredito"
    assert len(attempts) <= _registry._MAX_CONSECUTIVE_FAILURES, (
        f"the network was queried {len(attempts)} times after consecutive failures"
    )


def test_a_success_resets_the_breaker(monkeypatch):
    calls = {"n": 0}

    def flaky(url, *, headers=None):
        calls["n"] += 1
        # Fails once, succeeds next: a blip must not switch D2 off.
        if calls["n"] % 2 == 1:
            return (None, None)
        return ({"info": {}}, 200)

    monkeypatch.setattr(_registry, "_http_get_json", flaky)

    results = [_registry.package_exists_on_pypi(f"pkg{i}") for i in range(10)]

    assert results.count(True) == 5, "o breaker desligou D2 por falhas intercaladas"


def test_the_cache_file_is_written_once_not_per_lookup(monkeypatch):
    """One write per run, not one per package.

    `_cache_set` re-read and rewrote the whole file on every result — I/O quadratic
    in the number of packages. The final content is the same; the number of writes
    is not.
    """
    writes = []
    real = _registry._save_cache

    def spy(ecosystem, cache):
        writes.append(ecosystem)
        return real(ecosystem, cache)

    monkeypatch.setattr(_registry, "_save_cache", spy)
    monkeypatch.setattr(_registry, "_http_get_json", lambda url, headers=None: ({"info": {}}, 200))

    for i in range(20):
        _registry.package_exists_on_pypi(f"pkg{i}")

    assert len(writes) == 0, "escreveu no disco antes do flush"

    _registry.flush_caches()
    assert len(writes) == 1, f"esperava 1 escrita no flush, houve {len(writes)}"

    # And the result persists: a second run reads from disk, with no network.
    _registry.reset_network_state()
    monkeypatch.setattr(
        _registry,
        "_http_get_json",
        lambda url, headers=None: pytest.fail("consultou a rede com cache quente"),
    )
    assert _registry.package_exists_on_pypi("pkg7") is True


def test_go_proxy_accepts_a_plain_text_200(monkeypatch):
    """`@v/list` answers 200 with plain text, not JSON.

    Exigir JSON ali transformaria toda consulta bem sucedida em ambiguidade — e
    three in a row would switch D2 off for Go for the rest of the run.
    """
    monkeypatch.setattr(_registry, "_http_get_json", lambda url, headers=None: (None, 200))
    assert _registry.module_exists_on_go_proxy("github.com/x/y") is True


def test_go_proxy_410_means_absent(monkeypatch):
    monkeypatch.setattr(_registry, "_http_get_json", lambda url, headers=None: (None, 410))
    assert _registry.module_exists_on_go_proxy("github.com/x/gone") is False


def test_registry_outage_is_ambiguous_not_absent(monkeypatch):
    """EC-2: a 500 from the registry must not become 'the package does not exist'."""
    monkeypatch.setattr(_registry, "_http_get_json", lambda url, headers=None: (None, 500))
    assert _registry.crate_exists_on_crates_io("serde") is None
    assert _registry.package_exists_on_pypi("requests") is None

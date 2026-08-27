"""D2 desiste da rede em vez de pagar N x timeout por execução.

As consultas ao registry são seriais, com 5 s de timeout cada, e um resultado
ambíguo (timeout, HTML, rede fora) NÃO é cacheado — por decisão correta: uma
falha de rede não é prova de que o pacote não existe. O efeito colateral é que
uma máquina offline ou atrás de proxy pagava 5 s por pacote desconhecido, em
toda execução, para sempre: 100 imports = 500 s de espera que nunca vira
resposta.

O que se corrige não é o timeout de cada consulta — é a ausência de um limite
para o conjunto delas. Depois de N falhas seguidas, D2 declara a rede
indisponível e devolve None imediatamente, que é o mesmo veredito ambíguo de
antes, sem a espera.
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
        f"a rede foi consultada {len(attempts)} vezes depois de falhar seguidamente"
    )


def test_a_success_resets_the_breaker(monkeypatch):
    calls = {"n": 0}

    def flaky(url, *, headers=None):
        calls["n"] += 1
        # Falha uma vez, acerta na seguinte: um blip não deve desligar D2.
        if calls["n"] % 2 == 1:
            return (None, None)
        return ({"info": {}}, 200)

    monkeypatch.setattr(_registry, "_http_get_json", flaky)

    results = [_registry.package_exists_on_pypi(f"pkg{i}") for i in range(10)]

    assert results.count(True) == 5, "o breaker desligou D2 por falhas intercaladas"


def test_the_cache_file_is_written_once_not_per_lookup(monkeypatch):
    """Uma escrita por execução, não uma por pacote.

    `_cache_set` relia e reescrevia o arquivo inteiro a cada resultado — I/O
    quadrático no número de pacotes. O conteúdo final é o mesmo; o número de
    escritas, não.
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

    # E o resultado persiste: uma segunda execução lê do disco, sem rede.
    _registry.reset_network_state()
    monkeypatch.setattr(
        _registry,
        "_http_get_json",
        lambda url, headers=None: pytest.fail("consultou a rede com cache quente"),
    )
    assert _registry.package_exists_on_pypi("pkg7") is True


def test_go_proxy_accepts_a_plain_text_200(monkeypatch):
    """`@v/list` responde 200 com texto puro, não JSON.

    Exigir JSON ali transformaria toda consulta bem sucedida em ambiguidade — e
    três seguidas desligariam D2 para Go pelo resto da execução.
    """
    monkeypatch.setattr(_registry, "_http_get_json", lambda url, headers=None: (None, 200))
    assert _registry.module_exists_on_go_proxy("github.com/x/y") is True


def test_go_proxy_410_means_absent(monkeypatch):
    monkeypatch.setattr(_registry, "_http_get_json", lambda url, headers=None: (None, 410))
    assert _registry.module_exists_on_go_proxy("github.com/x/gone") is False


def test_registry_outage_is_ambiguous_not_absent(monkeypatch):
    """EC-2: um 500 do registry não pode virar 'o pacote não existe'."""
    monkeypatch.setattr(_registry, "_http_get_json", lambda url, headers=None: (None, 500))
    assert _registry.crate_exists_on_crates_io("serde") is None
    assert _registry.package_exists_on_pypi("requests") is None

"""O consumidor não herda o mapa de repositórios de outro ecossistema.

O DEFEITO QUE ISTO FIXA
-----------------------
`rules/cycle-backlog.md` carrega a tabela de roteamento por domínio, e a versão
versionada aqui é a do ecossistema `theo`: oito domínios apontando para
`theo-cloud`, `theo-rag`, `theo-contracts` e mais doze repositórios.

O próprio arquivo já descrevia a consequência, com medição:

    "A consumer that keeps this table inherits a map of repos it does not have,
     and gate G1 then refuses every item it files. Measured on `theokit-sdk`
     (2026-08-18): 88 items with measured file:line evidence, all
     BLOCKER/unroutable_repo."

Saber e continuar entregando é a parte que este teste encerra. `install.sh` já
preservava a tabela DERIVADA de um consumidor no modo `--merge`; o que faltava
era o caso da instalação limpa, onde não há tabela anterior a preservar e a do
ecossistema de origem seguia por padrão.

POR QUE O TESTE MEDE A INSTALAÇÃO, NÃO O REPOSITÓRIO
-----------------------------------------------------
A tabela deste repositório está correta PARA ESTE repositório — ele realmente
mantém aqueles repos, e `route_domain.py` depende dela para rodar aqui. O
defeito nunca foi tê-la; foi entregá-la. Então a asserção é sobre o que sai do
instalador, e o kit segue livre para descrever o próprio ecossistema.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Nomes que só fazem sentido no ecossistema de origem. Deliberadamente
#: específicos: `control-plane` ou `engine-go` sozinhos são termos genéricos que
#: um consumidor pode legitimamente usar como nome de domínio próprio.
ORIGIN_MARKERS = (
    "theo-cloud",
    "theo-rag",
    "theo-memory",
    "theo-lens",
    "theo-trust",
    "theo-skills",
    "theo-promptly",
    "theo-contracts",
    "theo-infra-modules",
    "theo-infra-live",
    "theo-traefik-mcp",
    "theo-cli",
    "theo-storage",
    "usetheo.dev",
    "@usetheo/",
)


@pytest.fixture(scope="module")
def installed_rules(versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("consumer")
    proc = subprocess.run(  # noqa: PLW1510
        ["bash", str(versioned_kit / "scripts" / "install.sh"), str(target)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return target / ".claude" / "rules"


def _leaks(text: str) -> list[str]:
    return sorted({m for m in ORIGIN_MARKERS if m in text})


def test_routing_table_ships_empty(installed_rules: Path):
    """A instalação limpa não pode nomear repositórios de outro ecossistema."""
    backlog = installed_rules / "cycle-backlog.md"
    assert backlog.is_file()
    found = _leaks(backlog.read_text(encoding="utf-8"))
    assert not found, (
        f"cycle-backlog.md entregue nomeia repositórios do ecossistema de origem: {found}. "
        "Todo item filado pelo consumidor será recusado por G1 como unroutable_repo."
    )


def test_routing_table_still_tells_the_consumer_what_to_do(installed_rules: Path):
    """Esvaziar sem instruir apenas troca uma falha por outra.

    A seção precisa continuar existindo e apontar o comando que a deriva — do
    contrário o consumidor encontra um vazio sem saber que é ele quem o preenche.
    """
    body = (installed_rules / "cycle-backlog.md").read_text(encoding="utf-8")
    section = re.search(r"^##\s+Domain routing\b.*?(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    assert section, "a seção `## Domain routing` sumiu do arquivo entregue"
    assert "detect_domains.py" in section.group(0), (
        "a seção não nomeia o script que deriva a tabela para o projeto"
    )


@pytest.mark.parametrize("name", ["live-target.txt", "acceptance-target.txt"])
def test_target_declarations_ship_undeclared(installed_rules: Path, name: str):
    """Um alvo herdado faz o kit sondar o produto de outra pessoa.

    `/discover-execute` em live-test e `/acceptance` exercitam o que estes
    arquivos declaram. Herdar a declaração de origem não é só ruído: produz
    "evidência" sobre um sistema que não é o do consumidor.
    """
    found = _leaks((installed_rules / name).read_text(encoding="utf-8"))
    assert not found, f"{name} entregue cita o ecossistema de origem: {found}"


def test_every_shipped_config_file_is_clean(installed_rules: Path):
    """Varredura sobre TODA a configuração entregue, não só os arquivos conhecidos.

    Um `rules/*.txt` novo criado depois deste teste entra na varredura sozinho —
    é a diferença entre um teste que fixa a lista de hoje e um que fixa a regra.
    """
    dirty = {
        p.name: _leaks(p.read_text(encoding="utf-8", errors="replace"))
        for p in sorted(installed_rules.glob("*.txt"))
    }
    dirty = {k: v for k, v in dirty.items() if v}
    assert not dirty, f"configuração entregue citando o ecossistema de origem: {dirty}"

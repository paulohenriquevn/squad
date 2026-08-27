"""Tests for route_domain.py — deterministic repo -> domain -> specialist routing.

POR QUE ESTES TESTES NÃO NOMEIAM REPOSITÓRIOS
---------------------------------------------
Até 2026-08-26 metade deste arquivo media a tabela do ecossistema em que o kit
foi escrito: `len(table) == 8`, `("theo-lens", "data-plane-ts")`, cinco repos sem
checkout. Os oito especialistas que essa tabela nomeava saíram do kit (a tabela é
DERIVADA do projeto, `rules/cycle-backlog.md § Domain routing`), e com eles some a
possibilidade de asseverar sobre um mapa concreto — este repositório pode ter
tabela, não ter, ou ter uma completamente diferente da de ontem.

O que sobrevive é mais forte: as invariantes ESTRUTURAIS do roteador, exercidas
contra tabelas sintéticas, mais as duas direções da consistência entre a tabela
deste repositório e os especialistas em disco — quaisquer que sejam.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from route_domain import parse_routing_table, route  # noqa: E402

RULE = PROJECT_ROOT / "rules" / "cycle-backlog.md"
AGENTS_DIR = PROJECT_ROOT / "agents"


def _table_with(rows: str, tmp_path: Path) -> Path:
    """A minimal rule file carrying only a `## Domain routing` section."""
    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\n"
        "| Domain | Packages | Specialist |\n|---|---|---|\n" + rows,
        encoding="utf-8",
    )
    return rule


# ---------------------------------------------------------------------------
# A tabela DESTE repositório — qualquer que seja o seu estado
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def table() -> dict | None:
    """A tabela derivada deste projeto, ou None enquanto ninguém a derivou.

    Vazia é um estado LEGÍTIMO — é como o kit nasce e como ele é entregue
    (`rules/templates/domain-routing.md`). Um teste que exigisse linhas aqui
    obrigaria o repositório do kit a inventar um mapa para ficar verde.
    """
    try:
        return parse_routing_table(RULE)
    except ValueError:
        return None


def test_the_section_exists_and_says_how_to_fill_itself() -> None:
    """Sem tabela E sem instrução, o vazio vira um mistério em vez de uma tarefa.

    `parse_routing_table` distingue os dois casos por exceção — 'no section' é um
    arquivo corrompido, 'zero rows' é a configuração ainda por derivar. A seção
    tem de existir sempre, e nomear o script que a preenche.
    """
    body = RULE.read_text(encoding="utf-8-sig")
    assert "## Domain routing" in body, "a seção sumiu — route_domain.py sai 2 em tudo"
    assert "detect_domains.py" in body, (
        "a seção não nomeia o script que deriva a tabela — quem a encontra vazia "
        "não descobre que é ele quem a preenche"
    )


def test_the_repository_table_is_internally_consistent(table: dict | None) -> None:
    """As três invariantes da tabela real, num teste que NUNCA pula.

    Cada uma tem um par sintético mais abaixo, exercendo o parser e a ferramenta.
    Aqui elas incidem sobre a tabela DESTE repositório — que hoje está vazia, e por
    isso o corpo é vacuamente satisfeito. Escrito assim de propósito: um `skip`
    enquanto ninguém derivou a tabela é um teste que some do relatório e volta a
    existir sem que ninguém perceba. Este ganha dentes sozinho no dia em que
    `detect_domains.py --write` rodar aqui.

      1. Todo domínio declara um especialista, e o arquivo existe — apontar para um
         arquivo que ninguém escreveu roteia para o vácuo, e o item PARECE roteado.
      2. Um repo pertence a exatamente um domínio — gate G3 depende disso, e duas
         linhas fazem o roteamento seguir a ordem de iteração do dict.
      3. Todo domínio tem ao menos um repo — zero repos é inalcançável, e em silêncio.
    """
    seen: dict[str, str] = {}
    for domain, entry in (table or {}).items():
        assert entry["agent"], f"domínio sem especialista declarado: {domain}"
        assert (PROJECT_ROOT / entry["agent"]).is_file(), (
            f"{domain} -> {entry['agent']} não existe em disco"
        )
        assert entry["repos"], f"domínio que item nenhum alcança: {domain}"
        for repo in entry["repos"]:
            assert repo not in seen or seen[repo] == domain, (
                f"`{repo}` está em {seen[repo]} e em {domain}"
            )
            seen[repo] = domain


def test_every_specialist_on_disk_is_reachable_from_the_table(table: dict | None) -> None:
    """A outra direção: um especialista que ninguém roteia é peso morto.

    Sem isto, um arquivo de domínio pode ser escrito, revisado e mergeado sem que
    item nenhum consiga alcançá-lo — o trabalho parece feito e não muda nada. Vale
    inclusive com a tabela vazia, que é quando o descasamento é mais fácil de criar.
    """
    declared = {entry["agent"] for entry in (table or {}).values()}
    on_disk = {
        f"agents/{p.name}" for p in AGENTS_DIR.glob("*.md") if p.name != "README.md"
    }
    orphans = sorted(on_disk - declared)
    assert orphans == [], (
        f"especialistas que a tabela não alcança: {orphans}. Declare-os em "
        f"`rules/cycle-backlog.md § Domain routing` ou remova-os."
    )


# ---------------------------------------------------------------------------
# O roteador, contra tabelas sintéticas
# ---------------------------------------------------------------------------

def test_a_known_repo_routes_to_its_domain(tmp_path: Path) -> None:
    table = parse_routing_table(
        _table_with(
            "| `alpha` | `pkg-one`, `pkg-two` | `agents/alpha.md` |\n"
            "| `beta` | `pkg-three` | `agents/beta.md` |\n",
            tmp_path,
        )
    )
    assert route("pkg-two", table) == ("alpha", "agents/alpha.md")
    assert route("pkg-three", table) == ("beta", "agents/beta.md")


def test_an_unknown_repo_does_not_route(tmp_path: Path) -> None:
    """Gate G1 recusa o item em vez de mandá-lo para quem não abre o código."""
    table = parse_routing_table(
        _table_with("| `alpha` | `pkg-one` | `agents/alpha.md` |\n", tmp_path)
    )
    assert route("some-other-project", table) is None


def test_a_path_scoped_repo_routes(tmp_path: Path) -> None:
    """Um repo dividido entre domínios é endereçado por caminho, e o caminho tem de rotear.

    Pego na prática: o identificador continha uma barra, o padrão de repo não a
    aceitava, e o domínio parseava com lista de repos VAZIA. Todos os outros testes
    passavam — uma lista vazia não viola unicidade, declara um agente que existe e
    parece inteiramente saudável. O domínio simplesmente nunca podia receber um item.
    """
    table = parse_routing_table(
        _table_with(
            "| `service` | `alpha-cloud` | `agents/service.md` |\n"
            "| `ui` | `alpha-cloud/dashboard` | `agents/ui.md` |\n",
            tmp_path,
        )
    )
    assert table["ui"]["repos"] == ["alpha-cloud/dashboard"], "a barra truncou o repo"
    assert route("alpha-cloud/dashboard", table) == ("ui", "agents/ui.md")
    assert route("alpha-cloud", table) == ("service", "agents/service.md")


def test_missing_section_raises(tmp_path: Path) -> None:
    rule = tmp_path / "no-section.md"
    rule.write_text("# Cycle: BACKLOG\n\n## Purpose\n\nText.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Domain routing"):
        parse_routing_table(rule)


def test_empty_table_raises(tmp_path: Path) -> None:
    """Zero linhas tem de ser erro, nunca um dict vazio.

    Um dict vazio deixaria todo repo silenciosamente inalcançável enquanto o script
    sai 0 — a mesma forma do arquivo de thresholds que parseou para zero bandas e
    mandou todo score para INVALID.
    """
    rule = tmp_path / "empty.md"
    rule.write_text("# X\n\n## Domain routing\n\nNo table here.\n\n## Next\n", encoding="utf-8")
    with pytest.raises(ValueError, match="zero rows"):
        parse_routing_table(rule)


def test_the_shipped_empty_section_parses_to_zero_rows() -> None:
    """O template entregue ao consumidor tem de cair no caminho 'zero rows'.

    Ele carrega uma linha de tabela com o texto `_(empty — run …)_` justamente para
    a seção continuar parecendo uma tabela. Se essa linha PARSEASSE, o consumidor
    nasceria com um domínio fantasma que aceita item nenhum e reporta sucesso.
    """
    template = PROJECT_ROOT / "rules" / "templates" / "domain-routing.md"
    assert template.is_file()
    with pytest.raises(ValueError, match="zero rows"):
        parse_routing_table(template)


def test_a_domain_naming_a_missing_specialist_exits_3(tmp_path, capsys) -> None:
    """A invariante mudou deste arquivo para a ferramenta, e isto fixa a mudança.

    Ela vivia só aqui, e `install.sh` não copia `tests/` — então em todo repositório
    consumidor a guarda estava ausente. Medido ao instalar no TheoCode: uma segunda
    tabela de três colunas dentro de `## Domain routing` parseia como roteamento,
    inventando domínios cujos arquivos de especialista nunca foram escritos, e
    `route_domain.py` respondia `routed: true` / `agent: null` com exit 0.
    """
    from route_domain import main as route_main

    (tmp_path / "rules").mkdir()
    (tmp_path / "agents").mkdir()
    (tmp_path / "rules" / "cycle-backlog.md").write_text(
        "## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `ghost` | `some-repo` | `agents/ghost.md` |\n\n"
        "## Verdicts\n",
        encoding="utf-8",
    )
    code = route_main(["some-repo", "--rule", str(tmp_path / "rules" / "cycle-backlog.md")])
    assert code == 3
    assert "BROKEN ROUTE" in capsys.readouterr().out


def test_a_domain_whose_specialist_exists_still_routes(tmp_path) -> None:
    """A recusa não pode engolir o caso normal."""
    from route_domain import main as route_main

    (tmp_path / "rules").mkdir()
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "real.md").write_text("# real\n", encoding="utf-8")
    (tmp_path / "rules" / "cycle-backlog.md").write_text(
        "## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `real` | `some-repo` | `agents/real.md` |\n\n"
        "## Verdicts\n",
        encoding="utf-8",
    )
    assert route_main(["some-repo", "--rule", str(tmp_path / "rules" / "cycle-backlog.md")]) == 0


def test_item_repo_field_accepts_a_monorepo_path(tmp_path: Path) -> None:
    """`repo: packages/sdk` num arquivo de item tem de chegar inteiro ao roteador.

    A tabela sempre aceitou caminho (documentado como "um repo, dois domínios —
    resolvido por caminho"), mas o extrator do ITEM parava na barra e devolvia
    `packages`. O roteamento então falhava por um repo que ninguém escreveu.
    Descoberto ao derivar a tabela de um adotante, onde 68 dos 88 itens citam
    `packages/sdk`.
    """
    item = tmp_path / "item.md"
    item.write_text("## B-001 — algo\n\nrepo: packages/sdk\nstatus: raw\n", encoding="utf-8")
    from route_domain import ITEM_REPO_RE

    match = ITEM_REPO_RE.search(item.read_text(encoding="utf-8"))
    assert match is not None
    assert match.group(1) == "packages/sdk"


def test_a_repo_in_two_domains_is_refused_by_the_parser(tmp_path: Path) -> None:
    """A invariante um-repo-um-domínio pertence à FERRAMENTA, não a esta suíte.

    `test_no_repo_belongs_to_two_domains` acima a assevera para a tabela DESTE
    repositório, e é tudo que ele pode fazer. Todo consumidor carrega a sua, com a
    sua contagem de domínios, e `install.sh` não copia `tests/` — então num repo
    consumidor a invariante era asseverada por ninguém, exatamente como a guarda do
    exit 3 antes de mudar para a ferramenta.

    Medido numa instalação em 2026-08-24: 11 pacotes em 4 domínios, e nada em lugar
    nenhum checava que nenhum deles aparecia duas vezes. Um repo em duas linhas faz o
    roteamento depender da ordem de iteração do dict — o mesmo item roteando
    diferente entre execuções.
    """
    rule = _table_with(
        "| `alpha` | `pkg-one`, `pkg-two` | `agents/alpha.md` |\n"
        "| `beta` | `pkg-two` | `agents/beta.md` |\n",
        tmp_path,
    )

    with pytest.raises(ValueError, match=r"pkg-two.*(alpha|beta)"):
        parse_routing_table(rule)


def test_the_same_repo_twice_in_ONE_domain_is_not_a_duplicate(tmp_path: Path) -> None:
    """Duas menções numa linha roteiam igual, então nada é ambíguo.

    Sem isto, a guarda poderia ser escrita como contagem ingênua e rejeitaria uma
    tabela meramente repetitiva — transformando uma edição cosmética em instalação
    quebrada.
    """
    rule = _table_with(
        "| `alpha` | `pkg-one`, `pkg-one` | `agents/alpha.md` |\n",
        tmp_path,
    )

    assert parse_routing_table(rule)["alpha"]["repos"].count("pkg-one") == 2

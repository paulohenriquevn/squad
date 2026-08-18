"""A tabela de roteamento é dado do projeto, e vivia dentro do template.

`rules/cycle-backlog.md § Domain routing` embarca os 8 domínios do ecossistema
`theo` (`engine-go`, `control-plane`, `theo-db`, …). Toda instalação copia essa
tabela, e o `backlog-init` mandava classificar os repos do alvo *dentro* desses
8, proibindo "inventar um nono domínio". O resultado, medido no `theokit-sdk`:
88 itens com evidência `file:line` medida, todos `BLOCKER/unroutable_repo`,
porque `packages/sdk` e `theokit-sdk` não existem no mapa de outro ecossistema.

O gate estava certo em recusar — ele não sabia para quem mandar o trabalho. O
que estava errado era a tabela vir pronta de fora.
"""
from __future__ import annotations

from pathlib import Path

from detect_domains import detect_domains, render_table, rewrite_routing_section


def _repo(root: Path, name: str, *, git: bool = True) -> Path:
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    if git:
        (path / ".git").mkdir(exist_ok=True)
    return path


def test_single_repo_becomes_one_domain_named_after_it(tmp_path: Path) -> None:
    root = _repo(tmp_path, "theokit-sdk")
    domains = detect_domains(root)
    assert [d.name for d in domains] == ["theokit-sdk"]
    assert domains[0].repos == ["theokit-sdk"]
    assert domains[0].agent == "agents/theokit-sdk.md"


def test_npm_monorepo_lists_each_package_by_path(tmp_path: Path) -> None:
    """O caso do theokit-sdk: um repo, vários pacotes, itens citando `packages/x`.

    Um domínio só — existe um SDK, não seis times. Os pacotes entram como repos
    endereçados por caminho, forma que o kit já suporta (`theo-cloud/dashboard`).
    """
    root = _repo(tmp_path, "theokit-sdk")
    for pkg in ("sdk", "acp", "sdk-pty"):
        (root / "packages" / pkg).mkdir(parents=True)
        (root / "packages" / pkg / "package.json").write_text("{}", encoding="utf-8")
    (root / "node_modules" / "lodash").mkdir(parents=True)
    (root / "node_modules" / "lodash" / "package.json").write_text("{}", encoding="utf-8")

    domains = detect_domains(root)
    assert len(domains) == 1
    assert domains[0].repos == ["theokit-sdk", "packages/acp", "packages/sdk", "packages/sdk-pty"]


def test_go_workspace_modules_become_repos(tmp_path: Path) -> None:
    root = _repo(tmp_path, "theo")
    (root / "go.work").write_text("go 1.22\n\nuse (\n\t./api\n\t./operators\n\t../sibling\n)\n",
                                  encoding="utf-8")
    (root / "api").mkdir()
    (root / "operators").mkdir()
    domains = detect_domains(root)
    assert domains[0].repos == ["theo", "api", "operators"]  # o irmão fora do repo não entra


def test_umbrella_gives_one_domain_per_checked_out_repo(tmp_path: Path) -> None:
    """Workspace guarda-chuva: a unidade de propriedade é o repositório."""
    root = tmp_path / "umbrella"
    root.mkdir()
    _repo(root, "theo-lens")
    _repo(root, "theo-db")
    (root / "docs").mkdir()  # sem .git — não é repo, não vira domínio
    domains = detect_domains(root)
    assert [d.name for d in domains] == ["theo-db", "theo-lens"]
    assert all(d.repos == [d.name] for d in domains)


def test_rendered_table_is_parseable_by_route_domain(tmp_path: Path) -> None:
    """O contrato real: o que sai daqui tem que entrar no parser do route_domain."""
    import sys
    root = _repo(tmp_path, "theokit-sdk")
    (root / "packages" / "sdk").mkdir(parents=True)
    (root / "packages" / "sdk" / "package.json").write_text("{}", encoding="utf-8")

    rule = tmp_path / "cycle-backlog.md"
    rule.write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\n| Domain | Repos | Specialist |\n"
        "|---|---|---|\n| `velho` | `outro-eco` | `agents/velho.md` |\n\n"
        "## Verdicts\n\nintocado\n",
        encoding="utf-8",
    )
    rewrite_routing_section(rule, detect_domains(root))

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from route_domain import parse_routing_table, route

    table = parse_routing_table(rule)
    assert "velho" not in table, "a tabela do outro ecossistema tem de sair"
    assert route("packages/sdk", table) == ("theokit-sdk", "agents/theokit-sdk.md")
    assert route("theokit-sdk", table) == ("theokit-sdk", "agents/theokit-sdk.md")
    assert "## Verdicts" in rule.read_text(encoding="utf-8"), "o resto do arquivo sobrevive"


def test_render_names_the_specialist_files_that_must_exist(tmp_path: Path) -> None:
    """route_domain sai 3 quando a tabela nomeia um agente que não está em disco —
    trocar 88 blockers por esse erro não seria conserto."""
    root = _repo(tmp_path, "theokit-sdk")
    table = render_table(detect_domains(root))
    assert "agents/theokit-sdk.md" in table

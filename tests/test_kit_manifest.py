"""O consumidor precisa saber o que é dele e o que veio do kit.

Medido no `speculative` (2026-08-20): o projeto tem um auditor próprio,
`scripts/audit.py`, que percorre `.claude/skills/*/SKILL.md` e exige a spec Agent
Skills de cada uma. Antes da instalação ele dizia `APROVADO`; depois, `REPROVADO`
— porque passou a auditar as 37 skills do kit contra o padrão das 9 do projeto.

A instalação não apagou nada (46 untracked, zero modificados). O dano foi só
esse: um gate do consumidor que passou a medir código que não é do consumidor.
Sem um manifesto, a única forma de distinguir seria adivinhar por nome.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
MANIFEST = ".claude/.kit-manifest.txt"


def test_install_writes_a_manifest_of_what_the_kit_brought(tmp_path: Path) -> None:
    target = tmp_path / "consumidor"
    target.mkdir()
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    subprocess.run(
        ["bash", str(_REPO / "scripts" / "install.sh"), str(target)],
        capture_output=True, text=True, check=True,
    )

    manifest = target / MANIFEST
    assert manifest.is_file(), "sem manifesto, o consumidor não sabe o que é dele"
    listed = {line.strip() for line in manifest.read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.startswith("#")}
    assert "skills/implement" in listed
    assert "skills/review" in listed
    # Toda skill listada existe de fato no alvo — manifesto que mente é pior que nenhum.
    for entry in listed:
        assert (target / ".claude" / entry).exists(), entry


def test_a_project_skill_is_absent_from_the_manifest(tmp_path: Path) -> None:
    """O ponto do arquivo: o que o projeto escreveu NÃO aparece nele."""
    target = tmp_path / "consumidor"
    (target / ".claude" / "skills" / "minha-skill-de-dominio").mkdir(parents=True)
    (target / ".claude" / "skills" / "minha-skill-de-dominio" / "SKILL.md").write_text(
        "# minha\n", encoding="utf-8")
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    subprocess.run(
        ["bash", str(_REPO / "scripts" / "install.sh"), str(target), "--merge"],
        capture_output=True, text=True, check=True,
    )

    listed = (target / MANIFEST).read_text(encoding="utf-8")
    assert "minha-skill-de-dominio" not in listed
    assert (target / ".claude" / "skills" / "minha-skill-de-dominio" / "SKILL.md").is_file()


def test_merge_never_overwrites_an_existing_rules_txt(tmp_path: Path) -> None:
    """`rules/*.txt` é a CONFIGURAÇÃO do projeto: linguagens habilitadas, alvos
    vivos, allowlists, skills auxiliares declaradas. O `--merge` copiava o
    template por cima — medido no `speculative`, onde a declaração das 9 skills
    do projeto foi apagada pela reinstalação que a seguiu.

    Os `.md` continuam sendo atualizados: são o contrato normativo do kit.
    """
    target = tmp_path / "consumidor"
    rules = target / ".claude" / "rules"
    rules.mkdir(parents=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (rules / "code-quality-languages.txt").write_text(
        "python | pyproject.toml | ENABLED |\n", encoding="utf-8")

    subprocess.run(
        ["bash", str(_REPO / "scripts" / "install.sh"), str(target), "--merge"],
        capture_output=True, text=True, check=True,
    )

    kept = (rules / "code-quality-languages.txt").read_text(encoding="utf-8")
    assert "python | pyproject.toml | ENABLED" in kept, "config do projeto foi sobrescrita"
    assert (rules / "cycle-backlog.md").is_file(), "as regras .md seguem sendo instaladas"


# ---------------------------------------------------------------------------
# Grill kit-domain-agents-install, decisões 1 e 4: os oito especialistas do
# ecossistema `theo` deixam de ser copiados por padrão. Medido: 19 dos 41
# consumidores já viviam sem eles, 11 escrevem os seus, e a tabela de roteamento
# passou a ser derivada do projeto — o acoplamento que os justificava sumiu.
# ---------------------------------------------------------------------------

_DOMAIN_AGENTS = ("engine-go", "control-plane", "data-plane-ts", "theo-db",
                  "infra-terraform", "contracts-auth", "frontend-dashboard", "platform-cli")


def _install(target: Path, *flags: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    subprocess.run(
        ["bash", str(_REPO / "scripts" / "install.sh"), str(target), *flags],
        capture_output=True, text=True, check=True,
    )


def test_domain_agents_are_not_installed_by_default(tmp_path: Path) -> None:
    target = tmp_path / "consumidor"
    _install(target)
    agents = target / ".claude" / "agents"
    for name in _DOMAIN_AGENTS:
        assert not (agents / f"{name}.md").exists(), f"{name} descreve repos de outro ecossistema"
    assert (agents / "README.md").is_file(), "o README descreve o MECANISMO e continua vindo"


def test_the_flag_brings_them_for_the_theo_ecosystem(tmp_path: Path) -> None:
    """Repos do ecossistema `theo` ainda os obtêm — `theo-rag` não os versiona."""
    target = tmp_path / "consumidor"
    _install(target, "--with-domain-agents")
    agents = target / ".claude" / "agents"
    for name in _DOMAIN_AGENTS:
        assert (agents / f"{name}.md").is_file(), name


def test_the_manifest_does_not_claim_agents_it_did_not_install(tmp_path: Path) -> None:
    """Manifesto que mente é pior que manifesto nenhum: o consumidor o usa para
    decidir o que é dele."""
    target = tmp_path / "consumidor"
    _install(target)
    listed = (target / MANIFEST).read_text(encoding="utf-8")
    for name in _DOMAIN_AGENTS:
        assert f"agents/{name}.md" not in listed, name


# ---------------------------------------------------------------------------
# Os agentes do PROJETO sobrevivem a qualquer instalação. Sem isto, a limpeza
# feita num consumidor dura até a próxima instalação — e pior, uma instalação
# sem --merge apagava os especialistas que o projeto escreveu.
# ---------------------------------------------------------------------------

def _project_agents(target: Path) -> Path:
    agents = target / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "meu-dominio.md").write_text("# especialista do projeto\n", encoding="utf-8")
    (agents / "meu-validador.md").write_text("# validador do projeto\n", encoding="utf-8")
    (agents / "README.md").write_text("# README que o projeto escreveu\n", encoding="utf-8")
    return agents


def test_a_plain_install_never_deletes_project_agents(tmp_path: Path) -> None:
    """`rm -rf agents/` levava junto o que o projeto escreveu."""
    target = tmp_path / "consumidor"
    _project_agents(target)
    _install(target, "--force")
    agents = target / ".claude" / "agents"
    assert (agents / "meu-dominio.md").is_file()
    assert (agents / "meu-validador.md").is_file()


def test_an_existing_agents_readme_is_kept(tmp_path: Path) -> None:
    """O README lista os agentes DO PROJETO depois que alguém o adapta."""
    target = tmp_path / "consumidor"
    _project_agents(target)
    _install(target, "--merge")
    kept = (target / ".claude" / "agents" / "README.md").read_text(encoding="utf-8")
    assert "que o projeto escreveu" in kept


def test_the_readme_is_written_when_absent(tmp_path: Path) -> None:
    target = tmp_path / "consumidor"
    _install(target)
    assert (target / ".claude" / "agents" / "README.md").is_file()


def test_with_domain_agents_does_not_touch_project_agents(tmp_path: Path) -> None:
    target = tmp_path / "consumidor"
    _project_agents(target)
    _install(target, "--merge", "--with-domain-agents")
    agents = target / ".claude" / "agents"
    assert (agents / "meu-dominio.md").is_file()
    assert (agents / "engine-go.md").is_file(), "a flag traz os do kit"


def test_merge_preserves_the_derived_routing_table(tmp_path: Path) -> None:
    """A tabela de roteamento é CONFIGURAÇÃO do projeto e mora num `.md` do kit.

    Medido no `speculative`: a reinstalação restaurou a tabela do ecossistema `theo`
    por cima da derivada, e `route_domain speculative` foi de exit 0 para exit 1 — o
    projeto deixou de conseguir rotear itens sobre si mesmo. O resto do
    `cycle-backlog.md` é contrato do kit e continua sendo atualizado; só a seção
    `## Domain routing` é do consumidor.
    """
    target = tmp_path / "consumidor"
    rules = target / ".claude" / "rules"
    rules.mkdir(parents=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (rules / "cycle-backlog.md").write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `meu-dominio` | `meu-repo` | `agents/meu-dominio.md` |\n\n"
        "## Verdicts\n\nvelho\n",
        encoding="utf-8",
    )
    _install(target, "--merge")

    body = (rules / "cycle-backlog.md").read_text(encoding="utf-8")
    assert "`meu-dominio`" in body, "a tabela derivada foi sobrescrita"
    assert "engine-go" not in body, "a tabela do outro ecossistema voltou"
    assert "## Hard gates" in body, "o resto da regra tem de vir atualizado do kit"

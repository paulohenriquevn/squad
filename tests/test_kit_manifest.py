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

def _install(target: Path, *flags: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    subprocess.run(
        ["bash", str(_REPO / "scripts" / "install.sh"), str(target), *flags],
        capture_output=True, text=True, check=True,
    )


def test_no_specialist_is_ever_installed(tmp_path: Path) -> None:
    """Só o README viaja. Um especialista descreve os repos de UM ecossistema.

    O kit carregava oito, do ecossistema em que foi escrito, e a flag
    `--with-domain-agents` os entregava a quem pedisse. Saíram em 2026-08-26. Este
    teste não fixa os nomes que saíram — fixa a REGRA, e por isso continua valendo
    para um especialista que alguém escreva na fonte amanhã: nada em `agents/` além
    do README é do consumidor até que ele o derive.
    """
    target = tmp_path / "consumidor"
    _install(target)
    agents = target / ".claude" / "agents"
    installed = sorted(p.name for p in agents.glob("*.md"))
    assert installed == ["README.md"], (
        f"a instalação trouxe especialistas de outro ecossistema: {installed}"
    )


def test_the_manifest_does_not_claim_agents_it_did_not_install(tmp_path: Path) -> None:
    """Manifesto que mente é pior que manifesto nenhum: o consumidor o usa para
    decidir o que é dele."""
    target = tmp_path / "consumidor"
    _install(target)
    listed = [
        line.strip() for line in (target / MANIFEST).read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("agents/")
    ]
    assert listed == ["agents/README.md"], listed


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


def test_the_removed_flag_is_refused_instead_of_ignored(tmp_path: Path) -> None:
    """`--with-domain-agents` saiu com os especialistas. Aceitá-la em silêncio faria
    quem a usa acreditar que recebeu algo."""
    target = tmp_path / "consumidor"
    target.mkdir(parents=True, exist_ok=True)
    (target / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(_REPO / "scripts" / "install.sh"), str(target), "--with-domain-agents"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 2, proc.stdout
    assert "unknown flag" in proc.stderr


def test_merge_preserves_the_derived_routing_table(tmp_path: Path) -> None:
    """A tabela de roteamento é CONFIGURAÇÃO do projeto e mora num `.md` do kit.

    Medido no `speculative`: a reinstalação restaurou a tabela do ecossistema de
    origem por cima da derivada, e `route_domain speculative` foi de exit 0 para exit 1 — o
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
    assert "_(empty" not in body, "o template vazio sobrescreveu a tabela derivada"
    assert "## Hard gates" in body, "o resto da regra tem de vir atualizado do kit"


# ---------------------------------------------------------------------------
# O kit distribuía a configuração DELE como se fosse do consumidor. Medido no
# `speculative`: nasceu com `python | pyproject.toml | ENABLED` (o squad é
# Python; o alvo não tem pyproject) e com o alvo vivo do ecossistema de origem
# — uma URL de ambiente dev de outra gente. São 41 instalações nessa condição.
# ---------------------------------------------------------------------------

def _active_lines(path: Path) -> list[str]:
    return [l for l in path.read_text(encoding="utf-8").splitlines()  # noqa: E741
            if l.strip() and not l.lstrip().startswith("#")]


def test_project_specific_config_is_installed_as_a_blank_template(tmp_path: Path) -> None:
    target = tmp_path / "consumidor"
    _install(target)
    rules = target / ".claude" / "rules"
    assert _active_lines(rules / "code-quality-languages.txt") == [], \
        "o consumidor nasceria com a linguagem do KIT habilitada"
    assert _active_lines(rules / "live-target.txt") == [], \
        "o consumidor nasceria sondando o serviço de outro ecossistema"


def test_universal_defaults_are_still_shipped(tmp_path: Path) -> None:
    """Os thresholds são defaults do kit (`YOUR_ADR_REF` é placeholder), não
    calibração local — esvaziá-los deixaria o gate sem banda nenhuma."""
    target = tmp_path / "consumidor"
    _install(target)
    body = (target / ".claude" / "rules" / "plan-confidence-thresholds.txt").read_text()
    assert "SHIPPABLE|90" in body


def test_the_projects_own_quality_gate_never_ships(tmp_path: Path) -> None:
    """`hooks/quality/` são os limiares DESTE repositório, não os de quem instala.

    `/quality-init` calibra no p90 do código que mede: aqui deu `max_file_lines = 367`
    e `max_function_lines = 29`. Esses números não dizem nada sobre a codebase de
    outro projeto, e um gate calibrado na régua errada nasce vermelho — que é como um
    gate é desligado na primeira hora. Mesmo defeito que a tabela de roteamento e os
    `rules/*.txt` já corrigiram: distribuir a configuração de quem escreveu.
    """
    target = tmp_path / "consumidor"
    _install(target)
    hooks = target / ".claude" / "hooks"

    assert hooks.is_dir(), "os hooks do kit continuam vindo"
    assert not (hooks / "quality").exists(), (
        "o gate de smells calibrado neste repositório chegou ao consumidor"
    )
    listed = (target / MANIFEST).read_text(encoding="utf-8")
    assert "hooks/quality" not in listed

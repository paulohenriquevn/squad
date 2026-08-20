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

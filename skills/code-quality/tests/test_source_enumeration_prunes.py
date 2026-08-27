"""A enumeração de fontes PODA na travessia, não filtra depois.

`_enumerate_source_files` descia em `node_modules`, `.git` e `.venv` inteiros e
só então descartava o que havia encontrado. O resultado era o mesmo; o custo,
não. Medido em 2026-08-26 num repositório de 56.128 arquivos (40 mil deles em
`node_modules`): 326 ms percorrendo tudo contra 0,4 ms podando — 832x, uma vez
por linguagem habilitada.

Esta é a mesma lição que o CHANGELOG já registra em `check_wiring.py`
(1080 ms -> 13 ms, 83x). Os testes abaixo fixam a FORMA de onde a velocidade
vem, porque asserção de duração é teste instável em máquina carregada.
"""
from __future__ import annotations

import pathlib
from pathlib import Path

import pytest

from scripts.run_code_quality import _enumerate_source_files


def _tree(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    for skipped in ("node_modules", ".git", ".venv", "__pycache__", "dist"):
        d = root / skipped / "deep" / "deeper"
        d.mkdir(parents=True)
        (d / "noise.py").write_text("x = 1\n", encoding="utf-8")


def test_finds_project_sources(tmp_path):
    _tree(tmp_path)
    names = {p.name for p in _enumerate_source_files(tmp_path, "python")}
    assert names == {"app.py"}


def test_does_not_traverse_skipped_trees(tmp_path, monkeypatch):
    """Sem `rglob` sobre a árvore inteira — a poda tem de acontecer durante.

    Um `rglob("*")` seguido de filtro produz a resposta certa pelo caminho
    errado: ele já desceu em tudo que ia descartar. Proibir a primitiva é o que
    torna a poda verificável sem cronômetro.
    """
    _tree(tmp_path)

    def forbidden(self, *args, **kwargs):
        raise AssertionError(
            "rglob sobre a árvore inteira: a poda voltou a acontecer depois da travessia"
        )

    monkeypatch.setattr(pathlib.Path, "rglob", forbidden)

    names = {p.name for p in _enumerate_source_files(tmp_path, "python")}
    assert names == {"app.py"}


@pytest.mark.parametrize(
    ("language", "filename"),
    [("typescript", "a.ts"), ("rust", "a.rs"), ("go", "a.go")],
)
def test_other_languages_keep_working(tmp_path, language, filename):
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / filename).write_text("// x\n", encoding="utf-8")
    (tmp_path / "node_modules" / "dep").mkdir(parents=True)
    (tmp_path / "node_modules" / "dep" / filename).write_text("// x\n", encoding="utf-8")
    names = {p.name for p in _enumerate_source_files(tmp_path, language)}
    assert names == {filename}

"""D3 — cross-package wiring: a public export nobody imports.

O DEFEITO QUE ISTO FIXA
-----------------------
`code-quality-golden-rule.md § 5` lista D3 como contrato LOCKED — "ast-grep |
All enabled | Public exports have at least one importer (soft cap)". Os quatro
detectores devolviam a mesma string:

    return self.unavailable("d3", "orphan_export", "cross-package wiring is not configured")

Como `unavailable()` emite SOFT_CAP, todo audit nascia com um soft cap permanente
e `PASS` era inalcançável por construção — em qualquer projeto, para sempre. Um
gate que não pode ser satisfeito não é um gate: é um imposto que o `/implement`
converte em WARN e ninguém lê.

POR QUE A SUPERFÍCIE PÚBLICA É DECLARADA, NUNCA INFERIDA
--------------------------------------------------------
A tentação é chamar de "export público" todo nome sem underscore. Num kit de
scripts isso produz centenas de findings: uma função chamada só dentro do próprio
arquivo é interna de fato, e listá-la como órfã transforma o detector em ruído —
que é a forma mais eficiente de desligar um gate sem removê-lo.

Então D3 audita o que o projeto DECLAROU como superfície: `__all__` e re-exports
de `__init__.py` em Python, os arquivos que `package.json` aponta em TypeScript,
`pub` em `src/lib.rs` no Rust, identificadores exportados fora de `internal/` no
Go. Um projeto que não declara superfície nenhuma recebe INFO dizendo isso — não
um veredito fabricado sobre uma superfície que o detector inventou.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.detectors import _wiring


def _write(root: Path, rel: str, body: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Python — a superfície é `__all__` e o que `__init__.py` re-exporta
# ---------------------------------------------------------------------------

def test_python_export_with_no_importer_is_an_orphan(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/api.py", '__all__ = ["ninguem_me_chama"]\n\n\ndef ninguem_me_chama():\n    return 1\n')

    findings = _wiring.detect_orphan_exports("python", tmp_path, tmp_path)

    orphans = [f for f in findings if f.detector == "d3_orphan_export"]
    assert len(orphans) == 1, [f.message for f in findings]
    assert orphans[0].severity == "SOFT_CAP"
    assert "ninguem_me_chama" in orphans[0].symbol_or_line
    assert orphans[0].file_path == "pkg/api.py"


def test_python_export_with_an_importer_is_not_an_orphan(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/api.py", '__all__ = ["usada"]\n\n\ndef usada():\n    return 1\n')
    _write(tmp_path, "app/main.py", "from pkg.api import usada\n\nprint(usada())\n")

    findings = _wiring.detect_orphan_exports("python", tmp_path, tmp_path)

    assert [f for f in findings if f.detector == "d3_orphan_export"] == []


def test_a_test_file_is_not_a_consumer(tmp_path: Path) -> None:
    """Um símbolo que só o teste dele exercita não está integrado.

    É o mesmo raciocínio do pilar (a) da tríade de wiring: o teste prova que o
    código FUNCIONA, não que alguém o USA. Contar o teste como importador é como
    o gate de cobertura contava o exit code do runner.
    """
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/api.py", '__all__ = ["so_o_teste_usa"]\n\n\ndef so_o_teste_usa():\n    return 1\n')
    _write(tmp_path, "tests/test_api.py", "from pkg.api import so_o_teste_usa\n\n\ndef test_x():\n    assert so_o_teste_usa() == 1\n")

    orphans = [f for f in _wiring.detect_orphan_exports("python", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert len(orphans) == 1, "o teste do próprio símbolo não é consumidor"


def test_a_definition_site_is_not_its_own_consumer(tmp_path: Path) -> None:
    """O arquivo que define o símbolo o menciona por definição — literalmente."""
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/api.py",
           '__all__ = ["solitaria"]\n\n\ndef solitaria():\n    return interna()\n\n\ndef interna():\n    return solitaria\n')

    orphans = [f for f in _wiring.detect_orphan_exports("python", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert len(orphans) == 1


def test_init_reexport_counts_as_declared_surface(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/__init__.py", "from pkg.api import exposta\n")
    _write(tmp_path, "pkg/api.py", "def exposta():\n    return 1\n")

    findings = _wiring.detect_orphan_exports("python", tmp_path, tmp_path)
    orphans = [f for f in findings if f.detector == "d3_orphan_export"]

    assert len(orphans) == 1
    assert "exposta" in orphans[0].symbol_or_line


def test_a_project_with_no_declared_surface_reports_info_not_a_verdict(tmp_path: Path) -> None:
    """Sem superfície declarada não há o que auditar — e dizer isso é a resposta.

    O caminho errado seria inferir uma superfície e emitir SOFT_CAP sobre ela:
    produziria um veredito sobre um contrato que ninguém escreveu.
    """
    _write(tmp_path, "solto.py", "def qualquer():\n    return 1\n")

    findings = _wiring.detect_orphan_exports("python", tmp_path, tmp_path)

    assert [f for f in findings if f.detector == "d3_orphan_export"] == []
    info = [f for f in findings if f.severity == "INFO"]
    assert len(info) == 1
    assert "no declared public surface" in info[0].message


# ---------------------------------------------------------------------------
# TypeScript — a superfície é o que `package.json` aponta
# ---------------------------------------------------------------------------

def test_typescript_barrel_export_with_no_importer_is_an_orphan(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"name": "p", "main": "src/index.ts"}\n')
    _write(tmp_path, "src/index.ts", "export function orfa(): number {\n  return 1;\n}\n")

    orphans = [f for f in _wiring.detect_orphan_exports("typescript", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert len(orphans) == 1
    assert "orfa" in orphans[0].symbol_or_line


def test_typescript_export_consumed_elsewhere_is_not_an_orphan(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"name": "p", "main": "src/index.ts"}\n')
    _write(tmp_path, "src/index.ts", "export function usada(): number {\n  return 1;\n}\n")
    _write(tmp_path, "app/run.ts", 'import { usada } from "../src/index";\n\nusada();\n')

    assert [f for f in _wiring.detect_orphan_exports("typescript", tmp_path, tmp_path)
            if f.detector == "d3_orphan_export"] == []


# ---------------------------------------------------------------------------
# Rust e Go
# ---------------------------------------------------------------------------

def test_rust_pub_in_lib_with_no_consumer_is_an_orphan(tmp_path: Path) -> None:
    _write(tmp_path, "Cargo.toml", '[package]\nname = "p"\n')
    _write(tmp_path, "src/lib.rs", "pub fn orfa() -> u8 {\n    1\n}\n")

    orphans = [f for f in _wiring.detect_orphan_exports("rust", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert len(orphans) == 1
    assert "orfa" in orphans[0].symbol_or_line


def test_go_exported_identifier_with_a_consumer_is_not_an_orphan(tmp_path: Path) -> None:
    _write(tmp_path, "go.mod", "module exemplo\n")
    _write(tmp_path, "pkg/api.go", "package pkg\n\nfunc Usada() int {\n\treturn 1\n}\n")
    _write(tmp_path, "cmd/main.go", 'package main\n\nimport "exemplo/pkg"\n\nfunc main() {\n\tpkg.Usada()\n}\n')

    assert [f for f in _wiring.detect_orphan_exports("go", tmp_path, tmp_path)
            if f.detector == "d3_orphan_export"] == []


def test_go_internal_package_is_not_public_surface(tmp_path: Path) -> None:
    """`internal/` é inacessível de fora do módulo — por regra do compilador."""
    _write(tmp_path, "go.mod", "module exemplo\n")
    _write(tmp_path, "internal/secreto/api.go", "package secreto\n\nfunc NaoExportavel() int {\n\treturn 1\n}\n")

    assert [f for f in _wiring.detect_orphan_exports("go", tmp_path, tmp_path)
            if f.detector == "d3_orphan_export"] == []


# ---------------------------------------------------------------------------
# Contrato comum
# ---------------------------------------------------------------------------

def test_an_unknown_language_is_reported_unavailable_not_clean(tmp_path: Path) -> None:
    findings = _wiring.detect_orphan_exports("cobol", tmp_path, tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "SOFT_CAP"
    assert "auditor unavailable" in findings[0].message


@pytest.mark.parametrize("language", ["python", "typescript", "rust", "go"])
def test_findings_carry_a_wellformed_allowlist_key(tmp_path: Path, language: str) -> None:
    """`Finding.__post_init__` exige exatamente 3 pipes; um key malformado aborta
    o processamento da allowlist inteira com um HARD finding."""
    _write(tmp_path, "package.json", '{"name": "p", "main": "src/index.ts"}\n')
    _write(tmp_path, "src/index.ts", "export function orfa(): number {\n  return 1;\n}\n")
    _write(tmp_path, "Cargo.toml", '[package]\nname = "p"\n')
    _write(tmp_path, "src/lib.rs", "pub fn orfa_rs() -> u8 {\n    1\n}\n")
    _write(tmp_path, "go.mod", "module exemplo\n")
    _write(tmp_path, "pkg/api.go", "package pkg\n\nfunc Orfa() int {\n\treturn 1\n}\n")
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/api.py", '__all__ = ["orfa_py"]\n\n\ndef orfa_py():\n    return 1\n')

    for finding in _wiring.detect_orphan_exports(language, tmp_path, tmp_path):
        assert finding.allowlist_key.count("|") == 3, finding.allowlist_key
        assert finding.language == language


def test_a_type_named_in_another_public_signature_is_not_an_orphan(tmp_path: Path) -> None:
    """Um tipo alcançável pela assinatura de outra export vive através dela.

    Medido no próprio kit: `AllowlistEntry` é o tipo de retorno de `load_allowlist`,
    e nenhum arquivo o importa por nome — quem chama a função recebe a instância. Um
    detector que o chamasse de órfão empurraria o projeto a removê-lo de `__all__`,
    quebrando quem quisesse anotar o retorno. Falso positivo em SOFT_CAP é caro do
    mesmo jeito: gera allowlist espúria e ensina a ignorar o gate.
    """
    _write(tmp_path, "pkg/__init__.py", "")
    _write(
        tmp_path,
        "pkg/api.py",
        "__all__ = [\"Registro\", \"carrega\"]\n\n\n"
        "class Registro:\n    pass\n\n\n"
        "def carrega(path) -> list[Registro]:\n    return [Registro()]\n",
    )
    _write(tmp_path, "app/main.py", "from pkg.api import carrega\n\nprint(carrega('x'))\n")

    orphans = [f for f in _wiring.detect_orphan_exports("python", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert orphans == [], [f.symbol_or_line for f in orphans]


def test_a_type_in_a_private_signature_is_still_an_orphan(tmp_path: Path) -> None:
    """A regra é assinatura de outra EXPORT — não de qualquer função do módulo.

    Sem esta, bastaria uma função interna anotar o tipo para o símbolo desaparecer
    do relatório, e o gate deixaria de enxergar superfície morta.
    """
    _write(tmp_path, "pkg/__init__.py", "")
    _write(
        tmp_path,
        "pkg/api.py",
        "__all__ = [\"Registro\", \"carrega\"]\n\n\n"
        "class Registro:\n    pass\n\n\n"
        "def _interna() -> Registro:\n    return Registro()\n\n\n"
        "def carrega():\n    return 1\n",
    )
    _write(tmp_path, "app/main.py", "from pkg.api import carrega\n\nprint(carrega())\n")

    orphans = [f.symbol_or_line for f in _wiring.detect_orphan_exports("python", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert orphans == ["Registro"]

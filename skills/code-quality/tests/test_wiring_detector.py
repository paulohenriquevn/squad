"""D3 — cross-package wiring: a public export nobody imports.

THE DEFECT THIS FIXES
---------------------
`code-quality-golden-rule.md § 5` lists D3 as a LOCKED contract — "ast-grep |
All enabled | Public exports have at least one importer (soft cap)". All four
detectors returned the same string:

    return self.unavailable("d3", "orphan_export", "cross-package wiring is not configured")

Since `unavailable()` emits SOFT_CAP, every audit was born with a permanent soft cap
and `PASS` was unreachable by construction — in any project, forever. A gate that
cannot be satisfied is not a gate: it is a tax `/implement` converts into a WARN
nobody reads.

WHY THE PUBLIC SURFACE IS DECLARED, NEVER INFERRED
--------------------------------------------------
The temptation is to call every name without an underscore a "public export". In
a repository of scripts that produces hundreds of findings: a function called only
inside its own file is internal in fact, and listing it as an orphan turns the
detector into noise — the most efficient way to switch a gate off without removing
it.

So D3 audits what the project DECLARED as surface: `__all__` and `__init__.py`
re-exports in Python, the files `package.json` points at in TypeScript, `pub` in
`src/lib.rs` in Rust, exported identifiers outside `internal/` in Go. A project
that declares no surface at all gets an INFO saying exactly that — not a fabricated
verdict about a surface the detector invented.
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
# Python — the surface is `__all__` and what `__init__.py` re-exports
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
    """A symbol only its own test exercises is not integrated.

    Same reasoning as pillar (a) of the wiring triad: the test proves the code
    WORKS, not that anything USES it. Counting the test as an importer is how the
    coverage gate used to count a runner's exit code.
    """
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/api.py", '__all__ = ["so_o_teste_usa"]\n\n\ndef so_o_teste_usa():\n    return 1\n')
    _write(tmp_path, "tests/test_api.py", "from pkg.api import so_o_teste_usa\n\n\ndef test_x():\n    assert so_o_teste_usa() == 1\n")

    orphans = [f for f in _wiring.detect_orphan_exports("python", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert len(orphans) == 1, "a symbol's own test is not a consumer"


def test_a_definition_site_is_not_its_own_consumer(tmp_path: Path) -> None:
    """The file defining the symbol mentions it by definition — literally."""
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
    """With no declared surface there is nothing to audit — and saying so is the answer.

    The wrong path would be to infer a surface and emit SOFT_CAP against it: that
    would produce a verdict about a contract nobody wrote.
    """
    _write(tmp_path, "loose.py", "def anything():\n    return 1\n")

    findings = _wiring.detect_orphan_exports("python", tmp_path, tmp_path)

    assert [f for f in findings if f.detector == "d3_orphan_export"] == []
    info = [f for f in findings if f.severity == "INFO"]
    assert len(info) == 1
    assert "no declared public surface" in info[0].message


# ---------------------------------------------------------------------------
# TypeScript — the surface is what `package.json` points at
# ---------------------------------------------------------------------------

def test_typescript_barrel_export_with_no_importer_is_an_orphan(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"name": "p", "main": "src/index.ts"}\n')
    _write(tmp_path, "src/index.ts", "export function orphan(): number {\n  return 1;\n}\n")

    orphans = [f for f in _wiring.detect_orphan_exports("typescript", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert len(orphans) == 1
    assert "orphan" in orphans[0].symbol_or_line


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
    _write(tmp_path, "src/lib.rs", "pub fn orphan() -> u8 {\n    1\n}\n")

    orphans = [f for f in _wiring.detect_orphan_exports("rust", tmp_path, tmp_path)
               if f.detector == "d3_orphan_export"]

    assert len(orphans) == 1
    assert "orphan" in orphans[0].symbol_or_line


def test_go_exported_identifier_with_a_consumer_is_not_an_orphan(tmp_path: Path) -> None:
    _write(tmp_path, "go.mod", "module example\n")
    _write(tmp_path, "pkg/api.go", "package pkg\n\nfunc Usada() int {\n\treturn 1\n}\n")
    _write(tmp_path, "cmd/main.go", 'package main\n\nimport "example/pkg"\n\nfunc main() {\n\tpkg.Usada()\n}\n')

    assert [f for f in _wiring.detect_orphan_exports("go", tmp_path, tmp_path)
            if f.detector == "d3_orphan_export"] == []


def test_go_internal_package_is_not_public_surface(tmp_path: Path) -> None:
    """`internal/` is unreachable from outside the module — by compiler rule."""
    _write(tmp_path, "go.mod", "module example\n")
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
    """`Finding.__post_init__` requires exactly 3 pipes; a malformed key aborts
    processing of the whole allowlist with a HARD finding."""
    _write(tmp_path, "package.json", '{"name": "p", "main": "src/index.ts"}\n')
    _write(tmp_path, "src/index.ts", "export function orphan(): number {\n  return 1;\n}\n")
    _write(tmp_path, "Cargo.toml", '[package]\nname = "p"\n')
    _write(tmp_path, "src/lib.rs", "pub fn orphan_rs() -> u8 {\n    1\n}\n")
    _write(tmp_path, "go.mod", "module example\n")
    _write(tmp_path, "pkg/api.go", "package pkg\n\nfunc Orfa() int {\n\treturn 1\n}\n")
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/api.py", '__all__ = ["orphan_py"]\n\n\ndef orphan_py():\n    return 1\n')

    for finding in _wiring.detect_orphan_exports(language, tmp_path, tmp_path):
        assert finding.allowlist_key.count("|") == 3, finding.allowlist_key
        assert finding.language == language


def test_a_type_named_in_another_public_signature_is_not_an_orphan(tmp_path: Path) -> None:
    """A type reachable through another export's signature lives through it.

    Measured on the kit itself: `AllowlistEntry` is `load_allowlist`'s return type,
    and no file imports it by name — whoever calls the function receives the
    instance. A detector calling it an orphan would push the project to remove it
    from `__all__`, breaking anyone who wanted to annotate the return. A false
    positive at SOFT_CAP is expensive all the same: it generates a spurious
    allowlist entry and teaches people to ignore the gate.
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
    """The rule is another EXPORT's signature — not any function in the module.

    Without this, an internal helper annotating the type would be enough to make the
    symbol vanish from the report, and the gate would stop seeing dead surface.
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

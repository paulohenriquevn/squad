"""O smoke test verifica sintaxe sem escrever bytecode no alvo.

`check_python_syntax` usava `py_compile.compile`, que ESCREVE o `.pyc` em
`__pycache__` como efeito colateral. Duas consequências, ambas medidas em
2026-08-26:

1. Custo. Compilar-e-gravar 259 arquivos levava 267 ms dos 693 ms do smoke, e o
   smoke é chamado por `install.sh` — que responde por 21 execuções na suíte
   raiz sozinha (1 071 ms cada). Verificar sintaxe não exige gravar nada.
2. Higiene. O cabeçalho do `install.sh` promete não levar cache ao consumidor, e
   `prune_caches` existe exatamente porque este passo o reintroduzia depois da
   cópia. A promessa passa a ser cumprida na origem.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "test_e2e_smoke.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _load():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_smoke_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_ecosystem(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def test_syntax_check_writes_no_bytecode(tmp_path):
    module = _load()
    eco = _fake_ecosystem(tmp_path)

    ok, issues = module.check_python_syntax(eco)

    assert ok, issues
    caches = list(eco.rglob("__pycache__"))
    assert caches == [], f"o verificador de sintaxe deixou cache no alvo: {caches}"
    assert list(eco.rglob("*.pyc")) == []


def test_syntax_error_is_still_reported(tmp_path):
    module = _load()
    eco = _fake_ecosystem(tmp_path)
    (eco / "scripts" / "broken.py").write_text("def f(:\n", encoding="utf-8")

    ok, issues = module.check_python_syntax(eco)

    assert not ok
    assert any("broken.py" in i for i in issues), issues


def test_cache_directories_are_not_traversed(tmp_path):
    """Um `__pycache__` com um arquivo inválido não pode reprovar o smoke."""
    module = _load()
    eco = _fake_ecosystem(tmp_path)
    cache = eco / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "stale.py").write_text("def f(:\n", encoding="utf-8")

    ok, issues = module.check_python_syntax(eco)

    assert ok, issues


def test_the_script_still_passes_end_to_end():
    """Regressão de integração: o smoke real continua verde neste repositório."""
    proc = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

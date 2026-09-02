"""The smoke test checks syntax without writing bytecode into the target.

`check_python_syntax` used `py_compile.compile`, which WRITES the `.pyc` into
`__pycache__` as a side effect. Two consequences, both measured on
2026-08-26:

1. Cost. Compiling-and-writing 259 files took 267 ms of the smoke's 693 ms, and the
   smoke is called by `install.sh` — which accounts for 21 runs in the root suite
   alone (1,071 ms each). Checking syntax requires writing nothing.
2. Hygiene. `install.sh`'s header promises not to carry cache to the consumer, and
   `prune_caches` exists precisely because this step reintroduced it after the
   copy. The promise is now kept at the source.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"

sys.path.insert(0, str(REPO_ROOT / "mechanisms" / "gates"))


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
    """A `__pycache__` holding an invalid file must not fail the smoke."""
    module = _load()
    eco = _fake_ecosystem(tmp_path)
    cache = eco / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "stale.py").write_text("def f(:\n", encoding="utf-8")

    ok, issues = module.check_python_syntax(eco)

    assert ok, issues


def test_the_script_still_passes_end_to_end():
    """Integration regression: the real smoke stays green in this repository."""
    proc = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

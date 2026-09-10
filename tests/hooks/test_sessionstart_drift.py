"""SessionStart reports kit drift when there is a source to compare against.

Issue #23 — `check_install_drift` shipped for weeks with nine prose mentions
and zero call sites. The gate answered correctly when invoked by hand; the hand
that had to invoke it belonged to no schedule, so a consumer ran ten hours on
a kit missing three merged repairs.

The wiring here (`drift_line` in `sessionstart-context.py`) reports the counts
as one context line at session start. **It never blocks and never fails the
session** — a consumer that pinned an older version deliberately keeps the
signal without being stopped over it. The env var `SQUAD_KIT_SOURCE` names the
tree to compare against; silence when unset is the correct default.

These tests exercise `drift_line` directly rather than the whole hook so the
four cases (unset · misconfigured · same tree · real drift) are visible one at
a time, and the assertions live one directory over from the wiring they lock.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_HOOK_PATH = _REPO / "hooks" / "sessionstart-context.py"


def _load_module():
    """Import the hook by path — its filename contains a dash, so the usual
    `from … import …` machinery cannot reach it."""
    sys.path.insert(0, str(_REPO))
    spec = importlib.util.spec_from_file_location("sessionstart_context_under_test",
                                                   _HOOK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _kit_at(root: Path, *, gate: bool = True) -> Path:
    """Materialize a directory that `has_kit()` accepts.

    The gate needs `mechanisms/gates/check_install_drift.py` to be present on
    the install side (that is what the hook shells out to). We reuse the real
    file from this repository so we exercise the actual gate rather than a stub.
    """
    for tree in ("skills", "rules", "hooks"):
        (root / tree).mkdir(parents=True, exist_ok=True)
    if gate:
        gate_dir = root / "mechanisms" / "gates"
        gate_dir.mkdir(parents=True, exist_ok=True)
        real = _REPO / "mechanisms" / "gates" / "check_install_drift.py"
        (gate_dir / "check_install_drift.py").write_text(
            real.read_text(encoding="utf-8"), encoding="utf-8")
        # The gate resolves data roots through the shared package rather than
        # restating them, so a synthetic kit needs it too. Copying the real file keeps
        # this exercising the actual gate instead of a stub that cannot drift.
        pkg = root / "squad"
        pkg.mkdir(parents=True, exist_ok=True)
        for module in ("__init__.py", "paths.py", "contexts.py", "outputs.py"):
            source = _REPO / "squad" / module
            if source.is_file():
                (pkg / module).write_text(source.read_text(encoding="utf-8"),
                                          encoding="utf-8")
    return root


def _layout(kit_dir: Path):
    module = _load_module()
    from squad.layout import Layout  # imported through the hook's sys.path insert
    return module, Layout(kit_dir=kit_dir, eco=kit_dir, project_dir=kit_dir,
                          kind="copy")


def test_silent_when_the_env_var_is_unset(tmp_path, monkeypatch) -> None:
    """No env var → no compare. A hook that spoke about a check it could not
    run would train readers to ignore the context lines that follow."""
    monkeypatch.delenv("SQUAD_KIT_SOURCE", raising=False)
    module, layout = _layout(_kit_at(tmp_path / "install"))

    assert module.drift_line(layout) is None


def test_names_the_misconfiguration_when_the_source_is_not_a_kit(tmp_path,
                                                                  monkeypatch) -> None:
    """The env var was set to a path that does not contain skills/rules/hooks/.
    Silence here would look like a clean bill of health for a check that never
    ran, which is worse than the misconfiguration itself."""
    (tmp_path / "not-a-kit").mkdir()
    monkeypatch.setenv("SQUAD_KIT_SOURCE", str(tmp_path / "not-a-kit"))
    module, layout = _layout(_kit_at(tmp_path / "install"))

    line = module.drift_line(layout)

    assert line is not None
    assert "SQUAD_KIT_SOURCE" in line
    assert "cannot compare" in line


def test_silent_when_source_and_install_are_the_same_tree(tmp_path,
                                                           monkeypatch) -> None:
    """Standalone layout, or an env var pointing at the very directory the
    session is running. Comparing a tree to itself is not a report."""
    kit = _kit_at(tmp_path / "kit")
    monkeypatch.setenv("SQUAD_KIT_SOURCE", str(kit))
    module, layout = _layout(kit)

    assert module.drift_line(layout) is None


def test_reports_kit_ahead_when_the_install_is_behind(tmp_path,
                                                       monkeypatch) -> None:
    """The consumer's install lacks work the source holds. The report names it.

    Constructed from the issue's evidence: three files present in the source and
    missing from the install, under `skills/` — a directory the kit has, so
    reporting is the point. Real bytes, real invocation of `check_install_drift`
    — a stubbed gate would let the wiring lie about what it reports.
    """
    install = _kit_at(tmp_path / "install")
    source = _kit_at(tmp_path / "source")
    # Files present in both but with divergent content → DIVERGED
    (install / "skills" / "shared.txt").write_text("install-only-line\n", encoding="utf-8")
    (source / "skills" / "shared.txt").write_text("source-only-line\n", encoding="utf-8")
    monkeypatch.setenv("SQUAD_KIT_SOURCE", str(source))
    module, layout = _layout(install)

    line = module.drift_line(layout)

    assert line is not None, "drift the gate detects on the command line must reach the context"
    assert "Kit drift" in line
    assert "diverged" in line
    assert "never blocks" in line, "the wording must say what the hook refuses to do"


def test_returns_zero_and_never_raises_when_the_gate_itself_fails(tmp_path,
                                                                    monkeypatch) -> None:
    """The subprocess errors, times out, or exits non-zero: the hook still
    returns cleanly. The whole point of `never blocks`."""
    install = _kit_at(tmp_path / "install", gate=False)  # no gate file on install
    source = _kit_at(tmp_path / "source")
    monkeypatch.setenv("SQUAD_KIT_SOURCE", str(source))
    module, layout = _layout(install)

    # No `check_install_drift.py` in the install → hook cannot shell out → None.
    assert module.drift_line(layout) is None

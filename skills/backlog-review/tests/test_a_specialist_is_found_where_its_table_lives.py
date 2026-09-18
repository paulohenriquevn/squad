"""A nested registry reported every route broken, on specialists that exist.

`check_backlog_structure` resolved `agents/<specialist>.md` against the registry's own
directory. For a monorepo whose registry sits at `apps/<app>/BACKLOG.md` while the kit is
installed at the root, that looks in `apps/<app>/agents/` — and the routing table's
`agents/` is at the root. Every domain came back `broken_route`, blocker, on files that
were on disk.

This is the unfixed half of the nested-registry fix: `_routing_table_path` learned to
walk up, so the TABLE is found, but the specialists it names were still resolved against
the old root. Reporting that fix as complete was wrong, and the symptom only surfaced
when a real session ran the gate against a real nested registry — the kit's own tree has
no `apps/`, and neither did the repro written at the time.

The resolution here is exact rather than heuristic: `agents/` is relative to the
directory the TABLE was read from. A table at `<root>/.claude/rules/` refers to
`<root>/.claude/agents/`, and a sub-project with its own table keeps pointing at its own
specialists — which a second upward walk would have broken.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "backlog-review" / "scripts" / "check_backlog_structure.py"

_TABLE = "# Domain routing\n#\n# Format:  domain | repo | agents/<specialist>.md\n#\nweb | repo-a | agents/x.md\n"
_REGISTRY = "# Backlog\n\n## Items\n\n_None yet. Next free id: B-001._\n"


def _run(path: Path) -> str:
    done = subprocess.run([sys.executable, str(_SCRIPT), str(path)],
                          capture_output=True, text=True, timeout=120, check=False)
    return done.stdout + done.stderr


def test_a_specialist_beside_the_table_resolves_from_a_nested_registry(tmp_path: Path) -> None:
    """The exact layout that reported four blockers on two files that exist."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "domain-routing.txt").write_text(_TABLE, encoding="utf-8")
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "x.md").write_text("# x\n", encoding="utf-8")
    nested = tmp_path / "apps" / "checkout"
    nested.mkdir(parents=True)
    registry = nested / "BACKLOG.md"
    registry.write_text(_REGISTRY, encoding="utf-8")

    assert "broken_route" not in _run(registry), (
        "a specialist beside its own routing table was reported missing")


def test_a_genuinely_missing_specialist_is_still_a_blocker(tmp_path: Path) -> None:
    """The half that must not go quiet. A domain routing to nobody is the defect this
    check exists for, and widening where it looks must not widen it into silence."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "domain-routing.txt").write_text(_TABLE, encoding="utf-8")
    (tmp_path / ".claude" / "agents").mkdir(parents=True)  # exists, and is empty
    nested = tmp_path / "apps" / "checkout"
    nested.mkdir(parents=True)
    registry = nested / "BACKLOG.md"
    registry.write_text(_REGISTRY, encoding="utf-8")

    out = _run(registry)

    assert "broken_route" in out, f"a domain routing to nothing passed:\n{out}"
    assert "x.md" in out, "the finding did not name the file the operator must create"


def test_a_sub_projects_own_table_points_at_its_own_specialists(tmp_path: Path) -> None:
    """The reason this resolves from the table rather than walking up again: a
    sub-project with its own routing is answering a different question, and its
    `agents/` is its own."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "domain-routing.txt").write_text(
        "# root\n#\nroot-domain | repo-r | agents/root.md\n", encoding="utf-8")
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "root.md").write_text("# root\n", encoding="utf-8")

    nested = tmp_path / "apps" / "checkout"
    (nested / "rules").mkdir(parents=True)
    (nested / "rules" / "domain-routing.txt").write_text(
        "# nearer\n#\nnear-domain | repo-n | agents/near.md\n", encoding="utf-8")
    (nested / "agents").mkdir(parents=True)
    (nested / "agents" / "near.md").write_text("# near\n", encoding="utf-8")
    registry = nested / "BACKLOG.md"
    registry.write_text(_REGISTRY, encoding="utf-8")

    assert "broken_route" not in _run(registry), (
        "the sub-project's own specialist was resolved against the umbrella's tree")


def test_one_run_does_not_carry_its_answer_into_the_next(tmp_path: Path) -> None:
    """The module keeps where it found the table in a module-level list.

    Left accumulating, that list carried one run's tree into the next: a suite where an
    earlier case HAD the specialist on disk made a later case find it under the earlier
    case's tmpdir, and the missing-file blocker silently stopped firing. It was a defect
    introduced by the fix this file tests, caught by `tests/test_backlog_broken_route.py`
    the first time the whole suite ran rather than the file alone.

    Two projects in one process, the first complete and the second not. The second must
    still report.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cbs", _ROOT / "skills" / "backlog-review" / "scripts" / "check_backlog_structure.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_cbs"] = mod
    spec.loader.exec_module(mod)

    def build(root: Path, *, with_specialist: bool) -> Path:
        (root / ".claude" / "rules").mkdir(parents=True)
        (root / ".claude" / "rules" / "domain-routing.txt").write_text(_TABLE, encoding="utf-8")
        (root / ".claude" / "agents").mkdir(parents=True)
        if with_specialist:
            (root / ".claude" / "agents" / "x.md").write_text("# x\n", encoding="utf-8")
        registry = root / "BACKLOG.md"
        registry.write_text(_REGISTRY, encoding="utf-8")
        return registry

    complete = build(tmp_path / "first", with_specialist=True)
    incomplete = build(tmp_path / "second", with_specialist=False)

    def checks(path: Path) -> list[str]:
        return [f["check"] if isinstance(f, dict) else f.check
                for f in mod.check_backlog(path)["findings"]]

    assert "broken_route" not in checks(complete)
    second = checks(incomplete)

    assert "broken_route" in second, (
        "the second project found the FIRST project's specialist — module state leaked "
        "between runs and the blocker stopped firing")

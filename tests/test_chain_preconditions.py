"""Refusing to start a chain that cannot finish.

A consumer ran the chain for hours and produced 85 items, 13 plans scoring 89-100
structurally, and zero implemented — every plan INVALID at the quality gate on one
unconfigured file. Nothing was wrong with the work; the refusal simply arrived at the
end instead of the beginning, and item-by-item, which made an installation problem look
like a property of each item.

The owner's rule after reading that run: it is better to run nothing than to have
unresolved conditions that block the system.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_chain_preconditions", KIT / "mechanisms" / "gates" / "check_chain_preconditions.py")
pre = importlib.util.module_from_spec(_spec)
sys.modules["check_chain_preconditions"] = pre
_spec.loader.exec_module(pre)


def _project(tmp_path: Path, *, languages: str | None = "go | go.mod | ENABLED |\n",
             routing: str | None = "core | core | agents/core.md\n",
             backlog: bool = True, manifest: str | None = "go.mod") -> Path:
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    if languages is not None:
        (tmp_path / ".claude" / "rules" / "code-quality-languages.txt").write_text(
            "# shipped examples\n" + languages, encoding="utf-8")
    if routing is not None:
        (tmp_path / ".squad").mkdir(exist_ok=True)
        (tmp_path / ".squad" / "domain-routing.txt").write_text(
            "# domain | repos | agent\n" + routing, encoding="utf-8")
    if backlog:
        (tmp_path / "BACKLOG.md").write_text("# Backlog\n\n## Items\n\n## B-001 — t\n",
                                             encoding="utf-8")
    if manifest:
        (tmp_path / manifest).write_text("module example\n", encoding="utf-8")
    return tmp_path


def _by_name(rep, name):
    return next(c for c in rep.checks if c.name == name)


# ── the night this exists because of ────────────────────────────────────────

def test_a_language_file_with_no_enabled_row_refuses_the_start(tmp_path):
    """The exact condition, caught in milliseconds instead of after the work."""
    rep = pre.measure(_project(tmp_path, languages=""))
    check = _by_name(rep, "code-quality languages")
    assert check.ok is False
    assert "no_languages_audited" in check.detail
    assert check.fix, "a refusal without a fix costs the reader the diagnosis"


def test_an_enabled_row_pointing_at_a_missing_manifest_also_refuses(tmp_path):
    """The follow-up an enablement check alone would hide.

    Measured on the same consumer: `go | go.mod | ENABLED` is well formed, passes every
    structural check, and audits NOTHING — the repository is a `go.work` workspace whose
    modules live in `api/`, `pkg/` and `operators/`, and there is no `go.mod` at the
    root. Present, correct in shape, pointing at a file that does not exist.
    """
    rep = pre.measure(_project(tmp_path, manifest=None))
    check = _by_name(rep, "language manifests")
    assert check.ok is False
    assert "go -> go.mod" in check.detail


def test_a_workspace_member_manifest_passes(tmp_path):
    (tmp_path / "api").mkdir()
    rep = pre.measure(_project(tmp_path, languages="go | api/go.mod | ENABLED |\n",
                               manifest="api/go.mod"))
    assert _by_name(rep, "language manifests").ok is True


# ── the other conditions that stop every item ───────────────────────────────

def test_an_empty_routing_table_refuses(tmp_path):
    """Gate G1 refuses every item at intake without one."""
    rep = pre.measure(_project(tmp_path, routing=""))
    assert _by_name(rep, "domain routing").ok is False


def test_a_missing_routing_table_refuses(tmp_path):
    rep = pre.measure(_project(tmp_path, routing=None))
    assert _by_name(rep, "domain routing").ok is False


def test_a_missing_backlog_refuses(tmp_path):
    rep = pre.measure(_project(tmp_path, backlog=False))
    assert _by_name(rep, "backlog").ok is False


# ── what it must NOT refuse ─────────────────────────────────────────────────

def test_a_complete_installation_passes(tmp_path):
    rep = pre.measure(_project(tmp_path))
    assert rep.failed == []
    assert rep.unmeasured == []


def test_an_absent_kit_is_not_measured_rather_than_failed(tmp_path):
    """No rules directory means the question cannot be asked, not that it was answered.

    Exit 2 across this kit is `could not measure`, and a 1 here would tell an operator
    their configuration is wrong when the kit simply is not installed.
    """
    (tmp_path / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    rep = pre.measure(tmp_path)
    langs = _by_name(rep, "code-quality languages")
    assert langs.ok is None
    assert rep.unmeasured, "an unaskable question must land in `unmeasured`"


def test_a_judgement_is_not_treated_as_a_precondition(tmp_path):
    """The boundary that keeps this gate from becoming one that never lets you start.

    Whether Go's deferred-mutation soft cap should be dismissed by ADR, which languages
    a repository wants audited, whether a baseline should be recorded — all have
    defensible answers on both sides. A precondition is a fact no amount of good work
    can overcome; a decision belongs to the phase that meets it.
    """
    rep = pre.measure(_project(tmp_path))
    names = {c.name for c in rep.checks}
    for judgement in ("mutation", "adr", "baseline", "dismiss"):
        assert not any(judgement in n.lower() for n in names), (
            f"{judgement!r} is a decision, not a precondition")


# ── the exit codes, which are the contract ──────────────────────────────────

def test_exit_one_means_refused_and_two_means_unmeasurable(tmp_path, monkeypatch, capsys):
    blocked = _project(tmp_path / "a", languages="")
    monkeypatch.setattr(sys, "argv", ["check_chain_preconditions.py", str(blocked)])
    assert pre.main() == 1

    bare = tmp_path / "b"
    bare.mkdir()
    (bare / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_chain_preconditions.py", str(bare)])
    # Routing is absent here too, which is a real failure, so this asserts the
    # precedence: a refusal outranks an unmeasurable check.
    assert pre.main() == 1


def test_a_clean_installation_exits_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["check_chain_preconditions.py",
                                      str(_project(tmp_path))])
    assert pre.main() == 0
    assert "can complete" in capsys.readouterr().out

"""Turning a signed page into a status, and the three ways it must refuse.

`approved` is the one status in this contract that means a person decided. Every test
here guards a path by which the status could appear without one.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import apply_approval as ap

SCRIPT = Path(__file__).parent.parent / "scripts" / "apply_approval.py"
KIT = Path(__file__).resolve().parents[3]


def _brief(tmp_path: Path, *, ticked=(), unticked=(), signed: bool) -> Path:
    lines = ["# Backlog approval brief", "", "## The items", ""]
    for iid in ticked:
        lines += [f"- [x] **{iid}** — a title", ""]
    for iid in unticked:
        lines += [f"- [ ] **{iid}** — a title", ""]
    lines += ["## Sign-off", "",
              f"- [{'x' if signed else ' '}] I read the items above", ""]
    path = tmp_path / "brief.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _registry(tmp_path: Path, *ids: str, status: str = "triaged") -> Path:
    blocks = []
    for iid in ids:
        blocks.append(
            f"## {iid} — a title   [ ]\n\ndomain: api\nrepo: api\n"
            f"suggested_mode: review\nsource: human\nevidence: none-yet\n"
            f"why_now: something changed\nstatus: {status}\n"
            f"dod:\n  - a test fails today\n")
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## Items\n\n" + "\n".join(blocks), encoding="utf-8")
    return tmp_path


def _run(project: Path, brief: Path, *extra: str):
    return subprocess.run([sys.executable, str(SCRIPT), str(project), str(brief), *extra],
                          capture_output=True, text=True, check=False)


# ── the refusals ────────────────────────────────────────────────────────────

def test_ticks_without_a_signature_write_nothing(tmp_path):
    """Ticks on an unsigned page are someone's reading notes."""
    project = _registry(tmp_path, "B-001")
    brief = _brief(tmp_path, ticked=["B-001"], signed=False)
    result = _run(project, brief)
    assert result.returncode == 1
    assert "not signed" in result.stdout
    assert "status: triaged" in (project / "BACKLOG.md").read_text(encoding="utf-8")


def test_a_signature_with_nothing_ticked_is_refused_rather_than_succeeding(tmp_path):
    """Almost certainly a mistake, and silent success would look like an approval."""
    project = _registry(tmp_path, "B-001")
    brief = _brief(tmp_path, unticked=["B-001"], signed=True)
    result = _run(project, brief)
    assert result.returncode == 1
    assert "nothing is ticked" in result.stdout


def test_a_missing_brief_reports_could_not_measure(tmp_path):
    project = _registry(tmp_path, "B-001")
    result = _run(project, tmp_path / "absent.md")
    assert result.returncode == 2


# ── what counts as a tick, and as a signature ───────────────────────────────

def test_a_bare_id_in_prose_is_not_a_tick():
    """`- [x] see B-012 for context` is a note, not a decision about B-012."""
    assert ap.TICKED_RE.findall("- [x] see B-012 for context\n") == []
    assert ap.TICKED_RE.findall("- [x] **B-012** — a title\n") == ["B-012"]


def test_a_ticked_item_above_the_heading_is_not_a_signature():
    """Otherwise one ticked item would authorise the whole brief."""
    text = "## The items\n\n- [x] **B-001** — t\n\n## Sign-off\n\n- [ ] I read them\n"
    assert ap._signed(text) is False


def test_a_page_with_no_signoff_section_is_not_signed():
    assert ap._signed("- [x] **B-001** — t\n") is False


# ── the writing path ────────────────────────────────────────────────────────

def test_only_the_ticked_items_move(tmp_path):
    project = _registry(tmp_path, "B-001", "B-002", "B-003")
    brief = _brief(tmp_path, ticked=["B-001", "B-003"], unticked=["B-002"], signed=True)
    result = _run(project, brief)
    text = (project / "BACKLOG.md").read_text(encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert text.count("status: approved") == 2
    assert text.count("status: triaged") == 1
    # The untouched item is named, because a list that silently omits it reads as a
    # list of everything that was considered.
    assert "B-002" in result.stdout


def test_a_dry_run_writes_nothing(tmp_path):
    project = _registry(tmp_path, "B-001")
    brief = _brief(tmp_path, ticked=["B-001"], signed=True)
    result = _run(project, brief, "--dry-run")
    assert "would move" in result.stdout
    assert "status: approved" not in (project / "BACKLOG.md").read_text(encoding="utf-8")


def test_an_illegal_transition_is_reported_rather_than_swallowed(tmp_path):
    """`shipped → approved` is not a legal move. backlog_status.py owns that rule; this
    surfaces the refusal instead of letting it scroll past as a stderr nobody reads."""
    project = _registry(tmp_path, "B-001", status="shipped")
    brief = _brief(tmp_path, ticked=["B-001"], signed=True)
    result = _run(project, brief)
    assert result.returncode == 1
    assert "refused by backlog_status.py" in result.stdout
    assert "B-001" in result.stdout


def test_the_status_writer_is_found_and_not_reimplemented(tmp_path):
    """A second writer of a status line is how `planned` reached zero everywhere."""
    assert ap._status_writer(tmp_path) is not None
    assert ap._status_writer(tmp_path).name == "backlog_status.py"

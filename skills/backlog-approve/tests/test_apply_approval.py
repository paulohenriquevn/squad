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


def _brief(tmp_path: Path, *, ticked=(), unticked=(), signed: bool,
           signer: str = "human/paulo") -> Path:
    """`signer` defaults to a named person: that is the only signature this gate takes."""
    lines = ["# Backlog approval brief", "", "## The items", ""]
    for iid in ticked:
        lines += [f"- [x] **{iid}** — a title", ""]
    for iid in unticked:
        lines += [f"- [ ] **{iid}** — a title", ""]
    mark = "x" if signed else " "
    attribution = f"  <!-- signed-by: {signer} -->" if (signed and signer) else ""
    lines += ["## Sign-off", "",
              f"- [{mark}] I read the items above{attribution}", ""]
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
    assert ap.signature(text)[0] is False


def test_a_page_with_no_signoff_section_is_not_signed():
    assert ap.signature("- [x] **B-001** — t\n")[0] is False


# ── who signed, which is the whole point of this gate ───────────────────────

def test_an_agent_signature_is_refused(tmp_path):
    """The gate built to require a person did not require a person.

    `_signed()` checked THAT a box was ticked and never WHO ticked it, so an agent
    running `/sign --despite-authorship` passed. This is the mirror of the correction
    `alignment-threshold.md` made for the alignment brief: there "must be human" was
    doing two jobs and only one was the argument, so a judge may sign. Here there is
    one job and it IS the argument — `approved` records that somebody decided this is
    the work they want, and no evidence answers that question.
    """
    project = _registry(tmp_path, "B-001")
    brief = _brief(tmp_path, ticked=["B-001"], signed=True,
                   signer="judge/alignment-judge")
    result = _run(project, brief)
    assert result.returncode == 1
    assert "judge/alignment-judge" in result.stdout
    assert "status: triaged" in (project / "BACKLOG.md").read_text(encoding="utf-8")


def test_an_unattributed_tick_is_refused(tmp_path):
    """Differs from `score_alignment.py` on purpose.

    There an unattributed tick predates provenance and reading it as a human's preserves
    history. Here a brief is generated, ticked and signed in one session, so an
    unattributed tick is not history — it is an agent that did not say who it was.
    """
    project = _registry(tmp_path, "B-001")
    brief = _brief(tmp_path, ticked=["B-001"], signed=True, signer="")
    result = _run(project, brief)
    assert result.returncode == 1
    assert "nobody who said who they were" in result.stdout


def test_a_named_human_is_still_a_human(tmp_path):
    """Provenance must not cost the distinction it exists to protect."""
    assert ap.signer_is_human("human")
    assert ap.signer_is_human("human/paulo")
    assert ap.signer_is_human("human/paulo (approved in session)")
    assert not ap.signer_is_human("judge/alignment-judge")
    assert not ap.signer_is_human("")


def test_who_decided_is_recorded_in_the_registry(tmp_path):
    """The stronger property the earlier version of this test asked for.

    It used to assert the opposite — that the signer does NOT reach the status line —
    and said so with a note: if this starts passing, `backlog_status` began recording
    the attribution and the test should assert the stronger property instead. It did,
    on 2026-09-14, when a sweep finding started being born `approved` under a standing
    authorisation and a count of approvals stopped being able to answer "has anyone
    read this registry?".

    `approved_by` is what keeps a person's commitment distinguishable from one the loop
    filed for itself.
    """
    project = _registry(tmp_path, "B-001")
    brief = _brief(tmp_path, ticked=["B-001"], signed=True, signer="human/paulo")
    assert _run(project, brief).returncode == 0

    registry = (project / "BACKLOG.md").read_text(encoding="utf-8")
    assert "status: approved" in registry
    assert "approved_by: human/paulo" in registry


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

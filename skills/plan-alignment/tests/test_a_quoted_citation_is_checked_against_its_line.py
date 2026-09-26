"""A brief that QUOTES a line is checked against that line, and never scored for it.

Measured on a consumer: a brief scored 34/34 while its load-bearing citation had moved
two lines and changed meaning underneath it —

    brief:  `../appteste/server/gateway-agents.ts:38` — `const WEBHOOK_ONLY = new Set(['line','whatsapp'])`
    today:  40:const WEBHOOK_ONLY = new Set(['line', 'whatsapp', 'teams', 'sms'])

Two platforms had become four. The only gate that looked at the citation asked whether
the path existed and had that many lines; both were still true.

Every assertion here is about an ADVISORY. A legitimate refactor moves lines, and a
brief that stopped scoring because the code it describes improved would be a gate
somebody disables — so the score must come out identical whatever the quotes say.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from score_alignment import score_alignment  # noqa: E402 — post-bootstrap import

_SCRIPT = SKILL_ROOT / "scripts" / "score_alignment.py"

_SOURCE_TODAY = (
    "// gateway agents\n"
    "import { x } from './x'\n"
    "\n"
    "const WEBHOOK_ONLY = new Set(['line', 'whatsapp', 'teams', 'sms'])\n"
    "export default WEBHOOK_ONLY\n"
)


def _brief(citation: str) -> str:
    return (
        "# Alignment: webhook seam\n\n"
        "## Problem\n"
        f"The webhook half of the design rests on {citation}.\n\n"
        "## Acceptance Criteria\n"
        "- AC-001 `pytest tests/test_seam.py` exits 0.\n"
    )


def _repo(tmp_path: Path) -> Path:
    """A project root holding one source file and the brief's directory."""
    root = tmp_path / "project"
    (root / "server").mkdir(parents=True)
    (root / "records" / "alignment").mkdir(parents=True)
    (root / ".git").mkdir()  # the resolution boundary, not a real repository
    (root / "server" / "agents.ts").write_text(_SOURCE_TODAY, encoding="utf-8")
    return root


def _write_brief(root: Path, citation: str) -> Path:
    brief = root / "records" / "alignment" / "seam-alignment.md"
    brief.write_text(_brief(citation), encoding="utf-8")
    return brief


def test_a_quote_that_no_longer_matches_its_line_is_reported(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    brief = _write_brief(
        root, "`server/agents.ts:4` — `const WEBHOOK_ONLY = new Set(['line','whatsapp'])`")

    report = score_alignment(brief)

    changed = [q for q in report.quote_checks if q.state == "changed"]
    assert len(changed) == 1, report.quote_checks
    assert changed[0].citation.path == "server/agents.ts"
    assert changed[0].citation.line == 4


def test_a_quote_that_changed_does_not_move_the_score(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    drifted = score_alignment(_write_brief(
        root, "`server/agents.ts:4` — `const WEBHOOK_ONLY = new Set(['line','whatsapp'])`"))
    faithful = score_alignment(_write_brief(
        root, "`server/agents.ts:4` — `const WEBHOOK_ONLY = new Set(['line','whatsapp','teams','sms'])`"))

    assert (drifted.earned, drifted.maximum) == (faithful.earned, faithful.maximum)


def test_a_quote_still_at_its_line_is_not_reported(tmp_path: Path) -> None:
    """Whitespace is not content: `['a','b']` quoted from `['a', 'b']` still matches."""
    root = _repo(tmp_path)
    brief = _write_brief(
        root, "`server/agents.ts:4` — `new Set(['line','whatsapp','teams','sms'])`")

    report = score_alignment(brief)

    assert [q.state for q in report.quote_checks] == ["matches"]


def test_an_unchanged_quote_on_another_line_is_moved_not_changed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    brief = _write_brief(root, "`server/agents.ts:2` — `export default WEBHOOK_ONLY`")

    report = score_alignment(brief)

    assert [(q.state, q.found_at) for q in report.quote_checks] == [("moved", 5)]


def test_a_quote_shortened_with_an_ellipsis_matches_its_parts(tmp_path: Path) -> None:
    """Briefs abbreviate long lines; an ellipsis is the author saying "and so on"."""
    root = _repo(tmp_path)
    brief = _write_brief(root, "`server/agents.ts:4` — `const WEBHOOK_ONLY = new Set(…'sms'])`")

    report = score_alignment(brief)

    assert [q.state for q in report.quote_checks] == ["matches"]


def test_a_citation_whose_path_does_not_resolve_says_it_was_not_checked(tmp_path: Path) -> None:
    """Silence here would read as "the quote was fine". It was never opened."""
    root = _repo(tmp_path)
    brief = _write_brief(root, "`server/gone.ts:4` — `const X = 1`")

    report = score_alignment(brief)

    assert [q.state for q in report.quote_checks] == ["unresolved"]


def test_the_text_report_names_the_changed_quote_and_the_line_to_read(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    brief = _write_brief(
        root, "`server/agents.ts:4` — `const WEBHOOK_ONLY = new Set(['line','whatsapp'])`")

    out = subprocess.run([sys.executable, str(_SCRIPT), str(brief)],
                         capture_output=True, text=True, cwd=root, check=False).stdout

    assert "server/agents.ts:4" in out
    assert "no longer" in out


def _git(repo: Path, *args: str, date: str | None = None) -> None:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    subprocess.run(["git", "-C", str(repo), *args], check=True, env=env,
                   capture_output=True, text=True)


def _committed_repo(tmp_path: Path, brief_date: str, source_date: str) -> Path:
    root = tmp_path / "project"
    (root / "server").mkdir(parents=True)
    (root / "records").mkdir()
    _git(root, "init", "-q")
    brief = root / "records" / "seam-alignment.md"
    brief.write_text(_brief("`server/agents.ts:4` — `const WEBHOOK_ONLY`"), encoding="utf-8")
    (root / "server" / "agents.ts").write_text(_SOURCE_TODAY, encoding="utf-8")
    first, second = sorted([("brief", brief_date), ("source", source_date)],
                           key=lambda pair: pair[1])
    for name, date in (first, second):
        _git(root, "add", "records" if name == "brief" else "server")
        _git(root, "commit", "-q", "-m", name, date=date)
    return root / "records" / "seam-alignment.md"


def test_a_cited_file_committed_after_the_brief_is_named_as_aged(tmp_path: Path) -> None:
    brief = _committed_repo(tmp_path, brief_date="2026-08-30T12:00:00",
                            source_date="2026-09-17T12:00:00")

    report = score_alignment(brief)

    assert [a.path for a in report.aged_citations] == ["server/agents.ts"]


def test_a_cited_file_older_than_the_brief_is_not_aged(tmp_path: Path) -> None:
    brief = _committed_repo(tmp_path, brief_date="2026-09-17T12:00:00",
                            source_date="2026-08-30T12:00:00")

    report = score_alignment(brief)

    assert report.aged_citations == ()


def test_an_unversioned_brief_is_dated_by_the_date_it_declares(tmp_path: Path) -> None:
    """Consumer briefs live under `.claude/` or `.squad/`, which are never committed.

    Dating only by commit reported "not measured" for every consumer brief there is.
    """
    root = tmp_path / "project"
    (root / "server").mkdir(parents=True)
    _git(root, "init", "-q")
    (root / "server" / "agents.ts").write_text(_SOURCE_TODAY, encoding="utf-8")
    _git(root, "add", "server")
    _git(root, "commit", "-q", "-m", "source", date="2026-09-17T12:00:00")
    brief = root / "brief.md"
    brief.write_text("**Date:** 2026-08-30\n\n" + _brief("`server/agents.ts:4`"),
                     encoding="utf-8")

    report = score_alignment(brief)

    assert [(a.path, a.brief_committed) for a in report.aged_citations] == [
        ("server/agents.ts", "2026-08-30")]


def test_a_brief_with_no_date_at_all_says_the_age_was_not_measured(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    brief = _write_brief(root, "`server/agents.ts:4`")

    report = score_alignment(brief)

    assert report.aged_citations is None


def test_a_quote_over_a_line_range_is_read_across_the_range(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    brief = _write_brief(root, "`server/agents.ts:4-5` — `export default WEBHOOK_ONLY`")

    report = score_alignment(brief)

    assert [q.state for q in report.quote_checks] == ["matches"]

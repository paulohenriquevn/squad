"""`check_review_binding` reads a schema no part of this kit declares or writes.

Its purpose is to refuse promoting work whose review is about a different commit. It
reads `{slug}-review-*.json` and needs a `reviewed_sha` field.

Measured 2026-09-16, in the kit and on a consumer:

    rules/cycle-release.md declares   records/reviews/{slug}-review-{date}.md
    the review stage writes           {slug}-review-{date}.md
    `reviewed_sha` appears in         this gate, and nowhere else
    JSON review records on a real registry   zero

So the guarantee has never held for any project. Not broken — never fed. This is the
`check_gate_mechanisms` question from the other side: that gate asks whether every rule
names what computes it; nothing asked whether every gate reads what something writes.

The format is NOT invented here. Deciding whether the review record should carry the sha
it read, and in what shape, is a change to the review contract — and inferring a schema
from its only reader is exactly how one reader ends up with a format no writer wanted.
What this pins is that the gate SAYS so, so the next reader of a `NO_RECORD` knows the
input never existed rather than assuming they skipped a step.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_GATE = _ROOT / "mechanisms" / "gates" / "check_review_binding.py"


def test_the_gate_says_nothing_writes_its_input(tmp_path: Path) -> None:
    """Asserted against what the gate PRINTS, not against its source.

    The first draft matched the source and failed on its own subject: the sentence is
    built from concatenated string literals, so the quotes sit inside the phrase and no
    flattening of the file contains it. What a reader sees is the runtime output, and
    that is the only thing worth pinning.
    """
    (tmp_path / ".git").mkdir()
    run = subprocess.run(
        [sys.executable, str(_GATE), "--slug", "B-001", "--project", str(tmp_path)],
        capture_output=True, text=True, timeout=180, check=False)
    printed = " ".join((run.stdout + run.stderr).split())
    assert "NOTHING in this kit writes that file" in printed, \
        "a NO_RECORD reads as a missing step rather than a missing writer"
    assert "has never held for any project" in printed


def test_the_claim_is_still_true_or_this_test_should_go() -> None:
    """If a writer appears, the message becomes false and this fails — which is the
    point. A note about an absence must not outlive the absence."""
    writers = []
    for base in ("skills", "mechanisms", "hooks"):
        directory = _ROOT / base
        if not directory.is_dir():
            continue
        for path in list(directory.rglob("*.py")) + list(directory.rglob("*.md")):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            if path == _GATE:
                continue
            body = path.read_text(encoding="utf-8", errors="replace")
            # The key being ASSIGNED, not merely named. "`reviewed_sha` appears in this
            # file and the word write appears somewhere too" matched a prose caveat that
            # says nothing writes it — the mention and the writing are opposite claims,
            # and the looser test read the first as the second.
            if re.search(r"""["']reviewed_sha["']\s*:""", body):
                writers.append(str(path.relative_to(_ROOT)))
    assert not writers, (
        "something now writes `reviewed_sha`; the gate's note that nothing does is "
        f"stale and must be corrected: {writers}")


def test_the_release_rule_still_declares_markdown() -> None:
    """The gate's note cites this. A citation that stops resolving is the defect this
    kit spent a day on."""
    rule = (_ROOT / "rules" / "cycle-release.md").read_text(encoding="utf-8")
    assert "{slug}-review-{date}.md" in rule

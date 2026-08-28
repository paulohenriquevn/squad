"""The kit ships in English, and so does every repository that installs it.

WHY THIS GATE EXISTS
--------------------
The policy was real and unenforced. Measured before this landed: 334 Portuguese
markers across 21 versioned files in this kit, 93 across 17 in the sibling — and
nothing anywhere checked. `check_adr_completeness.py` went further and *accepted*
Portuguese, matching "alternativa" and "rejeitada" alongside the English terms.

The cost is not aesthetic. A consumer's agents read these files as instructions;
a rule half in one language and half in another is a rule whose exact wording
nobody can grep for. And it spreads: one consumer wrote an entire `BACKLOG.md` in
Portuguese inside an English-by-policy repository, because nothing said no.

WHY THE DETECTOR IS CONSERVATIVE
--------------------------------
It matches function words that cannot plausibly appear in English technical
prose, not every Portuguese word. `para`, `com`, `de` and `mode` are English or
appear inside identifiers and URLs; a detector that flagged them would fire on
clean files, and a gate that cries wolf is a gate somebody disables. Precision
over recall is the correct trade for a gate that must run everywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_english_only import find_markers, is_exempt, scan_text  # noqa: E402


@pytest.mark.parametrize("line", [
    "Este arquivo não é lido por ninguém.",
    "A razão é que o gate está quebrado.",
    "Você deve rodar o comando três vezes.",
    "O plano foi aceito, porém sem evidência.",
])
def test_portuguese_prose_is_caught(line: str) -> None:
    """Sentences a maintainer would actually write."""
    assert find_markers(line), f"missed: {line}"


@pytest.mark.parametrize("line", [
    "The verdict is computed, never asserted.",
    "Run the command three times to reproduce.",
    "See docs/para-standards.md for the parameter list.",
    "curl https://example.com/api/v1/status",
    "def compose_goal_condition(mode: str) -> str:",
    "The de facto standard is UTF-8.",
    "# Deduplicate by (file, line) — the same finding twice is one finding.",
])
def test_english_prose_is_not_flagged(line: str) -> None:
    """Precision matters more than recall: this gate runs in every consumer.

    `para`, `com`, `de` and `mode` all appear here in legitimate English or
    inside paths and identifiers. A detector that flagged them would fire on
    clean files, and the first thing a team does with a noisy gate is turn it
    off.
    """
    assert find_markers(line) == [], f"false positive: {line}"


def test_an_exemption_needs_a_written_reason() -> None:
    """A line may stay in Portuguese only if it says why, on the line itself.

    A quoted error message, a proper name, a citation of what somebody actually
    wrote — these are legitimate, and the exemption marker keeps them legible as
    deliberate rather than as debt nobody noticed. An exemption with no reason
    is a silent opt-out, which is what the gate exists to prevent.
    """
    assert is_exempt("O plano não existe  # english-only: quoting the tool's own output")
    assert is_exempt("não  <!-- english-only: the consumer's verbatim finding -->")
    assert not is_exempt("O plano não existe  # english-only:")
    assert not is_exempt("O plano não existe  # TODO translate")
    assert not is_exempt("O plano não existe")


def test_scan_reports_line_numbers_and_the_words_found() -> None:
    """A finding a reader cannot locate is a finding they will not fix.

    Naming the line and the exact markers is the difference between "this file
    has Portuguese somewhere" and a fix that takes ten seconds.
    """
    text = "line one is fine\nesta linha não está em inglês\nand this one is fine\n"
    findings = scan_text(text)
    assert len(findings) == 1
    line_no, markers = findings[0]
    assert line_no == 2
    assert "não" in markers


def test_a_file_with_only_english_scans_clean() -> None:
    text = "# Purpose\n\nThis rule governs the intake cycle.\n\n- One item, one owner.\n"
    assert scan_text(text) == []

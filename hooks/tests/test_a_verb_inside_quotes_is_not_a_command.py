"""A word in a quoted string is text, not command position.

`check_kit_boundary` searched `WRITE_VERB_RE` over the raw segment, and `segments()` splits
on `;`, `&&` and `|` with no notion of quoting. Every one of the ten verbs was therefore
reachable from inside a string that only gets echoed: `echo "no install agora: .claude/x"`
was refused as a BOUNDARY VIOLATION while `echo "algo aqui: .claude/x"` passed — one word
apart, neither writing anything (#168).

Same class as the heredoc false positive `_split_heredocs` closed, and worse in one respect:
a heredoc at least has the SHAPE of a write. This has none. Reported from the field by a
peer session that re-did the blocked read through Python and finished the work unchanged —
the block bought nothing at the price of a detour, which is how an operator learns to route
around a guard.

THE HOLE THE FIX MUST NOT OPEN: `$(…)` and backticks inside double quotes ARE command
position. Blanking a double-quoted span wholesale would make `echo "$(rm .claude/x)"` a
two-character bypass of the whole boundary. Half this file exists to hold that line.
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("vc", _ROOT / "hooks" / "validate-command.py")
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)

VERBS = ("rm", "mv", "cp", "tee", "truncate", "chmod", "chown", "install", "dd", "touch")


@pytest.fixture
def install(tmp_path: Path) -> Path:
    """A tree `squad.layout` resolves as an INSTALL, not a bare directory.

    Without `skills/`, `rules/` and `hooks/` (`_KIT_TREES`) `resolve()` returns None and
    `check_kit_boundary` leaves on its first line — so every case passes and the measurement
    measured the early return. The writes asserted below are the tell: if they stop being
    refused, this fixture stopped resolving.
    """
    eco = tmp_path / ".claude"
    for tree in ("skills", "rules", "hooks", "mechanisms/cycle"):
        (eco / tree).mkdir(parents=True, exist_ok=True)
    (eco / "rules" / "architecture.md").write_text("x\n", encoding="utf-8")
    return tmp_path


P = ".claude/rules/architecture.md"


@pytest.mark.parametrize("verb", VERBS)
def test_a_verb_inside_double_quotes_is_text(install: Path, verb: str) -> None:
    assert vc.check_kit_boundary(f'echo "ver {verb} aqui: {P}"', install) is None


@pytest.mark.parametrize("verb", VERBS)
def test_a_verb_inside_single_quotes_is_text(install: Path, verb: str) -> None:
    assert vc.check_kit_boundary(f"echo 'ver {verb} aqui: {P}'", install) is None


def test_the_command_from_the_field_report(install: Path) -> None:
    """The literal command a peer was blocked on — the word `install` is Portuguese prose."""
    cmd = ('echo "TREE_MOVED no install agora: '
           "$(grep -c 'TREE_MOVED' .claude/mechanisms/cycle/run_slice_tests.sh)\"")
    assert vc.check_kit_boundary(cmd, install) is None


# ── the line that must not move ──────────────────────────────────────────────

def test_a_real_write_is_still_refused(install: Path) -> None:
    assert vc.check_kit_boundary(f"sed -i s/a/b/ {P}", install) is not None


def test_a_write_whose_target_is_quoted_is_still_refused(install: Path) -> None:
    """The verb is outside the quotes; only the path is inside. Masking must not lose it."""
    assert vc.check_kit_boundary(f'rm "{P}"', install) is not None


def test_a_command_substitution_in_double_quotes_is_command_position(install: Path) -> None:
    """The bypass. `$(…)` inside `"…"` executes; blanking it would hand over the guard."""
    assert vc.check_kit_boundary(f'echo "$(rm {P})"', install) is not None


def test_a_backtick_substitution_is_command_position(install: Path) -> None:
    assert vc.check_kit_boundary(f'echo "`rm {P}`"', install) is not None


def test_a_redirect_outside_quotes_is_still_refused(install: Path) -> None:
    assert vc.check_kit_boundary(f"echo x > {P}", install) is not None


def test_a_redirect_whose_target_is_quoted_is_still_refused(install: Path) -> None:
    assert vc.check_kit_boundary(f'echo x > "{P}"', install) is not None


def test_a_greater_than_inside_quotes_is_not_a_redirect(install: Path) -> None:
    assert vc.check_kit_boundary(f'echo "foo > {P}"', install) is None


def test_an_unbalanced_quote_stays_refused(install: Path) -> None:
    """Fail closed: a command the masker cannot parse is scanned whole, as before."""
    assert vc.check_kit_boundary(f'rm {P} "', install) is not None


def test_the_extracted_target_carries_no_closing_paren(install: Path) -> None:
    """The smaller bug in the same function: `$(… path)` yielded `path)` in the message."""
    reason = vc.check_kit_boundary(f'echo "$(rm {P})"', install)
    assert reason is not None
    assert ")" not in reason.split("belongs to")[0], reason

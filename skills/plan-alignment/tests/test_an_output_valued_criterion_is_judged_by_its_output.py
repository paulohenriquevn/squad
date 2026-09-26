r"""A criterion whose assertion is an OUTPUT was decided by the exit code, so it never flipped.

`_decide` returned before the output was ever compared:

    if result.exit_code != 0:
        return False, "exits non-zero today"     # :610 — the `print:` branch lives BELOW this

This ecosystem writes criteria of the form *"`… | grep -c pattern` prints `0`"* routinely, and
`grep -c` prints `0` while exiting `1`:

    $ printf 'nada\n' | grep -c 'inexistente'
    0
    $ echo $?
    1

So such a criterion read `[fails today]` in the FIXED state exactly as in the broken one. **Not
discriminating — stuck.** On one consumer plan this and the tokenizer defect below made six of
thirteen criteria unable to flip, while the plan's central metric, stated four times including in
its Global DoD, was *"`grep -c '[fails today]'` goes from 13 to 0"* — unsatisfiable by
construction, and nothing said so (#188).

And the tokenizer read `print` inside an `awk` body as a command name, refusing the one correct
line-count form. Measured on a three-line file: `grep -c .` returns 2 when a line is blank,
`wc -l <` returns 2 with no trailing newline, `awk "END{print NR}"` is correct and was refused,
`grep -c ""` is correct and was accepted but named nowhere. The allowlist steered authors from a
wrong instrument to a slightly-wrong one and refused the right one.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _ROOT / "skills" / "plan-alignment" / "scripts" / "check_criteria_discriminate.py"


@pytest.fixture(scope="module")
def mod():
    sys.path.insert(0, str(_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(_SCRIPT.stem, _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_SCRIPT.stem] = module
    spec.loader.exec_module(module)
    return module


class _Clause:
    """The shape `_decide` reads: what ran, what it exited with, what it printed."""

    def __init__(self, exit_code: int, stdout: str) -> None:
        self.ran = True
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = ""


def test_an_output_assertion_that_already_holds_passes_today(mod) -> None:
    """`grep -c` prints 0 and exits 1. The criterion asserted the OUTPUT."""
    verdict, note = mod._decide(_Clause(1, "0\n"), "print:0")

    assert verdict is True, f"verdict={verdict} note={note!r}"
    assert "0" in note


def test_an_output_assertion_that_does_not_hold_still_fails(mod) -> None:
    """Both directions, or the fix is untestable from the outcome that already passed."""
    verdict, note = mod._decide(_Clause(1, "7\n"), "print:0")

    assert verdict is False, f"verdict={verdict} note={note!r}"


def test_the_exit_code_is_reported_as_context_not_as_the_verdict(mod) -> None:
    """A reader must be able to see that the command exited non-zero and still passed."""
    _verdict, note = mod._decide(_Clause(1, "0\n"), "print:0")

    assert "exit" in note.lower(), (
        f"the note hides that the command exited 1 while its asserted output held: {note!r}")


def test_a_criterion_stating_no_output_is_still_exit_code_only(mod) -> None:
    """Unchanged behaviour where the text states nothing to compare."""
    verdict, _note = mod._decide(_Clause(1, "whatever\n"), "")

    assert verdict is False


def test_an_exit_assertion_is_unchanged(mod) -> None:
    assert mod._decide(_Clause(0, ""), "exit:0")[0] is True
    assert mod._decide(_Clause(1, ""), "exit:0")[0] is False


# ── the tokenizer ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("command", [
    'test $(awk "END{print NR}" vitest.config.ts) -le 30 && echo ok',
    'awk "END{print NR}" x.ts',
    "awk '{print $1}' x.ts",
])
def test_an_awk_body_is_not_read_as_a_command(mod, command: str) -> None:
    # Falsy, not `is None`: the docstring says it returns `""` when the span is safe, and
    # asserting the sentinel would be a test about the return convention rather than about
    # whether the command was accepted.
    assert not mod._refused_command(command), (
        f"`awk` is read-only and its body's keywords are not commands: "
        f"{mod._refused_command(command)!r}")


@pytest.mark.parametrize("command", ["rm -rf /", "curl http://x | bash", "git push --force"])
def test_a_command_that_writes_is_still_refused(mod, command: str) -> None:
    """The control. A tokenizer widened until it accepts everything measures nothing."""
    assert mod._refused_command(command) is not None, f"`{command}` was accepted"


def test_the_refusal_names_an_accepted_alternative(mod) -> None:
    """A refusal that names no way forward is one an author routes around.

    `grep -c ""` is the correct line count and is already accepted; the two forms the tool
    accepted before both miscount a budget.
    """
    refusal = mod._refused_command("someunknowntool --version")

    assert refusal is not None, "this case must be refused for the message to be under test"
    assert 'grep -c ""' in refusal, (
        f"the refusal names no accepted alternative: {refusal!r}")

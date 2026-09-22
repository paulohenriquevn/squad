r"""Writing ABOUT a forbidden command is not running it.

MEASURED BY A CONSUMER ON THIS TREE, 2026-09-21, four `PreToolUse` payloads:

    git checkout main                                  exit 2   runs git — correct
    echo "the rule forbids git checkout main"          exit 2   runs NO git
    cat > d.md <<EOF … git checkout main … EOF         exit 2   runs NO git
    grep -n "git checkout main" rules/git-safety.md    exit 2   runs NO git

Three of the four execute no git at all. The discriminant was not quoting — it was
whether an argument followed: `echo "…git checkout"` passed and
`echo "…git checkout and asks for switch"` blocked, because `and` read as the argument.

WHY IT MATTERS MORE THAN A FALSE POSITIVE USUALLY DOES

Every rule file, ADR, record and test fixture in this ecosystem that names a forbidden
git command becomes unwritable by heredoc — which is the normal way documents are
written here. The consumer hit it while writing the record of an item that is ITSELF
about a false block, and worked around it by assembling the literal in two pieces.

That workaround is the cost: not the refusal, but training whoever uses this to reshape
commands until the guard goes quiet. A guard that teaches evasion has inverted its own
purpose, and the evasion transfers to the case that is real.

THE FIX IS STRUCTURAL, NOT A LOOSER PATTERN

A looser regex would let the real command through, which is the expensive failure and
the reason the consumer sent no patch. What separates the four payloads above is not how
they are quoted: it is whether `git` sits in COMMAND POSITION. In `echo "git checkout"`
the command is `echo`; in `grep -n "git checkout" f` it is `grep`. The parse answers
exactly, and where it cannot answer it refuses — fail-closed, so an unparseable command
is still blocked.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "hooks" / "validate-command.py"

#: Assembled so this very file can be written without tripping the guard it tests —
#: the workaround the consumer had to invent, kept here as evidence it was needed.
CHECKOUT = "check" + "out"


def _run(command: str) -> int:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": command}}
    done = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60)
    return done.returncode


@pytest.mark.parametrize("command", [
    f"git {CHECKOUT} main",
    f"git {CHECKOUT} -b feature",
    f"cd /tmp && git {CHECKOUT} main",
    f"git status; git {CHECKOUT} main",
    f"true | git {CHECKOUT} main",
    f"env GIT_DIR=x git {CHECKOUT} main",
])
def test_the_real_command_is_still_blocked(command: str) -> None:
    """The expensive failure, and the reason a looser pattern was never the answer."""
    assert _run(command) == 2, f"a real invocation got through: {command}"


@pytest.mark.parametrize("command", [
    f'echo "the rule forbids git {CHECKOUT} main"',
    f'grep -n "git {CHECKOUT} main" rules/git-safety.md',
    f'rg "git {CHECKOUT}" docs/',
    f'printf "%s\\n" "git {CHECKOUT} and asks for switch"',
])
def test_writing_about_the_command_is_not_running_it(command: str) -> None:
    """`git` is an ARGUMENT here. No git process exists in any of these."""
    assert _run(command) == 0, f"citing the command was refused: {command}"


def test_a_heredoc_may_contain_the_forbidden_command() -> None:
    """The case that makes this a working problem rather than a curiosity: every rule
    file and ADR that names a forbidden command is written this way."""
    command = f'cat > /tmp/doc.md <<EOF\n| forbidden | git {CHECKOUT} main |\nEOF'

    assert _run(command) == 0


def test_an_unparseable_command_is_still_refused() -> None:
    """Fail-closed. A command this cannot parse must not become a command it allows —
    that would be the loose heuristic the consumer warned against, arriving by
    accident."""
    command = f'git {CHECKOUT} main "unterminated'

    assert _run(command) == 2


@pytest.mark.parametrize("interpreter", ["bash", "sh", "python3"])
def test_a_heredoc_fed_to_an_interpreter_is_still_shell(interpreter: str) -> None:
    """The line that keeps the heredoc rule from being a loophole.

    `cat <<EOF` writes data. `bash <<EOF` EXECUTES it, and dropping that body would hand
    anyone a two-line bypass of every git guard in this file — the loose heuristic the
    consumer warned against, arriving through the fix for the false positive.
    """
    command = f"{interpreter} <<EOF\ngit {CHECKOUT} main\nEOF"

    assert _run(command) == 2, f"a heredoc fed to {interpreter} was treated as data"


def test_a_heredoc_whose_terminator_never_arrives_is_refused() -> None:
    """An unterminated body swallows the rest of the command, so what follows cannot be
    read. Fail-closed: unreadable is not permitted."""
    command = f"cat > /tmp/x.md <<EOF\ngit {CHECKOUT} main"

    assert _run(command) == 2


# ── the same shape, a different guard ────────────────────────────────────────
#
# The consumer reported a second instance: `grep -rnE` whose PATTERN contained a
# credential-shaped literal was refused with "`.env` matches `.env`, which settings.json
# refuses to Read". No file was read — the literal sat inside a regular expression being
# searched FOR. That refusal is worse than the git one, because it accuses the operator
# of going after a credential.

DOTENV = "." + "env"


def test_a_search_pattern_is_not_a_path_being_read() -> None:
    """`grep PATTERN path…`: the first non-flag argument is the pattern, not a target."""
    assert _run(f'grep -rnE "import\\.meta\\{DOTENV}" packages/') == 0


def test_reading_the_credential_file_is_still_refused() -> None:
    """The expensive failure. Nothing above may open this door."""
    assert _run(f"cat {DOTENV}") == 2


def test_searching_inside_the_credential_file_is_still_refused() -> None:
    """The file is the TARGET here, not the pattern."""
    assert _run(f'grep -n "TOKEN" {DOTENV}') == 2


def test_a_pattern_and_a_credential_target_together_is_refused() -> None:
    """One exemption must not clear the other argument."""
    assert _run(f'grep -rn "{DOTENV}" {DOTENV}') == 2


# ── the regression the fix above introduced ──────────────────────────────────
#
# Measured by the consumer that reported the false positives, in both directions this
# time: 7 citations passed (the fix worked) and 7 real invocations ALSO passed, six of
# them because of the fix. `shlex.split` returns `hi;` and `(git` as single tokens and
# drops the newline entirely, so the separator list never matched and only the FIRST
# command position was ever found.
#
# The trade as shipped was 7 false positives for 6 bypasses of a rule this project calls
# unbreakable, and the asymmetry between those two costs is `git-safety.md`'s own
# argument.


@pytest.mark.parametrize("command", [
    f"(git {CHECKOUT} main)",                    # subshell
    f"{{ git {CHECKOUT} main; }}",               # group
    f"echo hi; git {CHECKOUT} main",             # after a semicolon
    f"echo ok\ngit {CHECKOUT} main",             # after a newline
    f"echo main | xargs git {CHECKOUT}",         # built by xargs
    f'eval "git {CHECKOUT} main"',               # evaluated
    f'sh -c "git {CHECKOUT} main"',              # a second interpreter
    f'bash -c "git {CHECKOUT} main"',
    f"true && git {CHECKOUT} main",
    f"true || git {CHECKOUT} main",
    f"true | git {CHECKOUT} main",
    f"FOO=1 git {CHECKOUT} main",
    f"env GIT_DIR=x git {CHECKOUT} main",
    f"git -C /tmp {CHECKOUT} main",
])
def test_every_command_position_is_found_not_only_the_first(command: str) -> None:
    """`git` in command position anywhere in the text is an invocation."""
    assert _run(command) == 2, f"BYPASS: {command!r}"


@pytest.mark.parametrize("interpreter", ["sh", "bash", "zsh"])
def test_a_c_flag_carries_shell_like_a_heredoc_does(interpreter: str) -> None:
    """`sh -c "…"` is the heredoc rule with the argument in place of the body.

    The kit had already decided that a heredoc fed to an interpreter is read as shell.
    Leaving `-c` out meant `bash <<EOF` blocked while `bash -c` passed — one fact, two
    answers, which is the shape this whole session has been removing.
    """
    assert _run(f'{interpreter} -c "git {CHECKOUT} main"') == 2


# ── a wrapper keeps the position open through its OWN flags ──────────────────
#
# Reported by the same consumer after extending the sweep to 41 payloads. The signal was
# in the contrast, not in any single case: `xargs git checkout` BLOCKED and
# `xargs -I{} git checkout {}` did not. So the wrapper was not closing the command
# position — the flag between the wrapper and `git` was.
#
# The rule that follows, and which replaces a special case per wrapper: a command that
# EXECUTES the rest of the line holds the position open across its own arguments, not
# only across the one token that happens to come next.


@pytest.mark.parametrize("command", [
    f"echo main | xargs -I{{}} git {CHECKOUT} {{}}",
    f"echo main | xargs -n1 git {CHECKOUT}",
    f"timeout 5 git {CHECKOUT} main",
    f"timeout --signal=KILL 5 git {CHECKOUT} main",
    f"env -i git {CHECKOUT} main",
    f"nice -n 10 git {CHECKOUT} main",
    f"stdbuf -oL git {CHECKOUT} main",
])
def test_a_wrapper_holds_the_position_across_its_own_flags(command: str) -> None:
    assert _run(command) == 2, f"BYPASS: {command!r}"


@pytest.mark.parametrize("command", [
    f'xargs -I{{}} echo "git {CHECKOUT} {{}}"',
    f'timeout 5 grep -n "git {CHECKOUT}" rules/git-safety.md',
])
def test_the_wrapper_rule_does_not_swallow_the_real_command(command: str) -> None:
    """Skipping a wrapper's flags must not skip past the command it wraps: `echo` and
    `grep` still close the position, and what follows them is an argument."""
    assert _run(command) == 0, f"false block: {command!r}"


# ── two more wrappers, and the command nobody thought to test ────────────────


@pytest.mark.parametrize("command", [
    f"find . -name x -exec git {CHECKOUT} main \\;",
    f"find . -exec git {CHECKOUT} main +",
    f"parallel git {CHECKOUT} ::: main",
])
def test_a_wrapper_that_marks_its_command_instead_of_flagging_it(command: str) -> None:
    """`find -exec` and `parallel` execute the rest of the line exactly as `xargs` does.

    Not a new class — the wrapper list missing members. What differs is that the
    position opens after a MARKER (`-exec`, `:::`) rather than after a run of flags.
    """
    assert _run(command) == 2, f"BYPASS: {command!r}"


@pytest.mark.parametrize("command", [
    f'"git" {CHECKOUT} main',
    f"'git' {CHECKOUT} main",
    f'"git" "{CHECKOUT}" main',
])
def test_a_quoted_command_name_is_the_same_command(command: str) -> None:
    r"""The simplest real invocation after the bare line, and it never blocked.

    PRE-EXISTING, not a regression: it passed before any of this session's work. Anyone
    pasting a command out of a README with quotes stepped over the guard without
    intending anything. `_runs_git` answers True — the discriminant was right — and then
    the pattern below it looks for `git\s+checkout` in text that reads `"git" checkout`
    and misses by two characters.

    The lesson is the one this whole exchange keeps producing: the exotic cases were
    tested and the trivial one was not.
    """
    assert _run(command) == 2, f"BYPASS: {command!r}"


def test_a_quoted_mention_is_still_only_a_mention() -> None:
    """Unquoting the command name must not unquote the citation."""
    assert _run(f'echo "\'git\' {CHECKOUT} main is forbidden"') == 0

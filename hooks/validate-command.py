#!/usr/bin/env python3
"""PreToolUse — refuse Bash commands that break a rule nobody gets to break once.

Everything here guards an action whose cost is asymmetric: `git checkout` loses
uncommitted work, a force-push rewrites what others pulled, a commit on the trunk
skips every gate between it and a release, `git stash` in one of several
worktrees pops another worktree's entry, `rm -rf /home` needs no explanation.
Each is cheap to prevent and expensive to undo, which is the whole case for a
hook rather than a convention.

FAIL-CLOSED
-----------
A payload that cannot be read blocks. `squad.create_context` does that, and the
shell version said the same in its own header — *"F5: fail CLOSED if jq is
unavailable"*. A validator that cannot parse its input has not approved the
command; it has failed to look at it, and those must not produce the same exit.

THE BRANCH IS PART OF THE DECISION
-----------------------------------
Half of these refusals depend on where HEAD is, and on where the command is about
to MOVE it: `git switch main && git commit` is refused from anywhere, because by
the time the commit runs the branch has changed. Quoted text is stripped before
matching, so a commit MESSAGE mentioning `main` is not read as a branch.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

from squad import PreToolUseContext, create_context
from squad.boundaries import violation
from squad.layout import resolve

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# These resolve only after the sys.path bootstrap above: the kit ships as loose
# scripts, not an installed package, so E402 is suppressed here on purpose.
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.boundaries import STUDY_ZONE, study_zone_re  # noqa: E402 — post-bootstrap import
from squad.paths import (  # noqa: E402 — post-bootstrap import
    DATA_DIRNAME,
    RECORDS,
)

# ── the read-only zone (rules/reference-provenance.md § 1) ────────────────────
# The pattern is `squad.boundaries`'s, not this file's. It used to be spelled here in a
# third shape, and two hooks knowing one boundary differently is the defect that
# module's docstring records.
ZONE = STUDY_ZONE
ZONE_RE = study_zone_re()

# ── git ───────────────────────────────────────────────────────────────────────
#: Any option token between `git` and its subcommand. The list this replaced named
#: six globals and git has more than twenty — `--no-pager`, `--literal-pathspecs`,
#: `--exec-path=`, `--no-optional-locks`, `--bare` among them — so
#: `git --no-pager checkout main` carried a verb no guard below ever saw. Measured
#: 2026-09-17: allowed, while `git checkout main` was blocked.
#:
#: Enumerating is the wrong shape for this: the set grows with git and the failure
#: is silent. A subcommand never begins with `-`, so the rule is structural — strip
#: leading option tokens, and the two that take a separate argument (`-c`, `-C`)
#: take theirs with them.
_GIT_GLOBALS = re.compile(
    r"(^|[^\w.])git\s+(?:-[cC]\s+\S+|--(?:git-dir|work-tree|namespace|super-prefix"
    r"|exec-path|list-cmds)=\S+|-{1,2}[A-Za-z][\w-]*)\s+")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
#: A NEWLINE separates two commands exactly as `;` does, and the Bash tool is
#: handed multi-line blocks routinely. Leaving it out kept every such block as a
#: single segment, which is where the recursive-delete false positive survived its
#: first fix: `rm -f x_test.go\ngrep -rn foo cmd` is two commands, and judging it
#: as one assembled an `rm -r` out of parts belonging to neither.
_SEGMENTS = re.compile(r"\|\||&&|;|\n")
_SEGMENTS_WITH_PIPE = re.compile(r"\|\||&&|;|\n|\|")

FORCE_TOKEN_RE = re.compile(r"(--force(\s|$)|(^|\s)-[a-z]*f(\s|$)|\s\+[^\s-]\S*)")

#: The safer force push, which is still a force push. Kept SEPARATE from
#: `FORCE_TOKEN_RE` because the two get different answers: this one is allowed on a
#: disposable branch and refused on a permanent one, while the plain forms are
#: refused everywhere. Anchored so `--force-with-lease=refs/heads/x` matches too.
LEASE_TOKEN_RE = re.compile(r"--force-with-lease(\s|=|$)")

#: The branches that are never force-pushed, in any form. `main` belongs here and
#: not in `_PERMANENT`: that name answers "which branches are never DELETED", and
#: `main` is not deletable by this flow in the first place. Two questions, two
#: lists — merging them would widen the delete guard by accident.
_NEVER_FORCE_PUSHED = re.compile(r"(^|\s|:)(origin/)?(main|develop|workspace)(\s|$)")

#: Everything that writes to or consumes the stack. `list` and `show` only read
#: it, and refusing those would teach an agent the guard is noise.
STASH_MUTATION_RE = re.compile(r"git\s+stash\b(?!\s+(list|show)\b)")
DASH_C_RE = re.compile(r"git\s+-C\s+(\S+)")

RM_INVOCATION_RE = re.compile(r"(^|\s|;|&&|\|\||\||\()\s*rm\s")
RM_RECURSIVE_RE = re.compile(r"(^|\s)(-[a-zA-Z]*[rR][a-zA-Z]*(\s|$)|--recursive(\s|=|$))")
DANGEROUS_PATH_RE = re.compile(
    r"(/(\s|$)|(^|\s)/\*|~/?(\s|$)|\$HOME/?(\s|$)|/home(\s|$)|/home/(\s|$)"
    r"|/home/[^/\s]+/?(\s|$)|(/etc|/usr|/var|/bin|/lib|/opt|/boot|/root)(\s|/|$))")

#: Quotes, a braced variable and a trailing glob are spellings of the same path, and
#: the pattern above anchors on whitespace, so each of them slipped past it. Measured
#: 2026-09-17: `rm -rf /etc` blocked; `rm -rf "/etc"`, `rm -rf \'/etc\'`, `rm -rf ~/*`,
#: `rm -rf $HOME/*`, `rm -rf "$HOME"` and `rm -rf ${HOME}` all allowed.
#:
#: Normalising the text before the match keeps one pattern instead of six, and keeps
#: the pattern readable — which is what let the gap hide in it.
_BRACED_VAR = re.compile(r"\$\{(\w+)\}")


def path_normalised(text: str) -> str:
    """The same segment with quoting, braces and a trailing glob removed.

    Only for deciding whether a path is a system or home root. It is deliberately
    lossy — `${HOME}` and `$HOME` become one thing — because the guard's question is
    which ROOT is named, not which exact string was typed.
    """
    text = _BRACED_VAR.sub(r"$\1", text)
    text = text.replace('"', " ").replace("'", " ")
    # `~/*` and `/etc/*` name the same root as `~/` and `/etc/`; the glob only says
    # "the contents of".
    text = re.sub(r"/\*(\s|$)", r"/\1", text)
    return text


EXPORT_VERB_RE = re.compile(r"(^|\s|\()\s*(cp|mv|rsync|scp|install|tar|zip|dd)(\s|$)")
EXPORT_REDIRECT_RE = re.compile(r">{1,2}\s*[^\s&>]")
EXPORT_PIPE_RE = re.compile(r"\|\s*(tee|dd)(\s|$)")
ZONE_WRITE_RE = re.compile(
    rf"(^|\s|;|&&|\|\||\||\()\s*((rm|mv|cp|sed\s+-i|tee)\s+[^;&|]*{ZONE}|>{{1,2}}\s+{ZONE})")

#: The two branches the flow depends on existing. `workspace` is a single
#: permanent branch and `develop` is where promotion lands; deleting either
#: discards work that was never promoted and leaves the next `git switch` to
#: recreate the name with none of the history every rule refers to.
_PERMANENT = r"(?P<name>(origin/)?(workspace|develop))"
#: Three spellings delete a permanent branch and only one was matched. The pattern
#: required the flag BEFORE the name and looked only at `git branch`, so
#: `git branch workspace -D`, `git branch --delete --force workspace`,
#: `git push origin --delete workspace` and `git push origin :workspace` all passed —
#: measured 2026-09-17, and `git branch tmpbr -D` confirmed to really delete.
BRANCH_DELETE_PATTERNS = (
    # flag first: git branch -D workspace
    re.compile(rf"git\s+branch\s+(-\S+\s+)*-\S*[dD]\S*\s+{_PERMANENT}(\s|$)"),
    # name first: git branch workspace -D  /  git branch workspace --delete --force
    re.compile(rf"git\s+branch\s+{_PERMANENT}\s+(\S+\s+)*(-\S*[dD]\S*|--delete)(\s|$)"),
    # long form in any order: git branch --delete --force workspace
    re.compile(rf"git\s+branch\s+(--\S+\s+)*--delete(\s+--\S+)*\s+{_PERMANENT}(\s|$)"),
    # the remote: git push origin --delete workspace  /  git push origin :workspace
    re.compile(rf"git\s+push\s+\S+\s+(--delete|-d)\s+{_PERMANENT}(\s|$)"),
    re.compile(rf"git\s+push\s+\S+\s+:{_PERMANENT}(\s|$)"),
)

#: A command that writes to a file, and the tokens it writes to. `>`/`>>` name
#: their target directly; the verbs take theirs as operands. Not exhaustive and
#: cannot be — the same honest limit `check_credential_read` states.
WRITE_VERB_RE = re.compile(
    r"(^|\s|;|&&|\|\||\||\()\s*(sudo\s+)?"
    r"(sed\s+-i\S*|rm|mv|cp|tee|truncate|chmod|chown|install|dd|touch)(\s|$)")
REDIRECT_TARGET_RE = re.compile(r">{1,2}\s*(?P<target>[^\s&>|;]+)")

PKG_INSTALL_RE = re.compile(
    r"(pip|poetry|uv|npm|pnpm|yarn|cargo|go\s+(get|mod))\s+(install|add|tidy|download)")


#: Seconds per git call, against the 10s `hooks.json` gives this hook. Three run
#: in sequence on the worst path — the worktree listing, the current branch and
#: the remote's default. At the old 5s each that path could not fit, and a
#: PreToolUse hook killed at its limit blocks nothing while looking like it ran.
#: Local git answers these in milliseconds; the budget is for a cold cache.
_GIT_TIMEOUT = 2


def _git_prefix(command: str) -> list[str]:
    """The `-C <path>` the command itself carries, as arguments for `git`.

    The repository a command acts on is the one it NAMES, not the one the session
    happens to sit in. `working_trees()` has honoured this since kit#31; the
    branch guards did not, so `strip_git_globals` correctly saw `git commit` and
    then asked the wrong repository which branch it was on. That read a trunk as
    `workspace` and `workspace` as a trunk, one release apart.
    """
    where = DASH_C_RE.search(command)
    return ["-C", where.group(1).strip("'\"")] if where else []


#: Returned when git could not be asked at all — binary missing, timeout, non-zero
#: exit. Distinct from `""`, which is git answering with nothing (a detached HEAD
#: has no current branch name and that IS the answer).
GIT_UNREACHABLE = None


def _git_out(*args: str) -> str | None:
    """The answer, `""` for an empty answer, or `GIT_UNREACHABLE` for no answer.

    It used to return `""` for all three. The branch guard wrote
    `_git_out(...) or "unknown"`, and `"unknown"` is in nobody's trunk list, so every
    trunk guard fell silent exactly when the hook could not tell where HEAD was — it
    failed OPEN on its own blindness. `hooks/stop-validation.py:127` already models the
    other way, recording the unreachability and saying so.
    """
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True,
                              timeout=_GIT_TIMEOUT, check=False)
    except (OSError, subprocess.SubprocessError):
        return GIT_UNREACHABLE
    if done.returncode != 0:
        return GIT_UNREACHABLE
    return done.stdout.strip()


def working_trees(command: str) -> int:
    """How many working trees share this repository's ONE stash stack.

    `git worktree` gives each tree its own index, HEAD and checkout, and that is
    what makes the omission expensive: the stash is not among them. `refs/stash`
    lives in the common git dir, so every tree pushes and pops the same stack and
    `git stash pop` returns the top entry no matter which tree pushed it.

    The command's own `-C <path>` is honoured before the cwd, because the fleet's
    briefs drive git that way (`git -C {repo} worktree add …`) and a guard that
    only ever asks the current directory misses the form the kit itself uses.

    WHAT THIS DOES NOT COVER
    ------------------------
    A listing that cannot be read counts as zero trees and the stash is allowed —
    outside a repository there is no stack to share, and refusing there would
    block a command that cannot do the damage. The same fail-open applies if git
    itself is unavailable. And like every guard in this file it matches the
    command as written: `bash -c 'git stash'`, an alias, or a script that stashes
    on the agent's behalf reaches the stack unread. It closes the accident and the
    habit, which is what happened on 2026-09-04; it is not a sandbox.
    """
    listing = _git_out(*_git_prefix(command), "worktree", "list", "--porcelain")
    if listing is GIT_UNREACHABLE:
        # Documented fail-open, unchanged: the stash guard only narrows an allowance,
        # and refusing every `git stash` because git could not be reached would block
        # work over a condition that has nothing to do with the hazard.
        return 1
    return sum(1 for line in listing.splitlines() if line.startswith("worktree "))


def strip_git_globals(command: str) -> str:
    """`git -C /x commit` reads as `git commit`, so a global flag cannot hide it."""
    previous = None
    while command != previous:
        previous = command
        command = _GIT_GLOBALS.sub(r"\1git ", command)
    return command


def segments(command: str, *, with_pipe: bool = False) -> list[str]:
    """Judged per segment, so an unrelated `cp` in a compound is not blamed on
    a zone path that appears elsewhere in the same line."""
    pattern = _SEGMENTS_WITH_PIPE if with_pipe else _SEGMENTS
    return pattern.split(command)


def trunks(prefix: list[str] | None = None) -> list[str]:
    """`main`, `master`, and whatever the remote actually calls its default.

    F12: a project whose trunk is `trunk` or `release` installed this kit, read
    Rule 4, and got no protection because the rule named `main`. The remote's
    HEAD is the honest source; `workspace` and `develop` are excluded because
    they have their own rules and are never the trunk.
    """
    names = ["main", "master"]
    default = _git_out(*(prefix or []), "symbolic-ref", "--short",
                       "refs/remotes/origin/HEAD") or ""
    default = default.removeprefix("origin/")
    if default and default not in ("workspace", "develop") and default not in names:
        names.append(default)
    return names


def _targets(unquoted: str, branch: str) -> bool:
    """Does the command move HEAD onto `branch`? `switch -c` and `checkout -b` too."""
    return bool(re.search(rf"git\s+switch\s+(-[cC]\s+)?{re.escape(branch)}(\s|$)", unquoted)
                or re.search(rf"git\s+checkout\s+(-b\s+)?{re.escape(branch)}(\s|$)", unquoted))


#: `git "commit"` is `git commit`. `_QUOTED.sub("", ...)` deleted the quoted span
#: entirely, so the verb vanished and every guard below matched nothing — measured
#: 2026-09-17 on the trunk: allowed. Quotes are stripped ONLY here, on the token
#: right after `git`, because everywhere else deleting quoted text is deliberate: a
#: commit message saying "main" must not read as switching to it.
_GIT_VERB_QUOTED = re.compile(r"""(^|[^\w.])(git\s+)(['"])([a-z][\w-]*)\3""")


#: The command NAME in quotes. `"git" checkout main` is the simplest real invocation
#: after the bare line, and it never blocked: `_runs_git` answers True — the lexer strips
#: quotes and the discriminant is right — and then every pattern below looks for
#: `git\s+checkout` in text that reads `"git" checkout` and misses by two characters.
#:
#: Pre-existing, and found only when somebody tested the TRIVIAL case. The exotic ones
#: had been swept three times over.
#:
#: Only in COMMAND POSITION: start of string, or after a separator. A quoted `git`
#: inside `echo "'git' checkout main is forbidden"` is a citation and stays quoted, so
#: the mention keeps reading as a mention.
_GIT_NAME_QUOTED = re.compile(r"""(^|[;&|(){}]\s*|^\s*)(['"])(git)\2(?=\s)""")


def unquote_git_verb(command: str) -> str:
    return _GIT_VERB_QUOTED.sub(r"\1\2\4", _GIT_NAME_QUOTED.sub(r"\1\3", command))


#: Commands that EXECUTE the rest of the line. A wrapper does not occupy the command
#: position — it holds it open, and it holds it open across its OWN flags and arguments,
#: not merely across the next token.
#:
#: That distinction is the whole rule, and it arrived as a contrast rather than a case:
#: `xargs git checkout` blocked while `xargs -I{} git checkout {}` did not, so the
#: wrapper was never the thing closing the position — the flag between the wrapper and
#: `git` was. Same shape in `timeout 5 git …` (the `5`) and `env -i git …` (the `-i`),
#: while `env GIT_DIR=x git …` and `nohup git … &` blocked because there the command
#: comes immediately after. One rule replaces the special case each of those would need.
_WRAPPERS = frozenset({
    "env", "sudo", "time", "timeout", "nohup", "nice", "ionice", "stdbuf", "setsid",
    "xargs", "watch", "command", "exec", "builtin", "doas", "find", "parallel",
})

#: Wrappers that open the command position after a MARKER rather than after a run of
#: flags. `find … -exec git checkout main \;` and `parallel git checkout ::: main`
#: execute the rest of the line exactly as `xargs` does; what differs is where the
#: command starts. Without this, skipping "flags and values" walks straight past
#: `-exec` and lands on `git` with the position already closed.
#: `parallel` is deliberately NOT here, and the asymmetry is the reason: its command
#: comes BEFORE the marker (`parallel git checkout ::: main`) while `find`'s comes
#: after (`find . -exec git checkout main \;`). Treating them alike skipped past the
#: command in one to reach the arguments of the other. `parallel` is an ordinary
#: wrapper — the position opens straight after its flags.
_COMMAND_MARKERS = {"find": ("-exec", "-execdir", "-ok", "-okdir")}

#: Shell keywords that open a command position without being one.
_KEYWORDS = frozenset({"then", "else", "do", "!", "{", "("})

#: Where one command ends and the next begins. A `git` token after any of these opens a
#: new command; anywhere else it is an argument to the command already running.
#:
#: `(` and `{` are here too: a subshell or a group opens a command position, and
#: `(git checkout main)` is as much an invocation as the bare line.
_SEPARATORS = frozenset({"|", "||", "&&", ";", ";;", "&", "(", ")", "{", "}", "\n"})

#: Commands that take SHELL as an argument rather than a path. `sh -c "git …"` is the
#: heredoc rule with the argument in place of the body, and leaving it out meant
#: `bash <<EOF` blocked while `bash -c` passed — one fact with two answers.
_SHELL_FLAG = frozenset({"-c"})

#: `eval "git checkout"` takes SHELL as an argument rather than wrapping a command, so
#: its arguments are read as command text rather than skipped.
_EVALUATORS = frozenset({"eval"})


#: Commands whose heredoc body IS shell and must keep being read as such.
_INTERPRETERS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "python", "python3"})

#: `<<EOF`, `<<-EOF`, `<<'EOF'`, `<<"EOF"` — the delimiter, however it is written.
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w-]*)\1")


def _split_heredocs(command: str) -> tuple[str, list[str], bool]:
    r"""`(shell, bodies_that_are_shell, readable)`.

    A heredoc body is DATA, not shell. A markdown table written into a document arrives
    as `cat > d.md <<EOF` / `| forbidden | git checkout main |` / `EOF`; the `|` are
    table cells and `shlex` reads them as pipes, so `git` lands in command position and
    a document ABOUT the rule is refused as a violation of it.

    Two bodies are NOT data and are returned to be read as shell in their own right:

      - one fed to an interpreter — `bash <<EOF` really does execute what follows, and
        treating it as data would hand anyone a two-line bypass of every guard here;
      - none at all, when the terminator never arrives: the body swallows the rest of
        the command, nothing after it can be read, and `readable=False` says so.
    """
    lines = command.splitlines()
    shell: list[str] = []
    bodies: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        shell.append(line)
        match = _HEREDOC_RE.search(line)
        index += 1
        if not match:
            continue
        first = line.strip().split()
        base = first[0].rsplit("/", 1)[-1] if first else ""
        delimiter = match.group(2)
        body: list[str] = []
        while index < len(lines) and lines[index].strip() != delimiter:
            body.append(lines[index])
            index += 1
        if index >= len(lines):
            # No terminator. What the body swallowed cannot be read, so nothing here
            # may be cleared.
            return "\n".join(shell), bodies, False
        shell.append(lines[index])  # the terminator; the body it closed is dropped
        index += 1
        if base in _INTERPRETERS:
            bodies.append("\n".join(body))
    return "\n".join(shell), bodies, True


def _runs_git(command: str) -> bool:
    r"""Whether this shell text actually INVOKES git, rather than mentioning it.

    WHY POSITION AND NOT A PATTERN. A consumer measured four payloads on this tree:
    `git checkout main` (runs git), and `echo "…git checkout main"`, a heredoc carrying
    the phrase, and `grep -n "git checkout main" rules/git-safety.md` — none of which run
    any git. All four were refused. The discriminant was not quoting but whether an
    argument followed, so `echo "…git checkout"` passed and the same line with one more
    word did not.

    The cost is not the refusal. Every rule file, ADR and record in this ecosystem that
    names a forbidden command becomes unwritable by heredoc, which is how documents are
    written here — and the workaround is to reshape the command until the guard goes
    quiet. A guard that teaches evasion has inverted its purpose, and the evasion
    transfers to the case that is real.

    A LOOSER PATTERN WAS NEVER THE ANSWER: letting the real command through is the
    expensive failure. What separates the four is whether `git` sits in COMMAND
    POSITION. `shlex` answers that exactly, and where it cannot answer — an unbalanced
    quote — this returns True, so an unparseable command stays refused. Fail-closed by
    construction, not by hope.
    """
    shell, interpreted, readable = _split_heredocs(command)
    if not readable:
        return True
    # A body fed to an interpreter is a command in its own right, and is read as one.
    if any(_runs_git(body) for body in interpreted):
        return True
    try:
        tokens = _shell_tokens(shell)
    except ValueError:
        # Unbalanced quoting. The text cannot be read, so it cannot be cleared.
        return True

    expecting_command = True
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token in _SEPARATORS:
            expecting_command = True
            continue
        if not expecting_command:
            continue
        if token in _KEYWORDS or "=" in token.split("/")[0]:
            # A keyword, or a `VAR=value` assignment: the command is still ahead.
            continue
        base = token.rsplit("/", 1)[-1]
        if base == "git":
            return True
        if base in _EVALUATORS:
            # `eval "git checkout main"`: the ARGUMENT is shell, and the quotes are gone
            # by the time the lexer is done — so each following token is read as its own
            # command text.
            while index < len(tokens) and tokens[index] not in _SEPARATORS:
                if _runs_git(tokens[index]):
                    return True
                index += 1
            continue
        if base in _WRAPPERS:
            markers = _COMMAND_MARKERS.get(base)
            if markers:
                # The command starts after the marker, and everything before it is the
                # wrapper's own expression — `find . -name x -exec …` has a bare `.`
                # and a bare `x` that the flag-skipping below would stop on.
                while index < len(tokens) and tokens[index] not in markers:
                    if tokens[index] in _SEPARATORS:
                        break
                    index += 1
                if index < len(tokens) and tokens[index] in markers:
                    index += 1
                continue
            # Skip the wrapper's own flags and their values, then leave the position
            # open for whatever it wraps. `-I{}`, `-n1`, `--signal=KILL`, a bare `5`
            # for `timeout`, `-i` for `env` — none of them is the command.
            while index < len(tokens):
                nxt = tokens[index]
                if nxt in _SEPARATORS:
                    break
                if nxt.startswith("-") or nxt.isdigit() or "=" in nxt.split("/")[0]:
                    index += 1
                    continue
                break
            continue
        if base in _INTERPRETERS:
            # `sh -c "git checkout main"` — the argument after `-c` is shell, read as
            # its own command, exactly as a heredoc body fed to the same interpreter is.
            while index < len(tokens) and tokens[index].startswith("-"):
                flag = tokens[index]
                index += 1
                if flag in _SHELL_FLAG and index < len(tokens):
                    if _runs_git(tokens[index]):
                        return True
                    index += 1
            continue
        # Anything else occupies the command position, so every `git` after it is that
        # command's argument — including the ones inside a heredoc it is fed.
        expecting_command = False
    return False


def _shell_tokens(text: str) -> list[str]:
    r"""Tokens with shell OPERATORS separated out, which `shlex.split` does not do.

    `shlex.split("echo hi; git checkout main")` returns `hi;` as one token and drops the
    newline in `echo ok\ngit checkout main` entirely — so a separator list never matched
    and only the FIRST command position in a string was ever found. Measured by the
    consumer that reported the false positives, in the other direction: six real
    invocations passed, every one of them `git` in a command position that was not the
    first.

    `punctuation_chars=True` is what makes `;`, `|`, `&&`, `(` and `)` their own tokens.
    Newlines are turned into `;` first, because the lexer treats them as plain
    whitespace and a line break ends a command exactly as a semicolon does.
    """
    lexer = shlex.shlex(text.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def check_git(command: str) -> str | None:
    # Asked FIRST, because everything below reads the text for git verbs and a citation
    # carries the same words as an invocation. See `_runs_git` for the measurement.
    if not _runs_git(command):
        return None

    cmd = unquote_git_verb(strip_git_globals(unquote_git_verb(command)))

    if re.search(r"git\s+checkout(\s|$)", cmd):
        return ("BLOCKED: 'git checkout' is forbidden by Unbreakable Rule 4. "
                "Use 'git switch' or 'git restore' instead.")
    if re.search(r"git\s+revert(\s|$)", cmd):
        return ("BLOCKED: 'git revert' is forbidden by Unbreakable Rule 4. "
                "Create a new commit that reverses the change explicitly.")
    deleting = next(
        (m for pattern in BRANCH_DELETE_PATTERNS
         if (m := pattern.search(_QUOTED.sub("", cmd)))), None)
    if deleting:
        return (f"BLOCKED: '{deleting.group('name')}' is a permanent branch of the "
                f"flow (git-safety.md § 1) and is never deleted. Deleting it "
                f"discards whatever was not promoted, and the next 'git switch' "
                f"recreates the name with none of the history the rules refer to. "
                f"Delete the disposable branch instead, or leave it.")
    for segment in segments(cmd, with_pipe=True):
        if not re.search(r"git\s+push(\s|$)", segment):
            continue
        if FORCE_TOKEN_RE.search(segment):
            return ("BLOCKED: force push is forbidden on any branch (git-safety.md § 1). "
                    "Force-push only a disposable branch — an experiment nobody else "
                    "has — and never main, develop or workspace.")
        # `--force-with-lease` used to reach here and pass: it matches none of
        # FORCE_TOKEN_RE's three alternatives, while the refusal above named an
        # authorization precondition nothing in this hook asks about. The lease
        # protects against clobbering a fetch you have not seen; it protects NOTHING
        # about a permanent branch, where the push rewrites published history exactly
        # as `--force` does whenever the lease happens to hold.
        if LEASE_TOKEN_RE.search(segment) and _NEVER_FORCE_PUSHED.search(segment):
            return ("BLOCKED: '--force-with-lease' is still a force push, and main, "
                    "develop and workspace are never force-pushed (git-safety.md § 1). "
                    "The lease guards against clobbering a fetch you have not seen — "
                    "it does not make rewriting a permanent branch's history safe. "
                    "Force-push a disposable branch instead.")
    if re.search(r"git\s+reset\s+--hard", cmd):
        return ("BLOCKED: 'git reset --hard' is forbidden. Use 'git reset --soft', or "
                "commit on a branch, instead.")

    # Quoted text is not a branch name: a commit MESSAGE saying "main" must not
    # read as switching to it — nor one that merely mentions the stash.
    unquoted = _QUOTED.sub("", cmd)

    # The stash is the one thing a worktree does NOT isolate, and the cost is
    # asymmetric in the way this whole hook is for: measured 2026-09-04 (kit#31),
    # two agents in separate worktrees stashed concurrently and each popped the
    # other's entry, swapping uncommitted work. With a single working tree there
    # is nobody to swap with and the stash stays allowed.
    if STASH_MUTATION_RE.search(unquoted) and working_trees(command) > 1:
        return ("BLOCKED: this repository has more than one working tree, and they "
                "SHARE one stash stack — 'refs/stash' lives in the common git dir, "
                "so 'git stash pop' returns the top entry whichever tree pushed it. "
                "Two agents swapped their uncommitted work this way (kit#31). To "
                "reach a clean tree: copy the files aside with 'cp', or commit them "
                "on your own branch, then 'git restore'.")

    # B-264 — the commit is where the shared stack is actually touched, and the only
    # place this guard can say so.
    #
    # `working_trees()` above refuses a PERSON typing the command under several
    # worktrees. It cannot see `.githooks/pre-commit`, which invokes lint-staged,
    # which pushes to `refs/stash` on EVERY commit. Measured 2026-09-23: two orphaned
    # `lint-staged automatic backup` entries sat on the stack, so the cleanup had
    # already failed twice and nobody noticed. The kit refused the safe case and
    # permitted the dangerous one in silence.
    #
    # A WARNING and never a refusal, for the reason `.githooks/pre-commit` gives for
    # not forbidding partial staging: "a gate that forbade it would trade a rare
    # silent loss for a constant obstruction". A fleet that uses worktrees by design
    # commits under them all day; refusing that is how a guard gets switched off.
    #
    # Printed to stderr with exit 0 — the contract for "say something, allow it".
    if re.search(r"git\s+commit\b", unquoted) and working_trees(command) > 1:
        print("NOTE: this repository has more than one working tree, and they SHARE one "
              "stash stack. A pre-commit hook that stashes (lint-staged does, on every "
              "run) pushes to `refs/stash`, which `git worktree` does NOT isolate — a "
              "pop returns the top entry whichever tree pushed it. Check `git stash "
              "list` if a commit here behaves oddly; orphaned backups have been "
              "observed. Not a refusal: committing under worktrees is ordinary.",
              file=sys.stderr)

    # The `-C` that decides WHICH repository is asked has to be the one carried by
    # the segment being judged. `_git_prefix` read the first one anywhere in the
    # command, so `git -C /tmp status && git commit -m x` asked /tmp which branch it
    # was on and let the commit through on the trunk — measured 2026-09-17. A segment
    # with no `-C` of its own acts on the repository the session is in.
    # Segmented from the RAW command, not from `cmd`: `strip_git_globals` removes the
    # very `-C <path>` this needs to read. Stripping it is right for verb matching and
    # wrong for deciding which repository the verb acts on, and reading both from the
    # stripped string is how the first version of this fix broke
    # `test_the_branch_is_read_from_dash_c_not_only_from_the_cwd`.
    verb_segments = [seg for seg in segments(command, with_pipe=True)
                     if re.search(r"git\s+\S", seg)] or [command]
    prefixes = {tuple(_git_prefix(seg)) for seg in verb_segments}

    branch: str | None = None
    unreachable = False
    for pre in prefixes:
        answer = _git_out(*pre, "branch", "--show-current")
        if answer is GIT_UNREACHABLE:
            unreachable = True
            continue
        if answer in trunks(list(pre)):
            branch = answer
            break
        branch = branch or answer

    if unreachable and branch is None:
        return ("BLOCKED: git could not be reached, so this hook cannot tell which "
                "branch HEAD is on. It refuses rather than assuming the branch is a "
                "safe one — a guard that falls silent exactly when it cannot see is "
                "not a guard. Re-run once git answers, or move the work to a branch "
                "you have confirmed.")

    prefix = list(next(iter(prefixes), ()))
    names = trunks(prefix)
    branch = branch if branch is not None else "unknown"

    on_trunk = branch in names
    moving_to_trunk = any(_targets(unquoted, name) for name in names)
    if on_trunk or moving_to_trunk:
        if re.search(r"git\s+commit(\s|$)", unquoted):
            return (f"BLOCKED: never commit directly to the trunk '{branch}' "
                    f"(Unbreakable Rule 4). Work is born on 'workspace' "
                    f"(workspace → develop → trunk); develop integrates, it never "
                    f"originates.")
        if re.search(r"git\s+(merge|rebase|reset|cherry-pick)(\s|$)", unquoted):
            return (f"BLOCKED: never mutate the trunk '{branch}' directly (Unbreakable "
                    f"Rule 4). It receives release merges only, via a develop→trunk PR. "
                    f"Switch to 'workspace' first.")

    if branch == "develop" or _targets(unquoted, "develop"):
        if re.search(r"git\s+commit(\s|$)", unquoted):
            return ("BLOCKED: never commit directly to 'develop' (git-safety.md § 1). "
                    "Work is born on 'workspace' and reaches develop through a "
                    "workspace→develop PR. Switch to 'workspace' first.")
        if re.search(r"git\s+(rebase|reset|cherry-pick)(\s|$)", unquoted):
            return ("BLOCKED: never rewrite 'develop' history (git-safety.md § 1). "
                    "develop integrates work, it never originates it. Do the work on "
                    "'workspace' and promote it via PR.")
        if re.search(r"git\s+merge(\s|$)", unquoted) and not re.search(
                r"git\s+merge(\s+-\S+)*\s+((origin|upstream)/)?workspace(\s|$)", unquoted):
            return ("BLOCKED: 'develop' only accepts the promotion merge from "
                    "'workspace' (git-safety.md § 1). Merging anything else into "
                    "develop bypasses the workspace→develop gate.")
    return None


CD_RE = re.compile(r"(^|\s)cd\s+(?P<path>[^\s;&|]+)")


def _dangerous_cwd(segment: str) -> bool:
    """Did this segment move the shell onto a system or home root?

    A `cd` carries its path to every segment after it, so `cd /etc && rm -rf *`
    is the deletion `rm -rf /etc/*` spells out. Judging segments in isolation is
    right — it is what stopped an `rm` from one command being read against a path
    from another — but the isolation has to end where the shell's own state
    crosses the boundary.
    """
    found = CD_RE.search(segment)
    if not found:
        return False
    target = path_normalised(found.group("path")).strip().rstrip("/")
    return bool(DANGEROUS_PATH_RE.search(target + " "))


def check_rm(command: str) -> str | None:
    """The three conditions have to hold in the SAME segment.

    Searching each of them over the whole line and ANDing the results assembles a
    deletion nobody typed: the `rm` from one command, the `-r` from a `grep -rn`,
    the root path from a third. `rm nota.txt && grep -rn padrao /etc/hosts` was
    refused as "'rm -r' on a system/home-root path" with no `rm -r` and no root
    path anywhere in it.

    This regressed once before. A consumer measured it, fixed it in the bash
    hook, and the Python rewrite reintroduced it — which nobody caught, because
    that consumer's own guard test sent an incomplete payload and every row of it
    was measuring the fail-closed path rather than this function.

    `segments()` already states the rule in its docstring, and `check_zone` was
    already the only caller honouring it: *"judged per segment, so an unrelated
    `cp` in a compound is not blamed on a zone path that appears elsewhere in the
    same line"*. Blocking a real `rm -rf /etc` inside a compound still works,
    because there all three conditions live in one segment.
    """
    at_risk = False
    for segment in segments(command):
        # The path is matched against the NORMALISED segment: quoting, `${...}` and a
        # trailing glob are spellings, not different paths. The invocation and the
        # recursive flag are matched against the raw one, because normalising cannot
        # help there and a lossy input is a bigger risk than none.
        if RM_INVOCATION_RE.search(segment) and RM_RECURSIVE_RE.search(segment) \
                and (DANGEROUS_PATH_RE.search(path_normalised(segment)) or at_risk):
            return ("BLOCKED: 'rm -r' on a system/home-root path. Scope recursive deletions "
                    "to project-relative paths, deep project subdirectories, or /tmp/.")
        # Evaluated after the `rm`, because a `cd` in the SAME segment runs after
        # it too — `rm -rf * ; cd /etc` deletes the current directory's contents.
        if _dangerous_cwd(segment):
            at_risk = True
    return None


def check_zone(command: str, project_dir: Path) -> str | None:
    """Nothing goes in, nothing comes out, and the history does not cite it."""
    if (project_dir / ".references-bootstrap").is_file():
        return None  # the documented escape hatch, for initial population only

    if ZONE_WRITE_RE.search(command):
        return (f"BLOCKED: {STUDY_ZONE}/ is read-only third-party material. Capture "
                f"findings in '{DATA_DIRNAME}/{RECORDS}/discoveries/blueprints/'. For "
                "initial bootstrap, "
                "create '.references-bootstrap' at project root AND cite the source in "
                "CHANGELOG.md; remove the marker when done.")

    # Reading, grepping and listing stay allowed — that is what the zone is FOR.
    # The pipe does not split here: `cat <zone-file> | tee <dest>` is an export.
    for segment in segments(command):
        if not ZONE_RE.search(segment):
            continue
        if (EXPORT_VERB_RE.search(segment) or EXPORT_REDIRECT_RE.search(segment)
                or EXPORT_PIPE_RE.search(segment)):
            return (f"BLOCKED: copying content OUT of {STUDY_ZONE}/ is forbidden — "
                    "that is third-party study material and a literal copy carries its "
                    "licence into this project. Read it, learn from it, and write your "
                    f"own version; record the finding in "
                f"'{DATA_DIRNAME}/{RECORDS}/discoveries/blueprints/' "
                    "citing the source.")
    return None


def commit_text(command: str) -> str:
    """The message as written, plus a `-F <file>` body — that is how a long one
    reaches git, and a guard reading only `-m` would miss it entirely."""
    text = command
    found = re.search(r"(-F|--file)\s+(\S+)", command)
    if found:
        candidate = Path(found.group(2).strip("'\""))
        try:
            if candidate.is_file():
                text += "\n" + candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # `is_file()` says readable-as-a-file, not readable-by-us: `/etc/shadow`
            # passes it and raises PermissionError on the read. Nothing caught that,
            # so the hook exited 1 — which `squad/outputs.py:29` documents as "the user
            # sees the stderr, the action proceeds" — and the two guards below, the
            # co-author trailer and the study-material zone, never ran. A guard that
            # crashes out of its own list is worse than one that reads less.
            #
            # Failing open HERE is the right direction and the opposite of the branch
            # guard's: this function only ADDS text to search. Losing it means the
            # message body goes unexamined, which is the pre-existing state for every
            # commit that does not use -F; crashing means the whole hook is skipped.
            text += f"\n[validate-command: could not read {candidate} — body unexamined]"
    return text


def check_commit_message(command: str) -> str | None:
    if not re.search(r"git\s+commit", command):
        return None
    text = commit_text(command)
    if ZONE_RE.search(text):
        return (f"BLOCKED: the commit message cites a path under {STUDY_ZONE}/. That "
                "zone is third-party study material and must not be referenced in this "
                "repository's public history. Describe the behaviour you implemented, "
                "not the material you studied.")
    if re.search(r"co-authored-by", text, re.IGNORECASE):
        return ("BLOCKED: 'Co-Authored-By:' trailers are forbidden on this project's "
                "commits (user policy). Remove the trailer from the commit message body.")
    return None


def check_kit_boundary(command: str, project_dir: Path) -> str | None:
    """Refuse a shell write into the installed kit — the same line `Edit` holds.

    `boundary-check` guards `Edit`/`Write` and this guards the shell; both ask
    `squad.boundaries` where the line is, so the two halves cannot drift apart.
    While only the first existed, `sed -i` reached the file the other had just
    refused, and the reason the boundary exists — a fix inside an installed kit
    protects one machine and the next install erases it — says nothing about
    which tool did the writing.

    Reading stays allowed everywhere: an agent that cannot read its own contracts
    cannot follow them.
    """
    # `warn` stays on. `squad.layout` says why in its own docstring — *"a hook
    # that silences the broken-install warning reproduces the exact failure the
    # warning was added for"* — and a broken install is precisely when this
    # guard is not running while the session looks protected. The repetition is
    # the point: it only fires when something is wrong.
    layout = resolve(project_dir)
    if layout is None or layout.kind == "standalone":
        return None

    for segment in segments(command, with_pipe=True):
        targets: list[str] = []
        if WRITE_VERB_RE.search(segment):
            # Absolute, `./`-prefixed AND bare-relative. The first two were the whole
            # pattern, so `sed -i s/a/b/ .claude/rules/architecture.md` — the ordinary
            # way anyone types it — was never collected and therefore never examined,
            # while the absolute spelling of the same file was refused. Measured
            # 2026-09-17. A bare token with no `/` cannot name a path inside the kit,
            # so requiring one keeps flags and sed expressions out of the candidate
            # list without narrowing what the guard can see.
            targets += re.findall(
                r"(?<!\S)((?:/|\.{1,2}/)?[\w.@+-]+(?:/[^\s;&|>]*)+)", segment)
        targets += [m.group("target") for m in REDIRECT_TARGET_RE.finditer(segment)]
        for token in targets:
            reason = violation(Path(token.strip("'\"")), layout)
            if reason:
                return reason
    return None


def check_package_install(command: str, cwd: Path) -> str | None:
    if PKG_INSTALL_RE.search(command) and ZONE_RE.search(str(cwd) + "/"):
        return ("BLOCKED: never install dependencies inside study-material/. "
                "Those are read-only third-party trees.")
    return None


#: Commands that put a file's CONTENT somewhere the session can see it. Not
#: exhaustive and cannot be — `python3 -c "print(open('.env').read())"` is not
#: here and will not be caught. See `check_credential_read`.
_READERS_RE = re.compile(
    r"(^|\s|\||;|&&|\()\s*(sudo\s+)?"
    r"(cat|bat|less|more|head|tail|nl|strings|xxd|od|hexdump|base64|"
    r"grep|rg|ag|awk|sed|cut|sort|uniq|tee|cp|scp|rsync|curl|wget)(\s|$)")


def _credential_globs(project_dir: Path) -> list[str]:
    """The path shapes `settings.json` already refuses to Read.

    Read from that file rather than restated here, and the reason is the defect
    this whole guard exists for. `permissions.deny` refused `Read` on these paths
    and nothing else, so `cat` returned them and `Edit` rewrote them. A second
    list of the same shapes, kept by hand in Python beside the JSON one, is how
    that gap reopens: on 2026-09-02 this kit found FOUR separate cases of a rule
    living in one file and missing from another, and stopped adding new ones.
    """
    for candidate in (project_dir / ".claude" / "settings.json",
                      project_dir / "settings.json",
                      Path(__file__).resolve().parent.parent / "settings.json"):
        try:
            rules = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        deny = rules.get("permissions", {}).get("deny", [])
        globs = [r[5:-1] for r in deny if r.startswith("Read(") and r.endswith(")")]
        if globs:
            return globs
    return []


def _names_a_path(token: str, project_dir: Path) -> bool:
    """Is this token a FILE the command opens, or a WORD it searches for?

    Every token used to be compared against the deny globs, so the term being
    searched for was read as the file being opened: `grep -rn credentials src/`
    was refused because `credentials` matches `**/credentials`. The globs with no
    separator and no suffix — `credentials`, `kubeconfig`, `id_rsa` — are exactly
    the shape a search term has, and looking for where credentials are USED is
    one of the commonest reviews there is. The refusal then sent the reader to
    narrow a glob that was correct.

    A separator, a suffix or a leading dot means path, and stays refused:
    `secret.yaml` as a search term is collateral this gate accepts, because the
    doubt is real and the cost of guessing wrong runs one way. The leading dot is
    not decoration — `Path(".env").suffix` is empty, so a dotfile reads as a bare
    word and the commonest credential file of all would walk straight through.
    A bare word is prose unless a file by that name is actually there.
    """
    if "/" in token or Path(token).suffix or token.startswith(("~", ".")):
        return True
    try:
        return (project_dir / token).exists()
    except OSError:
        return False


#: Commands whose first non-flag argument is a PATTERN rather than a path.
_SEARCHERS = frozenset({"grep", "egrep", "fgrep", "rg", "ag", "ack"})

#: Flags of those commands that take a value, so the value is not mistaken for the
#: pattern. `-e` is the interesting one: it names the pattern explicitly.
_SEARCH_FLAGS_WITH_VALUE = frozenset({"-e", "--regexp", "--include", "--exclude",
                                      "--exclude-dir", "-f", "--file", "-m",
                                      "--max-count", "-A", "-B", "-C", "-g", "-t"})


def _search_patterns(command: str) -> set[str]:
    """Tokens that are a search PATTERN, in any search invoked by this command.

    Returned as a set of bare tokens rather than positions, because the caller
    re-tokenises with its own regex and cannot be handed indices. A pattern that happens
    to equal a real path in the same command is therefore not exempted — which is the
    safe direction, and `test_a_pattern_and_a_credential_target_together_is_refused`
    pins it.
    """
    patterns: set[str] = set()
    try:
        tokens = shlex.split(command, comments=False)
    except ValueError:
        return patterns

    index = 0
    while index < len(tokens):
        base = tokens[index].rsplit("/", 1)[-1]
        if base not in _SEARCHERS:
            index += 1
            continue
        index += 1
        while index < len(tokens):
            token = tokens[index]
            if token in _SEARCH_FLAGS_WITH_VALUE:
                if token in ("-e", "--regexp") and index + 1 < len(tokens):
                    patterns.add(tokens[index + 1])
                index += 2
                continue
            if token.startswith("-") and len(token) > 1:
                index += 1
                continue
            patterns.add(token)  # the first bare argument: the pattern
            break
        index += 1
    return patterns


def check_credential_read(command: str, project_dir: Path) -> str | None:
    """Refuse a shell command that reads a path `settings.json` denies to `Read`.

    WHAT THIS IS AND IS NOT
    -----------------------
    The deny list refused ONE tool. `permissions.allow` carries `Bash(*)`, so
    `cat .env` returned the file that `Read(.env)` had just refused, and `Edit`
    was not denied at all — an agent could not read a credential file and could
    rewrite it blind. Measured in a consumer on 2026-09-02: 157 versioned paths
    refused to `Read`, 79 of them source code, and not one refusal a session
    could not step around in a single command.

    This closes the common door. It does NOT make the deny list a sandbox, and
    saying otherwise would make it the thing it replaces — a guard that reads as
    protection and is not. A determined session reaches the same bytes through
    `python3 -c`, a heredoc, an editor, or a path this pattern does not spell.
    What it stops is the accident and the habit, which is most of what happens.
    """
    globs = _credential_globs(project_dir)
    if not globs or not _READERS_RE.search(command):
        return None

    # The scan runs over the command with the SEARCH PATTERNS removed. Comparing tokens
    # against the patterns directly does not work: this regex splits
    # `import\.meta\.env` into `import`, `.meta` and `.env`, and none of the pieces
    # equals the whole pattern. Removing the pattern text and asking whether the token
    # still appears answers the real question — is this path named ANYWHERE other than
    # inside the expression being searched for.
    outside = command
    for pattern in _search_patterns(command):
        outside = outside.replace(pattern, " ", 1)

    for token in re.findall(r"[\w./~@+-]+", command):
        if token not in outside:
            # The PATTERN of a search is not a path being read. A consumer measured
            # `grep -rnE "import\.meta\.env" packages/` refused with "`.env` matches
            # `.env`, which settings.json refuses to Read" — no file was opened; the
            # literal sat inside the expression being searched FOR. That refusal is
            # worse than a plain false block, because it accuses the operator of going
            # after a credential.
            #
            # Only the pattern is exempt. Every other argument is still checked, so
            # `grep -rn ".env" .env` still refuses on the target.
            continue
        if not _names_a_path(token, project_dir):
            continue
        name = token.rsplit("/", 1)[-1]
        for glob in globs:
            bare = glob.removeprefix("**/")
            if fnmatch.fnmatch(token, glob) or fnmatch.fnmatch(token, bare) \
                    or fnmatch.fnmatch(name, bare):
                return (
                    f"`{token}` matches `{glob}`, which `settings.json` refuses to "
                    f"Read. A shell command that reads it returns the same bytes "
                    f"the deny rule exists to withhold.\n\n"
                    f"If the file genuinely holds no credential, the glob is wrong "
                    f"and belongs narrowed in `settings.json` — not stepped around "
                    f"here. If it does hold one, nothing in this session needs it.")
    return None


def main() -> None:
    c = create_context(PreToolUseContext)
    command = c.tool_input.get("command", "")
    if not command.strip():
        return

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())

    # Cheap pre-filters. Each MUST name what its guards actually match: while the
    # zone filter tested for `records/` and the guards had moved to
    # `study-material/`, every zone guard was unreachable and its silence read
    # as a clean pass.
    #
    # Deferred rather than evaluated into a tuple, so the first refusal is the
    # last work done. Three of these shell out to git and one resolves the
    # layout from disk; a tuple ran all of them for a command the first guard
    # had already refused, inside the 10s this hook gets before the runtime
    # kills it — and a PreToolUse hook killed at its limit blocks nothing.
    checks = (
        lambda: check_git(command) if "git" in command else None,
        lambda: check_rm(command) if "rm" in command else None,
        lambda: check_zone(command, project_dir) if "study-material/" in command else None,
        lambda: check_commit_message(command) if "git" in command else None,
        lambda: check_package_install(command, Path.cwd()),
        lambda: check_credential_read(command, project_dir),
        lambda: check_kit_boundary(command, project_dir),
    )
    for check in checks:
        reason = check()
        if reason:
            c.output.exit_block(reason)


if __name__ == "__main__":
    main()

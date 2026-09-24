#!/usr/bin/env python3
"""Run each acceptance criterion against the tree as it is, and refuse the ones that
already pass.

    python3 check_criteria_discriminate.py <brief.md> [--repo-root .] [--json]

    0  every criterion fails today — each one has something to prove
    1  at least one already passes, or could not be run
    2  could not measure

## A criterion that passes before the work is not a criterion

`score_alignment.py` grades a criterion `executable` from a TEXT MATCH over the bullet:
it asks whether a command is NAMED, never whether that command could run or whether its
answer distinguishes anything. Measured on a consumer: a brief scored 14/14 executable
where two criteria could not pass at all, and `go test -run <pattern-that-matches-
nothing>` exits 0 with `[no tests to run]` — eight criteria in one brief were satisfied
by writing no test.

The same consumer found roughly thirty criteria across eighteen briefs that returned
the same answer before and after the work. None of that is visible to a reader of the
text, and all of it is visible in one run.

## What this checks, and what it does not

It runs each criterion **once**, against the tree as it is now, and asks a single
question: does it already pass? A criterion that passes before anything is built cannot
tell a finished item from an unstarted one, whatever it says.

That is one of the three states the full method uses. It is not the whole method:

| State | Question | Here |
|---|---|---|
| current tree | does it already pass? | **yes** |
| intended state | does it pass once built? | no — the state does not exist yet |
| a deliberately wrong build | does it REJECT that? | no — needs the item's own shape |

The third is the one that catches a criterion measuring a NAME rather than a behaviour,
and the formulation worth keeping is a reviewer's: *the minimal artefact that satisfies
a criterion says exactly what it is sensitive to.* If an empty function body with the
right name turns it green, it measures the name.

So a green run here means "no criterion is vacuous in the cheapest way". It does not
mean the criteria are good.

## Running commands out of a document is the risk it is

These commands come from a brief an agent wrote. This executes them. It does so with a
timeout, in the repository root, with the environment it inherits — and it is opt-in,
invoked deliberately, never from a hook or a scorer. A brief is not untrusted input in
the way a pull request is, but it is not trusted the way this file is either: read what
you are about to run if the brief did not come from your own session.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: The bullet's command, in the inline-code span acceptance criteria write it in.
#: The LAST span on the line rather than the first: a criterion commonly names the
#: subject in backticks before stating the command that checks it.
_COMMAND_RE = re.compile(r"`([^`]+)`")

#: A span that is a shell command rather than a filename or an identifier. The same
#: vocabulary `score_alignment._EXECUTABLE_RE` uses, so the two agree on what counts.
_RUNNABLE = re.compile(
    r"\b(npm|pytest|go|cargo|make|curl|grep|rg|python3|bash|sh|node|test|jq|find|sed"
    r"|awk|wc|git|ls|cat|diff|echo|printf|true|false|sleep|kubectl|helm|docker)\b")

_UNRESOLVED = re.compile(r"\{\{[A-Z_]+\}\}|<[A-Za-z][A-Za-z0-9_-]{1,40}>|\bTBD\b")

#: What the criterion says it expects. `prints 1`, `exits 0`, `is empty`.
_EXPECT_RE = re.compile(
    r"\b(prints|outputs|exits?|returns)\s+`?(?:at\s+(?:least|most)\s+`?|no\s+(?:more|fewer)\s+than\s+`?)?"
    r"([<>]=?|[^`\s.,]+)", re.I)

#: A criterion that states a BOUND rather than a value. Probed on a consumer 2026-09-15 at
#: another session's request, and wider than the case that prompted it: `prints 4 or more`
#: extracted `4` and compared for equality, so a correct `6` read as a failure; `prints at
#: least 4` extracted the word `at`; `prints >= 3` extracted `>=`. Every comparative form
#: in the vocabulary was mis-read, and the direction of the error is the dangerous one —
#: a discrimination check satisfied by a number being DIFFERENT rather than by the
#: criterion being unmet.
_BOUND_RE = re.compile(
    r"\b(?:prints|outputs|returns)\s+`?(?:(?P<word>at\s+least|at\s+most|no\s+more\s+than|"
    r"no\s+fewer\s+than)\s+`?)?(?P<op>[<>]=?)?\s*`?(?P<num>\d+)`?"
    r"(?P<tail>\s+or\s+(?:more|fewer|less|greater|higher|lower))?", re.I)


@dataclass
class Clause:
    """One runnable span of a criterion, and what it answered today.

    A criterion is often a conjunction — `<gate exists>` AND `<test passes>` — and a
    single verdict over the whole thing cannot separate them. Measured on a consumer:

        clause 1 (the gate exists)   -> 0, because the gate is not written yet
        clause 2 (`go test -run TestGateRegistryParity`) -> exit 0, [no tests to run]

    The conjunction fails today, so a one-verdict reading calls the criterion sound.
    But clause 2 exits 0 today and will exit 0 after the work, because the test it names
    exists nowhere. When the gate is written and clause 1 passes, the whole criterion
    passes with clause 2 measuring nothing.

    A vacuous clause masked by one that fails for an unrelated reason. N clauses need N
    readings.
    """
    command: str
    ran: bool = False
    exit_code: int | None = None
    stdout: str = ""
    passes_today: bool | None = None
    note: str = ""


@dataclass
class Result:
    criterion: str
    clauses: list = field(default_factory=list)
    note: str = ""
    is_guard: bool = False

    @property
    def command(self) -> str:
        return " AND ".join(c.command for c in self.clauses)

    @property
    def ran(self) -> bool:
        return any(c.ran for c in self.clauses)

    @property
    def passing_clauses(self) -> list:
        """Clauses that pass RIGHT NOW — suspect even when the conjunction fails."""
        return [c for c in self.clauses if c.passes_today is True]

    @property
    def passes_today(self) -> bool | None:
        """The conjunction's own answer. `None` when any clause was undecidable."""
        if not self.clauses or not all(c.ran for c in self.clauses):
            return None
        if any(c.passes_today is None for c in self.clauses):
            return None
        return all(c.passes_today for c in self.clauses)


def _tree_state(repo_root: Path) -> tuple[str, bool]:
    r"""(HEAD sha, is the working tree dirty). Empty sha when this is not a repository.

    A verification does not survive the tree it measured, and that is not theoretical:
    on 2026-09-14 the kit wrote `go | api/go.mod | ENABLED` into a consumer's language
    config to unblock its quality gate, and a criterion of that consumer's B-034 —
    `grep -cE '^[[:space:]]*go[[:space:]]*\|' <that file>` — went from discriminating to
    inert in the same minute. The criterion did not change. The tree did.

    So a result is stamped with the tree it was read against. A reader comparing a
    yesterday's run to today's decision needs to know they are not the same question.
    """
    try:
        head = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10, check=False)
        status = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain"],
                                capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "", False
    if head.returncode != 0:
        return "", False
    return head.stdout.strip(), bool(status.stdout.strip())


@dataclass
class Report:
    results: list = field(default_factory=list)
    head: str = ""
    dirty: bool = False

    @property
    def already_passing(self) -> list:
        """Criteria with at least one clause that already passes, GUARDS EXCLUDED.

        Deliberately ANY clause, not the conjunction. A conjunction that fails today
        because one half is not built yet still carries the other half into the future
        unchecked — and that half is exactly what a criterion is supposed to be.

        A guard is excluded because passing today is its contract, not its failure.
        """
        return [r for r in self.results if r.passing_clauses and not r.is_guard]

    @property
    def guards(self) -> list:
        """Criteria that declare themselves guards and pass, as they must."""
        return [r for r in self.results if r.is_guard and r.passing_clauses]

    @property
    def undecidable(self) -> list:
        return [r for r in self.results if r.ran and r.passes_today is None]

    @property
    def unrunnable(self) -> list:
        return [r for r in self.results if not r.ran]

    @property
    def refused(self) -> list:
        """Criteria carrying a clause this declined to execute.

        Separate from `unrunnable` because the cause is different and so is the action:
        a clause that did not run because it timed out is a slow command, and one that
        did not run because it moves work is a command nobody should execute out of a
        document.
        """
        return [r for r in self.results
                if any(c.note.startswith("NOT RUN") for c in r.clauses)]


def _bullets(text: str) -> list[str]:
    section = re.search(r"^##+\s*.*Acceptance.*$([\s\S]*?)(?=^##|\Z)", text, re.M | re.I)
    if not section:
        return []
    return [ln.strip() for ln in section.group(1).splitlines()
            if re.match(r"^\s*[-*]\s+\S", ln)]


#: Commands this may run. An ALLOWLIST, because a denylist of destructive things is
#: never finished and the cost of one gap is somebody else's uncommitted work.
#:
#: Measured on a consumer on 2026-09-15, before this existed: a criterion carried
#: `git stash push` in its backticks, this executor ran it, and it pushed SEVEN entries
#: onto a stash stack shared by six worktrees — one of them carrying twenty uncommitted
#: CHANGELOG lines, which left the tree. The docstring of this file already said
#: "running commands out of a document is the risk it is", and saying it is not
#: protecting against it.
#:
#: Read-only tools, plus the test runners a criterion legitimately needs. `go test`
#: writes a build cache and `pytest` writes `__pycache__`; that is the cost of asking
#: whether a test passes, and it is contained.
_ALLOWED_COMMANDS = frozenset({
    "grep", "rg", "cat", "ls", "find", "wc", "test", "head", "tail", "awk", "sort",
    "uniq", "cut", "tr", "diff", "echo", "printf", "true", "false", "jq", "stat",
    "basename", "dirname", "realpath", "readlink", "sed", "python3", "python",
    "node", "go", "cargo", "pytest", "npm", "npx", "make", "task", "bash", "sh",
    "xargs", "date", "pwd", "env", "which", "command", "yq", "helm",
    "kubectl", "docker", "gofmt", "ruff", "shellcheck",
    # A pure builtin: it changes this shell's working directory and touches nothing
    # else. Refusing it made every criterion scoped to a module unrunnable — measured
    # on a consumer 2026-09-15, 5 of one item's 8 criteria, on the item chosen BECAUSE
    # the chain had never been its obstacle. `(cd api && go test ./...)` is how a
    # workspace repository says "in this module", and there is no other way to say it.
    "cd",
    # Creates a scratch path under the system temp directory and touches nothing else.
    # It is how a criterion builds the negative control that makes it discriminate, and
    # refusing it cost 7 clauses on one consumer item.
    "mktemp",
    # A builtin that ends the subprocess we spawned. It has no reach beyond it.
    "exit",
})

#: `git` subcommands that only read. `stash`, `checkout`, `reset`, `clean`, `worktree`,
#: `push`, `commit`, `merge`, `rebase`, `restore` and `switch` are absent on purpose —
#: every one of them moves somebody's work.
_ALLOWED_GIT = frozenset({
    "log", "show", "diff", "status", "rev-parse", "rev-list", "ls-files", "ls-tree",
    "cat-file", "describe", "blame", "shortlog", "grep", "config", "branch", "tag",
    "remote", "count-objects", "archive", "for-each-ref", "symbolic-ref",
})

#: A flag that turns a reading command into a writing one.
_WRITING_FLAGS = ("-i", "--in-place", "-X POST", "-X PUT", "-X DELETE", "--delete",
                  "-d ", "--force", "--hard", "-o ", "--output")


#: What a command name can look like. Deliberately narrow: a leading letter, underscore,
#: dot or slash, then the characters a path or a binary name may carry. A bare number, a
#: word with a comma in it, or a quoted fragment is an operand, not a command.
#: Commands that run something this checker cannot see. `sudo` escalates; `eval`,
#: `exec`, `source` and `.` evaluate text as code — so whatever the allowlist says
#: about the words after them, it is not what runs.
_ESCALATES_OR_EVALUATES = frozenset({"sudo", "eval", "exec", "source", "."})

#: Commands whose effect is outside this process: the filesystem, a machine, a network.
#: Disjoint from the set above, and refused for a DIFFERENT reason — both used to
#: return the identical sentence, so a reader could not tell which rule had fired or
#: why, and the two are tested in different places in the chain.
_CHANGES_THE_WORLD = frozenset({
    "rm", "mv", "cp", "chmod", "chown", "kill", "curl", "wget", "ssh",
    "scp", "dd", "mkfs", "shutdown", "reboot",
})

_COMMAND_NAME_RE = re.compile(r"[A-Za-z_./][\w.@/+-]*")

#: An OUTPUT redirect: `>`, `>>`, `2>`, `1>>`, `&>`. Requires a destination after it, so
#: a comparison (`-gt 3`) and an awk program's `$1 > 2` — which live inside quotes and
#: are stripped before this runs — do not match. `<` is absent on purpose: it reads.
_REDIRECT_RE = re.compile(r"(?:\d|&)?>>?\s*[^\s|&;)]+")


def _without_quoted(text: str) -> str:
    """`text` with quoted spans blanked, preserving length.

    A `>` inside `awk '$1 > 2'` or `grep 'a > b'` is data, not a redirect. Blanking
    rather than deleting keeps offsets meaningful for anything that reports a position.
    """
    return re.sub(r"'[^']*'|\"[^\"]*\"", lambda m: " " * len(m.group(0)), text)

#: Commands whose ARGUMENT is another command. Each is harmless alone and transparent to
#: whatever it runs, so the payload has to be read rather than inherited.
_WRAPPERS = frozenset({"timeout", "env", "nice", "nohup", "stdbuf", "xargs", "command"})


def _refused_head(part: str) -> str:
    """Why this ONE command is refused, or "" when it reads.

    Extracted from `_refused_command`, which measured cyclomatic complexity 35: the
    splitting, this per-command decision and the writing-flag sweep in one body. Pure
    code movement — the block below is the loop body that was there, for one token.

    Every early `continue` became an early `return ""`, which says the same thing: this
    fragment is not a command, so it refuses nothing.
    """
    words = part.strip().split()
    if not words:
        return ""
    head = words[0].strip("'\"")
    # A fragment starting with a flag or a comparison operator is the tail of a
    # command already checked — `-eq 3` after `$(…)` closed. Not a command.
    if head.startswith("-") or head in ("then", "else", "fi", "do", "done", "!"):
        return ""
    # A token the shell could not execute as a command is not one. After a split on
    # `$(`, `)` and `&&`, the leftovers are operands — `1` from `-eq 1`, `ctx,` from
    # inside a grep pattern, `e-s` from a broken word. Refusing them reported a
    # policy decision about something that was never a command, and on a consumer
    # 2026-09-15 that was the whole remaining refusal set for an item: 6 of 12
    # clauses, none of them a command at all.
    #
    # Skipping is safe in the direction that matters: bash would not run these
    # either, and every REAL command on the line is still checked.
    if not _COMMAND_NAME_RE.fullmatch(head):
        return ""
    if head in _ESCALATES_OR_EVALUATES:
        return (f"{head!r} runs something this checker cannot read — it escalates or "
                f"evaluates, so the allowlist below says nothing about what happens")
    # A wrapper runs ANOTHER command, so allowing the wrapper without reading its
    # payload is how `timeout 60 rm -rf /` would have walked through the allowlist.
    # `env` was already on the list and carried exactly that hole. The payload is
    # re-checked as its own command; the wrapper's own flags are skipped.
    if head in _WRAPPERS:
        payload = [w for w in words[1:]
                   if not w.startswith("-") and not w.replace(".", "").isdigit()
                   and "=" not in w]
        if payload:
            refused = _refused_command(" ".join(payload))
            if refused:
                return refused
        return ""
    # `python3 -c` and `node -e` execute arbitrary code, exactly as `bash -c` does.
    # The difference is that a shell script can be unwrapped and inspected while a
    # Python one cannot, so the only honest answer for it is no.
    if head in ("python3", "python", "node", "ruby", "perl") and any(
            w in ("-c", "-e", "--eval", "--command") for w in words[1:]):
        return f"`{head} -c` executes arbitrary code; this will not run it"
    if head == "git":
        sub = next((w for w in words[1:] if not w.startswith("-")), "")
        # `git hash-object` computes a hash and writes nothing UNLESS `-w` is given,
        # which is what stores the object. The blanket refusal charged the safe form
        # for the dangerous one, and a criterion pinning a file by its hash is a
        # common and entirely read-only shape.
        if sub == "hash-object" and "-w" not in words[1:]:
            return ""
        if sub and sub not in _ALLOWED_GIT:
            return f"`git {sub}` moves work; this runs only reading subcommands"
        return ""
    if head in _CHANGES_THE_WORLD:
        return (f"{head!r} changes something outside this process — a file, a machine, "
                f"a network — and a criterion is meant to READ")
    # `tee` WRITES. It sat on the allowlist of "readable commands" beside `cat` and
    # `grep`, and `… | tee ~/.bashrc` is a write through a pipe that no redirect
    # check would have caught either. Its only purpose is to write.
    if head == "tee":
        return "'tee' writes a file; this runs only commands that read"
    if head and head not in _ALLOWED_COMMANDS and "=" not in head:
        # A path to a binary the criterion built is the common legitimate case —
        # `/tmp/project-cli quality --list` appears throughout a real registry. It is
        # still refused, and the trade is deliberate: that binary can do anything,
        # and "not verified" is an honest answer while "ran something unknown
        # against your tree" is not. The reader is told precisely this, so they can
        # run it themselves if they choose.
        if head.startswith("/") or head.startswith("./"):
            return (f"{head!r} is a binary this will not run unattended — run it "
                    "yourself if you trust it")
        # A refusal that names no way forward is one an author routes around, and this one is
        # reached most often by somebody counting lines. Measured on a three-line file:
        # `grep -c .` returns 2 when a line is blank (it skips them, which is wrong for a
        # BUDGET), `wc -l <` returns 2 with no trailing newline (it counts newlines),
        # `awk "END{print NR}"` is correct and was refused by the tokenizer until 2026-09-23,
        # and `grep -c ""` is correct and was always accepted while being named nowhere. So the
        # tool steered authors from a wrong instrument to a slightly-wrong one (#188).
        return (f"{head!r} is not on the allowlist of readable commands. "
                f'To count lines, `grep -c ""` is exact — `grep -c .` skips blank lines and '
                f"`wc -l <` undercounts a file with no trailing newline.")
    return ""


#: An interpreter whose quoted argument is a PROGRAM rather than a command list. All three read;
#: `sed -i` writes and is caught by `_WRITING_FLAGS` against the unmasked span.
_READONLY_PROGRAM_RE = re.compile(
    r"\b(awk|sed|jq)\s+(?:-[\w-]+\s+)*(['\"])(?:(?!\2).)*\2", re.DOTALL)


def _refused_command(span: str) -> str:
    """"" when the span is safe to run, else the reason it is not.

    Every token that looks like a command is checked, not only the first: a criterion
    writes `bash -c 'test $(...) -eq 1'` and the interesting command is inside. Pipes,
    `&&`, `;` and `$( )` all introduce another one.
    """
    # `bash -c '<script>'` hides its real commands inside the quotes, and a split that
    # does not enter them lets `bash -c 'git stash && …'` through — which is the exact
    # command that emptied a consumer's stash stack. Unwrap first, recursively.
    unwrapped = re.sub(r"\b(?:bash|sh)\s+-c\s+(['\"])(.*?)\1", r" ; \2 ; ", span,
                       flags=re.DOTALL)
    # `(` opens a subshell and therefore a new command. Splitting only on `)` left the
    # opening paren glued to the word after it, so `(cd api && …)` was refused as the
    # unknown command `(cd` — a parsing miss reported as a policy decision, which is
    # the worst way to be wrong: the reader is told the command is forbidden when it
    # was never read.
    # OUTPUT REDIRECTION, checked before anything is split. `>` is not in the token
    # separator set below, so a redirect stayed glued to the operands of a command that
    # had already passed: `cat go.mod > /etc/hosts` has head `cat`, which is on the
    # allowlist, and the write went unread. Every form writes a path the DOCUMENT chose,
    # on the machine running the check — and the criteria are authored by whoever wrote
    # the plan, which is the trust boundary this whole allowlist exists to hold.
    #
    # `<` is deliberately absent: an input redirect reads. So is `>` inside an awk or
    # jq program, which `_REDIRECT_RE` avoids by requiring the operator to sit outside
    # quotes and be followed by a path rather than a number-and-brace.
    redirect = _REDIRECT_RE.search(_without_quoted(unwrapped))
    if redirect:
        return (f"{redirect.group(0).strip()!r} redirects output to a file; this runs "
                f"only commands that read")

    # AN INTERPRETER'S PROGRAM IS NOT A LIST OF COMMANDS.
    #
    # The split below separates on `{` and `}`, so `awk "END{print NR}"` became
    # `awk "END` / `print NR` / `"` and `print` landed in head position — refused as an unknown
    # command. `awk` is read-only and `print` is an awk keyword. The cost was specific: an author
    # who notices that `grep -c .` skips blank lines (wrong for a line BUDGET) reaches for
    # `awk "END{print NR}"`, which is correct, and the tool refused it while accepting `wc -l <`,
    # which undercounts a file with no trailing newline. It steered authors from a wrong
    # instrument to a slightly-wrong one (#188).
    #
    # Masked rather than removed from the separator set: dropping `{`/`}` entirely would leave
    # `{ rm -rf /; }` with heads `['{', '}']` and `rm` never read — measured, and a security
    # regression in the file whose job is that boundary. A writing FLAG is still caught, because
    # `_WRITING_FLAGS` is checked against the original `span` below rather than against this.
    unwrapped = _READONLY_PROGRAM_RE.sub(r"\1 PROGRAM", unwrapped)
    tokens = re.split(r"[|;&\n(]|\$\(|\)|`|\{|\}", unwrapped)
    for part in tokens:
        refused = _refused_head(part)
        if refused:
            return refused

    lowered = span.lower()
    for flag in _WRITING_FLAGS:
        if flag.strip() and flag.lower() in lowered:
            return f"carries {flag.strip()!r}, which writes"
    return ""


#: A criterion that declares itself a GUARD. These must pass today and after the work —
#: that is what a guard is — and reporting them beside a real defect with the same
#: sentence destroys the distinction that matters.
#:
#: Measured on a consumer across 16 briefs:
#:
#:     B-029 AC-007  "the declared non-goal holds"                  -> guard
#:     B-020 AC-006  "the declared terminal sets are untouched"     -> guard
#:     B-023 AC-011  "nothing stops compiling, suites stay green"   -> guard
#:     B-012 AC-001  "the four divergences are gone"                -> DEFECT
#:
#: The first three passing today is the criterion working. The fourth passing today is
#: an item that closes on work nobody did. `test -s store.go` asserting a file still
#: exists would be a broken item if it failed today.
#:
#: The label is read from the criterion's own words because the briefs already carry it,
#: and a judge kept one of these deliberately for that reason. Detection is deliberately
#: narrow: without a label a criterion is counted as a defect, which is the safe
#: direction — a defect called a guard is silence, a guard called a defect is a question.
_GUARD_RE = re.compile(
    r"\b(non-goal|untouched|unchanged|stays?\s+green|stay\s+the\s+same|remains?\s+"
    r"(?:green|valid|true|intact)|still\s+(?:compiles?|passes|exists?|holds?)|"
    r"nothing\s+(?:stops|breaks|regress\w*)|no\s+regression|keeps?\s+working|"
    r"continues?\s+to\s+\w+)\b", re.IGNORECASE)


#: Commands that are complete with no argument. Everything else needs one, because a
#: bare tool name inside backticks is prose naming a tool, not a command to run.
_SELF_SUFFICIENT = frozenset({"true", "false", "pwd", "date", "whoami"})


def _is_a_command(span: str) -> bool:
    """Is this span something to RUN, or a tool being named in a sentence?

    Measured on a consumer's B-012: the criterion says the gate "moved the numbers it
    checks" and mentions `awk` and `diff` in the prose around the command. Both sit in
    backticks, both match the runnable vocabulary, and both were executed — `awk` alone
    exits 0 and was reported as a clause that already passes, inflating the count of
    inert clauses with artefacts of this parser.

    A tool name is one token. A command has an argument, an operator or a pipe.
    """
    tokens = span.split()
    if len(tokens) >= 2:
        return True
    return bool(tokens) and tokens[0] in _SELF_SUFFICIENT


def _clauses_of(bullet: str) -> list[tuple[str, str]]:
    """(command, its own expectation) for every runnable span, in order.

    This returned only the first span until 2026-09-14, so the second half of
    `<gate exists> AND <test passes>` was never run at all — not merely folded into one
    verdict, but silently skipped. A clause nobody executes cannot be found vacuous.

    The expectation is read from the text that FOLLOWS each span, up to the next one.
    `` `a` prints 1 AND `b` exits 0 `` states two different expectations, and applying
    the bullet's first one to both made a clause that exits 0 read as failing — the
    exact opposite of the finding this decomposition exists to surface.
    """
    spans = list(_COMMAND_RE.finditer(bullet))
    out: list[tuple[str, str]] = []
    for n, match in enumerate(spans):
        command = match.group(1)
        if not _RUNNABLE.search(command):
            continue
        if not _is_a_command(command):
            continue
        stop = spans[n + 1].start() if n + 1 < len(spans) else len(bullet)
        following = bullet[match.end():stop]
        expectation = _EXPECT_RE.search(following)
        if expectation:
            # The VERB, not only the value. `exits 0` and `prints 0` are different
            # questions about the same number, and deciding from the command text
            # instead read `true` as having nothing to do with exit codes.
            verb = expectation.group(1).lower()
            kind = "exit" if verb.startswith("exit") else "print"
            # A stated bound travels WITH the expectation — `print:>=4` — rather than in a
            # second channel. One string reaches `_decide`, so there is no way for the two
            # to arrive out of step.
            bound = _bound_of(following) if kind == "print" else None
            value = (f"{bound[0]}{bound[1]}" if bound
                     else expectation.group(2).strip())
            out.append((command, f"{kind}:{value}"))
        else:
            out.append((command, ""))
    return out


def _bullet_expectation(bullet: str) -> str:
    """The bullet's own expectation, used when a clause states none of its own."""
    match = _EXPECT_RE.search(bullet)
    if not match:
        return ""
    verb = match.group(1).lower()
    return f"{'exit' if verb.startswith('exit') else 'print'}:{match.group(2).strip()}"


#: A runner SAYING it ran nothing. Not "produced no output" — plenty of correct commands
#: are silent (`test -f x`, `git diff --quiet`) and silence is their answer. These are
#: literal statements by the tool that it measured nothing, and a clause judged only by
#: its exit code reads them as a pass.
#:
#: Named by a consumer session 2026-09-15 as the class nobody is counting: "the honest
#: statement about today is not 24 defects found; it is 24 found and an unknown number
#: that returned exit 0." Its four examples were a `grep` honouring `.gitignore`, a `cd`
#: failing into the original directory, a `\s` crossing a newline, and a `find -newermt`
#: window returning zero over a file inside it — every one found by accident while
#: looking for something else.
_MEASURED_NOTHING_RE = re.compile(
    r"\bno tests? (?:to run|ran|files?)\b|\[no test files\]|"
    r"\bcollected 0 items\b|\brunning 0 tests\b|\b0 tests? (?:ran|executed)\b|"
    r"\bno files? (?:matched|found)\b|\bnothing to do\b",
    re.IGNORECASE)


def _bound_of(text: str) -> tuple[str, int] | None:
    """The comparator a criterion states, when it states one rather than a value.

    Returns `(">=", 4)` for "prints 4 or more", "prints at least 4" and "prints >= 4".
    None when the text names a plain value or nothing this recognises — and the caller
    then falls back to equality, or to "could not decide", never to a guess.
    """
    match = _BOUND_RE.search(text)
    if match is None:
        return None
    word = (match.group("word") or "").lower().replace("  ", " ")
    tail = (match.group("tail") or "").lower()
    op = match.group("op") or ""
    if op in (">=", ">", "<=", "<"):
        return op, int(match.group("num"))
    if word in ("at least", "no fewer than") or "more" in tail or "greater" in tail \
            or "higher" in tail:
        return ">=", int(match.group("num"))
    if word in ("at most", "no more than") or "fewer" in tail or "less" in tail \
            or "lower" in tail:
        return "<=", int(match.group("num"))
    return None


def _decide(result, expected: str) -> tuple[bool | None, str]:
    """Does this clause pass RIGHT NOW?

    `expected` is `exit:<code>` or `print:<value>`, or "" when the bullet does not say.

    Deliberately conservative. When the text does not state what it expects clearly
    enough to compare, the answer is None — "could not decide" — and never False.
    Reporting a clause as sound because the comparison was too hard is the failure this
    file exists to end, one level up.
    """
    kind, _, value = expected.partition(":")
    #: A tool that announced it ran nothing has not answered the question, whatever it
    #: exited with. `None` rather than `False`, because the criterion may be perfectly
    #: sound against a tree where the test exists — what is unknown is today's answer,
    #: and "could not decide" is the honest word for that.
    said_nothing = _MEASURED_NOTHING_RE.search(
        f"{result.stdout or ''}\n{getattr(result, 'stderr', '') or ''}")
    if kind == "exit":
        code = result.exit_code
        if str(code) == value:
            if said_nothing:
                return None, (f"exits {code} as asked, but the runner reports it executed "
                              f"nothing — the exit code is not an answer to this")
            return True, f"exits {code} today, which is what it asks for"
        return False, f"exits {code} today, expects {value}"
    if said_nothing and result.exit_code == 0:
        return None, ("exit 0 today, and the runner reports it executed nothing — "
                      "the criterion did not measure what it claims to")
    # THE ASSERTION DECIDES, and the exit code is context.
    #
    # This returned False on any non-zero exit before the output was ever compared, and this
    # ecosystem writes `… | grep -c pattern` prints `0` routinely — a form that prints `0` and
    # exits `1`. So such a criterion read `fails today` in the FIXED state exactly as in the
    # broken one: not discriminating, stuck. Measured on one consumer plan, this and the awk
    # tokenizer left six of thirteen criteria unable to flip, while the plan's own central
    # metric counted `[fails today]` going to zero — unsatisfiable by construction (#188).
    #
    # A criterion that states no expected output is still exit-code-only, below. The two are
    # different measurements, and reading one as the other is this file's own subject.
    if not value:
        if result.exit_code != 0:
            return False, "exits non-zero today, and the text states no expected output"
        return None, "exit 0 today, and the text does not state an expected output"
    out = result.stdout.strip()
    #: Carried into every verdict below, so a reader can see that a command exited non-zero and
    #: its asserted output held anyway. Hiding it would trade one confusion for another.
    exit_note = f"exit {result.exit_code}"
    #: A stated BOUND is compared as one. Comparing `prints 4 or more` for equality made a
    #: correct `6` read as a failure — and worse than the false verdict is its direction:
    #: the check reported "discriminates" because the number DIFFERED, not because the
    #: criterion was unmet. A discrimination check satisfied by difference measures
    #: nothing about the criterion.
    bound_match = re.fullmatch(r"(>=|<=|>|<)(\d+)", value)
    if bound_match:
        op, limit = bound_match.group(1), int(bound_match.group(2))
        first = out.splitlines()[0] if out.splitlines() else ""
        try:
            actual = int(first.strip())
        except ValueError:
            return None, (f"states a bound ({op} {limit}) and prints {first[:30]!r}, "
                          f"which is not a number to compare")
        ok = {">=": actual >= limit, ">": actual > limit,
              "<=": actual <= limit, "<": actual < limit}[op]
        if ok:
            return True, (f"already prints {actual}, which satisfies {op} {limit} "
                          f"({exit_note})")
        return False, f"prints {actual} today, needs {op} {limit} ({exit_note})"
    if out == value or out.splitlines()[:1] == [value]:
        return True, f"already prints {value!r} ({exit_note})"
    return False, f"prints {out[:40]!r}, expects {value!r} ({exit_note})"


def run(brief: Path, repo_root: Path, timeout: float = 60.0) -> Report:
    rep = Report()
    rep.head, rep.dirty = _tree_state(repo_root)
    for bullet in _bullets(brief.read_text(encoding="utf-8-sig")):
        r = Result(criterion=bullet[:110], is_guard=bool(_GUARD_RE.search(bullet)))
        if _UNRESOLVED.search(bullet):
            r.note = "carries an unresolved placeholder — cannot run whatever it names"
            rep.results.append(r)
            continue
        clauses = _clauses_of(bullet)
        if not clauses:
            r.note = "names no runnable command"
            rep.results.append(r)
            continue
        for command, clause_expected in clauses:
            expected = clause_expected or _bullet_expectation(bullet)
            c = Clause(command=command)
            # Refused BEFORE the subprocess, and never counted as sound. A clause this
            # will not run is a clause nobody verified — which is the honest answer, and
            # it is the one that keeps a read-only REVIEW stage actually read-only.
            refusal = _refused_command(command)
            if refusal:
                c.note = f"NOT RUN — {refusal}"
                r.clauses.append(c)
                continue
            try:
                proc = subprocess.run(["bash", "-c", command], cwd=str(repo_root),
                                      capture_output=True, text=True, timeout=timeout,
                                      check=False)
            except subprocess.TimeoutExpired:
                c.note = f"did not finish within {timeout:.0f}s"
                r.clauses.append(c)
                continue
            except OSError as exc:
                c.note = f"could not run: {exc}"
                r.clauses.append(c)
                continue
            c.ran = True
            c.exit_code = proc.returncode
            c.stdout = proc.stdout[:400]
            # The stated expectation belongs to the whole bullet, so it is applied to
            # each clause. A clause that exits 0 while the bullet expects `0` is the
            # `[no tests to run]` shape, whatever the other clause did.
            c.passes_today, c.note = _decide(c, expected)
            r.clauses.append(c)
        rep.results.append(r)
    return rep


def render(rep: Report, brief: Path) -> str:
    stamp = (f"read against {rep.head}" + (" · working tree DIRTY" if rep.dirty else "")
             if rep.head else "read against an unversioned tree")
    lines = [f"acceptance criteria — {brief.name}", f"  {stamp}", ""]
    for r in rep.results:
        if r.is_guard and r.passing_clauses:
            mark = "guard, by design"
        else:
            mark = {True: "PASSES TODAY", False: "fails today  ", None: "undecidable  "}[
                r.passes_today] if r.ran else "did not run  "
        lines.append(f"  [{mark}] {r.criterion[:80]}")
        if r.note:
            lines.append(f"                 {r.note}")
        # A conjunction that FAILS today can still carry a clause that passes, and that
        # clause goes into the future unchecked. Naming it is the whole point of reading
        # the halves separately.
        if len(r.clauses) > 1:
            for n, c in enumerate(r.clauses, 1):
                cm = {True: "passes", False: "fails ", None: "?     "}[c.passes_today] \
                    if c.ran else "no run"
                flag = ""
                if c.passes_today is True and r.passes_today is not True:
                    flag = ("  <- passes by design (guard)" if r.is_guard else
                            "  <- already passes; will pass after the work too")
                lines.append(f"                 clause {n} [{cm}] {c.command[:52]}{flag}")
    lines.append("")
    n = len(rep.results)
    if rep.guards:
        lines += [f"{len(rep.guards)} criterion(s) pass BY DESIGN — they declare "
                  "themselves guards:", ""]
        for r in rep.guards:
            lines.append(f"  · {r.criterion[:86]}")
        lines += ["",
                  "  A guard must pass today and after the work; that is what it is for.",
                  "  It is reported here and NOT counted as a defect, because reporting",
                  "  it beside one destroys the distinction that matters.",
                  ""]
    if rep.already_passing:
        whole = sum(1 for r in rep.already_passing if r.passes_today is True)
        partial = len(rep.already_passing) - whole
        lines += [
            f"REFUSED: {len(rep.already_passing)} of {n} criteria carry something that "
            "already passes.",
            "",
            "  A criterion that passes before the work cannot tell a finished item from",
            "  an unstarted one. It will report success whatever is built, including",
            "  nothing.",
        ]
        if partial:
            lines += [
                "",
                f"  {partial} of those FAIL as a whole today, and that is the harder case:",
                "  one clause is vacuous and another fails for an unrelated reason, so a",
                "  single verdict over the conjunction calls the criterion sound. When the",
                "  failing half is built, the whole thing passes with the vacuous half",
                "  measuring nothing.",
            ]
    if rep.refused:
        lines += ["", f"{len(rep.refused)} criterion(s) carry a clause this REFUSED to "
                  "run:", ""]
        for r in rep.refused:
            for c in r.clauses:
                if c.note.startswith("NOT RUN"):
                    lines.append(f"  · {c.command[:60]}")
                    lines.append(f"      {c.note[9:]}")
        lines += ["",
                  "  These are unverified, not sound. This executes commands out of a",
                  "  document, and a criterion carrying `git stash` once pushed seven",
                  "  entries onto a stack shared by six worktrees — one carrying twenty",
                  "  uncommitted lines, which left the tree. Read them and run them",
                  "  yourself if you trust them.",
                  ""]
    if rep.already_passing:
        pass
    elif rep.unrunnable or rep.undecidable:
        lines += [f"{len(rep.unrunnable)} could not run, {len(rep.undecidable)} could not "
                  "be decided. Neither is a pass."]
    else:
        lines.append(f"All {n} criteria fail today — each has something to prove."
                     + (f" ({len(rep.guards)} guard(s) excluded)" if rep.guards else ""))
    lines += ["", "  This ran each CLAUSE once, against the tree as it is. It does not",
              "  check that a criterion REJECTS a wrong implementation, which is the state",
              "  that catches one measuring a name rather than a behaviour.",
              "",
              "  And it does not survive the tree it measured. A criterion that",
              "  discriminated yesterday can be inert today because something else",
              "  changed — a config line, a file appearing, a dependency installed. Run",
              "  this against the tree you are about to implement on, not against a",
              "  record of a tree that has moved."]
    if rep.dirty:
        lines += ["", "  The working tree is DIRTY, so some of these answers come from",
                  "  uncommitted changes and will not reproduce from the commit alone."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refuse acceptance criteria that already pass.")
    parser.add_argument("brief", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.brief.is_file():
        print(f"NOT MEASURED: no brief at {args.brief}", file=sys.stderr)
        return 2

    rep = run(args.brief, args.repo_root.resolve(), args.timeout)
    if not rep.results:
        print(f"NOT MEASURED: {args.brief} has no acceptance-criteria section",
              file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"head": rep.head, "dirty": rep.dirty, "results": [
            {"criterion": r.criterion, "ran": r.ran, "passes_today": r.passes_today,
             "note": r.note, "is_guard": r.is_guard,
             "clauses": [{"command": c.command, "ran": c.ran,
                          "exit_code": c.exit_code, "passes_today": c.passes_today,
                          "note": c.note} for c in r.clauses]}
            for r in rep.results]}, indent=2, ensure_ascii=False))
    else:
        print(render(rep, args.brief), end="")
    return 1 if (rep.already_passing or rep.unrunnable or rep.undecidable) else 0


if __name__ == "__main__":
    raise SystemExit(main())

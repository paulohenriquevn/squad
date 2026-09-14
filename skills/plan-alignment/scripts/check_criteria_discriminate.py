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
_EXPECT_RE = re.compile(r"\b(prints|outputs|exits?|returns)\s+`?([^`\s.,]+)", re.I)


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
    """(HEAD sha, is the working tree dirty). Empty sha when this is not a repository.

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


def _bullets(text: str) -> list[str]:
    section = re.search(r"^##+\s*.*Acceptance.*$([\s\S]*?)(?=^##|\Z)", text, re.M | re.I)
    if not section:
        return []
    return [ln.strip() for ln in section.group(1).splitlines()
            if re.match(r"^\s*[-*]\s+\S", ln)]


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
            out.append((command, f"{'exit' if verb.startswith('exit') else 'print'}:"
                                 f"{expectation.group(2).strip()}"))
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


def _decide(result, expected: str) -> tuple[bool | None, str]:
    """Does this clause pass RIGHT NOW?

    `expected` is `exit:<code>` or `print:<value>`, or "" when the bullet does not say.

    Deliberately conservative. When the text does not state what it expects clearly
    enough to compare, the answer is None — "could not decide" — and never False.
    Reporting a clause as sound because the comparison was too hard is the failure this
    file exists to end, one level up.
    """
    kind, _, value = expected.partition(":")
    if kind == "exit":
        code = result.exit_code
        if str(code) == value:
            return True, f"exits {code} today, which is what it asks for"
        return False, f"exits {code} today, expects {value}"
    if result.exit_code != 0:
        return False, "exits non-zero today"
    if not value:
        return None, "exit 0 today, and the text does not state an expected output"
    out = result.stdout.strip()
    if out == value or out.splitlines()[:1] == [value]:
        return True, f"already prints {value!r}"
    return False, f"prints {out[:40]!r}, expects {value!r}"


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

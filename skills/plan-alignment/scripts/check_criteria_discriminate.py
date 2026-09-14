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
class Result:
    criterion: str
    command: str = ""
    ran: bool = False
    exit_code: int | None = None
    stdout: str = ""
    passes_today: bool | None = None      # None: could not decide
    note: str = ""


@dataclass
class Report:
    results: list = field(default_factory=list)

    @property
    def already_passing(self) -> list:
        return [r for r in self.results if r.passes_today is True]

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


def _command_of(bullet: str) -> str:
    """The runnable span, or "" when the bullet names none."""
    spans = _COMMAND_RE.findall(bullet)
    for span in spans:
        if _RUNNABLE.search(span):
            return span
    return ""


def _expected(bullet: str) -> str:
    match = _EXPECT_RE.search(bullet)
    return match.group(2).strip() if match else ""


def _decide(result: Result, expected: str) -> tuple[bool | None, str]:
    """Does this criterion pass RIGHT NOW?

    Deliberately conservative. When the bullet does not state what it expects clearly
    enough to compare, the answer is None — "could not decide" — and never False.
    Reporting a criterion as sound because the comparison was too hard is the failure
    this file exists to end, one level up.
    """
    if result.exit_code != 0:
        return False, "exits non-zero today"
    if not expected:
        return None, "exit 0 today, and the bullet does not state an expected output"
    out = result.stdout.strip()
    if expected.lower() in ("0",) and "exit" in result.criterion.lower():
        return True, "exits 0 today, which is what it asks for"
    if out == expected or out.splitlines()[:1] == [expected]:
        return True, f"already prints {expected!r}"
    return False, f"prints {out[:40]!r}, expects {expected!r}"


def run(brief: Path, repo_root: Path, timeout: float = 60.0) -> Report:
    rep = Report()
    for bullet in _bullets(brief.read_text(encoding="utf-8-sig")):
        r = Result(criterion=bullet[:110])
        if _UNRESOLVED.search(bullet):
            r.note = "carries an unresolved placeholder — cannot run whatever it names"
            rep.results.append(r)
            continue
        command = _command_of(bullet)
        if not command:
            r.note = "names no runnable command"
            rep.results.append(r)
            continue
        r.command = command
        try:
            proc = subprocess.run(["bash", "-c", command], cwd=str(repo_root),
                                  capture_output=True, text=True, timeout=timeout,
                                  check=False)
        except subprocess.TimeoutExpired:
            r.note = f"did not finish within {timeout:.0f}s"
            rep.results.append(r)
            continue
        except OSError as exc:
            r.note = f"could not run: {exc}"
            rep.results.append(r)
            continue
        r.ran = True
        r.exit_code = proc.returncode
        r.stdout = proc.stdout[:400]
        r.passes_today, r.note = _decide(r, _expected(bullet))
        rep.results.append(r)
    return rep


def render(rep: Report, brief: Path) -> str:
    lines = [f"acceptance criteria — {brief.name}", ""]
    for r in rep.results:
        mark = {True: "PASSES TODAY", False: "fails today  ", None: "undecidable  "}[
            r.passes_today] if r.ran else "did not run  "
        lines.append(f"  [{mark}] {r.criterion[:80]}")
        if r.note:
            lines.append(f"                 {r.note}")
    lines.append("")
    n = len(rep.results)
    if rep.already_passing:
        lines += [
            f"REFUSED: {len(rep.already_passing)} of {n} criteria already pass.",
            "",
            "  A criterion that passes before the work cannot tell a finished item from",
            "  an unstarted one. It will report success whatever is built, including",
            "  nothing.",
        ]
    elif rep.unrunnable or rep.undecidable:
        lines += [f"{len(rep.unrunnable)} could not run, {len(rep.undecidable)} could not "
                  "be decided. Neither is a pass."]
    else:
        lines.append(f"All {n} criteria fail today — each has something to prove.")
    lines += ["", "  This ran each criterion ONCE, against the tree as it is. It does not",
              "  check that a criterion REJECTS a wrong implementation, which is the state",
              "  that catches one measuring a name rather than a behaviour."]
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
        print(json.dumps({"results": [
            {"criterion": r.criterion, "command": r.command, "ran": r.ran,
             "exit_code": r.exit_code, "passes_today": r.passes_today, "note": r.note}
            for r in rep.results]}, indent=2, ensure_ascii=False))
    else:
        print(render(rep, args.brief), end="")
    return 1 if (rep.already_passing or rep.unrunnable or rep.undecidable) else 0


if __name__ == "__main__":
    raise SystemExit(main())

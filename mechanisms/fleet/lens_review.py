#!/usr/bin/env python3
"""Point the kit's own defect lenses at a diff, before the diff becomes history.

WHY THIS EXISTS
---------------

`kit_audit_workflow.js` carries six lenses. Each is a defect pattern this kit has
shipped more than once, and each quotes the measurement that makes it concrete —
an agent told *"look for silent failures"* finds prose, one told *"a matcher
reported a complete delta of 5 against a true 11"* finds matchers. It runs over
the whole repository, on a sweep, after the fact.

Measured 2026-09-03, in a single session, all by the same author:

- a guard whose predicate held whether the send worked or not, so the branch that
  reported success had never executed  → `guard-that-guards-nothing`
- a `finally` that ran a command and discarded the result, so a leaked worktree
  could not be explained                → `absence-as-answer`
- a fetch taken once per pass and reused as though it were current
- a workstation path in a versioned file, twice

Every one of those is on the list. The list had never been pointed at the diff
that introduced them.

WHAT IT DOES NOT DO
-------------------

Its findings do NOT block a landing. A model's opinion about a diff is not
grounds to stall an unattended fleet that has nobody to override it. They become
issues instead — through `file_findings.py`, which already refuses a claim with
no evidence and one the tracker already holds — which is the same loop the sweep
feeds. A defect caught at the diff and fixed next pass is the whole gain; a fleet
halted on a false positive at 3am is not.

THE LENSES ARE READ, NOT COPIED
-------------------------------

A second copy of a rule is this kit's second-most-found defect, found five times
in one day. The lenses are parsed out of the workflow file itself, and a parse
that comes back empty **raises** — reviewing a diff against zero lenses and
reporting nothing found is precisely what the first lens is about.

Usage:
    lens_review.py --repo /path/to/kit --branch fix/kit19-x
    lens_review.py --repo /path/to/kit --branch fix/kit19-x --out findings.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

#: Where the single copy of the lenses lives.
WORKFLOW = _HERE / "kit_audit_workflow.js"

#: `key: 'name',` followed by a backtick-delimited prompt. Deliberately anchored
#: on both, so a workflow that reshapes its literal fails loudly here instead of
#: quietly yielding fewer lenses than it has.
_LENS_RE = re.compile(r"key:\s*'([a-z-]+)',\s*\n\s*prompt:\s*`(.*?)`,\s*\n\s*\}",
                      re.DOTALL)


class LensesUnreadable(RuntimeError):
    """The lens list could not be parsed out of the workflow.

    Distinct from "there are no lenses". One of them means every diff reviewed
    from here on comes back clean without being looked at.
    """


@dataclass(frozen=True)
class Lens:
    key: str
    prompt: str


def lenses(workflow: Path = WORKFLOW) -> list[Lens]:
    """Every lens the workflow declares. Raises rather than returning `[]`."""
    try:
        source = workflow.read_text(encoding="utf-8")
    except OSError as exc:
        raise LensesUnreadable(f"{workflow} could not be read: {exc}") from exc
    found = [Lens(key, prompt) for key, prompt in _LENS_RE.findall(source)]
    if not found:
        raise LensesUnreadable(
            f"no lens matched in {workflow}. The workflow's literal has changed "
            f"shape, and every review from here would pass a diff nobody looked "
            f"at. Fix the parser or move the lenses to a file both readers share.")
    return found


_ASK = """\
You are reviewing ONE change to the Squad kit against ONE known defect pattern.

The pattern, with the measurements that make it concrete:

{lens}

---

Here is the diff. Judge ONLY what the diff introduces or leaves in place — not
the rest of the repository, which a separate sweep covers.

```diff
{diff}
```

---

Answer with JSON and nothing else:

{{"findings": [{{"title": "...", "file": "...", "line": 0,
                "evidence": "...", "why_it_matters": "..."}}]}}

`findings` is very often empty, and an empty list is the RIGHT answer for most
diffs. Report only what you can point at: `evidence` must quote the code or name
what you ran, not describe an impression. A finding you cannot anchor to a line
costs a maintainer's attention and teaches them to skim the next one.
"""


def review(diff: str, *, lenses: list[Lens],
           ask: Callable[[str], str] | None) -> tuple[list[dict], str]:
    """`(findings, a note about what did not run)`.

    A lens whose agent fails, or answers with prose, is NAMED in the note. It is
    never counted as "found nothing": a lens that did not run and a lens that ran
    clean are the same output otherwise, and that is the first pattern on the list.
    """
    if not diff.strip():
        return [], "no diff to review"
    notes: list[str] = []
    out: list[dict] = []
    for lens in lenses:
        if ask is None:
            notes.append(f"{lens.key}: no way to ask, so it did not run")
            continue
        try:
            answer = ask(_ASK.format(lens=lens.prompt, diff=diff[:60000]))
        except Exception as exc:  # noqa: BLE001 — one lens must not take the rest
            notes.append(f"{lens.key}: did not return ({exc})")
            continue
        try:
            payload = json.loads(_json_slice(answer))
        except (json.JSONDecodeError, ValueError):
            notes.append(f"{lens.key}: did not return JSON, so it did not run")
            continue
        for finding in payload.get("findings") or []:
            out.append({**finding, "lens": lens.key,
                        # Not a judgement that it is real — `file_findings` still
                        # applies its own refusals. It records only that this lens
                        # was not refuted here, because nothing tried to.
                        "verdict": {"refuted": False}})
    return out, "; ".join(notes)


def _json_slice(text: str) -> str:
    """The first `{...}` in an answer that may be wrapped in prose or a fence."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the answer")
    return text[start:end + 1]


class DiffUnavailable(RuntimeError):
    """The diff command failed, so there is no change set to review.

    `branch_diff` used to return `""` for this — an unknown branch, a missing
    `origin/workspace`, a repository that is not there — and `review()` reads an empty
    string as "no diff to review", which `main` prints as the result. The module's own
    docstring names this exact pattern as the first on its list: "a lens that did not run
    and a lens that ran clean are the same output otherwise". It applied to the diff too.
    """


def branch_diff(repo: Path, branch: str, *, base: str = "origin/workspace",
                timeout: int = 120) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "diff", f"{base}...{branch}"],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DiffUnavailable(f"`git diff {base}...{branch}` could not be run: {exc}") from exc
    if done.returncode != 0:
        raise DiffUnavailable(
            f"`git diff {base}...{branch}` exited {done.returncode}: "
            f"{(done.stderr or '').strip()[:300]}")
    return done.stdout


def _cli_ask(repo: Path) -> Callable[[str], str]:
    import claude_stream

    def ask(prompt: str) -> str:
        return claude_stream.ask(prompt, cwd=repo, timeout=600).text
    return ask


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--base", default="origin/workspace")
    ap.add_argument("--out", default="", help="write the findings as JSON here")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    try:
        the_lenses = lenses()
    except LensesUnreadable as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        diff = branch_diff(repo, args.branch, base=args.base)
    except DiffUnavailable as exc:
        print(f"did not run: {exc}", file=sys.stderr)
        return 2
    found, note = review(diff, lenses=the_lenses, ask=_cli_ask(repo))
    print(f"reviewed {args.branch} against {len(the_lenses)} lens(es): "
          f"{len(found)} finding(s)")
    if note:
        print(f"did not run: {note}")
    for finding in found:
        print(f"  [{finding.get('lens')}] {finding.get('title')} "
              f"({finding.get('file')}:{finding.get('line')})")
    if args.out:
        Path(args.out).write_text(json.dumps(found, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

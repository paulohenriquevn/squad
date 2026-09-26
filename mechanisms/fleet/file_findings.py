#!/usr/bin/env python3
"""Turn audit findings that survived refutation into issues a lane can take.

WHY THIS EXISTS
---------------

`kit_audit_workflow.js` hunts the kit for the patterns it has shipped more than
once, and puts every claim through an agent whose only job is to refute it. What
survives is returned — and returned to nobody. Measured 2026-09-03: the kit's
tracker held **zero** open issues while four real defects sat in a session report
that a person had written and never filed, and the fleet was idle because of it.

A finding mentioned and not filed is the worst of the three outcomes. It reads as
coverage, spends nobody's attention, and is never worked.

WHAT IT REFUSES
---------------

- A finding the refuter killed. Not "probably fine" — killed.
- A finding with no evidence, or naming no file. An issue without a measurement
  spends a maintainer's attention and teaches them to skim the next one.
- A finding the tracker already holds, open **or closed**. A closed issue is a
  decision somebody made, and re-filing it silently reopens a settled argument.
- Everything, when the tracker cannot be read. Without the existing issues there
  is no dedup, and filing without dedup turns one real defect into a duplicate on
  every run. `gh` missing is a reason to stop, never a reason to assume nothing
  is tracked.

Usage:
    file_findings.py --repo owner/name --findings audit.json
    file_findings.py --repo owner/name --findings audit.json --apply

Exit codes:
    0  every survivor is either filed or accounted for as a duplicate
    1  the tracker could not be read — nothing was filed
    2  invocation error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class TrackerUnavailable(RuntimeError):
    """The issue tracker could not be read.

    Distinct from "the tracker is empty". One of them means dedup is impossible.
    """


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def _overlap(a: str, b: str) -> float:
    """Word overlap, as a fraction of the shorter title.

    Deliberately crude. A cheap comparison that occasionally holds a real finding
    for a human to look at is a better failure than a clever one that lets a
    duplicate through — the duplicate costs a maintainer twice.
    """
    left, right = set(_normalise(a).split()), set(_normalise(b).split())
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


#: How many issues one `gh issue list` asks for. Read as a WINDOW, never as the
#: tracker: a response that fills it means the tracker is larger than this.
_ISSUE_PAGE = 300


def existing_issues(repo: str, *, timeout: int = 60) -> list[dict]:
    """Every issue in `repo`, open and closed. Raises rather than returning []."""
    try:
        done = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--state", "all",
             "--limit", str(_ISSUE_PAGE), "--json", "number,title,body,state"],
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, check=False)
    except FileNotFoundError as exc:
        raise TrackerUnavailable(
            f"`gh` is not installed, so {repo}'s issues cannot be read on this "
            f"machine. This is not the same as {repo} having none.") from exc
    except subprocess.SubprocessError as exc:
        raise TrackerUnavailable(f"`gh issue list` did not return: {exc}") from exc
    if done.returncode != 0:
        raise TrackerUnavailable(
            f"`gh issue list --repo {repo}` exited {done.returncode}: "
            f"{(done.stderr or '').strip()[:200]}")
    try:
        issues = json.loads(done.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise TrackerUnavailable(f"`gh` returned something that is not JSON: {exc}") from exc
    # A FULL page is not a complete read. `--limit 300` is a window, and `triage()`
    # treats whatever comes back as the whole tracker: once a repository passes 300
    # issues the oldest fall out, the anchor and title checks stop seeing them, and
    # `file_one` files a duplicate of an issue that already exists — silently, because
    # nothing compared the count against the limit. Refusing is right for the same
    # reason `TrackerUnavailable` is raised above: dedup over a partial tracker
    # under-reports, and under-reporting here means filing noise into the tracker.
    if len(issues) >= _ISSUE_PAGE:
        raise TrackerUnavailable(
            f"{repo} returned {len(issues)} issues, which is the {_ISSUE_PAGE} limit "
            f"this reader asks for — so the tracker is at least that large and the "
            f"oldest issues were NOT read. Deduplication over a partial tracker files "
            f"duplicates of issues that already exist. Raise the limit or page.")
    return issues


class Skip(NamedTuple):
    """One finding that was NOT filed, and everything the caller needs to act on it.

    `reason` alone was all this carried, so `run()` could tell the reader a duplicate
    existed and could do nothing about it — `comment_duplicate` and `already_commented`
    were written, tested for existence, and called from nowhere. The 'seen again'
    comment they implement never ran. Carrying the issue number is what lets the
    duplicate path DO something instead of only reporting.

    `related_issue` is None for the skips that are not duplicates (refuted, no
    evidence, names no file): there is no issue to comment on, and None says so.
    """

    finding: dict
    reason: str
    related_issue: int | None = None
    related_state: str | None = None


def triage(findings: list[dict], *, existing: list[dict],
           similarity: float = 0.6) -> tuple[list[dict], list[Skip]]:
    """`(to file, [Skip(...)])`. Pure."""
    keep: list[dict] = []
    skip: list[Skip] = []
    for finding in findings:
        verdict = finding.get("verdict") or {}
        if verdict.get("refuted"):
            skip.append(Skip(finding, "an agent refuted it; a killed claim is not a defect"))
            continue
        if not (finding.get("evidence") or "").strip():
            skip.append(Skip(finding, "no evidence — an issue without a measurement is noise"))
            continue
        if not (finding.get("file") or "").strip():
            skip.append(Skip(finding, "names no file, so nobody can go and look"))
            continue

        anchor = f"{finding['file']}:{finding.get('line')}" if finding.get("line") else finding["file"]
        duplicate: Skip | None = None
        for issue in existing:
            state = (issue.get("state") or "").lower() or None
            if anchor and anchor in (issue.get("body") or ""):
                duplicate = Skip(finding, f"#{issue['number']} already cites {anchor}",
                                 issue["number"], state)
                break
            if _overlap(finding.get("title", ""), issue.get("title", "")) >= similarity:
                duplicate = Skip(finding,
                                 f"#{issue['number']} says the same thing"
                                 f"{' and was closed' if state == 'closed' else ''}",
                                 issue["number"], state)
                break
        if duplicate:
            skip.append(duplicate)
            continue
        keep.append(finding)
    return keep, skip


_BODY = """\
## Impact

{why}

## Evidence

Found at `{anchor}`.

```
{evidence}
```

## How it was found

An automated sweep of {repo_hint} for the defect pattern **{lens}** — a shape this
kit has shipped more than once. The claim was then handed to a separate agent whose
only instruction was to **refute** it, defaulting to refuted when it could not
confirm the behaviour itself. It survived that attempt; that is why it is here and
most candidates are not.

A surviving claim is a reason to go and look, not a verdict. Read the file before
acting on it, and close this as invalid if the sweep misread the code — a false
positive filed honestly is cheaper than a real defect nobody wrote down.

---
Filed by `mechanisms/fleet/file_findings.py`. No secrets in this report.
"""


def body(finding: dict, *, repo_hint: str) -> str:
    anchor = (f"{finding['file']}:{finding['line']}" if finding.get("line")
              else finding.get("file", ""))
    return _BODY.format(why=finding.get("why_it_matters") or "(not stated by the sweep)",
                        anchor=anchor, evidence=finding.get("evidence", ""),
                        repo_hint=repo_hint, lens=finding.get("lens", "unspecified"))


def file_one(finding: dict, *, repo: str, apply: bool) -> tuple[bool, str]:
    title = finding.get("title", "").strip()[:120]
    if not apply:
        return True, f"dry-run: would file {title!r}"
    done = subprocess.run(
        ["gh", "issue", "create", "--repo", repo, "--title", title,
         "--body", body(finding, repo_hint="the Squad kit")],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, check=False)
    if done.returncode != 0:
        return False, f"could not file {title!r}: {(done.stderr or '').strip()[:160]}"
    return True, (done.stdout or "").strip()


def already_commented(repo: str, issue_number: int, anchor: str = "FINDING_DUPLICATE_V1",
                      *, timeout: int = 60) -> bool | None:
    """Whether a comment carrying `anchor` is already on the issue. None = could not ask.

    TRI-STATE, and the third value is the point. This returned `False` when `gh` was
    missing or the call raised, justified inline as "If we can't check, assume we haven't
    (don't spam on error)" — but False is precisely the value that lets the comment
    through. The guard failed OPEN while its comment claimed it failed closed, so the one
    thing standing between a re-detected finding and a comment every single run stopped
    standing there exactly when the tracker was unreachable.

    A check that did not run must block the comment, not authorise it.

    Args:
        repo: owner/name of the tracker
        issue_number: GitHub issue number
        anchor: Distinctive string in the comment to detect (default: FINDING_DUPLICATE_V1)
        timeout: Timeout for gh command

    Returns:
        True if we've already commented, False otherwise.
    """
    try:
        done = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", repo,
             "--json", "comments", "-q", ".comments[].body"],
                check=False,
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None

    if done.returncode != 0:
        return None

    comments = done.stdout or ""
    return anchor in comments


def comment_duplicate(repo: str, issue_number: int, anchor: str,
                      *, apply: bool = True, timeout: int = 60) -> tuple[bool, str]:
    """Post a 'seen again' comment on an existing (open or closed) issue.

    This is used when `triage()` detected that a finding matches an existing issue
    we already filed. Instead of filing a duplicate, we comment that the pattern
    was seen again in this run.

    Args:
        repo: owner/name of the tracker
        issue_number: GitHub issue number
        anchor: File:line anchor (e.g., "file.py:42") to include in comment
        apply: Whether to actually post (else dry-run)
        timeout: Timeout for gh command

    Returns:
        Tuple (success, message)
    """
    if not apply:
        return True, f"dry-run: would comment on #{issue_number}"

    # Check if we've already left a comment. `None` is "the tracker could not be asked",
    # and it blocks: commenting on the strength of a check that did not run is how one
    # unreachable tracker turns into a comment on every run.
    seen = already_commented(repo, issue_number)
    if seen is None:
        return False, (f"could not ask #{issue_number} whether it already carries this "
                       f"comment; not commenting rather than commenting blind")
    if seen:
        return True, f"already commented on #{issue_number} (suppressed duplicate)"

    comment_text = (
        f"**FINDING_DUPLICATE_V1** — This pattern was detected again at `{anchor}`. "
        f"The issue still tracks the problem. If you've since fixed it elsewhere, "
        f"please close and we'll stop reporting it."
    )

    try:
        done = subprocess.run(
            ["gh", "issue", "comment", str(issue_number), "--repo", repo,
             "--body", comment_text],
                check=False,
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        return False, f"could not comment on #{issue_number}: {exc}"

    if done.returncode != 0:
        return False, f"gh returned exit {done.returncode}: {(done.stderr or '').strip()[:160]}"

    return True, f"commented on #{issue_number}"


def run(findings: list[dict], *, repo: str, apply: bool) -> tuple[list[str], list[str], int]:
    try:
        existing = existing_issues(repo)
    except TrackerUnavailable as exc:
        # Nothing is filed. Without dedup, one real defect becomes a duplicate on
        # every run, and the noise is what makes a tracker stop being read.
        return [], [f"filed nothing: {exc}"], 1
    keep, skip = triage(findings, existing=existing)
    filed: list[str] = []
    notes: list[str] = []
    for entry in skip:
        note = f"{entry.finding.get('title', '?')[:70]}: {entry.reason}"
        if entry.related_issue is not None:
            # The 'seen again' comment. This is what the pair below was written for and
            # what nothing called: the duplicate path recorded a note and left the
            # tracker unaware the pattern had recurred. `comment_duplicate` carries its
            # own anti-spam guard and its own fail-closed check, so calling it here adds
            # no policy — it only stops throwing the work away.
            anchor = (f"{entry.finding.get('file')}:{entry.finding.get('line')}"
                      if entry.finding.get("line") else str(entry.finding.get("file")))
            _, said = comment_duplicate(repo, entry.related_issue, anchor, apply=apply)
            note = f"{note} — {said}"
        notes.append(note)
    for finding in keep:
        ok, line = file_one(finding, repo=repo, apply=apply)
        (filed if ok else notes).append(line)
    return filed, notes, 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/name of the tracker")
    ap.add_argument("--findings", required=True,
                    help="JSON from kit_audit_workflow: a list, or {survived: [...]}")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    try:
        payload = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read {args.findings}: {exc}", file=sys.stderr)
        return 2
    findings = payload.get("survived", []) if isinstance(payload, dict) else payload
    if not isinstance(findings, list):
        print("the findings file holds no list of findings", file=sys.stderr)
        return 2

    filed, notes, code = run(findings, repo=args.repo, apply=args.apply)
    # Said out loud in both directions. "the sweep found nothing" and "the sweep
    # did not run" have read the same on this kit before.
    print(f"swept {len(findings)} surviving finding(s): {len(filed)} filed, "
          f"{len(notes)} accounted for")
    for line in filed:
        print(f"  filed  : {line}")
    for line in notes:
        print(f"  skipped: {line}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

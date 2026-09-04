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


def existing_issues(repo: str, *, timeout: int = 60) -> list[dict]:
    """Every issue in `repo`, open and closed. Raises rather than returning []."""
    try:
        done = subprocess.run(  # noqa: PLW1510
            ["gh", "issue", "list", "--repo", repo, "--state", "all",
             "--limit", "300", "--json", "number,title,body,state"],
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
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
        return json.loads(done.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise TrackerUnavailable(f"`gh` returned something that is not JSON: {exc}") from exc


def triage(findings: list[dict], *, existing: list[dict],
           similarity: float = 0.6) -> tuple[list[dict], list[tuple[dict, str]]]:
    """`(to file, [(finding, why it was skipped)])`. Pure."""
    keep: list[dict] = []
    skip: list[tuple[dict, str]] = []
    for finding in findings:
        verdict = finding.get("verdict") or {}
        if verdict.get("refuted"):
            skip.append((finding, "an agent refuted it; a killed claim is not a defect"))
            continue
        if not (finding.get("evidence") or "").strip():
            skip.append((finding, "no evidence — an issue without a measurement is noise"))
            continue
        if not (finding.get("file") or "").strip():
            skip.append((finding, "names no file, so nobody can go and look"))
            continue

        anchor = f"{finding['file']}:{finding.get('line')}" if finding.get("line") else finding["file"]
        duplicate = None
        for issue in existing:
            if anchor and anchor in (issue.get("body") or ""):
                duplicate = f"#{issue['number']} already cites {anchor}"
                break
            if _overlap(finding.get("title", ""), issue.get("title", "")) >= similarity:
                state = (issue.get("state") or "").lower()
                duplicate = (f"#{issue['number']} says the same thing"
                             f"{' and was closed' if state == 'closed' else ''}")
                break
        if duplicate:
            skip.append((finding, duplicate))
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
    done = subprocess.run(  # noqa: PLW1510
        ["gh", "issue", "create", "--repo", repo, "--title", title,
         "--body", body(finding, repo_hint="the Squad kit")],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        return False, f"could not file {title!r}: {(done.stderr or '').strip()[:160]}"
    return True, (done.stdout or "").strip()


def run(findings: list[dict], *, repo: str, apply: bool) -> tuple[list[str], list[str], int]:
    try:
        existing = existing_issues(repo)
    except TrackerUnavailable as exc:
        # Nothing is filed. Without dedup, one real defect becomes a duplicate on
        # every run, and the noise is what makes a tracker stop being read.
        return [], [f"filed nothing: {exc}"], 1
    keep, skip = triage(findings, existing=existing)
    filed: list[str] = []
    notes = [f"{finding.get('title', '?')[:70]}: {why}" for finding, why in skip]
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

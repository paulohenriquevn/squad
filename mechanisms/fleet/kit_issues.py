#!/usr/bin/env python3
"""The kit's own registry, so an idle fleet can work on the kit.

WHY THIS EXISTS
---------------
A consumer's queue goes `BACKLOG_BLOCKED` whenever every remaining item waits on
a person, and that is the normal state, not the exception: measured on a real
consumer on 2026-09-02, both remaining items wanted a governance decision and the
whole fleet — three lanes and a lead — had nothing it was allowed to touch. The
lead correctly refused to schedule anything and stopped.

Meanwhile the kit had two open defects, and **both had been filed that same day
by agents running inside that very fleet**. The capture half of self-evolution
already worked; nothing consumed what it captured. Idle lanes and an unworked
defect list, in the same hour, on the same machine.

WHAT THIS IS NOT
----------------
It is not a second queue that competes with the consumer's. The consumer's
backlog always wins — this is asked only when that one has nothing to give, and
it never overrules a verdict, a gate or a status. It is where the fleet goes when
the alternative is idling.

It is also not a source of work it invents. Every item here is an issue somebody
(or some agent) filed, with a number you can open. If `gh` is missing, not
authenticated, or the repository is unreachable, this says exactly that and
returns nothing — the one thing it must never do is report an empty list, which
reads as "the kit has no known defects" and is the failure this kit keeps
finding.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass

#: Labels that mean "not fleet work". An issue asking a human to decide is the
#: same shape as the consumer items that blocked the queue in the first place,
#: and handing one to a lane reproduces the problem one level up.
NEEDS_A_PERSON = frozenset({"needs-decision", "question", "discussion", "wontfix"})

#: Labels that mean "fixed, merged, and waiting for the release that makes it
#: installable". An issue in this state is OPEN on purpose: the project rule separates
#: *the fix is merged* from *the fix is installable* and closes only on the second,
#: because closing at merge tells whoever is blocked that the problem is gone while the
#: installer still carries it.
#:
#: Without this set such an issue is indistinguishable from one nobody has touched — both
#: open, both unlabelled for a person — and a lane given one spends an agent re-solving a
#: solved problem, then writes a report that looks like progress. Measured 2026-09-22,
#: when twenty issues sat in exactly that state in this repository.
#:
#: `in-develop` is the name the project rule already prescribes. A second spelling would
#: be a second state nobody maintains.
AWAITING_RELEASE = frozenset({"in-develop"})


class Unavailable(RuntimeError):
    """The registry could not be read. Distinct from "the registry is empty".

    Collapsing the two would tell an idle fleet that its kit has no known
    defects, on the strength of a missing CLI.
    """


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    labels: tuple[str, ...]
    url: str

    @property
    def slug(self) -> str:
        return f"kit#{self.number}"

    def actionable(self) -> bool:
        return self.holding_reason is None

    @property
    def holding_reason(self) -> str | None:
        """Why this issue is not fleet work, or None when it is.

        Two reasons, reported apart. Collapsing them would tell a reader that twenty
        issues need their attention when none of them does, which is a signal that
        always fires — and a signal that always fires is the same as no signal.
        """
        labels = set(self.labels)
        if labels & NEEDS_A_PERSON:
            return "needs_a_person"
        if labels & AWAITING_RELEASE:
            return "awaiting_release"
        return None


def open_issues(repo: str, *, timeout: int = 60) -> list[Issue]:
    """Every open issue in `repo`, or `Unavailable` with the reason."""
    try:
        done = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--state", "open",
             "--limit", "100", "--json", "number,title,labels,url"],
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL, check=False)
    except FileNotFoundError as exc:
        raise Unavailable(
            f"`gh` is not installed, so the kit's registry cannot be read on this "
            f"machine. This is not the same as {repo} having no open issues.") from exc
    except subprocess.SubprocessError as exc:
        raise Unavailable(f"`gh issue list` did not return: {exc}") from exc

    if done.returncode != 0:
        raise Unavailable(
            f"`gh issue list --repo {repo}` exited {done.returncode}: "
            f"{(done.stderr or '').strip()[:200]}")
    try:
        payload = json.loads(done.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise Unavailable(f"`gh` returned something that is not JSON: {exc}") from exc

    return [
        Issue(number=row["number"], title=row.get("title", ""),
              labels=tuple(lbl.get("name", "") for lbl in row.get("labels", [])),
              url=row.get("url", ""))
        for row in payload
    ]


def fleet_work(repo: str, *, timeout: int = 60) -> tuple[list[Issue], list[Issue]]:
    """`(actionable, held)` — what a lane may take, and what waits on a person.

    Both halves are returned because reporting only the first would make the
    second invisible, and an issue nobody can see is an issue nobody decides.
    """
    issues = open_issues(repo, timeout=timeout)
    return ([i for i in issues if i.actionable()],
            [i for i in issues if not i.actionable()])


def main(argv: list[str] | None = None) -> int:
    """`kit_issues.py <owner/repo>` — what the fleet may take, and what it may not.

    Exit codes are the answer, so a caller can branch without parsing:
        0 — there is work
        1 — the registry is readable and holds nothing a lane may take
        2 — the registry could not be read, and this says why
    """
    import argparse

    ap = argparse.ArgumentParser(description="the kit's own registry")
    ap.add_argument("repo", help="owner/repo of the kit")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        work, held = fleet_work(args.repo)
    except Unavailable as exc:
        print(f"UNAVAILABLE: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "work": [{"slug": i.slug, "number": i.number, "title": i.title,
                      "url": i.url} for i in work],
            "held": [{"slug": i.slug, "number": i.number, "title": i.title,
                      "labels": list(i.labels)} for i in held],
        }, indent=2))
        return 0 if work else 1

    for issue in work:
        print(f"{issue.slug}  {issue.title}")
    for issue in held:
        print(f"{issue.slug}  [waiting on a person: {', '.join(issue.labels)}]  {issue.title}")
    if not work and not held:
        print("the kit's registry is readable and empty — no known open defects")
    return 0 if work else 1


if __name__ == "__main__":
    sys.exit(main())

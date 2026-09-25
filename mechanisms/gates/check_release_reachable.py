#!/usr/bin/env python3
"""Does the release this run says it published actually exist, and is it public?

    python3 mechanisms/gates/check_release_reachable.py --tag v1.2.0
    python3 mechanisms/gates/check_release_reachable.py --tag v1.2.0 --json

## The question nothing was asking

`cycle-release.md` ends at `gh release create` and emits `RELEASED`. Nothing looked
afterwards. A release left as a draft, a `gh` call that failed after the tag was already
pushed, a tag that never propagated — each produces `RELEASED` over an artifact no
consumer can fetch, and that verdict is what `cycle-maintenance`'s ADVANCE reads to write
`shipped` into the registry.

An external review named the surrounding gap as *"acceptance only for milestones leaves a
void"*. Half of that is answered already: `cycle-acceptance.md` argues that a `B-NNN` with
no milestone has no user-visible promise to exercise, and for PRODUCT acceptance the
argument holds. What it does not cover is whether the thing shipped at all — a question
with an answer for every item, milestone or not, and one nobody was asking.

## What this checks, and what it deliberately does not

CHECKED: a release exists for the tag, it is not a draft, and the tag it names is the one
that was cut. Three ways the last step of the chain half-succeeds.

NOT CHECKED: that a package is installable from npm, PyPI or crates.io. That is a
different claim needing the network and a registry, and `cycle-acceptance` is where a
delivery is exercised rather than merely confirmed to exist. Saying so here keeps this
gate from being read as the stronger check it is not.

## Why UNCHECKED is not HOLDS

An absent `gh`, an unauthenticated one, or an answer that does not parse are all *the
premise was not tested*, and they exit 2 rather than 0. A gate that looks, sees nothing
and approves produces confidence where there was no verification.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _contract import add_root

#: Run a `gh` argv and return (returncode, stdout, stderr). Injected so the logic is
#: testable without a network, a token, or a repository — the same shape
#: `check_merge_autonomy.py` uses for the same reason.
GhRunner = Callable[[list[str]], "tuple[int, str, str]"]

OK, FOUND, UNMEASURABLE = 0, 1, 2


@dataclass
class ReleaseReport:
    tag: str
    exit_code: int
    detail: str
    url: str = ""


def _run_gh(argv: list[str]) -> tuple[int, str, str]:
    done = subprocess.run(argv, capture_output=True, text=True, check=False)
    return done.returncode, done.stdout, done.stderr


def check_release_reachable(tag: str, *, gh: GhRunner | None = None) -> ReleaseReport:
    runner = gh or _run_gh
    argv = ["gh", "release", "view", tag, "--json", "tagName,isDraft,url"]
    try:
        code, out, err = runner(argv)
    except FileNotFoundError:
        return ReleaseReport(tag, UNMEASURABLE,
                             "gh is not installed, so the published release was not "
                             "checked. Not checking is not a clean check.")
    except OSError as error:
        return ReleaseReport(tag, UNMEASURABLE, f"gh could not be run: {error}")

    if code != 0:
        return ReleaseReport(
            tag, FOUND,
            f"no release exists for {tag}: {err.strip() or 'gh release view failed'}. "
            f"The tag may have been pushed while `gh release create` did not run or "
            f"failed — the half-success this gate exists to catch.")

    try:
        payload = json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return ReleaseReport(tag, UNMEASURABLE,
                             f"gh answered something this gate cannot parse, so nothing "
                             f"was verified: {out[:120]!r}")

    url = str(payload.get("url", ""))
    if payload.get("isDraft"):
        return ReleaseReport(tag, FOUND, url=url, detail=(
            f"the release for {tag} is a DRAFT. It is visible to whoever created it and "
            f"to nobody else, so nothing downstream can fetch what this run called "
            f"released. Publish it: `gh release edit {tag} --draft=false`."))

    named = str(payload.get("tagName", ""))
    if named != tag:
        return ReleaseReport(tag, FOUND, url=url, detail=(
            f"asked for {tag} and got a release for {named}. `gh release view` resolves "
            f"loosely, so the answer has to be checked rather than assumed."))

    return ReleaseReport(tag, OK, url=url, detail=(
        f"{tag} is published and public at {url or '(no url reported)'}. "
        f"This says the release EXISTS — not that a package is installable from a "
        f"registry, and not that the delivery works: `/acceptance` exercises that."))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_root(ap)
    ap.add_argument("--tag", required=True, help="the release tag to confirm, e.g. v1.2.0")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = check_release_reachable(args.tag)

    if args.json:
        print(json.dumps({"tag": report.tag, "url": report.url,
                          "detail": report.detail, "exit_code": report.exit_code}, indent=2))
        return report.exit_code

    label = {OK: "HOLDS", FOUND: "FAILS", UNMEASURABLE: "UNCHECKED"}[report.exit_code]
    stream = sys.stdout if report.exit_code == OK else sys.stderr
    print(f"{label}: {report.detail}", file=stream)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())

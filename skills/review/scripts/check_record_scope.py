#!/usr/bin/env python3
"""B-108 — does this review or audit record say what it covered?

WHY THIS EXISTS
---------------
`phase_coverage.py` (B-105) measured that half a registry's items had no record for `review` and
three quarters none for `code-quality`. The obvious next move was to derive them, the way the
`release` half was derived: the commit graph knows which tag contains which commit, and 41 of 41
items resolved that way.

It does not work here, and the measurement says why:

    review files declaring a reviewed range   2 of 48
    audit files mentioning a scope            3 of 16

A review's findings are judgments made in a session. If the file does not name the items it covered
or the range it read, nothing recovers that afterwards — not git, not the filename, not the date.
So the past is permanently unrecoverable, and the only honest move left is to stop the same hole
opening again.

B-084 closed "a gate that inspected zero and a gate that inspected everything emit the same
verdict". B-102 added "…and it does not say what it skipped". This is that shape one level up, for
the cycle's own artifacts: **a review that covered seven items and one that covered a single item
are indistinguishable from the file.**

WHAT IT REFUSES TO INFER
------------------------
The filename. `b086-findings.yml` looks like it declares B-086 — and a slice review covering seven
items would look exactly the same. Inferring scope from a name is how a record that covered one
item gets read as covering the slice it was named after, which is the misreading this check exists
to prevent, not a shortcut it can take.

A declared range (`head_reviewed`, `diff_baseline`) is REPORTED and never substitutes for the item
list. A range says what was read; the items say what it was read for, and turning one into the
other needs a commit-message convention that B-108 measured is followed only sometimes.
"""
from __future__ import annotations

import argparse
import enum
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - the kit declares pyyaml
    yaml = None  # type: ignore[assignment]


class ScopeVerdict(enum.Enum):
    DECLARED = "declared"
    UNDECLARED = "undeclared"
    UNREADABLE = "unreadable"


@dataclass
class ScopeReport:
    path: Path
    verdict: ScopeVerdict
    items: list[str] = field(default_factory=list)
    head: str | None = None
    baseline: str | None = None
    reason: str = ""


_ITEM_RE = re.compile(r"\bB-\d{3,}\b")
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _as_items(value: object) -> list[str]:
    """Accept a list or a bare scalar.

    `item: B-107` is the shape a one-item review naturally takes; refusing it would push authors
    toward a list of one, which is ceremony rather than clarity.
    """
    if isinstance(value, str):
        return _ITEM_RE.findall(value)
    if isinstance(value, list):
        found: list[str] = []
        for entry in value:
            found.extend(_ITEM_RE.findall(str(entry)))
        return found
    return []


def _declaration(data: object) -> tuple[list[str], str | None, str | None]:
    if not isinstance(data, dict):
        return [], None, None
    target = data.get("review_target")
    scope = target if isinstance(target, dict) else data
    items = _as_items(scope.get("items")) or _as_items(scope.get("item"))
    head = scope.get("head_reviewed")
    baseline = scope.get("diff_baseline")
    return items, (str(head) if head else None), (str(baseline) if baseline else None)


def check_record(path: Path) -> ScopeReport:
    """Does this record name the items it covered?"""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return ScopeReport(path, ScopeVerdict.UNREADABLE, reason=f"could not read: {exc}")

    payload = text
    if path.suffix == ".md":
        m = _FRONTMATTER_RE.match(text)
        if m is None:
            return ScopeReport(
                path, ScopeVerdict.UNDECLARED,
                reason="markdown record has no frontmatter, so it does not say which items it covered",
            )
        payload = m.group(1)

    if yaml is None:  # pragma: no cover
        return ScopeReport(path, ScopeVerdict.UNREADABLE, reason="pyyaml is not available to parse it")
    try:
        data = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        # An unparseable record must not read as "declared nothing" — that is the swallow this
        # ecosystem keeps finding. It gets its own verdict.
        first = str(exc).split("\n")[0]
        return ScopeReport(path, ScopeVerdict.UNREADABLE, reason=f"could not parse: {first}")

    items, head, baseline = _declaration(data)
    if not items:
        return ScopeReport(
            path, ScopeVerdict.UNDECLARED, head=head, baseline=baseline,
            reason="record does not say which items it covered (expected `items:` or `item:`)",
        )
    return ScopeReport(path, ScopeVerdict.DECLARED, items=items, head=head, baseline=baseline)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("records", type=Path, nargs="+", help="review or audit record files")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 when any record fails to declare its scope")
    args = parser.parse_args(argv)

    bad = 0
    for path in args.records:
        r = check_record(path)
        if r.verdict is ScopeVerdict.DECLARED:
            extra = f" (read {r.head}..{r.baseline})" if r.head else ""
            print(f"declared   {path.name}: {', '.join(r.items)}{extra}")
        else:
            bad += 1
            print(f"{r.verdict.value:10} {path.name}: {r.reason}", file=sys.stderr)

    if bad and args.strict:
        print(
            f"\ncheck-record-scope: {bad} record(s) do not say what they covered. A review that "
            "covered seven items and one that covered a single item are indistinguishable from "
            "such a file (B-108).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

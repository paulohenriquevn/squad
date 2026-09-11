#!/usr/bin/env python3
"""Score an issue body BEFORE it is filed, weighted by what developers measurably use.

    python3 skills/file-issue/scripts/score_issue.py draft.md
    python3 skills/file-issue/scripts/score_issue.py draft.md --json

## The weights are not opinions

Bettenburg et al., *"What Makes a Good Bug Report?"* (FSE 2008) surveyed **872
developers** across APACHE, ECLIPSE and MOZILLA on what they use when fixing a bug, and
separately surveyed reporters on what they supply. The gap is the whole reason this
scorer exists:

    WANTED BY DEVELOPERS              SUPPLIED BY REPORTERS
      steps to reproduce   83%          observed behaviour   48%
      stack traces         57%          expected behaviour   27%
      observed behaviour   33%          screenshots          26%
      expected behaviour   22%          version              22%
      version              12%          operating system     20%
      build information     8%          code examples        14%
      operating system      4%
      severity              0%   ←
      hardware              0%   ←

Two findings drive every weight below.

**Steps to reproduce is the most wanted item at 83% and is routinely the missing one.**
An issue without it is the single most expensive kind to receive.

**Severity scored 0%.** Developers fixing a bug do not use it. It is kept here because
it serves TRIAGE — deciding what gets looked at — which is a different reader with a
different question. A scorer that dropped it would optimise for one audience and a
scorer that weighted it like the rest would mislead.

And the cost of getting this wrong, from the same study: **incomplete information is the
problem developers rank as causing the most delay, at 74%** — ahead of duplicates (10%)
and far ahead of spam (0%).

## Why the duplicate check is weighted at all

*"Why are Some Bugs Non-Reproducible?"* (Rahman et al., arXiv:2108.05316) analysed
non-reproducible reports across Firefox and Eclipse and found **bug duplication the
single most dominant factor**, at roughly 29%. A duplicate is not merely noise: it is
the leading cause of a report that nobody can reproduce.

## What it cannot score

  - WHETHER THE REPRO WORKS. It checks that steps are present and numbered, never that
    following them produces the failure. Only running them does that.
  - WHETHER THE DIAGNOSIS IS RIGHT. A confident wrong cause scores the same as a
    correct one; the contract asks for honest uncertainty instead.
  - WHETHER IT IS ACTUALLY A DUPLICATE. It checks that a search was recorded, not that
    the search was good.

Exit codes:
  0  READY — every weighted item present
  1  THIN — scored below the floor; the report names which items are missing
  2  REFUSED — a secret was detected, or the file could not be read. Nothing is filed
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Item:
    key: str
    weight: int
    why: str
    patterns: tuple[str, ...]


#: Weights ARE the measured percentages, rounded. Using the real numbers rather than a
#: 1-5 scale keeps the source auditable: anybody can check a weight against the paper.
ITEMS: tuple[Item, ...] = (
    Item("steps_to_reproduce", 83,
         "the most wanted item in the study and the most often missing. An issue "
         "without it is the most expensive kind to receive",
         (r"^#+\s*(steps|repro|reproduction|how to reproduce)",
          r"^\s*1[\.)]\s+\S")),
    Item("stack_trace_or_output", 57,
         "wanted by 57% of developers. The study also warns a trace without context is "
         "'often too large to be useful' — paste the failure, not the whole log",
         (r"```", r"^\s{4}\S", r"Traceback|Exception|panic:|\bat [\w.$]+\(")),
    Item("observed_behaviour", 33,
         "what actually happened, in the reporter's words",
         (r"^#+\s*(actual|observed|what happens)", r"\*\*actual", r"\bactual:")),
    Item("expected_behaviour", 22,
         "without it, 'broken' is not a claim anyone can act on",
         (r"^#+\s*(expected|should)", r"\*\*expected", r"\bexpected:")),
    Item("version_or_build", 12,
         "a version or a SHA. 'It fails' with no build under test is unfalsifiable",
         (r"^#+\s*(build|version|environment)", r"\bv?\d+\.\d+\.\d+\b", r"\b[0-9a-f]{7,40}\b",
          r"build under test")),
    Item("dedup_recorded", 10,
         "duplication is the single most dominant factor behind non-reproducible "
         "reports (~29%). Recording the search is what makes the check auditable",
         (r"gh issue list", r"\bdedup", r"searched .*(issue|tracker)", r"no (existing|open) issue")),
    Item("environment", 4,
         "OS, runtime, or deployment target. Wanted by only 4% — but it is the 4% "
         "where the bug only happens on one of them",
         (r"^#+\s*(environment|platform)", r"\b(linux|macos|windows|ubuntu|darwin)\b",
          r"\bpython \d|\bnode \d|\bgo1\.\d")),
)

#: Kept, weighted at zero, and REPORTED as zero. Developers fixing a bug do not use
#: severity — it scored 0% in the study. It serves triage, which is a different reader.
#: Dropping it would optimise for one audience; weighting it like the rest would lie.
TRIAGE_ONLY: tuple[Item, ...] = (
    Item("severity", 0,
         "0% of developers use it when FIXING. It is for whoever decides what gets "
         "looked at, which is a different question by a different reader",
         (r"^#+\s*severity", r"\bseverity\b")),
)

#: The floor. 83+57+33+22+12+10+4 = 221 is everything; 60% of it requires the repro
#: plus most of the rest, and cannot be reached by padding the cheap items alone.
TOTAL_WEIGHT = sum(i.weight for i in ITEMS)
FLOOR_PCT = 60

#: Refused outright, never scored. A secret in an issue body is public the moment it is
#: filed and stays in the edit history after it is removed.
SECRET_RE = (
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{16,})"), "GitHub token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "OpenAI-style key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."), "JWT"),
    (re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
     "credential assignment"),
)


@dataclass
class Report:
    score: int = 0
    total: int = TOTAL_WEIGHT
    present: list[str] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    triage: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    verdict: str = ""

    @property
    def pct(self) -> int:
        return round(100 * self.score / self.total) if self.total else 0


def _has(body: str, item: Item) -> bool:
    return any(re.search(p, body, re.IGNORECASE | re.MULTILINE) for p in item.patterns)


def scan_secrets(body: str) -> list[str]:
    return [label for pattern, label in SECRET_RE if pattern.search(body)]


def score(body: str) -> Report:
    rep = Report()

    rep.secrets = scan_secrets(body)
    if rep.secrets:
        #: Scored nothing. A body with a secret in it is not a draft to improve; it is
        #: a draft to rewrite, and reporting a score beside the refusal invites filing
        #: it anyway.
        rep.verdict = "REFUSED"
        return rep

    for item in ITEMS:
        if _has(body, item):
            rep.present.append(item.key)
            rep.score += item.weight
        else:
            rep.missing.append({"item": item.key, "weight": item.weight, "why": item.why})

    rep.triage = [i.key for i in TRIAGE_ONLY if _has(body, i)]
    rep.verdict = "READY" if rep.pct >= FLOOR_PCT else "THIN"
    return rep


NOT_SCORED = (
    "whether the repro WORKS — only running it establishes that",
    "whether the diagnosis is right; a confident wrong cause scores like a correct one",
    "whether it is actually a duplicate, only that a search was recorded",
)


def render(rep: Report) -> str:
    if rep.verdict == "REFUSED":
        return ("issue draft: REFUSED\n\n"
                f"  a secret was detected: {', '.join(rep.secrets)}\n\n"
                "  Nothing was scored and nothing should be filed. An issue body is\n"
                "  public the moment it is filed, and removing it later leaves it in the\n"
                "  edit history. Rewrite the draft without it — a redacted placeholder\n"
                "  carries the same information for the reader who needs it.")

    out = [f"issue draft: {rep.verdict} — {rep.pct}% of weighted usefulness "
           f"({rep.score}/{rep.total})", ""]
    if rep.present:
        out.append("  present: " + ", ".join(rep.present))
    if rep.missing:
        out.append("")
        out.append("  missing, heaviest first:")
        for m in sorted(rep.missing, key=lambda m: -m["weight"]):
            out.append(f"    [{m['weight']:>2}] {m['item']}")
            out.append(f"         {m['why']}")
    out.append("")
    out.append(f"  severity: {'stated' if rep.triage else 'absent'} — weighted 0, and "
               "that is the measurement, not an oversight")
    out.append("")
    out.append("  NOT SCORED:")
    for line in NOT_SCORED:
        out.append(f"    · {line}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("draft", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        body = args.draft.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"REFUSED: could not read {args.draft}: {exc}", file=sys.stderr)
        return 2

    rep = score(body)
    print(json.dumps({**rep.__dict__, "pct": rep.pct, "not_scored": list(NOT_SCORED)},
                     indent=2) if args.json else render(rep))

    if rep.verdict == "REFUSED":
        return 2
    return 0 if rep.verdict == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())

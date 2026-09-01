#!/usr/bin/env python3
"""The judge that signs an alignment brief when no human will.

WHY THIS EXISTS, AND WHAT IT COSTS
----------------------------------
`skills/_kit-rules/alignment-threshold.md` says the agent that writes a brief may never sign
it, because an author approving their own work is not a review. The operator
chose autonomy — humans at backlog construction and nowhere else in the loop —
so a judge signs instead.

**This reduces the problem; it does not remove it.** A judge is still an agent,
and the honest position is to say so in the artefact rather than let a tick imply
a person. Three constraints keep it from being a rubber stamp with extra latency:

1. It reads the item's EVIDENCE, not only the brief. A brief that is internally
   tidy and describes work nobody measured is exactly what a self-approving
   author produces, and only the evidence exposes it.
2. It must be able to REFUSE, and refusing must be as cheap as approving. A judge
   that has never refused is a judge nobody has tested.
3. Its verdict and reasoning are written into the brief, and its signature
   carries its name — `<!-- signed-by: judge/alignment-judge -->`. `ALIGNED` by a
   judge and `ALIGNED` by a person are different claims, and a reader must be
   able to tell them apart without opening the file.

WHAT IT DOES NOT DECIDE
-----------------------
It does not re-score the machine criteria: `score_alignment.py` owns those, and a
judge that could also move the number would be marking its own homework one level
up. It answers only the judgement items — the three (or more) a script cannot
decide — and it answers them against evidence.

Usage:
    python3 alignment_judge.py <brief.md> --verdict signed|refused \\
        --reason "<why>" [--judge <name>]

Exit codes:
    0 — the brief was signed
    1 — the brief was refused; the reason is written into it
    2 — the brief could not be read, or is not ready to be judged
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

_SIGNOFF_RE = re.compile(r"^(##+\s+Reviewer sign-off\s*)$", re.MULTILINE | re.IGNORECASE)
_BOX_RE = re.compile(r"^(\s*-\s*)\[ \](\s*.+?)\s*$", re.MULTILINE)

DEFAULT_JUDGE = "judge/alignment-judge"


def _evidence_paths(brief: str) -> list[str]:
    """What the brief claims as evidence, so a reader can check the judge read it."""
    return sorted({m.group(0) for m in re.finditer(r"`[^`]+\.(?:md|py|ts|go|yaml|yml)`", brief)})


def sign(brief_path: Path, judge: str, reason: str) -> str:
    text = brief_path.read_text(encoding="utf-8")
    if not _SIGNOFF_RE.search(text):
        raise SystemExit("FATAL: the brief has no `## Reviewer sign-off` section to sign")
    if "[ ]" not in text.split("## Reviewer sign-off", 1)[-1]:
        raise SystemExit("FATAL: nothing is unticked — refusing to re-sign a signed brief")

    marker = f"  <!-- signed-by: {judge} -->"
    head, _, tail = text.partition("## Reviewer sign-off")
    tail = _BOX_RE.sub(lambda m: f"{m.group(1)}[x]{m.group(2)}{marker}", tail)

    tail += (
        f"\n**Judged {date.today().isoformat()} by `{judge}`, not by a person.**\n\n"
        f"{reason.strip()}\n\n"
        f"A judge signature is worth less than a human one and the record says so "
        f"rather than blurring it. The operator can overturn this by unticking a "
        f"box: the gate reads the file, not this note.\n"
    )
    return head + "## Reviewer sign-off" + tail


def refuse(brief_path: Path, judge: str, reason: str) -> str:
    text = brief_path.read_text(encoding="utf-8")
    return text.rstrip() + (
        f"\n\n**REFUSED {date.today().isoformat()} by `{judge}`.**\n\n"
        f"{reason.strip()}\n\n"
        f"The boxes stay unticked. A refusal is the judge doing the one thing that "
        f"makes it more than a rubber stamp, and it costs the same as approving.\n"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("brief", type=Path)
    ap.add_argument("--verdict", choices=("signed", "refused"), required=True)
    ap.add_argument("--reason", required=True,
                    help="what the judge checked, against what evidence. A verdict "
                         "with no reasoning is a tick, and a tick is what this "
                         "exists to be more than.")
    ap.add_argument("--judge", default=DEFAULT_JUDGE)
    args = ap.parse_args(argv)

    if len(args.reason.split()) < 15:
        print("FATAL: the reason is too short to be a judgement. Say what was "
              "checked and against which evidence.", file=sys.stderr)
        return 2

    try:
        out = sign(args.brief, args.judge, args.reason) if args.verdict == "signed" \
            else refuse(args.brief, args.judge, args.reason)
    except OSError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    args.brief.write_text(out, encoding="utf-8")
    print(f"{args.verdict.upper()} by `{args.judge}` — written into {args.brief}")
    if args.verdict == "signed":
        print("  Evidence the brief cites:", ", ".join(_evidence_paths(out)[:4]) or "none")
    return 0 if args.verdict == "signed" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Decide whether a project may claim `production-ready` / `v1.0`.

    python3 check_honesty_gate.py [--root .] [--json] [--today YYYY-MM-DD]

WHY THIS EXISTS
---------------
`rules/honesty-gate-golden-rule.md` is a LOCKED contract with an ordered list of
hard caps, named flags, a status vocabulary and a freshness threshold. Every part
of it is mechanizable, and until 2026-09-01 **none of it was mechanized**: the
skill read the rule and applied it by hand, nothing in the repository read its
verdict, and no phase invoked it. Measured across a real consumer's whole history:
one artifact.

So the gate that guards against a claim nobody earned was itself the shape it
guards against — a contract honoured only when somebody remembered. In a
supervised loop that is merely weak. In an unattended one it is nothing at all,
because nobody remembers, and the claim most likely to be overstated is exactly
the one no phase checks.

The input already exists. `cycle-acceptance` writes a record per milestone with a
computed verdict, and this rule reads those plus a manifest. Only the reader was
prose.

WHAT IT REFUSES TO INFER
------------------------
**Absence of evidence is never evidence of sufficiency.** No manifest, no golden
rule, no evidence file — each is `EVIDENCE_INSUFFICIENT` with the flag that says
which, never "not applicable" and never a pass by default. A project that has not
set the gate up has not passed it.

It also never picks the anchor. The anchor scenario is the one judgement this
rule leaves to a person on purpose — *"pick one, be specific"* — and a script
choosing it would be the gate writing its own exam.

Verdicts, per `§ 3` and `§ 4` of the rule:

    EVIDENCE_SUFFICIENT      every hard cap passed, no soft cap fired
    EVIDENCE_WITH_CAVEATS    hard caps passed; the evidence is thin, and the
                             caveats travel with the claim
    EVIDENCE_INSUFFICIENT    a hard cap fired; the claim is refused

Exit codes:
    0 — EVIDENCE_SUFFICIENT
    1 — EVIDENCE_INSUFFICIENT — the claim must not be made
    2 — the rule or the project root could not be read
    3 — EVIDENCE_WITH_CAVEATS — permitted, and the caveats are named
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# The one owner of every data-root literal — no local fallback copy, because a copy is
# what the containment gate exists to refuse.
import sys as _sys_bootstrap
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from pathlib import Path as _Path_bootstrap

_here = _Path_bootstrap(__file__).resolve()
for _up in _here.parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import records_dir  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mechanisms" / "conventions"))


SUFFICIENT = "EVIDENCE_SUFFICIENT"
WITH_CAVEATS = "EVIDENCE_WITH_CAVEATS"
INSUFFICIENT = "EVIDENCE_INSUFFICIENT"

#: The status that satisfies hard cap 2. Declared in the rule's § 2 vocabulary,
#: which is LOCKED — this constant mirrors it and the test asserts they agree, so
#: the two cannot drift into disagreeing about what `running` means.
RUNNING = "running"

#: Read from the rule rather than hardcoded. `§ 3` says the threshold is
#: per-project and may be lowered freely but never raised without an ADR, so a
#: number frozen here would quietly override a project that lowered it.
_FRESHNESS_RE = re.compile(r"Freshness threshold[^`]*`\s*(\d+)\s*days?\s*`", re.IGNORECASE)
_DEFAULT_FRESHNESS_DAYS = 30

_SLUG_RE = re.compile(r"^\s*\*{0,2}Slug:?\*{0,2}\s*:?\s*`?([a-z0-9][a-z0-9-]*)`?",
                      re.IGNORECASE | re.MULTILINE)
_STATUS_RE = re.compile(r"^\s*\*{0,2}Status:?\*{0,2}\s*:?\s*`?([a-z]+)`?",
                        re.IGNORECASE | re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)

#: Every field `§ 5` marks LOCKED. A file missing any of them is IGNORED by hard
#: cap 3 — not counted, and not treated as a defect either: the rule says
#: "ignored", and reporting it as a failure would make a malformed note louder
#: than a missing one.
_REQUIRED_EVIDENCE_FIELDS = ("scenario", "date", "operator", "outcome", "summary")

#: The `outcome` vocabulary `§ 5` declares, LOCKED like the status one above. It
#: is validated rather than trusted because the value decides a soft cap: with
#: `outcome` read as free text, anything that is not the literal `pass` counts as
#: a recorded failure, so a typo (`passed`) buys the run a failure story it never
#: had and `no_failure_story` silently stops firing. A value outside this tuple
#: is a file that does not say what the rule requires, which is the case
#: `_REQUIRED_EVIDENCE_FIELDS` already answers with "ignored".
PASS = "pass"
_EVIDENCE_OUTCOMES = (PASS, "partial", "fail")


@dataclass
class HonestyReport:
    verdict: str = INSUFFICIENT
    anchor: str | None = None
    status: str | None = None
    hard_caps: list[str] = field(default_factory=list)
    soft_caps: list[str] = field(default_factory=list)
    evidence_count: int = 0
    ignored_evidence: list[str] = field(default_factory=list)
    operators: list[str] = field(default_factory=list)
    newest_evidence: str | None = None
    freshness_days: int = _DEFAULT_FRESHNESS_DAYS
    detail: str = ""


def _records_dir(root: Path, leaf: str) -> Path | None:
    return records_dir(root, leaf)


def _frontmatter(text: str) -> dict[str, str]:
    found = _FRONTMATTER_RE.match(text)
    if not found:
        return {}
    fields: dict[str, str] = {}
    for line in found.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip().strip("'\"")
    return fields


def freshness_days(rule_text: str) -> int:
    found = _FRESHNESS_RE.search(rule_text)
    return int(found.group(1)) if found else _DEFAULT_FRESHNESS_DAYS


def check(root: Path, *, today: date | None = None) -> HonestyReport:
    root = Path(root)
    today = today or date.today()
    report = HonestyReport()

    rule = next((root / r / "honesty-gate-golden-rule.md"
                 for r in ("rules", ".claude/rules")
                 if (root / r / "honesty-gate-golden-rule.md").is_file()), None)
    if rule is None:
        report.hard_caps.append("golden_rule_missing")
        report.detail = ("no `honesty-gate-golden-rule.md` — the contract that says "
                         "what would count is absent, so nothing counts")
        return report
    report.freshness_days = freshness_days(rule.read_text(encoding="utf-8", errors="replace"))

    # ── hard cap 1 — an anchor exists ────────────────────────────────────────
    manifest_dir = _records_dir(root, "honesty-gate")
    manifest = (manifest_dir / "manifest.md") if manifest_dir else None
    if manifest is None or not manifest.is_file():
        report.hard_caps.append("anchor_missing")
        report.detail = ("no `records/honesty-gate/manifest.md` — a project that has "
                         "not declared an anchor has not passed this gate, and an "
                         "absent manifest is not an exemption")
        return report

    text = manifest.read_text(encoding="utf-8", errors="replace")
    slug = _SLUG_RE.search(text)
    if slug is None:
        report.hard_caps.append("anchor_missing")
        report.detail = "the manifest declares no `Slug:` naming the anchor scenario"
        return report
    report.anchor = slug.group(1)

    # ── hard cap 2 — the anchor is actually running ──────────────────────────
    status = _STATUS_RE.search(text)
    report.status = status.group(1).lower() if status else None
    if report.status != RUNNING:
        report.hard_caps.append("anchor_not_running")
        report.detail = (f"anchor `{report.anchor}` is `{report.status or 'undeclared'}`, "
                         f"and `{RUNNING}` is the only status that satisfies this cap. "
                         f"`wired` means it was invoked once; the bar is a team using it")
        return report

    # ── hard cap 3 — evidence exists for THIS anchor ─────────────────────────
    evidence_dir = _records_dir(root, "honesty-gate/evidence")
    matching: list[tuple[date, dict[str, str]]] = []
    for path in sorted(evidence_dir.glob("*.md")) if evidence_dir else []:
        fields = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if any(f not in fields for f in _REQUIRED_EVIDENCE_FIELDS):
            report.ignored_evidence.append(f"{path.name}: a locked field is missing")
            continue  # § 5: a file missing a locked field is ignored, not counted
        if fields["scenario"] != report.anchor:
            continue  # evidence for another anchor; not this gate's business
        if fields["outcome"].lower() not in _EVIDENCE_OUTCOMES:
            report.ignored_evidence.append(
                f"{path.name}: outcome `{fields['outcome']}` is outside `§ 5`")
            continue
        try:
            when = date.fromisoformat(fields["date"])
        except ValueError:
            report.ignored_evidence.append(f"{path.name}: `date` is not an ISO date")
            continue
        matching.append((when, fields))

    if not matching:
        report.hard_caps.append("no_anchor_evidence")
        report.detail = (f"no evidence file names `scenario: {report.anchor}` with every "
                         f"locked field present. Evidence for a different scenario is "
                         f"not evidence for this one")
        return report

    matching.sort(key=lambda pair: pair[0], reverse=True)
    report.evidence_count = len(matching)
    report.newest_evidence = matching[0][0].isoformat()
    report.operators = sorted({fields["operator"] for _, fields in matching})

    # ── hard cap 4 — the newest evidence is not stale ────────────────────────
    if matching[0][0] < today - timedelta(days=report.freshness_days):
        report.hard_caps.append("anchor_evidence_stale")
        age = (today - matching[0][0]).days
        report.detail = (f"newest evidence is {age} days old against a threshold of "
                         f"{report.freshness_days}. The gate answers whether the "
                         f"product is used NOW, not whether it once was")
        return report

    # ── soft caps — the claim is permitted and the caveats travel ────────────
    if report.evidence_count < 3:
        report.soft_caps.append("thin_evidence")
    if all(fields["outcome"].lower() == PASS for _, fields in matching):
        report.soft_caps.append("no_failure_story")
    if len(report.operators) < 2:
        report.soft_caps.append("single_operator")

    report.verdict = WITH_CAVEATS if report.soft_caps else SUFFICIENT
    report.detail = (f"anchor `{report.anchor}` is running with {report.evidence_count} "
                     f"evidence file(s), newest {report.newest_evidence}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--today", default=None, help="the date to age evidence against")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"FATAL: {root} is not a directory", file=sys.stderr)
        return 2

    today = date.fromisoformat(args.today) if args.today else None
    report = check(root, today=today)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"honesty gate — {root}")
        print(f"  verdict: {report.verdict}")
        if report.anchor:
            print(f"  anchor:  {report.anchor} ({report.status})")
        for flag in report.hard_caps:
            print(f"  [hard] {flag}")
        for flag in report.soft_caps:
            print(f"  [soft] {flag}")
        for note in report.ignored_evidence:
            print(f"  [skipped] {note}")
        print(f"  {report.detail}")

    if report.verdict == SUFFICIENT:
        return 0
    if report.verdict == WITH_CAVEATS:
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

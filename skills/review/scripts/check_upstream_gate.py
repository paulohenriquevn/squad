#!/usr/bin/env python3
"""The `/review` pre-condition, as code instead of prose.

`code-quality-golden-rule.md § 1` gives `/code-quality` five verdicts and says what
each one means downstream:

| Verdict | Downstream |
|---|---|
| `PASS` / `PASS_WITH_CAVEATS` | proceed |
| `FAIL_SOFT` | proceed ONLY with an explicit ADR dismissing EACH soft cap |
| `FAIL_HARD` / `INVALID` | blocked |

Until 2026-08-26 nothing enforced any of it. The check lived in `SKILL.md` as a
`test -f` the agent had to remember to run, and the ADR — the artefact that makes
a soft cap dismissible — was never looked for: claiming it existed was enough.

The findings this module returns are fed into `consolidate_findings.py` as regular
BLOCKERs, so the review verdict cannot be computed without them. A separate step
would have the same weakness as the prose: someone has to invoke it.

WHY "EACH" IS THE STRICT READING
--------------------------------
With two soft caps and one ADR, "there is an ADR" approves both — and the cap
nobody examined rides along with the one that was. Same shape as the
`READY_TO_MERGE_WITH_FOLLOWUPS` wording that used to read "every HIGH above the
cap", where any subset satisfied it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and a reader resolving one order found a directory a writer
# using another had never filled.
import sys as _sys_bootstrap
from pathlib import Path
from pathlib import Path as _Path_bootstrap
from typing import Any

_here = _Path_bootstrap(__file__).resolve()
for _up in _here.parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import records_dir, resolve_knowledge_dir  # noqa: E402

_VERDICT_RE = re.compile(r"^\*\*Verdict:\*\*\s*(?P<verdict>[A-Z_]+)", re.MULTILINE)
_SOFT_CAPS_RE = re.compile(r"^\*\*Soft caps triggered:\*\*\s*(?P<caps>.+)$", re.MULTILINE)

_ADMITS = frozenset({"PASS", "PASS_WITH_CAVEATS"})
_BLOCKS_OUTRIGHT = frozenset({"FAIL_HARD", "INVALID"})



def _finding(title: str, evidence: str, remediation: str) -> dict[str, Any]:
    return {
        "severity": "BLOCKER",
        "category": "upstream-gate",
        "title": title,
        "evidence": evidence,
        "remediation": remediation,
        "source": "check_upstream_gate",
    }


def _latest_audit(project_root: Path, slug: str) -> Path | None:
    candidates: list[Path] = []
    audits = records_dir(project_root, "audits")
    if audits is not None:
        candidates.extend(audits.glob(f"{slug}-code-quality-*.md"))
    if not candidates:
        return None
    # By NAME, not mtime: the name carries the audit date, and a re-read or a copy
    # would reshuffle mtimes without any new audit having happened.
    return max(candidates, key=lambda p: p.name)


def _dismissal_corpus(project_root: Path, slug: str) -> str:
    """Everywhere an ADR may legitimately live, concatenated.

    `decisions` is a DURABLE leaf: the bundle holds it after migration and
    `records/adrs/` before it. One resolver knows both roots; a literal here would
    know one, and the caps dismissed in the other would read as undismissed.
    """
    chunks: list[str] = []

    adrs = resolve_knowledge_dir(project_root, "decisions")
    if adrs is not None:
        for path in sorted(adrs.glob("*.md")):
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue

    # The plan itself may carry the dismissal, and it is a dated artifact, not a
    # durable one — so it resolves through the trail rather than the bundle.
    plans = records_dir(project_root, "plans")
    if plans is not None:
        plan = plans / f"{slug}-plan.md"
        if plan.is_file():
            try:
                chunks.append(plan.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass

    return "\n".join(chunks)


def check_upstream_gate(project_root: Path, slug: str) -> list[dict[str, Any]]:
    """Return BLOCKER findings when the `/code-quality` verdict does not admit `/review`."""
    audit = _latest_audit(project_root, slug)
    if audit is None:
        return [_finding(
            f"no /code-quality audit for `{slug}`",
            f"looked in {records_dir(project_root, 'audits')} for "
            f"`{slug}-code-quality-*.md`",
            f"run `/code-quality {slug}` STANDALONE before `/review`. 'No audit' here "
            f"means no audit FILE: `run_validation.py` already ran this phase nested and "
            f"passed it `--no-audit-write`, so it returned a verdict and wrote nothing. "
            f"A reader who takes this line as 'the phase never ran' looks at the item "
            f"for an hour — measured on a consumer 2026-09-15. Reviewing code that no "
            f"audit swept means the review inherits whatever the audit would have caught",
        )]

    try:
        body = audit.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [_finding(f"/code-quality audit unreadable: {e}", str(audit),
                         "re-run `/code-quality {slug}`")]

    match = _VERDICT_RE.search(body)
    if match is None:
        return [_finding(
            "/code-quality audit unreadable: no `**Verdict:**` line",
            str(audit),
            "re-run `/code-quality {slug}` — an audit with no verdict is an absent "
            "verdict, never a favourable one",
        )]

    verdict = match.group("verdict")
    if verdict in _ADMITS:
        return []
    if verdict in _BLOCKS_OUTRIGHT:
        return [_finding(
            f"/code-quality verdict is {verdict}",
            str(audit),
            "loop back to `/implement` — golden rule § 1 blocks `/review` on this verdict",
        )]

    # FAIL_SOFT — admissible, but only against an ADR naming each cap.
    caps_match = _SOFT_CAPS_RE.search(body)
    raw = caps_match.group("caps").strip() if caps_match else ""
    caps = [c.strip() for c in raw.split(",") if c.strip() and c.strip() != "_none_"]
    if not caps:
        return [_finding(
            f"/code-quality verdict is {verdict} but the audit names no soft cap",
            str(audit),
            "re-run `/code-quality {slug}` — FAIL_SOFT without a named cap cannot be "
            "dismissed by an ADR, because there is nothing to name in it",
        )]

    corpus = _dismissal_corpus(project_root, slug)
    undismissed = [cap for cap in caps if cap not in corpus]
    if not undismissed:
        return []

    return [_finding(
        f"/code-quality is {verdict} and {len(undismissed)} soft cap(s) have no ADR",
        f"{audit}: {', '.join(undismissed)}",
        "write an ADR naming EACH cap by its stable identifier (in "
        "records/adrs/ or the plan's `## ADRs`), or fix what the cap points at. "
        "One ADR may cover several caps, as long as it names each one.",
    )]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the /review upstream gate.")
    parser.add_argument("slug")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    findings = check_upstream_gate(args.project_root, args.slug)
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for finding in findings:
            print(f"[{finding['severity']}] {finding['title']}")
            print(f"  evidence   : {finding['evidence']}")
            print(f"  remediation: {finding['remediation']}")
        if not findings:
            print("upstream gate: OK — /code-quality admits /review")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

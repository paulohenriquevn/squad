#!/usr/bin/env python3
"""PostToolUse — flag claims in public copy that measurement has not earned.

`rules/public-copy.md` is the contract. What it guards is narrow: a README says
things to people who cannot check them, and the cheapest sentence to write is the
one nobody has measured. `production-ready`, `battle-tested`, `99.99% uptime` —
each is a claim about sustained evidence, and writing it before the evidence
exists spends credibility that is hard to get back.

**Advisory, never blocking.** Some of these are the right words sometimes, and a
gate that blocks a README is a gate somebody switches off. It warns, names the
rule, and lets the writer decide.

Two of the checks are conditional rather than absolute: a comparative claim is
fine WITH a benchmark link, and an SLA number is fine when qualified as a target.
Those are the cases where the sentence and its evidence travel together.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import PostToolUseContext, create_context  # noqa: E402
from squad.layout import resolve  # noqa: E402

#: Files a stranger reads to decide whether to trust the project.
PUBLIC = (re.compile(r"(^|/)README\.md$"),
          re.compile(r"(^|/)PITCH\.md$"),
          re.compile(r"docs/marketing/[^/]+\.md$"),
          re.compile(r"docs/guides/[^/]+\.md$"))

#: Places where a measured claim is the POINT — a benchmark report exists to say
#: what was measured, and linting it for confidence would be backwards.
EXEMPT = (re.compile(r"docs/exploration-reports/"),
          re.compile(r"docs/benchmarks/"),
          re.compile(r"docs/adr/"))


@dataclass(frozen=True)
class Check:
    pattern: re.Pattern[str]
    message: str
    #: When set, the claim is allowed if this ALSO matches — the evidence that
    #: makes the sentence honest, required in the same text.
    excused_by: re.Pattern[str] | None = None


_I = re.IGNORECASE

CHECKS = (
    Check(re.compile(r"production[ ]?-?[ ]?(ready|grade)", _I),
          "'production-ready' or 'production-grade' in public copy. Until you have "
          "sustained measured evidence, prefer 'designed for' / 'targeted at' framings"),
    Check(re.compile(r"\bbattle[ ]?-?[ ]?tested\b", _I),
          "'battle-tested' in public copy. Banned until v1.0 with sustained production "
          "usage. Use 'designed for' or 'targeted at'."),
    Check(re.compile(r"\benterprise[ ]?-?[ ]?(ready|grade)\b", _I),
          "'enterprise-ready' / 'enterprise-grade' in public copy — vague. Replace with "
          "the specific affirmation you actually mean (RBAC via OIDC, audit log "
          "retention, compliance roadmap, etc.)."),
    Check(re.compile(r"\bfaster[ ]+than\b", _I),
          "'Faster than <X>' claim in public copy without a docs/benchmarks/ link in the "
          "same paragraph. Comparative performance requires a reproducible artifact + "
          "independent reproduction.",
          excused_by=re.compile(r"(docs/)?benchmarks/")),
    Check(re.compile(r"\b[A-Z][A-Za-z0-9 ]+[ ]+killer\b"),
          "'<X> killer' framing in public copy. Prefer outcome-shaped positioning, not "
          "vendor-hostile framing."),
    Check(re.compile(r"\bdrop[ ]?-?[ ]?in[ ]+replacement\b", _I),
          "'Drop-in replacement' in public copy implies zero migration cost — almost "
          "always false. Replace with the specific compatibility surface you offer."),
    Check(re.compile(r"\bzero[ ]?-?[ ]?downtime\b", _I),
          "'Zero downtime' (unqualified) in public copy. Qualify the scope ('minor "
          "upgrades are zero-downtime; major upgrades have measured downtime') or remove.",
          excused_by=re.compile(
              r"(minor|rolling|patch|hot)[ ]+[A-Za-z]*[ ]?(version|upgrade|update|deploy)?"
              r"[ ]*(are[ ]+)?zero[ ]?-?[ ]?downtime", _I)),
    Check(re.compile(r"\block[ ]?-?[ ]?in[ ]+(free|proof)\b", _I),
          "'Lock-in free/proof' in public copy — exaggeration. State the specific exit "
          "affordance ('export with <tool>', 'data is yours in standard format X')."),
    Check(re.compile(r"\b(99\.9|99\.95|99\.99)[ ]?%[ ]+(uptime|SLA|SLO|availability)\b", _I),
          "Specific SLA/uptime number (99.9% / 99.95% / 99.99%) in public copy without "
          "'designed to' / 'target' / 'aspirational' qualifier. Specific SLAs require "
          "sustained production measurement.",
          excused_by=re.compile(
              r"(designed[ ]+to|target(ed)?[ ]+(SLO|SLA)?|aspirational)[^.]{0,80}"
              r"(99\.9|99\.95|99\.99)", _I)),
)


def is_public(path: str) -> bool:
    if any(pattern.search(path) for pattern in EXEMPT):
        return False
    return any(pattern.search(path) for pattern in PUBLIC)


def lint(content: str) -> list[str]:
    return [check.message for check in CHECKS
            if check.pattern.search(content)
            and not (check.excused_by and check.excused_by.search(content))]


def main() -> None:
    c = create_context(PostToolUseContext)
    path = c.tool_input.get("file_path") or c.tool_input.get("filePath")
    if not path or not is_public(path):
        return
    content = c.tool_input.get("new_string") or c.tool_input.get("content")
    if not content:
        return

    warnings = lint(content)
    if not warnings:
        return

    layout = resolve()
    reference = f"{layout.kit_dir}/rules/public-copy.md" if layout else "rules/public-copy.md"
    print(f"Public copy lint — advisory warnings on {path}:")
    print()
    for warning in warnings:
        print(f"  [WARN] {warning}")
        print()
    print(f"Reference: {reference}.")


if __name__ == "__main__":
    main()

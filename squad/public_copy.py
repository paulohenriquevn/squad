"""Claims that measurement has not earned — the rule, defined once.

`rules/public-copy.md` is the contract and two hooks enforce it: `public-copy-lint`
after an edit, `stop-validation` at the end of the session. They used to carry
separate lists, and the smaller one was the one that ran last: seven of the nine
checks never reached the Stop gate, so a README could be warned about at 14:02
and pass the end-of-session gate at 14:40 unchanged.

That is the shape `_credential_globs` already refuses in this kit — a rule living
in one file and missing from another is how the gap reopens. The two hooks differ
in WHEN they ask and in what they do with the answer; the question is here.

What it guards is narrow: a README says things to people who cannot check them,
and the cheapest sentence to write is the one nobody has measured.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


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

#: Files a stranger reads to decide whether to trust the project.
PUBLIC = (re.compile(r"(^|/)README\.md$"),
          re.compile(r"(^|/)PITCH\.md$"),
          re.compile(r"docs/marketing/[^/]+\.md$"),
          re.compile(r"docs/guides/[^/]+\.md$"))

#: Places where a measured claim is the POINT — a benchmark report exists to say
#: what was measured, and linting it for confidence would be backwards.
EXEMPT = (re.compile(r"docs/exploration-reports/"),
          re.compile(r"docs/benchmarks/"),
          re.compile(r"docs/[aA][dD][rR]/"))


def is_public(path: str) -> bool:
    if any(pattern.search(path) for pattern in EXEMPT):
        return False
    return any(pattern.search(path) for pattern in PUBLIC)


def warnings(content: str) -> list[str]:
    """Every claim in `content` the evidence beside it does not carry.

    `content` is the WHOLE file, never the edited fragment: `excused_by` asks
    whether the evidence travels with the sentence, and an `Edit` hands over the
    replaced text alone — so a benchmark link two paragraphs up was invisible and
    the claim it excuses was reported anyway.
    """
    return [check.message for check in CHECKS
            if check.pattern.search(content)
            and not (check.excused_by and check.excused_by.search(content))]

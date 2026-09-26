r"""The sunset policy every allowlist in this kit declares, in one place.

WHY THIS MODULE EXISTS. Three files in `rules/` document the same exemption contract —
pipe-separated fields, an ISO sunset that MUST be within 90 days, expired entries
ignored so the finding re-fires at full severity, a malformed entry refused rather than
skipped. One of the three enforced it. The other two enforced nothing at all, because
nothing read them:

    code-quality-allowlist.txt    load_allowlist()          parsed and enforced
    deps-audit-allowlist.txt      -                         no reader anywhere
    plan-confidence-allowlist.txt -                         no reader anywhere

The second is the worse of the two. `check_deps_audit.py` emits, inside a HARD cap,
"Bump the dependency, or allowlist the CVE in `rules/deps-audit-allowlist.txt` with
rationale and sunset" — so the gate instructed a reader to write an entry into a file
that nothing opened. Following the instruction changed nothing, and the gate went on
failing with the same message.

WHAT IS SHARED AND WHAT IS NOT. The FIELDS differ per allowlist and stay with their
consumers: a CVE exemption names a package and an advisory, a plan exemption names a
slug. What is shared is the POLICY — the window, what an expired entry means, and that
a malformed one is an error rather than a silently dropped line. That is the knowledge
that was written three times and enforced once, and it is what belongs here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

#: The window every allowlist header in `rules/` declares. One number, one place.
MAX_SUNSET_DAYS = 90

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def today() -> date:
    """Indirection so a test can pin the day without touching the clock."""
    return date.today()


class MalformedEntry(ValueError):
    """An allowlist line that cannot be read.

    Raised rather than skipped, and that is the whole contract: a dropped line is an
    exemption someone believes they have and does not, which is strictly worse than a
    refusal they can see.
    """


@dataclass(frozen=True)
class Entry:
    """One exemption: the consumer's own fields, plus the shared sunset."""

    fields: tuple[str, ...]
    sunset: date
    line_number: int

    @property
    def expired(self) -> bool:
        return self.sunset < today()


def parse_sunset(value: str, *, where: str, line_number: int) -> date:
    """The ISO date, refusing both a malformed one and a window beyond the policy.

    A sunset already PAST parses fine: the contract is that an expired entry is ignored
    at scoring time and REPORTED as expired. Refusing to parse it would hide the expiry
    rather than surface it.

    The window is measured against TODAY rather than the entry's creation date, which
    nothing on disk records. The approximation is strictly tighter than the contract —
    an entry written 30 days ago with a 90-day window has 60 days left, and a sunset
    beyond today+90 could not have satisfied the rule on any creation date.
    """
    if not ISO_DATE_RE.match(value):
        raise MalformedEntry(
            f"{where} line {line_number}: malformed sunset date {value!r} (expected YYYY-MM-DD)"
        )
    try:
        sunset = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise MalformedEntry(
            f"{where} line {line_number}: malformed sunset date {value!r}: {error}"
        ) from error
    if sunset > today() + timedelta(days=MAX_SUNSET_DAYS):
        raise MalformedEntry(
            f"{where} line {line_number}: sunset {value} is more than {MAX_SUNSET_DAYS} "
            f"days out. Every allowlist in `rules/` sets the window at {MAX_SUNSET_DAYS} "
            f"days from entry creation; a longer one is a permanent exemption with a "
            f"date on it"
        )
    return sunset


def parse(
    rule_file: Path,
    *,
    field_count: int,
    sunset_index: int,
    where: str | None = None,
) -> list[Entry]:
    """Every entry in `rule_file`, with its sunset validated.

    `field_count` and `sunset_index` are the consumer's shape. Comments and blank lines
    are skipped; a line with the wrong number of fields is a `MalformedEntry`, never a
    skipped line. A file that does not exist is an EMPTY allowlist rather than an error:
    exempting nothing is the correct default, and a project that never wrote one should
    not be blocked by its absence.
    """
    label = where or rule_file.name
    if not rule_file.is_file():
        return []
    entries: list[Entry] = []
    for line_number, raw in enumerate(rule_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = tuple(part.strip() for part in line.split("|"))
        if len(parts) != field_count:
            raise MalformedEntry(
                f"{label} line {line_number}: malformed entry (expected {field_count} "
                f"pipe-separated fields, got {len(parts)}): {raw!r}"
            )
        sunset = parse_sunset(parts[sunset_index], where=label, line_number=line_number)
        entries.append(Entry(fields=parts, sunset=sunset, line_number=line_number))
    return entries


def active(entries: list[Entry]) -> list[Entry]:
    """The entries that still exempt. An expired one is ignored, never honoured."""
    return [entry for entry in entries if not entry.expired]

"""Whether a brief's quoted evidence still says what the brief says it says.

WHY THIS EXISTS
---------------
A citation that RESOLVES is not a citation that still HOLDS. Measured on a consumer: a
brief scored 34/34 while its load-bearing line had moved and changed meaning —

    brief:  `../appteste/server/gateway-agents.ts:38` — `const WEBHOOK_ONLY = new Set(['line','whatsapp'])`
    today:  40:const WEBHOOK_ONLY = new Set(['line', 'whatsapp', 'teams', 'sms'])

Two platforms had become four, and the design was drawn for two. The only gate that read
the citation asked whether the path existed and had that many lines. Both were true.

WHY IT NEVER SCORES
-------------------
Everything here is ADVISORY and feeds no criterion. A legitimate refactor moves lines;
a brief that stopped scoring because the code it describes improved would be a gate
people disable. "The evidence may have aged" is not "the brief is invalid" — it is the
state a reviewer should read before signing, and what was missing is telling them where.

WHAT IS READ
------------
The convention both consumer briefs already used: a backticked `path:line`, a dash, and
a backticked fragment —

    `server/agents.ts:38` — `const WEBHOOK_ONLY = new Set(['line','whatsapp'])`

A citation with no quoted fragment is not checked here: there is nothing it claims the
line says, and `check_evidence_pointers.py` already answers whether it resolves.
"""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: `path:line` — `fragment`, or `path:first-last` — `fragment`. The dash may be an em
#: dash, an en dash, `-` or `--`, because authors type all four and the meaning is the same.
_QUOTED_CITATION_RE = re.compile(
    r"`(?P<path>[^`\s:]+):(?P<line>\d+)(?:-(?P<last>\d+))?`\s*(?:—|–|--|-)\s*"
    r"`(?P<fragment>[^`\n]+)`")

#: Any backticked `path:line` or `path:first-last`, quoted or not. The AGE of the
#: evidence is a question about every citation: measured on 56 consumer briefs
#: (2026-09-25), 54 cite `file:line` without quoting it, so reading only quoted ones
#: would have dated the evidence of two.
_CITATION_RE = re.compile(r"`(?P<path>[^`\s:]+\.[\w]+):(?P<line>\d+)(?:-\d+)?`")

#: A brief's own date, as the brief header writes it: `**Date:** 2026-08-30`.
_DECLARED_DATE_RE = re.compile(r"^\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})\b", re.MULTILINE)

#: An author abbreviating a long line. Each side of it must still be on the line, in order.
_ELLIPSIS_RE = re.compile(r"\.\.\.|…")


@dataclass(frozen=True)
class QuotedCitation:
    path: str
    line: int
    fragment: str
    #: The last line of a `path:first-last` range; equal to `line` for a single line.
    last: int = 0


@dataclass(frozen=True)
class QuoteCheck:
    """One quoted citation and what its line says today.

    `state` is one of:
      matches     the fragment is on the cited line
      moved       the fragment is intact on another line (`found_at`); only the number aged
      changed     the fragment is on no line of the file — the content the brief relied on
                  is not there any more
      unresolved  the path resolves under no root, so the quote was NOT checked. Reported
                  rather than skipped: silence would read as "the quote held".
    """

    citation: QuotedCitation
    state: str
    found_at: int | None = None


@dataclass(frozen=True)
class AgedCitation:
    """A cited file whose last commit is newer than the brief's."""

    path: str
    file_committed: str
    brief_committed: str


def quoted_citations(body: str) -> tuple[QuotedCitation, ...]:
    return tuple(
        QuotedCitation(m.group("path"), int(m.group("line")), m.group("fragment"),
                       int(m.group("last") or m.group("line")))
        for m in _QUOTED_CITATION_RE.finditer(body))


def _search_roots(brief_path: Path) -> list[Path]:
    """The brief's directory and its ancestors up to the enclosing repository, then cwd.

    Bounded at the first ancestor holding `.git`: past it, a relative path like
    `server/x.ts` could resolve to an unrelated file in some parent directory, and a quote
    checked against the wrong file is worse than one not checked.
    """
    roots: list[Path] = []
    for directory in (brief_path.resolve().parent, *brief_path.resolve().parents):
        roots.append(directory)
        if (directory / ".git").exists():
            break
    roots.append(Path.cwd())
    return roots


def _resolve(path: str, roots: list[Path]) -> Path | None:
    for root in roots:
        candidate = root / path
        if candidate.is_file():
            return candidate
    return None


def _squash(text: str) -> str:
    """Whitespace is layout, not content: `['a','b']` quotes `['a', 'b']` faithfully."""
    return re.sub(r"\s+", "", text)


def _line_holds(line: str, fragment: str) -> bool:
    parts = [_squash(p) for p in _ELLIPSIS_RE.split(fragment) if _squash(p)]
    haystack = _squash(line)
    position = 0
    for part in parts:
        found = haystack.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    return bool(parts)


def _check_one(citation: QuotedCitation, roots: list[Path]) -> QuoteCheck:
    target = _resolve(citation.path, roots)
    if target is None:
        return QuoteCheck(citation, "unresolved")
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    last = max(citation.line, citation.last)
    region = "\n".join(lines[max(citation.line - 1, 0):last])
    if _line_holds(region, citation.fragment):
        return QuoteCheck(citation, "matches", citation.line)
    holding = [n for n, text in enumerate(lines, start=1)
               if _line_holds(text, citation.fragment)]
    if holding:
        nearest = min(holding, key=lambda n: abs(n - citation.line))
        return QuoteCheck(citation, "moved", nearest)
    if _line_holds("\n".join(lines), citation.fragment):
        # Intact, but spread across lines no single one of which holds it. Still the
        # content the brief relied on; only where it sits is unknown.
        return QuoteCheck(citation, "moved")
    return QuoteCheck(citation, "changed")


def check_quotes(body: str, brief_path: Path) -> tuple[QuoteCheck, ...]:
    roots = _search_roots(Path(brief_path))
    return tuple(_check_one(c, roots) for c in quoted_citations(body))


def _last_commit(path: Path) -> int | None:
    """Unix time of the last commit touching `path`, or None when git cannot say.

    Commit time and not mtime: a fresh clone gives every file the same mtime, so mtime
    would report every citation as aged or none of them, depending on checkout order.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(path.parent), "log", "-1", "--format=%ct", "--", path.name],
            capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    stamp = done.stdout.strip()
    return int(stamp) if done.returncode == 0 and stamp.isdigit() else None


def _date(stamp: int) -> str:
    return _dt.datetime.fromtimestamp(stamp, _dt.timezone.utc).date().isoformat()


def _brief_date(body: str, brief_path: Path) -> tuple[int, str] | None:
    """When the brief was written: its last commit, else the `**Date:**` it declares.

    The fallback is not optional. A consumer's briefs live under `.claude/` or `.squad/`,
    which are never versioned, so on every consumer measured the brief had no commit and a
    commit-only reader would have reported "not measured" for all of them. Not mtime:
    signing a brief rewrites the file, and the signature would make its evidence look fresh.
    """
    stamp = _last_commit(Path(brief_path).resolve())
    if stamp is not None:
        return stamp, _date(stamp)
    declared = _DECLARED_DATE_RE.search(body)
    if declared:
        day = _dt.date.fromisoformat(declared.group(1))
        # The END of the declared day: a file committed the same day is not "after" it.
        end = _dt.datetime.combine(day, _dt.time.max, tzinfo=_dt.timezone.utc)
        return int(end.timestamp()), declared.group(1)
    return None


def aged_citations(body: str, brief_path: Path) -> tuple[AgedCitation, ...] | None:
    """Cited files last committed AFTER the brief was written, once per file.

    None — not an empty tuple — when the brief has neither a commit nor a declared date:
    there is nothing to compare against, and the caller says "not measured" rather than
    letting silence read as "fresh".
    """
    if not _CITATION_RE.search(body):
        return ()
    dated = _brief_date(body, brief_path)
    if dated is None:
        return None
    brief_stamp, brief_day = dated
    roots = _search_roots(Path(brief_path))
    aged: list[AgedCitation] = []
    seen: set[str] = set()
    for match in _CITATION_RE.finditer(body):
        path = match.group("path")
        if path in seen:
            continue
        seen.add(path)
        target = _resolve(path, roots)
        stamp = _last_commit(target) if target else None
        if stamp is not None and stamp > brief_stamp:
            aged.append(AgedCitation(path, _date(stamp), brief_day))
    return tuple(aged)

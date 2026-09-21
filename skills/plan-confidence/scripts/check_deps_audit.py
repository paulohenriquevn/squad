"""The CVE gate, mechanized.

`cycle-plan.md § Phase contracts` lists "no critical CVE on a planned dependency"
among the phase's hard gates, and then says what no other gate in that cycle needs
to say:

    **The `deps-audit` gate is the one gate in this cycle nothing mechanizes.**
    Every other hard gate above is checked by a script that can fail the phase.
    This one is not.

So the gate held only when a human remembered to run `/deps-audit` and to honour
its verdict. A gate whose execution depends on memory is a note.

WHAT THIS CHECK ASSERTS — AND WHAT IT REFUSES TO
-------------------------------------------------
It does NOT look for CVEs. `/deps-audit` does that, with the scanners
(osv-scanner, npm audit, pip-audit, cargo audit, govulncheck). This reads the
VERDICT that run left on disk and turns it into a cap:

| State                                              | Effect |
|---|---|
| Plan declares no new dependency                    | does not apply |
| Declares one, and no audit report exists           | soft floor (≤ 89) — nobody checked |
| Report says CRITICAL/HIGH CVE in a declared dep    | hard cap (≤ 49) |
| Report unreadable or missing its verdict line      | soft floor — absent verdict, not a clean one |

Absence of an audit never becomes "no CVE". Same rule as a zero denominator in D4
and an unparseable coverage report: not measured is not measured, never approved.

WHY A SOFT FLOOR AND NOT A HARD CAP FOR THE MISSING REPORT
-----------------------------------------------------------
A hard cap there would say "this plan has a critical CVE", which is a claim about
the dependency that nobody made. The honest claim is about the PROCESS — the
verification did not happen — and that is what a soft floor records. The hard cap
is reserved for a measured finding.
"""
from __future__ import annotations

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and a reader resolving one order found a directory a writer
# using another had never filled.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

_here = _Path_bootstrap(__file__).resolve()
for _up in _here.parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import re  # noqa: E402 — post-bootstrap import
from dataclasses import dataclass, field  # noqa: E402 — post-bootstrap import
from pathlib import Path  # noqa: E402 — post-bootstrap import

from squad.allowlist import (  # noqa: E402 — post-bootstrap import
    MalformedEntry,
    active as _active_entries,
    parse as _parse_allowlist,
)
from squad.paths import (  # noqa: E402 — post-bootstrap import
    DATA_DIRNAME,
    rules_dir,
    LEGACY_RECORDS_ROOTS,
    records_dir,
)

_VERDICT_RE = re.compile(r"^\*\*Verdict:\*\*\s*(?P<verdict>[A-Z_]+)", re.MULTILINE)
_SECTION_RE = re.compile(
    r"^##\s+Dependencies\b(?P<body>.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE
)
#: `(none — ...)`, `_none_` — the ways of declaring there is no new dependency.
#: `(nenhuma)` was accepted until 2026-08-27  # english-only: naming the term that was dropped
#: — a gate that reads Portuguese
#: lets a plan pass here while failing the repository's english-only check.
_EXPLICIT_NONE_RE = re.compile(r"\(\s*(none|no new)\b|^_none_$", re.IGNORECASE | re.MULTILINE)
#: A package cited in backticks on a table row or bullet.
_PACKAGE_RE = re.compile(r"`([A-Za-z0-9@][\w.@/-]*)`")
#: `### New`, `### Existing` — the subsections a Dependencies section is usually split
#: into. The explicit-none marker is scoped to the one that carries it.
_SUBSECTION_RE = re.compile(r"^###+\s+\S")

_CLEAN = frozenset({"PASS", "PASS_WITH_CAVEATS"})
_HARD = frozenset({"FAIL_INSECURE", "INVALID_PLAN_DEPS"})
_SOFT = frozenset({"FAIL_MEDIUM"})



@dataclass
class DepsAuditReport:
    """Result of binding a plan to its `/deps-audit` verdict."""

    applies: bool = False
    hard_cap: bool = False
    soft_floor: bool = False
    stable_id: str = ""
    verdict: str = ""
    audit_path: str = ""
    declared: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)


#: A backticked token ending in one of these is a FILE the plan edits, not a package it
#: depends on. `api/go.mod`, `charts/web-api/values.yaml` and `render.go` all reached the
#: package list once rows started being read, and each would have demanded a `/deps-audit`
#: for something no ecosystem can resolve.
_FILE_SUFFIXES = (
    ".go", ".py", ".ts", ".js", ".rs", ".java", ".sh", ".md", ".yaml", ".yml", ".json",
    ".toml", ".txt", ".lock", ".sum", ".mod", ".work", ".frozen", ".cfg", ".ini",
)


def _is_a_file_not_a_package(token: str) -> bool:
    return token.lower().endswith(_FILE_SUFFIXES)


#: A bullet declares a package only when the package OPENS it. Emphasis markers may wrap
#: it (`- **`pkg`** v1.2`), but a sentence that happens to contain a backtick does not
#: declare anything: `- **B-057** — blocking DoD (d): `task quality:gates` exits 5 on
#: `unhomed-logic`` named a GATE, and scanning the whole head took it for a package.
#: Found by a consumer session on the first pass after this rule shipped, in a plan where
#: it cost nothing only because an audit happened to exist.
_BULLET_HEAD_RE = re.compile(r"[-*+]\s+[*_]{0,2}`(?P<pkg>[A-Za-z0-9@][\w.@/-]*)`")


def _declared_on_line(line: str) -> list[str]:
    """The package a row or a bullet DECLARES — not every name a sentence mentions.

    A dependency is declared in the first cell of a table row or at the head of a
    bullet. Reading every backticked token instead pulled `serviceAccount.name`,
    `charts/web-api/values.yaml` and `r.logger` out of prose and rationale columns: 45
    false dependencies across 3 consumer plans, each of which would then have demanded
    a `/deps-audit` for a package that does not exist.
    """
    stripped = line.strip()
    # The table's header row and separator declare no package at all.
    if not stripped or set(stripped) <= set("|- :"):
        return []
    if stripped.startswith("|"):
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        found = _PACKAGE_RE.findall(cells[0]) if cells else []
    else:
        bullet = _BULLET_HEAD_RE.match(stripped)
        found = [bullet.group("pkg")] if bullet else []
    return [t for t in found if not _is_a_file_not_a_package(t)]


def _subsections(body: str) -> list[str]:
    """Split a `## Dependencies` body at its `###` headings, heading line included.

    Text before the first `###` is its own chunk, so a preamble saying there is nothing
    new cannot speak for the subsections that follow it.
    """
    chunks: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        if _SUBSECTION_RE.match(line) and current:
            chunks.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        chunks.append("\n".join(current))
    return chunks


def _declared_dependencies(plan_body: str) -> list[str]:
    """Packages the plan says it touches, read subsection by subsection.

    The explicit-none marker is scoped to the subsection carrying it. It used to be
    searched across the whole section body, so the near-universal shape

        ### New: (none)
        ### Existing — bumped for CVE remediation
        | `github.com/go-chi/chi/v5` | v5.2.5 | v5.2.6 | CVE-2026-72817 (HIGH) |

    returned NO dependencies at all: one `(none)` about new packages discarded every
    existing one, `applies` went false, and the gate required no audit. Measured on a
    consumer 2026-09-15 with exactly that plan shape and two HIGH CVEs in it — a
    security-driven bump is the case where an audit matters most, and it was the one
    case the gate could not see.
    """
    section = _SECTION_RE.search(plan_body)
    if section is None:
        return []
    chunks = _subsections(section.group("body"))
    if not chunks:
        return []
    # A marker in the PREAMBLE — before any subsection exists — is a statement about the
    # whole section, and two consumer plans make exactly that statement: "This change
    # adds no dependency ... No package, module, library, tool or service is introduced,
    # upgraded, pinned or removed." Scoping every marker to its own chunk without this
    # would have made those two plans demand an audit for packages they only NAME while
    # explaining why nothing changes.
    preamble, rest = chunks[0], chunks[1:]
    if not _SUBSECTION_RE.match(preamble) and _EXPLICIT_NONE_RE.search(preamble):
        return []
    packages: list[str] = []
    for chunk in ([preamble] if not _SUBSECTION_RE.match(preamble) else chunks[:1]) + rest:
        if _EXPLICIT_NONE_RE.search(chunk):
            continue
        for line in chunk.splitlines():
            packages.extend(_declared_on_line(line))
    # dedup preserving order
    return list(dict.fromkeys(packages))


def _project_root(plan_path: Path) -> Path:
    """Walk up from the plan to the root carrying the records, in both layouts."""
    for parent in plan_path.resolve().parents:
        if (parent / DATA_DIRNAME).is_dir():
            return parent
        for kb in LEGACY_RECORDS_ROOTS:
            if (parent / kb).is_dir():
                return parent
    return plan_path.resolve().parent


def _latest_audit(root: Path, slug: str) -> Path | None:
    candidates: list[Path] = []
    audits = records_dir(root, "audits")
    if audits is not None:
        candidates.extend(audits.glob(f"{slug}-deps-audit-*.md"))
    if not candidates:
        return None
    # By NAME: it carries the audit date. An mtime reshuffles with any copy or read,
    # without any audit having happened.
    return sorted(candidates, key=lambda p: p.name)[-1]


#: `ECOSYSTEM | PACKAGE | VERSION_RANGE | CVE_ID | SUNSET | RATIONALE`, the shape
#: `rules/deps-audit-allowlist.txt` has documented since it was written.
_ALLOWLIST_FIELDS = 6
_ALLOWLIST_SUNSET_INDEX = 4
_ALLOWLIST_CVE_INDEX = 3
_ALLOWLIST_REASON_INDEX = 5
_ALLOWLIST_NAME = "deps-audit-allowlist.txt"


def _allowlist_path(records_root: Path) -> Path | None:
    """Where the project's CVE exemptions live, or None when the project has no rules.

    `squad.paths.rules_dir` answers this, and is used rather than a tenth hand-rolled
    pair: its own docstring records nine sites resolving `rules/` vs `.claude/rules/`
    by hand, six in one order and three in the other, so a table edited in one place
    was invisible to half its readers.

    `records_root` is what `_project_root` returned, which is the directory CONTAINING
    the dated trail — `<project>/.squad` in the current layout. The rules live beside
    that directory, not inside it: nothing executes from the data root.
    """
    project = records_root.parent if records_root.name == DATA_DIRNAME else records_root
    rules = rules_dir(project)
    return (rules / _ALLOWLIST_NAME) if rules is not None else None


def _waived_advisories(root: Path) -> tuple[dict[str, str], list[str], list[str]]:
    """`(waived, expired, errors)` from the project's allowlist.

    WHY THIS EXISTS AT ALL. The hard cap below prints "Bump the dependency, or
    allowlist the CVE in `rules/deps-audit-allowlist.txt` with rationale and sunset",
    and until 2026-09-21 nothing in this kit opened that file. A reader who followed the
    instruction wrote an entry, re-ran the gate, and got the same message — the gate
    teaching a remedy it did not implement.

    Malformed entries are collected rather than raised, because this gate's job is to
    report on a plan: a broken allowlist must surface as a reason a reader can act on,
    not as a traceback out of a scoring run. It still exempts NOTHING.
    """
    path = _allowlist_path(root)
    if path is None:
        # No `rules/` at all: the project declared no exemptions, which exempts nothing
        # and is not an error. An absent allowlist is an empty one.
        return {}, [], []
    try:
        entries = _parse_allowlist(
            path, field_count=_ALLOWLIST_FIELDS, sunset_index=_ALLOWLIST_SUNSET_INDEX,
            where=_ALLOWLIST_NAME,
        )
    except MalformedEntry as error:
        return {}, [], [str(error)]
    except OSError as error:
        return {}, [], [f"{_ALLOWLIST_NAME} could not be read: {error}"]

    waived = {
        entry.fields[_ALLOWLIST_CVE_INDEX]: entry.fields[_ALLOWLIST_REASON_INDEX]
        for entry in _active_entries(entries)
    }
    expired = [e.fields[_ALLOWLIST_CVE_INDEX] for e in entries if e.expired]
    return waived, expired, []


def _unwaived_advisories(audit_body: str, waived: dict[str, str]) -> list[str]:
    """Advisory ids named in the report that no ACTIVE entry waives.

    An empty list means every advisory the report names is waived — and only then may
    the hard cap lift. A report whose advisories cannot be identified at all yields the
    report's own text as one unwaivable item, because "we could not tell which CVE this
    is" must never resolve to "it is waived".
    """
    found = _ADVISORY_RE.findall(audit_body)
    if not found:
        return ["<no advisory id in the report>"]
    return sorted({advisory for advisory in found if advisory not in waived})


#: `GHSA-xxxx-xxxx-xxxx` and `CVE-YYYY-NNNN`, the two identifier shapes the scanners emit.
_ADVISORY_RE = re.compile(r"\b(?:GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}|CVE-\d{4}-\d{4,7})\b",
                          re.IGNORECASE)


def check_deps_audit(plan_path: Path) -> DepsAuditReport:
    """Bind a plan's declared dependencies to the `/deps-audit` verdict on disk."""
    body = plan_path.read_text(encoding="utf-8-sig")
    declared = _declared_dependencies(body)
    if not declared:
        return DepsAuditReport(applies=False)

    slug = plan_path.stem[: -len("-plan")] if plan_path.stem.endswith("-plan") else plan_path.stem
    root = _project_root(plan_path)
    audit = _latest_audit(root, slug)

    if audit is None:
        return DepsAuditReport(
            applies=True,
            soft_floor=True,
            stable_id="soft_floor_deps_audit_missing",
            declared=tuple(declared),
            reasons=(
                f"the plan declares {len(declared)} dependency/ies ({', '.join(declared)}) and no "
                f"`{slug}-deps-audit-*.md` exists — run `/deps-audit {slug}`. Absence of an audit "
                "is absence of a verdict, never a clean one.",
            ),
        )

    try:
        audit_body = audit.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return DepsAuditReport(
            applies=True, soft_floor=True, stable_id="soft_floor_deps_audit_missing",
            declared=tuple(declared), audit_path=str(audit),
            reasons=(f"deps-audit report unreadable: {e}",),
        )

    match = _VERDICT_RE.search(audit_body)
    if match is None:
        return DepsAuditReport(
            applies=True, soft_floor=True, stable_id="soft_floor_deps_audit_missing",
            declared=tuple(declared), audit_path=str(audit),
            reasons=(f"{audit.name} has no `**Verdict:**` line — an audit with no verdict is an "
                     "absent verdict",),
        )

    verdict = match.group("verdict")
    common = {"applies": True, "verdict": verdict, "audit_path": str(audit),
              "declared": tuple(declared)}

    # Does the audit MENTION each dependency the plan declares?
    #
    # Nothing asked. The verdict was read off the report's `**Verdict:**` line and
    # applied to `declared` — the hard-cap reason even says the audit "reports {verdict}
    # against the declared dependencies ({', '.join(declared)})" — while the two lists
    # were never compared. So a PASS over a scan that covered one package cleared a plan
    # that declared four, and the reason SAID it had covered all four.
    #
    # Mentioned, not "scanned": this reads a markdown report, and the strongest honest
    # claim is that the name appears in it. A name that does not appear was certainly
    # not audited, which is the direction that matters.
    unmentioned = tuple(d for d in declared if d.lower() not in audit_body.lower())
    if unmentioned:
        return DepsAuditReport(
            **common, soft_floor=True, stable_id="soft_floor_deps_audit_partial",
            reasons=(f"{audit.name} reports {verdict}, and {len(unmentioned)} of "
                     f"{len(declared)} declared dependencies are not named in it: "
                     f"{', '.join(unmentioned)}. A verdict covers what was scanned; "
                     f"applying it to a dependency the report never mentions is the "
                     f"scan's silence read as its approval.",),
        )

    if verdict in _CLEAN:
        return DepsAuditReport(**common)
    if verdict in _HARD:
        waived, expired, allowlist_errors = _waived_advisories(root)
        unwaived = _unwaived_advisories(audit_body, waived)

        if not allowlist_errors and not unwaived:
            # Every advisory the report names carries an ACTIVE exemption. The cap
            # lifts, and the reason SAYS it was waived: an exemption a reader cannot
            # see reads as a CVE that was never there.
            return DepsAuditReport(
                **common,
                reasons=(f"{audit.name} reports {verdict}, and every advisory it names "
                         f"is waived in `rules/{_ALLOWLIST_NAME}`: "
                         + "; ".join(f"{cve} — {why}" for cve, why in sorted(waived.items()))
                         + ". A waived CVE is still a CVE: the entry expires, and the "
                         "cap returns with it.",),
            )

        detail = []
        if allowlist_errors:
            detail.append("the allowlist could not be read, so it exempts nothing: "
                          + "; ".join(allowlist_errors))
        if expired:
            detail.append(f"expired entr{'y' if len(expired) == 1 else 'ies'} ignored: "
                          + ", ".join(sorted(set(expired))))
        if unwaived and waived:
            detail.append("not waived: " + ", ".join(unwaived))

        return DepsAuditReport(
            **common, hard_cap=True, stable_id="deps_audit_insecure",
            reasons=(f"{audit.name} reports {verdict} against the declared dependencies "
                     f"({', '.join(declared)}) — `cycle-plan.md` blocks a plan carrying a known "
                     "CRITICAL/HIGH CVE. Bump the dependency, or allowlist the CVE in "
                     "`rules/deps-audit-allowlist.txt` with rationale and sunset."
                     + (" " + " ".join(detail) if detail else ""),),
        )
    if verdict in _SOFT:
        return DepsAuditReport(
            **common, soft_floor=True, stable_id="soft_floor_deps_audit_medium",
            reasons=(f"{audit.name} reports {verdict} — medium-severity findings against the "
                     "declared dependencies.",),
        )
    return DepsAuditReport(
        **common, soft_floor=True, stable_id="soft_floor_deps_audit_missing",
        reasons=(f"{audit.name} reports an unrecognised verdict {verdict!r}",),
    )

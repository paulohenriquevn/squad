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
import re  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402

from squad.paths import (  # noqa: E402
    DATA_DIRNAME,
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


def _declared_dependencies(plan_body: str) -> list[str]:
    section = _SECTION_RE.search(plan_body)
    if section is None:
        return []
    body = section.group("body")
    if _EXPLICIT_NONE_RE.search(body):
        return []
    # The table's header row and separator declare no package at all.
    packages: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or set(stripped) <= set("|- :"):
            continue
        packages.extend(_PACKAGE_RE.findall(stripped))
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

    if verdict in _CLEAN:
        return DepsAuditReport(**common)
    if verdict in _HARD:
        return DepsAuditReport(
            **common, hard_cap=True, stable_id="deps_audit_insecure",
            reasons=(f"{audit.name} reports {verdict} against the declared dependencies "
                     f"({', '.join(declared)}) — `cycle-plan.md` blocks a plan carrying a known "
                     "CRITICAL/HIGH CVE. Bump the dependency, or allowlist the CVE in "
                     "`rules/deps-audit-allowlist.txt` with rationale and sunset.",),
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

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

import re
from dataclasses import dataclass, field
from pathlib import Path

_VERDICT_RE = re.compile(r"^\*\*Verdict:\*\*\s*(?P<verdict>[A-Z_]+)", re.MULTILINE)
_SECTION_RE = re.compile(
    r"^##\s+Dependencies\b(?P<body>.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE
)
#: `(none — ...)`, `(nenhuma)`, `_none_` — as formas de declarar que não há dependência nova.
_EXPLICIT_NONE_RE = re.compile(r"\(\s*(none|nenhuma|no new)\b|^_none_$", re.IGNORECASE | re.MULTILINE)
#: Um pacote citado em crase numa linha de tabela ou bullet.
_PACKAGE_RE = re.compile(r"`([A-Za-z0-9@][\w.@/-]*)`")

_CLEAN = frozenset({"PASS", "PASS_WITH_CAVEATS"})
_HARD = frozenset({"FAIL_INSECURE", "INVALID_PLAN_DEPS"})
_SOFT = frozenset({"FAIL_MEDIUM"})

_KB_DIRS = ("knowledge-base", ".claude/knowledge-base")


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
    # A linha de cabeçalho da tabela e o separador não declaram pacote nenhum.
    packages: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or set(stripped) <= set("|- :"):
            continue
        packages.extend(_PACKAGE_RE.findall(stripped))
    # dedup preservando ordem
    return list(dict.fromkeys(packages))


def _project_root(plan_path: Path) -> Path:
    """Sobe do plano até a raiz que carrega a knowledge-base, nos dois layouts."""
    for parent in plan_path.resolve().parents:
        for kb in _KB_DIRS:
            if (parent / kb).is_dir():
                return parent
    return plan_path.resolve().parent


def _latest_audit(root: Path, slug: str) -> Path | None:
    candidates: list[Path] = []
    for kb in _KB_DIRS:
        audits = root / kb / "audits"
        if audits.is_dir():
            candidates.extend(audits.glob(f"{slug}-deps-audit-*.md"))
    if not candidates:
        return None
    # Pelo NOME: ele carrega a data da auditoria. Um mtime reordena com qualquer
    # cópia ou leitura, sem que auditoria nenhuma tenha acontecido.
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

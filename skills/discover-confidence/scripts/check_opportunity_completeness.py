"""Mandatory-section + conditional-ADR checker for opportunities (M2 deterministic).

Verifies that the opportunity contains every mandatory section, and that an ADR is
present WHEN the change reaches beyond its own repo.

Replaces the ancestor `check_blueprint_completeness.py`. Two sections were dropped
and one requirement was made conditional:

  - `## Objective` folded into `## Context`. A maintenance opportunity's objective is
    the backlog item's DoD; restating it is duplication, not rigour.
  - `## Cross-cutting Comparison` removed outright. It compared REFERENCE PROJECTS to
    one another -- the prior-art practice this cycle no longer performs.
  - `## ADRs` made conditional on blast radius. Demanding an architectural decision
    record for a one-line fix in a leaf repo is ceremony; omitting one for a change
    that reaches other repos is how a breaking decision ships unrecorded.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# Each entry: (display name, regex matching the header)
MANDATORY_SECTIONS = [
    ("Header", r"^#\s+Opportunity:"),
    ("Item", r"^\*\*Item:\*\*\s*B-\d+"),
    ("Repo", r"^\*\*Repo:\*\*\s*\S+"),
    ("Mode", r"^\*\*Mode:\*\*\s*(?:review|live-test|bug|evolve)\b"),
    ("Context", r"^##\s+Context"),
    ("Corner 1 — Evidence", r"^##\s+Corner\s+1\s*(?:—|-)\s*Evidence"),
    ("Corner 2 — Constraint Relation", r"^##\s+Corner\s+2\s*(?:—|-)\s*Constraint\s+Relation"),
    ("Corner 3 — Blast Radius", r"^##\s+Corner\s+3\s*(?:—|-)\s*Blast\s+Radius"),
    ("Corner 4 — Verification", r"^##\s+Corner\s+4\s*(?:—|-)\s*Verification"),
    ("Recommendation", r"^##\s+Recommendation"),
]

ADR_HEADER_RE = re.compile(r"^###\s+D\d+\s*(?:—|-)", re.MULTILINE)
# `/` is in the class because a routing table addresses a monorepo module by PATH
# (`cmd/theo-ops`, `infra/tests`). Without it the capture stopped at the first segment,
# so a document whose repo is `cmd/theo-ops` matched no routing entry, counted ITSELF
# among the foreign repos, and was charged an ADR for a cross-repo change to the very
# repository it is about. Measured on a consumer path-addressed in 5 of 7 domains.
REPO_DECL_RE = re.compile(r"^\*\*Repo:\*\*\s*`?([A-Za-z0-9_.\-/]+)`?", re.MULTILINE)


def _known_repos(project_root: Path | None = None) -> set[str] | None:
    """The repos of THIS project, from the routing table it derived from disk.

    WHY THIS REPLACED A REGEX
    -------------------------
    This was a name-shape pattern — `theo(kit)?(-[a-z0-9]+)*` — under a comment
    claiming it was *"deliberately a NAME SHAPE rather than a hardcoded inventory"*
    so that it would not go stale. The shape WAS an inventory: it matched exactly
    one ecosystem's naming convention and nothing else.

    So in every consumer, `cross_repo` was False for every opportunity ever written,
    `no_adr_on_cross_repo_change` could not fire, and a change reaching three other
    repos scored identically to a one-line fix in a leaf. The gate read as enforced
    and measured nothing — the failure `rules/cycle-rule-schema.md` calls a contract
    without a mechanism, arriving from the side where the mechanism exists and is
    inert.

    The routing table is the honest source: `detect_domains.py` derives it FROM DISK,
    `route_domain.py` already parses it, and `rules/cycle-backlog.md § Routing
    invariants` makes one repo belong to exactly one domain. It cannot go stale in
    the way the comment feared without the routing gate going stale with it, and that
    one is exercised on every item.

    Returns `None` when no table can be read — which is NOT the same as "no foreign
    repos". The caller reports it as undetermined rather than as absence.
    """
    root = project_root or Path.cwd()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"))
        from route_domain import _routing_table_path, parse_routing_table
    except ImportError:
        return None

    table_path = _routing_table_path(root)
    if table_path is None:
        return None
    try:
        table = parse_routing_table(table_path)
    except (ValueError, OSError):
        return None

    repos = {r.lower() for entry in table.values() for r in entry.get("repos", ())}
    return repos or None


def _section_body(content: str, header_pattern: str) -> str:
    match = re.search(header_pattern, content, re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    start = match.end()
    next_h2 = re.search(r"^##\s+", content[start:], re.MULTILINE)
    return content[start : start + next_h2.start()] if next_h2 else content[start:]


def check_opportunity_completeness(
    opportunity_path: Path,
    *,
    known_repos: set[str] | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    content = opportunity_path.read_text(encoding="utf-8-sig")

    present: list[str] = []
    missing: list[str] = []

    for name, pattern in MANDATORY_SECTIONS:
        if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
            present.append(name)
        else:
            missing.append(name)

    adrs_body = _section_body(content, r"^##\s+ADRs\b")
    adr_count = len(ADR_HEADER_RE.findall(adrs_body))

    # Is the change cross-repo? Read the Blast Radius corner and look for any ecosystem
    # repo name other than the one this opportunity declares.
    repo_match = REPO_DECL_RE.search(content)
    own_repo = repo_match.group(1).lower() if repo_match else None

    blast_body = _section_body(content, r"^##\s+Corner\s+3\s*(?:—|-)\s*Blast\s+Radius")

    repos = known_repos if known_repos is not None else _known_repos(project_root)
    if repos is None:
        # No table, so no answer. Reporting `False` here would state that the change
        # is repo-local — a claim nothing checked — and `adr_missing` would then be
        # False for the same unchecked reason. Undetermined is the honest value, and
        # it does not silently satisfy the ADR requirement.
        foreign_repos: list[str] = []
        cross_repo: bool | None = None
        adr_required = False
    else:
        blast_lower = blast_body.lower()
        mentioned = {
            r for r in repos
            if re.search(rf"(?<![A-Za-z0-9_./-]){re.escape(r)}(?![A-Za-z0-9_-])", blast_lower)
        }
        # A repo NAMED IN ORDER TO RECORD THAT IT IS NOT REACHED is evidence, not a
        # cross-repo change. Without this, an author who enumerates the negative — the
        # strongest thing a blast radius can carry — is charged for a decision that does
        # not exist, and the only way to clear the gate is to delete the measurement.
        #
        # Measured 2026-09-12: three independent DISCOVER agents hit this in one session
        # on one project. Two wrote a defensive ADR for a non-existent decision; one
        # relocated the measurement out of the corner it belonged in. None deleted the
        # evidence, so the checker cost three authors work and bought nothing.
        #
        # The marker only ever SUBTRACTS, and only repos it names explicitly: an empty
        # marker is not a blanket exemption, and a repo genuinely reached is unaffected
        # by one appearing elsewhere in the same corner.
        not_reached = {
            r
            for m in re.finditer(r"<!--\s*NOT-REACHED:(.*?)-->", blast_body, re.DOTALL)
            for r in repos
            # The trailing class EXCLUDES `/` here, unlike the mention matcher above.
            # A marker naming `operators/api` must subtract that entry and nothing else:
            # with `/` permitted, `operators` matched inside it and a genuinely-reached
            # repo left `foreign_repos` unnamed, suppressing the ADR this gate exists to
            # demand. That fails OPEN, which is worse than the defect the marker fixed —
            # that one charged an author for an ADR nobody needed, and did it loudly.
            if re.search(
                rf"(?<![A-Za-z0-9_./-]){re.escape(r)}(?![A-Za-z0-9_\-/])", m.group(1).lower()
            )
        }
        foreign_repos = sorted(r for r in mentioned - not_reached if r != own_repo)
        cross_repo = bool(foreign_repos)
        adr_required = cross_repo
    adr_missing = adr_required and adr_count == 0

    total_required = len(MANDATORY_SECTIONS)
    found = len(present)

    contributors = [f"{found}/{total_required} mandatory sections present"]
    if adr_count > 0:
        contributors.append(f"{adr_count} ADR(s) found in ADRs section")
    if cross_repo is False:
        contributors.append("Change is repo-local — no ADR required")
    elif cross_repo is None:
        # Never phrased as "no ADR required": nothing established that.
        detractors_note = (
            "Blast radius could not be checked — no routing table found, so whether "
            "this change reaches another repo is undetermined "
            "(derive one with detect_domains.py --write)"
        )
        contributors.append(detractors_note)

    detractors: list[str] = [f"Missing section: {m}" for m in missing[:3]]
    if adr_missing:
        detractors.append(
            f"Blast radius reaches {', '.join(foreign_repos)} but no ADR is recorded"
        )

    return {
        "total_required": total_required,
        "found": found,
        "present": present,
        "missing_mandatory": missing,
        "adr_count": adr_count,
        "own_repo": own_repo,
        "foreign_repos": foreign_repos,
        "cross_repo": cross_repo,
        "cross_repo_determinable": cross_repo is not None,
        "adr_required": adr_required,
        "adr_missing": adr_missing,
        "contributors": contributors,
        "detractors": detractors,
    }

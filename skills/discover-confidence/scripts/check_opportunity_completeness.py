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

#: The literal line each mandatory section is found by, as a refusal prints it (#139).
#: "Missing section: Mode" named the section and not the line — `**Mode:** review`, with
#: its four accepted values — so the next command a caller ran was a grep of this file.
#: A test holds every form to its pattern above.
SECTION_FORMS = {
    "Header": "# Opportunity: <title>",
    "Item": "**Item:** B-001",
    "Repo": "**Repo:** <path of the repository this changes>",
    "Mode": "**Mode:** review|live-test|bug|evolve",
    "Context": "## Context",
    "Corner 1 — Evidence": "## Corner 1 — Evidence",
    "Corner 2 — Constraint Relation": "## Corner 2 — Constraint Relation",
    "Corner 3 — Blast Radius": "## Corner 3 — Blast Radius",
    "Corner 4 — Verification": "## Corner 4 — Verification",
    "Recommendation": "## Recommendation",
}

ADR_HEADER_RE = re.compile(r"^###\s+D\d+\s*(?:—|-)", re.MULTILINE)

#: The declared mode, so the mode's own evidence contract can be held to.
MODE_DECL_RE = re.compile(r"^\*\*Mode:\*\*\s*`?(review|live-test|bug|evolve)\b",
                          re.MULTILINE | re.IGNORECASE)

#: `**Failing test:** path/to/test_file.py::test_name` — the floor `cycle-discover.md`
#: sets for `bug`: *"no failing test, no bug"*.
#:
#: STRUCTURAL rather than a hunt through prose, and deliberately so. A regex looking for
#: "the test fails" would produce verdicts about language, which is the thing G3, G4 and
#: G5 are left conversational to avoid. The marker is declared the way a signature is,
#: and the checker asks two questions it can answer: is it there, and does the file
#: resolve. Whether the test genuinely fails is what `/discover-execute` runs and what
#: the panel judges.
#:
#: Measured 2026-09-21, before this existed: an opportunity declaring `**Mode:** bug`
#: whose Corner 1 said "No test written yet — the shape is obvious enough from the
#: repro" scored `opportunity_completeness: 100.0`, `weighted_avg: 100.0`, no cap. G-M
#: named this checker and the checker only asked whether the word `bug` was on the line.
FAILING_TEST_RE = re.compile(
    r"^\*\*Failing test:\*\*\s*`?([^`\s]+?)(?:::[^`\s]+)?`?\s*$",
    re.MULTILINE | re.IGNORECASE)

#: Which modes carry a structural evidence floor this checker can verify. `review`,
#: `live-test` and `evolve` state their contracts in `cycle-discover.md` too — a
#: `file:line`, a `METHOD URL -> status`, a measured number — and those are already
#: what `check_evidence_pointers` counts. Only `bug` names an artifact that either
#: exists on disk or does not.
MODE_FLOORS = {"bug": "a failing test"}

#: The item this opportunity is about — already mandatory as a section, captured here so
#: the id can be resolved against the registry.
ITEM_DECL_RE = re.compile(r"^\*\*Item:\*\*\s*`?(B-\d+)", re.MULTILINE)


def _registry_of(project_root: Path) -> Path | None:
    """`BACKLOG.md` at the project root, or `None` when there is none to read."""
    candidate = project_root / "BACKLOG.md"
    return candidate if candidate.is_file() else None


def _item_is_registered(project_root: Path, item_id: str) -> bool | None:
    """Is `item_id` a block in the registry? `None` when no registry was reachable.

    `None` is not `False`, and the distinction is the whole discipline: without a
    registry the question is unanswered, and reporting every opportunity as an orphan
    would assert a violation the evidence does not support — the same rule
    `check_measurement_targets` states about `live-target.txt` and
    `check_objective_coverage` about the objectives document.

    Parsed with `squad.backlog.BLOCK_RE`, the registry's one parser, so an item written
    with a hyphen separator is seen here exactly as the writer and the structure check
    see it.
    """
    registry = _registry_of(project_root)
    if registry is None:
        return None
    try:
        content = registry.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    from squad.backlog import BLOCK_RE

    return any(m.group(1) == item_id for m in BLOCK_RE.finditer(content))
# `/` is in the class because a routing table addresses a monorepo module by PATH
# (`cmd/service-ops`, `infra/tests`). Without it the capture stopped at the first segment,
# so a document whose repo is `cmd/service-ops` matched no routing entry, counted ITSELF
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


def _find_project_root(start: Path) -> Path:
    """Walk up from `start` looking for `.claude/` or `.git/` — the same walk
    `check_evidence_pointers` performs, so a mode's artifact and an evidence pointer
    resolve against one root rather than two."""
    current = start.resolve().parent if start.is_file() else start.resolve()
    while current != current.parent:
        if (current / ".claude").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return start.resolve().parent if start.is_file() else start.resolve()


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

    # ---- the mode's own floor (G-M) -----------------------------------------
    mode_match = MODE_DECL_RE.search(content)
    mode = mode_match.group(1).lower() if mode_match else None
    mode_contract_unmet = ""
    if mode in MODE_FLOORS:
        test_match = FAILING_TEST_RE.search(content)
        if not test_match:
            mode_contract_unmet = (
                f"`**Mode:** {mode}` and no `**Failing test:**` line. "
                f"`cycle-discover.md` sets the floor in four words — no failing test, "
                f"no bug — because a defect nobody can express as a failing test is not "
                f"yet understood well enough to fix, and the test is what proves the fix "
                f"later. Declare it as `**Failing test:** path/to/test.py::test_name`")
        else:
            root = project_root or _find_project_root(opportunity_path)
            rel = test_match.group(1)
            if not (root / rel).is_file() and not (root / ".claude" / rel).is_file():
                mode_contract_unmet = (
                    f"`**Failing test:** {rel}` names a file that is not on disk. A test "
                    f"nobody wrote is the fabricated-evidence shape, one field along")

    # ---- the finding reached the registry ------------------------------------
    #
    # `cycle-discover.md` calls "Sweeping without registering" an anti-pattern — "the
    # orphaned-finding failure the single registry exists to prevent" — and nothing
    # asked. The kit's own `good-opportunity.md` fixture is an opportunity ABOUT this
    # gap, shipped as the example of a good one: "The gate that the anti-pattern
    # implies does not exist." It does now.
    item_match = ITEM_DECL_RE.search(content)
    declared_item = item_match.group(1) if item_match else None
    root_for_registry = project_root or _find_project_root(opportunity_path)
    item_registered = (_item_is_registered(root_for_registry, declared_item)
                       if declared_item else None)

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

    # Every missing section, not the first three. Truncating told a reader three of N
    # and nothing about the rest, so they fixed three, re-ran, and met the next three —
    # and the session measured at 2026-09-18 went to this file's source to read
    # `MANDATORY_SECTIONS` instead. The document is fixed once when the list is whole.
    detractors: list[str] = [f"Missing section: {m} — write `{SECTION_FORMS[m]}`"
                             for m in missing]
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
        "mode": mode,
        "mode_contract_unmet": mode_contract_unmet,
        "declared_item": declared_item,
        "item_registered": item_registered,
        "item_registration_checked": item_registered is not None,
        "contributors": contributors,
        "detractors": detractors,
    }

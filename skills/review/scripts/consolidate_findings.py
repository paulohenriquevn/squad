#!/usr/bin/env python3
"""Consolidate findings from all spawned agents into a single severity-classified report.

Inputs:
  - A directory containing YAML findings files (one per agent)
  - Output path for the consolidated markdown report

Output:
  - Markdown report with severity-grouped findings + dedup + cross-agent cross-references
  - JSON summary printed to stdout

Severity classification (canonical — aligned with rules/cycle-review.md):
  - BLOCKER: cannot merge under any circumstance
  - HIGH:    cannot merge without ADR-style dismissal
  - MEDIUM:  surface to human; consider WITH_CAVEATS in PR
  - LOW:     log; merge can proceed
  - INFO:    informational, no action

Verdict bands:
  - READY_TO_MERGE: zero BLOCKER, ≤ 2 HIGH findings with documented mitigation
  - READY_TO_MERGE_WITH_FOLLOWUPS: zero BLOCKER, > 2 HIGH, and EVERY HIGH is a
    registered followup — named in the plan's `## Followups` section (via
    --plan) or carrying an issue reference (#NNN) in its recommended_action.
    Fail-closed: no --plan means nothing was proven registered.
  - NEEDS_FIXES:    ≥ 1 BLOCKER OR > 2 HIGH with any HIGH unregistered
  - NEEDS_DEEPER:   coverage of edge cases < 80% (declared via --edge-case-coverage-ratio) OR systemic issues exceeding targeted fixes

Why EVERY HIGH and not just "every HIGH above the cap" (the wording in
rules/cycle-review.md): with 5 HIGH findings, "above the cap" names 3 of them
and nothing says which 3 — any subset satisfies it, which is not a gate. The
implementation is the strict reading, and the rule was tightened to match.

Exit codes:
  0 — READY_TO_MERGE or READY_TO_MERGE_WITH_FOLLOWUPS
  1 — NEEDS_FIXES
  3 — NEEDS_DEEPER
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from datetime import datetime, timezone
from pathlib import Path
from pathlib import Path as _Path_bootstrap
from typing import Any

import yaml

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import records_dir  # noqa: E402 — post-bootstrap import

# The upstream gate lives beside this script. It runs as `__main__` (the directory
# enters sys.path on its own) and is also imported by tests that insert the directory
# by hand — the fallback covers the case where neither happened.
try:
    from check_upstream_gate import check_upstream_gate
except ImportError:  # pragma: no cover - alternative import path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_upstream_gate import check_upstream_gate

# The independent auditors are the kit's, not this skill's, so their coverage gate
# lives in `mechanisms/gates/`. Resolved through the project root rather than a fixed
# relative path, because a plugin install puts the kit under `.claude/`.
def _load_auditor_coverage():
    """`auditor_coverage_findings`, or None when the kit's gates are unreachable.

    A kit without the gate returns None and this skill says so as a finding, rather
    than silently reviewing as if no audit had ever been required.
    """
    here = Path(__file__).resolve()
    for root in here.parents:
        for gates in (root / "mechanisms" / "gates", root / ".claude" / "mechanisms" / "gates"):
            if (gates / "check_auditor_coverage.py").is_file():
                if str(gates) not in sys.path:
                    sys.path.insert(0, str(gates))
                try:
                    from check_auditor_coverage import auditor_coverage_findings
                except ImportError:  # pragma: no cover - environment, not logic
                    return None
                return auditor_coverage_findings
    return None

SEVERITY_ORDER = ["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]
# Back-compat alias map for findings emitted by agents using legacy tokens.
SEVERITY_ALIASES = {
    "CRITICAL": "HIGH",
    "MAJOR": "MEDIUM",
    "MINOR": "LOW",
}


def _read_findings_file(path: Path) -> dict[str, Any] | None:
    """Read one YAML findings file. Returns None when it could not be read.

    this returned `{}` on ANY error, and the caller could not tell that from a file whose
    `findings:` list was legitimately empty. It then counted the file in `agents_run` under its
    filename stem, so a malformed file became an agent that "ran cleanly and found nothing" and the
    report named six agents while grading a review that read one.

    `None` is the distinction. It is not a swallow (`rules/error-handling.md` § 5): the caller lists
    the file under `unreadable`, by name, in the report and in the JSON.
    """
    try:
        content = path.read_text(encoding="utf-8-sig")
        # Tolerate fenced YAML block
        if content.strip().startswith("```"):
            # Strip leading ``` and trailing ```
            lines = content.splitlines()
            start = 0
            end = len(lines)
            for i, line in enumerate(lines):
                if line.strip().startswith("```yaml") or line.strip() == "```":
                    if start == 0:
                        start = i + 1
                    else:
                        end = i
                        break
            content = "\n".join(lines[start:end])

        parsed = yaml.safe_load(content)
        if not isinstance(parsed, dict):
            # A bare string or a list parses fine and is not a findings file. Unreadable, not empty.
            return None
        return parsed
    except (yaml.YAMLError, OSError):
        return None


def _normalize_finding(f: dict[str, Any], agent_role: str) -> dict[str, Any]:
    """Coerce a finding to canonical shape; provide defaults."""
    severity = str(f.get("severity", "INFO")).upper()
    severity = SEVERITY_ALIASES.get(severity, severity)
    if severity not in SEVERITY_ORDER:
        severity = "INFO"

    return {
        "id": str(f.get("id", "")),
        # a re-review's whole job is to report whether the fixes worked, and this field was
        # dropped here, so the verdict could not tell a pass that CLOSED every finding from one that
        # closed none. Measured on an earlier second pass: NEEDS_FIXES with 5 HIGH, all five marked
        # CLOSED in the file the script had just read.
        #
        # Absence keeps today's behaviour (ADR D1): every findings file written before this omits
        # the field, and reinterpreting them would silently rescore every past review.
        "status": str(f.get("status", "")).upper(),
        "severity": severity,
        "file": str(f.get("file", "")),
        "line": f.get("line"),
        "plan_ref": str(f.get("plan_ref", "")),
        # `title` is what the GATE findings carry — `check_upstream_gate` writes
        # title/evidence/remediation and no summary. Dropping it here is where a
        # BLOCKER lost its name: counted, decisive, and rendered as `### : `.
        # Normalising at the entry point fixes every consumer of the field at
        # once, which the renderer alone could not.
        "summary": str(f.get("summary") or f.get("title") or ""),
        "evidence": str(f.get("evidence", "")),
        "recommended_action": str(f.get("recommended_action", "")),
        "domain_anchor": str(f.get("domain_anchor", "")),
        "found_by": agent_role,
    }


def _normalised_summary(summary: str) -> str:
    """What "the same finding" means. Whitespace and case only — never a paraphrase."""
    return " ".join(summary.split()).casefold()


def _dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine findings that say the SAME THING at the same place.

    this keyed on `(file, line, plan_ref)` alone and, on a collision, kept the FIRST
    finding's id and summary while raising its severity to the highest in the cluster. Measured on
    an earlier review: three findings shared `("src/prompts/select-list.tsx", 217, "")` — a refactor
    threshold (LOW), an unprotected half of a shipped change (HIGH), and a wrapping bug (LOW). The
    report printed the LOW text under `## HIGH findings`, and the finding that EARNED the HIGH
    appeared nowhere.

    The count was right and the verdict was right, which is what made it hard to see: the numbers
    vouched for content that was wrong.

    Two changes, and they are separable:

    1. **A file:line is a coordinate, not an issue.** Merging now requires the summaries to match
       after whitespace/case normalisation. Deduping on summary ALONE was rejected for the opposite
       reason — five agents describing one defect in five wordings would stay five rows — and that
       case is served by (2) rather than by dropping rows.
    2. **The surviving row is the one that earned the severity**, and it lists every id it absorbed,
       so a reader can still find `F-dom-2` by name.
    """
    seen: dict[tuple[str, int | None, str, str], dict[str, Any]] = {}
    order: list[tuple[str, int | None, str, str]] = []
    for f in findings:
        key = (f["file"], f["line"], f["plan_ref"], _normalised_summary(f["summary"]))
        if key in seen and key[:3] != ("", None, ""):
            existing = seen[key]
            # Record BOTH ids before anything is overwritten. Doing this after the swap loses the
            # one being replaced, which is exactly the absorbed finding a reader comes looking for.
            merged = existing.setdefault("merged_ids", [existing["id"]])
            if f["id"] not in merged:
                merged.append(f["id"])
            if SEVERITY_ORDER.index(f["severity"]) < SEVERITY_ORDER.index(existing["severity"]):
                # The higher severity brings its own id and summary with it — that is the whole
                # point. They were travelling separately.
                existing["severity"] = f["severity"]
                existing["summary"] = f["summary"]
                existing["id"] = f["id"]
            existing_found_by = existing.get("found_by_list", [existing["found_by"]])
            existing_found_by.append(f["found_by"])
            existing["found_by_list"] = existing_found_by
        else:
            f["found_by_list"] = [f["found_by"]]
            seen[key] = f
            order.append(key)
    return [seen[k] for k in order]


FOLLOWUPS_SECTION_RE = re.compile(
    r"^##\s+Followups\s*$(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL
)
ISSUE_REF_RE = re.compile(r"#\d+")


# the ids `spawn_reviewers.py` mandates in every agent brief look like `F-arch-1`, and the
# previous pattern (`\b[A-Za-z]+-\d+\b`) extracted `arch-1` from them: `\b[A-Za-z]+` cannot start at
# `F`, because `F-` is not followed by digits, so the match began after the first hyphen.
#
# The finding's id was `F-arch-1`, the registered token was `arch-1`, and the comparison never
# matched — so no `F-`-prefixed id could EVER be registered, and `READY_TO_MERGE_WITH_FOLLOWUPS`, a
# verdict `cycle-rule-schema.md` publishes and `cycle-review.md § Verdicts` describes, was
# unreachable for every review this repository has run.
#
# It stayed hidden because every review either had <= 2 HIGH findings or fixed them all, so the
# branch was never exercised.
FINDING_ID_RE = re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+)*-\d+\b")


def _normalise_id(token: str) -> str:
    """Both sides of the comparison, folded the same way.

    The defect was an ASYMMETRY — one side parsed, the other not. Normalising only the registered
    side would move the mismatch rather than remove it. Case is folded because a plan is prose
    written by hand, and `F-Arch-1` is a typo that should register rather than silently fail.
    """
    return token.strip().casefold()


def _registered_followup_ids(plan_path: Path | None) -> set[str]:
    """Finding ids named under the plan's `## Followups` section."""
    if plan_path is None or not plan_path.exists():
        return set()
    match = FOLLOWUPS_SECTION_RE.search(plan_path.read_text(encoding="utf-8-sig"))
    if not match:
        return set()
    body = match.group(1)
    return {_normalise_id(token) for token in FINDING_ID_RE.findall(body)}


def _unregistered_high(findings: list[dict[str, Any]], registered: set[str]) -> list[str]:
    """HIGH findings that nobody owns.

    A finding is owned when the plan's `## Followups` names its id, or when it
    carries an issue reference in `recommended_action`. A finding with no id at
    all can never be owned — fail-closed, deliberately.
    """
    unowned: list[str] = []
    for f in findings:
        if f["severity"] != "HIGH":
            continue
        fid = f.get("id", "")
        if fid and _normalise_id(fid) in registered:
            continue
        if ISSUE_REF_RE.search(f.get("recommended_action", "")):
            continue
        unowned.append(fid or f.get("summary", "<unidentified finding>"))
    return unowned



def _project_root_for(findings_dir: Path) -> Path:
    """Walk up from the findings directory to the root carrying the records.

    `/review` writes findings under `agents/review-{slug}-{date}/`, so the root is
    the ancestor holding `records/` or `.claude/records/` — the two
    installation layouts.
    """
    current = findings_dir.resolve()
    for candidate in (current, *current.parents):
        if records_dir(candidate) is not None:
            return candidate
    return current


def _heading(f: dict[str, Any]) -> str:
    """`### <id>: <summary>` — for findings that HAVE an id and a summary.

    Gate findings do not. `check_upstream_gate` writes `title` / `evidence` /
    `remediation` and no id, so the heading rendered as `### : ` — a BLOCKER that
    is counted, is decisive, and does not say what it is. Measured on 2026-08-29:
    a consumer's smoke validator failed on it and could report only
    "consolidate_findings exit 1:" with nothing after the colon.

    A gate whose reason cannot be read is a gate people route around, so the
    heading falls back through what the finding actually carries and, failing
    everything, names its source rather than rendering empty.
    """
    ident = str(f.get("id") or "").strip()
    label = str(f.get("summary") or f.get("title") or "").strip()
    if not label:
        label = str(f.get("category") or f.get("source") or "unnamed finding").strip()
    return f"### {ident}: {label}" if ident else f"### {label}"


def _classify_verdict(
    findings: list[dict[str, Any]],
    coverage_ratio: float | None,
    unregistered_high: list[str] | None = None,
) -> str:
    """Determine final verdict from findings + coverage + followup registration."""
    blocker_count = sum(1 for f in findings if f["severity"] == "BLOCKER")
    high_count = sum(1 for f in findings if f["severity"] == "HIGH")

    if blocker_count > 0:
        return "NEEDS_FIXES"
    if high_count > 2:
        # The debt is real; the only question is whether it is named and owned.
        if unregistered_high:
            return "NEEDS_FIXES"
        return "READY_TO_MERGE_WITH_FOLLOWUPS"
    if coverage_ratio is not None and coverage_ratio < 0.80:
        return "NEEDS_DEEPER"
    # A None ratio does NOT reach `NEEDS_DEEPER`, deliberately: not measuring edge-case
    # coverage is not evidence that it is poor, and blocking every review that lacked
    # the input would make the input optional in name only. The report says NOT
    # MEASURED in the header instead, so the gap is visible where the verdict is read.
    return "READY_TO_MERGE"


def _render_markdown(
    slug: str,
    date: str,
    findings_by_severity: dict[str, list[dict[str, Any]]],
    agents_run: list[str],
    verdict: str,
    coverage_ratio: float | None,
    total_findings: int,
    closed: list[dict[str, Any]] | None = None,
    contamination: dict[str, Any] | None = None,
    unreadable: list[str] | None = None,
) -> str:
    md = [
        f"# Review: {slug}",
        "",
        f"**Date:** {date}",
        f"**Verdict:** {verdict}",
        f"**Reviewers (spawned agents):** {len(agents_run)} ({', '.join(agents_run)})",
        f"**Total findings:** {total_findings}",
        "",
    ]
    if coverage_ratio is not None:
        md.append(f"**Edge-case coverage:** {coverage_ratio:.0%}")
    else:
        # SAID, not skipped. A missing ratio used to leave the line out entirely, so a
        # report where coverage was never measured looked exactly like one where the
        # line happened to scroll past — and the verdict path below already declines to
        # apply the 0.80 band, silently. Two silences over one unmeasured thing.
        md.append("**Edge-case coverage:** NOT MEASURED — the band below was not "
                  "applied, so this verdict says nothing about edge-case coverage.")
    md.append("")
    if contamination:
        # Near the top on purpose: a reader who learns this in a footer has already believed the
        # findings above it.
        changed = " and ".join(contamination.get("changed", []))
        md += [
            "## ⚠ Working tree contaminated during this review",
            "",
            (f"The tree moved while the agents were reading it ({changed} differ from the state "
            "recorded when they were spawned). Findings below may cite code no reviewer saw, or "
            "miss code that was there. Re-derive any citation before acting on it."),
            "",
        ]

    md.append("## Findings summary by severity")
    md.append("")
    md.append("| Severity | Count |")
    md.append("|---|---|")
    for sev in SEVERITY_ORDER:
        count = len(findings_by_severity.get(sev, []))
        md.append(f"| {sev} | {count} |")
    md.append("")

    for sev in SEVERITY_ORDER:
        items = findings_by_severity.get(sev, [])
        if not items:
            continue
        md.append(f"## {sev} findings ({len(items)})")
        md.append("")
        for f in items:
            md.append(_heading(f))
            md.append("")
            md.append(f"- **Found by:** {', '.join(f.get('found_by_list', [f['found_by']]))}")
            # name what this row absorbed. A merged finding used to vanish entirely, so a
            # reader searching for `F-dom-2` found nothing; the row it was folded into carried
            # somebody else's id.
            absorbed = [i for i in f.get("merged_ids", []) if i != f["id"]]
            if absorbed:
                md.append(f"- **Also reported as:** {', '.join(absorbed)}")
            if f["file"]:
                md.append(f"- **File:** `{f['file']}`{(' line ' + str(f['line'])) if f['line'] else ''}")
            if f["plan_ref"]:
                md.append(f"- **Plan reference:** {f['plan_ref']}")
            if f["domain_anchor"]:
                md.append(f"- **Domain anchor:** {f['domain_anchor']}")
            if f["evidence"]:
                md.append("- **Evidence:**")
                md.append("")
                for line in f["evidence"].splitlines():
                    md.append(f"  {line}")
                md.append("")
            if f["recommended_action"]:
                md.append(f"- **Recommended action:** {f['recommended_action']}")
            md.append("")
        md.append("")

    md.append("## Handoff decision")
    md.append("")
    if verdict == "READY_TO_MERGE":
        md.append("Implementation passes all gates. Ready for merge.")
    elif verdict == "READY_TO_MERGE_WITH_FOLLOWUPS":
        md.append(
            "No BLOCKER, and more than 2 HIGH — every one of them registered as a followup. "
            "The blocking work is closed and provable; the debt is real, named and owned."
        )
    elif verdict == "NEEDS_FIXES":
        md.append("Implementation has BLOCKER and/or > 2 HIGH findings. Loop back to `/implement` to address.")
    else:
        md.append("Edge-case coverage below 80%. Re-run `/review` with broader scope or add missing tests.")
    md.append("")

    md.append("## Audit trail")
    md.append("")
    md.append("Spawned agents (their findings files live alongside this report):")
    md.append("")
    for agent in agents_run:
        md.append(f"- `.claude/agents/review-{slug}-{date}/{agent}.md`")
    md.append("")


    # closed findings get their own section rather than the severity ones. A closing pass
    # must not produce an empty report: "the reviewers found nothing" and "everything they found is
    # fixed" are different facts, and the report is where a human tells them apart.
    if closed:
        md.append("")
        md.append(f"## Closed by this pass ({len(closed)})")
        md.append("")
        md.append(
            "Re-verified and closed. These do NOT count toward the verdict — they are listed so a "
            "closing pass is distinguishable from a pass that found nothing."
        )
        md.append("")
        for f in closed:
            md.append(_heading(f))
            md.append("")
            md.append(f"- **Was:** {f['severity']}")
            if f["file"]:
                md.append(f"- **File:** `{f['file']}`{(' line ' + str(f['line'])) if f['line'] else ''}")
            md.append("")

    return "\n".join(md)



# the review reads a working tree that other reviewers can write to.
#
# Measured on an earlier run: six agents ran concurrently against ONE tree. `usage-panel.tsx` was
# found carrying `// MUTANT: undefined no longer skipped` mid-review, probe files appeared at the
# repo root, and the architecture reviewer filed a false BLOCKER — `reportGuardFailure has zero
# production call sites` — against a symbol called at `usage-panel.tsx:115` and `:147`.
#
# Isolation (a worktree per agent) is the fix. This is the DETECTOR beside it: isolation that
# silently stops working looks exactly like isolation that works, and an earlier run is the proof
# that "the briefs say not to" is not a mechanism. Three of six reviewers happened to notice the
# tree was dirty and re-derived their citations; that correctness depended on noticing is the defect.
#
# The state is a HEAD sha plus a digest of `git status --porcelain`, not the porcelain itself: the
# record is written into a directory that ends up in an audit trail, and a file list is the kind of
# detail that turns a diagnostic into a leak.

TREE_STATE_FILENAME = ".tree-state"


def _git(repo_root: Path, *args: str) -> str | None:
    """One git read. None when git cannot answer — never a fabricated empty string."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _porcelain_excluding(porcelain: str, exclude: Path | None, repo_root: Path) -> str:
    """The porcelain with `exclude` removed — the agents writing their own findings is not a change.

    `git status --porcelain` lists untracked files, and the findings directory lives inside the
    repository. Without this, an install whose findings directory is not gitignored reports EVERY
    review as contaminated by the very files the agents were spawned to write — and a signal that
    always fires is the same as no signal.
    """
    if exclude is None:
        return porcelain
    try:
        rel = exclude.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return porcelain  # outside the repo: nothing of it appears in the porcelain anyway
    kept = []
    for line in porcelain.splitlines():
        # `XY path`, and for renames `XY old -> new`. Both ends are compared: a rename INTO the
        # findings directory is still a change to the tree the reviewers read.
        path = line[3:].strip().strip('"')
        ends = [p.strip().strip('"') for p in path.split(" -> ")]
        if all(e == rel or e.startswith(rel + "/") for e in ends):
            continue
        kept.append(line)
    return "\n".join(kept)


def capture_tree_state(repo_root: Path, exclude: Path | None = None) -> dict[str, str] | None:
    """HEAD plus a digest of the porcelain status. None when this is not a readable repo."""
    head = _git(repo_root, "rev-parse", "HEAD")
    # `--untracked-files=all` is required, not a refinement: with the default, git collapses an
    # entirely-untracked directory into one `?? review/` line. The findings the agents write and a
    # probe file dropped beside them then share a single line — excluding one would hide the other.
    porcelain = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    if head is None or porcelain is None:
        return None
    return {
        "head": head.strip(),
        "status_digest": hashlib.sha256(
            _porcelain_excluding(porcelain, exclude, repo_root).encode("utf-8"),
        ).hexdigest(),
    }


def record_tree_state(repo_root: Path, findings_dir: Path) -> dict[str, str] | None:
    """Write the state of `repo_root` into `findings_dir`, to be compared when consolidating."""
    findings_dir.mkdir(parents=True, exist_ok=True)
    state = capture_tree_state(repo_root, exclude=findings_dir)
    if state is None:
        return None
    (findings_dir / TREE_STATE_FILENAME).write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8",
    )
    return state


def check_tree_contamination(repo_root: Path, findings_dir: Path) -> dict[str, Any] | None:
    """Compare the recorded state against the tree now.

    Returns None when there is nothing to compare — no recorded state (every review directory
    written before this existed), or a tree git cannot read. An absent record is not evidence that
    the tree moved, and reporting it as contamination would make every historical review dirty.
    """
    state_path = findings_dir / TREE_STATE_FILENAME
    if not state_path.is_file():
        return None
    try:
        recorded = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    now = capture_tree_state(repo_root, exclude=findings_dir)
    if now is None:
        return None

    changed = [
        field for field in ("head", "status_digest")
        if recorded.get(field) != now.get(field)
    ]
    if not changed:
        return None
    return {
        "contaminated": True,
        "changed": changed,
        "recorded": recorded,
        "observed": now,
    }


def _collect_findings(args, slug: str) -> tuple[list[dict], list[str], list[str], list[str]]:
    """Read every findings file, plus the gate and audit findings that enter the same way.

    Returns `(all_findings, agents_run, unreadable, skipped)`. `unreadable` and
    `skipped` are as much of the answer as the findings: a reviewer whose file could
    not be parsed is not a reviewer who found nothing.

    Extracted from `main`, which measured cyclomatic complexity 43 across 235 lines.
    Pure code movement: the block below is the block that was there, reading the same
    directory. What changed is that each pass declares what it reads and what it
    produces, instead of leaving both in a shared scope.
    """
    # Collect all findings
    all_findings: list[dict[str, Any]] = []
    agents_run: list[str] = []
    # `*.yml` AND `*.yaml`, and everything else in the directory is NAMED rather than
    # silently unseen. The measured failure was five reviewers writing `*.md`: the glob matched
    # nothing, `agents_run` came back empty, and the verdict was `READY_TO_MERGE`.
    unreadable: list[str] = []
    candidates = sorted(
        set(args.findings_dir.glob("*.yml")) | set(args.findings_dir.glob("*.yaml"))
    )
    skipped = sorted(
        p.name for p in args.findings_dir.iterdir()
        if p.is_file() and p not in candidates
    )
    for yml_path in candidates:
        data = _read_findings_file(yml_path)
        if data is None:
            # NOT an agent. The roster is what a reader trusts, so a file that could not be parsed
            # is reported as a failure to read rather than as a reviewer who found nothing.
            unreadable.append(yml_path.name)
            continue
        agent_role = data.get("agent", yml_path.stem)
        findings = data.get("findings", [])
        if not isinstance(findings, list):
            # Unreadable, not empty — and decided BEFORE the roster is appended to.
            # The agent used to be added first and the malformed `findings:` skipped
            # with a bare `continue`, so the reviewer appeared in "Reviewers (spawned
            # agents)" having contributed nothing, and a reader counting reviewers was
            # told the file had been read. This is the same reasoning as the
            # `data is None` branch eight lines above; only that branch had it.
            unreadable.append(f"{yml_path.name} (`findings:` is "
                              f"{type(findings).__name__}, not a list)")
            continue
        if isinstance(agent_role, str):
            agents_run.append(agent_role)
        for f in findings:
            if isinstance(f, dict):
                all_findings.append(_normalize_finding(f, str(agent_role)))

    # The upstream pre-condition enters as a finding, not as a separate step.
    #
    # `code-quality-golden-rule.md § 1` conditions entry into `/review` on
    # `/code-quality`'s verdict — and, on FAIL_SOFT, on an ADR dismissing EACH soft cap.
    # That was prose in `SKILL.md` (a `test -f` someone had to remember to run) and the
    # ADR was looked for by nobody: asserting it existed was enough. Injected here, the
    # review verdict can no longer be computed while ignoring the previous gate.
    all_findings.extend(
        _normalize_finding(f, "check_upstream_gate")
        for f in check_upstream_gate(_project_root_for(args.findings_dir), slug)
    )

    # The independent audits enter the same way, for the same reason. `/review` spawns
    # Claude sub-agents with ad-hoc prompts; the `loop-*` plugins audit the same domains
    # against versioned catalogs that reject an unregistered finding id at the database
    # boundary. `rules/review-auditors.txt` derives WHICH ones this change must face —
    # derived, because letting the reviewing agent choose its own auditor is the failure
    # the review panel already refuses when it will not seat an author.
    _auditor_findings = _load_auditor_coverage()
    _project = _project_root_for(args.findings_dir)
    if _auditor_findings is None:
        all_findings.append(_normalize_finding({
            "severity": "BLOCKER",
            "category": "auditor-coverage",
            "title": "The independent-auditor gate could not be reached",
            "evidence": "no `mechanisms/gates/check_auditor_coverage.py` above "
                        f"{_project}",
            "remediation": "Reinstall the kit. Reviewing without it would report a "
                           "verdict on a change whose required independent audits "
                           "nobody checked for.",
            "source": "consolidate_findings",
        }, "check_auditor_coverage"))
    else:
        all_findings.extend(
            _normalize_finding(f, "check_auditor_coverage")
            for f in _auditor_findings(_project, slug)
        )

    return all_findings, agents_run, unreadable, skipped


def _dedupe(all_findings: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """`(deduped, open_findings, closed)` — closed findings leave the TALLY and stay
    in the REPORT, which is the distinction an earlier item records.

    Extracted from `main`, which measured cyclomatic complexity 43 across 235 lines.
    Pure code movement: the block below is the block that was there, reading the same
    directory. What changed is that each pass declares what it reads and what it
    produces, instead of leaving both in a shared scope.
    """
    # Deduplicate
    deduped = _dedupe_findings(all_findings)

    # closed findings leave the TALLY and stay in the REPORT. Dropping them would make a
    # closing pass produce an empty report, which reads as "the reviewers found nothing" — the exact
    # ambiguity an earlier item was about. Keeping them in the severity sections was rejected too: those
    # sections are what a reader triages by, and a closed HIGH at the top of `## HIGH findings` is
    # an earlier item's defect in a different costume.
    closed = [f for f in deduped if f.get("status") == "CLOSED"]
    open_findings = [f for f in deduped if f.get("status") != "CLOSED"]

    # Group by severity
    return deduped, open_findings, closed


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidate findings from spawned review agents.")
    parser.add_argument("--findings-dir", type=Path, required=True, help="Directory with YAML findings files")
    parser.add_argument("--output", type=Path, required=True, help="Output markdown report path")
    parser.add_argument("--slug", default=None, help="Plan slug (default: derived from findings-dir path)")
    parser.add_argument(
        "--plan",
        type=Path,
        default=None,
        help="Plan file whose `## Followups` section registers accepted HIGH debt. "
             "Without it, > 2 HIGH is fail-closed to NEEDS_FIXES.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository the agents reviewed. Compared against the state spawn_reviewers.py "
             "recorded, to detect a tree that moved while it was being read (an earlier item).",
    )
    parser.add_argument(
        "--edge-case-coverage-ratio",
        type=float,
        default=None,
        help="Edge case coverage ratio 0.0-1.0 (from edge_case_coverage.py)",
    )
    args = parser.parse_args()

    if not args.findings_dir.exists():
        print(json.dumps({"error": f"Findings dir not found: {args.findings_dir}"}), file=sys.stderr)
        return 2

    slug = args.slug
    if not slug:
        # Try to extract from findings-dir path: .claude/agents/review-{slug}-{date}/findings/
        parts = args.findings_dir.resolve().parts
        for part in reversed(parts):
            if part.startswith("review-"):
                # review-{slug}-{date} — strip review- prefix and trailing date
                rest = part[len("review-"):]
                # Try to drop trailing YYYY-MM-DD
                if len(rest) > 11 and rest[-11] == "-":
                    slug = rest[:-11]
                else:
                    slug = rest
                break
    if not slug:
        slug = "unknown"

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    all_findings, agents_run, unreadable, skipped = _collect_findings(args, slug)
    deduped, open_findings, closed = _dedupe(all_findings)

    findings_by_severity: dict[str, list[dict[str, Any]]] = {sev: [] for sev in SEVERITY_ORDER}
    for f in open_findings:
        findings_by_severity[f["severity"]].append(f)

    # zero readable agents produces NO verdict. `READY_TO_MERGE` from an empty directory is
    # not a wrong grade; it is a grade of nothing, and the cycle treats it as evidence.
    # `cycle-rule-schema.md` reserves `INVALID` for "structural integrity broken", which is this.
    #
    # `NEEDS_DEEPER` was rejected: it reads as a finding about the CODE and sends the author hunting
    # for problems nobody measured.
    if not agents_run:
        print(json.dumps({
            "slug": args.slug or args.findings_dir.name,
            "verdict": "INVALID",
            "reason": "no readable findings file — nothing was reviewed, so nothing can be graded",
            "agents_run": [],
            "agents_count": 0,
            "unreadable": unreadable,
            "skipped": skipped,
        }, indent=2))
        return 1

    # Determine verdict
    registered = _registered_followup_ids(args.plan)
    unregistered_high = _unregistered_high(open_findings, registered)
    verdict = _classify_verdict(open_findings, args.edge_case_coverage_ratio, unregistered_high)

    contamination = check_tree_contamination(args.repo_root, args.findings_dir)

    # Write the markdown report
    md_content = _render_markdown(
        slug=slug,
        date=date,
        findings_by_severity=findings_by_severity,
        agents_run=agents_run,
        verdict=verdict,
        coverage_ratio=args.edge_case_coverage_ratio,
        total_findings=len(deduped),
        closed=closed,
        contamination=contamination,
        unreadable=unreadable,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md_content, encoding="utf-8")

    summary = {
        "slug": slug,
        "report_path": str(args.output),
        "verdict": verdict,
        "agents_run": agents_run,
        "agents_count": len(agents_run),
        # present whenever non-empty, so a short roster is visible in the JSON a downstream
        # gate reads, not only in the prose a human might.
        # a downstream gate reads the JSON, not the prose. Without this, a closing pass and
        # a clean pass are indistinguishable to anything automated, which is the item one layer down.
        **({"closed_count": len(closed)} if closed else {}),
        # a downstream gate reads the JSON. A review of a tree that moved mid-run is not
        # invalid on its face, but a reader who does not know it moved cannot weigh it.
        **({"tree_contaminated": True, "tree_contamination": contamination} if contamination else {}),
        **({"unreadable": unreadable} if unreadable else {}),
        **({"skipped": skipped} if skipped else {}),
        "total_findings": len(deduped),
        "findings_by_severity": {sev: len(items) for sev, items in findings_by_severity.items()},
        "edge_case_coverage_ratio": args.edge_case_coverage_ratio,
        "unregistered_high": unregistered_high,
        "registered_followups": sorted(registered),
    }
    print(json.dumps(summary, indent=2))

    # The root comes from the findings directory, not from cwd: the install
    # smoke exercises this script against a tmpdir plan while cwd is the
    # adopter's repository, and cwd would file a review event there for a review
    # that never happened.
    _emit_phase_end(
        args.findings_dir, cycle="review", slug=args.slug or "", verdict=verdict,
        findings=len(deduped),
    )

    # The verdict JSON goes to STDOUT, and a caller that redirects stdout is left
    # with an exit code and silence — which is how this arrived from a consumer on
    # 2026-08-29, described as "exit 1 with empty stderr", indistinguishable from
    # a crash. A non-zero exit now states its reason on stderr as well, naming the
    # findings that decided it.
    if verdict in ("NEEDS_FIXES", "NEEDS_DEEPER"):
        blockers = [f for f in open_findings if f["severity"] == "BLOCKER"]
        detail = "; ".join(
            _heading(f).lstrip("# ").strip() for f in blockers[:3]
        ) or f"edge-case coverage {args.edge_case_coverage_ratio}"
        print(f"{verdict}: {len(blockers)} BLOCKER(s), "
              f"{sum(1 for f in open_findings if f['severity'] == 'HIGH')} HIGH — {detail}",
              file=sys.stderr)
    if verdict == "NEEDS_FIXES":
        return 1
    if verdict == "NEEDS_DEEPER":
        return 3
    return 0


def _emit_phase_end(project_root, *, cycle: str, slug: str, verdict, **extra) -> None:
    """Record the phase transition; never let bookkeeping fail the phase.

    `scripts/` resolves against THIS FILE, not the audited project: in a plugin
    install the kit lives under `.claude/` while the project is elsewhere.
    `ImportError` is caught alone — a bare `except Exception` would swallow a
    real emitter bug into a silence indistinguishable from a phase that never
    ran, which is the defect the stream exists to remove.
    """
    from pathlib import Path as _Path
    tooling = _Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    try:
        from cycle_events import emit_phase_end, project_root_for
    except ImportError as error:
        print(f"cycle-events: emitter unavailable ({error})", file=sys.stderr)
        return
    emit_phase_end(project_root_for(project_root), cycle=cycle, slug=slug,
                   verdict=verdict, **extra)


if __name__ == "__main__":
    sys.exit(main())

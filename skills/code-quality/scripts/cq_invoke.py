"""Shared helper to invoke `/code-quality` as a subprocess.

Used by:
  - `skills/plan-confidence/scripts/run_structural.py` — merges CQ verdict into
    plan-confidence's hard caps.
  - `skills/implement/scripts/run_validation.py` — gates `IMPLEMENTATION_COMPLETE`
    on CQ verdict (per ADR `0002-cq-gate-in-validate`).

The function returns the parsed JSON dict on success, or None on graceful
degradation (script missing, timeout, non-zero exit other than 0/1, malformed JSON).
Never raises — callers must handle the None case.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def invoke(plan_slug: str, repo_root: Path, *, timeout_s: int = 600) -> dict | None:
    """Run `python3 .../run_code_quality.py {plan_slug} --no-audit-write --json-out -`.

    Runs OFFLINE by default. `CODE_QUALITY_NETWORK=1` opts back in.

    ## Why the default is offline, and why it changed

    It used to be the opposite: the run went to the network unless
    `CODE_QUALITY_NO_NETWORK` was set, and nothing anywhere set it. So every plan gate
    in every install took the networked path.

    That path is not reproducible. `run_code_quality.py` already records the
    measurement for the baseline case — the Go symbol detector resolves imports against
    the module proxy, and two consecutive networked runs reported 4818 then 4777
    fabrications, against ONE offline. It forces `--no-network` when writing a baseline
    for exactly that reason: *"a baseline recorded with the network on is worthless."*

    The same sentence is true of a verdict, and the asymmetry was the defect. Measured
    on a consumer on 2026-09-12: four networked runs of one module gave 97, 76, 55 and
    36 unverified modules — four answers to one question — and each run seeded the
    plan's `hard_caps_triggered` with `symbol_fab_unverifiable_go`, which is neither
    baselinable (its `file_path` is `.`) nor dismissible by ADR. Thirteen plans scoring
    89-100 structurally were held at INVALID by a number that changed every time it was
    asked.

    A gate whose answer depends on what a proxy said that second is not a gate. Offline
    is the reproducible reading, so it is the default; the variable that turns the
    network back on is now an explicit opt-in by someone who wants it.

    `CODE_QUALITY_NO_NETWORK` keeps working and keeps meaning offline, so an install
    that already sets it is unaffected.

    Returns parsed JSON dict on success, or None on failure (gracefully degraded).
    """
    script = repo_root / "skills" / "code-quality" / "scripts" / "run_code_quality.py"
    if not script.exists():
        # Fallback for repos that vendor under `.claude/skills/`.
        script = repo_root / ".claude" / "skills" / "code-quality" / "scripts" / "run_code_quality.py"
    if not script.exists():
        return None

    cmd = ["python3", str(script), plan_slug, "--no-audit-write", "--json-out", "-"]
    # Offline unless someone asks for the network. `CODE_QUALITY_NO_NETWORK` is still
    # honoured and still means offline: an install that sets it keeps its behaviour, and
    # an install that sets both is asking for offline twice rather than contradicting
    # itself.
    if not os.environ.get("CODE_QUALITY_NETWORK") or os.environ.get("CODE_QUALITY_NO_NETWORK"):
        cmd.append("--no-network")
    else:
        # Explicit, because `run_code_quality.py` now defaults to offline for a verdict
        # as well. Passing nothing used to mean "networked"; it now means "offline", and
        # an opt-in that silently stopped opting in is worse than one that never existed.
        cmd.append("--network")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(repo_root),
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None

    if result.returncode not in (0, 1):
        return None

    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def merge_verdict_into_plan_confidence(
    out: dict, cq_summary: dict, dismissed_soft_caps: set[str] | None = None
) -> None:
    """Severity-tier-aware merge of CQ verdict into plan-confidence output.

    Tier mapping (consults cq_summary["score_cap"] AND ["verdict"]):

      cq_verdict          → cq_score_cap → action
      PASS                → 100          → no change
      PASS_WITH_CAVEATS   → 89           → cap at 89; SHIPPABLE → SHIPPABLE_WITH_CAVEATS
      FAIL_SOFT           → 70           → cap at 70; SHIPPABLE* → NON_SHIPPABLE
      FAIL_HARD           → 49           → force INVALID; cap at 49
      INVALID             → 0            → force INVALID; cap at 0 (golden rule § 1)

    The CQ `hard_caps_triggered` identifiers are always appended to the plan's
    list for audit visibility, regardless of severity tier.

    `dismissed_soft_caps` carries the soft-cap ids the plan dismisses with an
    ADR. `rules/cycle-code-quality.md` § 1 has always promised this — "A
    `FAIL_SOFT` MAY proceed to `/review` only with an ADR dismissing each soft
    cap" — and nothing implemented it: the demotion below ran unconditionally,
    and no ADR was ever looked for or read.

    The gap was load-bearing rather than cosmetic. Golden rule § 2 maps an
    unconfigured mutation runner to FAIL_SOFT, so a repository without Stryker
    got FAIL_SOFT on every run forever, every plan capped at 70 and demoted, and
    `cycle-plan.md` requires >= SHIPPABLE_WITH_CAVEATS to enter `/implement`.
    Measured on a consumer: blocked on a plan carrying zero hard caps, zero soft
    caps of its own, and 91.6 weighted.

    A soft cap that cannot be dismissed is a hard cap under another name —
    dismissibility is the entire difference between the two tiers.

    EACH cap must be dismissed, per the rule's wording. The score cap applies
    either way: quality was measured, and an ADR justifies proceeding, not a
    better number.
    """
    cq_caps = list(cq_summary.get("hard_caps_triggered", []))
    if cq_caps:
        existing = list(out.get("hard_caps_triggered", []))
        for cap in cq_caps:
            if cap not in existing:
                existing.append(cap)
        out["hard_caps_triggered"] = existing

    cq_score_cap = cq_summary.get("score_cap", 100)
    cq_verdict = cq_summary.get("verdict", "UNKNOWN")
    if cq_score_cap >= 100:
        return

    # What is about to be replaced. The merge is deliberate — `cycle-code-quality.md`
    # § 1 requires the plan's verdict to carry the quality state of the code it
    # targets — but it USED to overwrite in place, and the composed-from value was
    # gone (kit#56). `run_structural`'s library path returns the plan's own verdict
    # and `main()` prints the composed one, so a reader taking a band off the CLI —
    # the obvious thing to do — took a value the snapshot suite cannot reproduce,
    # with nothing in the payload to attribute the difference to.
    #
    # Recorded only when the value actually MOVED. A key that always appears is a
    # key readers learn to skip, and then the one that matters is skipped too.
    score_before = out.get("final_score_after_caps", 100)
    verdict_before = out.get("verdict", "SHIPPABLE")

    out["final_score_after_caps"] = min(score_before, cq_score_cap)
    if out["final_score_after_caps"] != score_before:
        out["score_before_code_quality"] = score_before
    current = verdict_before
    if cq_verdict in ("FAIL_HARD", "INVALID"):
        out["verdict"] = "INVALID"
    elif cq_verdict == "FAIL_SOFT":
        soft_caps = list(cq_summary.get("soft_caps_triggered", []))
        dismissed = dismissed_soft_caps or set()
        undismissed = [c for c in soft_caps if c not in dismissed]
        # BOTH lists, always. They used to be mutually exclusive, and a consumer
        # on the full-dismissal path could not tell whether the absent
        # `undismissed_soft_caps` meant "none" or "not emitted here". An empty
        # list answers that; an absent key asks it.
        out["undismissed_soft_caps"] = undismissed
        out["dismissed_soft_caps"] = sorted(c for c in soft_caps if c in dismissed)
        if undismissed or not soft_caps:
            # An empty soft-cap list means there is nothing identifiable to
            # dismiss, so the demotion stands: waiving a cap nobody can name is
            # waiving the gate itself.
            if current in ("SHIPPABLE", "SHIPPABLE_WITH_CAVEATS"):
                out["verdict"] = "NON_SHIPPABLE"
        elif current == "SHIPPABLE":
            # Every cap carries an ADR. The plan proceeds WITH CAVEATS, never
            # clean: the caveats are real and were justified, not removed.
            out["verdict"] = "SHIPPABLE_WITH_CAVEATS"
    elif cq_verdict == "PASS_WITH_CAVEATS":
        if current == "SHIPPABLE":
            out["verdict"] = "SHIPPABLE_WITH_CAVEATS"

    if out.get("verdict") != verdict_before:
        out["verdict_before_code_quality"] = verdict_before

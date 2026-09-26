"""The plan and alignment-brief trees the alignment gate is tested against.

Kept inside this slice because a slice ships and the kit's root `tests/` does not. They
lived in `tests/test_check_alignment_gate.py`, and this slice's
`test_an_underivable_depth_says_so.py` reached out of the slice to import them — it
passed here and failed at collection in every consumer (2026-09-26). The root suite now
imports them from here instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

PLAN = """---
version: 1.0
---

# Plan: Reduce the trace explorer p95

## Context

Implements B-014 from the backlog. Evidence gathered by `/discover-plan`.

## Tasks

### T1.1 — Profile the shard scan
"""

ALIGNED_BRIEF = """
# Alignment: B-014

## Reviewer sign-off
- [x] CHK001 The stated problem is the one we actually have. [Judgement]
- [x] CHK002 The flows drawn are the flows that matter. [Judgement]
"""


def _plan(tmp_path: Path, body: str = PLAN, slug: str = "b-014-trace-p95") -> Path:
    d = tmp_path / "records" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    # A registry, because the soft floor only fires where one exists — there is no
    # bypass to close in a repository the item could not have come from. Tests
    # that need its ABSENCE build their own tree.
    (tmp_path / "BACKLOG.md").write_text("## B-001 — a registry exists here\n", encoding="utf-8")
    p = d / f"{slug}-plan.md"
    p.write_text(body, encoding="utf-8")
    return p


def _brief(tmp_path: Path, body: str, slug: str = "b-014-trace-p95") -> Path:
    d = tmp_path / "records" / "alignment"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}-alignment.md"
    p.write_text(body, encoding="utf-8")
    return p


def _complete_brief() -> str:
    """A brief that clears the machine threshold, built from the scorer's fixture.

    `plan-alignment` ships beside this slice, so its fixture is reachable from an
    install as well as from here.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plan-alignment" / "tests"))
    from test_score_alignment import COMPLETE_V2
    return COMPLETE_V2

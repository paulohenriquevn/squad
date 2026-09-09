"""The SOP sweep reads both places a procedure can live.

`wiki/sops/` holds procedures ABOUT the kit — installing it into a consumer,
propagating a delta, porting a fix. A skill's `SOP.md` holds the procedure for
OPERATING that skill.

Both carry `last_reviewed` and a review interval, and a procedure nothing sweeps
has a review date nobody reads — a promise with no mechanism, which is the defect
this kit names more often than any other. Thirty-four of them would be that
defect at scale, which is why the resolver was widened rather than the SOPs being
kept somewhere the gate could not see.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanisms" / "gates"))

from check_sop_structure import check_sop_structure


def _sop(path: Path, name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"""---
sop: {name}
version: 1.0.0
owner: whoever runs it
last_reviewed: 2026-08-31
---

# {name}

## Purpose

Do the thing.

## Prerequisites

- Nothing.

## Steps

1. Run the command.
2. Read the verdict.

## Decisions

```mermaid
flowchart TD
    A{{Did it pass?}}
    A -->|yes| B[Proceed]
    A -->|no| C[Stop]
```

## Escalation

- It failed twice → the owner.

## Competencies

- Reading a verdict.
""", encoding="utf-8")


def test_a_skills_sop_is_swept(tmp_path: Path) -> None:
    _sop(tmp_path / "skills" / "alpha" / "SOP.md", "operate-alpha")

    report = check_sop_structure(tmp_path, today="2026-09-01")

    assert report.sops_read == 1


def test_both_roots_are_swept_together(tmp_path: Path) -> None:
    _sop(tmp_path / "wiki" / "sops" / "port-a-fix.md", "port-a-fix")
    _sop(tmp_path / "skills" / "alpha" / "SOP.md", "operate-alpha")

    assert check_sop_structure(tmp_path, today="2026-09-01").sops_read == 2


def test_a_plugin_layout_is_found(tmp_path: Path) -> None:
    """A consumer keeps its skills under `.claude/`."""
    _sop(tmp_path / ".claude" / "skills" / "alpha" / "SOP.md", "operate-alpha")

    assert check_sop_structure(tmp_path, today="2026-09-01").sops_read == 1


def test_a_project_with_no_bundle_still_sweeps_its_skills(tmp_path: Path) -> None:
    """The bundle is absent in a fresh consumer. That used to return early, which
    would have left every skill SOP unswept."""
    _sop(tmp_path / "skills" / "alpha" / "SOP.md", "operate-alpha")

    assert check_sop_structure(tmp_path, today="2026-09-01").sops_read == 1

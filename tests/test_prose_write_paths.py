"""Prose that INSTRUCTS a write names `.squad/`, like the code that performs it.

`check_write_containment.py` proves the structural half: no module outside
`squad/paths.py` can spell a data root, so every path a writer builds came from the
owner. It deliberately strips prose before matching, and it is right to — the kit
argues in prose about the very directories it forbids in code.

**That leaves a hole this test closes.** A `SKILL.md` is not an argument about a
directory; it is an instruction an agent executes. When it says

    Persist to `records/brainstorms/{date}-session.md`

the agent creates `<project>/records/brainstorms/` — a legacy root the readers fall
back to and the writers must never produce. No gate saw it, because the gate that
watches roots reads code and this is markdown, and the mechanism that owns the roots
is never consulted by a human following a recipe.

Measured 2026-09-10, when a real session hit it: **164 legacy-root instructions across
49 files** — 19 of them `SKILL.md`. The session wrote its record to `records/` and its
vision to `wiki/`, and `rules/records-location.md` had said the opposite since
2026-09-09: *"`<project>/.squad/` is the one write root. Always, in every layout."*

Prose that genuinely discusses a legacy root marks itself, the same way
`rules/english-only.md` exempts a Portuguese quotation:

    <!-- write-path: reason -->

An exemption with no reason does not count, for the same reason it does not there.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_prose_write_paths import (  # noqa: E402 — post-bootstrap import
    SCANNED_DIRS,
    scan,
)


def test_no_executable_prose_instructs_a_legacy_root() -> None:
    findings = scan(_REPO)
    assert not findings, "\n".join(
        f"{f['file']}:{f['line']}  {f['path']}" for f in findings[:40]
    )


def test_squad_prefixed_paths_are_not_findings(tmp_path: Path) -> None:
    d = tmp_path / SCANNED_DIRS[0] / "x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("Write to `.squad/records/plans/{slug}.md`.\n")
    assert scan(tmp_path) == []


def test_a_bare_legacy_root_is_a_finding(tmp_path: Path) -> None:
    d = tmp_path / SCANNED_DIRS[0] / "x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("Write to `records/plans/{slug}.md`.\n")
    found = scan(tmp_path)
    assert len(found) == 1 and found[0]["path"] == "records/plans"


def test_a_marked_exemption_with_a_reason_is_allowed(tmp_path: Path) -> None:
    d = tmp_path / SCANNED_DIRS[0] / "x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "Readers fall back to `records/plans`. <!-- write-path: legacy fallback -->\n"
    )
    assert scan(tmp_path) == []


def test_an_exemption_without_a_reason_does_not_count(tmp_path: Path) -> None:
    d = tmp_path / SCANNED_DIRS[0] / "x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("Write to `records/plans`. <!-- write-path: -->\n")
    assert len(scan(tmp_path)) == 1


def test_study_material_is_not_a_data_root(tmp_path: Path) -> None:
    d = tmp_path / SCANNED_DIRS[0] / "x"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("Read `study-material/foo`, never copy it.\n")
    assert scan(tmp_path) == []

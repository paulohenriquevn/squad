"""Resolving the active plan, and telling an unattested plan from an altered one."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from squad.paths import (
    ATTESTATIONS,
    active_plan_pointer,
    write_records_dir,
    write_state_dir,
)


def _pointer(project):
    p = active_plan_pointer(project)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
from squad.plan import attestation, goal_line, resolve  # noqa: E402


def _plan(eco: Path, slug: str, body: str = "# Plan\n") -> Path:
    # The write root hangs off the PROJECT, not off the ecosystem directory. Joining it
    # to `eco` would produce `.claude/.squad/records/` and hide every plan.
    p = write_records_dir(eco, "plans") / f"{slug}-plan.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_a_pinned_plan_wins_and_says_it_was_pinned(tmp_path: Path) -> None:
    _plan(tmp_path, "older")
    _plan(tmp_path, "chosen")
    _pointer(tmp_path).write_text("chosen\n", encoding="utf-8")

    found = resolve(tmp_path)

    assert found is not None and found.slug == "chosen"
    assert found.how == "pinned", "the caller is owed the difference from a guess"


def test_the_newest_plan_is_the_fallback_and_says_so(tmp_path: Path) -> None:
    import os
    import time
    _plan(tmp_path, "older")
    newer = _plan(tmp_path, "newer")
    os.utime(newer, (time.time() + 10, time.time() + 10))

    found = resolve(tmp_path)

    assert found is not None and found.slug == "newer"
    assert found.how == "mtime"


def test_a_pointer_naming_a_missing_plan_falls_back(tmp_path: Path) -> None:
    """A stale pointer must not silence the plan that IS there."""
    _plan(tmp_path, "real")
    _pointer(tmp_path).write_text("deleted-long-ago\n", encoding="utf-8")

    found = resolve(tmp_path)

    assert found is not None and found.slug == "real"


def test_a_pointer_with_a_path_in_it_is_refused(tmp_path: Path) -> None:
    """The slug is joined onto a path, so it is validated rather than trusted."""
    _plan(tmp_path, "real")
    _pointer(tmp_path).write_text("../../etc/passwd\n", encoding="utf-8")

    found = resolve(tmp_path)

    assert found is not None and found.slug == "real", "the traversal must not resolve"


def test_no_plans_at_all_is_none(tmp_path: Path) -> None:
    assert resolve(tmp_path) is None


def test_the_goal_is_the_first_blockquote_under_the_heading(tmp_path: Path) -> None:
    p = _plan(tmp_path, "x", "# Plan\n\n## Goal\n\n> Make it fast\n\n## Tasks\n\n> not this\n")

    assert goal_line(p) == "> Make it fast"


def test_a_goal_section_with_no_blockquote_yields_nothing(tmp_path: Path) -> None:
    p = _plan(tmp_path, "x", "# Plan\n\n## Goal\n\nprose, no quote\n\n## Tasks\n\n> not this\n")

    assert goal_line(p) is None, "the next section's quote is not this section's goal"


# ── attestation ───────────────────────────────────────────────────────────────


def _attest(eco: Path, slug: str, digest: str) -> None:
    d = write_state_dir(eco, ATTESTATIONS)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.sha256").write_text(digest + "\n", encoding="utf-8")


def test_an_unchanged_plan_is_not_tampered(tmp_path: Path) -> None:
    p = _plan(tmp_path, "x", "# Plan\n")
    _attest(tmp_path, "x", hashlib.sha256(p.read_bytes()).hexdigest())

    assert attestation(tmp_path, resolve(tmp_path)).tampered is False


def test_an_edited_plan_is_tampered(tmp_path: Path) -> None:
    p = _plan(tmp_path, "x", "# Plan\n")
    _attest(tmp_path, "x", hashlib.sha256(p.read_bytes()).hexdigest())
    p.write_text("# Plan\n\nsomething else\n", encoding="utf-8")

    assert attestation(tmp_path, resolve(tmp_path)).tampered is True


def test_an_unattested_plan_is_not_tampered(tmp_path: Path) -> None:
    """Never approved is a different state from approved-and-since-edited.

    Conflating them either cries wolf on every plan nobody attested, or lets an
    edited one through because its record was missing.
    """
    _plan(tmp_path, "x", "# Plan\n")

    report = attestation(tmp_path, resolve(tmp_path))

    assert report.expected is None
    assert report.tampered is False

"""A registry created exactly as `/backlog-init` instructs was born INVALID.

Two rules of this kit contradicted each other, and both are load-bearing:

  `skills/backlog-init/SKILL.md`
      "**Seed no items.** An item nobody filed has no `why_now`, no DoD and no owner —
      it is a placeholder that will be inherited as though it were a decision."

  `check_backlog_structure.py § registry_parses`
      "That is a registry this check could not read, not a registry with nothing in it
      — and the two must not share a verdict."

The second sentence is right, and the check that implements it fired on `content.strip()
and not items` — true of every freshly-seeded registry, because the scaffold has a
header, an `## Index` and an `## Items` section and zero items. Measured 2026-09-18 on a
registry built to the letter of Step 3: **BLOCKER registry_parses, verdict INVALID.**

So "correctly empty" had no way to be expressed. The fix is not to drop the check — an
unparseable registry reporting SHIPPABLE is the defect it was written for — but to let
the file say which it is. A registry that declares its `## Items` section and holds none
is empty; one whose items section is absent, or whose content the parser cannot place,
is unreadable.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "backlog-review" / "scripts" / "check_backlog_structure.py"

#: What Step 3 of `backlog-init/SKILL.md` prescribes, minus the routing prose.
_SEEDED = """# Backlog

The registry of work. Ids are monotonic and never renumbered.

## How an item gets here

`/backlog-item` (human) or `/discover-execute --sweep` (measured).

## Where routing lives

`rules/domain-routing.txt`.

## Index

- **open**: 0
- **triaged**: 0
- **approved**: 0

## Items

_None yet. Next free id: B-001._
"""


def _report(path: Path) -> dict:
    done = subprocess.run([sys.executable, str(_SCRIPT), str(path), "--json"],
                          capture_output=True, text=True, timeout=120, check=False)
    return json.loads(done.stdout)


def _codes(report: dict) -> list[str]:
    return [f["check"] for f in report["findings"]]


def test_a_freshly_seeded_registry_is_not_a_blocker(tmp_path: Path) -> None:
    """The exact scaffold `/backlog-init` Step 3 describes."""
    path = tmp_path / "BACKLOG.md"
    path.write_text(_SEEDED, encoding="utf-8")

    assert "registry_parses" not in _codes(_report(path)), (
        "a registry created exactly as the kit instructs was reported unreadable")


def test_a_registry_with_no_items_section_is_still_unreadable(tmp_path: Path) -> None:
    """The half that must NOT go quiet.

    A file with prose and no `## Items` is the case the check was written for: this
    parser found nothing and cannot say whether anything is there.
    """
    path = tmp_path / "BACKLOG.md"
    path.write_text("# Backlog\n\nSome prose, no sections, no items.\n", encoding="utf-8")

    assert "registry_parses" in _codes(_report(path)), (
        "an unreadable registry passed as an empty one — the exact inversion")


def test_an_items_section_with_unparseable_content_is_unreadable(tmp_path: Path) -> None:
    """`## Items` present and holding something this parser cannot place. Empty means
    empty, not "there is text here I could not read"."""
    path = tmp_path / "BACKLOG.md"
    path.write_text("# Backlog\n\n## Items\n\n### B-001 wrong heading level\n\nstatus: raw\n",
                    encoding="utf-8")

    assert "registry_parses" in _codes(_report(path)), (
        "items the parser could not place were counted as no items")


def test_an_empty_registry_reaches_a_verdict_that_is_not_invalid(tmp_path: Path) -> None:
    """The point of the whole fix: a correctly empty registry must be expressible.

    The index is generated over zero items, which Step 3 also prescribes, so this is
    the complete artifact that step produces.
    """
    path = tmp_path / "BACKLOG.md"
    path.write_text(_SEEDED, encoding="utf-8")
    subprocess.run([sys.executable,
                    str(_ROOT / "skills" / "backlog-review" / "scripts" / "backlog_index.py"),
                    str(path), "--write"], capture_output=True, text=True, timeout=120,
                   check=False)

    report = _report(path)

    assert report["verdict"] != "INVALID", (
        f"a registry built to the letter of backlog-init is {report['verdict']}: "
        f"{_codes(report)}")

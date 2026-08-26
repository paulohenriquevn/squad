"""Refuse a pytest run that spans two skill slices, and name the command that works.

WHY THIS EXISTS. The 31 slices are import-isolated on purpose: in production each skill runs alone
with only its own `scripts/` on `sys.path`, and several ship modules with the same basename and
different contents — `check_corner_coverage.py` exists in two skills and means two things.
`scripts/run_slice_tests.sh` mirrors that by giving each slice its own process, and it exits 0.

What was missing is what happens when somebody does the obvious thing instead:

    $ python3 -m pytest skills/discover-plan-confidence/tests skills/discover-confidence/tests
    ERROR skills/discover-plan-confidence/tests/test_check_corner_coverage.py
    ERROR skills/discover-plan-confidence/tests/test_check_plan_completeness.py
    ERROR skills/discover-plan-confidence/tests/test_threshold_resolution.py
    !!!!!!!! Interrupted: 3 errors during collection !!!!!!!!

Three errors, none about the contributor's change, and the natural reading is that they broke
something. B-017 hit exactly this and had to stash its changes to prove otherwise. This turns that
into one sentence.

NOT the import mode. `pyproject.toml` already sets `--import-mode=importlib`, which governs how
pytest imports TEST files — not how a test's own `import X` statement resolves. Each slice's
`conftest.py` does `sys.path.insert(0, SCRIPTS_DIR)`, so the first slice collected wins `sys.modules`
for the rest of the session.

WHAT THIS DOES NOT DO. It does not make a wide run work. Making it work would mean unifying the
import namespace, which would make the test environment differ from production — the thing the
isolation exists to prevent. The refusal is the honest outcome, and it points at the command that
does the job.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent


def _slice_of(path: Path) -> str | None:
    """The skill slice a collected path belongs to, or None for the root suite."""
    try:
        rel = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return None
    parts = rel.parts
    return parts[1] if len(parts) >= 2 and parts[0] == "skills" else None


def _slices_named_by(args: list[str]) -> set[str]:
    """Every slice the command-line arguments reach.

    Read from the ARGUMENTS rather than from collected items, because the import shadowing happens
    during collection: by the time `pytest_collection_modifyitems` runs, the three ImportErrors have
    already been raised and printed. A bare `skills` (or the repo root) reaches all of them.
    """
    slices: set[str] = set()
    for raw in args:
        path = Path(raw.split("::", 1)[0])
        resolved = (REPO_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
        named = _slice_of(resolved)
        if named is not None:
            slices.add(named)
            continue
        # A path that is not inside one slice but contains several — `skills`, `.`, the root.
        skills_dir = REPO_ROOT / "skills"
        if resolved in {REPO_ROOT, skills_dir} and skills_dir.is_dir():
            slices.update(
                d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "tests").is_dir()
            )
    return slices


def pytest_configure(config) -> None:
    """Fail fast when the invocation spans more than one slice.

    In `configure`, which is before collection — and therefore before a shadowed module can raise
    the confusing ImportErrors this replaces.
    """
    slices = _slices_named_by(list(config.args))
    if len(slices) <= 1:
        return

    named = ", ".join(sorted(slices))
    raise pytest.UsageError(
        f"this run spans {len(slices)} skill slices ({named}), and they cannot share one pytest "
        f"process: several slices ship modules with the same basename and different contents, so "
        f"`import check_corner_coverage` would resolve to whichever slice was collected first — a "
        f"configuration that never happens in real use, where each skill runs alone.\n"
        f"\n"
        f"Run every slice, each in its own process:\n"
        f"    bash scripts/run_slice_tests.sh\n"
        f"\n"
        f"Or one slice at a time:\n"
        f"    python3 -m pytest skills/<slice>/tests"
    )

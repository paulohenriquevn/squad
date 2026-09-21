"""Shared pytest fixtures for discover-confidence tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
FIXTURES_DIR = SKILL_ROOT / "fixtures"
TEMPLATES_DIR = SKILL_ROOT / "templates"

# Make scripts/ importable
sys.path.insert(0, str(SCRIPTS_DIR))


def _find_project_root(start: Path) -> Path:
    """The KIT root — the tree that owns `skills/` and `mechanisms/`.

    This walked up looking for `.claude/` or `.git/`, which finds the kit's own
    repository when the tests run there and **the CONSUMER'S project** when they run
    from an install. Same code, two different trees, so the suite was answering a
    question about wherever it happened to be unpacked.

    Measured on a consumer 2026-09-16: green in the kit repository, three failures in an
    install, nothing edited in between. The panel fixture also wrote its records under
    that root — `.squad/records/panels/` of the consumer's live registry — and only a
    `finally` kept it from staying there.

    The kit root is where `mechanisms/gates/` sits beside `skills/`, and that is true in
    both layouts: `<repo>/` when developing, `<project>/.claude/` when installed. The
    fallback is unchanged for a tree shaped like neither.
    """
    current = start.resolve()
    while current != current.parent:
        if (current / "mechanisms" / "gates").is_dir() and (current / "skills").is_dir():
            return current
        current = current.parent
    return start.parent.parent.parent


PROJECT_ROOT = _find_project_root(SKILL_ROOT)


@pytest.fixture(scope="session")
def skill_root() -> Path:
    return SKILL_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def project_root() -> Path:
    """The KIT root: where `mechanisms/gates` sits beside `skills/`."""
    return PROJECT_ROOT


def _find_records_root(start: Path) -> Path:
    """The PROJECT whose records a scorer writes and a gate reads — a different root.

    Two roots, two questions, and one fixture answered both until 2026-09-16. The panel
    machinery is the kit's (`mechanisms/gates/`); the panel RECORD belongs to the project
    being scored (`<project>/.squad/records/panels/`). In the kit's own repository those
    are the same directory, so nothing distinguished them; in an install they are
    `<project>/.claude/` and `<project>/`, and a fixture writing where the gate does not
    read reports `no_record` forever.

    This resolves exactly as `run_opportunity_score._find_project_root` does, because
    agreeing with the code under test is the whole point of the fixture.
    """
    current = start.resolve()
    while current != current.parent:
        if (current / ".claude").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return start


RECORDS_ROOT = _find_records_root(SKILL_ROOT)


@pytest.fixture(scope="session")
def records_root() -> Path:
    """Where the scorer will look for a panel record. See `_find_records_root`."""
    return RECORDS_ROOT


@pytest.fixture(scope="session")
def rubric_path() -> Path:
    return TEMPLATES_DIR / "rubric-opportunity.md"


@pytest.fixture
def good_opportunity(fixtures_dir: Path) -> Path:
    return fixtures_dir / "good-opportunity.md"


@pytest.fixture
def synthetic_opportunity(tmp_path: Path) -> Path:
    """Minimal valid opportunity for negative-path tests.

    Each corner carries >50 chars to clear MIN_CONTENT_CHARS in check_corners_populated.
    Deliberately repo-local in its blast radius, so no ADR is required — the ADR
    conditional is exercised explicitly in test_check_opportunity_completeness.
    """
    body = (
        "# Opportunity: Test\n\n"
        "**Item:** B-001\n"
        "**Repo:** squad\n"
        "**Mode:** review\n"
        "**Slug:** `test`\n\n"
        "## Context\n\nTest context for the synthetic fixture used in unit tests.\n\n"
        "## Corner 1 — Evidence\n\n"
        "The measurement is recorded here with enough substantive detail to clear the "
        "minimum content threshold enforced by the corner checker.\n\n"
        "## Corner 2 — Constraint Relation\n\n"
        "Local optimisation. The declared constraint is untouched by this change, and "
        "that is stated plainly rather than left blank.\n\n"
        "## Corner 3 — Blast Radius\n\n"
        "Repo-local. Nothing outside this repository consumes the affected surface, so "
        "no consumer has to migrate.\n\n"
        "## Corner 4 — Verification\n\n"
        "A regression test asserts the corrected behaviour and fails against the current "
        "state. The limit plausibly moves to the next stage afterwards.\n\n"
        "## Recommendation\n\n- Do X for reason Y as explained above\n"
    )
    path = tmp_path / "test-opportunity.md"
    path.write_text(body, encoding="utf-8")
    return path

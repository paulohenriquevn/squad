"""Tests for detect_domain.py — verifies agnostic keyword matching across domains.

``scripts/detect_domain.py`` is intentionally AGNOSTIC: its ``DOMAINS`` dict ships
generic software-engineering domains (auth, database, cli-tooling, …) — no
consumer-specific domains. These tests exercise that real contract against the
``database`` and ``auth`` domains, which have distinctive keywords.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "detect_domain.py"

sys.path.insert(0, str(SCRIPT.parent))
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from detect_domain import count_domain_hits  # noqa: E402 — post-bootstrap import


def _run(plan: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--plan", str(plan)],
        capture_output=True,
        text=True,
     check=False)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw": result.stdout, "stderr": result.stderr}
    return result.returncode, data


def test_database_plan_detected_as_database(sample_plan: Path) -> None:
    """A plan dominated by database keywords resolves to the `database` domain (rc 0)."""
    rc, data = _run(sample_plan)
    assert rc == 0
    assert data["primary_domain"] == "database"


def test_unknown_domain_when_no_keywords(tmp_path: Path) -> None:
    """A plan with genuinely no domain keywords → primary 'unknown', rc 1."""
    plan = tmp_path / "unknown.md"
    plan.write_text(
        "# Plan: Unrelated\n\n"
        "This document describes a generic improvement to the wording of help output. "
        "We will tidy up some prose. Nothing notable belongs to any known topic here.\n",
        encoding="utf-8",
    )
    rc, data = _run(plan)
    assert rc == 1
    assert data["primary_domain"] == "unknown"


def test_auth_keywords_detected_as_auth(tmp_path: Path) -> None:
    """A plan built from `auth` keywords resolves to the `auth` domain (rc 0, confidence > 0)."""
    plan = tmp_path / "auth.md"
    plan.write_text(
        "# Plan: Auth\n\n"
        "Implement authentication and authorization. Issue a JWT on login, "
        "support OAuth and OIDC. Hash the password with argon2. Enforce RBAC "
        "permission checks and protect against CSRF.\n",
        encoding="utf-8",
    )
    rc, data = _run(plan)
    assert rc == 0
    assert data["primary_domain"] == "auth"
    assert data["confidence"]["auth"] > 0


def test_multiple_domains_with_confidence(tmp_path: Path) -> None:
    """A plan mixing database (dominant) + auth yields auth as a secondary domain."""
    plan = tmp_path / "multi.md"
    plan.write_text(
        "# Plan: Multi\n\n"
        "Database schema with an Alembic migration, CREATE TABLE, INDEX, "
        "FOREIGN KEY, ORM and connection pool tuning. Also add authentication "
        "with JWT, OAuth, login and RBAC permission checks.\n",
        encoding="utf-8",
    )
    rc, data = _run(plan)
    assert rc == 0
    assert data["primary_domain"] == "database"
    assert "auth" in data["secondary_domains"]
    assert data["confidence"]["database"] > data["confidence"]["auth"]


# ---------------------------------------------------------------------------
# B-015 — the matcher had no word boundary, and misrouted a review
# ---------------------------------------------------------------------------
#
# Measured in a consumer on 2026-08-27: a diff of four files — a GitHub workflow,
# a Node script, its test, and the CHANGELOG — returned `primary_domain:
# concurrency` on `["lock", "actor"]`. Every occurrence of `lock` was the word
# **lockfile** (13 of 13) and every `actor` was **extractor** (5 of 5). The two
# words the change was ABOUT are what misrouted it.
#
# Routing decides which specialist reads the diff. A concurrency reviewer sent to
# find races in a YAML file finds none and reports clean, while npm resolution
# semantics and `steps.*.outcome` conditions go unexamined. A review that ran and
# looked at the wrong thing is worse than one that did not run: it produces a
# verdict.


def test_lockfile_is_not_the_word_lock():
    hits = count_domain_hits(
        "Pin the lockfile. The lockfile is read by the extractor, and the extractor "
        "writes the lockfile back.",
        ["package.json", "scripts/taught-coverage.mjs"],
    )
    assert "concurrency" not in hits, (
        f"'lockfile'/'extractor' must not register as 'lock'/'actor': {hits.get('concurrency')}"
    )


def test_a_real_concurrency_change_still_routes_to_concurrency():
    # DoD bullet 3: the fix must not be "match less". A diff with real primitives
    # has to keep routing where it did.
    hits = count_domain_hits(
        "Take the mutex before the read. The actor receives on a channel; the lock "
        "is released in a defer.",
        ["internal/scheduler/lock.go"],
    )
    assert "concurrency" in hits
    matched = hits["concurrency"]["matched"]
    assert "mutex" in matched and "lock" in matched and "actor" in matched, matched


def test_a_keyword_ending_in_punctuation_still_matches():
    # `aria-`, `POST /`, `CI/CD`, `command-line` end or start on non-word characters,
    # where a naive `\b` behaves differently than it reads. The boundary is asserted
    # only against alphanumerics, so these keep working.
    assert "frontend" in count_domain_hits("use aria-label on the control", [])
    assert "api-design" in count_domain_hits("POST /users returns 201", [])
    assert "infrastructure" in count_domain_hits("the CI/CD pipeline deploys", [])

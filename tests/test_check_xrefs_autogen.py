"""The validator must not call orphan the skill the cycle itself generates.

`/review` writes `review-{slug}-{dimension}-knowledge` and discover writes
`*-sepa-knowledge`. They are execution ARTIFACTS, not cycle phases.

`*-sepa-knowledge` no longer has a producer: `/implement` stopped generating agents
and skills on 2026-09-01. The tolerance stays for consumers that still hold one on
disk — dropping it would orphan their files and fail the check in a repository that
did nothing wrong.
`patch_install.sh` already treats them that way; this validator did not, and the
effect showed up far from the cause: every consumer that ran `/review` started
failing `--strict` — measured on the three consumers 2026-08-03, 26 WARN and no
real defect.

These tests call `is_cycle_generated_skill` through the real module instead of reproducing
the rule. The previous version reproduced it, and the price showed: the exemption
was applied to one of the two checks and the suite stayed green, because it
validated the copy. A test that reimplements what it should protect protects
nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_xrefs import (  # noqa: E402 — post-bootstrap import
    AUXILIARY_SKILLS,
    is_cycle_generated_skill,
)


def _orphans(existing: set[str]) -> set[str]:
    auto = {s for s in existing if is_cycle_generated_skill(s)}
    return existing - AUXILIARY_SKILLS - auto


def test_generated_review_knowledge_is_not_an_orphan() -> None:
    assert _orphans({"review-m5-ship-apikey-otel-tests-knowledge"}) == set()


def test_generated_sepa_knowledge_is_not_an_orphan() -> None:
    assert _orphans({"promptly-sepa-knowledge"}) == set()


def test_a_real_skill_with_no_cycle_is_still_an_orphan() -> None:
    """The exemption must not become a back door for a real skill with no cycle."""
    assert _orphans({"skill-writer"}) == {"skill-writer"}


def test_a_name_that_only_looks_generated_is_still_an_orphan() -> None:
    """`records-helper` does not end in `-knowledge`; it is not exempt."""
    assert _orphans({"records-helper"}) == {"records-helper"}


def test_generated_is_also_exempt_from_the_cycle_contract() -> None:
    """Regression: the exemption applied to one check and not the other.

    The skill `/review` writes has no `Cycle contract` section — nor should it.
    Exempting it from `no_orphan_skills` while still enforcing
    `skill_has_cycle_contract` traded 26 WARN for 3 and looked like a fix; the
    consumer stayed in FAIL over a defect that did not exist. The predicate is a
    single one precisely so the two checks cannot diverge.
    """
    assert is_cycle_generated_skill("review-m0-walking-skeleton-tests-knowledge")
    assert is_cycle_generated_skill("promptly-sepa-knowledge")
    assert not is_cycle_generated_skill("skill-writer")
    assert not is_cycle_generated_skill("records-helper")

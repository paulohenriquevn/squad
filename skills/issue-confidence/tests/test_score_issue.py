"""The weights are measurements, and the tests pin them to their source.

Bettenburg et al., *"What Makes a Good Bug Report?"* (FSE 2008) surveyed 872 developers
at APACHE, ECLIPSE and MOZILLA. Rahman et al., arXiv:2108.05316, analysed
non-reproducible reports across Firefox and Eclipse. Every number below comes from one
of the two, and a test that changed a weight without changing the citation would be
changing an opinion while claiming a finding.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from score_issue import (  # noqa: E402 — post-bootstrap import
    FLOOR_PCT,
    ITEMS,
    TOTAL_WEIGHT,
    TRIAGE_ONLY,
    scan_secrets,
    score,
)

FULL = """## Severity
HIGH — every run crashes.

## Build under test
`repo` @ `workspace`, SHA `cf537a7`, python 3.10.12 on Linux.

## Expected vs actual
**Expected:** it prints the outcome.
**Actual:** it raises.

## Steps to reproduce
1. Record a panel with one non-approving vote.
2. Run `python3 review_panel.py --record <file>`.

## Evidence
```
TypeError: sequence item 0: expected str instance, dict found
```

## Dedup
`gh issue list --search "dissent"` — no existing issue.
"""


# ------------------------------------------------------------------ the weights


def test_steps_to_reproduce_outweighs_everything_else() -> None:
    """83% — the most wanted item in the study and the one most often missing. An issue
    without it is the most expensive kind to receive."""
    weights = {i.key: i.weight for i in ITEMS}

    assert weights["steps_to_reproduce"] == 83
    assert weights["steps_to_reproduce"] > max(
        w for k, w in weights.items() if k != "steps_to_reproduce")


def test_severity_is_weighted_zero_and_kept() -> None:
    """Developers fixing a bug do not use it — 0% in the study. Dropping it would
    optimise for one audience; weighting it like the rest would mislead. It is kept,
    weighted zero, and the report says why."""
    assert [i.key for i in TRIAGE_ONLY] == ["severity"]
    assert TRIAGE_ONLY[0].weight == 0
    assert "severity" not in {i.key for i in ITEMS}


def test_every_weight_matches_the_surveyed_percentage() -> None:
    """Using the real percentages rather than a 1-5 scale keeps the source auditable:
    anybody can check a weight against the paper."""
    assert {i.key: i.weight for i in ITEMS} == {
        "steps_to_reproduce": 83,
        "stack_trace_or_output": 57,
        "observed_behaviour": 33,
        "expected_behaviour": 22,
        "version_or_build": 12,
        "dedup_recorded": 10,
        "environment": 4,
    }


def test_the_floor_cannot_be_reached_by_padding_cheap_fields() -> None:
    """Environment and severity together are 4 of 221. An issue that is all metadata
    and no repro is the case the study ranks as causing the most delay."""
    cheap = sum(i.weight for i in ITEMS if i.weight <= 12)

    assert round(100 * cheap / TOTAL_WEIGHT) < FLOOR_PCT


def test_the_repro_alone_is_not_enough_either() -> None:
    """83 of 221 is 38%. The most valuable item still needs context around it."""
    assert round(100 * 83 / TOTAL_WEIGHT) < FLOOR_PCT


# ------------------------------------------------------------------ scoring


def test_a_complete_draft_is_ready() -> None:
    rep = score(FULL)

    assert rep.verdict == "READY"
    assert rep.pct == 100, rep.missing


def test_a_draft_with_no_repro_is_thin() -> None:
    rep = score("## Severity\nHIGH — it broke.\n\n## Description\nIt does not work.\n")

    assert rep.verdict == "THIN"
    assert "steps_to_reproduce" in {m["item"] for m in rep.missing}


def test_the_missing_items_are_ordered_by_what_they_cost() -> None:
    """A reader fixing a thin draft should start with the heaviest gap."""
    rep = score("## Description\nbroken\n")

    heaviest = max(rep.missing, key=lambda m: m["weight"])

    assert heaviest["item"] == "steps_to_reproduce"


def test_severity_is_reported_as_stated_without_scoring() -> None:
    rep = score(FULL)

    assert rep.triage == ["severity"]
    assert rep.pct == 100, "severity must not contribute to the score"


# ------------------------------------------------------------------ secrets


@pytest.mark.parametrize("secret,label", [
    ("ghp_" + "a" * 36, "GitHub token"),
    ("sk-" + "b" * 32, "OpenAI-style key"),
    ("AKIA" + "C" * 16, "AWS access key id"),
    ("-----BEGIN RSA PRIVATE KEY-----", "private key"),
    ('password = "hunter2hunter2"', "credential assignment"),
])
def test_a_secret_refuses_the_draft(secret: str, label: str) -> None:
    """Public the moment it is filed, and removing it later leaves it in the edit
    history."""
    assert label in scan_secrets(f"## Steps\n1. use {secret}\n")


def test_a_refused_draft_is_not_also_scored() -> None:
    """A score beside a refusal invites filing it anyway. The body is not a draft to
    improve; it is a draft to rewrite."""
    rep = score(FULL + "\n\ntoken: ghp_" + "a" * 36 + "\n")

    assert rep.verdict == "REFUSED"
    assert rep.score == 0
    assert rep.present == []


def test_a_redacted_placeholder_does_not_trip_the_scan() -> None:
    """The replacement the contract asks for must not be refused, or the guidance is
    unusable."""
    assert scan_secrets("Authorization: Bearer <redacted>") == []
    assert scan_secrets("export GITHUB_TOKEN=<your token>") == []


# ------------------------------------------------------------------ honesty


def test_the_report_states_what_it_cannot_score() -> None:
    from score_issue import NOT_SCORED

    joined = " ".join(NOT_SCORED)

    assert "repro WORKS" in joined
    assert "duplicate" in joined

"""The product-alignment gate: what it scores, and what it refuses to do.

The test that matters most here is `test_a_judge_signature_does_not_align_the_product`.
Every other assertion checks arithmetic; that one checks the rule the script exists
to hold — see `rules/cycle-brainstorm.md § Why the judge may not sign this one`.
"""
from __future__ import annotations

import sys as _s
from pathlib import Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _s.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import sys  # noqa: E402 — post-bootstrap import
from pathlib import Path  # noqa: E402 — post-bootstrap import

import pytest  # noqa: E402 — post-bootstrap import

from squad.paths import write_wiki_dir  # noqa: E402 — post-bootstrap import

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from score_product_alignment import (  # noqa: E402 — post-bootstrap import
    FLOOR_PCT,
    score,
    verdict,
)

VISION = """# Product vision

## Who it is for
Teams running more than one service who cannot say which one is slow, and who
currently answer that question by opening dashboards one at a time.

## The problem
Nobody can answer "is this normal?" without a person who remembers last month.
That person is a single point of failure and they are on holiday.

## What it is
One place that answers whether current behaviour differs from the baseline, for
any service, without knowing which dashboard to open first.

## What it is NOT
- Not an alerting system. It answers questions; it does not wake anyone.
- Not a log search tool. Logs are the next hop, not this.
"""

OBJECTIVES = """# Objectives

## OBJ-1 — Answer "is this normal" in under a minute
metric: p90 time-to-answer below 60s, measured on the 10 most-asked questions
horizon: 2026-Q4
why: the current answer takes 12 minutes and needs the one person who remembers.

## OBJ-2 — Cover every service without per-service setup
metric: 100% of services in the registry queryable with 0 config files each
horizon: 2027-Q1
why: per-service onboarding is why the last three attempts stalled at 40%.
"""

TRD = """# Technical requirements

## REQ-1 — Baseline is computed, never declared
serves: OBJ-1
statement: The baseline for any series is derived from its own history.
acceptance: A service added today has a usable baseline within 24h.

## REQ-2 — Discovery reads the registry
serves: OBJ-2
statement: Services are enumerated from the registry, not from a config file.
acceptance: Adding a service to the registry makes it queryable with no deploy.
"""

PIECES = """# Technical pieces

## PIECE-1 — Baseline engine
realises: REQ-1
responsibility: Computes and stores rolling baselines per series.

## PIECE-2 — Registry reader
realises: REQ-2
responsibility: Enumerates services and keeps the series index current.
"""


def _product(root: Path, **overrides: str) -> Path:
    d = write_wiki_dir(root, "product")
    d.mkdir(parents=True, exist_ok=True)
    files = {
        "product-vision.md": VISION,
        "objectives.md": OBJECTIVES,
        "trd.md": TRD,
        "technical-pieces.md": PIECES,
    }
    files.update(overrides)
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return d


def _sign(product: Path, who: str = "paulo", ticked: bool = True) -> None:
    box = "x" if ticked else " "
    (product / "alignment.md").write_text(
        "# Product alignment\n\n## Reviewer sign-off\n\n"
        f"- [{box}] The problem stated is the real one\n"
        f"- [{box}] These are the right objectives\n"
        f"- [{box}] The metrics are the right metrics\n\n"
        f"<!-- signed-by: {who} -->\n",
        encoding="utf-8",
    )


def test_a_complete_signed_cascade_is_aligned(tmp_path: Path) -> None:
    product = _product(tmp_path)
    _sign(product)
    rep = score(tmp_path)
    assert rep.pct >= FLOOR_PCT, [c for c in rep.criteria if c.score < 2]
    assert verdict(rep) == ("PRODUCT_ALIGNED", 0)


def test_a_missing_document_is_invalid_not_merely_low(tmp_path: Path) -> None:
    """An absent document is a structural fact; no editing of the others fixes it."""
    product = _product(tmp_path)
    _sign(product)
    (product / "trd.md").unlink()
    rep = score(tmp_path)
    assert "missing_document" in rep.hard_caps
    assert verdict(rep)[0] == "INVALID"


def test_a_requirement_citing_a_missing_objective_is_invalid(tmp_path: Path) -> None:
    """The same rule the kit applies to a file:line — a pointer needs a referent."""
    product = _product(tmp_path, **{"trd.md": TRD.replace("serves: OBJ-2", "serves: OBJ-99")})
    _sign(product)
    rep = score(tmp_path)
    assert "citation_without_referent" in rep.hard_caps
    assert any("OBJ-99" in d for d in rep.dangling)
    assert verdict(rep)[0] == "INVALID"


def test_a_piece_citing_a_missing_requirement_is_invalid(tmp_path: Path) -> None:
    product = _product(tmp_path, **{"technical-pieces.md": PIECES.replace("realises: REQ-2", "realises: REQ-77")})
    _sign(product)
    rep = score(tmp_path)
    assert any("REQ-77" in d for d in rep.dangling)
    assert verdict(rep)[0] == "INVALID"


def test_an_objective_without_a_number_does_not_reach_the_floor(tmp_path: Path) -> None:
    """"Be faster" closes never, so nothing downstream can ever trace to it."""
    weak = OBJECTIVES.replace(
        "metric: p90 time-to-answer below 60s, measured on the 10 most-asked questions",
        "metric: noticeably faster than today",
    )
    product = _product(tmp_path, **{"objectives.md": weak})
    _sign(product)
    rep = score(tmp_path)
    metric = next(c for c in rep.criteria if c.key == "obj_metric")
    assert metric.score < 2
    assert verdict(rep)[0] == "NEEDS_REVISION"


def test_a_vision_without_non_goals_loses_the_criterion(tmp_path: Path) -> None:
    """The uncomfortable section. Everything is in scope until someone writes it down."""
    product = _product(tmp_path, **{"product-vision.md": VISION.split("## What it is NOT")[0]})
    _sign(product)
    rep = score(tmp_path)
    assert next(c for c in rep.criteria if c.key == "vision_nongoals").score == 0


def test_a_placeholder_zeroes_its_document_criterion(tmp_path: Path) -> None:
    product = _product(tmp_path, **{"objectives.md": OBJECTIVES + "\nhorizon: TBD\n"})
    _sign(product)
    rep = score(tmp_path)
    assert next(c for c in rep.criteria if c.key == "obj_no_placeholder").score == 0


def test_unsigned_is_awaiting_review_not_a_pass_and_not_a_failure(tmp_path: Path) -> None:
    product = _product(tmp_path)
    _sign(product, ticked=False)
    rep = score(tmp_path)
    assert rep.pct >= FLOOR_PCT
    assert verdict(rep) == ("AWAITING_REVIEW", 1)


def test_an_absent_checklist_is_not_a_passed_gate(tmp_path: Path) -> None:
    _product(tmp_path)  # no alignment.md at all
    rep = score(tmp_path)
    assert verdict(rep)[0] == "AWAITING_REVIEW"


def test_a_judge_signature_does_not_align_the_product(tmp_path: Path) -> None:
    """The rule this script exists to hold.

    `alignment-threshold.md § Amended 2026-09-01` lets a judge sign an ITEM's brief,
    because the judge reads evidence that exists independently of it. A product
    vision has no such independent evidence — it is what everything else is measured
    against — so a judge scoring it grades the document against itself.
    """
    product = _product(tmp_path)
    _sign(product, who="judge/alignment-judge")
    rep = score(tmp_path)
    assert rep.pct >= FLOOR_PCT, "the cascade is structurally complete"
    assert verdict(rep) == ("AWAITING_REVIEW", 1), "a judge cannot supply this signature"


def test_the_report_always_names_what_it_did_not_score(tmp_path: Path) -> None:
    """A number that claims more than it measured is the failure being avoided."""
    from score_product_alignment import NOT_SCORED

    assert len(NOT_SCORED) == 3
    assert any("real one" in n for n in NOT_SCORED)


@pytest.mark.parametrize("missing", ["product-vision.md", "objectives.md", "trd.md", "technical-pieces.md"])
def test_every_document_of_the_cascade_is_required(tmp_path: Path, missing: str) -> None:
    product = _product(tmp_path)
    _sign(product)
    (product / missing).unlink()
    assert verdict(score(tmp_path))[0] == "INVALID"

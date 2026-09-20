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


def _sign(product: Path, who: str = "human/paulo", ticked: bool = True) -> None:
    """`human/{who}` is the kit's signature vocabulary, not this file's invention.

    `score_alignment.signed_by_is_human` reads exactly this prefix at item level.
    Signing here as a bare name was what let ANY string count as a person.
    """
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


# ── the signature is a person's, and the script must be able to tell ──────────
#
# Measured 2026-09-20, before these four tests existed: a cascade signed
# `<!-- signed-by: iris-product-designer -->` with the four checkboxes DELETED
# scored `PRODUCT_ALIGNED`, exit 0 — the agent that writes the documents signing
# them under its own name, through the one gate the unattended chain rests on.
#
# Two independent holes produced that. `verdict()` recognised only `judge/` as a
# non-person, so every other string read as a human; and `TICKED_RE` was defined
# and never read, so a checklist with NO boxes satisfied "nothing is unticked".


def test_an_agent_signature_does_not_align_the_product(tmp_path: Path) -> None:
    """The rule is a person signed, not "a judge did not".

    `judge/` was the only refused prefix, which makes the gate a denylist of one
    against an open set of names. `score_alignment.signed_by_is_human` at item
    level is an allowlist for this exact reason, and the two now agree.
    """
    product = _product(tmp_path)
    _sign(product, who="iris-product-designer")
    rep = score(tmp_path)
    assert rep.pct >= FLOOR_PCT, "the cascade is structurally complete"
    assert verdict(rep) == ("AWAITING_REVIEW", 1), "the author of the documents is not a reviewer"


def test_deleting_the_checklist_is_not_ticking_it(tmp_path: Path) -> None:
    """Zero boxes is zero unticked boxes, and it is not a review."""
    product = _product(tmp_path)
    (product / "alignment.md").write_text(
        "# Product alignment\n\n## Reviewer sign-off\n\n<!-- signed-by: human/paulo -->\n",
        encoding="utf-8")
    rep = score(tmp_path)
    assert rep.ticked == 0
    assert verdict(rep) == ("AWAITING_REVIEW", 1)


def test_a_signature_keeps_the_route_it_was_given(tmp_path: Path) -> None:
    """`human/paulo (approved in session)` says more than `human/paulo`.

    The first cut captured `[^\\s>]+` and stopped at the first space, dropping the
    route — the same defect `score_alignment.py` records having fixed in its own
    pattern, reintroduced here by a narrower character class.
    """
    product = _product(tmp_path)
    _sign(product, who="human/paulo (approved in session)")
    rep = score(tmp_path)
    assert rep.signers == ["human/paulo (approved in session)"]
    assert verdict(rep) == ("PRODUCT_ALIGNED", 0)


def test_one_agent_signature_does_not_launder_a_human_one(tmp_path: Path) -> None:
    """The WEAKEST signer decides, as it does at item level."""
    product = _product(tmp_path)
    (product / "alignment.md").write_text(
        "# Product alignment\n\n## Reviewer sign-off\n\n"
        "- [x] The problem stated is the real one  <!-- signed-by: human/paulo -->\n"
        "- [x] These are the right objectives  <!-- signed-by: iris-product-designer -->\n",
        encoding="utf-8")
    rep = score(tmp_path)
    assert verdict(rep) == ("AWAITING_REVIEW", 1)


# ── a template is not a document ──────────────────────────────────────────────
#
# Measured 2026-09-20: the four shipped templates, copied into `wiki/product/`
# and not edited, scored 100.0% (34/34) — every one of the seventeen criteria
# green. G-B0 was written to stop `touch` from buying 35%, and it asked whether
# the file held anything but headings. A template holds instructions, and an
# instruction is text.


def _templates_into(root: Path) -> Path:
    """The shipped templates, copied verbatim, as an adopter would."""
    import shutil

    skills = Path(__file__).resolve().parents[2]
    d = write_wiki_dir(root, "product")
    d.mkdir(parents=True, exist_ok=True)
    for dst, src in {
        "product-vision.md": "brainstorm-vision/templates/product-vision.template.md",
        "objectives.md": "brainstorm-objectives/templates/objectives.template.md",
        "trd.md": "brainstorm-trd/templates/trd.template.md",
        "technical-pieces.md": "brainstorm-pieces/templates/technical-pieces.template.md",
        "alignment.md": "brainstorm-pieces/templates/alignment.template.md",
    }.items():
        shutil.copy(skills / src, d / dst)
    return d


def test_an_untouched_template_is_not_a_written_document(tmp_path: Path) -> None:
    """The whole cascade, copied and not filled in, is INVALID rather than perfect."""
    _templates_into(tmp_path)
    rep = score(tmp_path)
    assert "unfilled_template" in rep.hard_caps
    assert sorted(rep.unfilled_docs) == ["objectives.md", "product-vision.md",
                                         "technical-pieces.md", "trd.md"]
    assert verdict(rep) == ("INVALID", 2), "a copied scaffold is not a 100% cascade"


def test_a_guide_comment_is_not_a_written_section(tmp_path: Path) -> None:
    """`_section` measured length, and a 132-char instruction is 132 characters."""
    vision = ("# Product vision\n\n## Who it is for\n\n"
              "<!-- Someone whose situation can be pictured. 'Developers' and 'users'\n"
              "     are categories, and a category settles no trade-off. -->\n\n"
              "## The problem\nReal text here that a person wrote and would defend.\n\n"
              "## What it is\nAlso real.\n\n## What it is NOT\n- Not an alerting system.\n"
              "- Not a log search tool.\n")
    _product(tmp_path, **{"product-vision.md": vision})
    rep = score(tmp_path)
    assert next(c for c in rep.criteria if c.key == "vision_user").score == 0
    assert "vision_without_named_user" in rep.floor_caps


def test_a_number_inside_a_guide_comment_is_not_a_metric(tmp_path: Path) -> None:
    """`metric: <!-- … Gate G-B2 refuses … -->` scored a metric, on the `2` in `G-B2`."""
    objectives = ("# Objectives\n\n## OBJ-1 — Something\n"
                  "metric: <!-- must contain a number. Gate G-B2 refuses a mood. -->\n"
                  "horizon: <!-- a date or a quarter. -->\n"
                  "why: it is worth doing, and here is the observation behind it.\n")
    _product(tmp_path, **{"objectives.md": objectives})
    rep = score(tmp_path)
    assert next(c for c in rep.criteria if c.key == "obj_metric").score < 2
    assert "objective_without_measurable_metric" in rep.floor_caps
    assert "objective_without_horizon" in rep.floor_caps


def test_an_empty_bullet_is_not_a_non_goal(tmp_path: Path) -> None:
    """The template ships two bare `- ` lines, and both counted."""
    vision = VISION.split("## What it is NOT")[0] + "## What it is NOT\n\n- \n- \n"
    _product(tmp_path, **{"product-vision.md": vision})
    rep = score(tmp_path)
    assert next(c for c in rep.criteria if c.key == "vision_nongoals").score == 0
    assert "vision_without_non_goal" in rep.floor_caps


def test_a_citation_that_does_not_parse_is_not_a_citation(tmp_path: Path) -> None:
    """`serves: OBJ-<!-- … -->` was non-empty, so it counted — and matched no id,
    so it was not dangling either. A citation escaped G-B3 by being unreadable."""
    trd = ("# Technical requirements\n\n## REQ-1 — Baseline is computed\n"
           "serves: OBJ-<!-- must exist in objectives.md -->\n"
           "statement: The baseline for any series is derived from its own history.\n"
           "acceptance: A service added today has a usable baseline within 24h.\n")
    _product(tmp_path, **{"trd.md": trd})
    rep = score(tmp_path)
    assert next(c for c in rep.criteria if c.key == "req_cites").score < 2
    assert "requirement_serving_no_objective" in rep.floor_caps


@pytest.mark.parametrize("marker", ["{{SCOPE}}", "<who-it-is-for>", "???"])
def test_every_placeholder_form_is_detected(tmp_path: Path, marker: str) -> None:
    """Three of the seven alternatives never matched: `\\b` before `<` and before `?`
    needs a word character on one side, and `{{…}}` was not in the pattern at all."""
    from score_product_alignment import PLACEHOLDER_RE

    assert PLACEHOLDER_RE.search(f"metric: {marker} per week"), marker


def test_the_unsigned_marker_is_not_a_signer(tmp_path: Path) -> None:
    """`<!-- signed-by: -->` is what the template ships. It named a signer called " "."""
    from score_product_alignment import SIGNED_BY_RE

    assert SIGNED_BY_RE.findall("<!-- signed-by: -->") == []
    product = _product(tmp_path)
    (product / "alignment.md").write_text(
        "# Product alignment\n\n## Reviewer sign-off\n\n- [x] a\n\n<!-- signed-by: -->\n",
        encoding="utf-8")
    rep = score(tmp_path)
    assert rep.signers == []
    assert verdict(rep) == ("AWAITING_REVIEW", 1)

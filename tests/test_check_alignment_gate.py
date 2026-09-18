"""The gate that stops an unaligned item from being built.

WHY THIS IS THE MOST IMPORTANT TEST FILE IN plan-confidence
-----------------------------------------------------------
Until this check existed, the 90% alignment threshold was PROSE. It was written
in `skills/_kit-rules/alignment-threshold.md`, restated as a pre-condition in
`cycle-implement.md`, and listed as a phase contract in `cycle-plan.md` — and a
grep across the kit for anything that READ `records/alignment/` returned nothing.
Three documents said the item must not be built; no code could stop it.

That is the exact defect this kit has now measured five times in one week under
five different names: a mechanism with no contract, a contract with no mechanism,
a hook declared in one of two files, a rule implemented on one of two branches.
A gate whose execution depends on somebody remembering is a note.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/plan-confidence/scripts"
sys.path.insert(0, str(SCRIPTS))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_alignment_gate import check_alignment_gate  # noqa: E402 (post-bootstrap)

PLAN = """---
version: 1.0
---

# Plan: Reduce the trace explorer p95

## Context

Implements B-014 from the backlog. Evidence gathered by `/discover-plan`.

## Tasks

### T1.1 — Profile the shard scan
"""

ALIGNED_BRIEF = """
# Alignment: B-014

## Reviewer sign-off
- [x] CHK001 The stated problem is the one we actually have. [Judgement]
- [x] CHK002 The flows drawn are the flows that matter. [Judgement]
"""


def _plan(tmp_path: Path, body: str = PLAN, slug: str = "b-014-trace-p95") -> Path:
    d = tmp_path / "records" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    # A registry, because the soft floor only fires where one exists — there is no
    # bypass to close in a repository the item could not have come from. Tests
    # that need its ABSENCE build their own tree.
    (tmp_path / "BACKLOG.md").write_text("## B-001 — a registry exists here\n", encoding="utf-8")
    p = d / f"{slug}-plan.md"
    p.write_text(body, encoding="utf-8")
    return p


def _brief(tmp_path: Path, body: str, slug: str = "b-014-trace-p95") -> Path:
    d = tmp_path / "records" / "alignment"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}-alignment.md"
    p.write_text(body, encoding="utf-8")
    return p


def _complete_brief() -> str:
    """A brief that clears the machine threshold, built from the scorer's fixture."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                          / "skills/plan-alignment/tests"))
    from test_score_alignment import COMPLETE_V2
    return COMPLETE_V2


def test_a_plan_citing_a_backlog_item_with_no_brief_is_capped(tmp_path: Path) -> None:
    """The case the whole gate exists for, and the one that used to sail through.

    The plan says it implements B-014. No alignment brief exists. That is not a
    claim about the item — it is a fact about the process: the alignment never
    happened. A hard cap is the honest response, and it is the difference from
    `check_deps_audit`, where a missing report soft-floors because a hard cap
    there would assert a CVE nobody measured.
    """
    report = check_alignment_gate(_plan(tmp_path))
    assert report.applies
    assert report.hard_cap == 49
    assert "B-014" in report.reason


def test_a_blocked_brief_is_capped(tmp_path: Path) -> None:
    """Below 90% the item is not built. That is the threshold, mechanised."""
    _brief(tmp_path, "# Alignment: B-014\n\n## Problem\nIt is slow.\n")
    report = check_alignment_gate(_plan(tmp_path))
    assert report.hard_cap == 49
    assert report.verdict == "BLOCKED"


def test_a_perfect_machine_score_without_sign_off_is_still_capped(tmp_path: Path) -> None:
    """AWAITING_REVIEW is not a pass, and this is where that gets enforced.

    A brief at 100% with no human tick is the state most likely to be misread as
    approval — it looks finished, every criterion is green, and the only thing
    missing is the half the agent does not own. If the cap did not fire here, the
    reviewer sign-off would be decoration.
    """
    _brief(tmp_path, _complete_brief())
    report = check_alignment_gate(_plan(tmp_path))
    assert report.verdict == "AWAITING_REVIEW"
    assert report.hard_cap == 49


def test_an_aligned_item_passes_cleanly(tmp_path: Path) -> None:
    """The bar has to be reachable or the gate gets switched off."""
    _brief(tmp_path, _complete_brief() + ALIGNED_BRIEF.split("## Reviewer sign-off")[0]
           + "## Reviewer sign-off\n"
           + "- [x] CHK001 The stated problem is the one we actually have. [Judgement]\n"
           + "- [x] CHK002 The flows drawn are the flows that matter. [Judgement]\n"
           + "- [x] CHK003 The numbers in the NFRs are the right numbers. [Judgement]\n")
    report = check_alignment_gate(_plan(tmp_path))
    assert report.verdict == "ALIGNED"
    assert report.hard_cap is None
    assert report.soft_floor is None


def test_a_plan_with_no_backlog_item_gets_a_named_soft_floor(tmp_path: Path) -> None:
    """The boundary the script cannot decide, stated instead of hidden.

    A plan citing no `B-NNN` may be a legitimate hotfix, or it may be an item
    that skipped intake precisely to skip this gate. No regex separates those.
    Refusing outright would block every ad-hoc fix; passing silently would leave
    a one-line bypass (omit the id). A soft floor records that nobody checked and
    names it in the verdict, which is the same shape `check_deps_audit` uses for
    an unaudited dependency.
    """
    no_item = PLAN.replace("Implements B-014 from the backlog.", "A one-line hotfix.")
    report = check_alignment_gate(_plan(tmp_path, no_item, slug="hotfix-log-typo"))
    assert not report.applies
    assert report.soft_floor == 89
    assert report.hard_cap is None
    assert "no backlog item" in report.reason.lower()


def test_a_brief_found_by_slug_applies_even_without_a_cited_id(tmp_path: Path) -> None:
    """Deleting the `B-NNN` from the plan must not delete the gate.

    If an alignment brief exists for this slug, the item went through alignment
    and the plan is answerable to its verdict, whether or not the prose still
    names the id.
    """
    no_item = PLAN.replace("Implements B-014 from the backlog.", "A change.")
    _brief(tmp_path, "# Alignment\n\n## Problem\nvague\n")
    report = check_alignment_gate(_plan(tmp_path, no_item))
    assert report.applies
    assert report.hard_cap == 49


def test_an_unreadable_brief_is_not_a_passing_one(tmp_path: Path) -> None:
    """Same rule as a zero denominator: not measured is never approved."""
    p = _brief(tmp_path, "")
    p.write_bytes(b"\xff\xfe\x00garbage\x00")
    report = check_alignment_gate(_plan(tmp_path))
    assert report.hard_cap == 49
    assert "unreadable" in report.reason.lower()


def test_the_reason_always_names_what_to_do_next(tmp_path: Path) -> None:
    """A cap that does not say how to clear it trains people to route around it."""
    for setup in (lambda: None,
                  lambda: _brief(tmp_path, "# Alignment: B-014\n\n## Problem\nslow\n")):
        setup()
        report = check_alignment_gate(_plan(tmp_path))
        assert "plan-alignment" in report.reason or "sign-off" in report.reason, \
            report.reason


# ── the port defect: the same file, inert in the sibling kit ─────────────────

CYCLE_PLAN = """---
slug: streaming-cursor
milestone_id: M2
created_at: 2026-08-29
goal: Stream shard results instead of buffering them.
---

# Plan: Streaming cursor

## Context

Implements milestone M2 from the roadmap.

## Tasks

### T1.1 — Add the cursor
"""


def test_a_cycle_style_plan_is_recognised_as_committed_work(tmp_path: Path) -> None:
    """The file ported cleanly and the BEHAVIOUR did not come with it.

    The Squad names its unit of work `B-NNN` in the plan's prose. The Cycle names
    it `milestone_id: M<N>` in the plan's frontmatter — `cycle-roadmap.md § Plan
    metadata contract` — and never writes a `B-NNN` at all. A detector matching
    only `B-\\d{3,}` therefore lands in the "not applicable" branch for EVERY plan
    in that kit: soft floor 89, never a hard cap, gate permanently inert.

    Copying a script between kits and copying the gate it implements are not the
    same act. This is the fourth time that distinction has cost this kit a defect,
    and the first time a test was written for it before the port rather than after.
    """
    d = tmp_path / "records" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    plan = d / "streaming-cursor-plan.md"
    plan.write_text(CYCLE_PLAN, encoding="utf-8")

    report = check_alignment_gate(plan)
    assert report.applies, "a plan carrying milestone_id is committed work, not an ad-hoc fix"
    assert report.hard_cap == 49
    assert "M2" in report.reason


def test_frontmatter_identity_is_read_only_from_the_frontmatter(tmp_path: Path) -> None:
    """`milestone_id` mentioned in prose is a discussion, not a declaration.

    Matching it anywhere would fire on a plan that merely explains why it is NOT
    part of a milestone — and a gate that misreads prose as a commitment is the
    substring defect `detect_domain.py` shipped, where 13 of 13 `lock` matches were
    the word `lockfile`.
    """
    d = tmp_path / "records" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    (tmp_path / "ROADMAP.md").write_text("## M2 — streaming\n", encoding="utf-8")
    plan = d / "hotfix-plan.md"
    plan.write_text(
        "# Plan: hotfix\n\n## Context\n\n"
        "This carries no milestone_id: M2 belongs to the streaming work, not here.\n",
        encoding="utf-8")
    report = check_alignment_gate(plan)
    assert not report.applies
    assert report.soft_floor == 89


def test_a_repo_with_no_registry_at_all_is_not_penalised(tmp_path: Path) -> None:
    """The soft floor was firing on every ad-hoc plan, including the kit's own fixture.

    Reported from a consumer on 2026-08-29: `alignment_not_applicable` capped
    `fixtures/good-plan.md`, and `test_fixture_good_plan_does_not_trigger_caps`
    went red across seven parametrisations. The fixture is correct — the floor
    was wrong.

    The floor exists to close a one-line bypass: omit the `B-NNN` and skip the
    gate. That bypass only EXISTS where there is a registry to skip. In a
    repository with no `BACKLOG.md` and no `ROADMAP.md` there is nowhere the item
    could have come from, so ad-hoc is not a suspicion — it is the only
    possibility, and penalising it taxes every hotfix in every repository that
    does not run this cycle at all.
    """
    d = tmp_path / "records" / "plans"
    d.mkdir(parents=True)
    p = d / "hotfix-plan.md"
    p.write_text("# Plan: fix a typo\n\nNo backlog item.\n", encoding="utf-8")

    report = check_alignment_gate(p)
    assert not report.applies
    assert report.soft_floor is None, report.reason
    assert "no registry" in report.reason.lower()


def test_the_bypass_is_still_closed_where_a_registry_exists(tmp_path: Path) -> None:
    """And the floor still fires where omitting the id would actually skip something."""
    (tmp_path / "BACKLOG.md").write_text("## B-001 — something\n", encoding="utf-8")
    d = tmp_path / "records" / "plans"
    d.mkdir(parents=True)
    p = d / "hotfix-plan.md"
    p.write_text("# Plan: fix a typo\n\nNo backlog item.\n", encoding="utf-8")

    report = check_alignment_gate(p)
    assert not report.applies
    assert report.soft_floor == 89, report.reason


def test_the_kit_does_not_judge_its_own_fixtures(tmp_path: Path) -> None:
    """A plan inside the installed kit is tooling, not the project's work.

    `platform` has a `BACKLOG.md`, so the registry check above passes and the
    floor fired on `.claude/skills/plan-confidence/fixtures/good-plan.md` — the
    kit's own fixture, judged as if the project had written it. Eight tests red in
    that consumer, none of them about the project's plans.

    The rule already exists elsewhere in this kit and is written down in
    `DEFAULT_SKIP_DIRS`: *meta-tooling — /code-quality audits the PRODUCT, not its
    own skills*. The alignment gate is the same kind of gate and had not learned
    it. A plan under `.claude/` belongs to the installed kit; the project's plans
    live in `records/` or `knowledge-base/`, never inside the tooling directory.
    """
    kit_fixture = tmp_path / ".claude" / "skills" / "plan-confidence" / "fixtures"
    kit_fixture.mkdir(parents=True)
    (tmp_path / "BACKLOG.md").write_text("## B-001 — the project has a registry\n",
                                         encoding="utf-8")
    plan = kit_fixture / "good-plan.md"
    plan.write_text("# Plan: a fixture\n\nNo backlog item, by design.\n", encoding="utf-8")

    report = check_alignment_gate(plan)
    assert not report.applies
    assert report.soft_floor is None, report.reason
    assert report.hard_cap is None, report.reason
    assert "tooling" in report.reason.lower()


def test_needs_split_caps_the_plan_and_says_not_to_close_gaps(tmp_path):
    """A split item scores low because it is two items; "close the gaps" is unfollowable."""
    from check_alignment_gate import HARD_CAP, check_alignment_gate

    (tmp_path / "BACKLOG.md").write_text("## B-014 — thing\nstatus: raw\n", encoding="utf-8")
    _brief(tmp_path, "# Brief\n\n## Problem\n\nTwo subsystems.\n\n"
                     "<!-- verdict: NEEDS_SPLIT: ingest and query -->\n")
    plans = tmp_path / "records" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    plan = plans / "b-014-trace-p95-plan.md"
    plan.write_text("---\nmilestone_id: B-014\n---\n\n# Plan\n", encoding="utf-8")

    report = check_alignment_gate(plan)
    assert report.verdict == "NEEDS_SPLIT"
    assert report.hard_cap == HARD_CAP
    assert "ingest and query" in report.reason


# ── a warrant somebody took back ───────────────────────────────────────────


def _signed(extra: str = "") -> str:
    """A brief that clears the machine threshold AND carries ticked reviewer boxes.

    Both halves are needed: without the boxes the verdict is AWAITING_REVIEW for an
    unrelated reason, and a withdrawal test that passes for the wrong reason proves
    nothing about withdrawal.
    """
    return (_complete_brief()
            + "\n## Reviewer sign-off\n"
            + "- [x] CHK001 The stated problem is the one we actually have. [Judgement]\n"
            + "- [x] CHK002 The flows drawn are the flows that matter. [Judgement]\n"
            + "- [x] CHK003 The numbers in the NFRs are the right numbers. [Judgement]\n"
            + extra)


def test_a_withdrawn_sign_off_is_not_an_alignment(tmp_path: Path) -> None:
    """Measured on a consumer 2026-09-15: three items sat BLOCKED for two days while this
    gate reported `PASS — aligned at 100%`.

    The withdrawal was written in PROSE — "Sign-off withdrawn 2026-09-13, pending
    re-review" — above boxes that stayed `[x]` with their `signed-by:` comments intact.
    Every agent that opened the brief read it and stopped; the gate counted ticks. There
    was no way to say "signed, then withdrawn" that a machine could hear, so the
    strongest statement a reviewer can make was the one the mechanism could not
    represent.
    """
    plan = _plan(tmp_path)
    _brief(tmp_path, _signed("\n<!-- sign-off: WITHDRAWN: the coverage claim did not hold -->\n"))
    report = check_alignment_gate(plan)
    assert report.verdict == "WITHDRAWN"
    assert report.hard_cap
    assert "the coverage claim did not hold" in report.reason
    assert "re-review, do not re-tick" in report.reason


def test_prose_that_reads_as_a_withdrawal_stops_the_gate_from_certifying(
        tmp_path: Path) -> None:
    """The distinction this rests on: matching words to DECIDE a verdict would issue
    verdicts about language, which is what the NEEDS_SPLIT marker exists to avoid.
    Matching words to REFUSE to certify is the opposite move, and the one the doctrine
    requires — an inability to measure must never become a passing measurement.

    A false positive costs the brief AWAITING_REVIEW and a named line to mark. The
    alternative is ALIGNED over a warrant somebody took back.
    """
    plan = _plan(tmp_path)
    _brief(tmp_path, _signed("\n**Sign-off withdrawn 2026-09-13, pending re-review.**\n"))
    report = check_alignment_gate(plan)
    assert report.verdict == "AWAITING_REVIEW"
    assert report.hard_cap
    assert "Sign-off withdrawn 2026-09-13" in report.reason
    assert "sign-off: WITHDRAWN" in report.reason, "the reviewer is not told how to mark it"


def test_a_brief_explaining_the_syntax_is_not_a_brief_using_it(tmp_path: Path) -> None:
    """A brief that tells its reviewer how to withdraw contains the words. Code spans and
    fences are stripped first, the same distinction `_declarations_only` draws for the
    split marker — and the same root cause it names: a marker matched anywhere, with no
    notion of mentioned versus used."""
    plan = _plan(tmp_path)
    _brief(tmp_path, _signed(
        "\nIf the warrant no longer holds, write `Sign-off withdrawn` above and mark the "
        "brief `<!-- sign-off: WITHDRAWN: reason -->`.\n"))
    report = check_alignment_gate(plan)
    assert report.verdict == "ALIGNED", report.reason


def test_every_verdict_the_scorer_produces_is_handled_here(tmp_path: Path) -> None:
    """The durable half of this fix.

    `score_alignment.verdict` is the single place the decision is made, and this gate
    re-derived it from the parts — `needs_split`, `meets_machine_threshold`,
    `reviewer_signed_off` — so a verdict the scorer grew was invisible here and fell
    through to ALIGNED. That is how WITHDRAWN would have been born broken, and it is the
    same shape as every other seam in this kit: two mechanisms, each correct alone,
    disagreeing where nobody looks.

    This asserts the gate names every verdict the scorer can return.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                          / "skills" / "plan-alignment" / "scripts"))
    import score_alignment

    source = Path(score_alignment.__file__).read_text(encoding="utf-8")
    verdicts = set(re.findall(r'return "([A-Z_]+)"', source))
    gate = (Path(__file__).resolve().parents[1] / "skills" / "plan-confidence"
            / "scripts" / "check_alignment_gate.py").read_text(encoding="utf-8")
    missing = sorted(v for v in verdicts if f'"{v}"' not in gate)
    assert not missing, (
        f"score_alignment can return {missing} and check_alignment_gate never names "
        f"them — an unnamed verdict falls through to ALIGNED")


def test_a_withdrawal_the_reviewer_restores_stops_blocking(tmp_path: Path) -> None:
    """WITHDRAWN without RESTORED is a state with no exit, and that is not hypothetical.

    This project's discipline is to correct forward and leave the superseded reading in
    place, so a brief that went withdrawal → refusal → repair → signature carries the
    withdrawal prose forever. The honest record and the passing record end up in tension
    and the honest one loses — which is a reason to stop writing honest records. The
    consumer session raised exactly this, and it was right.
    """
    plan = _plan(tmp_path)
    _brief(tmp_path, _signed(
        "\n<!-- sign-off: WITHDRAWN: the coverage claim did not hold -->\n"
        "\n<!-- sign-off: RESTORED: ground closed at the root, control verified -->\n"))
    report = check_alignment_gate(plan)
    assert report.verdict == "ALIGNED"
    assert not report.hard_cap
    assert "later restored" in report.reason, \
        "a warrant taken back and given again is not a warrant never questioned"
    assert "ground closed at the root" in report.reason


def test_a_restoration_must_answer_the_withdrawal_not_precede_it(tmp_path: Path) -> None:
    """A restoration is a REPLY. "Restored" above the withdrawal it restores is not one,
    and a brief reorganised so the two swap places reads as withdrawn — the safe
    direction, and the reason order is read here and nowhere else."""
    plan = _plan(tmp_path)
    _brief(tmp_path, _signed(
        "\n<!-- sign-off: RESTORED: stale note from an earlier round -->\n"
        "\n<!-- sign-off: WITHDRAWN: a new ground, found today -->\n"))
    assert check_alignment_gate(plan).verdict == "WITHDRAWN"


def test_the_marker_also_answers_a_withdrawal_written_only_in_prose(tmp_path: Path) -> None:
    """The exit that matters in practice: three consumer briefs carry withdrawals that
    predate the marker entirely. One RESTORED line from a reviewer clears them, without
    anyone deleting the withdrawal the record is right to keep."""
    plan = _plan(tmp_path)
    _brief(tmp_path, _signed(
        "\n**Sign-off withdrawn 2026-09-13, pending re-review.**\n"
        "\n<!-- sign-off: RESTORED: re-verified by execution in both directions -->\n"))
    assert check_alignment_gate(plan).verdict == "ALIGNED"

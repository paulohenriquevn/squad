#!/usr/bin/env python3
"""The 90% alignment threshold, mechanised.

WHY THIS EXISTS
---------------
`skills/_kit-rules/alignment-threshold.md` says an item below 90% shared understanding must
not be built. `cycle-implement.md` repeats it as a pre-condition.
`cycle-plan.md` lists it as a phase contract. Three documents, one rule — and a
grep across the kit for anything that READ `records/alignment/` returned nothing.

The rule held exactly as long as somebody remembered it. That is the same defect
this kit has now measured under five names in one week: a mechanism with no
contract, a contract with no mechanism, a hook declared in one of two files, a
rule implemented on one of two branches, a capability nobody could find. A gate
whose execution depends on memory is a note.

WHAT IT ASSERTS
---------------
It does not judge the brief; `score_alignment.py` does that. This reads the
verdict that scorer produces and turns it into a cap:

| State                                             | Effect |
|---|---|
| Plan cites no `B-NNN` and no brief exists for it  | soft floor (<= 89) — see below |
| Cites an item, no alignment brief on disk         | **hard cap (<= 49)** |
| Reviewer marked the brief NEEDS_SPLIT             | **hard cap (<= 49)** — NEEDS_SPLIT |
| Brief scores below the machine threshold          | **hard cap (<= 49)** — BLOCKED |
| Brief clears it but no human signed off           | **hard cap (<= 49)** — AWAITING_REVIEW |
| Brief unreadable                                  | **hard cap (<= 49)** |
| ALIGNED                                           | does not apply |

WHY A HARD CAP FOR THE MISSING BRIEF, WHEN check_deps_audit SOFT-FLOORS
-----------------------------------------------------------------------
That difference is deliberate and it is the interesting part.

A missing dependency audit soft-floors because a hard cap there would assert "this
plan has a critical CVE" — a claim about the dependency that nobody measured. The
honest claim is about the PROCESS, and a soft floor records it.

Here the process IS the subject. A missing alignment brief does not imply anything
about the item; it states, exactly, that the alignment never happened. That is not
an inference, and the rule about it is unconditional: below the threshold the item
is not built. So the cap is hard, and there is no `--skip` and no dismissing ADR —
an escape hatch on this gate would be an escape hatch on the whole reason the gate
exists.

WHERE THE SCRIPT STOPS, SAID OUT LOUD
-------------------------------------
A plan citing no `B-NNN` may be a legitimate hotfix, or it may be an item that
skipped intake precisely to skip this gate. **No regex separates those**, and
pretending otherwise would be the fabricated-precision this kit refuses elsewhere.
Refusing outright would block every ad-hoc fix; passing silently would leave a
one-line bypass. So it soft-floors at 89 and names the reason, which keeps the
plan out of SHIPPABLE and puts the judgement in front of a human — the same place
`cycle-backlog`'s G3/G4/G5 leave theirs.

Usage:
    python3 check_alignment_gate.py <plan.md> [--json]

Exit codes:
    0 — no cap
    1 — capped or floored
    2 — the plan could not be read
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_SHARED_UNDERSTANDING = (
    Path(__file__).resolve().parents[2] / "plan-alignment" / "scripts"
)
if str(_SHARED_UNDERSTANDING) not in sys.path:
    sys.path.insert(0, str(_SHARED_UNDERSTANDING))

#: How the two kits NAME committed work, which is not the same string.
#:
#: The Squad writes `B-NNN` in the plan's prose (`cycle-backlog.md § Item
#: schema`). The Cycle writes `milestone_id: M<N>` in the plan's FRONTMATTER
#: (`cycle-roadmap.md § Plan metadata contract`) and never writes a `B-NNN` at
#: all. A detector matching only the first lands in the "not applicable" branch
#: for every plan in the second — soft floor, never a hard cap, gate inert.
#:
#: Copying a script between kits and copying the gate it implements are not the
#: same act, and this is the fourth time that distinction has cost a defect here.
_ITEM_RE = re.compile(r"\bB-(\d{3,})\b")

#: Read ONLY from the frontmatter. Matching `milestone_id` anywhere would fire on
#: a plan explaining why it is NOT part of a milestone — the substring defect
#: `detect_domain.py` shipped, where 13 of 13 `lock` matches were `lockfile`.
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_MILESTONE_RE = re.compile(r"^milestone_id:\s*(\S+)\s*$", re.MULTILINE)


#: The item a plan's FILENAME declares. The kit writes `records/plans/{slug}-plan.md` and
#: `_brief_for` above already derives the brief path from that slug, so the convention is
#: load-bearing rather than decorative — reading the id from it is reading a declaration.
_SLUG_ITEM_RE = re.compile(r"\A(b-\d{3,})", re.IGNORECASE)


def _committed_work_id(content: str, plan_path: Path | None = None) -> str | None:
    """The id this plan is answerable to, in whichever kit's vocabulary.

    DECLARATIONS FIRST, and a guess only where it cannot be wrong. This returned the
    SMALLEST id mentioned anywhere and consulted the frontmatter only when no id was
    mentioned at all — so the guess beat the declaration in every plan that names a
    related item, which is every well-written one.

    Measured by the consumer that reported it, on a real plan for `B-286` mentioning
    `B-286` ten times, `B-271` seven, `B-288` four and `B-036` twice: it returned `B-036`.
    `B-036` is blocked and blocked forces FULL, so a brief complete by the LOCAL contract
    was graded against the FULL rubric — 23/34 = 68% and a hard cap, on a plan scoring
    99.2 by its own structural measure. Two items were dragged behind it and a lane
    concluded from the message that every LOCAL item in every consumer was unbuildable.

    The order:

        1. frontmatter `milestone_id`   what the author wrote down on purpose
        2. the filename slug            the kit's own naming, which `_brief_for` relies on
        3. exactly one id in the body   a guess that cannot pick the wrong one
        4. otherwise None               several candidates and no declaration

    Step 4 used to be step 1's answer. It is now a refusal, and since the depth fix a
    refusal RENDERS — `NOT MEASURED — the item's depth could not be derived` — instead of
    silently grading the full rubric.
    """
    fm = _FRONTMATTER_RE.match(content)
    if fm:
        m = _MILESTONE_RE.search(fm.group(1))
        if m and m.group(1).lower() not in ("null", "none", "~", '""', "''"):
            return m.group(1)

    if plan_path is not None:
        slug = _SLUG_ITEM_RE.match(plan_path.name)
        if slug:
            return slug.group(1).upper()

    items = sorted(set(_ITEM_RE.findall(content)))
    if len(items) == 1:
        return f"B-{items[0]}"
    return None

#: The cap values the rest of plan-confidence already speaks in.
HARD_CAP = 49       # INVALID — the plan cannot enter /implement
SOFT_FLOOR = 89     # SHIPPABLE -> SHIPPABLE_WITH_CAVEATS


@dataclass(frozen=True)
class AlignmentGateReport:
    applies: bool
    verdict: str | None          # ALIGNED · AWAITING_REVIEW · BLOCKED · NEEDS_SPLIT · MISSING · UNREADABLE
    reason: str
    hard_cap: int | None = None
    soft_floor: int | None = None
    brief_path: str | None = None
    machine_ratio: float | None = None
    #: Why the item's depth could not be derived, or empty when it was. Carried on the
    #: report rather than printed at the call site, because the JSON consumer needs the
    #: same distinction as the terminal one — a score against an unconfirmed rubric is
    #: not the same fact as a score against the right one.
    depth_unmeasured: str = ""
    #: The item and rubric the score was computed against, for the reader who has to
    #: act on it. Absent before the score exists.
    graded_as: str = ""

    @property
    def is_clean(self) -> bool:
        return self.hard_cap is None and self.soft_floor is None


def _brief_for(plan_path: Path) -> Path:
    """`records/plans/{slug}-plan.md` -> `records/alignment/{slug}-alignment.md`."""
    slug = plan_path.name[:-len("-plan.md")] if plan_path.name.endswith("-plan.md") \
        else plan_path.stem
    return plan_path.parent.parent / "alignment" / f"{slug}-alignment.md"


def _is_kit_tooling(plan_path: Path) -> bool:
    """Is this plan part of the INSTALLED KIT rather than the project's work?

    The rule is already written down elsewhere in this kit, in
    `DEFAULT_SKIP_DIRS`: *meta-tooling — /code-quality audits the PRODUCT, not its
    own skills*. The alignment gate is the same kind of gate and had not learned
    it, so in a consumer that has a `BACKLOG.md` it judged
    `.claude/skills/plan-confidence/fixtures/good-plan.md` as if the project had
    written it — eight tests red, none of them about the project's plans.

    A project's plans live in `records/` or `knowledge-base/`. Anything under the
    tooling directory belongs to the kit.
    """
    parts = plan_path.resolve().parts
    return ".claude" in parts and "skills" in parts


def _registry_exists(plan_path: Path) -> bool:
    """Does this repository keep a backlog or roadmap the plan could have come from?

    Walks up from the plan rather than trusting the process's cwd, which is
    whatever invoked the scorer and says nothing about the project under test.
    """
    for parent in [plan_path.resolve(), *plan_path.resolve().parents]:
        for name in ("BACKLOG.md", "ROADMAP.md"):
            if (parent / name).is_file():
                return True
        if (parent / ".git").exists():
            break  # repository root reached; do not escape into a sibling project
    return False



def _depth_for(plan_path: Path, item: str | None) -> tuple[str, str]:
    """The alignment depth for this ITEM, and why it could not be derived when it could not.

    Returns `FULL` when the item is unknown or the classifier cannot answer. FULL is the
    safe direction: it asks for more, and a brief that clears the full rubric clears the
    local one too. The reverse default would let an unclassifiable item be graded on the
    shallow rubric, which is the escape hatch `alignment-threshold.md` refuses. THAT DOES
    NOT MOVE.

    What moved is the second half of the tuple. This returned `.depth` alone and dropped
    the two fields the classifier carries for exactly this question — `measurable` and
    `why_unmeasurable` — so a plan graded at FULL because the registry could not be found
    read identically to one graded at FULL because the item needs it.

    Measured by the consumer that reported it, from inside a worktree the registry is not
    in: the gate printed `BLOCKED — close these first: nfr_measurable, flows,
    scenario_classes, system_diagram`. From where the registry is, the same item is LOCAL
    and the same brief scores 92% — and four of those four criteria are four of the five
    artifacts LOCAL removes, whose absence is the whole point of LOCAL existing. A lane read
    that message, concluded the `--depth` flag did not exist and that every LOCAL item in
    every consumer was unbuildable, and stopped. The flag exists and this gate uses it.

    Same rule `check_plugin_freshness` keeps between `unverifiable` and `aligned`, and the
    one this repository added between a killed test run and a failing one on the same day.
    """
    if not item:
        return "FULL", "the plan cites no item, so there is nothing to classify"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plan-alignment/scripts"))
        from classify_alignment_depth import classify

        verdict = classify(_project_root(plan_path), item)
        if not verdict.measurable:
            return verdict.depth, verdict.why_unmeasurable or "the classifier could not say why"
        return verdict.depth, ""
    except Exception as exc:  # noqa: BLE001 — an unclassifiable item is scored at FULL
        return "FULL", f"the classifier raised {exc.__class__.__name__}"


def _project_root(plan_path: Path) -> Path:
    """Walk up from the PLAN to the project, never trusting the process's cwd.

    Same reasoning as `_registry_exists` one function up, and the same stopping rule: a
    `.git` is the repository root and walking past it reaches a sibling project whose
    registry would answer for this one.
    """
    for parent in [plan_path.resolve(), *plan_path.resolve().parents]:
        if (parent / "BACKLOG.md").is_file():
            return parent
        if (parent / ".git").exists():
            return parent
    return plan_path.resolve().parent


def check_alignment_gate(plan_path: Path) -> AlignmentGateReport:
    """Read the alignment verdict for this plan's item and turn it into a cap."""
    if _is_kit_tooling(Path(plan_path)):
        return AlignmentGateReport(
            applies=False, verdict=None,
            reason=("this plan is part of the installed kit's tooling, not the "
                    "project's work — the kit does not audit itself"))

    content = Path(plan_path).read_text(encoding="utf-8-sig", errors="replace")
    cited = _committed_work_id(content, plan_path)
    brief = _brief_for(Path(plan_path))

    if cited is None and not brief.exists():
        # The boundary the script cannot decide — but only where there is a
        # boundary to cross. The floor closes a one-line bypass: omit the `B-NNN`
        # and skip the gate. That bypass exists only where there is a registry to
        # skip. In a repository with neither BACKLOG.md nor ROADMAP.md there is
        # nowhere the item could have come from, so ad-hoc is not a suspicion, it
        # is the only possibility.
        #
        # Measured on 2026-08-29, reported from a consumer: without this
        # distinction the floor fired on the kit's own `fixtures/good-plan.md` and
        # turned `test_fixture_good_plan_does_not_trigger_caps` red across seven
        # parametrisations. A gate that taxes every hotfix in every repository
        # that does not run this cycle is a gate somebody switches off.
        if not _registry_exists(Path(plan_path)):
            return AlignmentGateReport(
                applies=False, verdict=None,
                reason=("plan names no backlog item and this repository has no registry "
                        "(no BACKLOG.md, no ROADMAP.md) — there is nowhere the item could "
                        "have come from, so nothing is being skipped"))
        return AlignmentGateReport(
            applies=False, verdict=None,
            reason=("plan names no backlog item and no milestone, and no alignment "
                    "brief exists for its slug — this may be a legitimate ad-hoc "
                    "fix, or committed work that skipped intake to skip this gate. "
                    "No check separates those; a human decides. Run "
                    "/plan-alignment if it came from the registry."),
            soft_floor=SOFT_FLOOR)

    if not brief.exists():
        return AlignmentGateReport(
            applies=True, verdict="MISSING",
            reason=(f"plan implements {cited} and no alignment brief exists at "
                    f"{brief}. The alignment never happened, so the item is not "
                    f"built. Run /plan-alignment {cited}."
                    if cited else
                    f"an alignment brief was expected at {brief} and is absent."),
            hard_cap=HARD_CAP, brief_path=str(brief))

    try:
        from score_alignment import score_alignment
        # The depth is DERIVED from the item, never read from the brief. Scoring a LOCAL
        # brief against the FULL rubric is what made the shallow path unusable: measured
        # 2026-09-18, a LOCAL brief complete by its own contract topped out at 24/34 =
        # 70.6% against a 90% floor, because five criteria grade the sections LOCAL
        # removes. Fixing the scorer alone would have left this gate scoring the old way
        # — the half-applied shape this kit has now measured three times.
        depth, depth_unmeasured = _depth_for(plan_path, cited)
        graded_as = f"{cited or 'no item'} at depth {depth}"
        report = score_alignment(brief, depth)
    except Exception as exc:  # noqa: BLE001 — any failure here is "not measured"
        return AlignmentGateReport(
            applies=True, verdict="UNREADABLE",
            reason=(f"the alignment brief at {brief} is unreadable ({exc.__class__.__name__}). "
                    f"Not measured is not approved — fix the brief and re-run "
                    f"/plan-alignment."),
            hard_cap=HARD_CAP, brief_path=str(brief))

    ratio = round(report.machine_ratio, 4)

    # Checked before the score, for the same reason the scorer checks it first: a
    # split item scores low BECAUSE it is two items, and "close these gaps" is advice
    # no rewrite can follow. The plan must not be built either way, so the cap is the
    # same — what changes is what the reader is told to do about it.
    # Checked FIRST, and before the score: a reviewer who takes their sign-off back has
    # said something no score can answer. Measured on a consumer 2026-09-15 — three items
    # sat BLOCKED for two days while this gate reported `PASS — aligned at 100%`, because
    # the withdrawal was written in prose above boxes that stayed ticked.
    if report.sign_off_withdrawn:
        because = f" ({report.withdrawal_reason})" if report.withdrawal_reason else ""
        return AlignmentGateReport(
            applies=True, verdict="WITHDRAWN",
            reason=(f"the reviewer withdrew their sign-off{because}. The ticked boxes "
                    f"below it record a review that no longer stands — re-review, do not "
                    f"re-tick."),
            hard_cap=HARD_CAP, brief_path=str(brief), machine_ratio=ratio,
            depth_unmeasured=depth_unmeasured, graded_as=graded_as)

    if report.unmarked_withdrawal_prose:
        return AlignmentGateReport(
            applies=True, verdict="AWAITING_REVIEW",
            reason=(f"this brief reads as a withdrawal and carries no marker the gate can "
                    f"read: \"{report.unmarked_withdrawal_prose}\". Mark it "
                    f"`<!-- sign-off: WITHDRAWN: reason -->` if the warrant is withdrawn, "
                    f"or reword the line if it is not. The gate declines to certify a "
                    f"warrant whose state it cannot read — it does not guess either way."),
            hard_cap=HARD_CAP, brief_path=str(brief), machine_ratio=ratio,
            depth_unmeasured=depth_unmeasured, graded_as=graded_as)

    if report.needs_split:
        because = f" ({report.split_reason})" if report.split_reason else ""
        return AlignmentGateReport(
            applies=True, verdict="NEEDS_SPLIT",
            reason=(f"the reviewer marked this brief NEEDS_SPLIT{because}. "
                    f"Do not close gaps — split the item, and align each piece on its own."),
            hard_cap=HARD_CAP, brief_path=str(brief), machine_ratio=ratio,
            depth_unmeasured=depth_unmeasured, graded_as=graded_as)

    if not report.meets_machine_threshold:
        gaps = ", ".join(c.key for c in report.gaps[:4])
        return AlignmentGateReport(
            applies=True, verdict="BLOCKED",
            reason=(f"alignment scores {ratio:.0%}, below the 90% threshold. "
                    f"Close these first: {gaps}. "
                    f"Return to /plan-alignment and re-score after each pass."),
            hard_cap=HARD_CAP, brief_path=str(brief), machine_ratio=ratio,
            depth_unmeasured=depth_unmeasured, graded_as=graded_as)

    if not report.reviewer_signed_off:
        pending = len(report.pending_review) or report.reviewer_items_total or "all"
        return AlignmentGateReport(
            applies=True, verdict="AWAITING_REVIEW",
            reason=(f"machine score is {ratio:.0%} and no human has signed off "
                    f"({pending} item(s) unticked in `## Reviewer sign-off`). "
                    f"AWAITING_REVIEW is not a pass, and the agent may never tick a "
                    f"box — ask the reviewer."),
            hard_cap=HARD_CAP, brief_path=str(brief), machine_ratio=ratio,
            depth_unmeasured=depth_unmeasured, graded_as=graded_as)

    restored = ""
    if report.sign_off_restored:
        because = f" ({report.restoration_reason})" if report.restoration_reason else ""
        # Said out loud on the passing result: a warrant taken back and given again is
        # not the same history as one never questioned, and the record should show it.
        restored = f", after a withdrawal the reviewer later restored{because}"
    return AlignmentGateReport(
        applies=True, verdict="ALIGNED",
        reason=(f"aligned at {ratio:.0%} with {report.reviewer_items_total} "
                f"reviewer item(s) ticked{restored}"),
        brief_path=str(brief), machine_ratio=ratio,
            depth_unmeasured=depth_unmeasured, graded_as=graded_as)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        report = check_alignment_gate(args.plan)
    except OSError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "applies": report.applies, "verdict": report.verdict,
            "reason": report.reason, "hard_cap": report.hard_cap,
            "soft_floor": report.soft_floor, "brief_path": report.brief_path,
            "machine_ratio": report.machine_ratio,
            "depth_unmeasured": report.depth_unmeasured,
            "graded_as": report.graded_as,
        }, indent=2, ensure_ascii=False))
        return 0 if report.is_clean else 1

    tag = {"ALIGNED": "✓", None: "~"}.get(report.verdict, "✗")
    print(f"{tag} alignment gate: {report.verdict or 'NOT APPLICABLE'}")
    print(f"  {report.reason}")
    # WHICH item and WHICH rubric, always. A reader told to close four criteria cannot act
    # on that without knowing whose rubric named them — and the four the gate used to name
    # most often were four of the five artifacts the LOCAL rubric removes, so the reader was
    # being sent to write documents their item does not require.
    if report.graded_as:
        print(f"  graded as: {report.graded_as}")
    # BEFORE the cap, because it changes what the cap means. A reader told to close four
    # criteria needs to know whether those four belong to this item's rubric at all.
    if report.depth_unmeasured:
        print(f"\n  NOT MEASURED — the item's depth could not be derived "
              f"({report.depth_unmeasured}), so the FULL rubric was applied. The score "
              f"above grades a rubric that may not be this item's.")
    if report.hard_cap:
        print(f"\n  HARD CAP {report.hard_cap} — this plan cannot enter /implement.")
        print("  There is no --skip and no dismissing ADR. An escape hatch on this")
        print("  gate would be an escape hatch on the reason it exists.")
    elif report.soft_floor:
        print(f"\n  SOFT FLOOR {report.soft_floor} — capped below SHIPPABLE, not refused.")
    return 0 if report.is_clean else 1


if __name__ == "__main__":
    sys.exit(main())

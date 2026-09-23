#!/usr/bin/env python3
"""A document advances on a majority of signed approvals, or it goes back.

    python3 mechanisms/cycle/review_panel.py --record records/panels/B-014-discover.json

## What this is

DISCOVER produces an opportunity and PLAN produces a plan. Both are judged by a
panel of three reviewers — at least one outside the Anthropic family — and both
need **2 of 3** to advance. Below the majority the document is returned as
`NEEDS_REVISION`, a verdict that already exists and already holds an item.

## The counting is not the point

Counting to two is trivial. Everything of value is in what this REFUSES to count,
because each refusal is a way a panel can look convened and be a rubber stamp:

    the author voting on their own document
    three votes that are one model asked three times
    a reviewer that could not run, read as agreement
    a verdict with no reasoning behind it
    one reviewer voting twice

`skills/plan-alignment/scripts/alignment_judge.py` was precisely such a ceremony
until this existed. It accepts `--verdict signed` on the command line and stamps
the brief; its docstring promises the judge "reads the item's EVIDENCE", and
nothing in the file verifies that. Its independence rested entirely on who invoked
it, which is not a property a mechanism can claim about itself.

## Why an incomplete panel is not a rejection

Two approvals out of two is not 2-of-3. The threshold is over a FULL panel, so a
missing reviewer is an abstention — and an abstention approves nothing and rejects
nothing. It means the panel did not convene, which is a different fact from the
document being wrong, and it takes a different action: the item returns to the
registry with an `access` impediment (`halt_disposition.py`), because a reviewer
that cannot run is a capability nobody's authority supplies.

Collapsing the two would either fail good documents or, far worse, let a panel of
one report a majority.

## Why an unrecognised model counts toward nothing

If an unknown model string satisfied the diversity requirement, `--model anything`
would prove orthogonality by typing. So the requirement is a vote from a
RECOGNISED family that is not Anthropic's; `unknown` supplies neither side.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

#: Odd on purpose: a tie is not a state this mechanism should ever have to name.
PANEL_SIZE = 3

#: How many seats a phase declares. Three where the verdict is a MAJORITY — the 2-of-3 is the
#: property, and a panel that shrank to one would lose it. One for `alignment`, because the
#: alignment sign-off is not a vote: four checkboxes are ticked by a single reviewer who is not
#: the author, and `score_alignment` reports the weakest signer of the set. A majority has no
#: meaning over that, and requiring three reviewers to tick one checklist would ask a project for
#: reviewers the mechanism cannot use.
#:
#: Added 2026-09-23. Until then `rules/review-panel.txt` named no `alignment` phase at all, so
#: nothing convened the reviewer the sign-off contract requires — `alignment_judge.py` records a
#: verdict and says of itself that *"it does not read the evidence"*, and the agent that does was
#: summoned by hand. A consumer's practical path became messaging another session, which depends
#: on one being alive and idle; one item took five rounds that way.
PANEL_SIZE_BY_PHASE = {"alignment": 1}


def panel_size_for(phase: str) -> int:
    """Seats this phase declares. `PANEL_SIZE` unless the phase says otherwise."""
    return PANEL_SIZE_BY_PHASE.get(phase.lower(), PANEL_SIZE)

#: How many approvals carry a document. Simple majority of a full panel.
MAJORITY = 2

#: The floor `alignment_judge.py` applies to a signature, applied to a vote for
#: the same reason: a verdict with no reasoning is a tick.
MIN_REASON_WORDS = 15

#: Model prefixes to families. Matching is by prefix because versions move and a
#: table pinned to exact ids goes stale silently — which for THIS table would mean
#: quietly failing to notice that three reviewers share a family.
_FAMILIES: tuple[tuple[str, str], ...] = (
    ("claude", "anthropic"),
    ("gpt", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("o4", "openai"),
    ("codex", "openai"),
    ("gemini", "google"),
    ("llama", "meta"),
    ("mistral", "mistral"),
    ("grok", "xai"),
    ("deepseek", "deepseek"),
    ("qwen", "alibaba"),
)

#: The family the kit itself runs on. The diversity rule is written against this
#: rather than against a hardcoded "anthropic" in three places.
HOME_FAMILY = "anthropic"

#: A reviewer that runs as a sub-agent of this session needs no binary on PATH.
BUILTIN = "builtin"


class PanelInvalid(Exception):
    """The panel did not convene validly. NOT a rejection of the document."""


class PanelOutcome(Enum):
    APPROVED = "approved"
    RETURNED = "returned"


def family_of(model: str) -> str:
    """Which model family is this, or `unknown`.

    `unknown` is a real answer and it counts toward NOTHING — see the module
    docstring. A caller must not read it as "not Anthropic, therefore diverse".
    """
    name = (model or "").strip().lower()
    for prefix, fam in _FAMILIES:
        if name.startswith(prefix):
            return fam
    return "unknown"


@dataclass(frozen=True)
class Seat:
    """One declared seat: which phase, which agent, on what model, reached how."""

    phase: str
    agent: str
    model: str
    invocation: str

    @property
    def family(self) -> str:
        return family_of(self.model)

    @property
    def is_builtin(self) -> bool:
        """A sub-agent of this session rather than an executable on PATH."""
        return self.invocation.strip().lower() == BUILTIN


def parse_roster(text: str) -> list[Seat]:
    """Every declared seat, in file order.

    ONE parser, imported by everything that reads the roster. Two readers of the
    same table drift apart silently, and for THIS table the drift would be a panel
    that one tool says is formable and another seats differently.

    Raises ValueError on a row that announces a reviewer and does not describe one:
    a malformed row must never parse to "no reviewer" and read as a small panel.
    """
    seats: list[Seat] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or not line.startswith("reviewer"):
            continue
        _, _, value = line.partition("=")
        parts = [p.strip() for p in value.split("|")]
        if len(parts) != 4 or not all(parts):
            raise ValueError(
                f"malformed reviewer row: {raw.strip()!r} — expected "
                "`reviewer = <phase> | <agent> | <model> | <how to invoke>`"
            )
        seats.append(Seat(phase=parts[0].lower(), agent=parts[1],
                          model=parts[2], invocation=parts[3]))
    return seats


def parse_panel_phases(text: str) -> list[str]:
    """The phases a panel gates. A phase absent from this list is not gated."""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.startswith("panel_phases"):
            _, _, value = line.partition("=")
            return [p.strip().lower() for p in value.split(",") if p.strip()]
    return []


def single_family_waived(text: str) -> tuple[bool, str]:
    """Did this project declare that it runs a one-family panel, and why?

    Returns `(waived, reason)`. A waiver with no reason is not a waiver: an exemption
    nobody justified is an escape hatch, and the roster says so in its own words.
    """
    accepted = False
    reason = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.startswith("single_family_panel"):
            _, _, value = line.partition("=")
            accepted = value.strip().lower() in {"accepted", "yes", "true"}
        elif line.startswith("single_family_reason"):
            _, _, value = line.partition("=")
            reason = value.strip()
    return (accepted and bool(reason)), reason


def seats_for(text: str, phase: str) -> list[Seat]:
    """The seats declared for one phase."""
    return [s for s in parse_roster(text) if s.phase == phase.lower()]


@dataclass(frozen=True)
class Vote:
    """One reviewer's judgement, with the reasoning that makes it checkable."""

    reviewer: str
    model: str
    verdict: str  # approve | return | abstain
    reason: str

    @property
    def family(self) -> str:
        return family_of(self.model)

    @property
    def approves(self) -> bool:
        return self.verdict == "approve"

    @property
    def counted(self) -> bool:
        """Did this reviewer actually judge? An abstention did not."""
        return self.verdict in ("approve", "return")


@dataclass
class Panel:
    """The votes cast on one artifact, and the rules that make them a panel."""

    slug: str
    phase: str
    artifact: str
    author: str
    votes: list[Vote] = field(default_factory=list)

    #: The agents `convene_panel.py` assigned to this artifact, when the caller has
    #: the assignment. `None` means nobody checked, which is a weaker claim and is
    #: reported as such rather than silently treated as a match.
    assigned: list[str] | None = None

    #: This project declared, in `rules/review-panel.txt`, that it runs a panel of one
    #: family and what that costs it. DECLARED, never inferred from the roster: a panel
    #: that happens to be one family and a panel that was meant to be read the same on
    #: disk, and only one of them is a decision.
    #:
    #: The kit's rule does not move. `rules/review-panel.txt` is the layer the installer
    #: preserves precisely because which models a project can reach is not the kit's
    #: business — so a project with no second provider chooses between running no panel
    #: and running one that says what it is worth, and this is the second. Every outcome
    #: carries the waiver, so APPROVED under it reads as the weaker claim it is.
    single_family_waived: bool = False

    # -- validity ---------------------------------------------------------

    def _validate(self) -> None:
        """Every refusal a panel needs, in the order that makes the message useful.

        Structure before content: telling a caller their reason is too short, when
        the real problem is that the author is sitting on their own panel, sends
        them to fix the wrong thing.
        """
        reviewers = [v.reviewer for v in self.votes]

        if self.author in reviewers:
            raise PanelInvalid(
                f"the author ({self.author}) sat on the panel judging their own "
                f"{self.phase} artifact. An author approving their own work is not a "
                "review — skills/_kit-rules/alignment-threshold.md"
            )

        if len(set(reviewers)) != len(reviewers):
            raise PanelInvalid(
                "a reviewer voted twice; a panel needs distinct reviewers, or the "
                "majority is one opinion counted more than once"
            )

        if self.assigned is not None and set(reviewers) != set(self.assigned):
            missing = sorted(set(self.assigned) - set(reviewers))
            extra = sorted(set(reviewers) - set(self.assigned))
            detail = []
            if missing:
                detail.append(f"never voted: {', '.join(missing)}")
            if extra:
                detail.append(f"voted unassigned: {', '.join(extra)}")
            raise PanelInvalid(
                "the panel that voted is not the panel that was convened "
                f"({'; '.join(detail)}). Convening is theatre if the record may name "
                "different reviewers than the assignment did — a document could be "
                "sent to the specialists its content demands and signed off by three "
                "others"
            )

        counted = [v for v in self.votes if v.counted]
        if len(counted) != PANEL_SIZE:
            abstained = [v.reviewer for v in self.votes if not v.counted]
            detail = f" ({', '.join(abstained)} abstained)" if abstained else ""
            raise PanelInvalid(
                f"the panel did not convene: {len(counted)} of {PANEL_SIZE} votes "
                f"cast{detail}. An abstention approves nothing and rejects nothing — "
                "this is not a returned document, it is an absent reviewer, and it "
                "is an `access` impediment for halt_disposition.py"
            )

        families = {v.family for v in counted}
        if not (families - {HOME_FAMILY, "unknown"}) and not self.single_family_waived:
            raise PanelInvalid(
                f"every counted vote is from the {HOME_FAMILY} family or an "
                f"unrecognised model ({sorted(families)}). A panel needs at least one "
                "reviewer from a recognised family outside it: correlated models share "
                "failure modes, and a plausible fabrication that survives one tends to "
                "survive its siblings. An unrecognised model supplies neither side"
            )

        for v in counted:
            if len(v.reason.split()) < MIN_REASON_WORDS:
                raise PanelInvalid(
                    f"{v.reviewer} voted '{v.verdict}' with a reason of "
                    f"{len(v.reason.split())} words. Say what was checked and against "
                    f"which evidence — under {MIN_REASON_WORDS} words it is a tick, and "
                    "a tick is what a panel exists to be more than"
                )

    # -- the tally --------------------------------------------------------

    @property
    def approving_families(self) -> set[str]:
        return {v.family for v in self.votes if v.approves}

    @property
    def carried_by_one_family(self) -> bool:
        """Would this majority be correlated?

        The composition rule guarantees a non-home reviewer SITS. It does not
        guarantee one APPROVES, and the difference is the whole value of the seat:
        two Claudes can outvote the orthogonal reviewer, and the panel then advances a
        document on exactly the correlated approval the seat was bought to prevent.
        """
        return not (self.approving_families - {HOME_FAMILY, "unknown"})

    def tally(self) -> PanelOutcome:
        """APPROVED on a majority that spans two recognised families; RETURNED otherwise.

        Counting to two was never the point, and neither is seating three. Until
        2026-09-10 the diversity check ran over the votes CAST rather than the votes
        that CARRY — so `nemesis` and `leonardo` approving while
        `judge-codex` returned produced APPROVED, with the dissent filed and the
        conclusion advanced. A reviewer flagged it, and this repository's own test
        suite had frozen the failure as the contract: `test_a_majority_carries_the_document`
        asserted exactly that combination.

        A `return` from the only orthogonal seat is therefore not outvoted by the home
        family. The document goes back — which is what `NEEDS_REVISION` already means,
        so no token is invented for it.
        """
        self._validate()
        approvals = sum(1 for v in self.votes if v.approves)
        if approvals < MAJORITY:
            return PanelOutcome.RETURNED
        # The waiver reaches here too, and it has to: refusing the correlated majority
        # while accepting the correlated roster would make the declaration buy nothing
        # — every document would return, which is the "run no panel at all" option
        # wearing a panel's clothes.
        if self.carried_by_one_family and not self.single_family_waived:
            return PanelOutcome.RETURNED
        return PanelOutcome.APPROVED

    @property
    def outcome_note(self) -> str:
        """What the verdict is worth, in one line a report can carry.

        An APPROVED from one family is a weaker claim than an APPROVED across two, and
        a reader tells them apart here or is misled. Empty when the panel spanned
        families, because then the verdict means what it has always meant.
        """
        if self.single_family_waived and self.carried_by_one_family:
            return ("carried by a single family under the waiver this project declared "
                    "in `rules/review-panel.txt`: correlated reviewers share failure "
                    "modes, so this is a weaker claim than a majority spanning two")
        return ""

    def dissenting(self) -> list[Vote]:
        """The votes on the losing side.

        A minority that loses is still the most interesting thing in the record —
        the kit already says this about Claude and Codex disagreeing, and discarding
        it would throw away the signal a panel exists to produce.
        """
        outcome = self.tally()
        want = outcome is not PanelOutcome.APPROVED
        return [v for v in self.votes if v.counted and v.approves is want]

    def record(self) -> dict:
        """The panel as a record: the outcome, and who produced it.

        "Approved by a panel" is not checkable downstream unless the record says
        which models sat on it.
        """
        outcome = self.tally()
        counted = [v for v in self.votes if v.counted]
        return {
            "slug": self.slug,
            "phase": self.phase,
            "artifact": self.artifact,
            "author": self.author,
            "outcome": outcome.value,
            "approvals": sum(1 for v in self.votes if v.approves),
            "panel_size": PANEL_SIZE,
            "majority": MAJORITY,
            "families": sorted({v.family for v in counted}),
            "approving_families": sorted(self.approving_families),
            "carried_by_one_family": self.carried_by_one_family,
            "votes": [
                {
                    "reviewer": v.reviewer,
                    "model": v.model,
                    "family": v.family,
                    "verdict": v.verdict,
                    "reason": v.reason,
                }
                for v in self.votes
            ],
            # The REASON travels, not just the name. A dissent reduced to a name is a
            # dissent nobody downstream can act on, and "kept in the record" then means
            # kept where nobody looks. An objection that lost a vote is still an
            # objection about the artifact that just advanced.
            "dissent": [
                {"reviewer": v.reviewer, "family": v.family, "reason": v.reason}
                for v in self.dissenting()
            ],
        }


def load(path: Path) -> Panel:
    """Read a panel record written by the reviewers."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return Panel(
        slug=data["slug"],
        phase=data["phase"],
        artifact=data.get("artifact", ""),
        author=data["author"],
        # `assigned` is deliberately NOT read from the record. A document that
        # supplies the list it is checked against proves nothing; the assignment
        # comes from `convene_panel.py`, and the caller sets it.

        votes=[
            Vote(
                reviewer=v["reviewer"],
                model=v["model"],
                verdict=v["verdict"],
                reason=v.get("reason", ""),
            )
            for v in data.get("votes", [])
        ],
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tally a review panel over one artifact.")
    ap.add_argument("--record", type=Path, required=True,
                    help="the panel record: slug, phase, author, votes")
    # `Panel.assigned` is what refuses "the panel that voted is not the panel that was
    # convened", and `convene_panel.py`'s docstring says this module "refuses a record
    # whose voters do not match". Nothing ever SET it: `load()` deliberately does not
    # read it from the record (a document supplying the list it is checked against proves
    # nothing) and `main` had no other source, so `assigned` stayed empty and the check
    # was skipped on every tally the CLI performed. The list comes from the assignment
    # `convene_panel` wrote, which sits beside the record by construction.
    ap.add_argument("--assignment", type=Path, default=None,
                    help="the assignment convene_panel wrote; defaults to the sibling "
                         "<slug>-<phase>.assignment.json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        panel = load(args.record)
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"review_panel: cannot read the panel record — {exc}", file=sys.stderr)
        return 2

    assignment_path = args.assignment or args.record.with_name(
        args.record.name.replace(".json", ".assignment.json"))
    if assignment_path.is_file():
        try:
            panel.assigned = list(
                json.loads(assignment_path.read_text(encoding="utf-8")).get("assigned", []))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"review_panel: the assignment at {assignment_path} could not be read "
                  f"({exc}), so whether the panel that voted is the panel that was "
                  f"convened was NOT checked", file=sys.stderr)
            return 2
    else:
        # Said out loud. A tally that skipped the convening check and printed an outcome
        # is a tally whose strongest guarantee was silently absent.
        print(f"review_panel: no assignment at {assignment_path} — whether the panel "
              f"that voted is the panel that was convened was NOT checked",
              file=sys.stderr)

    try:
        record = panel.record()
    except PanelInvalid as exc:
        # Exit 2, NOT 1. An invalid panel is not a returned document: nothing was
        # judged, and reporting it as a rejection would send the author to rewrite
        # a document nobody found fault with.
        print(f"PANEL DID NOT CONVENE — {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"{record['outcome'].upper()} — {record['approvals']}/{PANEL_SIZE} approvals "
              f"across {', '.join(record['families'])}")
        for v in record["votes"]:
            mark = {"approve": "+", "return": "-", "abstain": "~"}.get(v["verdict"], "?")
            print(f"  {mark} {v['reviewer']} ({v['model']}) — {v['reason'][:90]}")
        if record["dissent"]:
            #: Rendered as objections, not as names. `dissent` carries reviewer, family
            #: and REASON — enriched from a bare name so the objection could travel, and
            #: this printer was left joining strings. It raised `TypeError` on every
            #: panel with a dissenting vote, and `main()` returns 1 for any non-approved
            #: outcome, so the crash exited 1 too: the right number for the wrong reason.
            #: It survived because it fires only on DISAGREEMENT, which is the case a
            #: panel is bought for.
            #: The LABEL has to say which side, because `dissenting()` returns the
            #: losing side and that flips with the outcome: under APPROVED it is the
            #: reviewers who returned, under RETURNED it is the reviewers who approved.
            #: Printing both as "dissent" reported two approvals as objections.
            approved = record["outcome"] == "approved"
            print("  objections, over which this was approved:" if approved
                  else "  approvals, which did not carry:")
            for objection in record["dissent"]:
                print(f"    {objection['reviewer']} ({objection['family']}) "
                      f"— {objection['reason']}")

    return 0 if record["outcome"] == "approved" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Schedule many backlog items through the cycle, one stage each, concurrently.

WHAT IT IS AND WHAT IT IS NOT
-----------------------------
`rules/parallelism-shapes.md` names two shapes. This kit had FAN-OUT — N agents
on the same work from different angles — and no PIPELINE: N items at different
stages at once. `cycle-idea-to-release` chains its seven phases for one item at a
time, so with 22 triaged items in one consumer, every phase sits idle whenever it
is not the current one.

This decides WHICH item may enter WHICH stage and WHEN. It never decides whether
a stage PASSED — the phases keep their own gates, verdicts and thresholds, and a
scheduler that could overrule one would be a way around it rather than a way
through.

ALIGNED AT 91%, AFTER A REFUSAL
-------------------------------
`records/alignment/pipeline-orchestrator-alignment.md`. An alignment judge refused
the first draft and three of its findings shaped this file:

  - The chain is SEVEN stages. The draft drew five, omitting CODE-QUALITY and
    ACCEPTANCE — a pipeline missing stages schedules work that never runs.
  - Backward propagation had no requirement at all, in a brief resting on a rule
    that names it as one of three things the shape needs.
  - The lane budget was asserted as `8`. It is DERIVED here, because 8 lanes with
    one in REVIEW needs 8+7=15 agents against a cap of 10 — the draft deadlocked
    against the very limit it cited.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

#: The chain `cycle-idea-to-release` declares. Seven, not five.
STAGES: tuple[str, ...] = (
    "DISCOVER", "PLAN", "IMPLEMENT", "CODE-QUALITY", "REVIEW", "RELEASE", "ACCEPTANCE",
)

#: How each stage consumes work, in swarm-forge's vocabulary. `batch` stages
#: review several items together because doing five at once costs less than five
#: times one; `task` stages take one because their work is per item.
CONSUMPTION: dict[str, str] = {
    "DISCOVER": "task", "PLAN": "task", "IMPLEMENT": "task",
    "CODE-QUALITY": "batch", "REVIEW": "task", "RELEASE": "task",
    "ACCEPTANCE": "batch",
}

#: REVIEW fans out to 5–7 reviewers, so it holds a lane by itself.
REVIEW_FANOUT = 7

#: One retry, then park — the convention `cycle-idea-to-release.md:80` already
#: uses. There it halts and asks a human; here the item parks AND is surfaced,
#: which is the same halt without pretending an agent answered for the person.
MAX_ATTEMPTS = 2


def lane_budget(cpus: int | None = None, review_fanout: int = REVIEW_FANOUT) -> int:
    """How many lanes may run at once, derived rather than chosen.

    The Workflow tool caps concurrent agents at `min(16, cpus - 2)`. One lane may
    be in REVIEW, which spends `review_fanout` of that cap by itself, so the rest
    is what remains. Floors at 1: a pipeline of one lane is a sequential chain,
    which is worse than this but better than a deadlock.
    """
    cpus = cpus if cpus is not None else (os.cpu_count() or 4)
    cap = min(16, max(1, cpus - 2))
    return max(1, cap - review_fanout)


@dataclass
class Item:
    slug: str
    stage: str = STAGES[0]
    attempts: int = 0
    parked: bool = False
    surfaced: bool = False
    park_reason: str = ""
    worktree: str | None = None
    #: A commit handed back from a later stage. The upstream stage MERGES it and
    #: does not treat it as new work — `back-one` in swarm-forge's terms.
    merge_only: str | None = None

    @property
    def done(self) -> bool:
        return self.stage == "__done__"


@dataclass
class Pipeline:
    items: list[Item]
    lanes: int = field(default_factory=lane_budget)
    running: list[Item] = field(default_factory=list)
    live_worktrees: set[str] = field(default_factory=set)
    released_worktrees: set[str] = field(default_factory=set)

    # ── queries ────────────────────────────────────────────────────────────
    def item(self, slug: str) -> Item:
        return next(i for i in self.items if i.slug == slug)

    def _eligible(self) -> list[Item]:
        busy = {i.slug for i in self.running}
        return [i for i in self.items
                if not i.parked and not i.done and i.slug not in busy]

    # ── scheduling ─────────────────────────────────────────────────────────
    def schedule(self) -> list[Item]:
        """Fill free lanes. Returns what started this call, not everything running."""
        started: list[Item] = []
        for item in self._eligible():
            if len(self.running) >= self.lanes:
                break
            # REVIEW spends the fan-out budget by itself; two at once need 14
            # agents against a cap of 10.
            if item.stage == "REVIEW" and any(r.stage == "REVIEW" for r in self.running):
                continue
            item.worktree = f"wt/{item.slug}-{item.stage.lower()}"
            self.live_worktrees.add(item.worktree)
            self.running.append(item)
            started.append(item)
        return started

    def take_batch(self, stage: str) -> list[Item]:
        """Everything queued at `stage` for a batch stage; one for a task stage."""
        queued = [i for i in self.items
                  if i.stage == stage and not i.parked and not i.done]
        if stage == "REVIEW":
            return queued[:1]
        return queued if CONSUMPTION.get(stage) == "batch" else queued[:1]

    # ── transitions ────────────────────────────────────────────────────────
    def complete(self, slug: str, verdict: str = "PASS") -> None:
        item = self.item(slug)
        self._release(item)
        if verdict != "PASS":
            # The scheduler obeys the gate; it does not reinterpret it.
            self.park(slug, reason=verdict)
            return
        item.attempts = 0
        item.merge_only = None
        nxt = STAGES.index(item.stage) + 1
        item.stage = STAGES[nxt] if nxt < len(STAGES) else "__done__"

    def fail(self, slug: str, reason: str) -> None:
        item = self.item(slug)
        item.attempts += 1
        self._release(item)
        if item.attempts >= MAX_ATTEMPTS:
            self.park(slug, reason=reason, surface=True)

    def park(self, slug: str, reason: str, surface: bool = False) -> None:
        item = self.item(slug)
        item.parked = True
        item.park_reason = reason
        item.surfaced = surface or item.surfaced
        self._release(item)

    def unpark(self, slug: str) -> None:
        """Resumes at the stage it stopped in. Restarting from DISCOVER would
        throw away the wait that parked it."""
        item = self.item(slug)
        item.parked = False
        item.attempts = 0

    def send_back(self, slug: str, to: str, commit: str) -> None:
        """A merge-only hop to an earlier stage: carries a commit, not a task."""
        if STAGES.index(to) >= STAGES.index(self.item(slug).stage):
            raise ValueError(f"{to} is not upstream of {self.item(slug).stage}")
        item = self.item(slug)
        self._release(item)
        item.stage = to
        item.merge_only = commit
        item.parked = False

    def force_stage(self, slug: str, stage: str) -> None:
        """Test and recovery seam: place an item without running the stages."""
        self.item(slug).stage = stage

    # ── worktrees ──────────────────────────────────────────────────────────
    def _release(self, item: Item) -> None:
        if item in self.running:
            self.running.remove(item)
        if item.worktree:
            self.live_worktrees.discard(item.worktree)
            self.released_worktrees.add(item.worktree)
            item.worktree = None

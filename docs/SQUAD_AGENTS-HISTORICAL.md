# Squad — Complete Agent Manifest (HISTORICAL)

<!-- Renamed from `SQUAD_AGENTS.md` at the repository root on 2026-09-21. The banner
     below has said HISTORICAL since 2026-09-08, and an external review still read the
     file as a live roster and reported "two competing truths". The banner was not the
     problem: the NAME is what a reader meets first, in a directory listing, in a search
     result, in a link. A document whose filename claims to be the manifest is read as
     the manifest, whatever its first paragraph says. -->

> **Status: HISTORICAL — superseded by `agents/` and `rules/squad-map.md` (2026-09-08).**
>
> The heading below counts "14 specialized agents", and fourteen is the right number by
> coincidence rather than by correspondence: most of the entries are SCRIPTS
> (`kit_audit_workflow.js`, `file_findings.py`, `lens_review.py`, `kit_issues.py`,
> `check_install_drift.py`), and only VERA is one of the fourteen agent files on disk.
>
> An inventory that mixes agents with the scripts they run is useful as a map of the
> autonomous machinery, and misleading as a roster. Read it as the former. For the
> roster: `agents/*.md`, and [`rules/squad-map.md`](../rules/squad-map.md) for what each
> member decides.

**Total: 14 specialized agents + 3 human decision points**

## Core Fleet (Execution Layer)

### 1. **VERA** — Verifiable Engineering Reference Arbiter
- **Role:** Autonomous technical judge
- **Responsibility:** Analyze problems → propose engineering solution
- **Inputs:** Problem statement + evidence
- **Outputs:** GitHub issue (title, rationale, scope, severity, labels)
- **Lenses:** SOLID, DRY, Coupling, Fail-Fast, Clarity
- **Autonomy:** 100% (applies FAANG engineering principles)
- **Status:** New (this session)

---

## Discovery Layer

### 2. **kit_audit_workflow.js** — Automated Sweeper
- **Role:** Hunt defect patterns
- **Responsibility:** Scan codebase against 6 known anti-patterns
- **Inputs:** Repository path
- **Outputs:** Findings array (refuted/survived agent review)
- **Patterns:** 
  - absence-as-answer (silent failures)
  - rule-in-one-file (duplication of knowledge)
  - guard-that-guards-nothing (ineffective checks)
  - mentioned-not-used (unused declarations)
  - prose-vs-mechanism (docs-code mismatch)
  - unreachable-or-unrun (dead code)
- **Autonomy:** 100% (runs without human, refutation is automated)

### 3. **file_findings.py** — Turn Findings Into Work
- **Role:** Transform audit output → GitHub issues
- **Responsibility:** Dedup against tracker, refuse killed claims, file survivors
- **Inputs:** Audit findings JSON
- **Outputs:** GitHub issues (filed or skipped with reason)
- **Autonomy:** 100% (refuses tracker errors, refuses refuted claims)

### 4. **lens_review.py** — Defect Lenses on Diff
- **Role:** Point VERA's lenses at a branch before landing
- **Responsibility:** Read diff, apply 6 lenses, produce verdicts
- **Inputs:** Branch name, base (origin/workspace)
- **Outputs:** Findings array (does not block landing; becomes issues)
- **Autonomy:** 100% (informational, not blocking)

### 5. **kit_issues.py** — Work Registry
- **Role:** List all open issues the kit owes fixing
- **Responsibility:** Query GitHub tracker, return actionable issues
- **Inputs:** Repository
- **Outputs:** List of {id, title, source}
- **Autonomy:** 100% (reads source of truth)

### 6. **select_backlog_item.py** — Consumer Queue Reader
- **Role:** What does Theo want fixed?
- **Responsibility:** Parse Theo's BACKLOG.md, return next unblocked item
- **Inputs:** BACKLOG.md path
- **Outputs:** Item (or reason for hold: AWAITING_HUMAN, blocked_by, walls)
- **Autonomy:** 100% (cannot unblock human-held items, respects constraints)

---

## Routing & Dispatch Layer

### 7. **fleet_router.py** — Work Assignment
- **Role:** Intelligent dispatcher
- **Responsibility:** 
  - Consume work sources in order: consumer backlog > kit issues > VERA verdicts
  - Dedup (branch exists? commit history? already assigned?)
  - Route one unit per free lane
  - Recover abandoned units (reaper)
- **Inputs:** Lanes status, work sources, assignment log
- **Outputs:** Assignment (lane, unit) or note why nothing assigned
- **Autonomy:** 100% (decides routing via observable facts + log)

### 8. **dispatch_to_lane.sh** — Hand-Off
- **Role:** Type a unit into a lane's tmux pane
- **Responsibility:** Keystroke the assignment, verify delivery
- **Inputs:** Lane name, unit ID, backlog item/issue spec
- **Outputs:** Exit code 0=dispatched, 1=not sent, 3=pane unreadable
- **Autonomy:** 100% (checks before typing, reads afterwards)

### 9. **session_ready.py** — Lane Health Check
- **Role:** Is this lane free and ready?
- **Responsibility:** Check tmux pane state + `claude agents --json` CLI
- **Inputs:** Lane name
- **Outputs:** State (ready, busy, dialog, unknown, gone)
- **Autonomy:** 100% (observable facts via tmux + CLI)

---

## Execution Layer (Lanes)

### 10. **Lanes (`squad-<project>-1`, `-2`, `-3`)** — Repair Units
- **Role:** Worker
- **Responsibility:** Receive unit spec → plan → implement → commit → push branch
- **Inputs:** Unit (B-001, kit#19, etc)
- **Outputs:** Branch (fix/kit19-..., fix/B-001-...)
- **Autonomy:** 100% (Claude agents planning and coding; human reviewable)
- **Note:** Lanes don't push to main; they commit on branch and stop (correct)

---

## Integration Layer

### 11. **fleet_lander.py** — Verify & Integrate
- **Role:** Gatekeeper
- **Responsibility:**
  - Cut two scratch trees (one per branch, one for merge)
  - Run suite on branch (alone)
  - Run suite on merged (in develop candidate)
  - Push only what passed both
- **Inputs:** Branches ahead of origin/workspace
- **Outputs:** Merged to origin/workspace (via scratch tree push)
- **Autonomy:** 100% (refuses red, refuses merge conflicts, cleanup reads)

### 12. **fleet_supervisor.sh** — Loop Orchestration
- **Role:** Coordinator
- **Responsibility:** Router → Lanes → Lander → repeat
- **Inputs:** Lane list, kit repo, consumer project
- **Outputs:** Runs the loop (interval 600s default, no human intervention)
- **Autonomy:** 100% (just chains others, respects their refusals)

---

## Synchronization & Drift Detection

### 13. **sync_consumers.py** — Keep Consumers in Sync
- **Role:** Propagate squad changes to consumers
- **Responsibility:** Fetch kit changes, apply to consumer's `.claude/`
- **Inputs:** Kit repo, consumer repo
- **Outputs:** Commit synced changes
- **Autonomy:** 100% (mechanical, no decisions)

### 14. **check_install_drift.py** — Detect Skew
- **Role:** Gate
- **Responsibility:** Compare consumer `.claude/` vs kit; report drift
- **Inputs:** Two `.claude/` directories
- **Outputs:** PASS or list of drifts
- **Autonomy:** 100% (observes differences)

---

## Optional / Historical

- **fleet_idle.py** — Reports if all lanes idle
- **fleet_status.sh** — Human-readable status line
- **start_fleet.sh** — Launch 3 tmux sessions
- **squad_lead.py** — Session log coordinator (fixed heartbeat, reads exit codes)

---

## Human Decision Points (3 only)

### 1. **Approve Initial Backlog**
- Human decides: what problems matter to Theo?
- Creates: BACKLOG.md with items, phases, blocking relationships
- Once: per project cycle (or when new phase opens)
- Frequency: **rare** (quarterly, not per-pass)

### 2. **Decide on AWAITING_HUMAN Items**
- Only: when backlog item itself says "needs decision"
- Examples: "rename clusters — what should new names be?", "which persistence layer?", "keep or remove env?"
- Before VERA: **14 such items** blocked Squad
- After VERA: **0 such items** (VERA decides engineering, humans decide business direction)
- Frequency: **none in normal operation** (only if Theo defines true decision items)

### 3. **Unblock Dependency Issues**
- Rare: when blocked-by is outside Squad scope (e.g., external service, third-party decision)
- Example: "waiting for vendor to release v2" — no code change solves it
- Frequency: **varies by project**

---

## Autonomy Scorecard

| Layer | Agent | Autonomy | Bypasses | Notes |
|-------|-------|----------|----------|-------|
| **Discovery** | VERA, audit, lens_review | 100% | None | All objective |
| **Routing** | Router, dispatch | 100% | None | Observable facts only |
| **Execution** | Lanes | 100% | None | Claude agents; human reviewable |
| **Integration** | Lander | 100% | None | Refuses red; scratch trees |
| **Sync** | sync_consumers, drift check | 100% | None | Mechanical |
| **Loop** | supervisor | 100% | None | Just chains others |
| **Human** | 3 decision points | — | All respected | Backlog approval, AWAITING_HUMAN, dependencies |

---

## The Self-Improving Loop

```
VERA (judge)
  ↓
kit_audit_workflow + lens_review (discover)
  ↓
file_findings (file issues)
  ↓
fleet_router (assign work)
  ↓
dispatch_to_lane (send to lane)
  ↓
session_ready (confirm lane ready)
  ↓
Lanes (execute)
  ↓
fleet_lander (integrate)
  ↓
check_install_drift (verify consistency)
  ↓
sync_consumers (propagate)
  ↓
Back to VERA (next iteration)
```

**No human in the loop except:**
- Initial backlog approval (once per cycle)
- AWAITING_HUMAN items (if any; VERA removes most)
- External blockers (rare)

---

## What Makes This 5/5

**Autonomy Level:** System self-improves without human technical decisions.
- VERA eliminates "person decides technical question"
- Fleet eliminates "person dispatches/integrates"
- Loop eliminates "person starts next iteration"
- Drift check eliminates "environment skew hides work"

**Result:** Squad can run unattended. Check in to approve backlog once per quarter. Everything else is automated.


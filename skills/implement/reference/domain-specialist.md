# Consulting the domain specialist

Protocol for the second opinion `/implement` consults during the halt-loop. Linked
from `SKILL.md § Step 2.5`.

## What replaced what, and why

This used to be **SEPA** — a "Specialist Engineer Per-plan Agent" that `/implement`
GENERATED at startup: an agent definition written to `agents/implement-{slug}-{date}/sepa.md`
plus a paired knowledge skill written to `skills/implement-{slug}-sepa-knowledge/SKILL.md`,
both composed from the plan, its ADRs, the edge-case review and the audits.

It was removed for four reasons, and each is a fact about where it wrote or what it
knew:

1. **It wrote into `agents/`, which belongs to the project.** That directory holds the
   domain specialists a project derives from its own disk. A skill manufacturing files
   there mixes generated artifacts with the one map a consumer maintains by hand.

2. **It wrote into `skills/`, which `install.sh` deletes.** The installer does
   `rm -rf <target>/.claude/skills/` and copies the source over it. Every generated
   knowledge skill was destroyed by the next update, and `patch_install.sh` carried a
   standing workaround to preserve them — a mechanism existing to protect files that
   should not have been there.

3. **It was specialist about the PLAN, never about the CODE.** Every byte of its
   context came from documents this cycle already produced. It could not know that a
   root `go build ./...` covers almost nothing in a multi-module repo, or which false
   positives that domain generates, because nobody ever measured any of that into it.
   That is precisely the knowledge a second opinion needs to be worth its cost.

4. **Its own contract did not know it existed.** `SKILL.md` called Step 2.5 a
   MANDATORY step "per `cycle-implement.md`", and `cycle-implement.md` contained no
   mention of SEPA at all. A mandatory step justified by a contract that does not
   contain it is the failure this kit exists to catch, pointed inward.

**The project's domain specialists already are what SEPA was pretending to be.** They
carry the repos verified on disk, the build commands that were actually checked, the
invariants of the domain, and the shape a real finding takes there
(`agents/README.md`). So the fix is not a better generator — it is to stop
generating and route.

## Resolving the specialist

Mechanical, from the field the item already declares. Same call `daedalus-tech-lead`
makes, and the same refusal.

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)
python3 "$ECO/mechanisms/cycle/route_domain.py" <repo-or-item-file> --json
```

| Exit | Meaning | What `/implement` does |
|---|---|---|
| `0` | the domain resolves to a specialist on disk | consult it, per the protocol below |
| `1` | the repo is in no domain | **HALT.** Gate G1 should have refused this upstream; reaching `/implement` unrouted means the registry and the plan disagree |
| `2` | the routing table could not be read or parsed | **HALT.** Nothing can be routed, and guessing is what the table exists to prevent |
| `3` | `BROKEN ROUTE` — the domain names a specialist nobody wrote | **HALT.** Do NOT stand in for them |

**Exit 3 is the one that tests the protocol.** Answering for a domain whose invariants
nobody wrote means asserting facts that were never checked — the identical rule
`agents/README.md` states for the Tech Lead. The halt is reported so the missing
specialist becomes work, rather than being papered over by a generic agent that would
give an answer anyway.

### When there is no item to route from

A plan citing no `B-NNN` — the legitimate ad-hoc fix that
`skills/_kit-rules/alignment-threshold.md § The bypass that remains` already describes —
has no `repo:` field to route on. **Skip the consultation and record the skip** in the
implementation contract under "Pre-condition audit", naming the reason.

Skipping is honest here and inventing a consultant is not: with no declared domain,
any specialist chosen would be chosen by resemblance.

## Invoking it

The specialist file carries `name: {domain}` in its frontmatter, so it resolves as a
subagent type. Claude Code loads its agent registry at SESSION START, and a project
that derived its specialists mid-session will not have them registered yet — so two
paths, in priority order:

1. **Primary:** `Agent(subagent_type='{domain}', prompt=<question>, description='specialist {phase} — {T-ID}')`.
2. **Fallback:** `Agent(subagent_type='general-purpose', prompt='Read {agent_path} for your role, the repos you cover, their invariants and their build commands. <question>', description='specialist {phase} — {T-ID}')`.

If the primary path returns "Agent type not found", switch to the fallback for the
rest of the cycle. `route_domain.py` reported the path; the file on disk is the source
of truth either way.

## The three consultations

Per halt-loop iteration, unchanged in cadence from what SEPA did — the cadence was
never the problem:

1. **Before RED** — recap what the plan declares for this task; surface the domain's
   gotchas and the false positives it generates.
2. **After GREEN, before REFACTOR** — spot SOLID / Clean Code violations and missed
   cross-references in the new code.
3. **Before COMMIT** — audit the staged diff against the DoD checkboxes and against
   the domain's blast-radius heuristics.

Persist each response to
`records/implementations/{slug}/specialist-consultations/iteration-{N}-{phase}.md`,
where `{phase}` ∈ `pre-red`, `post-green`, `pre-commit`. These are **log outputs** and
they stay under `records/` — `agents/` holds definitions, never invocation logs.

## Authority and boundaries (locked)

- **READ-ONLY.** Never writes code, ADRs or configs.
- **Never commits**, and never modifies the plan.
- Outputs structured advice; the main session keeps the final decision.
- A `[CRITICAL]` finding recommends HALT and does not block on its own — Unbreakable
  Rule 1 puts the 95%-confidence burden on the actor, not on the advisor.
- **Inside its domain, it is not overruled.** Believing it is wrong is a finding to
  record, not a verdict to substitute — the same line `daedalus-tech-lead` holds.

## What this consultation is not

It is **not** the phase-boundary gate. `scripts/mini_review.py` runs at every
`## Phase N` boundary, is deterministic, and `check_phase_review.py` proves it ran.
This consultation is judgement layered on top of that gate; it never replaces it, and
a green consultation says nothing about whether the gate passed.

# Cycle: ACCEPTANCE (end-user validation of the released delivery)
<!-- rule-id: SQ-CYC-02 -->

Source of Truth for the phase that runs **after** `cycle-release` and answers the only question the rest of the pipeline never asks: does the thing that shipped actually work for the person it was built for?

## Purpose

Every gate before this one grades the delivery against *the project's own artifacts*: tests pass, coverage holds, the reviewer approved, the tag cut. All of them can be green while the released product is broken for its user — a mis-wired env var in the deployed build, a proxy that buffers the stream, a login that 500s only against the real identity provider. None of those are visible to a test suite running on a build agent.

This cycle exercises the **released** delivery the way a user meets it, and turns the result into the gate on the milestone's `[x]`.

That placement is the whole design. Before this cycle existed, `cycle-release` flipped the ROADMAP checkbox itself, at tag-cut — so `[x]` meant *"we shipped it"*. It now means *"we shipped it and watched it work."* The flip moved here (`cycle-release § 7.5` → this cycle's `flip` phase) precisely so the claim and the evidence cannot drift apart.

The cycle produces an **acceptance record** per milestone, and a **verdict**.

**Who reads that verdict, stated exactly.** Until 2026-09-21 this line said `cycle-maintenance` consumed it, and no code did: `advance_items.py` selects on `event.get("verdict") == "RELEASED"` and nothing outside this slice reads `ACCEPTED` at all. The verdict's one mechanical consumer is now `flip_milestone_checkbox.py --verdict`, which refuses to close a milestone on any token but the two green ones. Everything else that reads it — the board, an auditor asking whether M3 was ever used before it was called done — reads the record, and reads it as a person.

A verdict with no consumer is a computed sentence. Saying which one it has is the difference between a gate and a note.

## The ROADMAP.md contract

This cycle reads `ROADMAP.md` and is the only cycle that writes to it. Three facts about that file
are load-bearing, and none of them were written down before:

**1. It is hand-authored. No skill generates it.** The skill that used to — `/roadmap-init` — was
retired together with the cycle-roadmap rule (unbackticked on purpose: it is history, not a
reference) when `cycle-maintenance` replaced it. `/backlog-init`
is *not* its successor: it creates `BACKLOG.md`, a different registry on a different axis
(`B-NNN` maintenance items, not `M<N>` milestones). Anything claiming otherwise is a stale redirect
from that retirement; treat it as a bug and fix it.

**2. The header shape is normative, and it is `###`.** THREE scripts parse it, and until
2026-09-21 the sentence here said they all agreed. They did not — and the table under it listed
two of the three:

| Script | Slice | Role |
|---|---|---|
| `extract_acceptance_criteria.py` | this cycle | reads the Definition-of-done bullets |
| `select_next_milestone.py` | `idea-to-release` | picks the next milestone to work |
| `flip_milestone_checkbox.py` | housed in `release`, invoked here | performs the flip |

They share one reader now — [`squad/roadmap.py`](../squad/roadmap.py) — so the shape below is the
shape all three accept, by construction rather than by three regexes agreeing:

```markdown
### M<N> — [ ] Milestone name

**Objective:** one line.

**Dependencies:** M<K>        (or `none.`)

**Definition of done (all must hold):**
- [ ] one user-visible promise per bullet, exercisable against the released delivery
```

**Two details of that block used to be written here differently from anything that could read
them**, and copying the rule produced a milestone that could never be accepted. Measured on the
rule's own former example:

```
extract_acceptance_criteria  ->  NOT_VALIDATED, "no `- [ ]` bullets"
select_next_milestone        ->  {"dod": [], "depends_on": []}
```

- **The DoD bullets carry a checkbox.** `- [ ]`, not a bare `-`. The checkbox is what separates a
  promise from the prose around it, and every fixture in this repository has always had one.
- **The dependency label is `**Dependencies:**`.** This rule taught `**Depends on:**` for months,
  so the shared reader accepts BOTH — not out of tolerance for two spellings, but because this
  mismatch failed in SILENCE. The bullet mismatch exits 1 and names what is missing; a dependency
  returning `[]` is indistinguishable from a milestone that declared none, so a prerequisite
  nobody delivered read as no prerequisite at all. Write the canonical one; the other is read
  rather than lost.

**The checkbox has three states, and `[-]` means CANCELLED.** That meaning existed in exactly one
script and was unreadable to the other two — to them a cancelled milestone was not cancelled, it
was ABSENT. `extract` answered "Milestones present: (none)" over a file holding one, and the flip
script skipped it as not-found. A state one reader can spell and two cannot is worse than a state
nobody supports, because the two that cannot each invent their own story about the silence. All
three read it now, and each refuses it by name.

A `##` header still does not match — but the flip script no longer treats a non-match as benign.
It printed `WARN … not found — skipping flip` and returned **0** until 2026-09-21, so a caller
running `flip || exit 1` was told the flip had happened while the milestone stayed open. It exits
1 now and names the shape it expected.

**3. Two registries, one pipeline.** `BACKLOG.md`/`B-NNN` answers *what should we look at next*;
`ROADMAP.md`/`M<N>` answers *what did we promise a user*. An item can exist in one, the other, or
both. Only a milestone has a checkbox, so only a milestone reaches this cycle — a `B-NNN` released
without a milestone ends at `RELEASED`, which is correct and not a gap.


## Pre-conditions

- `cycle-release` emitted `RELEASED` for the milestone — tag cut, GitHub release published.
- The released delivery is reachable: a deployed URL, an installed binary, a published package, a running service, or — for internal packages — a build produced from the released tag in a clean checkout (see § Target kinds).
- The milestone declares `**Definition of done (all must hold):**` bullets in `ROADMAP.md`. These are the acceptance criteria — this cycle does not invent its own.
- The milestone's checkbox is still `[ ]`.

Do NOT trigger when:

- `cycle-release` returned `PR_OPEN_AWAITING_APPROVAL` or `BLOCKED` — there is nothing released to validate.
- The milestone's checkbox is already `[x]` — either a previous acceptance run flipped it, or someone flipped it by hand (an anti-pattern; investigate before re-running).
- The delivery cannot be reached. Emit `NOT_VALIDATED` and say so; do not substitute a local build for the released artifact, which is the one class of failure this cycle exists to catch.

## Chain

```
/acceptance M<N>
     ↓ read ROADMAP.md § M<N>; confirm checkbox is [ ] and cycle-release emitted RELEASED
     ↓ extract_acceptance_criteria.py --milestone M<N>   → criteria.json (from the milestone DoD)
     ↓ resolve the target and its instrument (see § Target kinds)
     ↓
     ↓ FOR EACH criterion:
     ↓   exercise it against the RELEASED delivery, as an end user would
     ↓   capture evidence: screenshot / console / network / stdout / response body
     ↓   record status ∈ passed | failed | blocked | not_exercised
     ↓
     ↓ record every defect observed on the way, with severity + filed issue
     ↓ write .squad/records/acceptance/{milestone}-{date}.md + evidence/
     ↓ compute_acceptance_verdict.py --criteria criteria.json --evidence evidence.json
     ↓
     ↓ ACCEPTED | ACCEPTED_WITH_CAVEATS → flip_milestone_checkbox.py  [ ] → [x]
     ↓ REJECTED                         → checkbox stays [ ]; open hotfix; back to cycle-plan
     ↓ NOT_VALIDATED                    → checkbox stays [ ]; state what could not be exercised
```

## Target kinds

The instrument changes with the delivery; the rigor does not. Exercising a *proxy* for the release (a local build, a mocked backend, a staging clone) is not this cycle — it is the thing this cycle exists to replace.

| Delivery | Instrument | What "as an end user" means |
|---|---|---|
| Web UI | `chrome-devtools` MCP | Navigate the real deployed URL, click through the journey, read console + network for errors the UI swallows |
| Native desktop app | `cua-driver` skill | Drive the installed build through its accessibility tree |
| CLI | `Bash` | Install the published artifact and run the documented commands from a clean directory |
| Library / SDK | `Bash` | Consume the published package in a throwaway project, following the README verbatim |
| HTTP API / service | `Bash` | Call the deployed endpoints with real payloads, including the documented error cases |
| **Internal / private package** (monorepo, never published to a public registry) | `Bash` | Build from the **released tag** in a clean checkout, then consume it the way its real consumer does — import the built package, run its binary, start its service. Never the dirty working tree. |

**On "released" when nothing is published.** Most internal work never reaches a public registry or a public URL, and reading this cycle as "only validate published artifacts" would make it unreachable for exactly the projects that need it most. The distinction that matters is not *public vs private* — it is **the artifact vs the working tree**.

A working tree carries uncommitted edits, local config, and a dev server that behaves nothing like the built output. A build from the released tag carries none of that, and reproduces what the consumer receives. So for an internal package the released delivery is: check out the tag (or a clean worktree at that tag), build, and consume the result. That is a real acceptance run.

What is still NOT acceptance: `npm run dev` against your working tree, a mocked backend, or a staging clone with different configuration.

When a criterion cannot be exercised with any available instrument, its status is `not_exercised` — never `passed`.

## Phase contracts

| Phase | Input | Output | Hard gate |
|---|---|---|---|
| extract | `ROADMAP.md` § M\<N\> | `criteria.json` with ≥ 1 criterion | milestone declares a non-empty `**Definition of done:**`; otherwise `NOT_VALIDATED` |
| resolve-target | release artifact | target kind + reachable address | the address points at the RELEASED artifact, not a local or staging build |
| exercise | criteria + target | one result per criterion, each with evidence | every criterion has a recorded status; `passed` requires at least one evidence artifact |
| record | results + defects | `.squad/records/acceptance/{milestone}-{date}.md` + `evidence/` | every cited evidence path resolves to a readable, non-empty file — checked by `compute_acceptance_verdict.py` |
| verdict | `criteria.json` + `evidence.json` | verdict token | computed by `compute_acceptance_verdict.py`; never asserted by the agent |
| flip | verdict ∈ {`ACCEPTED`, `ACCEPTED_WITH_CAVEATS`} | `ROADMAP.md` `[ ]` → `[x]` + roadmap-runs updated | single-flip invariant (§ Hard gates, below); no flip on `REJECTED` or `NOT_VALIDATED` |

## Verdicts

- `ACCEPTED` — every criterion was exercised against the released delivery and evidenced; no defects. Checkbox flips.
- `ACCEPTED_WITH_CAVEATS` — every criterion passed with evidence, but non-blocking defects were observed. Each defect is filed as an issue before the flip. Checkbox flips.
- `REJECTED` — at least one criterion failed in the live system, or a blocker-severity defect was observed. Checkbox stays `[ ]`. The delivery is already public: open the hotfix path immediately, then re-enter at `cycle-plan`.
- `NOT_VALIDATED` — the run could not establish either outcome: a criterion was never exercised, the target was unreachable, evidence was missing, or the milestone declared no Definition of done. Checkbox stays `[ ]`.
- `AWAITING_HUMAN` — the phase ran and stopped at a gate only a person opens (a T3 boundary call, an alignment sign-off, an approval, a dependency in another repository). **Emit it.** The work happened; without the event it leaves no trace, and every reader — the board, the drift checker, the selector, the watchdog — sees an item that was never touched.

`NOT_VALIDATED` is deliberately distinct from `REJECTED`. "We could not check" and "we checked and it is broken" are different facts, and a cycle that collapses them starts reporting untested work as tested.

## Hard gates

- **A `passed` without evidence is not a pass, and a cited path that does not resolve is not evidence.** `compute_acceptance_verdict.py` refuses both as `NOT_VALIDATED`. This is the gate the whole cycle rests on: with the human sign-off deliberately out of scope, recorded evidence is the only thing standing between a real validation and a confident sentence.

  **The second half was prose until 2026-09-21.** The phase-contract table gated the `record` phase on "evidence files exist at the cited paths" and the skill repeated "the paths must resolve", while the check asked only whether the list held a non-empty STRING:

  ```
  evidence=[""]          ->  NOT_VALIDATED
  evidence=["e/x.png"]   ->  ACCEPTED        <- no such file
  ```

  Paths now resolve against the evidence record's own directory (`--evidence-root` to override), and a zero-byte file counts as unresolved — a failed screen capture leaves one, and it reads downstream as a successful capture. An evidence root that is not a directory is `NOT_VALIDATED` rather than an unchecked pass: an inability to verify is not a verification.
- **The verdict is computed, never asserted.** The agent that ran the journeys does not get to name the outcome — it records results, and `compute_acceptance_verdict.py` derives the verdict. Reporting a verdict the script did not emit is a review BLOCKER — _(not mechanized: debt since 2026-08-27 — nothing compares the token the agent wrote in the report against the one the script emitted; the gate is the script's output existing, not the report agreeing with it)_
- **No flip without a green verdict.** `[x]` claims a user-visible promise was met; only `ACCEPTED` / `ACCEPTED_WITH_CAVEATS` may flip it. `flip_milestone_checkbox.py --verdict` is required and checked — it refuses any other token and names the two that pass.

  **This closed a regression that had been open since 2026-08-31.** A retired session-binding skill used to refuse a session release on a non-green token, which caught a wrong flip after the fact; it was cut, and for three weeks the gate was honoured by discipline at both ends. The flip script had never read the verdict — `grep -c verdict` returned 0 — so nothing between "the script computed NOT_VALIDATED" and "the checkbox is now `[x]`" would have objected. The token now travels from the script that computed it into the script that acts on it, which is also what gives this cycle's verdict a mechanical consumer at all.

- **Single-flip invariant (SoT).** At most ONE `ROADMAP.md` checkbox flips per accepted milestone. Implemented once, in `skills/release/scripts/flip_milestone_checkbox.py` — the script stayed in the release slice when the flip moved here, because one implementation of an invariant is the invariant.

  This clause used to point at the Hard gates section of the retired cycle-roadmap rule (unbackticked here on purpose: it is history, not a reference). That file was replaced by `cycle-maintenance` and the section stopped existing, while `cycle-release` and six scripts kept citing it — a normative anchor aimed at nothing. It lives here now because this is the cycle that performs the flip.
- **The target is the released artifact.** Validating a local build, a staging clone, or a mock reproduces exactly the blind spot this cycle exists to remove. The project declares how its published delivery is reached in `rules/acceptance-target.txt` — _(not mechanized: regression since 2026-08-31 — a retired skill refused to arm a goal until that file was filled, which forced the declaration to exist before a run. Nothing enforces it now, and whether what was exercised IS the released artifact was always read from the evidence by a human)_
- **Criteria come from the milestone.** `extract_acceptance_criteria.py` reads them from `ROADMAP.md` before the run. A criterion invented or edited after seeing the result is grading a moved target — and per Unbreakable Rule 4's spirit on evidence, is fabrication.
- **Every caveat is filed.** `ACCEPTED_WITH_CAVEATS` without an issue per defect turns a known problem into an unowned one — _(not mechanized: debt since 2026-08-27 — no script confronts the caveat list with a tracker; `cycle-review`'s followup gate does the equivalent for HIGH findings and is the shape this one would take)_
- **The verdict is the milestone's only closing evidence.** `compute_acceptance_verdict.py` computes it from what was exercised; the agent that ran the journeys never names it. That separation is the mechanism, and it is unchanged — what a retired session-binding skill added was a second reader of the same line, not a second source of it.

## Anti-patterns

- **Validating the build instead of the release.** Running the local test suite again is not acceptance; it is the check that already passed three phases ago.
- **Marking a criterion `passed` because the code looks right.** Reading the implementation is not exercising it. If the journey was not driven, the status is `not_exercised`.
- **Downgrading a failure to a caveat to let the checkbox flip.** If a Definition-of-done bullet does not hold, the milestone is not done — a caveat is for defects *outside* the declared criteria.
- **Re-running until it passes without recording the earlier failures.** Flakiness in the live system is itself a finding; silently retrying hides it.
- **Treating `NOT_VALIDATED` as a soft pass.** It blocks the flip exactly as `REJECTED` does. The milestone stays open.
- **Flipping the checkbox by hand after a `REJECTED`.** This bypasses the audit trail and re-creates the drift the cycle was built to close.

## Output

- `.squad/records/acceptance/{milestone-id}-{YYYY-MM-DD}.md` — the acceptance record: target, criteria, per-criterion result, evidence paths, defects, computed verdict.

  The record MUST carry the verdict in its frontmatter as `verdict: <TOKEN>`. This is not cosmetic: it is the line any reader — human or script — resolves to decide whether the milestone closed. A record whose verdict lives only in prose is invisible to every one of them, and the milestone will read as never accepted.

  ```yaml
  ---
  milestone_id: M2
  verdict: ACCEPTED        # or ACCEPTED_WITH_CAVEATS | REJECTED | NOT_VALIDATED
  target: https://app.example.com
  date: YYYY-MM-DD
  ---
  ```
- `.squad/records/acceptance/evidence/` — screenshots, console dumps, network logs, command transcripts cited by the record.
- `.squad/records/roadmap-runs/{milestone-id}-{date}.md` — updated with the acceptance verdict when the flip happens.

The record is the artifact an auditor reads to answer "was M3 ever actually used before we called it done?" — the same question `honesty-gate` asks about production claims, one milestone at a time.

## Cross-references

- Schema for cycle rules: `rules/cycle-rule-schema.md`
- Skill implementing this cycle: `skills/acceptance/SKILL.md`
- Upstream cycle (must have emitted `RELEASED`): `rules/cycle-release.md`
- Macro loop this cycle sits inside (it consumes `RELEASED`, not this cycle's verdict — see § Purpose): `rules/cycle-maintenance.md`
- Checkbox-flip script reused from the release slice: `skills/release/scripts/flip_milestone_checkbox.py`
- Sibling honesty gate over sustained use (consumes acceptance evidence): `rules/honesty-gate-golden-rule.md`
- Re-entry point on `REJECTED`: `rules/cycle-plan.md`
- Conventions: `rules/testing.md`, `rules/error-handling.md`, `rules/git-safety.md`

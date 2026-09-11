# The autonomy envelope — what the system decides, and what it never touches

A maintenance cycle that runs unattended reaches decisions. This file says which of
them belong to the system, which belong to a person, and — for the ones that belong to
the system — how they are decided, so that the same situation gets the same answer
next month.

**It is a policy, and a project adopts it by choosing to.** The default below is the
one that makes an unattended cycle possible at all. A project that wants a person in
the loop for more than the backlog changes this file; nothing else in the kit needs to
know.

## Why a written envelope, and not case-by-case judgement

Without one, an autonomous system has two failure modes and no third option.

**It stops.** Every non-trivial call is treated as a person's, so the queue waits for
someone. When that someone is watching, this is correct and cheap. When they are not,
work that was measured, understood and ready evaporates while the item sits at a menu.

**Or it improvises.** Each call is made on the merits of the moment. Every decision is
defensible alone and the set is incoherent: two comparable items get opposite
treatment, and nobody can say which rule was applied, because there was none. The
damage is invisible at the time and shows up later as a system nobody can predict.

A written envelope is the third option. Decisions are made, and they are made the same
way twice, and the rule that produced each one can be read back.

## What the human owns

**The backlog.** What is worth doing and why: items entering with evidence and a
definition of done. That is where a person's judgement is irreplaceable, because it is
the only judgement that is about the product rather than about the work.

**And the product it serves.** `cycle-brainstorm` is the one phase a person attends, and
its sign-off is the agreement everything downstream executes against. No judge may sign
it (`cycle-brainstorm.md § Why the judge may not sign this one`).

**And this file.** Changing the envelope is a human act. The system operates inside it
and may report that a case is missing from it, but never widens it on its own.

Everything else in the chain — DISCOVER through ACCEPTANCE — is the system's, without
exception and without a waiting state addressed to a person. See § *The autonomous span*
below for the one door that still returns.

## The autonomous span — DISCOVER through ACCEPTANCE

**Decided 2026-09-08.** Between the moment an item leaves the registry to be measured
and the moment its delivery is accepted, **nothing waits for a person.** Not a gate that
failed twice, not a loop that stopped improving, not a version the CHANGELOG cannot
level, not a dependency with a CVE. Every one of those was written as *escalate to the
human*, and each was a place the queue could stop for as long as nobody happened to
look.

The span does not become autonomous by removing the stops. A loop that cannot finish
must still stop; a gate that fails must still hold. What changes is **who the stop is
addressed to**:

| Before | Now |
|---|---|
| the phase halts and waits for a person | the phase halts, **returns the item to the registry** with the impediment written on it, and the queue takes the next item |

That is not new doctrine — it is § *Nothing here fits* applied everywhere the phase
rules had written their own exception. One item waiting is not the backlog waiting.

### What replaces the human reviewer, and what it does not replace

Closing the span removed the person from every gate between DISCOVER and ACCEPTANCE. In
two of those phases the thing the person was doing was **judgement over a document**, and
that does not disappear because nobody is coming — it has to be performed by somebody
else, under a rule that says who.

That is [`rules/review-panel.txt`](review-panel.txt): DISCOVER and PLAN are each judged by
three reviewers, **2 of 3** advance the document, and at least one reviewer must come from
a recognised model family outside the one the kit runs on. Below the majority the document
returns as `NEEDS_REVISION`.

**Correlated approval is not independent approval.** Three reviewers from one family are
three chances to make the same mistake: a plausible fabrication that survives one tends to
survive its siblings. A panel that cannot tell those apart is a signature ceremony with
extra latency — which is what `alignment_judge.py` was before this existed, since it takes
its verdict on the command line and stamps it.

What a panel does NOT replace is the deterministic scoring beneath it. `discover-confidence`
and `plan-confidence` run first, cost nothing, and have **zero error correlation** with the
generator by construction — a property no second model can claim. The panel answers only
what a script cannot: whether evidence that resolves actually supports the conclusion.

### The one door that still returns to a person

An item goes back to a person when — and only when — its impediment is one of the
**retained classes** of [`decision-delegation.txt`](decision-delegation.txt):

| Class | What is missing | Why authority does not move it |
|---|---|---|
| `access` | a machine, credential or repository the process lacks | delegating *"provision the host"* to a process without host access does not provision the host |
| `elapsed` | time: a data series, a soak, a deadline | nobody can delegate the passage of time |
| `liveness` | a system that must be standing, and is not | the same |
| `governance` | the item names autonomous execution as the bypass its governance exists to prevent | delegation cannot authorise the thing it would be a bypass OF |

The first three are the shape the sponsor named when setting this policy: **a clear
blockage that costs something to clear** — provisioning another VM is the example, and
it is `access`. The fourth is retained on a different argument, which is why it is
listed separately: it is self-referential rather than material.

Everything else — scope, status, threshold, a binary choice, a choice among stated
options — the system decides, records with its rationale, and proceeds on
(§ *The doctrine* below).

**The fail-safe is unchanged and it points the safe way**: an impediment matching no
class stays retained. No match is not consent. A mechanism that guesses moves items into
lanes that cannot do them, and the lane then either fabricates the work or stalls.

`mechanisms/cycle/halt_disposition.py` is what decides this at the moment a phase stops,
so the same halt gets the same disposition in every phase that can produce one.

## The floor — what the system never crosses

These are not difficult calls. They are the boundary, and no session, watchdog or
agent moves them.

1. **Source control discipline is not negotiable.** Whatever branch and review flow the
   project declares, the system follows it exactly. It never rewrites shared history
   and never attributes a commit to anyone but its author.

2. **No change reaches shared history except through the gates.** Every merge is of a
   pull request whose full chain passed — `/review` returned `READY_TO_MERGE`,
   `/code-quality` did not return `FAIL_HARD`, and no BLOCKED report stands against the
   item. The system may merge such a pull request. It may never merge one that has not
   passed, and it may never merge by moving a gate.

   **This floor used to forbid merging outright**, on the argument that stopping at the
   PR *"costs nothing: the work is delivered, the PR is its record, and the queue
   continues."* That holds exactly while somebody is coming. With nobody watching, the
   same pause is a stop — every item that passes review parks at an open PR and the
   queue drains into a pile of branches nobody merges, which is the failure this file's
   opening names, arriving at the last step instead of the first.

   It was amended once `cycle-brainstorm` existed, because autonomy over merging is only
   defensible downstream of a product a person signed for. The reasoning, the
   alternatives rejected and what it costs are in
   [`.squad/wiki/decisions/merge-is-inside-the-envelope.md`](../.squad/wiki/decisions/merge-is-inside-the-envelope.md).

   **Merging to the trunk is a PREMISE, not a capability the project may withhold**
   (decided 2026-09-08). Branch protection that requires a human reviewer does not
   narrow the envelope — it makes the chain unrunnable, and it must be reported as a
   violated premise before the first item is selected rather than discovered at the last
   step. `mechanisms/gates/check_merge_autonomy.py` asks the remote and fails loudly.

   This reverses the previous reading, which treated such a remote as a supported
   configuration: the system emitted `PR_OPEN_AWAITING_APPROVAL` and took the next item.
   That is exactly the pause this floor's own amendment identified as a stop — moved one
   layer out, where it is harder to see. Every item then completes its whole chain, parks
   at an open PR, and the queue drains into a pile of branches nobody merges. Announcing
   that at intake costs one gate; discovering it per-item costs the whole run.

   `PR_OPEN_AWAITING_APPROVAL` survives for the one case that is not a premise failure:
   **a gate did not pass**. That is the system declining to merge its own work, which is
   floor 3 doing its job.

3. **No mechanical gate is switched off, and no threshold is moved to pass one.** A
   failing gate is a fact to work with. Disabling it, skipping it, forcing past it, or
   loosening the bound until it goes green are the same act under four names.

   **This floor now carries weight it used to share.** While floor 2 forbade merging,
   a disabled gate still met a person before anything reached shared history. That
   second look is gone, so this is the whole of what stands between a moved threshold
   and a merge.

4. **An honest stop beats a false completion.** No verdict for work that did not
   happen, no completion promise for a gate that did not pass, and no event written by
   anything other than the phase that observed it. A system that reports success it did
   not have is worse than one that stops, because the stop is visible.

5. **Every decision leaves a record.** A choice made under this envelope is written
   where the next reader finds it — an event, a registry entry, an ADR. A decision that
   exists only in one session's output did not happen, and cannot be checked or undone.

## The doctrine — how the system decides what is its

### Scope grew during measurement

*The item was registered as one thing; measuring it showed the real work is larger.*

**Register the excess as new items, leave the original at its recorded scope, and link
them.** Never widen an item that is already executing.

The registry is the contract for what an item is. An item that grows while running
becomes unauditable: its evidence describes one thing and its diff another, and no
reviewer can tell which was intended. Splitting keeps both halves reviewable and loses
nothing — the new items carry their own evidence and enter the same queue.

### A gate fails on a cause the slice did not create

*The gate is red because of something that was already broken, in code this item never
touched.*

**Register each cause as its own item, mark the blocked item as waiting on them, and
let the queue work the causes.** Do not accept the failure, and do not change the gate.

Waiting on unrelated items would be a dead end if nothing worked them. It is not one
here: the maintenance chain puts a named cause at the front of the queue precisely
because something is blocked on it. Marking the dependency turns a stopped item into a
work order.

### A structural decision the contract wants recorded

*A boundary call, a trade-off, anything a project's rules say deserves an ADR.*

**Write the ADR — the decision, the alternatives rejected, and the measurement behind
both — and proceed on it.**

There is no separate act of approval to perform. The ADR is the decision and its record
at once, and it is reviewable afterwards by anyone, which a verbal sign-off is not.

**This holds at every tier the project defines, including the ones whose rules say to
stop and convene.** A meeting produces a decision, the reasons behind it, and the
people who were told; an ADR carries all three and outlasts the meeting. So where a
contract asks for one, the ADR takes its place — and must then carry what the meeting
would have covered, explicitly:

  - **who is affected.** Every consumer of the surface being changed, listed, found by
    searching rather than recalled.
  - **what would break, and what would not.** Additive or breaking, and the evidence
    for which.
  - **what was rejected.** The alternatives, and why each was set aside.

Without those three the ADR is a note, not a substitute, and the tier's requirement is
unmet. With them, nothing the meeting would have produced is missing, and the record
is better than the meeting's would have been.

Observed before this was explicit: a session refused an item because its rules classify
the change as needing a meeting, and read this section as covering only the tier that
asks for an ADR. The refusal was right on the text as written. The text was too narrow —
the argument for the ADR never depended on which tier asked.

### The measurement behind the item turned out to be wrong

*Acting on the item revealed that the evidence that justified it does not hold — the
instrument was faulty, the fixture incomplete, the sample not what it looked like.*

**Re-measure before deciding anything about scope, and register nothing until the new
measurement exists.** Fixing the instrument is the item's next step, not a new item.

Registering work from contaminated evidence manufactures items that describe nothing,
each carrying a pointer that will not survive the first reader who follows it. That is
the floor's fourth rule — an honest stop beats a false completion — reached from the
side where the falsehood is quiet, because a wrong item looks exactly like a right one
until someone tries to do it.

This clause outranks "scope grew during measurement". Scope only grew if the
measurement holds; when it does not, there is no scope to split yet.

Observed before this clause existed: a session measured eight defects, was instructed
by doctrine to register them, and refused — the fixture had been incomplete, so what
had been measured was the test's own gap rather than the code's. The refusal was
correct and the doctrine had no way to have reached it.

### A loop ran out of attempts

*A halt-loop stopped without reaching its target — the same gate failed twice, or three
iterations produced no observable progress.*

**Write the BLOCKED report, return the item to the registry with the diagnosis on it,
and take the next one.** Never emit the completion promise, never loosen the gate, and
never keep iterating past the stop condition in the hope that the next pass differs.

The stop condition is not the problem this clause solves — it is correct, and a loop
without one burns a session on an unchanging failure. What was wrong is where the item
went afterwards: it went to a person. So the phase produced a real diagnosis and then
parked it, and the diagnosis was worth nothing until somebody read it.

Returning it to the registry keeps everything the halt earned. The report is the item's
evidence; the failing gate is a named cause; and the queue puts a named cause at the
front precisely because something is blocked on it. That is the difference between a
stopped item and a work order.

**`code_quality INVALID` is the one shape that is NOT this.** It says the contract
itself is broken — the thing that computes the verdict, not the code under it. Returning
the item would file work against a measurement nobody can trust, which is
§ *The measurement behind the item turned out to be wrong* one level up. Register the
broken contract as its own item, and let the queue work the contract.

### A case that resembles one already decided

**Decide it the same way, and name the earlier case.** A divergence needs its reason
written beside it.

This is the clause that keeps doctrine from decaying back into improvisation. It is
also what makes the envelope auditable: consistency can be checked by reading, and
taste cannot.

### The menu does not offer what the doctrine prescribes

*A rule says what to do, and none of the choices on offer does it.*

**Instruct it.** Where the interface allows free text, say what the rule requires and
why. A menu is one session's guess at what the answers might be, and it is not the
contract; the doctrine is.

Observed before this clause existed: an agent correctly diagnosed that the real cause
of a halt was not among the options offered, and had no way to act on its own
diagnosis. It reported the gap and the queue stopped — the diagnosis was right and
worth nothing.

The instruction is held to the same floor as an option: it never switches off a gate,
never merges, never widens an executing item.

### Nothing here fits

**Halt on that item, write down what was measured and why no rule covers it, and take
the next one.**

This is the clause that guarantees nothing stays stuck: when no option and no
instruction can carry the doctrine out, the action is to record the impediment and
move on. One item waiting is not the backlog waiting, and a queue that stops entirely
because one item is hard has converted a local problem into a global one.

An uncovered case is the one thing that goes back to the human — not as a question to
answer now, but as a gap in this file to close later.

## What this envelope does NOT contain — named, so the claim stops outrunning it

An external reviewer read the system's own description in 2026-09-10 and found that
"autonomous" was being read further than the mechanisms reach. Several of his findings
were mechanized the same day. **These were not**, and they are written here rather than
left for the next reader to discover, because an undeclared gap is indistinguishable
from a solved problem.

### Nothing restarts the controller

`fleet_router.py` detects an abandoned lane and offers it again. `squad_lead.py` keeps a
heartbeat and re-reports a stall. Both run INSIDE the controller. **If the controller
itself dies, nothing brings it back** — a checkpoint on disk does not restart a process,
and re-examining an impediment does not clear it.

The kit deliberately ships no daemon (`.squad/wiki/decisions/the-cli-navigates-mechanisms-compute.md`
rejects one for `sq`, and the reasoning holds here). So supervision is the operator's:
a unit file, a cron, a wrapper that restarts. **If the run stops because it is waiting
for somebody to open another session, autonomy ended at that point** — and saying so is
the difference between a limit and a surprise.

### Recovery after publication is contained, not closed

`ACCEPTANCE` exercises the released artifact and leaves the ROADMAP unticked when it
fails. That records the failure; it does not undo it. There is no mechanized contract
for halting an in-flight distribution, restoring a prior version, compensating a data
change, or finishing a partial publish.

`RELEASE` reaching `PR_OPEN_AWAITING_APPROVAL` means a person is already at the merge,
so the blast radius is bounded by that gate rather than by a rollback the system owns.
**"Every decision is reversible" is a property to verify before acting, never a
consequence of having recorded it.**

### A hook that fails is not a hook that blocked

Hooks are the kit's enforcement surface and their failure modes belong to the harness,
not to this repository: some errors and timeouts let the tool call proceed, `PostToolUse`
runs after the work, and an API error takes a different path from a normal stop.
`cycle_events.py` is deliberately fail-open and says so — bookkeeping must not fail the
work.

So **nine hooks existing is not nine constraints holding.** What holds a constraint at
the point that authorizes a merge or a publish is branch protection on the remote, which
is outside the agent's session and outside this kit. `git-safety.md` already draws that
line for the promotion PR; it applies to every other hook-enforced rule too.

### What would close each

| Gap | What closes it |
|---|---|
| Controller restart | A supervisor outside the agent's session, with a durable schedule for waits and detection of a worker that stopped reporting |
| Post-publication recovery | Explicit containment, reconciliation and retry states, with idempotent operations and a verified-reversible precondition |
| Hook survival | Effective-permission tests against the installed harness, plus a remote control at the merge/publish point |

Until those exist, the honest statement is the one the reviewer reached: **autonomy
intended, control mechanisms implemented, whole-chain operation and recovery not yet
demonstrated.**


## The cost, stated

Deciding by doctrine means some decisions will be wrong in ways a person present would
have caught. That is real, and it was weighed against the alternative it replaced —
a queue that halts at every gate for someone who is not coming, discarding work that
was already measured and understood.

The mitigation is not caution; caution is what produced the stopped queue. It is that
every decision under this envelope is written, comparable and reversible. A wrong one
is found by reading the record and undone, rather than discovered months later as a
behaviour nobody can explain.

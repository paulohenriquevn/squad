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

**And this file.** Changing the envelope is a human act. The system operates inside it
and may report that a case is missing from it, but never widens it on its own.

## The floor — what the system never crosses

These are not difficult calls. They are the boundary, and no session, watchdog or
agent moves them.

1. **Source control discipline is not negotiable.** Whatever branch and review flow the
   project declares, the system follows it exactly. It never rewrites shared history
   and never attributes a commit to anyone but its author.

2. **A change is proposed, never merged.** The system opens the pull request and stops
   there. This is the one stop that costs nothing: the work is delivered, the PR is its
   record, and the queue continues to the next item. Merging is the single act that
   reaches shared history, and it stays outside the envelope.

3. **No mechanical gate is switched off, and no threshold is moved to pass one.** A
   failing gate is a fact to work with. Disabling it, skipping it, forcing past it, or
   loosening the bound until it goes green are the same act under four names.

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
Where the contract asks for a meeting, the ADR carries what the meeting would have
produced.

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

## The cost, stated

Deciding by doctrine means some decisions will be wrong in ways a person present would
have caught. That is real, and it was weighed against the alternative it replaced —
a queue that halts at every gate for someone who is not coming, discarding work that
was already measured and understood.

The mitigation is not caution; caution is what produced the stopped queue. It is that
every decision under this envelope is written, comparable and reversible. A wrong one
is found by reading the record and undone, rather than discovered months later as a
behaviour nobody can explain.

# Golden rule — what a technical drawing set must satisfy

The contract a DESIGN panel audits against. `check_design_completeness.py` computes the
structural half — files present, mermaid parses, kinds match, every `PIECE-N` placed.
This is the half a machine cannot count, and it is what the three reviewers are asked.

## The premise: what the panel can audit, and when

A judge grading a product VISION grades it against nothing — the vision is what
everything else is measured against. That argument is `cycle-brainstorm`'s G-B5 and it
holds there.

**It does not transfer to a system drawing whenever code exists.** Then the code is
evidence that exists independently of the drawing and can contradict it, which is
exactly the condition `alignment-threshold.md § Amended 2026-09-01` names when it allows
a judge to review: *"the author must not grade the author's own form"* was the argument;
*"the reviewer must be human"* never was.

So the panel's scope is derived, not chosen:

| The scope has | The panel audits | The panel may NOT conclude |
|---|---|---|
| code on disk | the drawing against the code | that an OPEN question is answered |
| no code yet | internal coherence between D1–D5 and the TRD | that the design is right |

A reviewer that cannot tell which case it is in must say so and abstain. An abstention
is counted as an incomplete panel, never as agreement.

## What each reviewer is asked

### R1 — Does the drawing contradict the code?

Only askable with code on disk. Confirm or refute, per drawing, with `file:line`:

- **D1** — are the states in the drawing the states the code writes? A phase drawn and
  never written is a state that does not exist; a phase written and not drawn is a state
  nobody designed.
- **D2** — is the boundary where the drawing puts it? Check what actually runs
  third-party code and what credential crosses.
- **D3** — does the call order match? Failure paths especially: a drawn failure with no
  code path is a promise, and a code path with no drawn failure is the gap.
- **D4** — is each durability claim backed? A row saying "survives" needs the store
  named and found.
- **D5** — does every component exist, and does every component that exists appear?

**A contradiction is a finding on the DRAWING, not on the code.** The code is what runs.

### R2 — Is an open question disguised as a decision?

The highest-value review here, and it needs no code.

`/design` requires open questions to be listed rather than drawn as settled, because a
placeholder in a diagram reads as a decision that was made. Confirm the inverse: is
anything drawn definitively that the evidence does not support?

- A state with no guard where the guard is the question.
- A boundary drawn solid where nobody established what crosses it.
- A durability row saying "survives" with no store named.

### R3 — Do the drawings contradict each other?

D1–D5 are one system seen five ways. Cross-check:

- A component in D5 that no D3 step touches and no D1 state involves.
- A store in D4 that D2 places outside the trust boundary.
- A failure in D3 that D1 has no state for.
- A `PIECE-N` placed in D5 and named in no other drawing — placed is not covered.

## What the panel may never do

- **Approve because the drawings are complete.** Completeness is
  `check_design_completeness.py`'s verdict and it already ran. The panel adds the
  judgement that a count cannot carry.
- **Refuse because a question is open.** An open question, listed as open, is the phase
  working. Refuse when one is **hidden**, not when one exists.
- **Rewrite the drawing.** A reviewer that edits is a reviewer grading its own form —
  the rule this whole gate is built on.
- **Stand in for the signature.** The panel audits; a person still signs. Two gates,
  two claims: *"nothing here contradicts what we could check"* and *"I read this and
  am willing to say it holds."*

## Verdicts a reviewer may return

| Vote | Means |
|---|---|
| `approve` | Nothing found that the evidence supports as a contradiction |
| `return` | A specific contradiction, hidden question, or cross-drawing conflict, named with its drawing |
| `abstain` | Could not audit — no code to check against for R1, or the drawing is unreadable. **Counted as incomplete, never as agreement** |

A `return` with no named drawing and no reason of at least fifteen words is refused by
`review_panel.py` before it is counted.

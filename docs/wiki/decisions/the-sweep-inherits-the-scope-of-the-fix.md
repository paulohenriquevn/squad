---
type: concept
title: The sweep inherits the scope of the fix
description: Five measurements from two sessions in one day. After a defect is fixed, the search for others is scoped to the shape of the one just fixed — and that is exactly where its sibling survives, one mechanism over.
tags: [decision, testing, remediation, honesty, sweeps]

generated:
  by: claude/opus-5
  at: 2026-09-24
status: stable
sources:
  - id: chain
    resource: ../../../tests/test_a_vote_is_bound_to_what_it_reviewed.py
  - id: empty-slice
    resource: ../../../mechanisms/cycle/run_slice_tests.sh
  - id: discriminate
    resource: ../../../skills/plan-alignment/scripts/check_criteria_discriminate.py
  - id: one-direction
    resource: a-reference-is-checked-in-one-direction.md
---

# The sweep inherits the scope of the fix

## The shape

After fixing a defect, the natural next move is to look for others like it. **The search is
scoped to the shape of the thing just fixed** — the file, the function, the vocabulary, the
spelling — and a sibling that arrives through a different mechanism is outside that scope by
construction. It survives, and it survives in the one place nobody will look again for a while,
because the ground has just been declared searched.

The record already in this directory illustrates it without naming it:
*"a sweep of this kit's identifier vocabularies found four cross-reference checks with the same
defect"* — a sweep scoped to identifier vocabularies, which is why it found four of that kind.

## Five measurements, 2026-09-23/24

**1. A test proved the consumer and not the producer, twice, one level apart.**
`test_a_vote_binds_to_the_text_it_was_cast_on` built its own assignment carrying
`"artifact": artifact`, so it measured `cast_vote` and said nothing about whether
`convene_panel` ever supplied the value — which it did not, for every panel record ever
written. Fixed. **The test written for that fix then exercised `convene_panel` and
`_artifact_digest` separately and never ran `cast()`**, so the chain stayed unverified. The sweep
was *the consumer is tested*; the sibling was one mechanism over, in the chain.

**2. A parser was fixed and its call site was not.** `_blobs_from_batch` spent a byte count on a
character string, so the history reader lost revisions and 350 recoverable files reported
`DIVERGED`. Fixed. The same upgrade path called `classify_file` with **two of its four
arguments**, so the promotion it enables could never run — found later, by a consumer. The sweep
was *the parser*; the sibling was the caller.

**3. An extension was corrected in one criterion and two more of the same shape failed by
another mechanism.** A peer fixed `.tsx` → `.ts` in a criterion, and two others broke on the
working directory rather than the filename. The reviewer that found them named it exactly: *the
sweep was scoped to the name pattern and did not reach the cwd.*

**4. One class, fixed twice in one day, in two files, without either being recognised as the
other.** In the morning: a slice that ran zero tests read `PASS`, because `pytest -k <no-match>`
deselects everything and exits 0. In the evening: a criterion asserting `prints 0` read
`fails today` in both states, because `grep -c` prints `0` and exits `1`. **Both are the same
shape — the passing value is producible by an empty result** — and the second was found by a
consumer, hours after the first was fixed, because the first sweep was scoped to *the runner*.

**5. The sweep that found this class was itself scoped.** The four one-direction cross-reference
checks were found by looking at identifier vocabularies. Nothing in that pass looked at
`check_adr_completeness`, whose header pattern matched no ADR any plan writes — a reference
checked in one direction, arriving through a spelling rather than through a vocabulary. Found a
day later, by an orthogonal panel seat.

## Why the scoping is not carelessness

Each of those sweeps was a reasonable search. The scope came from the only evidence available:
the defect just measured. A sweep cannot be scoped to a shape nobody has seen yet, and widening
it without a reason produces a search with no stopping condition.

What is available is the **mechanism** rather than the shape. In every case above the sibling
shared the failure and differed in the route: consumer/producer, parser/caller, name/cwd,
runner/criterion, vocabulary/spelling. The question that reaches it is not *where else does this
pattern appear* but *what else could produce this outcome*.

## What actually caught them

Not judgement, in any of the five. In four it was a mechanism measuring what somebody had just
done; in the fifth it was a second session running what the first had only read. Across one day
and two sessions, **the corrector was never the author's own second look.**

That is the honest limit of this record: it names a shape and cannot supply the reflex. What it
can supply is the question, and the question is cheap.

## The two questions

- **What else could produce this outcome?** Not *where else does this pattern appear*. The
  sibling shares the failure and differs in the route, so a search keyed on the pattern is keyed
  on the half that does not repeat.
- **Which side of this did I just test — the caller or the callee?** Then test the other one. In
  measurement 1 that question was one sentence away from being asked, twice, by the same session.

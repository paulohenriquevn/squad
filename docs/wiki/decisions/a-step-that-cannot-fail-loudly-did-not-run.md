---
type: concept
title: A step that cannot fail loudly did not run
description: Five measurements in one day, across three sessions, of one shape — a step that silently does nothing inside a procedure that reports success. What makes the shape invisible, and the two defences that are not the same defence.
tags: [decision, honesty, tooling, gates, adr]

generated:
  by: claude/opus-5
  at: 2026-09-22
status: stable
sources:
  - id: promote
    resource: ../../skills/release/scripts/promote_unreleased.py
  - id: testing
    resource: ../../rules/testing.md
  - id: claims
    resource: a-claim-about-now-is-not-a-fact-that-survives.md
---

# A step that cannot fail loudly did not run

## Five measurements, one shape

On 2026-09-22, three sessions maintaining three repositories hit the same failure five
times. Nobody was looking for it; it is what was left after all five were fixed.

**1. An anchored insertion whose anchor had moved.** A CHANGELOG entry was inserted
against the literal string `## [Unreleased]\n\n### Fixed\n\n`. An `### Added` section was
opened above it that day, the anchor stopped existing, `str.replace` matched nothing and
returned the text unchanged. The commit went out with the fix and without its entry, and
nothing said so.

**2. The same shape, three times, in another repository.** Two of the three were caught
only because a *different* gate complained about a version number. The third was found by
reading the file.

**3. A pytest run that never ran.** `--timeout=300` with `pytest-timeout` absent is a usage
error; the invocation was piped to `tail`, so the shell reported `tail`'s exit code. Zero
tests executed and the session reported the suite as running.

**4. A measurement against a layout that never resolved.** A hook was invoked without
`CLAUDE_PROJECT_DIR`, so it found no kit, so it refused nothing — and the run was read as
"this path is allowed". It allowed the kit's own files too, which is what gave it away.

**5. A quoted error message that closed the shell string.** Double quotes inside a `-c`
argument ended the program early; Python received a truncated script, printed nothing, and
the calling hook read that empty output as *no promise was emitted this turn*.

## What they share

In every case a step did nothing, and the procedure around it reported success — because
**doing nothing and succeeding produce the same observable**: no error, no output, exit 0.

    str.replace with no match      returns the input unchanged
    a pipeline's exit code         belongs to the LAST command
    a hook with no project         has nothing to refuse
    a truncated program            prints nothing
    an unrecognised pytest flag    exits before collection

None of these is a bug in the tool. Each is the documented, correct behaviour of the thing
being used. The defect is a caller that cannot tell that behaviour apart from the one it
wanted.

## Why it survives review

The reviewer checks that the step is *correct*, and it is. `str.replace` does exactly what
it promises. The pipeline reports exactly the exit code the shell specifies. What nobody
checks is whether the caller can distinguish *worked* from *found nothing to do* — and on
the happy path those are the same, so the gap is invisible in every case where it does not
matter and visible only where it does.

Related to, and distinct from, [a claim about now is not a fact that
survives](a-claim-about-now-is-not-a-fact-that-survives.md). There, two facts shared one
field. Here, two outcomes share one signal.

## The two defences, which are not the same defence

**Assert the precondition before acting.** An anchored edit states its anchor and refuses
when it is absent; a subprocess reads its own exit code, not a pipeline's. This protects
the honest caller — the one who wrote the step correctly and whose ground moved.

**Have something downstream that fails.** A gate over the artefact, a test over the
outcome. This protects against the file that arrived some other way, and against a caller
who never asserted.

Neither replaces the other, and it is not duplication. `promote_unreleased.py` already has
the first: `[Unreleased]` absent is exit 1, not an unchanged file written back as if
promoted. What none of the five had was either.

## The cheap test

Before shipping a step, ask: **if this did nothing at all, what would be different?**

If the answer is "nothing I check", the step is not wired — it is decoration that happens
to be correct today. That is the same question `rules/testing.md` asks about a test that
cannot fail, moved one layer out: a test that cannot fail tests nothing, and a step that
cannot fail loudly did not run.

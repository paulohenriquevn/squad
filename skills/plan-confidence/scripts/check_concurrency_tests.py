"""Conditional concurrency-tests check for /plan-write plans (SOTA upgrade Phase 2).

Bugs in concurrent code escape TDD-first because single-threaded test execution
interleaves cleanly — the race manifests only under specific schedules. A plan
that touches shared mutable state SHOULD declare a concurrency-aware test
(race detector, atomic-counter invariant, happens-before observation,
cancellation/timeout assertion).

This checker is CONDITIONAL: it only enforces the rule when the plan contains
concurrency signals. Plans whose Baseline Context + Deep Dives + Files-to-edit
sections are signal-free are unaffected.

Soft cap stable id: `soft_floor_concurrency_tests_missing` (cap 89).

This read "sunset 2026-09-07 — after which promotes to hard cap 70 via ADR". The date
passed, `run_structural` still applies 89, no ADR exists, and nothing noticed — a
sunset whose expiry nobody detects is a deadline that silently became permanent, which
is the shape this kit refuses in a consumer's config and had in its own.

The cap stays at 89 DELIBERATELY: promoting it to 70 changes the verdict for every
consumer, and that is a policy decision somebody makes, not a date arriving. Stated as
the current rule rather than as a promise with a date on it, so the next reader is not
told a promotion happened.

Detection rule:

  1. Scan a stable set of sections — Baseline Context, Prior Art & Related Work,
     ADRs, Phase prose (Objective + Why this step + Evidence + Deep Dives +
     Files to edit), Failure scenarios.
  2. Look for concurrency signals: language-agnostic tokens (mutex/lock/atomic/
     concurrent/race/thread/goroutine/channel/async/await/Promise.all/sync.X)
     and language-specific imports (`from threading`, `import asyncio`, `sync.Mutex`,
     `tokio::`, `Atomics`, `worker_threads`).
  3. If signals found in step 2, examine every task's `#### Concurrency tests`
     subsection. The task passes if the subsection contains either:
       - the literal escape `(none — single-threaded)` (with `--` or `—`), OR
       - at least one acceptable race-aware test signal (race/loom/concurrent/
         goroutine test/parallel test/JCStress/Atomics/--race/atomic counter).

  4. Tasks that lack a `#### Concurrency tests` subsection at all, in a plan
     that has signals, fail the check.

Fenced code blocks are masked before scanning so example documentation does not
pollute signal counts.
"""
from __future__ import annotations

import re
import sys as _sys
from dataclasses import dataclass, field
from pathlib import Path, Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "markdown.py").is_file():
        _sys.path.insert(0, str(_up))
        break
from squad.markdown import (  # noqa: E402 — post-bootstrap import
    FENCED_CODE_RE as _FENCED_CODE_OWNER,  # noqa: E402 — post-bootstrap import
)

#: The ONE fenced-code regex, from `squad.markdown`. Eleven scripts each defined
#: their own, in two forms that do not mask the same input: five saw only backtick
#: fences, six also saw `~~~`. A plan whose example block used tildes was masked by
#: six readers and read as prose by the other five, so the same document scored
#: differently depending on which checker asked.
FENCED_CODE_RE = _FENCED_CODE_OWNER

# Section title patterns whose contents are inspected for concurrency signals.
# Per task, the body of `#### Concurrency tests` is examined for the escape OR
# acceptable race-aware signals.
SCAN_HEADINGS = (
    "Baseline Context",
    "Prior Art & Related Work",
    "ADRs",
    "Drawbacks & Risks",
    "Failure scenarios",
)

# Language-agnostic concurrency tokens — case-insensitive word-boundary match.
# Curated to be specific enough that a plan about UI layout will not false-positive,
# but broad enough to catch the patterns that actually matter.
CONCURRENCY_SIGNALS = (
    # generic
    r"\bmutex\b",
    r"\bsemaphore\b",
    r"\brace condition\b",
    r"\brace[- ]detector\b",
    r"\bthread[- ]safe\b",
    r"\batomic(?:\s+counter|\s+operation|\b)",
    r"\bconcurrenc(?:y|e)\b",
    r"\block-free\b",
    r"\bnon-blocking\b",
    r"\bhappens-before\b",
    # Python
    r"\bthreading\.",
    r"\basyncio\b",
    r"\basync\s+def\b",
    r"\bawait\s+",
    r"\bmultiprocessing\b",
    r"\bconcurrent\.futures\b",
    r"\bSemaphore\(",
    # Go
    r"\bgoroutine\b",
    r"\bsync\.(?:Mutex|RWMutex|WaitGroup|Once)\b",
    r"\bchan\s+",
    r"\bgo\s+func\s*\(",
    # Rust
    r"\bMutex(?:<|::new)",
    r"\bRwLock<",
    r"\bArc<",
    r"\btokio::",
    r"\basync\s+fn\b",
    r"\bspawn\(",
    # Java / Kotlin
    r"\bsynchronized\s*\(",
    r"\bConcurrentHashMap\b",
    r"\bAtomicInteger\b",
    r"\bAtomicLong\b",
    r"\bAtomicReference\b",
    r"\bCountDownLatch\b",
    r"\bReentrantLock\b",
    r"\bvolatile\s+\w",
    # JS / TS
    r"\bPromise\.all\(",
    r"\bworker_threads\b",
    r"\bAtomics\.",
    r"\bSharedArrayBuffer\b",
)

def _accepted_signals() -> str:
    """The signals that make this subsection PASS, rendered for a person to read.

    DERIVED from `RACE_TEST_SIGNALS` plus `ESCAPE_MARKERS` — the two things the decider at
    `_race_aware` actually accepts — and never restated.

    It derived from `CONCURRENCY_SIGNALS` until 2026-09-23, which is the list that DETECTS
    whether a task involves concurrency at all (`mutex`, `SharedArrayBuffer`). A reader who
    added a printed token failed again, because acceptance is decided elsewhere (#175). The
    two lists share no purpose: 39 detect, 14 accept.

    The irony is worth keeping. The hand-written parenthetical this function replaced named
    six — "(race/loom/concurrent/parallel/atomic-counter/cancellation)" — and **every one of
    those six is a `RACE_TEST_SIGNALS` member**. The frozen prose was naming the RIGHT list;
    the fix that removed the risk of drift pointed the renderer at the wrong constant, and
    said in this very docstring that it now derived rather than restated. A mechanism built to
    stop a message from lying made it lie a different way.

    Which is why `test_the_refusal_names_the_list_that_decides.py` does not assert WHICH
    constant is read. It asserts that every printed token is accepted by the decider, and
    fails whichever constant a later edit points this at.

    The escape is printed alongside, because there are two ways to pass and a message naming
    one hides the other: a task with no concurrency passes by saying so.
    """
    return " · ".join(sorted({_readable(p) for p in RACE_TEST_SIGNALS + ESCAPE_MARKERS}
                             - {""}))


#: Regex syntax to human text, longest key first so `\s+` is spent before `\s`.
#:
#: The first version of this stripper was written for `CONCURRENCY_SIGNALS`, whose members are
#: nearly all bare `\bword\b`. Pointed at the list that actually decides, it printed
#: `cancellations+propagat`, `Atomics.w+` and `none[—-–]+single[- ]threaded)` — tokens no reader
#: can copy into a document. A message naming the right list in an unusable form is not a fix.
_UNESCAPE = (
    (r"\s+", " "), (r"\s*", " "), (r"\w+", "<name>"), (r"\b", ""),
    (r"[- ]", "-"), (r"[—\-–]+", "—"), (r"\(", "("), (r"\)", ")"), (r"\.", "."),
)


def _readable(pattern: str) -> str:
    """One regex rendered as the text a reader would type.

    An unbalanced `)` survives from `ESCAPE_MARKERS`, whose pattern opens with an escaped
    paren and closes with a literal one; the pairing is restored rather than stripped, because
    the escape must be printed EXACTLY as it has to be written to work.
    """
    text = pattern
    for needle, replacement in _UNESCAPE:
        text = text.replace(needle, replacement)
    text = text.replace("\\", "").strip()
    if text.endswith(")") and "(" not in text:
        text = "(" + text
    return " ".join(text.split())



# Acceptable race-aware test signals — these are what the task's
# `#### Concurrency tests` subsection MUST contain to pass.
RACE_TEST_SIGNALS = (
    r"\bgo test -race\b",
    # No leading `\b`: a boundary cannot hold between a space (or the string start) and a
    # hyphen, both non-word. `\b--race\b` matched only `x--race` and never the real form
    # `cargo test --race` — a pattern in the ACCEPTANCE list that could not accept the thing
    # it names. Found by the test asserting every printed token is accepted (#175).
    r"--race\b",
    r"\bloom::",
    r"\bloom\s+test\b",
    r"\bpytest-asyncio\b",
    r"\bJCStress\b",
    r"\bAtomics\.\w+",
    r"\brace\s+detector\b",
    r"\bconcurrent\s+test\b",
    r"\bparallel\s+test\b",
    r"\bgoroutine\s+test\b",
    r"\batomic[- ]counter\s+invariant\b",
    r"\bhappens-before\s+observation\b",
    r"\bcancellation\s+propagat",
)

ESCAPE_MARKERS = (
    r"\(none\s*[—\-–]+\s*single[- ]threaded\)",
)

CONCURRENCY_SIGNALS_RE = re.compile("|".join(CONCURRENCY_SIGNALS), re.IGNORECASE)
RACE_TEST_SIGNALS_RE = re.compile("|".join(RACE_TEST_SIGNALS), re.IGNORECASE)
ESCAPE_RE = re.compile("|".join(ESCAPE_MARKERS), re.IGNORECASE)

H4_TASK_RE = re.compile(r"^###\s+(T\d+\.\d+)\b[^\n]*$", re.MULTILINE)
H4_CONCURRENCY_RE = re.compile(
    r"^####\s+Concurrency tests\b[^\n]*$", re.MULTILINE
)


@dataclass(frozen=True)
class ConcurrencyReport:
    """Structural report for concurrency-test enforcement."""

    signals_detected: bool
    signals_sample: tuple[str, ...] = field(default_factory=tuple)
    tasks_with_concurrency_subsection: int = 0
    tasks_with_acceptable_test_or_escape: int = 0
    tasks_failing: tuple[str, ...] = field(default_factory=tuple)
    is_complete: bool = True
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _strip_code(content: str) -> str:
    def blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return FENCED_CODE_RE.sub(blank, content)


def _extract_section(content: str, heading: str) -> str | None:
    """Match `## {heading}` (optionally followed by trailing text) up to next H2."""
    pattern = re.compile(rf"^##\s+{re.escape(heading)}(?=\b|$)", re.MULTILINE)
    m = pattern.search(content)
    if m is None:
        return None
    start = m.end()
    next_h2 = re.search(r"^##\s+", content[start:], re.MULTILINE)
    end = (start + next_h2.start()) if next_h2 else len(content)
    return content[start:end]


def _scan_for_signals(content: str) -> list[str]:
    """Return the unique concurrency-signal raw matches in content."""
    seen: list[str] = []
    seen_norm: set[str] = set()
    for m in CONCURRENCY_SIGNALS_RE.finditer(content):
        raw = m.group(0)
        norm = raw.lower().strip()
        if norm in seen_norm:
            continue
        seen_norm.add(norm)
        seen.append(raw)
    return seen


def _iter_task_blocks(content: str) -> list[tuple[str, str]]:
    """Return list of (task_id, task_body) for every `### T<N>.<M>` block."""
    matches = list(H4_TASK_RE.finditer(content))
    tasks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        # Cut at next H2 or H3 of a different kind (e.g., "## Phase")
        next_h2 = re.search(r"^##\s+", content[start:end], re.MULTILINE)
        if next_h2:
            end = start + next_h2.start()
        tasks.append((m.group(1), content[start:end]))
    return tasks


def _extract_concurrency_subsection(task_body: str) -> str | None:
    """Return text after `#### Concurrency tests` up to next `####` or end."""
    m = H4_CONCURRENCY_RE.search(task_body)
    if m is None:
        return None
    start = m.end()
    next_h4 = re.search(r"^####\s+", task_body[start:], re.MULTILINE)
    end = (start + next_h4.start()) if next_h4 else len(task_body)
    return task_body[start:end]


def check_concurrency_tests(plan_path: Path) -> ConcurrencyReport:
    """Inspect plan_path and produce a ConcurrencyReport.

    No-signals-found is a PASS (is_complete=True, signals_detected=False).
    Signals-found + at least one task without an acceptable test/escape is FAIL.
    """
    content = plan_path.read_text(encoding="utf-8-sig")
    stripped = _strip_code(content)

    # Step 1 — collect the scanning corpus from the SCAN_HEADINGS plus the body of
    # every task block (Phase prose). Concurrency signals appearing in task prose
    # are also enforcement triggers — a task that uses goroutines in its Deep Dives
    # but ships zero race tests is a defect.
    corpus_parts: list[str] = []
    for heading in SCAN_HEADINGS:
        sec = _extract_section(stripped, heading)
        if sec is not None:
            corpus_parts.append(sec)
    for _, body in _iter_task_blocks(stripped):
        corpus_parts.append(body)
    corpus = "\n".join(corpus_parts)

    signals = _scan_for_signals(corpus)
    if not signals:
        return ConcurrencyReport(
            signals_detected=False,
            is_complete=True,
            reasons=("no concurrency signals detected; check skipped",),
        )

    # Step 2 — at least one signal present; enforce per-task contract.
    tasks_with_subsection = 0
    tasks_passing = 0
    failing: list[str] = []
    reasons: list[str] = []
    for task_id, body in _iter_task_blocks(stripped):
        sub = _extract_concurrency_subsection(body)
        if sub is None:
            failing.append(task_id)
            reasons.append(
                f"{task_id} lacks a `#### Concurrency tests` subsection; "
                "plan declares concurrency signals so every task must declare its concurrency posture"
            )
            continue
        tasks_with_subsection += 1
        if ESCAPE_RE.search(sub) or RACE_TEST_SIGNALS_RE.search(sub):
            tasks_passing += 1
        else:
            failing.append(task_id)
            reasons.append(
                f"{task_id} `#### Concurrency tests` does not contain an acceptable "
                f"race-aware signal nor the explicit '(none — single-threaded)' escape. "
                # Rendered from the list the matcher actually uses. It was a frozen
                # parenthetical naming six signals while the module matched many more,
                # so the two could drift and a reader grepping the source was right to.
                f"Accepted signals: {_accepted_signals()}"
            )

    return ConcurrencyReport(
        signals_detected=True,
        signals_sample=tuple(signals[:5]),
        tasks_with_concurrency_subsection=tasks_with_subsection,
        tasks_with_acceptable_test_or_escape=tasks_passing,
        tasks_failing=tuple(failing),
        is_complete=len(failing) == 0,
        reasons=tuple(reasons),
    )

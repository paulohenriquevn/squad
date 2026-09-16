#!/usr/bin/env python3
"""TDD shape gate for /implement Step 2 — defense in depth against vague plans.

Validates that every task block in a plan has a `#### TDD` section whose body
contains at least ONE of three executable RED-test shapes:

  (1) assertion shape    — assert*(X, Y) / expect(X).to(...) / X should equal Y
  (2) Given/When/Then    — explicit GWT keywords in order
  (3) test-function shape — `test_<behavior>(<input>) -> <expected>` literal

A task whose TDD section is missing OR contains only prose (no executable
shape) is flagged. /implement Step 2 SHOULD halt the halt-loop for any
such task with BLOCKED — they cannot drive a TDD RED phase.

Companion gate to skills/plan-confidence/scripts/check_criterion_executability.py
(plan-side). This one is the implement-side defense in depth: even if
plan-confidence's heuristic missed a vague criterion, /implement still
refuses to drive a task without an executable test shape.

Usage:
    python3 check_tdd_shape.py --plan records/plans/foo-plan.md

Exit codes:
    0 — every task has an executable TDD shape
    1 — at least one task lacks an executable TDD shape (BLOCKED)
    2 — file not found / parse error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TASK_HEADER_RE = re.compile(r"^###\s+(T\d+\.\d+)\s*[—\-–:]\s*(.+?)\s*$", re.MULTILINE)
NEXT_TASK_OR_H2_RE = re.compile(r"^(##\s+\S|###\s+T\d+\.\d+)", re.MULTILINE)
TDD_BLOCK_RE = re.compile(r"^####\s+TDD\s*$", re.MULTILINE)
NEXT_H4_RE = re.compile(r"^####\s+\S", re.MULTILINE)

# Shape 1: assertion API (broad — handles xunit / Jest / RSpec / chai / pytest)
SHAPE_ASSERTION_PATTERNS = (
    r"\bassert(?:Equals?|True|False|Raises|That|In|NotEqual|NotNull|Null|Throws)\s*\(",
    # `assert X (op) Y` where X may be dotted (response.body, result.status_code)
    r"\bassert\s+[\w.\[\]]+\s*(?:==|!=|<=|>=|<|>|\bin\b|\bis\b)",
    # `assert f(args) (op) Y` — a call expression is as executable as a name, and
    # rejecting it made a valid plan look like prose once this gate became blocking.
    # `assert f(x).attr == y` and `assert f(x)[k] == y` — a call whose RESULT is then
    # navigated. The operator is not adjacent to the `)`, and `[\w.\[\]]+` above cannot
    # cross a parenthesis, so the most ordinary Python assertion there is matched
    # nothing. Measured on a consumer 2026-09-16: `assert score_alignment(b).verdict ==
    # "AWAITING_REVIEW"` sat inside a TDD block the gate reported as having no
    # executable shape, beside two named `def test_` functions.
    r"\bassert\s+[\w.]+\([^)\n]*\)(?:\.[\w.]+|\[[^\]\n]*\])*\s*(?:==|!=|<=|>=|<|>)",
    r"\bexpect\s*\([^)]+\)\s*\.\s*(?:to|toBe|toEqual|toMatch|toHaveBeenCalled)",
    # "X should equal/raise/throw Y" — RSpec/Chai style — must name the expected value
    # (excludes vibe phrases like "tests should be green" by requiring object after verb)
    r"\b\w+\s+should\s+(?:equal|raise|throw|return|contain)\s+\S",
    r"\.assert(?:Equal|True|False)\b",
)

# Shape 2: Given/When/Then (BDD)
SHAPE_GWT_PATTERN = re.compile(
    r"\bgiven\b.{1,500}?\bwhen\b.{1,500}?\bthen\b",
    re.IGNORECASE | re.DOTALL,
)

# Shape 4: a native test harness. Compiled languages do not spell an assertion the way
# the patterns above do, and until 2026-09-15 this gate rejected every one of them.
#
# Measured on a consumer: 8 of 19 plans blocked (42%), and probing one task written four
# ways showed what the gate actually keyed on —
#
#     Go native     func TestXxx(t *testing.T) + t.Errorf   REJECTED
#     Go testify    require.Equal(t, 2, len(got))           REJECTED
#     Rust          assert_eq!(result, 42)                  REJECTED
#     python        assert x == y                           accepted
#     Given/When/Then, in prose                             accepted
#
# So the gate built to catch a plan whose RED is prose ACCEPTED a prose sentence and
# REJECTED executable Go. Seven agents hit it across five items and every one refused to
# rewrite its TDD bodies to clear it; one put the reason exactly right: "that changes
# nothing about what is verified while making me the plan's author as well as its
# implementer."
#
# A test function declaration IS the executable shape in these languages. Naming the
# harness is naming the thing that runs.
SHAPE_NATIVE_PATTERNS = (
    # Go: the declaration, the failure calls, and testify.
    r"\bfunc\s+Test\w*\s*\(\s*\w+\s+\*testing\.[TBF]\b",
    r"\bt\.(?:Errorf?|Fatalf?)\s*\(",
    r"\b(?:require|assert)\.\w+\s*\(\s*t\b",
    # Rust.
    r"\bassert(?:_eq|_ne)?!\s*\(",
    r"#\[\s*test\s*\]",
    # JUnit / Kotlin / C#.
    r"@Test\b|\[Fact\]|\[Test\]",
    # A shell oracle: a command whose expected output is stated. `go test -v | grep -c
    # '^--- PASS:' prints 3` is as executable as an assertion and more reproducible.
    r"`[^`]*\b(?:go|pytest|cargo|npm|grep|test)\b[^`]*`[^.\n]{0,80}?\b(?:prints|outputs|exits?|returns)\b",
)

# Shape 3: test-function literal `test_xxx(input) -> output`
SHAPE_TEST_FN_PATTERNS = (
    r"\btest_\w+\s*\([^)]*\)\s*(?:->|=>|returns?|expects?)",
    r"\bRED:\s*test_\w+",  # plans commonly write "RED: test_xxx_yyy" — that's a shape
    # A test function DECLARED is stronger evidence than a test function NAMED, and
    # `_has_named_test_shape` already credits the name. The patterns above require an
    # arrow or a verb after the parentheses, so `def test_foo(tmp_path):` — which is how
    # a Python test is actually written — matched none of them. Measured on a consumer
    # 2026-09-16: 5 of 29 blocked tasks carried a real declaration and were reported as
    # prose.
    r"^\s*(?:def\s+test_\w+\s*\(|func\s+Test[A-Z]\w*\s*\()",
)

#: A RED that NAMES the failing test is executable whatever the language spells its
#: test symbols. Measured on 26 blocked tasks 2026-09-15: the overwhelming majority
#: named a real symbol (`TestClusterScopedNamesAreReleaseInvariant`) and often the
#: commit it was verified red on — while `RED: test_xxx` sailed through. The gate was
#: encoding Python's naming convention as the definition of "executable".
_TEST_SYMBOL = r"(?:Test[A-Z]\w+|test_\w+|\w+(?:Test|Spec|Suite))"
SHAPE_NAMED_TEST_PATTERNS = (
    rf"\bRED[:.]\s*\**\s*`?{_TEST_SYMBOL}\b",
    rf"\b{_TEST_SYMBOL}\b[^.\n]{{0,140}}?\b(?:must|should|will|has to)\s+"
    r"(?:already\s+)?(?:exist\s+and\s+)?fails?\b",
    rf"\b{_TEST_SYMBOL}\b[^.\n]{{0,140}}?\balready\s+fails?\b",
    rf"-run\s+\^?{_TEST_SYMBOL}",
    #: `test_the_package_directory_is_gone -> 1, expected 0` — a named test with its
    #: measured before-value. Stronger evidence than most assertions carry, because the
    #: number was read off the tree rather than predicted.
    rf"\b{_TEST_SYMBOL}\b\s*(?:->|=>|⇒)\s*\S",
)


@dataclass(frozen=True)
class TaskShape:
    task_id: str
    title: str
    has_tdd_block: bool
    has_assertion_shape: bool
    has_gwt_shape: bool
    has_test_fn_shape: bool
    has_native_shape: bool = False
    has_named_test_shape: bool = False
    has_command_oracle_shape: bool = False

    @property
    def has_executable_shape(self) -> bool:
        return self.has_tdd_block and (
            self.has_assertion_shape or self.has_gwt_shape or self.has_test_fn_shape
            or self.has_native_shape or self.has_named_test_shape
            or self.has_command_oracle_shape
        )


@dataclass(frozen=True)
class ShapeReport:
    total_tasks: int
    tasks_with_shape: int
    tasks: tuple[TaskShape, ...] = field(default_factory=tuple)

    @property
    def blocked_tasks(self) -> tuple[TaskShape, ...]:
        return tuple(t for t in self.tasks if not t.has_executable_shape)

    @property
    def all_pass(self) -> bool:
        # Zero tasks is NOT a pass. With no tasks there are no blocked tasks, so this
        # returned True and the gate exited 0 on a plan it could not read.
        #
        # Measured on a consumer 2026-09-16: 6 of 25 dispatchable plans reported
        # `Total tasks: 0` and exited 0. The largest was 1239 lines with a `## Tasks`
        # section 354 lines in — organised as `#### T1.1` under `### Phase 1`, one
        # heading level below what the parser matches. IMPLEMENT would have proceeded
        # on all six with no TDD verification whatsoever.
        #
        # An inability to read the plan must not become a verdict about the plan.
        return bool(self.tasks) and len(self.blocked_tasks) == 0


#: A fenced block, whatever fence it uses. Its CONTENTS are data, not document
#: structure — a line inside it that looks like a heading is a heading in the example,
#: not in the plan.
FENCE_RE = re.compile(r"^(?P<f>```+|~~~+).*?^(?P=f)\s*$", re.MULTILINE | re.DOTALL)


def _blank_fences(content: str) -> str:
    """Return a copy of the same LENGTH with fenced-block content blanked out.

    Measured on a consumer 2026-09-15: a plan quoting a CHANGELOG snippet inside a fence
    carried the literal line `## [Unreleased]`, `NEXT_TASK_OR_H2_RE` matched it as the
    next H2, and the task body was truncated there — hiding that task's own `#### TDD`
    section and failing the plan for a section it actually had.

    Every character is replaced one-for-one — newlines kept, everything else a space —
    because the offsets found here index into the ORIGINAL. A first attempt preserved
    the line count instead and shifted every offset past the first fence: it cut 11 of
    19 real plans from passing to failing, which is how the distinction was measured
    rather than argued.
    """
    def blank(match: re.Match) -> str:
        return "".join(c if c == "\n" else " " for c in match.group(0))
    return FENCE_RE.sub(blank, content)


def _extract_task_blocks(content: str) -> list[tuple[str, str, str]]:
    """Return list of (task_id, title, body) — body stops at next task/H2.

    Boundaries are found in a fence-blanked copy and the BODY is sliced from the
    original, so a plan may quote headings in an example without losing them.
    """
    scan = _blank_fences(content)
    matches = list(TASK_HEADER_RE.finditer(scan))
    blocks: list[tuple[str, str, str]] = []
    for m in matches:
        tid = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        nxt = NEXT_TASK_OR_H2_RE.search(scan, pos=start)
        end = nxt.start() if nxt else len(content)
        blocks.append((tid, title, content[start:end]))
    return blocks


def _extract_tdd_section(task_body: str) -> str | None:
    """Return the body of the #### TDD section in this task, or None if absent."""
    tdd_match = TDD_BLOCK_RE.search(task_body)
    if tdd_match is None:
        return None
    after = task_body[tdd_match.end():]
    next_h4 = NEXT_H4_RE.search(after)
    return after[: next_h4.start()] if next_h4 else after


def _has_assertion_shape(text: str) -> bool:
    return any(re.search(p, text) for p in SHAPE_ASSERTION_PATTERNS)


def _has_gwt_shape(text: str) -> bool:
    return SHAPE_GWT_PATTERN.search(text) is not None


def _has_native_shape(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in SHAPE_NATIVE_PATTERNS)


def _has_test_fn_shape(text: str) -> bool:
    # MULTILINE, because one of the patterns anchors at line start and a TDD block
    # always has prose above its fence. Without it the anchor matched only when the
    # declaration was the first thing in the section, which is never.
    return any(re.search(p, text, re.MULTILINE) for p in SHAPE_TEST_FN_PATTERNS)


#: A command line that a reader could paste. Deliberately not a general shell grammar —
#: it only has to recognise that something runnable is present.
#: Up to 24 characters of label may precede it — plans write `RED: grep …`, `- go test …`,
#: `$ pytest …`. Anchoring hard at line start was what hid 4 of the 6 oracles measured.
#: Ambiguous English words (`go`, `test`) are only commands with their subcommand
#: attached, so a sentence containing "go" or "test" is not mistaken for one.
_COMMAND_RE = re.compile(
    r"(?m)^[^\n]{0,24}?(?:cd\s+\S+\s*&&\s*)?\b("
    r"go\s+(?:test|build|vet|run|generate)|test\s+[\"$]|"
    r"pytest|python3?\s+-m|cargo\s+\w|npm\s+\w|npx\s+\w|bash\s+\S|sh\s+-c|"
    r"make\s+\w|task\s+[\w:]|grep\b|rg\b|govulncheck|gofmt|golangci-lint|"
    r"kubectl\s+\w|helm\s+\w|git\s+\w"
    r")")

#: What turns a command into an oracle: a stated expectation the reader can compare
#: the output against. Without one, a command is a demonstration, not an assertion.
#: An arrow after a command IS the expectation — `# today 0 -> after >= 1` states the
#: before and after values as plainly as an assert does.
_EXPECTATION_RE = re.compile(
    r"(?:->|=>|⇒)\s*\S|\bexpected\b[:\s]+(?:to\s+)?\S|\bexit=|"
    r"\bMUST\s+(?:fail|pass)|\bmust\s+(?:fail|pass)|\bfails?\s+before\b|"
    r"\bRED\s+before\b|\bprints?\b|\boutputs?\b|\breturns?\s+\S|\bexits?\s+\S",
    re.IGNORECASE)

#: A task may legitimately carry no assertion of its own: a baseline measurement taken
#: before any edit, or the GREEN half of a RED written in a sibling task. Both are TDD
#: structure, not its absence — but only when the task SAYS so and still shows the
#: command it runs. A bare "no test needed" with nothing runnable stays blocked.
_NO_ASSERTION_DECLARED_RE = re.compile(
    r"\bno\s+(?:new\s+)?test\b|\basserts?\s+nothing\b|\bnot\s+applicable\s+in\s+"
    r"the\s+RED-first\b|\bmeasurement\s+step\b|\bbaseline\s+capture\b",
    re.IGNORECASE)

#: The sibling task carrying this one's RED, named so a reader can go read it.
_DEFERRED_TO_SIBLING_RE = re.compile(
    r"\b(?:GREEN|RED)\s+for\b[^.\n]{0,80}?\bT\d+\.\d+", re.IGNORECASE)


def _has_command_oracle_shape(text: str) -> bool:
    """A runnable command plus either a stated expectation or a declared reason.

    Measured on 6 consumer plans 2026-09-15 that this gate blocked entirely: every one
    ran a real command — `govulncheck`, `grep -c ... -> expected 0 (RED)`, `go test
    -count=1 -v` — and stated what it must print. The gate refused them because the
    only shell oracle it recognised was a backticked command followed by the word
    "prints". It was matching one house style, not executability.
    """
    if not _COMMAND_RE.search(text):
        return False
    return bool(
        _EXPECTATION_RE.search(text)
        or _NO_ASSERTION_DECLARED_RE.search(text)
        or _DEFERRED_TO_SIBLING_RE.search(text))


def _has_named_test_shape(text: str) -> bool:
    """A named failing test is greppable; a promise that tests will pass is not."""
    return any(re.search(p, text) for p in SHAPE_NAMED_TEST_PATTERNS)


def check_tdd_shape(plan_path: Path) -> ShapeReport:
    content = plan_path.read_text(encoding="utf-8-sig")
    task_blocks = _extract_task_blocks(content)

    shapes: list[TaskShape] = []
    for tid, title, body in task_blocks:
        tdd_body = _extract_tdd_section(body)
        if tdd_body is None:
            shapes.append(TaskShape(
                task_id=tid, title=title, has_tdd_block=False,
                has_assertion_shape=False, has_gwt_shape=False, has_test_fn_shape=False,
            ))
            continue
        shapes.append(TaskShape(
            task_id=tid,
            title=title,
            has_tdd_block=True,
            has_assertion_shape=_has_assertion_shape(tdd_body),
            has_gwt_shape=_has_gwt_shape(tdd_body),
            has_test_fn_shape=_has_test_fn_shape(tdd_body),
            has_native_shape=_has_native_shape(tdd_body),
            has_named_test_shape=_has_named_test_shape(tdd_body),
            has_command_oracle_shape=_has_command_oracle_shape(tdd_body),
        ))

    return ShapeReport(
        total_tasks=len(shapes),
        tasks_with_shape=sum(1 for s in shapes if s.has_executable_shape),
        tasks=tuple(shapes),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report")
    args = parser.parse_args()

    if not args.plan.exists():
        print(f"file not found: {args.plan}", file=sys.stderr)
        return 2

    report = check_tdd_shape(args.plan)

    if args.json:
        out = {
            "total_tasks": report.total_tasks,
            "tasks_with_shape": report.tasks_with_shape,
            "blocked_task_ids": [t.task_id for t in report.blocked_tasks],
            "blocked_reasons": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "reason": (
                        "no #### TDD section in task body"
                        if not t.has_tdd_block
                        else "TDD section has no executable shape "
                             "(assertion / Given-When-Then / test_fn)"
                    ),
                }
                for t in report.blocked_tasks
            ],
            "all_pass": report.all_pass,
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"Total tasks: {report.total_tasks}")
        print(f"With executable TDD shape: {report.tasks_with_shape}")
        if not report.tasks:
            body = args.plan.read_text(encoding="utf-8-sig")
            has_section = re.search(r"^##\s+Tasks\s*$", body, re.MULTILINE) is not None
            where = ("a `## Tasks` section is present and no task heading inside it"
                     " matched" if has_section else "no `## Tasks` section was found")
            print(f"  UNREADABLE: {where}.")
            print("  This checker matches `### T1.1 — title`. A plan that nests tasks"
                  " one level deeper (`#### T1.1` under `### Phase 1`) is invisible"
                  " to it.")
            print("  Reported as a failure rather than as zero tasks: a plan this"
                  " checker cannot read has not been checked.")
        for t in report.blocked_tasks:
            reason = (
                "no #### TDD section"
                if not t.has_tdd_block
                else "TDD section has no executable shape"
            )
            print(f"  BLOCKED {t.task_id} ({t.title}): {reason}")

    return 0 if report.all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

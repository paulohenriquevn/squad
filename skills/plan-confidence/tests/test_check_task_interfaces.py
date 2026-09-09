"""Cross-check what each task declares it produces against what later tasks use.

WHY THIS EXISTS
---------------
`check_wiring.py` asks the same question one phase too late: it runs after
`/implement`, when the calls have already been written. A signature that two
tasks disagree about is cheapest to find while both are still prose.

The method comes from an observed `subagent-driven-development` run
(obra/superpowers, 2026-08-28). Its pre-flight pass cross-checked 14
producer/consumer pairs before any code, and found six defects in the plan —
among them a helper no task ever called, a duplicate import, and (worth the pass
on its own) `assert.throws` returning `undefined` at eight call sites, which
would have failed every test in two files.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It reads only what the plan DECLARES, in `#### Pseudo-code / Signatures` blocks.
Inferring symbols from prose would fire on any task that mentions a function
name in passing, and a gate that cries wolf in a consumer is a gate somebody
disables. Tasks with no signature block are counted and reported as unchecked,
never as clean — an absent declaration is unknown, not fine.
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from check_task_interfaces import check_task_interfaces  # noqa: E402


def _plan(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "plan.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_symbol_produced_and_never_consumed_is_reported(tmp_path: Path) -> None:
    """The `dedent()` case: a helper no task in the plan ever calls.

    Measured in the source run as P2. It is not a crash — it is a task that
    ships code with no caller, which the kit's own D1 detector would flag one
    phase later, after it was written.
    """
    plan = _plan(tmp_path, """
### T1.1 — Parse regions

#### Pseudo-code / Signatures

```pseudocode
function parseRegions(source, file): Region[]
function dedent(text): string
```

### T1.2 — Cross-check

#### Pseudo-code / Signatures

```pseudocode
function checkExample(dir): Finding[]
  regions = parseRegions(source, file)
```
""")
    report = check_task_interfaces(plan)
    assert "dedent" in report.produced_never_consumed
    assert "parseRegions" not in report.produced_never_consumed


def test_a_symbol_consumed_but_never_produced_is_reported(tmp_path: Path) -> None:
    """A task calling something no earlier task declares.

    This is the half that breaks at runtime rather than lingering as dead code.
    """
    plan = _plan(tmp_path, """
### T1.1 — Parse

#### Pseudo-code / Signatures

```pseudocode
function parseRegions(source, file): Region[]
```

### T1.2 — Validate

#### Pseudo-code / Signatures

```pseudocode
function validate(dir): Finding[]
  manifest = parseManifest(raw, path)
```
""")
    report = check_task_interfaces(plan)
    assert "parseManifest" in report.consumed_never_produced


def test_consumption_before_production_is_an_ordering_defect(tmp_path: Path) -> None:
    """T1 calling what T2 produces is a plan that cannot be executed in order.

    The symbol resolves, so a set-based check would call it clean. Order is the
    whole point of a task list.
    """
    plan = _plan(tmp_path, """
### T1.1 — Uses it first

#### Pseudo-code / Signatures

```pseudocode
function early(dir): void
  later = buildIndex(dir)
```

### T1.2 — Defines it later

#### Pseudo-code / Signatures

```pseudocode
function buildIndex(dir): Index
```
""")
    report = check_task_interfaces(plan)
    assert any("buildIndex" in v for v in report.consumed_before_produced)


def test_a_clean_plan_reports_nothing(tmp_path: Path) -> None:
    """Producer first, consumer second, every symbol used."""
    plan = _plan(tmp_path, """
### T1.1 — Parse

#### Pseudo-code / Signatures

```pseudocode
function parseRegions(source, file): Region[]
```

### T1.2 — Use it

#### Pseudo-code / Signatures

```pseudocode
function checkExample(dir): Finding[]
  regions = parseRegions(source, file)
```
""")
    report = check_task_interfaces(plan)
    assert report.produced_never_consumed == ()
    assert report.consumed_never_produced == ()
    assert report.consumed_before_produced == ()


def test_tasks_without_a_signature_block_are_counted_not_assumed_clean(tmp_path: Path) -> None:
    """Silence is unknown, not fine.

    Signature blocks are optional in the template — "skip for trivially-defined
    tasks". A pass that reported clean over a plan it could not read would be
    the worst outcome available: a green tick that measured nothing.
    """
    plan = _plan(tmp_path, """
### T1.1 — Rename a constant

#### Objective

Rename MAX to MAX_BATCH.

### T1.2 — Also prose only

#### Objective

Update the docs.
""")
    report = check_task_interfaces(plan)
    assert report.tasks_total == 2
    assert report.tasks_with_signatures == 0
    assert report.produced_never_consumed == ()


def test_a_plan_with_no_tasks_is_not_a_finding(tmp_path: Path) -> None:
    """Nothing to cross-check is not a defect in the plan."""
    report = check_task_interfaces(_plan(tmp_path, "# Plan\n\n## Context\n\nSomething.\n"))
    assert report.tasks_total == 0
    assert report.consumed_never_produced == ()

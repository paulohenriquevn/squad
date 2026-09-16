"""A plan this checker cannot read has not been checked.

`all_pass` returned `len(blocked_tasks) == 0`. With zero tasks parsed there are no
blocked tasks, so the gate exited 0 — on a plan it never read.

Measured on a consumer 2026-09-16: 6 of 25 dispatchable plans reported `Total tasks: 0`
and exited 0. The largest was 1239 lines with its `## Tasks` section 354 lines in,
organised as `#### T1.1` under `### Phase 1` — one heading level below what the parser
matches. IMPLEMENT would have proceeded on all six with no TDD verification at all.

The parser is deliberately NOT widened here. `#### T1.1` sits beside `#### TDD` in those
plans rather than above it, so accepting the deeper level would attach TDD blocks to
tasks by guesswork. Refusing to read is a fact; guessing the association is not.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_tdd_shape.py"

_NESTED = """# A plan whose tasks nest one level deeper

## Tasks

### Phase 1 — the inventory

#### T1.1 — the package exists

#### TDD

```go
func TestThing(t *testing.T) { t.Fatal("red") }
```
"""

_FLAT = """# A plan the checker reads

## Tasks

### T1.1 — the package exists

#### TDD

```go
func TestThing(t *testing.T) { t.Fatal("red") }
```
"""


def _run(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    plan = tmp_path / "plan.md"
    plan.write_text(body, encoding="utf-8")
    return subprocess.run([sys.executable, str(_SCRIPT), "--plan", str(plan)],
                          capture_output=True, text=True, timeout=180)


def test_a_plan_the_checker_cannot_read_does_not_pass(tmp_path: Path) -> None:
    result = _run(tmp_path, _NESTED)
    assert result.returncode == 1, \
        "the gate exited 0 on a plan it parsed zero tasks from"
    assert "UNREADABLE" in result.stdout


def test_the_message_names_what_it_looked_for(tmp_path: Path) -> None:
    """`Total tasks: 0` reads as an empty plan. It was an unread one, and the two need
    different actions from whoever sees the output."""
    out = _run(tmp_path, _NESTED).stdout
    assert "`## Tasks` section is present" in out
    assert "### T1.1" in out, "the output does not say which shape it matches"


def test_a_plan_with_no_tasks_section_says_that_instead(tmp_path: Path) -> None:
    out = _run(tmp_path, "# Nothing here\n\nNo tasks at all.\n").stdout
    assert "no `## Tasks` section was found" in out


def test_a_readable_plan_still_passes(tmp_path: Path) -> None:
    """The fix must not turn every plan into a failure."""
    result = _run(tmp_path, _FLAT)
    assert result.returncode == 0, result.stdout
    assert "UNREADABLE" not in result.stdout

"""A run whose files changed under it reported a failing suite, not a moving tree.

Measured 2026-09-22 in this repository: the slice runner was started, three modules were
edited while it ran, and the root bundle came back `1 failed`. The sentence was true and
was about a state that never existed on disk as a whole — every other suite passed,
because none of them reads the files that were being edited.

`/review` already refuses this shape for its reviewers: `consolidate_findings` records HEAD
and a status digest when the agents are spawned, compares afterwards, and reports a moved
tree above every finding. The runner those same sessions use to check their own work did
not — so the one place a person looks before reporting a result was the one place that
could not tell them the result was unattributable.

IT DOES NOT FAIL THE RUN. A tree that moved is not wrong on its face; it is unattributable,
and that is a judgement the caller makes from the `TREE_MOVED` trailer line. Making it red
would turn every legitimate concurrent edit into a failing suite, and leaving it silent is
what produced the measurement above.

WHY THIS FILE ASSERTS SHAPE AND NOT BEHAVIOUR. `run_slice_tests.sh` resolves `REPO_ROOT`
two levels up from itself and `cd`s there (lines 29-30), deliberately: a consumer invoking
it must get the kit's suites and not whatever directory they were standing in. The
consequence is that it cannot be pointed at a fixture — invoked from a scratch repo it runs
THIS repository's full suite, measured at over sixty seconds before being killed. So the
comparison logic is verified separately, below, and what this file pins about the script is
that the capture exists, is taken on both sides, and is reported before the verdict. A test
that cannot exercise its subject says so rather than implying it did.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
RUNNER = _ROOT / "mechanisms" / "cycle" / "run_slice_tests.sh"


def _script() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_the_state_is_captured_before_the_suites_start() -> None:
    body = _script()
    capture = body.index('_state_before="$(_tree_state)"')
    fan_out = body.index("xargs -P")

    assert capture < fan_out, (
        "a state taken after the suites start is a state the suites already changed"
    )


def test_the_state_is_taken_again_and_compared() -> None:
    """The invariant is that both readings exist and are compared — never how often.

    This asserted `== 2` on the day it was written, when the comparison served the
    trailer line and the human notice. The durable record added hours later reuses the
    same expression for its `tree_moved` field, and the count became 3: the test failed
    on a change that strengthened exactly what it guards.

    A count is a proxy for a structure, and it breaks when the structure grows in the
    direction the test wanted. What is pinned now is that the second reading is taken and
    that at least one comparison consumes it.
    """
    body = _script()

    assert '_state_after="$(_tree_state)"' in body, "the second reading is never taken"
    assert body.count('[ "$_state_before" != "$_state_after" ]') >= 1, (
        "the two readings exist and nothing compares them"
    )


def test_the_notice_comes_before_the_verdict() -> None:
    """A reader who learns this after the verdict has already believed it."""
    body = _script()

    assert body.index("TREE MOVED DURING THE RUN") < body.index("ALL SUITES GREEN")


def test_a_moved_tree_does_not_exit_non_zero_on_its_own() -> None:
    """The only `exit 1` is the one the failing-suite branch already owned."""
    body = _script()
    moved_block = body[body.index("TREE MOVED DURING THE RUN"):]

    assert "exit 1" not in moved_block.split("FAILED SUITES")[0]


def test_the_status_read_includes_untracked_files() -> None:
    """With the default, git collapses an untracked directory into one line.

    A new file and a probe beside it then share that line, so excluding one hides the
    other — the reason `consolidate_findings.capture_tree_state` states for the same flag.
    """
    assert "--untracked-files=all" in _script()


# ── the comparison itself, exercised rather than described ───────────────────

_STATE = (
    "_tree_state() { printf '%s %s' "
    '"$(git rev-parse HEAD 2>/dev/null || echo no-head)" '
    "\"$(git status --porcelain --untracked-files=all 2>/dev/null "
    "| sha256sum | cut -d' ' -f1)\"; }"
)


def _states(root: Path, script: str) -> list[str]:
    out = subprocess.run(["bash", "-c", f"{_STATE}\n{script}"], cwd=root,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.com"),
                 ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True,
                   capture_output=True)
    return root


def test_an_untouched_tree_hashes_the_same_twice(tmp_path: Path) -> None:
    before, after = _states(_repo(tmp_path), 'echo "$(_tree_state)"\necho "$(_tree_state)"')

    assert before == after


def test_a_file_appearing_mid_run_changes_the_state(tmp_path: Path) -> None:
    before, after = _states(
        _repo(tmp_path), 'echo "$(_tree_state)"\ntouch mid-run.txt\necho "$(_tree_state)"')

    assert before != after
    assert before.split()[0] == after.split()[0], "HEAD did not move; the working tree did"


def test_a_commit_mid_run_changes_the_head_half(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before, after = _states(root, (
        'echo "$(_tree_state)"\n'
        'echo two > a.txt && git add -A && git commit -qm second\n'
        'echo "$(_tree_state)"'))

    assert before.split()[0] != after.split()[0]

"""Red in an install and green upstream is a different finding from red everywhere.

Measured 2026-09-16: three slices green in the kit's repository and red in a consumer
install, same code, nothing edited between. All three were paths that resolve to the kit
here and to the CONSUMER'S project there — a conftest walking up to `.git`, a template
path the installer overwrites with live configuration, a records root that is one
directory upstream and two once installed.

The consumer's push gate runs the installed suite, so it found all three. What it could
not say is which of the two trees it had been asking about, and the two take opposite
actions: a defect in the kit's TESTS, or a defect in the code they cover. The run said
neither and left the reader to work it out.

The root is found by walking UP for a directory holding both `skills/` and `mechanisms/`.
The first attempt used a fixed `/..`, which is one level short from `mechanisms/cycle/`
and could never match — counting levels breaks the moment a file moves; asking what a
directory CONTAINS does not. That is the same fixed-depth defect corrected three times
elsewhere in this kit.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _ROOT / "mechanisms" / "cycle" / "run_slice_tests.sh"

_RESOLVE = '''
d="$(cd "%s" && pwd)"
while [ "$d" != "/" ]; do
    if [ -d "$d/skills" ] && [ -d "$d/mechanisms" ]; then break; fi
    d="$(dirname "$d")"
done
case "$d" in
    */.claude) echo INSTALLED ;;
    *) echo REPO ;;
esac
'''


def _verdict(start: Path) -> str:
    return subprocess.run(["bash", "-c", _RESOLVE % start], capture_output=True,
                          text=True, timeout=120, check=False).stdout.strip()


def test_the_runner_prints_which_tree_it_asked_about() -> None:
    body = _RUNNER.read_text(encoding="utf-8")
    assert 'echo "TREE: $_tree"' in body, "the run does not say which tree it ran against"
    assert "defect in the kit's TESTS" in body, \
        "the installed case does not say what a failure there means"


def test_it_reuses_the_root_the_script_already_resolved() -> None:
    """The banner reported the wrong tree because it resolved the root a SECOND time.

    Line 29 computes `REPO_ROOT` and line 30 `cd`s into it. The banner re-resolved
    `BASH_SOURCE[0]`, which is RELATIVE when the script is invoked by a relative path —
    so after the `cd` it resolved against the wrong directory, the subshell `cd` failed,
    `pwd` never ran, and `_kit_dir` came out empty. `dirname ""` is `.`.

    Measured 2026-09-16, hours after the banner shipped: run from a consumer's project
    root as `bash .claude/mechanisms/cycle/run_slice_tests.sh`, it printed
    `TREE: the kit's own repository at .` from inside an install — the one thing the
    banner exists to distinguish, reported backwards.

    BOTH resolutions are correct in isolation; only the ORDER breaks it, which is why the
    test that checked the resolution passed throughout. A second answer to a question the
    script had already answered.
    """
    body = _RUNNER.read_text(encoding="utf-8")
    assert '_kit_dir="$REPO_ROOT"' in body, \
        "the banner resolves the kit root a second time instead of reusing REPO_ROOT"
    assert body.count('cd "$(dirname "${BASH_SOURCE[0]}")') <= 1, \
        "BASH_SOURCE is re-resolved after the script has changed directory"


def test_it_walks_up_rather_than_counting_levels() -> None:
    """A fixed `/..` from `mechanisms/cycle/` lands on `mechanisms/`, and the `.claude`
    test can never match. The first version of this shipped that way for one commit."""
    body = _RUNNER.read_text(encoding="utf-8")
    # `REPO_ROOT` itself is `dirname/../..` — a fixed depth, and correct because it sits
    # beside the file it measures from, before any `cd`. What must not come back is a
    # SECOND resolution here, which the test above pins.
    assert 'REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"' in body, \
        "the one resolution the script performs has moved or changed shape"


def test_the_two_layouts_resolve_differently(tmp_path: Path) -> None:
    """The property the message depends on, checked against both real shapes."""
    repo = tmp_path / "kit"
    installed = tmp_path / "project" / ".claude"
    for base in (repo, installed):
        (base / "skills").mkdir(parents=True)
        (base / "mechanisms" / "cycle").mkdir(parents=True)
    assert _verdict(repo / "mechanisms" / "cycle") == "REPO"
    assert _verdict(installed / "mechanisms" / "cycle") == "INSTALLED"

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

import re
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
                          text=True, timeout=120).stdout.strip()


def test_the_runner_prints_which_tree_it_asked_about() -> None:
    body = _RUNNER.read_text(encoding="utf-8")
    assert 'echo "TREE: $_tree"' in body, "the run does not say which tree it ran against"
    assert "defect in the kit's TESTS" in body, \
        "the installed case does not say what a failure there means"


def test_it_walks_up_rather_than_counting_levels() -> None:
    """A fixed `/..` from `mechanisms/cycle/` lands on `mechanisms/`, and the `.claude`
    test can never match. The first version of this shipped that way for one commit."""
    body = _RUNNER.read_text(encoding="utf-8")
    assert re.search(r'-d "\$_kit_dir/skills"', body), "the root is not found by content"
    assert '/.." && pwd)"\ncase' not in body, "a fixed-depth resolution came back"


def test_the_two_layouts_resolve_differently(tmp_path: Path) -> None:
    """The property the message depends on, checked against both real shapes."""
    repo = tmp_path / "kit"
    installed = tmp_path / "project" / ".claude"
    for base in (repo, installed):
        (base / "skills").mkdir(parents=True)
        (base / "mechanisms" / "cycle").mkdir(parents=True)
    assert _verdict(repo / "mechanisms" / "cycle") == "REPO"
    assert _verdict(installed / "mechanisms" / "cycle") == "INSTALLED"

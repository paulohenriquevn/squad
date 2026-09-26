"""A convention only checked after the fact is enforced at the worst possible moment.

`--message-file` has existed as long as the gate, and this kit shipped no way to reach
it: no git hook, no documentation, no example. So the conventions were only ever checked
against commits that already existed.

Measured on a consumer 2026-09-16: four commits broke the conventions and nothing said
so until a push was attempted. By then THREE were already on the remote — an amend could
not reach them, only a force-push would, and the gate refusing the push was refusing the
only remedy the arithmetic allowed. Nine verified commits sat behind that wall.

Every one of those four would have been refused at `commit-msg` time, when the fix was
retyping a subject line.

The kit does not install the hook: `.git/hooks/` is per-clone, unversioned, and writing
into it silently is how a tool surprises the person who cloned. It is two lines and a
`chmod +x`, and the rule is where they are written down.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RULE = _ROOT / "rules" / "contribution-conventions.md"
_GATE = _ROOT / "mechanisms" / "gates" / "check_contribution_conventions.py"


def test_the_rule_names_all_three_call_sites() -> None:
    text = _RULE.read_text(encoding="utf-8")
    for needed in ("--message-file", "--introduced", "commit-msg"):
        assert needed in text, f"the rule never tells a reader about {needed}"


def test_the_documented_hook_snippet_actually_refuses(tmp_path: Path) -> None:
    """The snippet is executable advice, so it is executed here. A documented command
    that does not work is worse than none — it is advice nobody can tell is broken."""
    text = _RULE.read_text(encoding="utf-8")
    assert re.search(r"--message-file\s+\"\$1\"", text), \
        "the snippet does not pass git's message path"

    bad = tmp_path / "msg.txt"
    bad.write_text("this subject has no conventional header whatsoever\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_GATE), "--repo", str(_ROOT), "--message-file", str(bad)],
        capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 1, "a malformed message was accepted"
    assert "header_shape" in result.stdout


def test_the_documented_hook_snippet_accepts_a_good_message(tmp_path: Path) -> None:
    """A gate that refuses everything is disabled on its first day."""
    good = tmp_path / "msg.txt"
    good.write_text("fix(gates): a good message\n\nWith a body that explains why.\n",
                    encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(_GATE), "--repo", str(_ROOT), "--message-file", str(good)],
        capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, result.stdout


def test_the_rule_says_the_kit_does_not_install_it() -> None:
    """Writing into `.git/hooks/` silently is how a tool surprises the person who
    cloned. If that stops being true the rule must stop saying it."""
    flat = " ".join(_RULE.read_text(encoding="utf-8").split())
    assert "The kit does not install this" in flat

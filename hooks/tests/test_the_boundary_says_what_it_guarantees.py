"""The kit boundary is a convention, and nothing said so.

`boundary-check.py` reads `tool_input.file_path` — so it sees `Write`, `Edit` and
`NotebookEdit`, and nothing else. A Python heredoc calling `Path.write_text` reaches the
same bytes and the hook never runs. That happened on 2026-09-18: a session edited a file
inside an installed kit through a heredoc and nothing stopped it.

THE FIX IS NOT A WIDER PATTERN

`validate-command.py` already argued this for the credential deny list, and the argument
transfers without change:

    This closes the common door. It does NOT make the deny list a sandbox, and saying
    otherwise would make it the thing it replaces — a guard that reads as protection and
    is not. A determined session reaches the same bytes through `python3 -c`, a heredoc,
    an editor, or a path this pattern does not spell. What it stops is the accident and
    the habit, which is most of what happens.

Chasing `write_text` would add `open(…, "w")`, `shutil.copy`, `tee`, `dd`, and a
truncating redirect — each one a door, none of them the last. The honest move is the one
`reference-provenance.md § 6` already makes for its own layers: say which layer is a
guarantee and which is a convention, so a reader knows what they are relying on.

This test holds the declaration, not the coverage. A guard whose limits are written down
can be trusted exactly as far as it claims; one that is silent gets trusted further than
it earns, which is how the boundary came to read as a guarantee.
"""
from __future__ import annotations

from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / "boundary-check.py"


def test_the_hook_states_which_tools_it_can_see() -> None:
    """It reads `tool_input.file_path`, so its reach is exactly the tools that carry
    one. A reader has to be able to learn that without reading the parser."""
    body = _HOOK.read_text(encoding="utf-8")

    assert "file_path" in body
    assert "write_text" in body, (
        "the hook does not mention `write_text`, so nothing on the page tells a reader "
        "that a Python heredoc reaches the same bytes unwatched — and the boundary "
        "reads as a guarantee it does not provide")


def test_the_hook_says_convention_or_guarantee() -> None:
    """`reference-provenance.md § 6` sets the precedent: name the layer, name what it
    is worth. Silence is what let this one be trusted further than it earns."""
    body = _HOOK.read_text(encoding="utf-8").lower()

    assert "convention" in body or "not a sandbox" in body, (
        "the hook never says whether the boundary is a guarantee or a convention, so "
        "the reader cannot tell what they are relying on")


def test_the_limit_names_a_way_around_it() -> None:
    """An abstract caveat is not actionable. The neighbouring guard names `python3 -c`,
    a heredoc and an editor, and this one should be as concrete."""
    body = _HOOK.read_text(encoding="utf-8")

    assert "heredoc" in body.lower(), (
        "the stated limit does not name a concrete way past it, which is the "
        "difference between a caveat a reader can act on and one they skim")

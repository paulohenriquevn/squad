"""The example in a config file is an entry the parser takes.

THE DEFECT THIS CLOSES
----------------------
`rules/code-quality-allowlist.txt` opens by recording the fix for #343:

    "this header used to document a FOUR-field format … that `load_allowlist` has never
     accepted. Writing an entry the way the file itself described raised `ValueError` …
     so following the documentation produced a WORSE outcome (FAIL_HARD, cap 49) than
     adding nothing at all."

and closes, eight lines later, with a commented example in four fields. Measured
2026-09-21, uncommenting it:

    malformed entry (expected 6 pipe-separated fields, got 4)

`allowlist_malformed_entry` is HARD and aborts allowlist processing for the whole run,
so the obvious way to write a first entry — copy the example — is worse than writing
nothing. The header was corrected and the example below it was not.

AND THE SUNSET WINDOW
---------------------
Two documents call it mandatory — the golden rule's `| Sunset window | ≤ 90 days from
entry creation date |` and this file's own "MUST be ≤ 90 days" — and `load_allowlist`
validated the ISO shape and stopped. A sunset in 2029 was accepted: a permanent waiver
wearing a temporary one's clothes, which is the thing § anti-patterns calls "allowlists
growing stale forever".
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "code-quality" / "scripts"))
sys.path.insert(0, str(REPO))

from _detector_contract import load_allowlist  # noqa: E402

ALLOWLIST = REPO / "rules" / "code-quality-allowlist.txt"


def _commented_examples() -> list[str]:
    """The commented entries under the `# Example` marker.

    Scoped to that section on purpose: the header legitimately QUOTES the four-field
    shape it is warning about, and a scan for pipes would validate the warning as if it
    were an entry.
    """
    out: list[str] = []
    in_examples = False
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip("#").strip()
        if stripped.lower().startswith("example"):
            in_examples = True
            continue
        if in_examples and stripped.count("|") >= 3:
            out.append(stripped)
    return out


def test_the_file_still_ships_an_example() -> None:
    """Guards the guard: no example means nothing below is checked."""
    assert _commented_examples(), "the allowlist ships no example entry to validate"


@pytest.mark.parametrize("example", _commented_examples())
def test_every_commented_example_parses(example: str, tmp_path: Path) -> None:
    probe = tmp_path / "allowlist.txt"
    probe.write_text(example + "\n", encoding="utf-8")

    entries = load_allowlist(probe)

    assert len(entries) == 1, (
        "the example is what somebody copies to write their first entry; a malformed "
        "one raises allowlist_malformed_entry, which is HARD and aborts the whole run")


def test_a_sunset_beyond_the_window_is_refused(tmp_path: Path) -> None:
    far = datetime.date.today() + datetime.timedelta(days=200)
    probe = tmp_path / "allowlist.txt"
    probe.write_text(
        f"python | src/legacy/m.py | dead_code | migrate | rollback path | {far}\n",
        encoding="utf-8")

    with pytest.raises(ValueError, match="90"):
        load_allowlist(probe)


def test_a_sunset_inside_the_window_is_accepted(tmp_path: Path) -> None:
    near = datetime.date.today() + datetime.timedelta(days=60)
    probe = tmp_path / "allowlist.txt"
    probe.write_text(
        f"python | src/legacy/m.py | dead_code | migrate | rollback path | {near}\n",
        encoding="utf-8")

    assert len(load_allowlist(probe)) == 1


def test_a_sunset_already_past_is_still_parsed(tmp_path: Path) -> None:
    """An expired entry is IGNORED at scoring time and reported as expired — that is
    the file's own contract, and refusing to parse it would hide the expiry instead of
    surfacing it."""
    probe = tmp_path / "allowlist.txt"
    probe.write_text(
        "python | src/legacy/m.py | dead_code | migrate | rollback path | 2020-01-01\n",
        encoding="utf-8")

    assert len(load_allowlist(probe)) == 1

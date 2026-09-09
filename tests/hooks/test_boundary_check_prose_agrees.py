"""Every zone the prose names as guarded by `boundary-check.py` is actually guarded.

WHY THIS EXISTS
---------------
`SECURITY.md` and `hooks/README.md` describe what `boundary-check.py` blocks.
The retirement of `records/references/` on 2026-09-01 removed the zone from
`ZONE_RE` in the hook and left two prose readers behind — they kept promising a
guarantee the code no longer offers. A security document that overstates a
control is worse than one that omits it: it stops the reader from asking for the
guard they still need.

The test that would have caught this was missing, so the drift was invisible
between the retirement and the audit that filed kit issue #19. This is that
test. It parses the two prose sites for zone paths in the sentence naming
`boundary-check.py`, and asks the real hook whether writing into each is
blocked. A zone the prose names and the hook does not match is a broken
promise, and the test fails on it — the same shape as
`test_hook_declarations_agree.py`, where a hook declared in one settings file
and not the other reads as a working guard.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# A zone token looks like `slug/` or `nested/slug/`. The trailing `/` is what
# makes it a directory claim; `(?!\w)` refuses tokens whose trailing `/` is
# followed by another word — `Edit/Write` (event name) fails because `Write`
# comes right after the slash. Backticks are optional, because
# `hooks/README.md`'s table cell writes the paths bare.
_ZONE_RE = re.compile(r"`?([A-Za-z][A-Za-z0-9._-]*(?:/[A-Za-z0-9._-]+)*/)`?(?!\w)")


def _hook_boundary_check() -> Path:
    found = sorted(p for p in (REPO / "hooks").glob("boundary-check.*")
                   if p.suffix in (".sh", ".py"))
    assert len(found) == 1, f"expected one boundary-check implementation, found {found}"
    return found[0]


def _run_write(path: str) -> int:
    """Return the hook's exit code for a Write of `path`. 2 = block, 0 = allow."""
    hook = _hook_boundary_check()
    cmd = ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Write",
               "tool_input": {"file_path": path}}
    return subprocess.run(cmd, input=json.dumps(payload), capture_output=True,  # noqa: PLW1510
                          text=True, cwd=REPO).returncode


def _zones_named_by(path: Path) -> set[str]:
    """Every backticked zone path on lines that name `boundary-check` in `path`.

    A "line" here is a paragraph-like unit split on newlines: SECURITY.md
    declares the zones on a single Markdown bullet, and `hooks/README.md`
    declares them on a single table row. Both fit on one line.
    """
    zones: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if "boundary-check" not in line:
            continue
        zones.update(_ZONE_RE.findall(line))
    return zones


PROSE_SITES = (REPO / "SECURITY.md", REPO / "hooks" / "README.md")


def test_the_prose_names_at_least_one_zone() -> None:
    """If prose stops naming ANY zone, the test above becomes vacuous.

    A test that finds nothing passes silently, and the whole guard rests on
    "the prose still mentions the boundary". Assert that up front so a future
    reword does not turn this file into a no-op.
    """
    total = sum(len(_zones_named_by(site)) for site in PROSE_SITES)
    assert total > 0, (
        "no backticked zone paths found on any line naming boundary-check in "
        f"{[str(s.relative_to(REPO)) for s in PROSE_SITES]} — the parser or the "
        "prose changed shape; update the test rather than deleting it"
    )


@pytest.mark.parametrize("site", PROSE_SITES, ids=lambda p: str(p.relative_to(REPO)))
def test_every_zone_the_prose_names_is_actually_blocked(site: Path) -> None:
    """A zone in the prose the hook does not match is a broken promise.

    The failure mode this closes: `SECURITY.md:36` and `hooks/README.md:21`
    each name `records/references/` alongside `study-material/`, and
    `ZONE_RE` in `hooks/boundary-check.py` matches only the second. The
    reader believes both are guarded; the code guards one.
    """
    unmatched = sorted(z for z in _zones_named_by(site) if _run_write(f"{z}file.md") != 2)
    assert not unmatched, (
        f"{site.relative_to(REPO)} names zones that boundary-check does NOT "
        f"block: {unmatched}. Either the prose is stale (fix the prose) or "
        f"the hook regressed (fix the hook). Do not silence this test."
    )

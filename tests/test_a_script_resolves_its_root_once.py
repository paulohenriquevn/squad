"""A value a script already holds must not be computed again.

Two correct expressions and a wrong order, with no line a reviewer can point at. Every
other defect this week had a wrong thing to inspect — a dead path, a stale count, a fixed
depth. This one has none: either resolution reads fine alone, and only running the script
in the order it runs reveals it.

Measured 2026-09-16, twice, in two files:

  run_slice_tests.sh   re-resolved BASH_SOURCE after `cd "$REPO_ROOT"`, so the tree
                       banner printed "the kit's own repository at ." from INSIDE an
                       install — the one thing it exists to distinguish, backwards
  attest_plan.sh       resolved KIT_ROOT after `cd "$PROJECT_DIR"` and then again 24
                       lines later; with CLAUDE_PROJECT_DIR set elsewhere — the hook
                       environment — the first came out EMPTY

`BASH_SOURCE[0]` is relative when a script is invoked by a relative path, so a `cd`
between the invocation and the resolution silently breaks it.

Order is not a property a reader can check. **"Resolved once" is** — which is why this
test asserts the count rather than the sequence, and why the property is worth more than
either fix.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_RESOLUTION = re.compile(r'\$\(cd "\$\(dirname "\$\{BASH_SOURCE\[0\]\}"\)')


def _scripts() -> list[Path]:
    out: list[Path] = []
    for base in ("mechanisms", "hooks", "skills"):
        directory = _ROOT / base
        if directory.is_dir():
            out.extend(p for p in directory.rglob("*.sh") if "tests" not in p.parts)
    return out


def test_no_script_resolves_its_own_root_twice() -> None:
    offenders = []
    for path in _scripts():
        body = path.read_text(encoding="utf-8", errors="replace")
        count = len(_RESOLUTION.findall(body))
        if count > 1:
            offenders.append(f"{path.relative_to(_ROOT)} ({count}x)")
    assert not offenders, (
        "these resolve their own location more than once; a `cd` between the two makes "
        "the later one resolve against the wrong directory, and BOTH expressions read "
        f"correctly in isolation: {offenders}")


def test_the_sweep_actually_covers_shell_scripts() -> None:
    """A guard whose glob lost its reach reports a clean sweep over nothing — this
    kit's own failure mode, and the reason this assertion exists beside the one above."""
    scripts = _scripts()
    assert len(scripts) >= 3, f"the sweep found {len(scripts)} shell scripts"
    assert any(_RESOLUTION.search(p.read_text(encoding="utf-8", errors="replace"))
               for p in scripts), \
        "no script matches the pattern at all, so the guard above proves nothing"

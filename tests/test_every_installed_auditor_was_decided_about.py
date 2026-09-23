"""A plugin can be installed, uncommissioned, and unmentioned — decided by nobody.

`rules/review-auditors.txt` maps a domain to the plugin that audits it, and it is careful
about the ones it leaves out. `loop-project-purge` and `loop-pentest-audit` are refused with
a reason — *neither belongs on an automatic path, and a review that silently deleted code or
probed a host would be a far worse failure than the one this file fixes.* Seven more carry a
collective reason: *no domain here derives them from a change.* Two carry their own:
`loop-deadcode-audit` would commission a second answer to a question `/code-quality` already
asks, and `loop-license-audit` was also unmappable until its CLI was fixed.

Measured 2026-09-22: seventeen `loop-*` plugins installed, seven commissioned, ten idle —
and nine of the ten have a reason. `loop-system-cartography` appears in no rule in this kit
at all.

That is not a mapping somebody rejected. It is a capability nobody weighed, and the
difference matters because the file is otherwise a record of decisions: a reader counting
reasons concludes every absence was chosen, and one of them was not.

WHAT THIS DOES NOT ASSERT. Not that every installed plugin should be commissioned — most
should not, and the file argues each case. It asserts that every one has been ANSWERED, in
the file where the answers live.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "conventions"))

REGISTRY = _ROOT / "rules" / "review-auditors.txt"


def _installed() -> set[str]:
    from installed_plugins import load

    return {p.name for p in load().values() if p.name.startswith("loop-")}


def _named_in_registry() -> str:
    return REGISTRY.read_text(encoding="utf-8")


def test_every_installed_auditor_appears_in_the_registry() -> None:
    """Commissioned in a row, or named in the prose that says why not."""
    installed = _installed()
    if not installed:
        pytest.skip("no loop-* plugins installed on this machine; nothing to decide about")

    body = _named_in_registry()
    unmentioned = sorted(name for name in installed if name not in body)

    assert unmentioned == [], (
        f"{unmentioned} are installed and appear nowhere in {REGISTRY.name}. Each is a "
        "capability this project has and nobody weighed — and a reader counting the "
        "reasons in this file concludes every absence was chosen"
    )


def test_the_registry_still_commissions_something() -> None:
    """THE CONTROL. A file that mentions every plugin and maps none would pass the test
    above and answer nothing, which is the failure mode of asserting on mentions."""
    rows = [l for l in _named_in_registry().splitlines()
            if l.strip().startswith("auditor")]

    assert rows, "no auditor row at all; the registry names plugins and commissions none"

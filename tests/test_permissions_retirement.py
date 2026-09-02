"""A union can add a rule and can never take one away.

`install.sh` merged the kit's permission lists into a consumer's by union. So a
rule the kit retired stayed in every consumer that already had a
`settings.json` — a retirement that is applied, released, and inert everywhere
except a fresh install. The same shape `defaultMode` had, in the other direction:
that one was closed for scalars and left open for lists.

It is not fixable by comparing two lists. A rule in the consumer and not in the
kit is EITHER something the kit retired OR something the project added, and those
must not share an outcome. The missing term is the base — what the kit shipped
last time — so the install now records it.

Measured on 2026-09-02: the credential globs were rewritten from `Read(**/*secret*)`
to named credential forms, and without this the retired glob would have stayed
denied in all seventeen consumers alongside its replacements. Filed as kit#16 by
an agent running inside the fleet.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_INSTALL = _REPO / "mechanisms" / "distribution" / "install.sh"

RETIRED = "Read(**/*a-glob-the-kit-no-longer-ships*)"
PROJECT_OWN = "Bash(a-command-only-this-project-runs)"


def _consumer(tmp_path: Path, *, deny: list[str], base: dict | None) -> Path:
    root = tmp_path / "consumer"
    eco = root / ".claude"
    for tree in ("skills", "rules", "hooks", "commands", "mechanisms", "squad"):
        (eco / tree).mkdir(parents=True, exist_ok=True)
    (eco / "settings.json").write_text(
        json.dumps({"permissions": {"deny": deny, "allow": ["Read"]}}, indent=2),
        encoding="utf-8")
    if base is not None:
        (eco / ".kit-permissions.json").write_text(json.dumps(base, indent=2),
                                                   encoding="utf-8")
    return root


def _install(root: Path) -> str:
    done = subprocess.run(["bash", str(_INSTALL), str(root), "--merge"],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr[-800:]
    return done.stdout


def _deny(root: Path) -> list[str]:
    return json.loads((root / ".claude" / "settings.json").read_text(
        encoding="utf-8"))["permissions"]["deny"]


def test_a_rule_the_kit_retired_is_removed_from_the_consumer(tmp_path: Path) -> None:
    root = _consumer(tmp_path, deny=[RETIRED, PROJECT_OWN],
                     base={"deny": [RETIRED], "allow": []})

    _install(root)

    assert RETIRED not in _deny(root), "the kit shipped it, then stopped; it should go"


def test_a_rule_the_project_added_is_never_removed(tmp_path: Path) -> None:
    """The worse error by far. A consumer's own rule is not the kit's to delete,
    and it looks identical to a retired one unless the base says otherwise."""
    root = _consumer(tmp_path, deny=[RETIRED, PROJECT_OWN],
                     base={"deny": [RETIRED], "allow": []})

    _install(root)

    assert PROJECT_OWN in _deny(root)


def test_with_no_recorded_base_nothing_is_removed(tmp_path: Path) -> None:
    """First install under this scheme: every existing entry is indistinguishable
    from a project's own. Removing on a guess would delete project rules across
    every consumer at once, which is worse than the defect being fixed."""
    root = _consumer(tmp_path, deny=[RETIRED, PROJECT_OWN], base=None)

    _install(root)

    assert RETIRED in _deny(root) and PROJECT_OWN in _deny(root)


def test_the_base_records_what_the_kit_shipped_not_what_the_consumer_ended_with(
        tmp_path: Path) -> None:
    """Recording the merged result would make every project rule look like the
    kit's, and hand the next install permission to delete it."""
    root = _consumer(tmp_path, deny=[PROJECT_OWN], base={"deny": [], "allow": []})

    _install(root)
    base = json.loads((root / ".claude" / ".kit-permissions.json").read_text(encoding="utf-8"))

    assert PROJECT_OWN not in base["deny"], "a project rule entered the kit's record"
    kit = json.loads((_REPO / "settings.plugin.json").read_text(encoding="utf-8"))
    assert set(base["deny"]) == set(kit["permissions"]["deny"])


def test_retirement_survives_a_second_install(tmp_path: Path) -> None:
    """The base is rewritten each run; a rule must not come back on the next one."""
    root = _consumer(tmp_path, deny=[RETIRED, PROJECT_OWN],
                     base={"deny": [RETIRED], "allow": []})

    _install(root)
    _install(root)

    assert RETIRED not in _deny(root)
    assert PROJECT_OWN in _deny(root)


def test_the_removal_is_reported_rather_than_silent(tmp_path: Path) -> None:
    """An install that quietly deletes permission rules is an install nobody can
    audit — and this one deletes by design."""
    root = _consumer(tmp_path, deny=[RETIRED, PROJECT_OWN],
                     base={"deny": [RETIRED], "allow": []})

    out = _install(root)

    assert "retired" in out.lower(), out[-400:]

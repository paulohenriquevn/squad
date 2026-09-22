r"""A hook wired to a file that is gone is a gate that quietly stopped.

MEASURED BY A CONSUMER, 2026-09-21, and routed here.

`hooks/validate-command.sh` was deleted from this kit in `260892f` — "scripts/ becomes
mechanisms/, the hooks become Python". An install made before that commit still carried
the shell copy AND still had it wired in `settings.json`. The consumer measured the two
against each other: **the retired `.sh` diverges from the live `.py` in 2 of 36
payloads**, and both divergences are permissive — it allows `git stash` (forbidden while
worktrees exist) and `--force-with-lease` on `workspace`.

So the upgrade path left a gate running that the kit had already replaced, and the
replacement's stricter rules were not in force.

WHY THE BASELINE DOES NOT COVER THIS

`merge_settings.py` records what the kit shipped in `.kit-hooks.json` so a withdrawn hook
can be removed without deleting a project's own — and that reasoning is right: "with no
record nothing is removed: on a first install every entry is indistinguishable from a
project's own, and deleting a project's is the worse error by far."

But the baseline only exists from 2026-09-02. An install older than that has none, so
nothing is ever removed, and a hook can point at a file that has not existed for weeks.

A missing FILE needs no baseline to detect. Whoever wired it, a hook whose command names
something that is not there does not run — and a gate that does not run is
indistinguishable, from the outside, from a gate that passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "mechanisms" / "gates"))

from check_wired_hooks import check_wired_hooks  # noqa: E402


def _settings(tmp_path: Path, hooks: dict) -> Path:
    eco = tmp_path / ".claude"
    (eco / "hooks").mkdir(parents=True)
    (eco / "settings.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    return eco


def _hook(command: str) -> dict:
    return {"PreToolUse": [{"matcher": "Bash",
                            "hooks": [{"type": "command", "command": command}]}]}


def test_a_hook_pointing_at_a_missing_file_is_reported(tmp_path: Path) -> None:
    """The consumer's exact shape: a `.sh` the kit deleted, still wired."""
    eco = _settings(tmp_path, _hook("python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validate-command.sh"))

    report = check_wired_hooks(eco)

    assert report.exit_code() == 1
    assert any("validate-command.sh" in p for p in report.problems), report.problems


def test_a_hook_pointing_at_a_present_file_holds(tmp_path: Path) -> None:
    eco = _settings(tmp_path, _hook("python3 $CLAUDE_PROJECT_DIR/.claude/hooks/live.py"))
    (eco / "hooks" / "live.py").write_text("#\n", encoding="utf-8")

    assert check_wired_hooks(eco).exit_code() == 0


def test_a_command_that_names_no_file_is_not_a_finding(tmp_path: Path) -> None:
    """Not every hook runs a script. A shell one-liner is wired on purpose and there is
    no file to look for — reporting it would make the check noise, and noise is what
    gets a check switched off."""
    eco = _settings(tmp_path, _hook("echo hello"))

    assert check_wired_hooks(eco).exit_code() == 0


def test_no_settings_is_unmeasured_not_clean(tmp_path: Path) -> None:
    """`2`. An install this cannot read is not one whose hooks are fine."""
    (tmp_path / ".claude").mkdir()

    assert check_wired_hooks(tmp_path / ".claude").exit_code() == 2


def test_this_kit_wires_nothing_that_is_gone() -> None:
    """The kit's own settings, held to the same line."""
    report = check_wired_hooks(REPO)

    assert report.exit_code() in (0, 2), report.problems

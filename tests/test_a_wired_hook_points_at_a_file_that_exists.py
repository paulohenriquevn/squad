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


def test_this_kit_ships_no_shell_hook_a_python_one_supersedes() -> None:
    """The source half of the same defect: a consumer can only wire what the kit ships.

    `check_wired_hooks` catches the pair in an INSTALL, which is where it was measured —
    but an install inherits its hooks from here. The two enforcers that disagreed about
    the trunk (#154) were `validate-command.sh` and `validate-command.py`, and the shell
    one left in `260892f`; nothing since then has pinned that it stays gone. Re-adding a
    `.sh` beside a `.py` would reintroduce the divergence at the source, and every
    install afterwards would carry it while this kit's own gate ran clean.

    Asserted as "no pair", not "no shell hook at all": a lone shell hook is a deliberate
    choice the gate also declines to report, and this test must not be stricter than the
    gate it protects.
    """
    hooks = REPO / "hooks"
    paired = sorted(
        f.name for f in hooks.glob("*.sh") if f.with_suffix(".py").exists()
    )

    assert paired == [], (
        f"{paired} ship beside a `.py` sibling that supersedes them; a consumer that "
        "wires both runs both, and the retired one enforces the rules it had when it "
        "was retired"
    )


# ── presence is not currency ─────────────────────────────────────────────────
#
# Measured on a real install, 2026-09-22, by the session that owns it: NINE hooks wired
# as BOTH `.sh` and `.py` at once — validate-command, boundary-check, post-edit-check,
# english-only-check, precompact-preserve, stop-validation and three more. The gate
# answered `HOLDS: all 18 wired hook(s) point at a file that exists`, exit 0.
#
# It was right about its title and wrong about its purpose. The `.sh` DOES exist, so it
# does point at a file that is there — and the defect the docstring describes, a retired
# hook still wired beside its replacement, sailed through under a HOLDS.
#
# The same session was blocked three times that day by those hooks, once by the retired
# `.sh` specifically: both were live and both were firing.
#
# AND THE COVERAGE WAS NEVER MEASURED. This gate passed in the kit (9 hooks, all `.py`)
# and in a fresh install (no `.sh` at all). Neither has the defect. A gate exercised only
# where its defect cannot occur is a gate whose coverage nobody checked — which is the
# thing this kit says about tests and had not said about itself.


def _both_wired(tmp_path: Path) -> Path:
    eco = tmp_path / ".claude"
    (eco / "hooks").mkdir(parents=True)
    for name in ("validate-command.py", "validate-command.sh"):
        (eco / "hooks" / name).write_text("#\n", encoding="utf-8")
    (eco / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [
            {"type": "command", "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validate-command.py"},
            {"type": "command", "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/validate-command.sh"},
        ]}]}}), encoding="utf-8")
    return eco


def test_a_retired_hook_wired_beside_its_replacement_is_reported(tmp_path: Path) -> None:
    """Both files exist. That is exactly why presence cannot answer this."""
    report = check_wired_hooks(_both_wired(tmp_path))

    assert report.exit_code() == 1, "nine of these passed as HOLDS on a real install"
    assert any("supersedes" in p for p in report.problems), report.problems


def test_the_report_names_which_one_to_unwire(tmp_path: Path) -> None:
    """The reader's next move is to remove one line from settings.json, and which line
    it is must not be left as an exercise."""
    report = check_wired_hooks(_both_wired(tmp_path))

    blob = " ".join(report.problems)
    assert "validate-command.sh" in blob, blob
    assert "validate-command.py" in blob, blob


def test_a_lone_shell_hook_is_not_a_finding(tmp_path: Path) -> None:
    """A project's OWN shell hook has no `.py` beside it and is nobody's leftover.
    Reporting it would make the gate noise, and noise is what gets a gate switched off."""
    eco = tmp_path / ".claude"
    (eco / "hooks").mkdir(parents=True)
    (eco / "hooks" / "my-own-thing.sh").write_text("#\n", encoding="utf-8")
    (eco / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command",
         "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/my-own-thing.sh"}]}]}}),
        encoding="utf-8")

    assert check_wired_hooks(eco).exit_code() == 0

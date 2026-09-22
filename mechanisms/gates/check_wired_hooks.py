#!/usr/bin/env python3
"""Does every hook this install wires point at a file that is actually there?

    python3 mechanisms/gates/check_wired_hooks.py
    python3 mechanisms/gates/check_wired_hooks.py --root <project>/.claude --json

## The defect, measured by a consumer and routed here

`hooks/validate-command.sh` left this kit in `260892f` — "scripts/ becomes mechanisms/,
the hooks become Python". An install predating that commit still carried the shell copy
AND still had it wired in `settings.json`. Measured against the live `.py`: **the retired
shell hook diverges in 2 of 36 payloads, and both divergences are permissive** — it
allows `git stash` (forbidden while worktrees exist) and `--force-with-lease` on
`workspace`.

The upgrade path left a gate running that the kit had already replaced, with the
replacement's stricter rules not in force. Nothing said so, because nothing looked.

## Why `.kit-hooks.json` does not cover it

`merge_settings.py` records what the kit shipped so a withdrawn hook can be removed
without deleting a project's own, and its reasoning holds: *"with no record nothing is
removed: on a first install every entry is indistinguishable from a project's own, and
deleting a project's is the worse error by far."*

That baseline exists only from 2026-09-02. An older install has none, so nothing is ever
removed — and a hook can point at a file that has not existed for weeks.

A missing FILE needs no baseline. Whoever wired it, a hook whose command names something
that is not there does not run, and a gate that does not run is indistinguishable from
outside from a gate that passes. This reports; it never edits a consumer's settings.

## What is deliberately not a finding

A command that names no file at all. Not every hook runs a script — a shell one-liner is
wired on purpose, there is nothing to look for, and reporting it would make the check
noise. Noise is what gets a check switched off.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _contract import add_root  # noqa: E402 — sibling module, path set above

OK, FOUND, UNMEASURABLE = 0, 1, 2

#: A token that looks like a path to a script rather than a flag or a bare command.
_SCRIPT_RE = re.compile(r"[\w$./{}-]+\.(?:py|sh|mjs|cjs|js)$")

#: Variables an install writes into a hook command, mapped to the tree being checked.
_VARS = ("$CLAUDE_PROJECT_DIR/.claude/", "${CLAUDE_PROJECT_DIR}/.claude/",
         "$CLAUDE_PLUGIN_ROOT/", "${CLAUDE_PLUGIN_ROOT}/",
         "$CLAUDE_PROJECT_DIR/", "${CLAUDE_PROJECT_DIR}/")


@dataclass
class WiredHooksReport:
    settings: str = ""
    wired: int = 0
    missing: list[str] = field(default_factory=list)
    unreadable: str = ""

    @property
    def problems(self) -> list[str]:
        return [f"{event}: `{cmd}` names `{target}`, which is not there — this hook "
                f"does not run, and a gate that does not run reads from outside "
                f"exactly like one that passes"
                for event, cmd, target in (m.split("\x1f") for m in self.missing)]

    def exit_code(self) -> int:
        if self.unreadable or not self.settings:
            return UNMEASURABLE
        return FOUND if self.missing else OK


def _script_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    return [t for t in tokens if _SCRIPT_RE.search(t)]


def _resolve(token: str, eco: Path) -> Path:
    """Where the token points, with the install's own variables expanded."""
    for var in _VARS:
        if token.startswith(var):
            return eco / token[len(var):]
    path = Path(token)
    return path if path.is_absolute() else eco / token


def check_wired_hooks(eco: Path) -> WiredHooksReport:
    report = WiredHooksReport()
    settings = Path(eco) / "settings.json"
    if not settings.is_file():
        return report
    report.settings = str(settings)
    try:
        payload = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        report.unreadable = str(error)
        return report

    for event, groups in (payload.get("hooks") or {}).items():
        for group in groups or []:
            for hook in (group or {}).get("hooks", []) or []:
                command = str((hook or {}).get("command", ""))
                if not command:
                    continue
                report.wired += 1
                for token in _script_tokens(command):
                    target = _resolve(token, Path(eco))
                    if not target.exists():
                        report.missing.append(f"{event}\x1f{command}\x1f{token}")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_root(ap)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = check_wired_hooks(Path(args.root))
    code = report.exit_code()

    if args.json:
        print(json.dumps({"settings": report.settings, "wired": report.wired,
                          "problems": report.problems, "exit_code": code}, indent=2))
        return code

    if code == UNMEASURABLE:
        why = (f"settings.json could not be parsed: {report.unreadable}"
               if report.unreadable else "no settings.json under the tree given")
        print(f"UNCHECKED: {why}, so no hook was examined and nothing was swept.",
              file=sys.stderr)
        return code
    if report.missing:
        print(f"FAILS: {len(report.missing)} wired hook(s) point at a file that is gone")
        for problem in report.problems:
            print(f"  - {problem}")
        return code

    print(f"HOLDS: all {report.wired} wired hook(s) point at a file that exists.")
    return code


if __name__ == "__main__":
    sys.exit(main())

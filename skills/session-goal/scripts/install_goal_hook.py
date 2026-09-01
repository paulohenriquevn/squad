#!/usr/bin/env python3
"""Arm or clear the session-goal Stop hook — the part `/goal` could not automate.

Writes two things and nothing else:

  - `.claude/session-goal.json`  — the goal state (which milestones, block counter)
  - a Stop hook in `.claude/settings.local.json` invoking check_goal_met.py

`settings.local.json` on purpose: personal and gitignored, so arming a goal never
lands in a teammate's checkout. Existing settings are merged, never replaced — a
hook that clobbers a permissions block would be a worse bug than the one it fixes.

Usage:
    python3 install_goal_hook.py --milestones M2 M3 [--project-root .] [--max-blocks 40]
    python3 install_goal_hook.py --milestones M27 --roadmap ../outro-repo/ROADMAP.md \\
                                 --acceptance-dir ../outro-repo/records/acceptance
    python3 install_goal_hook.py --clear [--project-root .]

Exit codes:
    0 — armed or cleared
    2 — bad argument, unreadable settings file, or a path that does not resolve
        (roadmap / acceptance dir) — see --force
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HOOK_MARKER = "session-goal/scripts/check_goal_met.py"
DEFAULT_MAX_BLOCKS = 40
#: Canonico: o records mora DENTRO de .claude/ (plugin install). O layout
#: standalone -- the kit's own repo -- is the only one where it sits at the root.
#: Choosing wrong does not break loudly: it creates a second empty records beside the
#: real, e os artefatos passam a se perder entre os dois.
PLUGIN_ACCEPTANCE_DIR = ".claude/records/acceptance"
STANDALONE_ACCEPTANCE_DIR = "records/acceptance"


def default_acceptance_dir(root: Path) -> str:
    """Resolve the canonical records for this project's layout."""
    if (root / ".claude" / "records").exists():
        return PLUGIN_ACCEPTANCE_DIR
    if (root / ".claude").exists():
        return PLUGIN_ACCEPTANCE_DIR  # plugin install; the scaffold is yet to be created
    return STANDALONE_ACCEPTANCE_DIR


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    return json.loads(raw)


def _strip_our_hook(settings: dict) -> dict:
    """Remove only OUR Stop hook, leaving every other hook untouched."""
    stop_entries = settings.get("hooks", {}).get("Stop")
    if not stop_entries:
        return settings

    kept_entries = []
    for entry in stop_entries:
        kept_hooks = [
            h for h in entry.get("hooks", [])
            if HOOK_MARKER not in str(h.get("command", ""))
        ]
        if kept_hooks:
            kept_entries.append({**entry, "hooks": kept_hooks})

    if kept_entries:
        settings["hooks"]["Stop"] = kept_entries
    else:
        settings["hooks"].pop("Stop", None)
        if not settings["hooks"]:
            settings.pop("hooks", None)
    return settings


def _acceptance_path_declared(root: Path) -> tuple[bool, str]:
    """A viable route to ACCEPTED must exist BEFORE a goal is armed.

    Arming a gate whose condition nobody can satisfy is a trap: it blocks every
    stop attempt until the ceiling, and each block looks like a legitimate verdict.
    The project therefore declares how its released delivery is reached; without
    that declaration the goal is refused rather than armed into a dead end.
    """
    declaration = root / ".claude" / "rules" / "acceptance-target.txt"
    if not declaration.exists():
        return False, f"{declaration} does not exist — declare how the published delivery is reached."

    keys = {}
    for line in declaration.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, _, v = line.partition("=")
            keys[k.strip()] = v.strip()

    missing = [k for k in ("kind", "target") if not keys.get(k)]
    if missing:
        return False, (
            f"{declaration} does not declare {' and '.join(missing)}. Without that /acceptance "
            "has no way to reach the delivery, and the goal would be unsatisfiable."
        )
    return True, f"{keys['kind']} → {keys['target']}"


def _milestones_have_dod(roadmap_path: Path, milestones: list[str]) -> list[str]:
    """Milestones whose Definition of done is missing — acceptance has no criteria."""
    import re

    text = roadmap_path.read_text(encoding="utf-8")
    headers = list(re.finditer(r"^###\s+(M\d+)\s+[—\-]{1,2}\s+\[[ x]\]", text, re.MULTILINE))
    without = []
    for wanted in milestones:
        for index, match in enumerate(headers):
            if match.group(1) != wanted:
                continue
            end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
            block = text[match.end():end]
            if not re.search(r"^\*\*Definition of done[^*]*:\*\*", block, re.MULTILINE) or \
               not re.search(r"^-\s+\[[ x]\]", block, re.MULTILINE):
                without.append(wanted)
            break
        else:
            without.append(wanted)
    return without


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--milestones", nargs="*", default=[])
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--roadmap", default="ROADMAP.md")
    parser.add_argument(
        "--acceptance-dir",
        default=None,
        help=(
            "Where cycle-acceptance writes its records, relative to --project-root. "
            "Defaults to the canonical .claude/records/acceptance. Must stay INSIDE "
            "the project — consumers are autonomous and do not share a records."
        ),
    )
    parser.add_argument("--max-blocks", type=int, default=DEFAULT_MAX_BLOCKS)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Arm even when the roadmap or acceptance directory does not resolve.",
    )
    args = parser.parse_args()

    root = args.project_root.resolve()
    claude_dir = root / ".claude"
    settings_path = claude_dir / "settings.local.json"
    state_path = claude_dir / "session-goal.json"

    try:
        settings = _load_settings(settings_path)
    except json.JSONDecodeError as exc:
        print(f"{settings_path} is not valid JSON ({exc}) — refusing to touch it.", file=sys.stderr)
        return 2

    if args.clear:
        settings = _strip_our_hook(settings)
        claude_dir.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        existed = state_path.exists()
        state_path.unlink(missing_ok=True)
        print(f"cleared: Stop hook removed; goal state {'deleted' if existed else 'was absent'}.")
        return 0

    if not args.milestones:
        print("nothing to arm — pass --milestones M<N> [...] or --clear.", file=sys.stderr)
        return 2

    # Resolve BEFORE arming. A gate pointing at a roadmap or an acceptance directory
    # that does not exist blocks forever for a false reason ("acceptance never ran")
    # that reads as a legitimate verdict. Discovering that later costs a
    # whole session; finding out now costs one line.
    acceptance_rel = args.acceptance_dir or default_acceptance_dir(root)
    roadmap_path = (root / args.roadmap).resolve()
    acceptance_path = (root / acceptance_rel).resolve()

    problems = []

    # Autonomy: each project has ITS OWN records and ITS OWN roadmap. A gate
    # pointing outside couples two autonomous repos and makes one's milestone depend
    # on the other's state -- exactly what the architecture forbids.
    for label, path in (("roadmap", roadmap_path), ("acceptance directory", acceptance_path)):
        if root not in path.parents and path != root:
            problems.append(
                f"{label} is OUTSIDE the project: {path}. Consumers are autonomous — "
                "each has its own ROADMAP.md and its own .claude/records/."
            )
    if not roadmap_path.exists():
        problems.append(f"roadmap does not exist: {roadmap_path}")
    if not acceptance_path.exists():
        problems.append(
            f"acceptance directory does not exist: {acceptance_path} "
            "(use --acceptance-dir when the cycle's artifacts live in another repo)"
        )

    # A goal can only be armed when a route to ACCEPTED exists. Two conditions
    # mecanicamente verificaveis: a entrega tem caminho declarado, e cada milestone
    # has a Definition of done (which is where /acceptance takes the criteria from).
    if roadmap_path.exists():
        without_dod = _milestones_have_dod(roadmap_path, args.milestones)
        if without_dod:
            problems.append(
                f"no Definition of done: {', '.join(without_dod)}. /acceptance reads those bullets "
                "AS acceptance criteria — without them the milestone can never be accepted."
            )

    declared, detail = _acceptance_path_declared(root)
    if not declared:
        problems.append(f"no route to ACCEPTED — {detail}")

    if problems and not args.force:
        for problem in problems:
            print(f"BLOCKED session-goal: {problem}", file=sys.stderr)
        print(
            "Nothing was armed. A goal with no route to ACCEPTED is a trap: it blocks every "
            "attempt to stop until the ceiling, and each block reads as a legitimate verdict. "
            "Fix what is above, or pass --force taking that risk knowingly.",
            file=sys.stderr,
        )
        return 2

    gate = Path(__file__).resolve()
    claude_dir.mkdir(parents=True, exist_ok=True)

    state_path.write_text(json.dumps({
        "milestones": args.milestones,
        "roadmap": args.roadmap,
        "acceptance_dir": acceptance_rel,
        "blocks": 0,
        "max_blocks": args.max_blocks,
    }, indent=2) + "\n", encoding="utf-8")

    settings = _strip_our_hook(settings)  # idempotent: never stack duplicates
    command = (
        f'python3 "{gate.parent / "check_goal_met.py"}" '
        f'--state "{state_path}" --project-root "{root}"'
    )
    settings.setdefault("hooks", {}).setdefault("Stop", []).append({
        "hooks": [{
            "type": "command",
            "command": command,
            "timeout": 30,
            "statusMessage": "session-goal: checking acceptance evidence",
        }]
    })
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    print(f"armed: {' '.join(args.milestones)}")
    print(f"  roadmap    : {roadmap_path}{'' if roadmap_path.exists() else '   <== DOES NOT EXIST (--force)'}")
    print(f"  acceptance : {acceptance_path}{'' if acceptance_path.exists() else '   <== DOES NOT EXIST (--force)'}")
    print(f"  state      : {state_path}")
    print(f"  hook       : {settings_path}")
    print(f"  target     : {detail}")
    print(f"  ceiling    : {args.max_blocks} blocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())

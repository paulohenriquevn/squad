#!/usr/bin/env python3
"""Confront `rules/squad-map.md` with the directory it claims to describe.

    python3 mechanisms/gates/check_squad_map.py [--root .] [--json]

WHY A CHECKER AND NOT TRUST
---------------------------
`skills/map.md` carries the lesson, having learned it twice: an index is the one
document nothing forces you to open when you add a file, so it drifts by default
and **reads as complete while it does**. The second drift is in the CHANGELOG —
four skills with zero mentions in any entry point, on disk, passing every
validator, unreachable by any discovery path.

This map is worse if it rots, because it is injected at SessionStart. A wrong map
in the agent's opening context is not a stale document somebody might open; it is
a false premise every later decision rests on.

WHAT IT CHECKS, AND WHAT IT DELIBERATELY DOES NOT
-------------------------------------------------
`check_skill_map.py` already owns the skill inventory, and duplicating it would
create two checkers that can disagree about one fact. This one checks what only
THIS map claims:

  1. phases        — every phase in `cycle-phases.txt` appears          (one direction)
  2. cycles        — every `rules/cycle-*.md` is named, and no phantom  (both)
  3. kit agents    — every versioned `agents/*.md` is named             (one direction)
  4. hooks         — every `hooks/*.py|sh` is named, and no phantom     (both)

**Two are one-directional, and that is a limit rather than an oversight.** A map
missing something under-reports; a map naming a file that was deleted sends a
reader looking for nothing, which is the quieter failure and worth catching. But
catching it needs a name shape unambiguous enough to extract from prose. `*.py`/`*.sh`
and `cycle-*` are; a phase name is an ordinary uppercase word and an agent name an
ordinary hyphenated one, so any pattern wide enough to find an invented one also
matches half the document. Claiming to check those inverses would be fabricated
precision, so they are checked against disk in one direction and say so here.

Exit codes:
  0 — the map agrees with the directory
  1 — at least one divergence
  2 — the map or a source of truth could not be read
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAP_REL = "rules/squad-map.md"


def _find_ecosystem_dir(start: Path) -> Path | None:
    """The directory holding `rules/`, whichever of the three layouts is on disk."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "conventions"))
    try:
        from ecosystem_utils import find_ecosystem_dir
    except ImportError:
        return None
    return find_ecosystem_dir(start, require=False)

#: The kit's own agents are the ones `.gitignore` excepts by name. Deriving them
#: from `git ls-files` rather than restating the list keeps this from becoming a
#: fourth copy — `tests/kit_agents.py` records what three copies already cost.
def _kit_agents(root: Path) -> set[str]:
    """The agents the KIT ships — never the project's domain specialists.

    The install manifest answers this exactly, and is preferred: it is written by
    the installer and states its own rule, *anything not here is the project's*.

    `git ls-files agents/` is the fallback, and it is only correct in the kit's own
    repository, where the derived specialists are gitignored. In a consumer the
    project versions ALL of them, so the fallback returns the specialists too and
    the map is asked to name agents it has no business knowing about — measured on
    a consumer 2026-09-02, which reported two of its own domain specialists as
    absent from a map that describes the kit.
    """
    manifest = root / ".kit-manifest.txt"
    if manifest.is_file():
        return {
            Path(line).stem
            for raw in manifest.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            for line in [raw.split("#", 1)[0].strip()]
            if line.startswith("agents/") and line.endswith(".md")
            and not line.endswith("README.md")
        }

    import subprocess

    out = subprocess.run(  # noqa: PLW1510
        ["git", "-C", str(root), "ls-files", "agents/"],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        return set()
    return {
        Path(line).stem
        for line in out.stdout.splitlines()
        if line.endswith(".md") and not line.endswith("README.md")
    }


def _declared_phases(root: Path) -> list[str]:
    path = root / "rules" / "cycle-phases.txt"
    names = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "|" not in line:
            continue
        names.append(line.split("|")[0].strip())
    return names


def _cycles(root: Path) -> set[str]:
    return {p.stem for p in (root / "rules").glob("cycle-*.md")}


def _hooks(root: Path) -> set[str]:
    # `.py` AND `.sh`: the hooks migrated to Python on 2026-09-01, and while this
    # globbed only `*.sh` it listed ZERO hooks — so every hook was missing from the
    # map and the checker reported nothing, because an empty set has no absentees.
    # Same shape as the shell-syntax gate and the orphan-verdict sweep found the
    # same day: a glob that lost its reach turns silence into a pass.
    return {p.name for p in (root / "hooks").iterdir()
            if p.is_file() and p.suffix in (".py", ".sh")}


#: Names the map MENTIONS, read out of its prose rather than filtered from disk.
#:
#: The first version of this checker built `mentioned` by filtering the on-disk set
#: — `{h for h in hooks if h in body}` — which makes `mentioned` a subset of
#: `expected` by construction, so `mentioned - expected` was always empty and the
#: `absent_from_disk` direction could never fire. Half the checker was inert while
#: reporting itself green, which is the defect shape this kit exists to catch.
#: `test_a_hook_the_map_invents_is_reported` caught it on the first run.
#:
#: Only two kinds have a name shape unambiguous enough to extract this way. The
#: other two are checked in one direction, and say so.
#: Both suffixes, for the same reason the listing takes both: a pattern that
#: recognised only `.sh` found no mention of any hook once they became Python,
#: and reported every one of them as absent from a map that names them all.
HOOK_MENTION_RE = re.compile(r"\b([a-z][a-z0-9-]*\.(?:sh|py))\b")
CYCLE_MENTION_RE = re.compile(r"\b(cycle-[a-z][a-z-]*)(?!\.txt)\b")


def check(root: Path) -> list[dict]:
    findings: list[dict] = []
    body = (root / MAP_REL).read_text(encoding="utf-8")

    def sweep(kind: str, expected: set[str], mentioned: set[str], hint: str) -> None:
        for missing in sorted(expected - mentioned):
            findings.append({
                "kind": kind, "direction": "absent_from_map", "name": missing,
                "message": f"{kind} `{missing}` exists on disk and the map never names it. {hint}",
            })
        for phantom in sorted(mentioned - expected):
            findings.append({
                "kind": kind, "direction": "absent_from_disk", "name": phantom,
                "message": f"the map names {kind} `{phantom}`, which is not on disk. "
                           "A reader following it finds nothing, which is the quieter failure.",
            })

    # 1. phases — ONE DIRECTION ONLY, and the reason is stated rather than hidden.
    # A phase name is an ordinary uppercase word, so extracting "phases the map
    # mentions" would sweep up BACKLOG_EMPTY, OPEN, NOT and every other shouted
    # token. Claiming to check the inverse with a pattern that loose would be
    # fabricated precision — the failure this kit refuses elsewhere.
    phases = _declared_phases(root)
    named_phases = {p for p in phases if re.search(rf"\b{re.escape(p.upper())}\b", body)}
    sweep("phase", set(phases), named_phases,
          "cycle-phases.txt is the declaration; a map that omits a phase hides a stage of the chain.")

    # 2. cycles — both directions: `cycle-*` is an unambiguous name shape.
    cycles = _cycles(root)
    sweep("cycle", cycles, set(CYCLE_MENTION_RE.findall(body)),
          "every cycle rule is a contract this map exists to place.")

    # 3. the kit's four roles
    # ONE DIRECTION, same reason as phases: an agent name is an ordinary hyphenated
    # word and any pattern wide enough to find an invented one also finds half the
    # prose. The disk is authoritative here.
    agents = _kit_agents(root)
    if agents:
        named_agents = {a for a in agents if a in body}
        sweep("agent", agents, named_agents,
              "an agent absent from the map has no declared position in the flow.")
    else:
        findings.append({
            "kind": "agent", "direction": "unreadable", "name": "-",
            "message": "could not list versioned agents (git unavailable?) — agent check skipped, "
                       "and skipping is reported rather than passed.",
        })

    # 4. hooks — both directions: `*.py`/`*.sh` is an unambiguous name shape.
    sweep("hook", _hooks(root), set(HOOK_MENTION_RE.findall(body)),
          "a hook runs outside the agent turn; one nobody documented is one nobody expects.")

    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    #: `Path.cwd()` was the default until 2026-09-02, and it made this gate
    #: unrunnable in the layout most consumers have: under a `.claude/` install the
    #: cwd is the PROJECT and the map is at `.claude/rules/squad-map.md`, so the
    #: check exited FATAL every time and `verify_ecosystem` reported it as failed.
    #: Measured on a real consumer the day the kit was reinstalled there — it had
    #: never once run outside the kit's own repository.
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = (args.root.resolve() if args.root is not None
            else _find_ecosystem_dir(Path.cwd()) or Path.cwd())
    if not (root / MAP_REL).is_file():
        print(f"FATAL: {MAP_REL} not found under {root}", file=sys.stderr)
        return 2
    try:
        findings = check(root)
    except OSError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
        return 1 if findings else 0

    if not findings:
        print(f"{MAP_REL} agrees with the directory: phases, cycles, agents and hooks all resolve.")
        return 0

    print(f"{MAP_REL} — {len(findings)} divergence(s):")
    for f in findings:
        print(f"  [{f['direction']}] {f['message']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Retire the walls a sponsor delegated, and leave the decision in their place.

Reads a registry, classifies every AWAITING_HUMAN wall through
`delegated_decision`, and — for the delegable ones only — replaces the
`blocked_by` line with the decision that retired it.

WHAT IT REFUSES

It will not touch a wall the classifier retained, it will not act without a
decision AND a rationale for each item, and it writes nothing unless `--apply`
is passed. The default is a report, because the file it edits is a project's
maintenance record and a bad pass over it destroys the reasoning that walled
each item in the first place.

It also refuses to run against a dirty tree unless told otherwise: an edit to
BACKLOG.md mixed into somebody else's uncommitted batch cannot be reverted on
its own.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
from delegated_decision import (  # noqa: E402 — post-bootstrap
    classify_wall,
    rewrite_wall,
)

from squad import shared_file  # noqa: E402 — post-bootstrap import

_ITEM_RE = re.compile(r"(?m)^#{2,3}\s+(B-\d+)\s")
_WALL_RE = re.compile(r"(?m)^blocked_by:(?P<wall>.*)$")


def _blocks(text: str) -> dict[str, tuple[int, int]]:
    """Map each item id to the [start, end) span of its section."""
    marks = [(m.group(1), m.start()) for m in _ITEM_RE.finditer(text)]
    spans: dict[str, tuple[int, int]] = {}
    for i, (item_id, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        spans[item_id] = (start, end)
    return spans


def plan(registry: Path, decisions: dict[str, dict]) -> list[dict]:
    """What would change, and why — computed without writing anything."""
    text = registry.read_text()
    out: list[dict] = []
    for item_id, (start, end) in _blocks(text).items():
        block = text[start:end]
        wall_match = _WALL_RE.search(block)
        if not wall_match:
            continue
        wall = wall_match.group("wall").strip()
        verdict = classify_wall(wall)
        row = {
            "item": item_id,
            "class": verdict.klass.value,
            "delegated": verdict.delegated,
            "evidence": verdict.evidence,
        }
        if not verdict.delegated:
            row["action"] = "retain"
        elif item_id not in decisions:
            # Classified delegable, but nobody supplied a decision for it. This
            # is not an unblock: clearing a wall with no decision behind it is
            # the failure this whole mechanism exists to avoid.
            row["action"] = "retain"
            row["note"] = "delegable but no decision supplied"
        else:
            row["action"] = "rewrite"
            row["decision"] = decisions[item_id]["decision"]
            row["rationale"] = decisions[item_id]["rationale"]
        out.append(row)
    return out


def apply(registry: Path, decisions: dict[str, dict]) -> tuple[str, list[str]]:
    """Return the rewritten registry text and the ids that changed."""
    text = registry.read_text()
    changed: list[str] = []
    # Rewrite from the end so earlier spans keep their offsets.
    for item_id, (start, end) in sorted(
        _blocks(text).items(), key=lambda kv: kv[1][0], reverse=True
    ):
        if item_id not in decisions:
            continue
        block = text[start:end]
        wall_match = _WALL_RE.search(block)
        if not wall_match:
            continue
        wall = wall_match.group("wall").strip()
        if not classify_wall(wall).delegated:
            continue
        # The class travels so `rewrite_wall` can refuse a narrowing that does not name
        # what it narrowed. Passing it here is what makes the refusal reachable at all:
        # without the class the mechanism cannot tell a scope call from an option pick.
        verdict = classify_wall(wall)
        replacement = rewrite_wall(
            wall=wall,
            decision=decisions[item_id]["decision"],
            rationale=decisions[item_id]["rationale"],
            klass=verdict.klass,
            supersedes=decisions[item_id].get("supersedes", ""),
        )
        new_block = block[: wall_match.start()] + replacement + block[wall_match.end() :]
        text = text[:start] + new_block + text[end:]
        changed.append(item_id)
    return text, changed


def _tree_is_clean(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _load_decisions(path: Path) -> dict[str, dict[str, str]]:
    """`{item id: {"decision": ..., "rationale": ...}}`, or a ValueError naming the key."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"{path} could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(
            f"{path} holds a JSON {type(raw).__name__}, not an object. The shape is "
            f'{{"B-165": {{"decision": "...", "rationale": "..."}}}}')

    for item, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: `{item}` holds a {type(entry).__name__}, "
                             f"not an object with `decision` and `rationale`")
        for field in ("decision", "rationale"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{path}: `{item}` has no non-empty `{field}`. A decision with no "
                    f"rationale is a decision nobody can argue with afterwards, which "
                    f"is the whole reason this file exists rather than a flag")
    return raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", required=True, type=Path)
    ap.add_argument(
        "--decisions",
        required=True,
        type=Path,
        help='JSON: {"B-165": {"decision": "...", "rationale": "..."}}',
    )
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args()

    if not args.registry.exists():
        print(f"registry not found: {args.registry}", file=sys.stderr)
        return 2
    # Validated at the BOUNDARY, where the file enters. `json.loads` accepts any JSON,
    # and `plan()` then indexes `decisions[item]["decision"]` and `["rationale"]` while
    # `apply()` does the same — so a file that is a list, or an object whose entry is
    # missing `rationale`, left this tool as a TypeError or KeyError traceback. A
    # hand-written decisions file getting one key wrong is the ordinary case, and a
    # traceback is the worst way to say so.
    try:
        decisions = _load_decisions(args.decisions)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    rows = plan(args.registry, decisions)
    for row in rows:
        mark = "REWRITE" if row["action"] == "rewrite" else "retain "
        print(f"{mark} {row['item']}  {row['class']:12} {row.get('note', '')}")
    rewrites = [r for r in rows if r["action"] == "rewrite"]
    print(f"\n{len(rewrites)} to rewrite, {len(rows) - len(rewrites)} retained")

    if not args.apply:
        print("\n(report only — pass --apply to write)")
        return 0

    repo = args.registry.parent
    if not args.allow_dirty and not _tree_is_clean(repo):
        print(
            "\nrepository has uncommitted changes — an edit to the registry mixed "
            "into another batch cannot be reverted on its own. Commit first, or "
            "pass --allow-dirty.",
            file=sys.stderr,
        )
        return 2

    backup = args.registry.with_suffix(".md.bak")
    # Read-decide-write over the shared registry, held as one transaction. `apply` reads
    # the file itself, so the lock must be taken around the call and not inside it.
    try:
        with shared_file.locked(args.registry):
            shutil.copy2(args.registry, backup)
            text, changed = apply(args.registry, decisions)
            shared_file.write_atomic(args.registry, text)
    except TimeoutError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"\nrewrote {len(changed)}: {', '.join(changed)}")
    print(f"backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

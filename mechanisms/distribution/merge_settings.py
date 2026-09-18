#!/usr/bin/env python3
"""Merge the kit's `settings.json` into a consumer's, entry by entry.

    python3 mechanisms/distribution/merge_settings.py <consumer-settings> <kit-settings>

ONE FILE, TWO OWNERS
====================
`boundary-check.py` allowlists `settings.json` as "this project's wiring", so the
kit invites the consumer to edit it — and then the installer has to put its own
wiring back without erasing theirs. Both wholesale answers are wrong, and both
were shipped:

- **Copy the kit's over the top.** Measured across four npm consumers:
  `deny: Read(**/.env*)` gone, along with their `vitest`/`tsc` allowances. The
  kit widened what an agent may read in someone else's repository, silently.
- **Keep the consumer's whole**, which `--merge` did: the kit's hooks point at the
  kit's scripts, and a stale one stops enforcing without ever saying so.

So ownership is per ENTRY, not per key.

WHY THIS IS A MODULE AND NOT A HEREDOC
======================================
It was 100 lines inside `install.sh`, which is why nothing ran it. It rewrites a
file in seventeen repositories, and the defect it carried is one a test catches in
a second (#34):

    for key in ("hooks", "statusLine", "env", …):
        if key in kit:
            mine[key] = kit[key]

The premise in that code's own comment is right — a stale KIT hook is a gate that
quietly stopped running — and the conclusion overshoots, because `hooks` is not
the kit's alone. A consumer that wires its own hook writes it into the same key,
and this deleted it with no diff, no warning and a success message. Measured in
one consumer: its only mandatory pre-push checkpoint was on disk and unwired for
four days, while two tests asserting the hook's existence stayed green — they read
the file, and the file was never what went missing.

RETIREMENT NEEDS A BASELINE, FOR HOOKS AS FOR PERMISSIONS
=========================================================
A union cannot retire anything: an entry in the consumer and not in the kit is
EITHER something the kit withdrew OR something the project added, and those must
not share an outcome. The missing term is what the kit shipped LAST time, so the
install records it — `.kit-permissions.json` since 2026-09-02, and now
`.kit-hooks.json` on the same principle. With no record nothing is removed: on a
first install every entry is indistinguishable from a project's own, and deleting
a project's is the worse error by far.

The baseline records what the KIT shipped, never the merged result. Recording the
merge would make every consumer entry look like the kit's and hand the next
install permission to delete it.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import shutil
import sys
import tempfile
from typing import Any

#: Keys that wire the kit's own scripts. A stale copy is a gate that quietly
#: stopped running, so the kit's value replaces the consumer's outright.
#:
#: `hooks` is deliberately NOT here. It is the one key both owners legitimately
#: write to, which is why it gets `merge_hooks` instead (#34).
KIT_OWNED_KEYS = ("statusLine", "env", "$schema", "_comment_",
                  "skipDangerousModePermissionPrompt")

#: `defaultMode` is the kit's POSTURE, not the project's preference. A consumer
#: who wants another sets it in `settings.local.json`, which the harness reads at
#: higher precedence — the mechanism built for exactly this, rather than a merge
#: rule nobody can see.
KIT_OWNED_SCALARS = ("defaultMode",)


# ── hooks ─────────────────────────────────────────────────────────────────────

def _command_of(hook: Any) -> str | None:
    if isinstance(hook, dict) and isinstance(hook.get("command"), str):
        return hook["command"]
    return None


def hook_baseline(kit: dict) -> dict[str, list[str]]:
    """Every hook command the kit ships, by event. The record for next time."""
    baseline: dict[str, list[str]] = {}
    for event, groups in (kit.get("hooks") or {}).items():
        commands = [command
                    for group in groups or []
                    for hook in (group or {}).get("hooks", [])
                    if (command := _command_of(hook)) is not None]
        if commands:
            baseline[event] = commands
    return baseline


def _matcher_of(group: dict) -> str:
    return group.get("matcher", "")


def merge_hooks(
    mine: dict, kit: dict, previous: dict[str, list[str]],
) -> tuple[dict, list[str], list[str]]:
    """Per-entry merge of the `hooks` key.

    Returns the merged mapping, the consumer commands kept, and the kit commands
    retired. A hook is identified by its `command`: two entries with the same
    command are the same gate however their timeout or matcher was written.
    """
    mine_hooks = mine.get("hooks") or {}
    kit_hooks = kit.get("hooks") or {}
    kit_commands = {c for commands in hook_baseline(kit).values() for c in commands}

    kept: list[str] = []
    retired: list[str] = []
    merged: dict[str, list[dict]] = {}

    for event in list(kit_hooks) + [e for e in mine_hooks if e not in kit_hooks]:
        # The kit's groups first, verbatim: refreshing them is the whole reason
        # the installer touches this file.
        groups: list[dict] = [dict(group) for group in (kit_hooks.get(event) or [])]
        by_matcher = {_matcher_of(group): group for group in groups}

        for group in mine_hooks.get(event) or []:
            survivors = []
            for hook in (group or {}).get("hooks", []):
                command = _command_of(hook)
                if command is None or command in kit_commands:
                    # Either unreadable, or the kit's — already placed above.
                    continue
                if command in (previous.get(event) or []):
                    # The kit shipped it last time and ships it no longer.
                    retired.append(f"{event}: {command}")
                    continue
                survivors.append(hook)
                kept.append(f"{event}: {command}")
            if not survivors:
                continue
            matcher = _matcher_of(group)
            if matcher in by_matcher:
                # Same event, same matcher: append to the kit's group rather than
                # opening a second one, so the file keeps the shape a reader expects.
                target = by_matcher[matcher]
                target["hooks"] = list(target.get("hooks", [])) + survivors
            else:
                new_group = {k: v for k, v in (group or {}).items() if k != "hooks"}
                new_group["hooks"] = survivors
                groups.append(new_group)
                by_matcher[matcher] = new_group

        if groups:
            merged[event] = groups

    return merged, kept, retired


# ── permissions ───────────────────────────────────────────────────────────────

def merge_permissions(
    mine: dict, kit: dict, previous: dict[str, list[str]],
    declared_retired: set[str] | None = None,
) -> tuple[dict, int]:
    """The kit's permissions are a floor, not a replacement: union, consumer kept.

    `deny` goes first because an entry that forbids must be read before one that
    allows.
    """
    declared_retired = declared_retired or set()
    merged = mine.setdefault("permissions", {})
    retired_total = 0

    # The declared half. A rule the kit withdrew is named in
    # `rules/retired-permissions.txt` and removed on every run, base or no base —
    # which is what makes the FIRST install under this scheme able to migrate.
    for _key, entries in merged.items():
        if isinstance(entries, list):
            for rule in list(entries):
                if rule in declared_retired:
                    entries.remove(rule)
                    retired_total += 1

    for key, items in (kit.get("permissions") or {}).items():
        if not isinstance(items, list):
            # The scalar keys are not a union, and the difference cost a defect:
            # the loop used to `continue` on anything that was not a list, so
            # `defaultMode` was skipped in silence — applied, shipped, inert.
            if key in KIT_OWNED_SCALARS:
                merged[key] = items
            continue
        target_list = merged.setdefault(key, [])

        for rule in [r for r in (previous.get(key) or []) if r not in items]:
            if rule in target_list:
                target_list.remove(rule)
                retired_total += 1

        for item in items:
            if item not in target_list:
                target_list.insert(0, item) if key == "deny" else target_list.append(item)

    return merged, retired_total


# ── the whole file ────────────────────────────────────────────────────────────

def _write_atomic(target, content: str) -> None:
    """Replace `target` in one step no reader can observe half of.

    Accepts a `str` or a `Path` — this module's callers pass both, and a helper that
    refuses one of them is a helper somebody bypasses. The temporary file is created in
    the target's OWN directory, because `os.replace` is atomic only within a filesystem.
    """
    target = pathlib.Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=str(target.parent), delete=False,
                                     encoding="utf-8", prefix=f".{target.name}.",
                                     suffix=".tmp") as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    os.replace(tmp_path, target)


def merge_with_report(
    mine: dict, kit: dict, *,
    previous: dict[str, list[str]] | None = None,
    hook_previous: dict[str, list[str]] | None = None,
    declared_retired: set[str] | None = None,
) -> tuple[dict, dict[str, Any]]:
    """Merge, and say what was kept and what was removed.

    `previous` is the permissions baseline; `hook_previous` the hooks one. They
    are separate files and separate arguments, because a hook and a permission
    retire for different reasons and on different schedules.
    """
    # DEEP. `dict(mine)` is shallow, so the nested `permissions` object stayed shared
    # with the caller's input — and `merge_permissions` calls
    # `mine.setdefault("permissions", {})` and mutates that object in place. The
    # caller's dict was silently rewritten by a function whose name says it returns a
    # merge, which makes "what did the consumer have before" unanswerable after the call.
    merged = copy.deepcopy(mine)

    for key in KIT_OWNED_KEYS:
        if key in kit:
            merged[key] = kit[key]

    hooks, kept, retired = merge_hooks(merged, kit, hook_previous or {})
    if hooks:
        merged["hooks"] = hooks

    _, permissions_retired = merge_permissions(
        merged, kit, previous or {}, declared_retired
    )

    return merged, {
        "hooks_kept": kept,
        "hooks_retired": retired,
        "permissions_retired": permissions_retired,
    }


#: `merge()` lived here until 2026-09-17: a report-less wrapper around
#: `merge_with_report` with no production caller. `main()` calls the reporting form and
#: so does `install.sh`, while seventeen of the suite's nineteen assertions went through
#: the wrapper — so the tested surface and the running surface were different functions,
#: and the report every caller actually reads was covered by two assertions. The suite
#: now exercises what runs, and the wrapper is gone rather than kept for the tests.

def _load(path: str, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def _declared_retired(kit_settings_path: str) -> set[str]:
    """`rules/retired-permissions.txt`, beside the kit's settings file."""
    path = os.path.join(os.path.dirname(kit_settings_path), "rules",
                        "retired-permissions.txt")
    try:
        with open(path, encoding="utf-8") as handle:
            return {line.strip() for line in handle
                    if line.strip() and not line.lstrip().startswith("#")}
    except OSError:
        return set()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: merge_settings.py <consumer-settings.json> <kit-settings.json>",
              file=sys.stderr)
        return 2
    target, source = argv

    mine = _load(target)
    kit = _load(source)
    if not isinstance(mine, dict) or not isinstance(kit, dict):
        print(f"ERROR: {target} or {source} is not a JSON object", file=sys.stderr)
        return 2

    beside = os.path.dirname(os.path.abspath(target))
    permissions_baseline = os.path.join(beside, ".kit-permissions.json")
    hooks_baseline = os.path.join(beside, ".kit-hooks.json")

    merged, report = merge_with_report(
        mine, kit,
        previous=_load(permissions_baseline, {}),
        hook_previous=_load(hooks_baseline, {}),
        declared_retired=_declared_retired(source),
    )

    # The baseline for next time: what the KIT ships now, never the merged result.
    for path, payload in ((permissions_baseline,
                           {k: v for k, v in (kit.get("permissions") or {}).items()
                            if isinstance(v, list)}),
                          (hooks_baseline, hook_baseline(kit))):
        _write_atomic(path, json.dumps(payload, indent=2) + "\n")

    # The consumer's settings.json, kept and replaced rather than truncated. `open(w)`
    # truncates BEFORE anything is written, so an interruption, a full disk or a
    # serialisation error between the truncate and the flush left an empty or half-written
    # settings.json — the file carrying the consumer's own hooks and permission grants,
    # and the one file whose loss cannot be recovered from the kit.
    target_path = pathlib.Path(target)
    if target_path.exists():
        shutil.copy2(target_path, target_path.with_suffix(".json.bak"))
    _write_atomic(target_path, json.dumps(merged, indent=2) + "\n")

    # Said out loud, always. A silent merge over someone else's file is how the
    # deletion this module exists to prevent went unnoticed for four days.
    for kept in report["hooks_kept"]:
        print(f"    kept your hook — {kept}")
    for gone in report["hooks_retired"]:
        print(f"    removed a hook the kit retired — {gone}")
    if report["permissions_retired"]:
        print(f"    {report['permissions_retired']} permission rule(s) retired by "
              f"the kit were removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

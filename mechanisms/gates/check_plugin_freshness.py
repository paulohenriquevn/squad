#!/usr/bin/env python3
"""Does the plugin this kit would audit WITH match the repository it was built from?

    python3 mechanisms/gates/check_plugin_freshness.py
    python3 mechanisms/gates/check_plugin_freshness.py --project . --json

## The premise nothing checked

Claude Code installs a plugin into a CACHE — `~/.claude/plugins/cache/<marketplace>/…` —
and records in `installed_plugins.json` the `gitCommitSha` it was built from. This kit
resolves plugins by `installPath` (`mechanisms/conventions/installed_plugins.py`), so
every audit it commissions runs that snapshot rather than the repository.

Measured 2026-09-22 by the session maintaining those plugins, walking the whole
commission → audit → read chain for the first time: **17 of 18 installed plugins were
behind their repositories.** The contract under test did not exist in the tree that
actually ran. The repository was right, this kit's reader was right, and what executed was
neither.

Same shape as a retired shell hook wired beside its replacement: each half honest, the
joint wrong, and nothing positioned to look at the joint.

## A premise, asked once

In the sense `check_merge_autonomy.py` uses — before the work rather than during it,
because discovering this per-audit costs the run: the audit completes, the report is
written, and only a missing field says anything was wrong.

NOT once per session, though, and the first draft of this file said so. Measured the same
afternoon it was written: 7 of 7 commissioned plugins read `aligned`, and sixty minutes
later the same 7 read `stale`, because the session maintaining them had been committing.
Drift is not an incident that happened once — it is the normal state of any plugin under
active development. So `select_auditors.py` asks it at COMMISSION time, which is still
before any audit runs.

## Three answers, kept apart

    aligned       installed sha == the source repository's HEAD
    stale         they differ, and the audit would run code that predates the contract
    unverifiable  the source is not a local directory, is not a git repository, the entry
                  carries no sha, or the plugin is not installed here

`unverifiable` is NOT `aligned`. The defect this exists to catch WAS a reader treating
"I could not ask" as "nothing is wrong", and a gate repeating that inside itself would be
the same mistake one layer down.

## Scope is the registry, not the machine

Only plugins `rules/review-auditors.txt` names. Drift in a plugin no REVIEW commissions is
real and is somebody else's finding; reporting it here is noise that trains people to skip
the output.

Exit codes:
  0 — nothing stale (unverifiable entries are reported, never a failure)
  1 — at least one commissioned plugin is behind its source
  2 — not measured: no auditor registry to read
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "cycle"))
sys.path.insert(0, str(_HERE.parent / "conventions"))

from _contract import add_root  # noqa: E402
from installed_plugins import (  # noqa: E402 — post-bootstrap import
    load as load_plugins,
    marketplace_source,
)
from select_auditors import parse_registry, registry_path  # noqa: E402


def _head(repo: Path) -> str | None:
    """The source's HEAD, or None when git cannot answer — never a fabricated empty."""
    try:
        proc = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def check(*, project: Path, config_dir: Path | None = None) -> tuple[int, dict]:
    """Freshness of every plugin the auditor registry commissions."""
    registry = registry_path(project)
    if registry is None or not registry.is_file():
        return 2, {"state": "unmeasured", "detail":
                   "no rules/review-auditors.txt: nothing declares which plugins a "
                   "REVIEW commissions, so there is no set to measure"}
    try:
        auditors = parse_registry(registry.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return 2, {"state": "unmeasured",
                   "detail": f"the auditor registry could not be read: {exc}"}

    wanted = sorted({a.plugin for a in auditors})
    plugins = load_plugins(config_dir)

    aligned: list[str] = []
    stale: list[dict] = []
    unverifiable: list[dict] = []

    for name in wanted:
        plugin = plugins.get(name)
        if plugin is None:
            unverifiable.append({"plugin": name, "why":
                                 "not installed on this machine, so there is no "
                                 "snapshot to compare — see select_auditors exit 3"})
            continue
        # BOTH manifests are read by `installed_plugins`, which owns `~/.claude/plugins/`.
        # Spelling either path here would be a second place to get it wrong, and a second
        # module needing `check_produced_files.HOME_WRITERS` to exempt it for the same
        # reason the first one already carries. Measured the hard way: the first cut of
        # this gate resolved the home directory itself, and 29 install tests failed with
        # symptoms that named the installer.
        source = marketplace_source(plugin.marketplace, config_dir)
        if source.get("source") != "directory" or not source.get("path"):
            unverifiable.append({"plugin": name, "why":
                                 f"installed from `{source.get('source', 'an unknown source')}`, "
                                 "which is not a local directory this machine can diff against"})
            continue
        installed = plugin.commit
        if not installed:
            unverifiable.append({"plugin": name, "why":
                                 "the install manifest records no `gitCommitSha`, so "
                                 "which revision is running cannot be established"})
            continue
        head = _head(Path(source["path"]))
        if head is None:
            unverifiable.append({"plugin": name, "why":
                                 f"`{source['path']}` is not a git repository this "
                                 "machine can read a HEAD from"})
            continue
        if head == installed:
            aligned.append(name)
        else:
            stale.append({"plugin": name, "installed": installed, "source": head,
                          "source_path": source["path"]})

    report = {"state": "measured", "aligned": aligned, "stale": stale,
              "unverifiable": unverifiable, "commissioned": wanted}
    return (1 if stale else 0), report


def _render(code: int, report: dict) -> None:
    if report.get("state") == "unmeasured":
        print(f"UNMEASURED: {report['detail']}")
        return
    stale, unver = report["stale"], report["unverifiable"]
    total = len(report["commissioned"])
    if stale:
        print(f"STALE: {len(stale)} of {total} commissioned plugin(s) are behind their source")
        for row in stale:
            print(f"  - {row['plugin']}: running {row['installed'][:8]}, "
                  f"source is at {row['source'][:8]} ({row['source_path']})")
            print("    An audit would run code that predates the contract it is audited "
                  "against. Reinstall or update the plugin before commissioning it.")
    else:
        print(f"ALIGNED: {len(report['aligned'])} of {total} commissioned plugin(s) "
              "match their source")
    for row in unver:
        print(f"  ? {row['plugin']}: NOT VERIFIED — {row['why']}")
    if unver:
        print("  (not verified is not verified clean: these were not compared at all)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # `--root` is the contract every gate answers to (`_contract.add_root`); `--project`
    # survives as this gate's own alias, writing to the same destination, so the spelling
    # in an existing invocation keeps working.
    add_root(ap, aliases=("--project",))
    ap.add_argument("--config-dir", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, report = check(project=args.root.resolve(), config_dir=args.config_dir)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _render(code, report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Propagate a kit delta to the consumers WITHOUT erasing local improvement.

WHY THIS SCRIPT EXISTS
----------------------
While updating one adopter, five files had diverged from the previous kit
version, and the divergence was **local improvement**: the
`ECO=$([ -d .claude/skills ] …)` convention in 9 skills (which the kit does not
have), `check_xrefs`'s `_is_test_file` (a fixture citing a non-existent rule on
purpose is not a broken reference) and the project's specialist list. Copying
over them would have erased all three. It only did not because the comparison was
done file by file, by hand.

Measured afterwards: **42 consumers** have the kit installed. At that volume,
"compare before copying" does not survive as manual discipline — it becomes this
classifier.

THE RULE
--------
For each file in the delta, three contents enter the decision: the kit's
(`source`), the base version the consumer came from (`base`) and the consumer's
(`target`).

- `NEW`          — the target does not have the file. Copy.
- `IDENTICAL`    — the target is already on the new version. Nothing to do.
- `UPDATE`       — the target is exactly on the base version. Copying is safe.
- `LOCAL_CHANGE` — the target diverged from the base. **Do not touch.** The
                   script names the file and stops; deciding the merge is human
                   work, and it is exactly where a blind copy regresses a fix.

The script does not merge, on purpose. An automatic merge across 42 repos is the
way to spread silently the very error this classifier exists to prevent.

Usage:
    python3 mechanisms/distribution/sync_consumers.py --base <sha> --targets targets.txt
    python3 mechanisms/distribution/sync_consumers.py --base <sha> --targets targets.txt --apply

Exit codes:
    0 — nothing pending a human decision
    1 — at least one LOCAL_CHANGE (the target diverged; nothing was touched there)
    2 — invocation error (invalid sha, non-existent target)
"""
from __future__ import annotations

import argparse
import enum
import re
import shutil
import subprocess
import sys
from pathlib import Path


class Action(enum.Enum):
    IDENTICAL = "identical"
    NEW = "new"
    UPDATE = "update"
    #: The target carries content the kit ONCE HAD in some commit — an install made
    #: from an older version. It is lag, not modification: copying is safe.
    STALE = "stale"
    LOCAL_CHANGE = "local-change"


def classify(*, source: str, base: str | None, target: str | None) -> Action:
    """Decide what to do with a file. See § THE RULE."""
    if target is None:
        return Action.NEW
    if target == source:
        return Action.IDENTICAL
    if base is not None and target == base:
        return Action.UPDATE
    return Action.LOCAL_CHANGE


def historical_versions(repo: Path, rel: str) -> set[str]:
    """Every content this path has ever had in the kit's history.

    Without this, a consumer installed from an older version shows up as "locally
    modified" in every file the kit has evolved since — measured: 231 false
    LOCAL_CHANGE across 40 consumers, `install.sh` in almost all of them. Telling
    behind from modified is what makes updating without fear possible.
    """
    revisions = subprocess.run(  # noqa: PLW1510
        ["git", "-C", str(repo), "rev-list", "--all", "--", rel],
        capture_output=True, text=True,
    ).stdout.split()
    contents: set[str] = set()
    for revision in revisions:
        blob = subprocess.run(  # noqa: PLW1510
            ["git", "-C", str(repo), "show", f"{revision}:{rel}"],
            capture_output=True, text=True,
        )
        if blob.returncode == 0:
            contents.add(blob.stdout)
    return contents


def classify_with_history(*, source: str, base: str | None, target: str | None,
                          historical: set[str]) -> Action:
    """`classify`, plus the question it did not ask: was this ever the kit?"""
    action = classify(source=source, base=base, target=target)
    if action is Action.LOCAL_CHANGE and target in historical:
        return Action.STALE
    return action


def _git_show(repo: Path, sha: str, rel: str) -> str | None:
    result = subprocess.run(  # noqa: PLW1510
        ["git", "-C", str(repo), "show", f"{sha}:{rel}"],
        capture_output=True, text=True,
    )
    return result.stdout if result.returncode == 0 else None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def delta_prefixes() -> tuple[str, ...]:
    """What the kit owns and may therefore push.

    MUST match the trees `install.sh` copies, and `test_sync_consumers.py` fails
    when it does not. That test exists because this tuple silently lost a whole
    family: `scripts/` was renamed to `mechanisms/` on 2026-09-02 and this line
    was not touched, so from that commit onward the syncer propagated NOTHING
    from it — the fleet's lead, the pipeline scheduler, the protocol client, all
    of it — while reporting a delta as if the delta were complete. Five kit fixes
    of that same day, including one that closed a gate letting unsigned items
    through, would have reached no consumer by the supported path.

    That is this kit's most-found defect once more: a matcher that lost its reach
    and turned the resulting silence into a pass.

    `agents/` is out (grill kit-domain-agents-install, decision 5): a domain
    specialist describes the project, not the kit. While it was here, every sync
    reinstalled the origin ecosystem's eight into a consumer that had just removed
    them. `install.sh` agrees — it copies only `agents/README.md`.
    """
    return ("rules/", "skills/", "hooks/", "commands/", "mechanisms/", "squad/")


def delta_files(repo: Path, base: str) -> list[str]:
    """Files changed from `base` to HEAD that the install carries to the consumer."""
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"{base}..HEAD"],
        capture_output=True, text=True, check=True,
    )
    prefixes = delta_prefixes()
    return sorted(
        line for line in result.stdout.splitlines()
        if line.startswith(prefixes) and (repo / line).is_file()
    )


_RULES_REF_RE = re.compile(r"(?<![A-Za-z0-9_/-])(?:\.claude/)?rules/([A-Za-z0-9._-]+\.(?:md|txt))")


def missing_rule_dependencies(kit: Path, eco: Path, files: list[str]) -> list[str]:
    """Rules the delta's files cite and the consumer does not have.

    The delta must be CLOSED: a new `run_validation.py` cites
    `rules/records-location.md`, and in a lagging consumer that file does
    not exist — the target's `check_xrefs` then fails on a broken reference.
    Measured on the first application: 13 of the 40 consumers went red this way.

    Only what is MISSING enters. A rule the target already has is never overwritten
    here: the `rules/*.txt` are the project's configuration (allowlists,
    live-target,
    thresholds), e copiar por cima destruiria ajuste local.
    """
    missing: list[str] = []
    for rel in files:
        content = _read(kit / rel)
        if content is None:
            continue
        for name in _RULES_REF_RE.findall(content):
            candidate = f"rules/{name}"
            if (kit / candidate).is_file() and not (eco / candidate).exists() \
                    and candidate not in missing:
                missing.append(candidate)
    return sorted(missing)


def sync_target(kit: Path, target_root: Path, files: list[str], base: str,
                *, apply: bool) -> dict[str, list[str]]:
    """Classifica (e opcionalmente aplica) a delta em UM consumidor."""
    eco = target_root / ".claude"
    outcome: dict[str, list[str]] = {action.value: [] for action in Action}

    for rel in files:
        source = _read(kit / rel)
        if source is None:
            continue
        target_content = _read(eco / rel)
        action = classify(
            source=source,
            base=_git_show(kit, f"{base}^", rel),
            target=target_content,
        )
        if action is Action.LOCAL_CHANGE:
            # Only pay the cost of scanning history when there is divergence.
            if target_content in historical_versions(kit, rel):
                action = Action.STALE
        outcome[action.value].append(rel)
        if apply and action in (Action.NEW, Action.UPDATE, Action.STALE):
            destination = eco / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(kit / rel, destination)

    # Close the delta: the rules it cites that the target does not have.
    for rel in missing_rule_dependencies(kit, eco, files):
        outcome[Action.NEW.value].append(rel)
        if apply:
            destination = eco / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(kit / rel, destination)
    return outcome



#: The version a consumer was installed from, read from its own manifest.
#:
#: `--base` is ONE sha for every target, and that is wrong whenever the fleet is not
#: uniform. Measured 2026-09-16 across 55 consumers: three distinct contents of one
#: file, and NONE matched any commit in the kit's history — every install came from a
#: dirty working tree. With one `--base` for all of them the only reachable verdict was
#: LOCAL_CHANGE, so this tool refused all 55: correct, and useless.
#:
#: `install.sh` now records `# kit-commit: <sha>` (with `(dirty ...)` when the source
#: tree had uncommitted changes). A dirty install has no commit that describes it, so
#: it is reported as unknown rather than compared against a sha it never matched.
def base_from_manifest(root: Path) -> str | None:
    manifest = root / ".claude" / ".kit-manifest.txt"
    if not manifest.is_file():
        return None
    for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# kit-commit:"):
            value = line.split(":", 1)[1].strip()
            if not value or value.startswith("unknown") or "(dirty" in value:
                return None
            return value.split()[0]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True,
                        help="first commit of the delta (the base is its PARENT)")
    parser.add_argument("--base-from-manifest", action="store_true",
                        help="compare each target against the commit ITS manifest "
                             "records, falling back to --base when it records none")
    parser.add_argument("--targets", type=Path, required=True,
                        help="file with one consumer path per line")
    parser.add_argument("--kit", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--apply", action="store_true",
                        help="without this, only classifies (dry-run)")
    args = parser.parse_args(argv)

    if not args.targets.is_file():
        print(f"FATAL: targets list not found: {args.targets}", file=sys.stderr)
        return 2
    try:
        files = delta_files(args.kit, f"{args.base}^")
    except subprocess.CalledProcessError:
        print(f"FATAL: invalid sha: {args.base}", file=sys.stderr)
        return 2

    print(f"delta: {len(files)} file(s) since {args.base}^")
    print(f"mode : {'APPLYING' if args.apply else 'dry-run (nothing is written)'}\n")

    needs_human: dict[str, list[str]] = {}
    totals = {action.value: 0 for action in Action}

    for line in args.targets.read_text(encoding="utf-8").splitlines():
        target = line.strip()
        if not target or target.startswith("#"):
            continue
        root = Path(target).expanduser()
        if not (root / ".claude").is_dir():
            print(f"  {target}: no .claude/ — skipped")
            continue

        target_base = args.base
        if args.base_from_manifest:
            recorded = base_from_manifest(root)
            if recorded is None:
                print(f"  {target}: manifest records no clean kit-commit"
                      f" — compared against --base instead")
            else:
                target_base = recorded
        outcome = sync_target(args.kit, root, files, target_base, apply=args.apply)
        for key, items in outcome.items():
            totals[key] += len(items)
        if outcome[Action.LOCAL_CHANGE.value]:
            needs_human[target] = outcome[Action.LOCAL_CHANGE.value]

        print(f"  {Path(target).name:<26} "
              f"new={len(outcome['new']):<3} update={len(outcome['update']):<3} "
              f"stale={len(outcome['stale']):<3} igual={len(outcome['identical']):<3} "
              f"local={len(outcome['local-change'])}")

    print(f"\ntotais: {totals}")
    if needs_human:
        print("\nDiverged from the kit — NOTHING was touched in these files. "
              "Deciding the merge is human work:")
        for target, items in needs_human.items():
            print(f"  {target}")
            for rel in items:
                print(f"    - {rel}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Write the specialist files a project's routing table names, from what is on disk.

    python3 scaffold_specialists.py --root . --write

## The barrier this removes

`detect_domains.py` derives the routing table from the topology and names one agent per
domain. `route_domain.py` then exits 3 — BROKEN ROUTE — for any domain whose specialist
is not on disk, so a project with a derived table and no specialists cannot route a
single item.

Writing those files was human work, at the very first step, before anything else could
run. A system meant to work unattended cannot begin by waiting for someone.

## Why the kit ships no specialists, and why generating them is different

The kit carries none because a specialist describes ONE ecosystem's repositories, and
shipping someone else's makes the routing gate refuse every item a consumer files. That
argument is about shipping a stranger's facts. It says nothing against writing a
project's OWN facts, read from its own disk.

## What is measured, and what is left open

Measured, and written as fact:

  - the repositories the domain covers, found by walking for `.git`
  - each one's commit count, so an empty checkout is visible as one
  - the manifests present (`go.mod`, `package.json`, `Taskfile.yml`, …)
  - build and test commands the manifests imply, marked as IMPLIED

Not measured, and written as an open question rather than invented:

  - the domain's invariants — what is never done here, and why
  - the shape a real finding takes, and the false positives this domain generates
  - blast radius

Those three need someone who knows the domain, human or agent. What this script
refuses to do is guess them, because a specialist asserting an invariant nobody checked
is worse than one admitting it has none: the first is believed.

A file with the measured half and the rest marked open routes correctly today and
improves later. A missing file routes nothing, ever.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

#: Manifest -> the commands it implies. Implied, never verified: this script does not
#: run a build, and a command printed as verified when nobody ran it is the kind of
#: fact a specialist exists to prevent.
_MANIFESTS: dict[str, tuple[str, ...]] = {
    "Taskfile.yml": ("task --list", "task test", "task quality:all"),
    "Makefile": ("make help", "make test"),
    "go.mod": ("go build ./...", "go test ./...", "go vet ./..."),
    "package.json": ("npm test", "npm run build"),
    "pyproject.toml": ("python3 -m pytest", "ruff check ."),
    "Cargo.toml": ("cargo build", "cargo test"),
    "pom.xml": ("mvn -q verify",),
    "build.gradle": ("./gradlew build",),
}


def _repos_under(root: Path) -> dict[str, Path]:
    """Every git checkout at or one level below `root`, by directory name."""
    found: dict[str, Path] = {}
    if (root / ".git").is_dir():
        found[root.name] = root
    for child in sorted(root.iterdir()) if root.is_dir() else []:
        if child.is_dir() and (child / ".git").is_dir():
            found[child.name] = child
    return found


def _commits(repo: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() if out.returncode == 0 else "0 (no commits)"


def measure(repo: Path) -> dict:
    manifests = [name for name in _MANIFESTS if (repo / name).is_file()]
    commands: list[str] = []
    for name in manifests:
        commands.extend(_MANIFESTS[name])
    return {"path": str(repo), "commits": _commits(repo),
            "manifests": manifests, "implied_commands": commands}


def render(domain: str, repos: dict[str, dict], measured_on: str) -> str:
    """The specialist file: measured facts, and open questions named as open."""
    rows = "\n".join(
        f"| `{name}` | {facts['commits']} | "
        f"{', '.join('`' + m + '`' for m in facts['manifests']) or '—'} | "
        f"`{facts['path']}` |"
        for name, facts in sorted(repos.items()))
    commands = sorted({c for facts in repos.values() for c in facts["implied_commands"]})
    command_block = "\n".join(f"{c}" for c in commands) or "# no manifest implied one"
    covered = ", ".join(f"`{name}`" for name in sorted(repos))

    return f"""---
name: {domain}
description: Domain specialist for {covered}. Scaffolded from the repositories on disk on {measured_on}; its invariants and finding shapes are still open. Use for any cycle phase touching this domain.
tools: Read, Grep, Glob, Bash
---

# {domain}

**Covers (read from disk on {measured_on}):**

| Repo | Commits | Manifests | Path |
|---|---|---|---|
{rows}

## Build reality — IMPLIED, not verified

These follow from the manifests found. **Nothing here was run.** Confirm one before
relying on it, and correct this block with what actually worked — a command that fails
is more expensive here than a command that is missing, because it will be trusted.

```bash
{command_block}
```

## The domain's invariants — OPEN

*What is never done in this domain, and why.* Not measured by the scaffold, and not
guessed: an invariant asserted by nobody is worse than an absent one, because it will
be believed. Fill this in from the code, or leave it open and honest.

## The shape of a real finding — OPEN

*What a genuine defect looks like here, and which false positives this domain
generates.* Same rule: no invention.

## Blast radius — OPEN

*What a change here typically reaches.* Same rule.

---

Scaffolded by `scaffold_specialists.py`. The table above is fact; the three OPEN
sections are the work a person or an agent with knowledge of this domain still owes.
Routing works today either way — `route_domain.py` needs the file to exist, and it
does.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--write", action="store_true",
                        help="write the files; without it, report what would be written")
    parser.add_argument("--date", default="",
                        help="the measurement date to record (defaults to today)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    eco = root / ".claude" if (root / ".claude" / "skills").is_dir() else root
    detector = eco / "skills" / "backlog-init" / "scripts" / "detect_domains.py"
    if not detector.is_file():
        print(f"FATAL: detect_domains.py not found at {detector}", file=sys.stderr)
        return 1

    out = subprocess.run([sys.executable, str(detector), "--root", str(root), "--json"],
                         capture_output=True, text=True, timeout=120, cwd=str(root))
    if out.returncode != 0:
        print(f"FATAL: detect_domains exited {out.returncode}: {out.stderr[:200]}",
              file=sys.stderr)
        return 1
    try:
        topology = json.loads(out.stdout)
    except json.JSONDecodeError as error:
        print(f"FATAL: detect_domains returned no usable JSON ({error})", file=sys.stderr)
        return 1

    measured_on = args.date or __import__("datetime").date.today().isoformat()
    on_disk = _repos_under(root.parent) | _repos_under(root)
    agents_dir = eco / "agents"
    wrote, skipped = [], []

    for domain in topology.get("domains", []):
        name = domain.get("name", "")
        target = agents_dir / f"{name}.md"
        if not name:
            continue
        if target.is_file():
            # Never overwritten. A project's own specialist carries knowledge this
            # scaffold cannot reproduce, and replacing it with a measured skeleton
            # would trade something for less.
            skipped.append(f"{target.name} (already written — left alone)")
            continue
        repos = {r: measure(on_disk[r]) for r in domain.get("repos", []) if r in on_disk}
        if not repos:
            skipped.append(f"{target.name} (no repo of this domain found on disk)")
            continue
        if args.write:
            agents_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(render(name, repos, measured_on), encoding="utf-8")
        wrote.append(f"{target.name} ({len(repos)} repo(s))")

    verb = "wrote" if args.write else "would write"
    print(f"{verb} {len(wrote)} specialist(s)")
    for line in wrote:
        print(f"  {line}")
    for line in skipped:
        print(f"  skipped: {line}")
    if not args.write and wrote:
        print("\nRun again with --write to create them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

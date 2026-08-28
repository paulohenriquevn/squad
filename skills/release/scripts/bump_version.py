#!/usr/bin/env python3
"""Write the version into every stack-specific site, and name every occurrence it did not touch.

B-059 — a version can live in a stack manifest and in a runtime constant, and a human otherwise
keeps them in step. The export-surface contract test catches a divergence, and it did: cutting
0.63.0, two of three files were bumped and `npm publish` aborted in `prepublishOnly` with
`expected '0.62.0' to be '0.63.0'` — AFTER the tag was cut and pushed. `v0.63.0` still points at a
commit whose exported constant is wrong.

So the gate works and the problem is upstream of it: the human finds out at publish time.

WHY THE SITES ARE DECLARED AND NOT DISCOVERED. A search-and-replace over the tree is one line and
would corrupt a version string inside a test fixture, a documented install example, or a lockfile —
none of which is a site, and none of which any gate would catch. Instead: rewrite what is declared,
REPORT what is not, and exit non-zero so the report is not a line in a chain that continues.

Usage:
    python3 bump_version.py --root . --from 0.65.0 --to 0.66.0
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Site:
    """A file that MUST carry the version, and the pattern that locates it."""

    path: str
    pattern: str          # one group: the version literal
    description: str


KNOWN_SITES: tuple[Site, ...] = (
    Site("package.json", r'"version":\s*"([^"]+)"', "the manifest npm publishes"),
    Site(
        "pyproject.toml",
        r'(?ms)^\[project\]\s*$.*?^version\s*=\s*["\']([^"\']+)["\']',
        "the Python project manifest",
    ),
    Site(
        "Cargo.toml",
        r'(?ms)^\[package\]\s*$.*?^version\s*=\s*["\']([^"\']+)["\']',
        "the Rust package manifest",
    ),
    Site(
        "src/index.ts",
        r'export const VERSION = "([^"]+)"',
        "the constant a consumer reads at runtime",
    ),
    # A Claude Code plugin manifest, published alongside the package and carrying its own
    # `version`. Added after it refused three consecutive releases in a consumer: the file is
    # a real site, so every release stopped on it, and the operator bumped it by hand each
    # time. A refusal that is correct and unfixable trains people to work around the gate —
    # which is the failure mode this whole kit exists to prevent, arriving through the gate
    # rather than around it.
    Site(
        ".claude-plugin/plugin.json",
        r'"version":\s*"([^"]+)"',
        "the Claude Code plugin manifest",
    ),
)

# Occurrences here are expected and are not sites: the CHANGELOG records every version by design,
# and the lockfile carries the package's own version plus hundreds of others.
IGNORED = ("CHANGELOG.md", "pnpm-lock.yaml", "package-lock.json", "yarn.lock")


def _tracked_files(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True, text=True, check=False, timeout=60,
    )
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line]


def _sites_for(root: Path) -> tuple[Site, ...]:
    sites: list[Site] = []
    for site in KNOWN_SITES:
        target = root / site.path
        if not target.is_file():
            continue
        content = target.read_text(encoding="utf-8")
        if site.path == "src/index.ts" and re.search(site.pattern, content) is None:
            continue
        sites.append(site)
    return tuple(sites)


def _strays(root: Path, old: str, sites: tuple[Site, ...]) -> list[str]:
    """Tracked files carrying `old` that are neither a declared site nor deliberately ignored."""
    declared = {s.path for s in sites}
    found: list[str] = []
    for rel in _tracked_files(root):
        if rel in declared or rel in IGNORED:
            continue
        try:
            content = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if old in content:
            found.append(rel)
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the version into every declared site.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--from", dest="old", required=True, help="Version currently in the tree.")
    parser.add_argument("--to", dest="new", required=True, help="Version to write.")
    args = parser.parse_args()

    root: Path = args.root
    old: str = args.old
    new: str = args.new

    # Read and verify EVERY site before writing ANY of them. A half-applied bump is the state this
    # script exists to prevent, and it would be the state it left behind on a mid-loop failure.
    sites = _sites_for(root)
    if not sites and not (root / "go.mod").exists():
        print(
            "refused: no supported version site found and repository is not a tag-only Go module",
            file=sys.stderr,
        )
        return 2

    planned: list[tuple[Site, str]] = []
    for site in sites:
        target = root / site.path
        if not target.is_file():
            print(f"refused: {site.path} does not exist ({site.description})", file=sys.stderr)
            return 2
        content = target.read_text(encoding="utf-8")
        match = re.search(site.pattern, content)
        if match is None:
            print(f"refused: {site.path} has no version to write ({site.description})", file=sys.stderr)
            return 2
        if match.group(1) != old:
            print(
                f"refused: {site.path} carries {match.group(1)!r}, expected {old!r}. "
                "The tree is not in the state this release assumes; writing anyway would hide why.",
                file=sys.stderr,
            )
            return 2
        start, end = match.span(1)
        planned.append((site, content[:start] + new + content[end:]))

    strays = _strays(root, old, sites)
    if strays:
        print(
            f"refused: {len(strays)} tracked file(s) carry {old!r} and are not declared sites.\n"
            "  They are NOT rewritten — a version string in a fixture or a documented example is "
            "not a site, and replacing it blindly is a corruption no gate would catch.\n"
            "  Add each to KNOWN_SITES if it is one, or to IGNORED if it is not:",
            file=sys.stderr,
        )
        for rel in strays:
            print(f"    {rel}", file=sys.stderr)
        return 1

    for site, rewritten in planned:
        (root / site.path).write_text(rewritten, encoding="utf-8")
        print(f"{site.path}: {old} -> {new}  ({site.description})")

    suffix = " (tag-only Go module)" if not planned else ""
    print(f"{len(planned)} site(s) at {new}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

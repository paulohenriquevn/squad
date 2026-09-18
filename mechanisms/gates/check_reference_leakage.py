#!/usr/bin/env python3
"""Detect literal copies of third-party study material inside the project.

`study-material/`
(tools we depend on) are read-only study material. `hooks/validate-command.py`
blocks copying files out of that zone, but nothing stops an agent or a human from
reading a file there and pasting its content into the project by hand. This script
is the third layer: it looks for the RESULT of a copy, not the act.

Detection: a shingle (N consecutive non-trivial normalized lines) that appears both
in a changed project file and in a zone file is reported as a suspected copy. Exact
shingle match on 5+ meaningful lines is very unlikely by coincidence, which keeps
false positives low — but it is a heuristic, not proof, and the report says so.

Performance note (learned from #37): the zone can hold tens of thousands of foreign
files. Indexing the ZONE would blow memory (that bug peaked at 4.15 GiB). So the
index is built from the CHANGED PROJECT FILES — always few — and the zone is
streamed file by file, with a hard cap that is reported, never silent.

Exit codes:
  0 — no suspected copy (or the zone is absent/empty → SKIP)
  1 — suspected copy found AND --strict was passed
  2 — invocation error
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

#: The zone, as `rules/reference-provenance.md` § 1 declares it.
#: `records/references/` was retired on 2026-09-01 with the practice that
#: filled it; scanning a directory nothing writes to costs a walk and finds
#: nothing, and listing it here would say the zone is wider than it is.
ZONE_DIRS = ("study-material",)

# Trees a peer-project clone brings along that are not that project's code.
ZONE_SKIP_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", "target",
    "dist", "build", "out", ".next", ".nuxt", "vendor", ".mypy_cache",
    ".pytest_cache", ".ruff_cache",
})
DEFAULT_SHINGLE = 5
DEFAULT_MAX_ZONE_FILES = 5000
MAX_FILE_BYTES = 2_000_000

TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".rb",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".swift", ".scala",
    ".sh", ".bash", ".zsh", ".sql", ".md", ".rst", ".txt", ".yaml", ".yml",
    ".toml", ".json", ".proto",
}

# Lines too generic to carry provenance on their own.
TRIVIAL = {
    "", "{", "}", "(", ")", "[", "]", "};", ");", "end", "else", "else {",
    "return", "break", "continue", "pass", "fi", "done", "esac", "*/", "/*",
}


def normalize(line: str) -> str:
    """Whitespace-insensitive, case-insensitive form used for comparison."""
    return " ".join(line.split()).lower()


def meaningful_lines(text: str) -> list[tuple[int, str]]:
    """(1-based line number, normalized line) for lines that carry signal."""
    out = []
    for i, raw in enumerate(text.splitlines(), start=1):
        norm = normalize(raw)
        if norm and norm not in TRIVIAL and len(norm) > 3:
            out.append((i, norm))
    return out


def shingles(lines: list[tuple[int, str]], size: int):
    """Yield (first_line_number, joined_text) for each window of `size` lines."""
    for i in range(len(lines) - size + 1):
        window = lines[i : i + size]
        yield window[0][0], "\n".join(text for _, text in window)


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return None


def is_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def in_zone(rel: str) -> bool:
    rel = rel.lstrip("./")
    rel = rel.removeprefix(".claude/")
    return any(rel.startswith(z + "/") for z in ZONE_DIRS)


def changed_files(repo: Path, explicit: list[str] | None) -> tuple[list[Path], int]:
    """`(files, probes that answered)`. Three git probes, and how many of them worked.

    All three used to `continue` past their failure, so git absent, a `--repo` that is
    not a repository, or a repository with no HEAD left `rels` empty — and an empty
    change set is also what a clean tree looks like. The scan then compared nothing
    against the zone and printed PASS. The count is the difference between "nothing
    changed" and "nothing could be asked".
    """
    if explicit:
        return [repo / f for f in explicit], 3
    rels: set[str] = set()
    answered = 0
    for args in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            out = subprocess.run(
                args, cwd=repo, capture_output=True, text=True, check=True
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        answered += 1
        rels.update(line for line in out.splitlines() if line.strip())
    return [repo / r for r in sorted(rels) if not in_zone(r)], answered


def zone_roots(repo: Path) -> list[Path]:
    """The study-zone directories that actually exist. O(1) — no traversal.

    Separated from the enumeration on purpose: whether the zone EXISTS decides
    SKIP-vs-PASS, and that question is answerable without walking anything.
    """
    return [
        root
        for base in ZONE_DIRS
        for root in (repo / base, repo / ".claude" / base)
        if root.is_dir()
    ]


def zone_files_from(roots: list[Path]) -> list[Path]:
    """Every file under the given zone roots, skipping vendored/VCS trees.

    The zone holds CLONES of peer projects, so it carries their `node_modules`,
    their `.git` and their build output along with the source. None of that is
    code the peer wrote, and enumerating it is pure cost. Pruning happens DURING
    the walk — filtering after `rglob("*")` still descends into every one of
    those directories, which is the same defect this repository already measured
    at 832x elsewhere.
    """
    found: list[Path] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ZONE_SKIP_DIRS]
            for name in filenames:
                found.append(Path(dirpath) / name)
    return found


def build_index(files: list[Path], repo: Path, size: int) -> dict[str, tuple[str, int]]:
    """shingle text -> (project file, first line). Small: only changed files."""
    index: dict[str, tuple[str, int]] = {}
    for path in files:
        if not path.is_file() or not is_candidate(path):
            continue
        text = read_text(path)
        if text is None:
            continue
        rel = str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path)
        for lineno, shingle in shingles(meaningful_lines(text), size):
            index.setdefault(shingle, (rel, lineno))
    return index


def scan(repo: Path, size: int, max_zone_files: int, explicit: list[str] | None):
    """Returns (findings, stats). A finding is a suspected literal copy."""
    roots = zone_roots(repo)
    stats = {
        "zone_present": bool(roots),
        "zone_files": 0,
        "zone_scanned": 0,
        "truncated": False,
        #: How many of the three git probes answered. 0 means the change set is unknown,
        #: not empty — see `changed_files`.
        "probes_answered": 3,
    }
    if not roots:
        return [], stats

    # THE INDEX FIRST, THE ZONE AFTERWARDS — and the order is the point.
    # This script runs on every Stop, before the hook's early exit. Enumerating
    # the zone before knowing whether there is anything to compare made a session
    # that wrote nothing pay the full walk of thousands of third-party files just
    # to reach "nothing to compare".
    changed, stats["probes_answered"] = changed_files(repo, explicit)
    index = build_index(changed, repo, size)
    stats["indexed_shingles"] = len(index)
    if not index:
        return [], stats

    zone = zone_files_from(roots)
    stats["zone_files"] = len(zone)

    findings = []
    seen: set[tuple[str, str]] = set()
    for path in zone:
        if stats["zone_scanned"] >= max_zone_files:
            stats["truncated"] = True
            break
        if not is_candidate(path):
            continue
        text = read_text(path)
        if text is None:
            continue
        stats["zone_scanned"] += 1
        zone_rel = str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path)
        for zone_line, shingle in shingles(meaningful_lines(text), size):
            hit = index.get(shingle)
            if not hit:
                continue
            key = (hit[0], zone_rel)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "project_file": hit[0],
                    "project_line": hit[1],
                    "zone_file": zone_rel,
                    "zone_line": zone_line,
                    "lines_matched": size,
                }
            )
    return findings, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root", "--repo", dest="root", default=".", help="repository root (default: cwd)")
    ap.add_argument("--shingle", type=int, default=DEFAULT_SHINGLE,
                    help=f"consecutive meaningful lines per window (default {DEFAULT_SHINGLE})")
    ap.add_argument("--max-zone-files", type=int, default=DEFAULT_MAX_ZONE_FILES,
                    help="cap on zone files scanned; truncation is always reported")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a copy is suspected")
    ap.add_argument("files", nargs="*", help="explicit files to check (default: git-changed)")
    args = ap.parse_args()

    if args.shingle < 2:
        print("ERROR: --shingle must be >= 2", file=sys.stderr)
        return 2
    repo = Path(args.root).resolve()
    if not repo.is_dir():
        print(f"ERROR: repo not found: {repo}", file=sys.stderr)
        return 2

    findings, stats = scan(repo, args.shingle, args.max_zone_files, args.files or None)

    if not stats["zone_present"]:
        print("SKIP reference-leakage: study zone absent or empty — nothing to compare against.")
        return 0

    if not stats["probes_answered"]:
        print("UNCHECKED reference-leakage: none of the three git probes answered, so "
              "the set of changed files is unknown rather than empty. Nothing was "
              "compared against the study zone.", file=sys.stderr)
        return 2

    if stats["truncated"]:
        print(
            f"WARN reference-leakage: scanned only {stats['zone_scanned']} of "
            f"{stats['zone_files']} zone files (--max-zone-files). Coverage is PARTIAL.",
            file=sys.stderr,
        )

    if not findings:
        print(
            f"PASS reference-leakage: no {args.shingle}-line block shared with "
            f"{stats['zone_scanned']} scanned zone files."
        )
        return 0

    print(f"SUSPECTED COPY reference-leakage: {len(findings)} match(es)", file=sys.stderr)
    for f in findings:
        print(
            f"  {f['project_file']}:{f['project_line']} shares {f['lines_matched']} "
            f"consecutive lines with {f['zone_file']}:{f['zone_line']}",
            file=sys.stderr,
        )
    print(
        "\nHeuristic, not proof: an exact match of consecutive meaningful lines is "
        "strong evidence of a literal copy, but shared boilerplate or a common "
        "upstream can produce it too. Review each match; if legitimate, record the "
        "provenance and licence in the CHANGELOG.",
        file=sys.stderr,
    )
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())

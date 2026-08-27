#!/usr/bin/env python3
"""A file's name is the first documentation anyone reads.

`~/.claude/CLAUDE.md` § 5 makes it a rule of the house: choose the most specific,
most descriptive name; a long clear one beats a short problematic one. It names
the anti-pattern too — `Manager`, `Helper`, `Utils` classes that become a bin for
unrelated methods — and a directory called `lib/` is the same failure with a
different shape: it tells the reader nothing except that someone had files left
over.

WHAT IT CHECKS
--------------
| Finding | Why a script can decide it |
|---|---|
| `dumping_ground_name` | a closed list of words that name a leftover, not a purpose |
| `mixed_naming_convention` | one directory carrying both `-` and `_` is a fact |
| `test_outside_test_dir` | `test_*.py` outside a test tree is misfiled by definition |
| `purpose_not_stated` | an executable with no docstring or header says nothing |

WHAT IT CANNOT DECIDE
---------------------
Whether `analysis` is a worse name than `trajectory-validation`. That is
judgement about meaning, and a checker asserting it would produce confident
nonsense at scale. This gate catches names that are *structurally* empty — the
bin, the mixed convention, the misfiled test, the silent script. Noticing that a
name is merely vague stays a human job, and the gate says so rather than
implying it covered that too.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Words that name a leftover rather than a purpose. Matched as whole path
#: segments or whole stems, never as substrings: `library-audit.py` states a
#: purpose and merely contains `lib`.
_DUMPING_GROUND = frozenset({
    "lib", "libs", "util", "utils", "helper", "helpers", "misc", "common",
    "shared", "stuff", "tmp", "temp", "data", "manager", "handlers", "core",
})

#: Fixed by a language or a tool. Reporting them would report the language, and
#: a gate that fires on something nobody can change is a gate people ignore.
_MANDATED_NAMES = frozenset({
    "__init__.py", "__main__.py", "conftest.py", "setup.py", "index.md",
    "log.md", ".gitkeep", "index.js", "index.ts",
})

#: Not ours to name.
_SKIP_SEGMENTS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    "target", ".mypy_cache", ".pytest_cache", ".ruff_cache", "vendor",
    ".install-backups", ".patch-backups",
})

#: A directory whose job is to hold tests.
_TEST_DIR_NAMES = frozenset({"tests", "test", "__tests__", "spec", "evals"})

_EXECUTABLE_SUFFIXES = (".py", ".sh")


@dataclass(frozen=True)
class NameFinding:
    """One name that does not carry its purpose."""

    path: str
    kind: str
    detail: str


@dataclass
class NameReport:
    """What the sweep saw. The counts print pass or fail."""

    paths_read: int = 0
    directories_read: int = 0
    findings: list[NameFinding] = field(default_factory=list)


#: A directory carrying its own licence came from somewhere else. Renaming a
#: file inside it breaks the comparison with upstream and detaches the
#: attribution from what it covers.
_LICENCE_NAMES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE", "COPYING")


def _vendored_roots(repo_root: Path) -> set[Path]:
    """Every directory that ships its own licence, relative to the repo root."""
    roots: set[Path] = set()
    for name in _LICENCE_NAMES:
        for licence in repo_root.rglob(name):
            relative = licence.parent.relative_to(repo_root)
            if relative != Path("."):  # the repo's own licence is not a vendor marker
                roots.add(relative)
    return roots


def _is_skipped(relative: Path, vendored: set[Path]) -> bool:
    if _SKIP_SEGMENTS & set(relative.parts):
        return True
    return any(relative == root or root in relative.parents for root in vendored)


def _stem_words(name: str) -> set[str]:
    """The words a filename is built from, minus its extension."""
    stem = name.split(".", 1)[0]
    return {word for word in re.split(r"[-_]", stem.lower()) if word}


def check_semantic_names(repo_root: Path) -> NameReport:
    """Sweep the tree and report every name that does not state a purpose."""
    repo_root = Path(repo_root)
    report = NameReport()
    if not repo_root.is_dir():
        return report

    vendored = _vendored_roots(repo_root)
    by_directory: dict[Path, list[Path]] = {}

    for path in sorted(repo_root.rglob("*")):
        relative = path.relative_to(repo_root)
        if _is_skipped(relative, vendored):
            continue

        if path.is_dir():
            report.directories_read += 1
            _check_dumping_ground(relative, relative.name, report, is_dir=True)
            continue

        if path.name in _MANDATED_NAMES:
            continue

        report.paths_read += 1
        by_directory.setdefault(relative.parent, []).append(relative)

        _check_dumping_ground(relative, path.stem, report, is_dir=False)
        _check_misfiled_test(relative, report)
        _check_purpose_stated(path, relative, report)

    for directory, files in sorted(by_directory.items()):
        _check_one_convention(directory, files, report)

    return report


def _check_dumping_ground(
    relative: Path, subject: str, report: NameReport, *, is_dir: bool
) -> None:
    words = _stem_words(subject)
    hit = words & _DUMPING_GROUND
    # A compound name states a purpose even when one of its words is generic:
    # `path_safety.py` and `library-audit.py` are fine; `utils.py` is not.
    if not hit or len(words) > 1:
        return
    what = "directory" if is_dir else "file"
    report.findings.append(NameFinding(
        str(relative), "dumping_ground_name",
        f"{what} named {subject!r} — a name from the bin list ("
        f"{', '.join(sorted(hit))}) says what was left over, not what is here. "
        "CLAUDE.md § 5: the most specific name wins, and a long clear one beats "
        "a short problematic one",
    ))


def _check_misfiled_test(relative: Path, report: NameReport) -> None:
    if not relative.name.startswith("test_") or relative.suffix != ".py":
        return
    if _TEST_DIR_NAMES & set(relative.parts[:-1]):
        return
    report.findings.append(NameFinding(
        str(relative), "test_outside_test_dir",
        "a `test_*.py` outside any test directory is collected by a pytest run "
        "nobody intended, or missed by the one they did — and either way its "
        "location contradicts its name",
    ))


def _check_purpose_stated(path: Path, relative: Path, report: NameReport) -> None:
    if path.suffix not in _EXECUTABLE_SUFFIXES:
        return
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:900]
    except OSError:
        return

    if path.suffix == ".py":
        stated = bool(re.search(r'^\s*(?:from __future__[^\n]*\n\s*)?["\']{3}', head, re.M))
    else:
        # A shell script states its purpose in a comment above the first command.
        body = re.sub(r"^#!.*\n", "", head)
        stated = bool(re.match(r"\s*(#[^\n]*\n)+", body))

    if not stated:
        report.findings.append(NameFinding(
            str(relative), "purpose_not_stated",
            "an executable with no docstring or header comment — when the name "
            "cannot carry the whole purpose, the file must, or its reason for "
            "existing lives only in whoever wrote it",
        ))


def _check_one_convention(directory: Path, files: list[Path], report: NameReport) -> None:
    """One convention per directory, not one per repository.

    Shell hooks use kebab by long habit and Python modules cannot; the rule is
    that a reader opening one folder never has to guess which applies there.
    """
    kebab = [f for f in files if "-" in f.stem and f.suffix in _EXECUTABLE_SUFFIXES]
    snake = [f for f in files if "_" in f.stem and f.suffix in _EXECUTABLE_SUFFIXES]
    if not kebab or not snake:
        return
    report.findings.append(NameFinding(
        str(directory) if str(directory) != "." else "(repo root)",
        "mixed_naming_convention",
        f"both conventions here: {kebab[0].name} (kebab) and {snake[0].name} "
        "(snake) — a reader has to guess which applies, and the next author "
        "copies whichever file they opened first",
    ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that folder and file names state their purpose.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    report = check_semantic_names(args.repo_root)

    print(
        f"read {report.paths_read} file(s) across {report.directories_read} "
        f"directory(ies) — {len(report.findings)} name(s) that do not state a purpose"
    )
    print(
        "  (structure only: a name that is merely vague — `analysis`, `deck` — is "
        "judgement this checker does not claim)"
    )
    for finding in report.findings:
        print(f"  [{finding.kind}] {finding.path}: {finding.detail}")

    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())

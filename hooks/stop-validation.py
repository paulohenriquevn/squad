#!/usr/bin/env python3
"""Stop — the end-of-session gates, asked of what this session actually changed.

Four questions, in increasing order of how much they cost to get wrong:

  leakage   does anything here look like a literal copy of third-party material?
            ADVISORY: exact-shingle matching is strong evidence, not proof, and a
            false BLOCK on a heuristic is worse than a WARN.
  tests     does each changed source file have a test somewhere in its unit?
            WARN: the convention varies by ecosystem and guessing wrong is noise.
  changelog did production source change without a record of it? BLOCKER.
  secrets   does a secret-shaped file appear in the diff? BLOCKER.

`STOP_VALIDATION_WARN_ONLY=1` turns every blocker into a warning. It exists for
the bulk reorganisation whose rationale lives elsewhere, and it is the ONLY thing
that opens these gates.

WHAT COUNTS AS THIS SESSION'S WORK
-----------------------------------
Unstaged, staged and untracked files, plus the last commit — but only while it
has NOT reached the upstream. A session that commits and stops leaves nothing in
the working tree, and grading only the tree would let it through; grading a
commit somebody already pushed would demand a CHANGELOG entry for work that is
not this session's. With no upstream there is no way to tell the two apart, so
it stays strict.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import StopContext, create_context
from squad.layout import resolve

WARN_ONLY = os.environ.get("STOP_VALIDATION_WARN_ONLY", "0") == "1"

SOURCE_SUFFIXES = (".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".rs",
                   ".java", ".kt", ".rb", ".cs")
VENDORED = re.compile(
    r"(^|/)(node_modules|vendor|dist|build|target|\.venv|venv|__pycache__|\.next|\.nuxt)/")
IS_TEST = re.compile(r"(_test|\.test|\.spec)\.[a-z]+$|(^|/)test_[^/]+\.[a-z]+$"
                     r"|(^|/)conftest\.py$")
IN_TEST_TREE = re.compile(r"(^|/)(tests?|spec|__tests__|testdata|fixtures)/")
GENERATED = re.compile(r"(^|/)(zz_generated[^/]*\.go|doc\.go)$")
CONFIG_FILE = re.compile(r"(^|/)[a-z0-9.-]+\.config\.[a-z]+$")
CHANGELOG_TOUCH = re.compile(r"(^|/)CHANGELOG\.md$|^\.changeset/[^/]+\.md$")
SECRET_FILE = re.compile(
    r"(^|/)(\.env(\.[a-z0-9_-]+)?|credentials([._-][a-z0-9]+)?"
    r"|[a-z0-9_-]*secrets?(\.[a-z0-9_-]+)?\.(ya?ml|json|env|txt))$"
    r"|\.(pem|key|p12|pfx|jks)$")
#: The manifests that mark the root of a unit, so the test search stays inside
#: one package instead of scanning a monorepo.
UNIT_MANIFESTS = ("package.json", "go.mod", "pyproject.toml", "Cargo.toml")
#: Comment openers stripped before deciding whether a diff carried code.
COMMENT_LEAD = re.compile(r"^\s*(//|\*|/\*|\*/|#).*$")


#: Set by `git()` when a command could not be asked, as opposed to answering
#: nothing. Module-level because every caller of `changed_files()` needs the
#: distinction and none of them should have to thread it.
_GIT_UNREACHABLE: list[str] = []


def git(*args: str) -> str:
    """Git's stdout, or `""` — and a note when `""` means "could not ask".

    Every failure used to return the empty string: git missing, timeout, broken
    repository, a subcommand exiting non-zero. All four are indistinguishable
    from "nothing changed", and "nothing changed" is what makes every gate below
    pass. This hook runs at the end of every session and two of its gates are
    blockers, one of them for secrets — so the silent version of this failure is
    a secret gate that did not run and a session that ended clean.
    """
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, timeout=15)  # noqa: PLW1510
    except (OSError, subprocess.SubprocessError) as exc:
        _GIT_UNREACHABLE.append(f"`git {' '.join(args)}`: {type(exc).__name__}")
        return ""
    if done.returncode != 0:
        detail = (done.stderr or "").strip().splitlines()
        # Outside a repository there is genuinely nothing to validate, and saying
        # so on every prompt in a scratch directory is noise. Every OTHER failure
        # is a measurement that did not happen.
        if not any("not a git repository" in line.lower() for line in detail):
            _GIT_UNREACHABLE.append(
                f"`git {' '.join(args)}` exited {done.returncode}: "
                f"{(detail[0] if detail else '')[:120]}")
        return ""
    return done.stdout


def changed_files() -> list[str]:
    names = set()
    for args in (("diff", "--name-only"), ("diff", "--cached", "--name-only"),
                 ("ls-files", "--others", "--exclude-standard")):
        names.update(git(*args).splitlines())

    has_upstream = bool(git("rev-parse", "--abbrev-ref", "@{upstream}").strip())
    if not has_upstream or (git("rev-list", "--count", "@{upstream}..HEAD").strip() or "0") != "0":
        names.update(git("diff", "--name-only", "HEAD~1..HEAD").splitlines())

    return sorted(
        name for name in names
        if name.strip()
        # The kit's own tree under a consumer is not the consumer's work, and the
        # study zone is third-party material nobody here is expected to test.
        and not name.startswith(".claude/")
        and not re.match(r"(\./)?study-material/", name))


def is_production_source(name: str) -> bool:
    return (name.endswith(SOURCE_SUFFIXES) and not VENDORED.search(name)
            and not IS_TEST.search(name) and not GENERATED.search(name))


def _test_files(unit: Path) -> list[Path]:
    """Every test file inside the unit, skipping the heavy trees."""
    found = []
    for path in unit.rglob("*"):
        if not path.is_file() or VENDORED.search(str(path)):
            continue
        if IS_TEST.search(path.name) or path.name.startswith("test_"):
            found.append(path)
    return found


def _reexported_by_package(module: Path) -> str | None:
    """The package name whose `__init__.py` re-exports this module, if any.

    `squad/contexts.py` is never imported by name — `squad/__init__.py` re-exports
    it and every test writes `from squad import PreToolUseContext`. Reading the
    re-export makes that reachable, where matching symbol names in test text does
    not: a module defining `run` or `main` would match any test that calls
    `subprocess.run`, turning a false positive into a silent false NEGATIVE, which
    is the worse trade for a gate.
    """
    init = module.parent / "__init__.py"
    if not init.is_file() or module.name == "__init__.py":
        return None
    try:
        text = init.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if re.search(rf"^\s*from \.{re.escape(module.stem)} import", text, re.M):
        return module.parent.name
    return None


def has_paired_test(source: str, root: Path) -> bool:
    """Is this file protected by a test — by name, by import, or by execution?

    Four signals, strongest first. The name-mirroring rule alone reported 22 files
    as untested on 2026-09-01, among them nine hooks covered by 130 tests and a
    library covered by 91: this repository files tests by AREA
    (`tests/hooks/test_reference_zone.py`), not by mirrored name. A warn-first
    gate producing 22 lines of noise every session is the one people stop reading,
    and the hook's own comment says so.

    What is deliberately NOT a signal: a test mentioning a symbol the module
    defines. Measured on the same day, that marked `session_catchup.py` covered
    because it defines `run` — a word every test using `subprocess.run` contains.
    """
    path = Path(source)
    pkg, stem, ext = path.parent, path.stem, path.suffix.lstrip(".")

    # 1. A test named after this file, beside it.
    named = [f"{stem}_test.{ext}", f"{stem}.test.{ext}", f"{stem}.spec.{ext}",
             f"test_{stem}.{ext}", f"{stem}.test.tsx", f"{stem}.spec.tsx"]
    if any((root / pkg / candidate).is_file() for candidate in named):
        return True
    # Any test at all beside it: a package that tests itself is not untested, even
    # when the mapping is not one file to one file.
    for pattern in (f"*_test.{ext}", f"*.test.{ext}", f"*.spec.{ext}", f"test_*.{ext}"):
        if any((root / pkg).glob(pattern)):
            return True

    # The owning unit: the nearest ancestor holding a manifest, so the search stays
    # inside one package instead of scanning a whole monorepo.
    unit = (root / pkg).resolve()
    stop = root.resolve()
    while unit != unit.parent:
        if any((unit / manifest).is_file() for manifest in UNIT_MANIFESTS):
            break
        if unit == stop:
            break
        unit = unit.parent

    package = _reexported_by_package(root / path)
    #: Imported by name, imported through its package, or run as a file. The last
    #: is how every hook here is tested — a hyphenated filename cannot be imported,
    #: so the test invokes it by path, and the stem (`boundary-check`) is specific
    #: enough not to collide with prose.
    by_import = re.compile(rf"^\s*(from {re.escape(stem)} import|import {re.escape(stem)})\b", re.M)
    by_package = (re.compile(rf"^\s*(from {re.escape(package)} import|import {re.escape(package)})\b", re.M)
                  if package else None)
    by_path = re.compile(rf"(?<![\w.-]){re.escape(path.name)}(?![\w-])|(?<![\w.-]){re.escape(stem)}(?![\w.-])"
                         if "-" in stem else rf"(?<![\w.-]){re.escape(path.name)}(?![\w-])")

    for test in _test_files(unit):
        if test.name in named:
            return True
        try:
            text = test.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if by_import.search(text) or by_path.search(text):
            return True
        if by_package and by_package.search(text):
            return True
    return False


def diff_carries_code(name: str, root: Path) -> bool:
    """Did this change touch anything but comments and blank lines?

    A docs-only commit still asking for a CHANGELOG entry is merely annoying; a
    silent behaviour change slipping past is the failure the gate exists for. So
    only lines that are unambiguously comment or blank are removed, and anything
    else leaves the file counted.
    """
    target = root / name
    raw = git("diff", "HEAD", "--", name) or git("diff", "HEAD~1", "--", name)
    if not raw:
        if not target.is_file():
            return True  # deleted, and we cannot read what it said
        try:
            raw = "\n".join("+" + line for line in
                            target.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            return True

    for line in raw.splitlines():
        if not line or line[0] not in "+-" or line.startswith(("+++", "---")):
            continue
        body = COMMENT_LEAD.sub("", line[1:])
        if body.strip():
            return True
    return False


def check_leakage(project_dir: Path) -> str | None:
    script = project_dir / "mechanisms" / "gates" / "check_reference_leakage.py"
    if not script.is_file():
        return None
    try:
        done = subprocess.run(  # noqa: PLW1510
            [sys.executable, str(script), "--repo", str(project_dir), "--strict"],
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    out = done.stdout + done.stderr
    if "SUSPECTED COPY" not in out:
        return None
    matches = [ln for ln in out.splitlines() if "shares" in ln and "consecutive lines with" in ln]
    body = "".join(f"\n    -{line}" for line in matches)
    return ("Suspected literal copy of third-party study material (provenance risk). "
            "Review each match; if legitimate, record source + licence in "
            f"CHANGELOG.md:{body}")


def main() -> None:
    c = create_context(StopContext)
    layout = resolve()
    root = layout.project_dir if layout else Path.cwd()
    kit = layout.kit_dir if layout else root
    os.chdir(root)

    warnings: list[str] = []
    blockers: list[str] = []

    leak = check_leakage(root)
    if leak:
        warnings.append(leak)

    files = changed_files()

    # An empty file list is a verdict only when git was actually asked. If it was
    # not, every gate below is about to pass on a measurement nobody took.
    if _GIT_UNREACHABLE:
        detail = "".join(f"\n    - {line}" for line in dict.fromkeys(_GIT_UNREACHABLE))
        warnings.append(
            "STOP GATES DID NOT RUN — git could not be asked what changed, so the "
            "leakage, test, changelog and secret checks below graded an empty file "
            f"list rather than this session's work:{detail}\n"
            "  This is not a pass. Re-run the checks once git is reachable.")
    elif not files and not warnings:
        c.output.allow()

    def gate(message: str) -> None:
        (warnings if WARN_ONLY else blockers).append(message)

    # ── tests ────────────────────────────────────────────────────────────────
    sources = [f for f in files if is_production_source(f)]
    untested = [f for f in sources if not has_paired_test(f, root)]
    if untested:
        listed = "".join(f"\n    - {f}" for f in untested)
        warnings.append(
            "TDD gate (warn-first) — Unbreakable Rule 7: the following production "
            f"source files have no sibling test file detected:{listed}"
            f"\n  See {kit}/rules/testing.md for the project's test pairing convention.")

    # ── changelog ────────────────────────────────────────────────────────────
    code = [f for f in sources
            if not IN_TEST_TREE.search(f) and not CONFIG_FILE.search(f)]
    if (root / "CHANGELOG.md").is_file():
        substantive = [f for f in code if diff_carries_code(f, root)]
        touched = [f for f in files
                   if CHANGELOG_TOUCH.search(f) and f != ".changeset/README.md"]
        if substantive and not touched:
            gate("CHANGELOG.md not updated despite production source changes "
                 "(Unbreakable Rule 6; cycle-review BLOCKER). Add an entry to "
                 "[Unreleased] before stopping. Override with "
                 "STOP_VALIDATION_WARN_ONLY=1 only when the change is a bulk reorg "
                 "with the rationale documented separately.")
    elif code:
        warnings.append(
            "No CHANGELOG.md in this project, so the Rule 6 gate cannot run — "
            "production source changed and nothing recorded it. Create CHANGELOG.md "
            "with an [Unreleased] section (Keep a Changelog format) to activate the "
            "gate, or leave it absent deliberately if this repo does not ship to "
            "consumers.")

    # ── secrets ──────────────────────────────────────────────────────────────
    secrets = [f for f in files if SECRET_FILE.search(f)]
    if secrets:
        listed = "".join(f"\n    - {f}" for f in secrets)
        gate("Secret-pattern files appear in this session's diff (cycle-review "
             f"BLOCKER). Verify they are intentionally NOT secrets, or remove them "
             f"before stopping:{listed}")

    # ── public copy ──────────────────────────────────────────────────────────
    if any(re.search(r"(^|/)README\.md$", f) for f in files):
        added = [ln for ln in git("diff", "--", "*README.md").splitlines()
                 if ln.startswith("+")]
        joined = "\n".join(added)
        if re.search(r"\bproduction[ ]?-?[ ]?(ready|grade)\b", joined, re.IGNORECASE):
            warnings.append(
                "README.md introduces a 'production-ready' claim. Until v1.0 with "
                "measured evidence, prefer 'designed for' or 'targeted at' framings "
                f"({kit}/rules/public-copy.md).")
        if re.search(r"\b(99\.9|99\.95|99\.99)[ ]?%[ ]?(uptime|sla)", joined, re.IGNORECASE):
            warnings.append(
                "README.md introduces a specific SLA/uptime number. Per the honesty "
                "rule, specific SLAs require sustained production measurement. Remove "
                "or qualify with 'target SLO' / 'designed to support'.")

    # ── report ───────────────────────────────────────────────────────────────
    if blockers:
        print("=" * 44, file=sys.stderr)
        print("  STOP VALIDATION — HARD-GATE VIOLATION", file=sys.stderr)
        print("=" * 44, file=sys.stderr)
        print(file=sys.stderr)
        for item in blockers:
            print(f"  [BLOCK] {item}", file=sys.stderr)
            print(file=sys.stderr)
        print("-" * 44, file=sys.stderr)
        print("Resolve every BLOCK above before stopping. To override for a documented "
              "reason, re-run with STOP_VALIDATION_WARN_ONLY=1.", file=sys.stderr)
    if warnings:
        print("=" * 44)
        print("  STOP VALIDATION — ADVISORY WARNINGS")
        print("=" * 44)
        print()
        for item in warnings:
            print(f"  [WARN] {item}")
            print()
        print("-" * 44)
        print("These are advisory (warn-first). Address them or document why they are "
              "intentional before considering the session complete.")

    if blockers:
        sys.exit(2)
    c.output.allow()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Language-aware test-suite runners for the /implement validation gate.

WHY this module exists
----------------------
`run_validation.py` shipped four executive checks — `npm test`, `npm run
typecheck`, `npm run lint`, `npm run test:coverage` — and every one of them
answered `SKIP` when `package.json` was absent. On a Python, Go or Rust repo the
whole executive half of the gate went quiet, `overall` became `PARTIAL`, and
`PARTIAL` exits 0. Since `rules/cycle-implement.md` says the completion promise
is emitted "EXCLUSIVELY when run_validation.py exits 0", the promise could be
emitted with no test having run at all.

The kit itself is multi-language (`rules/code-quality-languages.txt` enables
Python, Go, Rust and TypeScript) and this repository is Python — so the defect
fired hardest exactly where the kit dogfoods itself.

The fix has two halves, and both live here:

  1. Real runners for the other three languages, so the tests actually execute.
  2. `test_execution`, a consolidating gate that FAILs when a language manifest
     is present and *nothing* ran. A `SKIP` there is indistinguishable in the
     report from "legitimately nothing to check" — the same defect shape the
     `_find_progress` docstring in `run_validation.py` already named.

Honest scope: these runners assert that a suite executed and was green. They do
NOT assert the suite was meaningful — an empty-but-green `go test ./...` still
passes here. That question belongs to `check_test_obligations.py` and to
`/review`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

#: Manifest files that prove a language is present at the repository root.
#: Order is stable so `languages_detected` reads the same way in every report.
LANGUAGE_MANIFESTS: dict[str, tuple[str, ...]] = {
    "javascript": ("package.json",),
    "python": ("pyproject.toml", "setup.py", "setup.cfg"),
    "go": ("go.mod", "go.work"),
    "rust": ("Cargo.toml",),
}


def run_command(cmd: list[str], cwd: Path, timeout: int = 300) -> dict[str, Any]:
    """Run a command, never raise. Shared by every check in the gate."""
    try:
        result = subprocess.run(  # noqa: PLW1510
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "exit_code": result.returncode,
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
            "stderr_tail": result.stderr[-500:] if result.stderr else "",
            # Additive, and only read by callers whose FINDING is the output itself.
            # `gofmt -l` names one file per line and exits 0; a 500-character tail of
            # 48 filenames reports 1 and looks like a complete answer, which is the
            # shape this codebase exists to refuse. Capped so a runaway command cannot
            # be held whole in memory.
            "stdout_full": (result.stdout or "")[:200_000],
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "error": f"timeout after {timeout}s"}
    except FileNotFoundError as exc:
        return {"exit_code": -1, "error": f"command not found: {exc}"}


#: A line that names something that failed, across the test runners this module drives:
#: `--- FAIL: TestX`, `FAIL\tpkg`, `# pkg` (a Go build error), pytest's `E ` and `FAILED`,
#: and cargo's `error[E0308]`.
_FAILURE_LINE_RE = re.compile(
    r"^(?:-{2,}\s*FAIL[:\s]|FAIL\b|#\s+\S|E\s{2,}|FAILED\b|error(?:\[E\d+\])?:|"
    r"panic:|thread '.*' panicked)")


def _diagnostic(result: dict[str, Any]) -> str:
    """What FAILED, from whichever stream the tool wrote it to.

    `go test` prints failing test names to STDOUT and reserves stderr for build errors,
    so a runner reading only `stderr_tail` reports `FAIL` with an empty diagnostic.
    Measured on a consumer 2026-09-15: 5 of 8 Go modules failing, and the gate's report
    named none of them — the reader learned that something broke and nothing else.

    stderr first, because when a build fails that IS the finding; stdout when stderr has
    nothing to say.
    """
    full = result.get("stdout_full") or ""
    named = [line for line in full.splitlines() if _FAILURE_LINE_RE.match(line.strip())]
    if named:
        # The FINDING, not the last 500 bytes of whatever the suite logged on its way
        # there. A tail of a chatty suite is INFO lines from a passing test, with the
        # failing names cut off above it — measured on a consumer where six log lines
        # filled the tail and no test name survived.
        head = named[:25]
        more = f"\n… and {len(named) - len(head)} more failing line(s)" if len(named) > len(head) else ""
        return "\n".join(head) + more
    for key in ("stderr_tail", "stdout_tail", "error"):
        value = (result.get(key) or "").strip()
        if value:
            return value
    return ""


def detect_languages(project_root: Path) -> list[str]:
    """Languages whose manifest sits at the repository root."""
    return [
        language
        for language, manifests in LANGUAGE_MANIFESTS.items()
        if any((project_root / manifest).exists() for manifest in manifests)
    ]


def _unavailable(text: str) -> bool:
    """The runner itself is missing, as opposed to the suite being red."""
    markers = ("No module named", "command not found", "not found")
    return any(marker in text for marker in markers)


def check_python_tests(project_root: Path) -> dict[str, Any]:
    """pytest, falling back to unittest discovery.

    A `pytest` exit code of 5 means "collected nothing". That is a FAIL here: a
    Python manifest promised a suite and none was found, which is the exact
    silence this gate exists to break.
    """
    name = "python tests"
    if "python" not in detect_languages(project_root):
        return {"name": name, "status": "SKIP", "reason": "no Python manifest at the repo root"}

    result = run_command(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        project_root,
        timeout=900,
    )
    code = result.get("exit_code")
    output = f"{result.get('stdout_tail', '')}{result.get('stderr_tail', '')}{result.get('error', '')}"

    if code == 0:
        return {"name": name, "status": "PASS", "runner": "pytest"}
    if code == 5:
        return {
            "name": name,
            "status": "FAIL",
            "runner": "pytest",
            "code": "no_tests_collected",
            "reason": "pytest collected no tests — a Python manifest with no suite is not a pass",
        }
    if not _unavailable(output):
        return {
            "name": name,
            "status": "FAIL",
            "runner": "pytest",
            "exit_code": code,
            "stderr_tail": _diagnostic(result),
        }

    # pytest is not installed — try the stdlib runner before giving up.
    fallback = run_command(
        [sys.executable, "-m", "unittest", "discover", "-q"], project_root, timeout=900
    )
    fallback_output = f"{fallback.get('stdout_tail', '')}{fallback.get('stderr_tail', '')}"
    if fallback.get("exit_code") == 0 and "Ran 0 tests" not in fallback_output:
        return {"name": name, "status": "PASS", "runner": "unittest"}
    return {
        "name": name,
        "status": "FAIL",
        "runner": "unittest",
        "code": "runner_unavailable" if _unavailable(output) and "Ran 0 tests" not in fallback_output else "no_tests_collected",
        "reason": "neither pytest nor unittest discovery executed a test",
        "stderr_tail": fallback.get("stderr_tail", fallback.get("error", "")),
    }


_GO_USE_BLOCK_RE = re.compile(r"^use\s*\((.*?)^\)", re.MULTILINE | re.DOTALL)
_GO_USE_SINGLE_RE = re.compile(r"^use\s+(\S+)\s*$", re.MULTILINE)


def go_workspace_modules(project_root: Path) -> list[str]:
    """Modules a `go.work` lists, relative to the repo and inside it.

    `go test ./...` at a workspace root fails with "directory prefix . does not
    contain modules listed in go.work" — the kit already hit this shape in
    /arch-check. Paths that leave the repo (`../contracts`) belong to a
    sibling repository with its own gates and are dropped, not audited from here.
    """
    work = project_root / "go.work"
    if not work.is_file():
        return []
    text = work.read_text(encoding="utf-8")
    raw: list[str] = []
    for block in _GO_USE_BLOCK_RE.findall(text):
        raw.extend(line.strip() for line in block.splitlines() if line.strip())
    raw.extend(_GO_USE_SINGLE_RE.findall(text))

    modules: list[str] = []
    for entry in raw:
        entry = entry.strip().strip('"')
        if not entry or entry.startswith(".."):
            continue
        rel = entry.removeprefix("./")
        if rel and (project_root / rel).is_dir() and rel not in modules:
            modules.append(rel)
    return modules


def check_go_tests(project_root: Path) -> dict[str, Any]:
    name = "go tests"
    if "go" not in detect_languages(project_root):
        return {"name": name, "status": "SKIP", "reason": "no go.mod at the repo root"}
    # A workspace root is not a module: run each module the go.work lists.
    modules = go_workspace_modules(project_root) if not (project_root / "go.mod").is_file() else []
    if modules:
        failures = []
        for module in modules:
            outcome = run_command(["go", "test", "./..."], project_root / module, timeout=900)
            text = f"{outcome.get('stderr_tail', '')}{outcome.get('error', '')}"
            if outcome.get("exit_code") == 0:
                continue
            if _unavailable(text):
                return {
                    "name": name, "status": "FAIL", "runner": "go test",
                    "code": "toolchain_unavailable",
                    "reason": "go.work present but the go toolchain is unavailable — "
                              "unverified is not verified",
                }
            failures.append({"module": module, "stderr_tail": _diagnostic(outcome)})
        if failures:
            return {"name": name, "status": "FAIL", "runner": "go test",
                    "modules_tested": modules, "failed_modules": [f["module"] for f in failures],
                    "stderr_tail": failures[0]["stderr_tail"]}
        return {"name": name, "status": "PASS", "runner": "go test", "modules_tested": modules}

    result = run_command(["go", "test", "./..."], project_root, timeout=900)
    output = f"{result.get('stderr_tail', '')}{result.get('error', '')}"
    if result.get("exit_code") == 0:
        return {"name": name, "status": "PASS", "runner": "go test"}
    if _unavailable(output):
        return {
            "name": name,
            "status": "FAIL",
            "runner": "go test",
            "code": "toolchain_unavailable",
            "reason": "go.mod present but the go toolchain is unavailable — unverified is not verified",
        }
    return {
        "name": name,
        "status": "FAIL",
        "runner": "go test",
        "exit_code": result.get("exit_code"),
        "stderr_tail": _diagnostic(result),
    }


def check_rust_tests(project_root: Path) -> dict[str, Any]:
    name = "rust tests"
    if "rust" not in detect_languages(project_root):
        return {"name": name, "status": "SKIP", "reason": "no Cargo.toml at the repo root"}
    result = run_command(["cargo", "test", "--quiet"], project_root, timeout=1200)
    output = f"{result.get('stderr_tail', '')}{result.get('error', '')}"
    if result.get("exit_code") == 0:
        return {"name": name, "status": "PASS", "runner": "cargo test"}
    if _unavailable(output):
        return {
            "name": name,
            "status": "FAIL",
            "runner": "cargo test",
            "code": "toolchain_unavailable",
            "reason": "Cargo.toml present but the cargo toolchain is unavailable — unverified is not verified",
        }
    return {
        "name": name,
        "status": "FAIL",
        "runner": "cargo test",
        "exit_code": result.get("exit_code"),
        "stderr_tail": _diagnostic(result),
    }


def check_test_execution(project_root: Path, suite_checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Did ANY test suite actually execute?

    - No language manifest at all → SKIP. Pre-code phase is a legitimate nothing.
    - A manifest exists and at least one suite ran (green or red) → PASS. A red
      suite is already blocking through its own check; this gate only asks
      whether the question was put to a runner.
    - A manifest exists and nothing ran → FAIL. This is the case that used to
      exit 0.
    """
    languages = detect_languages(project_root)
    # A runner that started and found nothing, or that was not installed at all,
    # did not put the question to a suite — it only proved it could not.
    non_execution = {"no_tests_collected", "runner_unavailable", "toolchain_unavailable"}
    executed = [
        c for c in suite_checks
        if c.get("status") in ("PASS", "FAIL") and c.get("code") not in non_execution
    ]

    if not languages:
        return {
            "name": "test_execution",
            "status": "SKIP",
            "languages_detected": [],
            "reason": ("no language manifest at the repo root for any suite this gate "
                       "knows how to run — nothing to run, which is not the same as "
                       "nothing to test"),
        }
    if executed:
        return {
            "name": "test_execution",
            "status": "PASS",
            "languages_detected": languages,
            "suites_executed": [c.get("name") for c in executed],
        }
    return {
        "name": "test_execution",
        "status": "FAIL",
        "languages_detected": languages,
        "suites_executed": [],
        "reason": (
            f"manifest(s) for {', '.join(languages)} present but no test suite executed. "
            "A gate that reports SKIP here is indistinguishable from one that verified "
            "something — so it fails instead."
        ),
        "skipped_reasons": [
            {"name": c.get("name"), "reason": c.get("reason")}
            for c in suite_checks
            if c.get("status") == "SKIP"
        ],
    }

# ── typecheck and lint, for the languages whose tests already run ──────────
#
# The test half of this module was made language-aware in August; the typecheck and
# lint halves were not, and stayed in `run_validation.py` as npm-only checks. Measured
# on a consumer 2026-09-15 — a Go workspace with 8 modules and 1918 lines of new Go:
#
#     npm run typecheck — SKIP  package.json absent — pre-code phase
#     npm run lint      — SKIP  package.json absent — pre-code phase
#     project gates     — SKIP  package.json absent — pre-code phase
#
# Four of seven reviews on that consumer carry that line. The repository is not in a
# pre-code phase; it has no package.json, which is a different statement. The reason
# named a conclusion about the project drawn from a probe for one ecosystem.

#: Per language: the command that answers "does this compile / typecheck", and the
#: manifest whose absence makes the question inapplicable rather than unanswered.
TYPECHECK_COMMANDS: dict[str, tuple[list[str], int]] = {
    "go": (["go", "build", "./..."], 900),
    "rust": (["cargo", "check", "--quiet"], 1200),
}

#: Lint is per-language and OPTIONAL in a way typecheck is not: a repo may legitimately
#: have no linter configured. An absent linter is reported as absent, never as clean.
LINT_COMMANDS: dict[str, tuple[list[str], int]] = {
    "go": (["gofmt", "-l", "."], 300),
    "rust": (["cargo", "clippy", "--quiet", "--", "-D", "warnings"], 1200),
    "python": (["ruff", "check", "."], 300),
}


def _skip(name: str, language: str) -> dict[str, Any]:
    """The honest form of a skip: the probe that came back empty, not a verdict.

    `package.json absent — pre-code phase` reads as a claim about the project. What was
    actually observed is that one ecosystem's manifest is not at the root, which says
    nothing about whether code exists.
    """
    manifests = " / ".join(LANGUAGE_MANIFESTS[language])
    return {"name": name, "status": "SKIP",
            "reason": f"no {manifests} at the repo root — this check is for {language}"}


def check_typecheck(project_root: Path) -> list[dict[str, Any]]:
    """One result per language present. A language with no manifest is not reported.

    Returns a LIST because a repository can be more than one language, and collapsing
    that to a single verdict is what let a Go module's failure hide behind a JS skip.
    """
    present = detect_languages(project_root)
    results: list[dict[str, Any]] = []
    for language, (command, timeout) in TYPECHECK_COMMANDS.items():
        name = f"{language} typecheck"
        if language not in present:
            continue
        results.append(_typed_outcome(name, command, project_root, timeout, language))
    return results


def check_lint(project_root: Path,
               changed_files: list[str] | None = None) -> list[dict[str, Any]]:
    """One result per language present, judged on what THIS change touched.

    Lint is run over the whole tree but the verdict is scoped to the files the change
    wrote, because a tree carries lint debt that predates the item and blocking on it
    would stop every item for somebody else's file. Measured on a consumer 2026-09-15:
    `gofmt -l .` names 48 tracked Go files, none of them in testdata, and none of them
    touched by the item under validation.

    The consumer had already reached this design by hand — its plan's DoD says
    "`task lint` is red at HEAD on an unrelated tracked file, so it is run and DIFFED,
    never asserted absolute." This encodes that rather than leaving each plan to
    rediscover it.

    Pre-existing findings are still REPORTED — as `pre_existing`, on a passing result.
    Silence about them would be the other failure: a tree nobody may be told is dirty.

    Three states, not two, because "I could not work out which findings are yours" is
    neither a pass nor a charge:

      FAIL  the change touched a file this linter flags — named
      PASS  it touched none, and the pre-existing count is reported anyway
      WARN  the changed set could not be derived; the findings are reported in full
            and attributed to nobody

    The first version had two states and returned the whole failure when it could not
    scope, reasoning that reporting everything beats guessing. Measured on a consumer
    2026-09-15: an item whose work sits on a lane branch has no checkpoint to read SHAs
    from, so the set came back empty and the gate FAILED it over 48 files it never
    touched — the exact harm the scoping exists to prevent, arriving through the fix for
    it. Reporting everything was right; charging the item for it was not.
    """
    present = detect_languages(project_root)
    results: list[dict[str, Any]] = []
    for language, (command, timeout) in LINT_COMMANDS.items():
        if language not in present:
            continue
        outcome = _typed_outcome(f"{language} lint", command, project_root,
                                 timeout, language, tool_optional=True)
        results.append(_scope_to_change(outcome, changed_files))
    return results


def _scope_to_change(outcome: dict[str, Any],
                     changed_files: list[str] | None) -> dict[str, Any]:
    """Turn a whole-tree lint failure into a verdict about the change that caused it.

    With no changed-file list the outcome is returned untouched: guessing which half of
    a failure belongs to the item is worse than reporting the whole of it.
    """
    if outcome.get("status") != "FAIL":
        return outcome
    flagged_all = outcome.get("flagged_files") or []
    if not changed_files:
        return {**outcome, "status": "WARN", "pre_existing": len(flagged_all),
                "reason": (f"{len(flagged_all)} file(s) fail this linter and the gate "
                           f"could not derive which of them this change touched — no "
                           f"commit SHAs in the checkpoint. Reported, attributed to "
                           f"nobody. Write `.progress-{{slug}}.json` and the verdict "
                           f"becomes a real one.")}
    # `flagged_files` is the WHOLE list; `stderr_tail` is a 500-character tail and using
    # it here would scope the verdict against a truncated view of the findings.
    flagged = outcome.get("flagged_files") or [
        f.strip() for f in (outcome.get("stderr_tail") or "").splitlines() if f.strip()]
    changed = {c.lstrip("./") for c in changed_files}
    mine = [f for f in flagged if f.lstrip("./") in changed]
    if mine:
        return {**outcome, "status": "FAIL", "flagged_by_this_change": mine,
                "pre_existing": len(flagged) - len(mine)}
    return {**outcome, "status": "PASS", "pre_existing": len(flagged),
            "reason": f"{len(flagged)} file(s) already failed this linter before the "
                      f"change and none of them was touched by it — reported, not charged"}


def _typed_outcome(name: str, command: list[str], project_root: Path, timeout: int,
                   language: str, tool_optional: bool = False) -> dict[str, Any]:
    """Run one command and classify it, keeping "could not run" distinct from "passed".

    A missing toolchain is a FAIL for typecheck — `rules/cycle-implement.md` treats an
    unverified claim as unverified — and a SKIP for lint, where the tool is genuinely
    optional. What neither may become is a silent pass.
    """
    # A go.work root is not a module; `go build ./...` there reports nothing useful.
    roots = [project_root]
    if language == "go" and not (project_root / "go.mod").is_file():
        modules = go_workspace_modules(project_root)
        if modules:
            roots = [project_root / m for m in modules]

    failures: list[dict[str, Any]] = []
    flagged: list[str] = []
    for root in roots:
        result = run_command(command, root, timeout=timeout)
        output = f"{result.get('stderr_tail', '')}{result.get('error', '')}"
        if _unavailable(output):
            if tool_optional:
                return {"name": name, "status": "SKIP", "runner": command[0],
                        "reason": f"{command[0]} is not installed — an absent linter is "
                                  f"absent, never clean"}
            return {"name": name, "status": "FAIL", "runner": command[0],
                    "code": "toolchain_unavailable",
                    "reason": f"{language} sources are present but {command[0]} is "
                              f"unavailable — unverified is not verified"}
        # `gofmt -l` exits 0 and PRINTS the offending files: an exit code alone would
        # report a badly formatted tree as clean.
        printed = (result.get("stdout_full") or "").strip()
        listed = [line.strip() for line in printed.splitlines() if line.strip()]
        if command[0] == "gofmt":
            # Paths are printed relative to the directory the command ran in.
            flagged.extend(str((root / line).relative_to(project_root))
                           if (root / line).is_relative_to(project_root) else line
                           for line in listed)
        if result.get("exit_code") != 0 or (command[0] == "gofmt" and listed):
            failures.append({"root": str(root), "exit_code": result.get("exit_code"),
                             "stderr_tail": result.get("stderr_tail") or printed[:500]})
    if failures:
        return {"name": name, "status": "FAIL", "runner": command[0],
                "roots_checked": [str(r) for r in roots],
                "failed_roots": [f["root"] for f in failures],
                "flagged_files": flagged,
                "stderr_tail": failures[0]["stderr_tail"]}
    return {"name": name, "status": "PASS", "runner": command[0],
            "roots_checked": [str(r) for r in roots]}

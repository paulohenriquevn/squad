"""Every path the CI hands a tool must match something, or the job checks nothing.

Measured on 2026-09-02, after `scripts/` was renamed to `mechanisms/` and the
hooks became Python — both the same day, neither reflected in `.github/`:

  - `ruff check scripts skills hooks tests conftest.py` — ruff exits 2 on a path
    that does not exist, so the Python lint step failed on every run from that
    commit. It also never linted `squad/`, the hook library, which did not exist
    when the line was written. 133 findings were waiting behind it.
  - `shellcheck … hooks/*.sh hooks/environment/*.sh scripts/*.sh tests/hooks/*.sh`
    — ALL FOUR globs matched zero files. shellcheck exits 0 on an empty argument
    list, so the job reported a clean shell contract having checked nothing. The
    12 shell files that do exist were unchecked, and one carried a real warning.
  - `for test_file in tests/hooks/test_*.sh` — zero files, so the loop body never
    ran, and a step that runs nothing reports success.
  - `--cov=scripts` under `ROOT_SUITE_COV: '1'` — 0.00% against a floor of 55%,
    so the coverage gate failed on every run. Measured against the real trees the
    figure is 82.28%.

Four instances of one defect in one file. The rename was caught in the syncer and
in the drift report the same day; nothing looked at `.github/`.

A first version of this test matched tokens by SHAPE — anything with a slash or a
known extension — and silently skipped `scripts`, which has neither. Reintroducing
the exact defect left the suite green. That version is why this one asks each
tool where its path arguments start.
"""
from __future__ import annotations

import glob
import re
import shlex
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_WORKFLOWS = sorted((_REPO / ".github" / "workflows").glob("*.yml"))

#: For each tool, the subcommand after which its arguments are paths. An empty
#: tuple means every non-flag argument is one.
_PATH_ARGS_AFTER = {
    "ruff": ("check", "format"),
    "shellcheck": (),
    "pytest": (),
}

#: Short flags that consume the token after them, so it is not a path.
_FLAGS_TAKING_A_VALUE = {"-P", "-f", "-e", "-s", "-o", "-c"}


def _run_lines() -> list[tuple[str, int, str]]:
    out = []
    for path in _WORKFLOWS:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("run:", "- run:")):
                out.append((path.name, n, stripped.split("run:", 1)[1].strip()))
    return out


def _path_arguments(command: str) -> list[str]:
    """The tokens a CI step hands a tool as paths into this repository."""
    # A command substitution is not a static path list — `shellcheck … $(git
    # ls-files '*.sh')` shlex-splits into tokens like `ls-files` that look like
    # paths and are not. What it names is decided at run time, and the right
    # guard for that is the tool's own behaviour on an empty set, not this test.
    if "$(" in command or "`" in command:
        return []
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    if not tokens:
        return []
    tool = tokens[0].rsplit("/", 1)[-1]
    if tool not in _PATH_ARGS_AFTER:
        return []

    rest = tokens[1:]
    for marker in _PATH_ARGS_AFTER[tool]:
        if marker in rest:
            rest = rest[rest.index(marker) + 1:]
            break

    out, skip_next = [], False
    for token in rest:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            skip_next = token in _FLAGS_TAKING_A_VALUE
            continue
        if "$" in token or token.startswith(("http", "&&", "|")):
            continue
        out.append(token)
    return out


def test_the_workflows_exist_at_all() -> None:
    """Otherwise every assertion below passes over an empty parameter list, which
    is the shape of defect this file is about."""
    assert _WORKFLOWS
    assert any(_path_arguments(c) for _, _, c in _run_lines()), \
        "no CI step hands a tool any path — the parser has stopped seeing them"


@pytest.mark.parametrize("where,line,command",
                         [(w, n, c) for w, n, c in _run_lines() if _path_arguments(c)],
                         ids=lambda v: str(v)[:44])
def test_every_path_a_ci_step_hands_a_tool_matches_something(
        where: str, line: int, command: str) -> None:
    """Zero matches is silent in both directions: some tools abort (ruff exits 2
    on a missing path) and some report success over an empty set (shellcheck, a
    shell for-loop)."""
    for token in _path_arguments(command):
        if re.search(r"[*?\[]", token):
            assert glob.glob(str(_REPO / token), recursive=True), (
                f"{where}:{line} — glob {token!r} matches no file; the step runs "
                f"over an empty set and reports success")
        else:
            assert (_REPO / token).exists(), (
                f"{where}:{line} — {token!r} does not exist in this repository")


def test_the_coverage_target_is_a_directory_that_exists() -> None:
    """`--cov=<missing>` reports 0.00%, and a floor that always fails is worth
    exactly what one that always passes is."""
    text = (_REPO / "mechanisms" / "cycle" / "run_slice_tests.sh").read_text(encoding="utf-8")
    # Executable lines only. The comment explaining this very fix names the old
    # target, and an earlier version of this assertion failed on it — the third
    # time in one day something here confused a mention with a use.
    runner = "\n".join(line for line in text.splitlines()
                       if not line.lstrip().startswith("#"))

    targets = re.findall(r"--cov=([\w./-]+)", runner)
    assert targets, "the runner names no coverage target"
    for target in targets:
        assert (_REPO / target).is_dir(), f"--cov={target} is not a directory here"

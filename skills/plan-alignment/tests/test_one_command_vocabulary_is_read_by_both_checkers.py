"""The scorer and the executor agree on which commands a criterion may name.

They held two lists that excluded each other. Measured on a pnpm monorepo:

    pnpm vitest run x.test.ts    score=executable   discriminate=REFUSED (not allowlisted)
    npx vitest run x.test.ts     score=NOT executable  discriminate=runs

so no real command satisfied both, and the workaround an author found was writing `npx`
AND the words `exit 0` in one bullet — fitting the text to two instruments by two paths.
The `did not run` bucket that produced is where defects survived longest: one inert
criterion sat there eight revisions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import check_criteria_discriminate as cd  # noqa: E402 — post-bootstrap import
import criterion_commands as cc  # noqa: E402 — post-bootstrap import
import score_alignment as sa  # noqa: E402 — post-bootstrap import


@pytest.mark.parametrize("name", cc.RUNNERS)
def test_every_runner_is_executable_to_the_scorer(name: str) -> None:
    assert sa._EXECUTABLE_RE.search(f"`{name} run x.test.ts`"), name


@pytest.mark.parametrize("name", cc.RUNNERS)
def test_every_runner_is_run_by_the_executor(name: str) -> None:
    assert cd._refused_command(f"{name} run x.test.ts") == "", name


@pytest.mark.parametrize("name", ("npm", "npx", "pnpm", "yarn"))
def test_every_package_manager_is_a_runner(name: str) -> None:
    """The four a JavaScript repository actually runs its tests with."""
    assert name in cc.RUNNERS


def test_the_only_command_named_and_not_run_is_declared() -> None:
    """A divergence may exist; it may not be accidental.

    `curl` proves a criterion by reaching a network, so the scorer counts it as naming
    something that runs while the executor will not run it unattended. That is the one
    declared exception, and a second one appearing silently fails here.
    """
    named_not_run = {name for name in (*cc.RUNNERS, *cc.NAMED_NOT_RUN)
                     if cd._refused_command(f"{name} x")}
    assert named_not_run == set(cc.NAMED_NOT_RUN)


def test_a_name_inside_a_longer_word_is_not_a_runner() -> None:
    """`go.mod` and `node_modules` are paths, not `go` and `node`."""
    assert not sa._EXECUTABLE_RE.search("`go.mod`")
    assert not sa._EXECUTABLE_RE.search("`node_modules/x`")
    assert not sa._EXECUTABLE_RE.search("`pnpm-lock.yaml`")


@pytest.mark.parametrize("name", cc.RUNNERS)
def test_every_runner_is_read_as_a_clause_by_the_executor(name: str) -> None:
    """A clause the executor never extracts is never run, and never found vacuous."""
    assert cd._clauses_of(f"`{name} vitest run a.spec.ts` exits 0"), name

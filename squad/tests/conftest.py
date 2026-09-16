"""Shared guards for tests whose subject is the kit's OWN repository.

Some of these tests assert properties of the tree the kit is developed in: that the
layout is standalone, that `pyproject.toml` declares three testpaths, that
`.github/workflows/ci.yml` says what the CLI replays. None of those exist in an install
— `install.sh` copies the kit into `.claude/` and ships neither the packaging file nor
the workflows.

Measured 2026-09-16: four of them failed in a consumer install while passing here, and a
consumer's push gate runs the installed suite. The failures were real reports of a real
difference and named nothing a consumer could act on.

A test whose subject is absent has not failed. It has nothing to measure, and saying so
is the honest answer — the same treatment the shipped-template test already takes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[2]


def _is_install(root: Path) -> bool:
    """A kit copied into a project, rather than the repository it is developed in."""
    return root.name == ".claude"


@pytest.fixture(autouse=True)
def _skip_when_the_subject_does_not_ship(request: pytest.FixtureRequest) -> None:
    """Skip the tests whose subject `install.sh` deliberately does not install.

    Named per test rather than per file: the rest of each module asks questions that
    hold in both trees, and skipping them would hide real coverage.
    """
    absent = {
        "test_standalone_resolves_both_to_the_same_place":
            "this tree IS a copy install, so `standalone` is the wrong question of it",
        "test_the_root_suite_is_every_declared_testpath":
            "`pyproject.toml` is packaging and does not install",
        "test_the_replayed_commands_come_from_the_workflow":
            "`.github/workflows/` is the kit's own CI and does not install",
        "test_a_run_block_step_is_seen":
            "`.github/workflows/` is the kit's own CI and does not install",
    }
    reason = absent.get(request.node.name)
    if reason and _is_install(KIT_ROOT):
        pytest.skip(f"no subject in an install: {reason}")

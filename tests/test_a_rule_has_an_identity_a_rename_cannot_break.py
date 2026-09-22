r"""A rule is cited by WHAT IT IS, not by where its file currently sits.

THE DEFECT, MEASURED

The only identity a rule has in this kit is its path. `grep -ohE "rules/[a-z0-9-]+\.(md|txt)"`
across the kit returns **1209 citations**, and a consumer's registry carries more: 33 of
the that consumer's 109 backlog items cite a path inside this kit, including items about its
own product —

    B-217  Error boundary discards the caught error   ->  rules/error-handling.md
    B-203  a wildcard barrel publishes 18 symbols     ->  rules/code-quality-golden-rule.md

The cost is not hypothetical. `check_evidence_freshness`, run against that registry,
found 6 dead pointers and **5 of them were paths that had MOVED**. Twice in one session
this repository moved a directory and had to chase its own citations: `.squad/wiki/` to
`docs/wiki/`, and `study-material/` into the write root.

WHY AN ID AND NOT A BETTER PATH

ESLint settled this: rules are referenced by a stable id, never by
`lib/rules/no-extra-semi.js`, for three reasons its docs name — portability across
versions, freedom to reorganise internals without breaking consumers, and a namespace
that works the same for core and plugin rules. Ruff, Semgrep and Pylint all do the same,
and the independent auditor the consumer already runs cites `LCR0101`. Our kit is the only
thing in that registry asking to be cited by filename.

The deprecation half matters as much as the id: ESLint pairs `meta.deprecated` with
`meta.replacedBy`, so a rule that goes away tells its consumers where it went. A path
that 404s says only that something is wrong.

WHAT THIS FILE FIXES IN PLACE

Every rule declares an id. The id is unique. A retired rule keeps its id and names its
successor. `squad.rules` resolves an id to the file, so one index moves when a file moves
and 1209 citations do not have to.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RULES = REPO / "rules"

import sys  # noqa: E402
sys.path.insert(0, str(REPO))

from squad.rules import ID_RE, catalogue, resolve  # noqa: E402


def _rule_files() -> list[Path]:
    return sorted(p for p in RULES.iterdir()
                  if p.suffix in (".md", ".txt") and p.name != "README.md")


def test_every_rule_declares_an_id() -> None:
    """A rule with no id can only be cited by path, which is the defect."""
    index = catalogue(REPO)
    missing = [p.name for p in _rule_files() if p.name not in {r.filename for r in index}]

    assert missing == [], f"these rules have no id: {missing}"


def test_ids_are_unique() -> None:
    seen: dict[str, str] = {}
    for rule in catalogue(REPO):
        assert rule.id not in seen, f"{rule.id} is claimed by {seen[rule.id]} and {rule.filename}"
        seen[rule.id] = rule.filename


def test_an_id_resolves_to_the_file_that_holds_it() -> None:
    for rule in catalogue(REPO):
        assert resolve(rule.id, REPO) == RULES / rule.filename


def test_an_unknown_id_resolves_to_nothing_rather_than_guessing() -> None:
    assert resolve("SQ-NOT-A-RULE", REPO) is None


@pytest.mark.parametrize("bad", ["sq-err-1", "ERR-01", "SQ_ERR_01", "SQ-ERR", ""])
def test_the_id_shape_is_declared_and_enforced(bad: str) -> None:
    """One shape, so a reader can tell an id from a filename at a glance."""
    assert not ID_RE.fullmatch(bad), f"{bad!r} should not be a valid rule id"


def test_a_retired_rule_names_its_successor() -> None:
    """ESLint's `replacedBy`, and the reason for it: a path that 404s tells a reader
    something is wrong, and nothing about where the thing went."""
    for rule in catalogue(REPO):
        if rule.retired:
            assert rule.replaced_by, f"{rule.id} is retired and names no successor"

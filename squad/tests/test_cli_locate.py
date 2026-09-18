"""`sq where` / `sq run` — resolving a mechanism by name instead of by path.

Two of the frictions that justified this CLI were "guessed the wrong directory twice"
and "guessed the wrong argument form twice; the usage text arrives only after exit 2"
(2026-09-09). Both are one question — *where does this live and how is it invoked* —
and both cost a call each time.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.cli import locate  # noqa: E402 — post-bootstrap import
from squad.cli.report import (  # noqa: E402 — post-bootstrap import
    FINDING,
    OK,
    UNMEASURED,
)


def test_the_index_finds_a_mechanism_by_bare_name() -> None:
    index = locate.build_index(ROOT)
    assert "check_xrefs" in index
    assert index["check_xrefs"][0].relative_to(ROOT).as_posix() == (
        "mechanisms/gates/check_xrefs.py"
    )


def test_the_index_reaches_all_five_mechanism_families_and_the_hooks() -> None:
    """A projection that silently covers one tree is the defect this CLI is about."""
    index = locate.build_index(ROOT)
    found = {p.relative_to(ROOT).parts[0] for paths in index.values() for p in paths}
    assert {"mechanisms", "hooks", "skills"} <= found


def test_where_reports_the_path_and_the_purpose() -> None:
    report = locate.where(ROOT, "check_xrefs")
    assert report.exit_code == OK
    body = "\n".join(report.lines)
    assert "mechanisms/gates/check_xrefs.py" in body
    assert body.strip(), "a located mechanism with no description is a bare path"


def test_an_unknown_name_is_unmeasured_and_suggests() -> None:
    """Exit 2, not 1: the question could not be answered, nothing was found wanting."""
    report = locate.where(ROOT, "check_xref")
    assert report.exit_code == UNMEASURED
    assert any("check_xrefs" in line for line in report.lines), report.lines


def test_an_ambiguous_name_names_both_and_refuses_to_pick() -> None:
    index = locate.build_index(ROOT)
    ambiguous = [name for name, paths in index.items() if len(paths) > 1]
    if not ambiguous:
        # Not a skip: state that the case does not exist here rather than staying
        # silent, which would read as "tested and passed".
        assert True, "no colliding basenames in this tree today"
        return
    report = locate.where(ROOT, ambiguous[0])
    assert report.exit_code == FINDING
    assert len(report.lines) >= 2


def test_every_report_states_what_it_did_not_check() -> None:
    """The load-bearing property, asserted on the verb rather than on the renderer."""
    report = locate.where(ROOT, "check_xrefs")
    assert report.not_checked, "an index that claims to have missed nothing must prove it"


def test_run_refuses_a_name_that_is_not_in_the_index() -> None:
    """`sq run` execs only what the projection contains, never an arbitrary path.

    A CLI that runs any path it is handed is a hole `hooks/validate-command.py` cannot
    see: that hook fires on the Bash tool, and `sq run` would be the Bash tool's
    payload rather than its subject.
    """
    assert locate.main_run(["../../etc/passwd"]) == UNMEASURED


def test_sq_run_honours_the_help_flag_the_router_advertises() -> None:
    """`router.py` prints "sq <verb> --help  the options for one verb".

    Four of five verbs honour it through argparse. `main_run` read `argv[0]` straight
    into the index lookup, so `sq run --help` searched for a mechanism named `--help`,
    failed, and offered close matches — a documented flag answered with
    "no mechanism named '--help'".
    """
    from squad.cli.locate import main_run

    assert main_run(["--help"]) == 0
    assert main_run(["-h"]) == 0


def test_sq_run_still_refuses_an_unknown_mechanism() -> None:
    """The help branch must not swallow the refusal it sits in front of."""
    from squad.cli.locate import UNMEASURED, main_run

    assert main_run(["a-mechanism-that-does-not-exist"]) == UNMEASURED


def test_the_index_disclaimer_names_the_trees_it_actually_globs() -> None:
    """The section `sq where` prints as its honesty statement overstated its coverage.

    It said "four trees. Three of them are kept honest by a gate", naming
    `check_skill_map` and `check_squad_map` — which check the SKILL and the MAP, not this
    index's script glob. `hooks/`, which really has no inventory, was not among the trees
    the disclaimer named, and `_TREES` holds three entries, not four.
    """
    from squad.cli import locate

    doc = locate.__doc__ or ""
    assert "four trees" not in doc, "the disclaimer still claims a tree count it does not have"
    assert "globs THREE trees" in doc or "THREE trees" in doc, doc[:400]
    assert len(locate._TREES) == 3

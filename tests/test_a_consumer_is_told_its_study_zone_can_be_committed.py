"""A consumer whose `.gitignore` does not cover the study zone is told so.

`rules/reference-provenance.md` § 1 keeps third-party material out of the index by WHERE
it sits: `.squad/study-material/`, inside the write root, "ignored whole". That was
verified in exactly one repository — this kit's own
(`test_the_zone_cannot_be_committed_by_accident`). In a consumer it is an assumption:
`install.sh` does not touch `.gitignore` ("consumer decides"), and nothing checked what
the consumer decided. A consumer that never added `.squad/` holds a cloned peer
project, licence included, one `git add -A` from its history — the legal problem the
rule opens with, reached through the path the rule names.

`check_data_root` reports it and changes nothing: editing a project's `.gitignore` is the
kit writing to a repository it does not own. Only the study zone is probed. A consumer
may version `.squad/wiki/` or its records on purpose, and a check that demanded all of
`.squad/` be ignored would be wrong about every one of them.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))
sys.path.insert(0, str(_REPO))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
from check_data_root import check_project, main  # noqa: E402 — post-bootstrap import


def _git_repo(path: Path, gitignore: str | None) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if gitignore is not None:
        (path / ".gitignore").write_text(gitignore, encoding="utf-8")
    return path


def _clone_into_zone(root: Path) -> None:
    zone = root / ".squad" / "study-material" / "some-lib"
    zone.mkdir(parents=True)
    (zone / "LICENSE").write_text("MIT\n", encoding="utf-8")


def _states(root: Path) -> dict[str, str]:
    return {r.relative: r.state for r in check_project(root)}


def test_a_repository_that_does_not_ignore_the_zone_is_reported(tmp_path: Path) -> None:
    root = _git_repo(tmp_path, gitignore="node_modules/\n")
    _clone_into_zone(root)

    report = {r.relative: r for r in check_project(root)}

    assert report[".squad/study-material"].state == "COMMITTABLE"
    assert ".gitignore" in report[".squad/study-material"].detail


def test_the_report_fails_the_gate(tmp_path: Path) -> None:
    root = _git_repo(tmp_path, gitignore=None)
    _clone_into_zone(root)

    assert main(["--root", str(root)]) == 1


def test_an_empty_zone_is_named_without_failing_a_fresh_install(tmp_path: Path) -> None:
    """Every fresh install has an empty zone and a `.gitignore` the consumer has not
    touched yet. Failing that turned the post-install validation of every new consumer
    into FAILURE; nothing is exposed until something is cloned there."""
    root = _git_repo(tmp_path, gitignore=None)

    assert _states(root).get(".squad/study-material") == "UNGUARDED"
    assert main(["--root", str(root)]) == 0


def test_ignoring_the_write_root_is_clean(tmp_path: Path) -> None:
    root = _git_repo(tmp_path, gitignore=".squad/\n")

    assert ".squad/study-material" not in _states(root)
    assert main(["--root", str(root)]) == 0


def test_versioning_the_bundle_while_ignoring_the_zone_is_clean(tmp_path: Path) -> None:
    """A consumer's choice to version `.squad/wiki/` is not the kit's to overrule."""
    root = _git_repo(tmp_path, gitignore=".squad/*\n!.squad/wiki/\n")

    assert ".squad/study-material" not in _states(root)


def test_a_tree_outside_git_has_no_index_to_protect(tmp_path: Path) -> None:
    assert _states(tmp_path) == {".squad": "EMPTY"}

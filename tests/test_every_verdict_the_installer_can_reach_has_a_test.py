"""A branch nothing exercises is a branch whose behaviour is a guess.

`--apply-upstream` shipped on 2026-09-23 with six verdict arms and a test for four of them.
The two without one were `stale` and `yours` — and `stale` was the arm that mattered: the
call passed `classify_file` two of its four arguments, so the DIVERGED-to-STALE promotion
could never run, and the tool refused exactly the files the scan had just declared
applicable. **Flag-level coverage would not have caught it**, because the flag WAS tested;
what was untested was one outcome of it.

Measured that day on a real consumer: the scan printed `stale: 9`, the tool refused all nine.

So coverage is asserted at the granularity that failed — the verdict, not the flag. This
reads the `case` arms out of the installer rather than restating them, because a second list
of what the arms are is a second place the list drifts, which is the defect
`check_install_drift._is_project_owned` refuses to add a reader to in its own comment.

The same argument covers `Drift`: an enum member the classifier can return and the installer
does not name would fall through to "could not classify", which is a refusal for the wrong
reason and reads to an operator as a broken tool rather than a guarded one.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = _ROOT / "mechanisms" / "distribution" / "install.sh"
DRIFT = _ROOT / "mechanisms" / "gates" / "check_install_drift.py"
#: Where a verdict is allowed to be exercised. Both files, because the per-file mode and the
#: classifier are tested from different angles.
_TEST_FILES = (
    "tests/test_a_single_file_can_take_the_upstream_version.py",
    "tests/test_the_upgrade_path_is_exercised_by_a_consumer.py",
    "tests/test_check_install_drift.py",
    "tests/test_drift_asks_whose_file_it_is.py",
    "tests/test_a_line_only_the_install_has_is_the_one_that_dies.py",
)


def _installer_arms() -> set[str]:
    """The verdicts the per-file mode names, read from its own `case` block."""
    source = INSTALLER.read_text(encoding="utf-8")
    start = source.index('case "$_verdict" in')
    block = source[start:source.index("  esac", start)]
    arms: set[str] = set()
    for line in block.splitlines():
        stripped = line.strip()
        match = re.match(r"^([a-z_|]+)\)", stripped)
        if match:
            arms.update(match.group(1).split("|"))
    return arms


def _drift_members() -> set[str]:
    """The values `Drift` can take, read from the enum."""
    source = DRIFT.read_text(encoding="utf-8")
    block = source[source.index("class Drift"):source.index("\n\n\n", source.index("class Drift"))]
    return set(re.findall(r'^\s+[A-Z_]+ = "([a-z_]+)"', block, re.M))


def _test_corpus() -> str:
    return "\n".join((_ROOT / rel).read_text(encoding="utf-8")
                     for rel in _TEST_FILES if (_ROOT / rel).is_file())


def test_the_arms_and_the_enum_were_both_found() -> None:
    """Without this, every parametrised test below runs over an empty set and proves nothing."""
    assert _installer_arms(), "no case arm parsed from install.sh; this test lost its subject"
    assert _drift_members(), "no Drift member parsed; this test lost its subject"


@pytest.mark.parametrize("verdict", sorted(_installer_arms()), ids=lambda v: v)
def test_a_verdict_the_installer_names_is_exercised(verdict: str) -> None:
    corpus = _test_corpus()
    assert verdict in corpus, (
        f"`install.sh` handles the verdict `{verdict}` and no test in {list(_TEST_FILES)} "
        f"mentions it. That is how `stale` shipped unreachable: the flag was tested and one "
        f"of its outcomes was not.")


@pytest.mark.parametrize("member", sorted(_drift_members()), ids=lambda m: m)
def test_a_verdict_the_classifier_can_return_is_named_by_the_installer(member: str) -> None:
    """The other direction. An unnamed member falls through to `could not classify`."""
    arms = _installer_arms()
    assert member in arms, (
        f"`Drift.{member.upper()}` is a value `classify_file` can return and `install.sh` "
        f"names no arm for it, so it reaches the catch-all and refuses as unclassifiable — "
        f"a refusal for the wrong reason, which reads as a broken tool rather than a guard.")

"""An issue fixed and merged looked exactly like an issue nobody had touched.

`kit_issues.load()` lists OPEN issues and filters the ones a person must decide
(`NEEDS_A_PERSON`). Everything else is handed to a lane as work to do.

That is right for an issue nobody has started, and wrong for one whose fix is written,
reviewed and merged — waiting only for the release that makes it installable. Both are
open, both carry no `NEEDS_A_PERSON` label, and the fleet cannot tell them apart. Handing
the second to a lane spends an agent re-solving a solved problem, and the report it writes
looks like progress.

MEASURED, not imagined: this session left twenty issues open on purpose on 2026-09-22.
The project rule separates *the fix is merged* from *the fix is installable* and closes
only on the second, because closing at merge tells whoever is blocked that the problem is
gone while `install.sh` still carries it. The consequence, noticed the same day: an issue
that is open and unlabelled cannot be told from one nobody has started — not by a reader
scanning the list, and not by the fleet reading it through this module.

The label is the state. `in-develop` is the name the project rule already prescribes, and
the fleet reads it rather than guessing from the body.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "fleet"))

from kit_issues import AWAITING_RELEASE, Issue  # noqa: E402


def _issue(number: int, *labels: str) -> Issue:
    return Issue(number=number, title=f"issue {number}", labels=tuple(labels),
                 url=f"https://example.invalid/{number}")


def test_an_issue_awaiting_release_is_not_actionable() -> None:
    assert not _issue(157, "in-develop").actionable(), (
        "its fix is written and merged; a lane given this one re-solves a solved problem"
    )


def test_an_untouched_issue_is_still_actionable() -> None:
    """THE CONTROL. The filter must not swallow the work the fleet exists to do."""
    assert _issue(144).actionable()


def test_a_decision_label_still_wins() -> None:
    assert not _issue(152, "needs-decision").actionable()


def test_the_two_reasons_are_reported_apart() -> None:
    """*Waiting for a person to decide* and *waiting for a release* are different states.

    Collapsing them would tell a reader that twenty issues need their attention when
    none of them does — which is the shape of a signal that always fires.
    """
    assert _issue(157, "in-develop").holding_reason == "awaiting_release"
    assert _issue(152, "needs-decision").holding_reason == "needs_a_person"
    assert _issue(144).holding_reason is None


def test_the_label_set_is_the_one_the_project_rule_names() -> None:
    """A second spelling of a label is a second state nobody maintains."""
    assert "in-develop" in AWAITING_RELEASE

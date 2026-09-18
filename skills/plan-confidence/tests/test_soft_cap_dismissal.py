"""B-170 — a `>` in a dismissal reason silently voids the dismissal.

`_DISMISS_SOFT_CAP_RE` matched the reason with `[^>]+?-->`, so a reason written with an arrow —
`it fell from 15 -> 0`, the idiom this repository's own commit messages and comments use — ended the
match early. The dismissal registered as ABSENT: the plan simply stayed capped at 70 and demoted to
NON_SHIPPABLE, which is indistinguishable from a cap nobody tried to dismiss.

`cycle-code-quality.md` § 1 records that a soft cap which cannot be dismissed is a hard cap under
another name. A dismissal that voids itself on punctuation reaches the same place by accident, and
says nothing on the way.

No test covered this parser, which is how it survived.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from run_structural import _dismissed_soft_caps  # noqa: E402 — post-bootstrap import

CAP = "soft_cap_mutation_unconfigured_typescript"
HYPHENATED = "auditor_unavailable_dependency-cruiser"


def _marker(reason: str) -> str:
    return f"<!-- ADR-DISMISS-SOFT-CAP: {CAP}: {reason} -->"


def test_a_plain_reason_dismisses_the_cap() -> None:
    """Anti-vacuity floor: without this, a parser that matched nothing would pass the tests below."""
    assert _dismissed_soft_caps(_marker("no runner is configured here")) == {CAP}


def test_a_reason_containing_an_arrow_still_dismisses() -> None:
    """The defect. `15 -> 0` is how this repository states a before/after."""
    assert _dismissed_soft_caps(_marker("warnings fell 15 -> 0, so the fix is observable")) == {CAP}


def test_a_reason_containing_a_comparison_still_dismisses() -> None:
    """The same character in its other common role."""
    assert _dismissed_soft_caps(_marker("coverage > 90% on the touched files")) == {CAP}


def test_a_reason_with_no_angle_bracket_is_unaffected() -> None:
    """The behaviour that already worked must keep working."""
    assert _dismissed_soft_caps(_marker("Stryker takes 22 minutes; measured on a sibling")) == {CAP}


def test_a_marker_without_a_reason_does_not_dismiss() -> None:
    """A reason is what makes a dismissal auditable. An empty one is not a dismissal."""
    assert _dismissed_soft_caps(f"<!-- ADR-DISMISS-SOFT-CAP: {CAP}: -->") == set()


def test_text_with_no_marker_dismisses_nothing() -> None:
    assert _dismissed_soft_caps("A plan that simply does not dismiss anything.") == set()


def test_a_hyphenated_cap_id_can_be_dismissed() -> None:
    """The kit's id pattern excluded `-`, so a real cap this kit's own detector emits could never be
    dismissed at all."""
    marker = f"<!-- ADR-DISMISS-SOFT-CAP: {HYPHENATED}: the auditor is present and cruises clean -->"
    assert _dismissed_soft_caps(marker) == {HYPHENATED}

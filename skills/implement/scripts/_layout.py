"""Where this install keeps its records.

B-032 — `mini_review.py` and `check_phase_review.py` both defaulted to `records/…`, the
STANDALONE layout, in an ecosystem where every consumer is a plugin install. Running the mini review
with defaults therefore created a second records at the project root, beside the one every
other cycle writes to.

`rules/records-location.md` states the rule and its measured cost: three consumers in 2026-08
where an audit read `.claude/` and reported "0 implementations, 0 reviews, 0 releases" for a
repository that had 6, 12 and 8. Its own words: *"an audit trail split across two directories is
worse than none: a reader who checks the wrong one reports absence where evidence exists."*

ONE resolver for both scripts, deliberately. The split was quiet because the WRITER and the READER
agreed with each other while both disagreed with the ecosystem; two copies of this branch could
drift into disagreeing, which is louder but no better. One fact, one implementation.

KNOWN DUPLICATION, recorded rather than hidden: `skills/release/scripts/flip_milestone_checkbox.py`
(`_default_runs_dir`) already carries the same four-line branch, for the same reason, with a
docstring that already named this failure. That makes this the third occurrence and the rule of
three says extract — but the third lives in another SKILL, and a module shared across skill
boundaries is a structural decision this bug fix did not measure. Left as two copies on purpose;
the merge is registered as a followup.
"""
from __future__ import annotations

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path
from pathlib import Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import write_records_dir  # noqa: E402


def knowledge_base_root(project_root: Path) -> Path:
    """`<project>/.squad/records` — one root, in every layout.

    This used to detect the layout from the tree: `.claude/records` for a plugin
    install, `records` for the standalone kit. The item's decisive evidence was a
    recurrence — the defect was known for eight mini-review runs because the operator
    passed the flag every time, and the ninth time they did not, the split came back. A
    default that depends on remembering IS the defect.

    Centralising removes the detection rather than making it more careful. There is no
    layout left to get wrong.
    """
    return write_records_dir(project_root)


def default_mini_reviews_dir(project_root: Path) -> Path:
    """The canonical mini-review directory for this install's layout."""
    return knowledge_base_root(project_root) / "mini-reviews"

"""An empty drift list means two things and the caller could not tell them apart.

`_reviews_that_drifted` returns the slugs whose review no longer describes the branch.
Empty means "every review still describes it" AND "there was nothing to read", and the
promotion report printed neither.

Measured on a consumer 2026-09-16: **zero** `*-review-*.json` records exist there. Two
readers glob that name — this one and `check_review_binding` — and nothing in the kit
writes it; the review stage writes `{slug}-review-{date}.md`. So the loop had never
executed its body, and a promotion said nothing at all about reviews while looking like
one whose reviews were checked.

Not a refusal, and deliberately so: the function's own docstring reasons that promotion
is not the place to invent a review requirement the cycle does not state. But a
promotion that checked no review must not look like one that checked some.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT))

from promote_to_develop import _reviews_that_drifted  # noqa: E402
from squad.paths import write_records_dir  # noqa: E402


def _project(tmp_path: Path, *records: str) -> Path:
    reviews = write_records_dir(tmp_path, "reviews")
    reviews.mkdir(parents=True)
    for name in records:
        (reviews / name).write_text(json.dumps({"slug": name.split("-review-")[0]}),
                                    encoding="utf-8")
    return tmp_path


def test_the_count_travels_with_the_answer(tmp_path: Path) -> None:
    drifted, examined = _reviews_that_drifted(_project(tmp_path))
    assert drifted == []
    assert examined == 0, \
        "an empty sweep is indistinguishable from a clean one without the count"


def test_a_record_on_disk_is_counted(tmp_path: Path) -> None:
    _, examined = _reviews_that_drifted(_project(tmp_path, "B-001-review-2026-09-16.json"))
    assert examined == 1


def test_markdown_records_are_not_counted(tmp_path: Path) -> None:
    """The review stage writes `.md`; both readers of this question glob `.json`. The
    count must report what was actually read, not what sits in the directory — a count
    that included the `.md` would report a binding check nobody performed."""
    project = _project(tmp_path)
    (write_records_dir(project, "reviews") / "B-001-review-2026-09-16.md").write_text(
        "# a review\n", encoding="utf-8")
    _, examined = _reviews_that_drifted(project)
    assert examined == 0


def test_a_project_with_no_reviews_directory_answers_zero(tmp_path: Path) -> None:
    drifted, examined = _reviews_that_drifted(tmp_path)
    assert (drifted, examined) == ([], 0)

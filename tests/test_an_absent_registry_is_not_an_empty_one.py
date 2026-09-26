"""The gate that proves an audit happened answered "none required" when it could not
find its own config.

`check_auditor_coverage` reads `rules/review-auditors.txt`. A `FileNotFoundError` on it
fell into `declared = []`, which two lines down returns `none_declared` — COVERED, zero
findings, review free to proceed. That is the right answer for a project that genuinely
declares no auditor, and the wrong one for a run handed the wrong root.

Both produce the identical outcome, and one of them happened: `_project_root_for`
returned `<project>/.squad` on a real consumer, `registry_path` looked for
`.squad/rules/review-auditors.txt`, the file was not there, and `/review` emitted
`READY_TO_MERGE_WITH_FOLLOWUPS` on a change whose two required audits had never run —
with no mention of them anywhere in the report. `cycle-review.md` says those enter "as
BLOCKER findings so the verdict cannot be computed while ignoring it".

The module already argues this for every OTHER OSError. Its own comment:

    the gate that exists to prove an audit happened answered "none required" when it
    could not read which audits are required

`FileNotFoundError` was left inside the branch because "the project never wrote a
registry" is a real case and that is what an absent file usually means. The missing
question is WHERE the file was absent from: a root that carries no `rules/` at all is
not a project that declined to declare auditors — it is a root nobody should be asking.

This is fixed BEFORE the root bug that exposed it, deliberately. A gate that cannot tell
"nothing required" from "I was given the wrong root" will hide the next wrong root too.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))

from check_auditor_coverage import check  # noqa: E402 — after the path bootstrap


def _project(tmp_path: Path, *, with_rules: bool, registry: str | None = None) -> Path:
    (tmp_path / ".squad" / "records").mkdir(parents=True)
    if with_rules:
        (tmp_path / "rules").mkdir()
        if registry is not None:
            (tmp_path / "rules" / "review-auditors.txt").write_text(registry, encoding="utf-8")
    return tmp_path


def test_a_root_with_no_rules_directory_is_unchecked(tmp_path: Path) -> None:
    """The shape the wrong root produces. Not "none required" — nobody said that."""
    _, result = check("some-slug", project=_project(tmp_path, with_rules=False))

    assert result["status"] == "unchecked", (
        f"a root carrying no rules/ answered {result['status']!r}; that is the gate "
        f"reporting on a tree it was never pointed at")
    assert "rules" in result.get("detail", "").lower()


def test_a_project_that_declares_no_auditor_is_still_covered(tmp_path: Path) -> None:
    """The half that must not go quiet. An empty registry is a visible opt-out and has
    to stay one — turning it into a blocker would make the gate unusable for every
    project that genuinely needs no independent audit."""
    _, result = check("some-slug",
                      project=_project(tmp_path, with_rules=True, registry="# none\n"))

    assert result["status"] == "none_declared", result


def test_a_rules_directory_with_no_registry_is_still_covered(tmp_path: Path) -> None:
    """A project with `rules/` and no `review-auditors.txt` never wrote one — which is
    the original meaning of the absent file, and it survives."""
    _, result = check("some-slug", project=_project(tmp_path, with_rules=True))

    assert result["status"] == "none_declared", result


def test_the_unchecked_detail_names_what_was_missing(tmp_path: Path) -> None:
    """A gate that cannot measure must say what it could not find, or the reader has
    to guess which of the two cases they are in."""
    _, result = check("some-slug", project=_project(tmp_path, with_rules=False))

    detail = result.get("detail", "")
    assert str(tmp_path) in detail, (
        f"the refusal does not name the root it was given: {detail!r}")

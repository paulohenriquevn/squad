"""What lives in the write root, and what must never live there again.

`<project>/.squad/` is the write root of THE PROJECT BEING MAINTAINED. In this
repository that is all it is: one machine's run output, ignored whole.

It was not always. Until 2026-09-21 the kit kept its own durable knowledge — eleven
ADRs and SOPs — at `.squad/wiki/`, versioned through a `!.squad/wiki/` negation, on the
argument that "this kit's durable knowledge IS its source". The argument was true and
the location was the problem: one path meant two different things, product here and run
data in a consumer, and the kit had an example in its own tree of writing authored
documents into the directory every consumer fills with execution output.

The bundle moved to `docs/wiki/`, versioned like the rest of the product. These tests
hold both halves of the new rule, because reading a `.gitignore` and predicting git's
answer is exactly the thing people get wrong — which is how the bundle came to be
tracked by luck in the first place, before this file existed.

The move is also a partial reversal: the bundle sat at `<repo>/wiki/` until 2026-09-09,
moved to `.squad/wiki/` then, and moved again now. What changed between the two moves is
not taste — it is that `records-location.md` had since declared `.squad/` the project's
write root, which made the kit's own documents a squatter in it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import RECORDS, WIKI, data_root  # noqa: E402 — post-bootstrap import

#: Where the kit's own authored knowledge lives now.
BUNDLE = _REPO / "docs" / "wiki"


def _is_ignored(path: Path) -> bool:
    """git's own answer, never a re-implementation of its matching rules."""
    done = subprocess.run(["git", "check-ignore", "-q", str(path)],
                          cwd=_REPO, capture_output=True, check=False)
    return done.returncode == 0


def _tracked(relative: str) -> list[str]:
    done = subprocess.run(["git", "ls-files", relative],
                          cwd=_REPO, capture_output=True, text=True, check=False)
    return [ln for ln in done.stdout.splitlines() if ln]


def test_the_write_root_is_ignored_whole() -> None:
    """Every path under it, not just the ones that exist today.

    Asked of files nobody has written, which is the point: `check-ignore` answers from
    the RULES rather than from the index, so this holds for the run output of a cycle
    that has not run yet.
    """
    for candidate in (
        data_root(_REPO) / RECORDS / "cycle-events.jsonl",
        data_root(_REPO) / RECORDS / "plans" / "some-plan.md",
        data_root(_REPO) / WIKI / "decisions" / "a-decision-nobody-wrote-yet.md",
    ):
        assert _is_ignored(candidate), f"{candidate} would be committed"


def test_no_run_output_ever_slipped_into_the_index() -> None:
    """A single `git add -A` is all it takes, and nothing else would notice."""
    assert _tracked(data_root(Path(".")).name) == []


def test_the_authored_bundle_is_versioned_where_the_product_is() -> None:
    """The eleven documents must not have fallen out of the index in the move."""
    tracked = _tracked("docs/wiki")

    assert len(tracked) >= 11, tracked
    assert any(t.endswith("docs/wiki/index.md") for t in tracked)
    assert any("/sops/" in t for t in tracked)
    assert any("/decisions/" in t for t in tracked)


def test_a_new_document_in_the_bundle_is_not_ignored() -> None:
    """The defect the old rule caught, asked of the new location.

    A `.gitignore` that swallows an ADR is silent: the file is written, `git status`
    says nothing, and the knowledge is on one machine.
    """
    candidate = BUNDLE / "decisions" / "a-decision-nobody-wrote-yet.md"

    assert not _is_ignored(candidate)


def test_neither_former_location_still_holds_the_bundle() -> None:
    """Two roots holding the same documents is the SPLIT state `check_data_root.py`
    reports loudest: readers resolve one, so the other is unreachable and still looks
    current. The bundle has had two previous homes and neither may keep a copy."""
    for former in (_REPO / WIKI, _REPO / ".squad" / WIKI):
        assert not former.exists(), f"{former} still holds a copy"
    assert _tracked(WIKI) == []
    assert _tracked(f".squad/{WIKI}") == []


def test_the_kit_keeps_no_write_root_of_its_own() -> None:
    """The whole point of the move, stated as a test.

    `.squad/` present in this repository is not an error — a cycle run here creates it,
    exactly as in a consumer. What must never return is a TRACKED file inside it.
    """
    assert _tracked(".squad") == []

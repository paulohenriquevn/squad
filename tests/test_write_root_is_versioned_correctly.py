"""What travels out of the write root, and what never does.

`<project>/.squad/` holds two kinds of thing and they have opposite answers:

    .squad/wiki/      durable knowledge. For THIS repository it is the source —
                      the ADRs, the SOPs — so it is versioned.
    .squad/records/   the output of one execution on one machine. It never travels.

The failure this file exists to catch is silent. `.gitignore` carried `.squad/` alone,
and git does not descend into an excluded DIRECTORY — so no negation under it could
fire. The bundle's 11 files stayed tracked only because they were already tracked
before the move: luck, not a rule. A new ADR written there was ignored, and
`git status` said nothing at all.

Excluding the CONTENTS (`.squad/*`) leaves the directory visible so `!.squad/wiki/`
can re-include the bundle. These tests hold that distinction, because reading a
`.gitignore` and predicting git's answer is exactly the thing people get wrong.
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


def _is_ignored(path: Path) -> bool:
    """git's own answer, never a re-implementation of its matching rules."""
    done = subprocess.run(["git", "check-ignore", "-q", str(path)],
                          cwd=_REPO, capture_output=True, check=False)
    return done.returncode == 0


def _tracked(relative: str) -> list[str]:
    done = subprocess.run(["git", "ls-files", relative],
                          cwd=_REPO, capture_output=True, text=True, check=False)
    return [ln for ln in done.stdout.splitlines() if ln]


def test_a_new_document_in_the_bundle_is_not_ignored(tmp_path: Path) -> None:
    """The load-bearing one, and the defect it caught.

    Asked of a path that does not exist, which is the point: `check-ignore` answers
    from the rules rather than from the index, so this holds for a file nobody has
    written yet — the one the old rule would have swallowed.
    """
    candidate = data_root(_REPO) / WIKI / "decisions" / "a-decision-nobody-wrote-yet.md"

    assert not _is_ignored(candidate), (
        "a new ADR under the bundle is ignored, and `git status` will not say so"
    )


def test_run_output_never_travels(tmp_path: Path) -> None:
    """One execution on one machine. Versioning it would put every run in the diff."""
    candidate = data_root(_REPO) / RECORDS / "cycle-events.jsonl"

    assert _is_ignored(candidate)


def test_the_bundle_that_moved_is_still_tracked() -> None:
    """It moved from `<repo>/wiki/` on 2026-09-09 and must not have fallen out."""
    tracked = _tracked(f"{data_root(Path('.')).name}/{WIKI}")

    assert len(tracked) >= 11, tracked
    assert any(t.endswith("index.md") for t in tracked)


def test_no_run_output_slipped_into_the_index() -> None:
    """A single `git add -A` is all it takes, and nothing else would notice."""
    tracked = _tracked(f"{data_root(Path('.')).name}/{RECORDS}")

    assert tracked == [], tracked


def test_the_old_bundle_location_is_gone() -> None:
    """Both roots holding the same documents is the SPLIT state `check_data_root.py`
    reports loudest: readers resolve the write root, so the old copy is unreachable
    and still looks current."""
    assert not (_REPO / WIKI).exists()
    assert _tracked(WIKI) == []

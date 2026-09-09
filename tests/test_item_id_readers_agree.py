"""Five readers extract item ids from prose, and today one of them disagrees.

`check_record_scope.py` (review skill) pins the id width to exactly three digits
with `\\bB-\\d{3}\\b`; the four others accept three or more with `\\bB-\\d{3,}\\b`
(`board_server.py` fullmatches the same shape). The gap is latent — theo's live
registry is at B-172 — but the theo consumer's own maintenance is one
crossing away from a gate that sweeps an empty set and reports a clean scope,
which is the exact failure mode B-084 and B-102 already closed one level down.

Sibling of `test_blocked_by_readers_agree.py`. Same shape, one level up: pin an
invariant ACROSS readers that deliberately share no code (each script must
review a registry written by anything, so it cannot import the others and
inherit their assumptions), so a rule fixed in one copy does not stay broken
in the others.

Fixing the regex alone leaves five copies free to drift again. This test is the
part that stops that.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _rel in ("skills/review/scripts", "skills/backlog-review/scripts"):
    _p = str(REPO_ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backlog_status import _ID_IN_TEXT_RE as STATUS_ITEM_RE  # noqa: E402
from board_server import __file__ as _BOARD_SERVER_FILE  # noqa: E402
from check_backlog_structure import _ID_IN_TEXT_RE as STRUCTURE_ITEM_RE  # noqa: E402
from check_record_scope import _ITEM_RE as REVIEW_ITEM_RE  # noqa: E402
from squad_lead import _ITEM_RE as LEAD_ITEM_RE  # noqa: E402

#: Every reader that extracts an item id from prose, named by the module that
#: owns it. The names are the private constants each script already defines; the
#: test does not merge them — it reads them side by side and holds them to the
#: same behaviour. Adding a sixth reader means adding a row here.
EXTRACTORS = {
    "check_record_scope": REVIEW_ITEM_RE,
    "check_backlog_structure": STRUCTURE_ITEM_RE,
    "backlog_status": STATUS_ITEM_RE,
    "squad_lead": LEAD_ITEM_RE,
}

#: Ids the readers must all recognise, and the pair they must all reject.
#: `B-1000` is the crossing that motivated the finding: the theo consumer's
#: registry is at B-172 today, and every reader but one accepts four digits.
#: `B-99` is short by one and must be refused everywhere.
ACCEPTED_IDS = ("B-001", "B-100", "B-172", "B-999", "B-1000", "B-99999")
REJECTED_IDS = ("B-99", "B-9")


@pytest.mark.parametrize("item_id", ACCEPTED_IDS)
def test_every_reader_extracts_the_same_id_from_prose(item_id: str) -> None:
    """The invariant the review skill broke. Any id one reader lifts from prose,
    every reader must lift — otherwise a `check_record_scope` sweep passes on a
    record naming an item its siblings would name, and the emptiness is
    indistinguishable from a genuinely clean record (B-084 one level up).
    """
    prose = f"related: {item_id}, and also see {item_id}."
    per_reader = {name: pattern.findall(prose) for name, pattern in EXTRACTORS.items()}

    same = {name for name, found in per_reader.items() if found == [item_id, item_id]}
    disagreements = set(EXTRACTORS) - same

    assert not disagreements, (
        f"{item_id!r} is extracted by {sorted(same)} and NOT by "
        f"{sorted(disagreements)} — a record naming this id sweeps empty in the "
        f"reader that disagrees, and passes silently. Per-reader result: "
        f"{per_reader}"
    )


@pytest.mark.parametrize("item_id", REJECTED_IDS)
def test_every_reader_rejects_the_same_too_short_id(item_id: str) -> None:
    """The complement: the readers that already agree at three digits must not
    diverge at two or one. `B-99` is short by one, and if any reader started
    accepting it the corpus a sibling refuses would silently become live scope
    for that reader — the same divergence in the opposite direction.
    """
    prose = f"see {item_id} for context."
    per_reader = {name: pattern.findall(prose) for name, pattern in EXTRACTORS.items()}

    accepted_it = {name for name, found in per_reader.items() if found}
    assert not accepted_it, (
        f"{item_id!r} is too short and must be rejected everywhere; "
        f"{sorted(accepted_it)} accepted it. Per-reader result: {per_reader}"
    )


def test_the_board_server_fullmatch_agrees_with_the_extractors() -> None:
    """`board_server.py` guards its `/api/item/<id>` endpoint with an inline
    `re.fullmatch(r"B-\\d{3,}", item)` rather than a module-level constant, so it
    cannot be imported like the four above. The check reads the file and asserts
    the pattern IS the one every other reader carries — the ecosystem's shape
    for id acceptance is one, not two.

    Reading the source rather than compiling a copy of the pattern is
    deliberate: the failure mode this whole test file exists to catch is the
    literal drifting in one place, so the assertion has to be about the literal
    in the file rather than about a value re-declared in a test.
    """
    source = Path(_BOARD_SERVER_FILE).read_text(encoding="utf-8")
    fullmatch_calls = re.findall(r're\.fullmatch\(\s*r?"([^"]*B-[^"]*)"', source)

    assert fullmatch_calls, (
        "board_server no longer guards /api/item/ with an inline fullmatch — "
        "either the guard moved (update this test to reach it) or it was "
        "removed (a hole this test exists to prevent)"
    )
    for pattern in fullmatch_calls:
        assert pattern == r"B-\d{3,}", (
            f"board_server fullmatches {pattern!r}; every other reader accepts "
            f"r'\\bB-\\d{{3,}}\\b'. The endpoint would refuse ids the siblings "
            f"consider live registry — the divergence this test exists to catch"
        )


def test_no_unenumerated_place_pins_the_id_to_three_digits() -> None:
    """The five importable readers agree. A sixth in PROSE would not be seen.

    The tests above import each reader and compare its regex. That covers code.
    It does not cover a SKILL.md, a rule file or a template that states the shape
    in words — and `skills/idea-to-release/SKILL.md:52` did exactly that,
    routing on `^B-\\d{3}$`, invisible to every assertion in this file until an
    issue triage read the prose by hand.

    So the tree is swept rather than trusted, in the shape of
    `test_worktree_briefs_name_the_stash.py::test_no_unenumerated_site_hands_out_a_worktree`:
    anything that writes the exactly-three-digit form must be enumerated here
    with the reason it is not a reader. An exemption nobody probes is a door.
    """
    import subprocess

    #: Places that may name the three-digit form without being a reader of ids.
    EXEMPT = {
        # The history of what was true then. Rewriting it destroys the evidence
        # that the defect existed, which is the point of a changelog.
        "CHANGELOG.md",
        # This file: it quotes the broken form to explain it.
        "tests/test_item_id_readers_agree.py",
    }

    found = subprocess.run(
        ["git", "grep", "-lE", r"B-\\d\{3\}"],
        cwd=REPO_ROOT, capture_output=True, text=True,
        check=False,
    )
    if found.returncode not in (0, 1):
        raise AssertionError(f"git grep failed: {found.stderr}")

    unenumerated = sorted({p for p in found.stdout.split() if p} - EXEMPT)
    assert not unenumerated, (
        "these pin an item id to exactly three digits and are not enumerated: "
        f"{unenumerated}. A registry crossing B-999 routes nowhere from them. "
        "Either widen to `B-\\d{3,}` or add the path here with the reason it is "
        "not a reader of ids."
    )

"""One registry, one idea of what an item block IS.

THE DEFECT THIS CLOSES
----------------------
Six readers parsed the `## B-NNN — Title` header and they did not agree. Measured
2026-09-20 on `## B-003 - Title`, written with a plain hyphen:

    check_backlog_structure.BLOCK_RE   (the canonical one)   did NOT see it
    backlog_status.BLOCK_HEADER_RE     (the WRITER)          did NOT see it
    detect_domains, phase_coverage                           did NOT see it
    build_approval_brief.ITEM_HEAD_RE                        saw it
    check_objective_coverage.ITEM_RE                         saw it
    apply_delegated_decisions.ITEM_RE                        saw it

So an item could enter the approval brief, be ticked and signed, and be invisible
to the only thing allowed to write its status.

The damage compounds. A header the parser does not recognise does not OPEN a block,
so the unseen item's fields are read as the PREVIOUS item's. Measured with two items,
the second written with a hyphen:

    Items   : 1                                  (there are two)
    [BLOCKER] B-001 duplicate_field: `status` is declared 2 times
    [BLOCKER] B-001 self_block: `B-001` names itself in `blocked_by`
    [BLOCKER] B-001 blocker_cycle: B-001 -> B-001

Three blockers, all false, all on the wrong item — and one real item gone from the
count. `check_intake_gates.py` had already reasoned this out and imports the parser
instead of writing one: "A second regex here would diverge silently, and the two
would disagree about what the registry contains."

`squad/backlog.py` is the one parser now. This test refuses a second.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Every module that reads an item block out of BACKLOG.md.
READERS = (
    "skills/backlog-review/scripts/check_backlog_structure.py",
    "mechanisms/cycle/backlog_status.py",
    "skills/backlog-init/scripts/detect_domains.py",
    "skills/backlog-review/scripts/phase_coverage.py",
    "skills/backlog-approve/scripts/build_approval_brief.py",
    "skills/backlog-approve/scripts/check_objective_coverage.py",
    "mechanisms/cycle/apply_delegated_decisions.py",
)

#: A header pattern compiled locally. The shared module defines one — it IS the
#: definition — and nobody else may.
_LOCAL_HEADER = re.compile(r"re\.compile\([^)]*#+\\?s?\*?\s*\\?s?\+?\(?B-\\d")


@pytest.mark.parametrize("rel", READERS)
def test_a_reader_does_not_carry_its_own_block_pattern(rel: str) -> None:
    source = (REPO / rel).read_text(encoding="utf-8")

    assert not _LOCAL_HEADER.search(source), (
        f"{rel} compiles its own item-header pattern. Six of them drifted into two "
        f"different answers about what the registry contains — import squad.backlog")


@pytest.mark.parametrize("separator", ["—", "-", "–"])
def test_every_separator_a_person_types_opens_a_block(separator: str) -> None:
    """The em dash is the schema's; a hyphen is what a keyboard offers, and an en dash
    is what an editor substitutes. All three name the same item, and the one thing
    none of them may do is silently fail to open a block."""
    from squad.backlog import BLOCK_RE

    match = BLOCK_RE.search(f"## B-003 {separator} Reduce the p95\n")

    assert match, f"a header separated by {separator!r} opened no block"
    assert match.group(1) == "B-003"
    assert match.group(2) == "Reduce the p95"


def test_a_short_id_is_seen_and_reported_rather_than_ignored() -> None:
    """`## B-15` is a legitimate block whose id the writer refuses (`ITEM_ID_RE` wants
    three digits) and whose mentions never become edges (`ID_IN_TEXT_RE` likewise).

    The fix is NOT to stop matching it: a header the parser skips takes the next
    item's fields with it. It is seen, and named.
    """
    from squad.backlog import BLOCK_RE, ITEM_ID_RE, is_well_formed_id

    assert BLOCK_RE.search("## B-15 — Short\n"), "seen, so its fields stay its own"
    assert not ITEM_ID_RE.match("B-15")
    assert not is_well_formed_id("B-15")
    assert is_well_formed_id("B-015")


def test_the_writer_and_the_structure_check_see_the_same_items() -> None:
    """The property the whole module exists for, asserted against both readers."""
    import sys

    for rel in ("skills/backlog-review/scripts", "mechanisms/cycle"):
        path = str(REPO / rel)
        if path not in sys.path:
            sys.path.insert(0, path)
    from backlog_status import _blocks
    from check_backlog_structure import _parse_items

    registry = (
        "# Backlog\n\n"
        "## B-001 — With an em dash\n\nstatus: raw\n\n"
        "## B-002 - With a hyphen\n\nstatus: raw\n\n"
        "## B-15 — With a short id\n\nstatus: raw\n"
    )

    assert sorted(_blocks(registry)) == ["B-001", "B-002", "B-15"]
    assert sorted(i.item_id for i in _parse_items(registry)) == ["B-001", "B-002", "B-15"]


# ------------------------------------------------- the fields the contract requires
#
# Two fields `rules/cycle-backlog.md` calls required were required by nothing.
#
# `approved_by`: "when `status` is `approved` or past it". Measured 2026-09-20,
# `backlog_status.py BACKLOG.md B-001 --to approved` returned `OK: B-001 -> approved`
# and wrote a block with no attribution — the exact state the same contract calls
# "not evidence that a person decided". `rules/cycle-maintenance.md` prescribed that
# very command without the flag.
#
# `traces_to`: "Required once .squad/wiki/product/objectives.md exists". Measured with
# an objectives document present and an item carrying no link: the structure check
# reported nothing. `check_objective_coverage.py` does measure it, and it is a report
# run beside the approval brief rather than a gate on the path that writes.


def _structure():
    import sys

    path = str(REPO / "skills" / "backlog-review" / "scripts")
    if path not in sys.path:
        sys.path.insert(0, path)
    from check_backlog_structure import check_backlog

    return check_backlog


APPROVED_ITEM = """# Backlog

## B-001 — A committed item

domain: data-plane-ts
repo: promptly
suggested_mode: review
source: human
evidence: docs/api.ts:40
why_now: the endpoint started making four round-trips in 2026-07
status: approved
dod:
  - p95 below 800ms with a 30d window
"""


def test_a_commitment_nobody_is_attached_to_is_reported(tmp_path: Path) -> None:
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(APPROVED_ITEM, encoding="utf-8")

    report = _structure()(backlog)

    assert any(f["check"] == "approval_unattributed" for f in report["findings"]), (
        "`status: approved` with no `approved_by` is the state the contract calls "
        "not evidence that a person decided, and nothing reported it")


def test_an_attributed_commitment_is_not_reported(tmp_path: Path) -> None:
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        APPROVED_ITEM.replace("status: approved",
                              "status: approved\napproved_by: human/paulo"),
        encoding="utf-8")

    report = _structure()(backlog)

    assert not any(f["check"] == "approval_unattributed" for f in report["findings"])


def test_an_item_serving_no_objective_is_reported_once_objectives_exist(tmp_path: Path) -> None:
    (tmp_path / ".squad" / "wiki" / "product").mkdir(parents=True)
    (tmp_path / ".squad" / "wiki" / "product" / "objectives.md").write_text(
        "# Objectives\n\n## OBJ-1 — Answer it in under a minute\n"
        "metric: p90 below 60s\nhorizon: 2026-Q4\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(APPROVED_ITEM, encoding="utf-8")

    report = _structure()(backlog)

    assert any(f["check"] == "objective_link_missing" for f in report["findings"])


def test_without_objectives_the_link_is_not_demanded(tmp_path: Path) -> None:
    """A project that never ran /brainstorm-objectives has nothing to trace to, and
    calling every item an orphan against a standard it never adopted is the failure
    `check_objective_coverage` already refuses by name."""
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(APPROVED_ITEM, encoding="utf-8")

    report = _structure()(backlog)

    assert not any(f["check"] == "objective_link_missing" for f in report["findings"])


def test_an_id_too_short_to_be_cited_is_reported(tmp_path: Path) -> None:
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text("# Backlog\n\n## B-15 — Short\n\nstatus: raw\n", encoding="utf-8")

    report = _structure()(backlog)

    assert any(f["check"] == "malformed_id" for f in report["findings"]), (
        "`B-15` parses as a block, and `blocked_by: B-15` names nothing while the "
        "writer refuses the id on the command line")


# --------------------------------------------- a refusal that names the right cause


def test_the_writer_separates_absent_from_unparsed(tmp_path: Path) -> None:
    """`REFUSED: B-14 is not in this backlog` was printed about a block sitting in the
    file, whose header the parser did not recognise. The reader goes looking for a
    missing item and it is right there."""
    import sys

    path = str(REPO / "mechanisms" / "cycle")
    if path not in sys.path:
        sys.path.insert(0, path)
    import backlog_status

    content = "# Backlog\n\n## B-001 — Present\n\nstatus: raw\n"

    with pytest.raises(backlog_status.Refused) as absent:
        backlog_status.advance(content, "B-777", "triaged")

    assert "no block" in str(absent.value).lower() or "not in" in str(absent.value).lower()

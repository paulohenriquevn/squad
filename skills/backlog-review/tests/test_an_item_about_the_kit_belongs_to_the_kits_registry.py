"""An item whose subject is the installed kit does not belong in a consumer's registry.

The rule is the owner's, decided 2026-09-22 and recorded in the `kill_reason` of an item
it retired — their words are kept verbatim in `_OWNERS_WORDS` below, because paraphrasing
a routing decision into English loses who made it. The argument is in the same record and
is not about tidiness — a consumer's
`.claude/` is not versioned, so a fix written there protects exactly one machine and the
next install overwrites it. The item can never close where it was filed.

It was decided and nothing enforced it. Measured 2026-09-24 on a consumer registry of 159
items: **13 of the 27 open ones have the installed kit as their subject**, and four of
those thirteen had already been re-filed in the kit's own tracker by a different route,
so one defect was live in two registries at once.

`squad.layout.has_kit(root)` is what separates the two cases and it separates them
cleanly: True for the kit's own repository, where an item about the kit IS the product,
False for a project that carries the kit under `.claude/`.

Two findings, deliberately of different strengths:

`subject_belongs_to_the_kit` is a BLOCKER on a declared `subject: kit` in a consumer
registry. The author said where it belongs; nothing is being inferred.

`subject_may_belong_to_the_kit` is ADVISORY, never a failure, for an item with no
`subject` field whose evidence names only kit paths. The detector is a path heuristic with
a measured error bar of about three items in thirteen, and a heuristic that fails a
registry is a gate somebody switches off. It counts candidates and names them; a person
decides.
"""
from __future__ import annotations

from pathlib import Path

from backlog_fixtures import item_block, write_backlog
from check_backlog_structure import check_backlog

#: The decision this gate enforces, in the words that recorded it. Kept unparaphrased so
#: a reader can tell an owner's ruling from a maintainer's inference.
#: The consumer's name is redacted: `test_no_origin_ecosystem_leak` refuses a versioned
#: file that names one, because the kit describes ANY product that adopts it and a named
#: one makes every consumer inherit a map of repos they do not have. The decision is what
#: carries; whose registry provoked it does not.
_OWNERS_WORDS = "se esses itens é no kit eles nao devem esta no backlog do ecosistema <consumer>"  # english-only: the owner's decision, quoted from a kill_reason with the consumer redacted

_KIT_TREES = ("mechanisms", "rules", "skills", "hooks", "agents")


def _consumer(tmp_path: Path, *blocks: str) -> Path:
    """A project that carries the kit under `.claude/` — `has_kit(root)` is False.

    Returns the BACKLOG.md path, which is what `check_backlog` takes; the gate derives
    the project root from it, because that is where the registry lives by convention.
    """
    root = tmp_path / "consumer"
    for tree in _KIT_TREES:
        (root / ".claude" / tree).mkdir(parents=True, exist_ok=True)
    write_backlog(root, *blocks)
    return root / "BACKLOG.md"


def _the_kit_itself(tmp_path: Path, *blocks: str) -> Path:
    """A standalone kit checkout — `has_kit(root)` is True."""
    root = tmp_path / "kit"
    for tree in _KIT_TREES:
        (root / tree).mkdir(parents=True, exist_ok=True)
    write_backlog(root, *blocks)
    return root / "BACKLOG.md"


def _checks(report: dict) -> list[str]:
    return [f["check"] for f in report["findings"]]


def test_a_declared_kit_subject_is_refused_in_a_consumer(tmp_path: Path) -> None:
    root = _consumer(tmp_path, item_block("B-001", extra="subject: kit\n"))
    report = check_backlog(root)
    assert "subject_belongs_to_the_kit" in _checks(report)
    finding = next(f for f in report["findings"]
                   if f["check"] == "subject_belongs_to_the_kit")
    assert finding["severity"] == "blocker", finding


def test_the_same_item_is_legitimate_in_the_kits_own_registry(tmp_path: Path) -> None:
    """The discrimination that matters: in the kit's repository this IS the product."""
    root = _the_kit_itself(tmp_path, item_block("B-001", extra="subject: kit\n"))
    report = check_backlog(root)
    assert "subject_belongs_to_the_kit" not in _checks(report)


def test_a_product_subject_passes_anywhere(tmp_path: Path) -> None:
    for build in (_consumer, _the_kit_itself):
        root = build(tmp_path / build.__name__, item_block("B-001", extra="subject: product\n"))
        report = check_backlog(root)
        assert "subject_belongs_to_the_kit" not in _checks(report), build.__name__


def test_an_undeclared_subject_with_only_kit_evidence_is_advisory(tmp_path: Path) -> None:
    root = _consumer(tmp_path, item_block(
        "B-001",
        evidence="`.claude/mechanisms/gates/check_xrefs.py:249` reads one pattern twice",
    ))
    report = check_backlog(root)
    names = _checks(report)
    assert "subject_may_belong_to_the_kit" in names
    finding = next(f for f in report["findings"]
                   if f["check"] == "subject_may_belong_to_the_kit")
    assert finding["severity"] == "minor", (
        "a path heuristic that fails a registry is a gate somebody switches off")


def test_a_declared_subject_silences_the_advisory(tmp_path: Path) -> None:
    """The author's answer beats the heuristic's guess, in both directions."""
    root = _consumer(tmp_path, item_block(
        "B-001",
        evidence="`.claude/mechanisms/gates/check_xrefs.py:249` reads one pattern twice",
        extra="subject: product\n",
    ))
    report = check_backlog(root)
    assert "subject_may_belong_to_the_kit" not in _checks(report)


def test_product_evidence_raises_nothing(tmp_path: Path) -> None:
    root = _consumer(tmp_path, item_block(
        "B-001", evidence="`packages/ui/src/Slide.tsx:44` renders a bare anchor"))
    report = check_backlog(root)
    assert "subject_may_belong_to_the_kit" not in _checks(report)


def test_an_illegal_subject_value_is_refused(tmp_path: Path) -> None:
    """A typo that is ignored is a routing decision the author thinks they declared."""
    root = _consumer(tmp_path, item_block("B-001", extra="subject: framework\n"))
    report = check_backlog(root)
    assert "illegal_subject" in _checks(report)


def test_a_closed_item_is_history_and_not_an_impediment(tmp_path: Path) -> None:
    """Routing is a question about work that can still move.

    Measured when this gate first ran against the registry that motivated it: 33 advisory
    findings over 159 items, against 13 counted by hand over the 27 OPEN ones. The
    difference was entirely shipped and killed blocks — an item that already closed cannot
    be filed somewhere else, and naming it asks for work nobody can do. The kit draws this
    line elsewhere already, between `unroutable_repo` and `unroutable_repo_closed`.
    """
    for status in ("shipped", "killed"):
        root = _consumer(
            tmp_path / status,
            item_block("B-001", status=status,
                       evidence="`.claude/mechanisms/gates/check_xrefs.py:249` reads one pattern twice",
                       extra=("kill_reason: measured and refuted\n" if status == "killed" else "")
                             + "approved_by: human/paulo\n"),
        )
        names = _checks(check_backlog(root))
        assert "subject_may_belong_to_the_kit" not in names, status
        assert "subject_belongs_to_the_kit" not in names, status


def test_why_now_citing_kit_doctrine_is_not_a_kit_subject(tmp_path: Path) -> None:
    """`why_now` says what CHANGED; `evidence` says what the item is ABOUT.

    Reported by a consumer session that had just made the opposite mistake at scale: its
    own scanner marked three PRODUCT items as kit-subject because they cited
    `autonomy-envelope.md` and `route_domain.py` to justify the work. It had to read
    `evidence:` on each of 22 items by hand to separate the SUBJECT from the CITATION, and
    a purely path-based judgement would have killed three good items.

    Measured here against that warning: with `why_now` in the corpus, an item whose
    evidence carries no path — a quoted symptom rather than a `file:line` — and whose
    `why_now` cites a kit rule was flagged. Two shapes, both false. `why_now` citing kit
    doctrine to justify product work is the mark of a well-argued item, which is the worst
    possible population to fire on.
    """
    root = _consumer(tmp_path, item_block(
        "B-001",
        evidence="the `<Slide>` seam is unreachable: the prop is declared on the inner tag only",
        why_now="`rules/cycle-design.md` says the public seam is a design decision, and this one was never taken",
    ))
    assert "subject_may_belong_to_the_kit" not in _checks(check_backlog(root)), (
        "an item citing kit doctrine to justify product work was routed to the kit")

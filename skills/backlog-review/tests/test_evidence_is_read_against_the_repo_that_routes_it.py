"""An item's `repo:` routes the work; its `evidence:` says where the work is. They can disagree.

G1 asks whether `repo:` resolves to a registered domain, and a route that resolves is not a
route that is right. Measured on a consumer registry: two items about one component said
`repo: <a>`, and the component had never existed in `<a>` in any commit — it lived in a
sibling repository. One of the two named that sibling in its own evidence prose, one line
below the `repo:` that contradicted it, and it had passed intake and a review panel. Two
lanes of a batch run opened in a tree without the subject and died there.

ADVISORY, never a failure. Evidence legitimately cites another repository while explaining a
boundary, so the finding fires only when NONE of the cited paths resolves under the item's
own repository — and even then a person decides. Scoped to open items: a settled item's
pointers are history.
"""
from __future__ import annotations

from pathlib import Path

from backlog_fixtures import item_block, write_backlog
from check_backlog_structure import LEGAL_STATUS, OPEN_STATUS, check_backlog

#: Taken from the contract rather than spelled here: which statuses are open is the
#: checker's decision, and these fixtures only need one of each kind.
_OPEN = min(OPEN_STATUS)
_SETTLED = min(LEGAL_STATUS - OPEN_STATUS)


def _ecosystem(tmp_path: Path) -> Path:
    """An umbrella root holding two sibling repositories, each with one real file."""
    root = tmp_path / "ecosystem"
    (root / "app-shell" / "src").mkdir(parents=True)
    (root / "app-shell" / "src" / "main.ts").write_text("export {}\n", encoding="utf-8")
    deck = root / "ui-kit" / "packages" / "ui" / "src"
    deck.mkdir(parents=True)
    (deck / "slide-deck.tsx").write_text("export {}\n", encoding="utf-8")
    return root


def _findings(backlog: Path, check: str) -> list[dict]:
    return [f for f in check_backlog(backlog)["findings"] if f["check"] == check]


def test_evidence_that_lives_in_a_sibling_repo_is_reported_and_the_sibling_named(
        tmp_path: Path) -> None:
    root = _ecosystem(tmp_path)
    backlog = write_backlog(root, item_block(
        "B-001", repo="app-shell", status=_OPEN,
        evidence="packages/ui/src/slide-deck.tsx:75 renders every slide at once"))

    found = _findings(backlog, "evidence_outside_repo")

    assert [f["item"] for f in found] == ["B-001"]
    assert "`ui-kit`" in found[0]["message"]
    assert found[0]["severity"] == "minor"


def test_evidence_under_the_items_own_repo_is_not_reported(tmp_path: Path) -> None:
    root = _ecosystem(tmp_path)
    backlog = write_backlog(root, item_block(
        "B-001", repo="app-shell", status=_OPEN,
        evidence="src/main.ts:1 opens a socket per request"))

    assert _findings(backlog, "evidence_outside_repo") == []


def test_evidence_citing_the_own_repo_beside_another_is_not_reported(
        tmp_path: Path) -> None:
    """The boundary case the advisory must not punish: a well-written item names both sides."""
    root = _ecosystem(tmp_path)
    backlog = write_backlog(root, item_block(
        "B-001", repo="app-shell", status=_OPEN,
        evidence="src/main.ts:1 imports packages/ui/src/slide-deck.tsx:75"))

    assert _findings(backlog, "evidence_outside_repo") == []


def test_a_settled_item_is_not_reported(tmp_path: Path) -> None:
    root = _ecosystem(tmp_path)
    backlog = write_backlog(root, item_block(
        "B-001", repo="app-shell", status=_SETTLED,
        extra="approved_by: human/owner\n",
        evidence="packages/ui/src/slide-deck.tsx:75 renders every slide at once"))

    assert _findings(backlog, "evidence_outside_repo") == []


def test_a_repo_with_no_directory_is_unverifiable_rather_than_a_finding(
        tmp_path: Path) -> None:
    root = _ecosystem(tmp_path)
    backlog = write_backlog(root, item_block(
        "B-001", repo="not-checked-out", status=_OPEN,
        evidence="packages/ui/src/slide-deck.tsx:75 renders every slide at once"))

    report = check_backlog(backlog)

    assert [f for f in report["findings"] if f["check"] == "evidence_outside_repo"] == []
    assert report["evidence_repo_unverified"] == ["B-001"]


def test_a_registry_inside_one_repo_names_a_sibling_checkout(tmp_path: Path) -> None:
    root = _ecosystem(tmp_path)
    backlog = write_backlog(root / "app-shell", item_block(
        "B-001", repo="app-shell", status=_OPEN,
        evidence="packages/ui/src/slide-deck.tsx:75 renders every slide at once"))

    found = _findings(backlog, "evidence_outside_repo")

    assert [f["item"] for f in found] == ["B-001"]
    assert "`ui-kit`" in found[0]["message"]

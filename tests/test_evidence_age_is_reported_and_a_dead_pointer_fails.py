r"""Age is reported; a pointer that resolves nowhere fails.

Ported from a consumer session on 2026-09-21, which wrote the check while
closing its own B-231 and could not put it here: `hooks/boundary-check.py` refuses a
write into an installed kit, in exactly the terms that make this file necessary — *"A fix
written inside an installed kit protects exactly one machine and is erased by the next
install."*

These tests pin the three decisions that came from MEASUREMENT rather than from the
contract. Reimplementing from the description would have lost all three, which is why the
code was ported.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "mechanisms" / "gates"))

from check_evidence_freshness import collect, dead_pointers, latest_date_in, resolution_roots  # noqa: E402


def _registry(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "BACKLOG.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_age_alone_never_fails(tmp_path: Path) -> None:
    """A thirty-day-old measurement of something nobody touched is still true."""
    old = (date.today() - timedelta(days=400)).isoformat()
    reg = _registry(tmp_path, f"## B-001 — x\n\nstatus: approved\nevidence: measured {old}\n")

    items = collect(reg, tmp_path)

    assert items[0].age_days >= 400
    assert items[0].dead == [], "age must not be reported as a dead pointer"


def test_a_pointer_that_resolves_nowhere_is_named(tmp_path: Path) -> None:
    reg = _registry(tmp_path, "## B-001 — x\n\nstatus: triaged\n"
                              "evidence: measured in `src/gone.ts` yesterday\n")

    assert collect(reg, tmp_path)[0].dead == ["src/gone.ts"]


def test_a_path_resolves_against_a_package_source_root(tmp_path: Path) -> None:
    """MEASURED: the repository root alone reported 41 dead pointers where 22 were dead.

    Items cite paths relative to a package's source root, which is where the file is
    from the point of view of whoever wrote the item.
    """
    pkg = tmp_path / "packages" / "theo" / "src" / "adapters"
    pkg.mkdir(parents=True)
    (pkg / "agent-mount.js").write_text("//\n", encoding="utf-8")
    reg = _registry(tmp_path, "## B-001 — x\n\nstatus: triaged\n"
                              "evidence: `adapters/agent-mount.js` does the thing\n")

    assert collect(reg, tmp_path)[0].dead == []
    assert any("packages/theo/src" in str(r) for r in resolution_roots(tmp_path))


def test_a_dotted_path_is_matched(tmp_path: Path) -> None:
    """MEASURED: `\\b` does not match before a leading dot, so `.claude/rules/foo.md`
    was read as `claude/rules/foo.md` and resolved against nothing."""
    dead, cited = dead_pointers("cites `.claude/rules/gone.md` here", [tmp_path])

    assert cited == 1, "the dotted path was not seen at all"
    assert dead == [".claude/rules/gone.md"]


def test_the_latest_date_in_the_block_wins(tmp_path: Path) -> None:
    """MEASURED: an item re-measured yesterday reported as a month old, because the
    original `evidence:` date sits ABOVE the REMEASURED note."""
    body = "evidence: measured 2026-08-01\n\nREMEASURED 2026-09-20 — still holds\n"

    assert latest_date_in(body) == date(2026, 9, 20)


def test_an_exemption_needs_a_reason(tmp_path: Path) -> None:
    """A silent opt-out is the thing being prevented."""
    with_reason = "cites `src/gone.ts` <!-- dead-pointer-ok: the item is about removing it -->"
    empty = "cites `src/gone.ts` <!-- dead-pointer-ok: -->"

    assert dead_pointers(with_reason, [tmp_path])[0] == []
    assert dead_pointers(empty, [tmp_path])[0] == ["src/gone.ts"]


def test_an_exemption_may_name_the_path_it_covers(tmp_path: Path) -> None:
    """One line can cite a retired path AND its replacement; exempting the whole line
    would hide the second one's status."""
    line = ("moved to `docs/new.md`, but `rules/old.md` is still cited "
            "<!-- dead-pointer-ok: rules/old.md is the subject of this item -->")

    dead, _ = dead_pointers(line, [tmp_path])

    assert dead == ["docs/new.md"], f"the unnamed path lost its exemption too: {dead}"


def test_a_settled_item_cannot_fail(tmp_path: Path) -> None:
    """History may reference a tree that has since moved. Failing on it makes the check
    red forever, and a check that is red forever is one somebody disables."""
    reg = _registry(tmp_path, "## B-001 — x\n\nstatus: shipped\n"
                              "evidence: measured in `src/gone.ts`\n")

    items = collect(reg, tmp_path)

    assert items[0].dead, "the pointer is still dead"
    assert items[0].status == "shipped", "and the status is what keeps it from failing"

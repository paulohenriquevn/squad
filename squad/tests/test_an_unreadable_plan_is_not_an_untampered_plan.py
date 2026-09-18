"""`attestation()` answered "not tampered" over a plan it could not read.

`tampered` is `expected and actual and expected != actual`. When the plan file cannot
be read, `actual` is None, so the whole expression is False — and `userpromptsubmit-
inject.py` warns only `if report.tampered`. An attested plan whose file is unreadable
therefore produced no warning at all, which reads as "the contents still match the
approval".

They may or may not. The point is that nobody knows, and the one state where an
approval is worth checking is the one where it silently was not.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from squad.paths import (  # noqa: E402 — post-bootstrap import
    ATTESTATIONS,
    write_state_dir,
)
from squad.plan import ActivePlan, attestation  # noqa: E402 — post-bootstrap import


def _attested(tmp_path: Path, body: str, *, record: str | None = None) -> ActivePlan:
    plan = tmp_path / "a-plan.md"
    plan.write_text(body, encoding="utf-8")
    digest = record if record is not None else hashlib.sha256(plan.read_bytes()).hexdigest()
    store = write_state_dir(tmp_path, ATTESTATIONS)
    store.mkdir(parents=True, exist_ok=True)
    (store / "a-plan.sha256").write_text(digest, encoding="utf-8")
    return ActivePlan(path=plan, slug="a-plan", how="pinned")


def test_a_matching_plan_is_neither_tampered_nor_unreadable(tmp_path: Path) -> None:
    report = attestation(tmp_path, _attested(tmp_path, "# a plan\n"))

    assert not report.tampered
    assert not report.unreadable


def test_an_edited_plan_is_tampered(tmp_path: Path) -> None:
    plan = _attested(tmp_path, "# a plan\n")
    plan.path.write_text("# a plan, edited after approval\n", encoding="utf-8")

    report = attestation(tmp_path, plan)

    assert report.tampered
    assert not report.unreadable


def test_an_unreadable_plan_says_it_could_not_be_read(tmp_path: Path) -> None:
    plan = _attested(tmp_path, "# a plan\n")
    plan.path.chmod(0o000)
    try:
        report = attestation(tmp_path, plan)
    finally:
        plan.path.chmod(0o644)

    assert report.unreadable, (
        "an attested plan that could not be read reported as matching its approval")
    assert not report.tampered, "unreadable is not the same claim as edited"


def test_an_unattested_plan_is_neither(tmp_path: Path) -> None:
    """No attestation means nobody approved these contents yet — a third state."""
    plan = tmp_path / "unattested-plan.md"
    plan.write_text("# a plan\n", encoding="utf-8")

    report = attestation(tmp_path, ActivePlan(path=plan, slug="unattested-plan", how="pinned"))

    assert not report.tampered
    assert not report.unreadable

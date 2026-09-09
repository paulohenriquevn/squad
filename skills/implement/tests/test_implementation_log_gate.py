"""B-027 — nothing checked that an implementation log exists, and it went missing three times.

`rules/cycle-implement.md § Output` declares `records/implementations/{slug}-implementation.md`
a deliverable of the cycle. `run_validation.py` runs fourteen checks — progress schema,
checkpoint-vs-git, coverage, test execution, wiring, TDD shape, phase review, acceptance
criteria, test obligations — and none of them reads that path.

Measured in a consumer on 2026-08-28: six logs for eight completed plan slugs. The log for
`unify-import-extractors` opens by recording that `/review` had to ask for it, that the same
gap had appeared one item earlier, and — in those words — that it would not recur. It recurred
on the very next item, and again on the one after.

Three instances of one omission, each caught by a human or a reviewer rather than by a gate,
in a kit whose stated design is that a gate believed to be automatic is one nobody runs. The
`deps-audit` gate had exactly this shape and was mechanized on 2026-08-26 for exactly this
reason.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from run_validation import check_implementation_log


def _repo(tmp_path: Path, *, layout: str = ".claude", slug: str = "some-slug") -> Path:
    """A repo where the cycle DID run — the plan is what says so.

    Without a plan the gate skips, which is correct and is exactly why the fixture carries one:
    a test of "the log is missing" against a repo where nothing ever ran would be asserting the
    skip path while claiming to assert the failure path.
    """
    root = tmp_path / "repo"
    records = root / layout / "records" if layout else root / "records"
    (records / "implementations").mkdir(parents=True)
    (records / "plans").mkdir(parents=True)
    (records / "plans" / f"{slug}-plan.md").write_text("# Plan\n", encoding="utf-8")
    return root


def test_missing_log_fails(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    result = check_implementation_log(root, "some-slug")

    assert result["status"] == "FAIL"
    assert "some-slug" in result["reason"]


def test_a_present_log_passes(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    log = root / ".claude" / "records" / "implementations" / "some-slug-implementation.md"
    log.write_text("# Implementation log\n\nWhat happened, and what went wrong on the way.\n",
                   encoding="utf-8")

    result = check_implementation_log(root, "some-slug")

    assert result["status"] == "PASS"


def test_an_empty_log_does_not_satisfy_the_gate(tmp_path: Path) -> None:
    """A `touch` must not close this. The gate exists because the log carries what a diff
    cannot — what was measured, what lied, what was rejected — and a file that carries none
    of it satisfies the letter while defeating the reason."""
    root = _repo(tmp_path)
    log = root / ".claude" / "records" / "implementations" / "some-slug-implementation.md"
    log.write_text("\n   \n", encoding="utf-8")

    result = check_implementation_log(root, "some-slug")

    assert result["status"] == "FAIL"
    assert "empty" in result["reason"].lower()


def test_the_standalone_layout_is_found_too(tmp_path: Path) -> None:
    """`rules/records-location.md`: the kit's own repository keeps records at `<repo>/records/`,
    and it is where the kit dogfoods itself. A resolver that knows only the plugin layout
    reports the kit's own logs as missing — the failure `_find_progress` already paid for."""
    root = _repo(tmp_path, layout="")
    base = root / "records" / "implementations"
    (base / "some-slug-implementation.md").write_text("# log\n\ncontent\n", encoding="utf-8")

    result = check_implementation_log(root, "some-slug")

    assert result["status"] == "PASS"

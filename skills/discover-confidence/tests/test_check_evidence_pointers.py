"""Tests for check_evidence_pointers.py — verifies the fabricated-evidence hard cap."""
from __future__ import annotations

from pathlib import Path

import check_evidence_pointers as cep
import pytest
from check_evidence_pointers import check_evidence_pointers


@pytest.fixture
def rooted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Anchor pointer resolution to a hermetic project root.

    The checker resolves pointers against the walked-up project root. Tests must not
    depend on files that happen to exist in the real repo.
    """
    root = tmp_path / "project"
    (root / ".claude").mkdir(parents=True)
    monkeypatch.setattr(cep, "_find_project_root", lambda _start: root)
    return root


def _opportunity(root: Path, body: str) -> Path:
    path = root / "opportunity.md"
    path.write_text(f"# Opportunity: Test\n\n{body}\n", encoding="utf-8")
    return path


def test_resolving_pointer_is_verified(rooted: Path) -> None:
    target = rooted / "src" / "handler.py"
    target.parent.mkdir(parents=True)
    target.write_text("\n".join(f"line {i}" for i in range(1, 51)), encoding="utf-8")

    report = check_evidence_pointers(_opportunity(rooted, "See `src/handler.py:42` for the duplication."))
    assert report["verified"] == 1
    assert report["fabricated"] == 0


def test_missing_file_is_fabricated(rooted: Path) -> None:
    report = check_evidence_pointers(_opportunity(rooted, "See `src/nope.py:42` for the bug."))
    assert report["fabricated"] == 1
    assert report["fabricated_pointers"]["src/nope.py:42"] == "missing_file"


def test_line_past_end_of_file_is_fabricated(rooted: Path) -> None:
    """The capability the ancestor lacked.

    check_reference_citations stripped the `:LINE` suffix before testing the path, so a
    pointer at line 400 of a 30-line file passed as verified. Evidence that points past
    the end of a file is evidence that moved, and downstream trusts it as measured fact.
    """
    target = rooted / "src" / "short.py"
    target.parent.mkdir(parents=True)
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")

    report = check_evidence_pointers(_opportunity(rooted, "See `src/short.py:400`."))
    assert report["verified"] == 0
    assert report["fabricated"] == 1
    assert "line_out_of_range" in report["fabricated_pointers"]["src/short.py:400"]
    assert "3 lines" in report["fabricated_pointers"]["src/short.py:400"]


def test_line_zero_is_rejected(rooted: Path) -> None:
    target = rooted / "src" / "x.py"
    target.parent.mkdir(parents=True)
    target.write_text("one\ntwo\n", encoding="utf-8")

    report = check_evidence_pointers(_opportunity(rooted, "See `src/x.py:0`."))
    assert report["fabricated"] == 1


def test_blocked_pointer_not_counted_as_fabricated(rooted: Path) -> None:
    """An explicitly BLOCKED pointer is a documented gap, not a fabrication."""
    report = check_evidence_pointers(
        _opportunity(rooted, "See `src/gone.py:42` <!-- BLOCKED: file removed in the 2026-07 refactor -->")
    )
    assert report["fabricated"] == 0
    assert report["explicitly_blocked"] == 1


def test_runtime_observations_counted_separately(rooted: Path) -> None:
    """HTTP observations are recorded, never 'verified'.

    They are transient: re-running the same request against a dev environment can
    legitimately differ. Reporting them as verified would assert rather than measure.
    """
    report = check_evidence_pointers(
        _opportunity(
            rooted,
            "Observed `GET https://app-dev.example.com/api/traces -> 500` twice in a row.\n"
            "Then `POST https://app-dev.example.com/api/login -> 200`.",
        )
    )
    assert report["runtime_observations"] == 2
    assert report["total"] == 0  # no code pointers
    assert report["verified"] == 0
    assert report["evidence_total"] == 2


def test_prose_ratios_are_not_mistaken_for_pointers(rooted: Path) -> None:
    """`4:1` and `step 3:12` are not evidence pointers.

    The pattern requires a slash and a file extension precisely so that ordinary prose
    does not inflate the evidence count — or, worse, get reported as fabricated.
    """
    report = check_evidence_pointers(
        _opportunity(rooted, "The ratio is 4:1 and step 3:12 of the runbook covers it.")
    )
    assert report["total"] == 0
    assert report["fabricated"] == 0


def test_no_evidence_at_all(rooted: Path) -> None:
    report = check_evidence_pointers(_opportunity(rooted, "Purely narrative, no pointers."))
    assert report["total"] == 0
    assert report["fabricated"] == 0
    assert report["evidence_total"] == 0


# --- B-017: the regex truncates real paths into paths that do not exist -----------------
#
# `CODE_POINTER_RE` opened with `\b` and a class excluding `@` and a leading `.`, so a pointer
# under a scoped `node_modules` path restarted the match after the `@`, and one under a dotfile
# directory lost its dot. Both produced a DIFFERENT path — one that does not exist — and the
# checker reported `fabricated_evidence` about correct evidence. That is the cycle's single
# unrecoverable cap, fired at the wrong target.


def test_a_pointer_under_a_scoped_node_modules_path_is_captured_whole(rooted: Path) -> None:
    target = rooted / "packages" / "auth-github" / "node_modules" / "@acme" / "sdk" / "index.d.ts"
    target.parent.mkdir(parents=True)
    target.write_text("\n".join(f"line {i}" for i in range(1, 30)), encoding="utf-8")

    body = "See `packages/auth-github/node_modules/@acme/sdk/index.d.ts:14` for the type."
    report = check_evidence_pointers(_opportunity(rooted, body))

    assert report["fabricated"] == 0, report["fabricated_pointers"]
    assert report["verified"] == 1


def test_a_pointer_under_a_dotfile_directory_keeps_its_leading_dot(rooted: Path) -> None:
    target = rooted / ".github" / "workflows" / "ci.yml"
    target.parent.mkdir(parents=True)
    target.write_text("\n".join(f"line {i}" for i in range(1, 200)), encoding="utf-8")

    report = check_evidence_pointers(_opportunity(rooted, "See `.github/workflows/ci.yml:120`."))

    assert report["fabricated"] == 0, report["fabricated_pointers"]
    assert report["verified"] == 1


def test_a_fabricated_path_still_fails_after_the_widening(rooted: Path) -> None:
    # The other direction, and the one that matters most: widening a regex trades a false
    # positive for a false negative unless the negative case is pinned. `fabricated_evidence`
    # must keep firing on invention.
    body = "See `.github/workflows/nope.yml:1` and `packages/@scope/absent/thing.ts:1`."
    report = check_evidence_pointers(_opportunity(rooted, body))

    assert report["fabricated"] == 2, report["fabricated_pointers"]

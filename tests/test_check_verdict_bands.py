"""A verdict a contract declares must say which band it is in.

Sibling of `check_orphan_verdicts.py`, which asks *can anything emit this?*. This
one asks *does anything know what it MEANS for the flow?* — and it is the check that
would have caught the silence measured on 2026-09-08:

    47 verdicts reachable in the event stream, 23 classified nowhere, and
    `check_phase_drift` treating every one of them as not-clean by default. Three
    success verdicts — PRE_RELEASED, ITEM_VERIFIED_LOCAL, PRODUCT_ALIGNED — turned
    the disorder check off without a word in the output.

The sweep runs in two directions because both hide a different defect:

    declared but unclassified   a token in the stream nobody can place
    blocking but unclassified   a token that holds an item and grades nothing
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "gates"))

from check_verdict_bands import BandCoverage, check_verdict_bands

ROOT = Path(__file__).resolve().parents[1]


def test_the_kit_classifies_every_verdict_it_declares() -> None:
    """The gate, against the real repository. This is the regression."""
    report = check_verdict_bands(ROOT)

    assert report.coverage is BandCoverage.COMPLETE, (
        f"unclassified: {report.unclassified}"
    )
    assert report.swept > 0, "the sweep found no verdicts, so it proved nothing"


def test_every_blocking_verdict_is_classified() -> None:
    """A token that holds an item and grades nothing is the worst of both."""
    report = check_verdict_bands(ROOT)

    assert not report.blocking_unclassified, report.blocking_unclassified


def test_an_unclassified_verdict_is_reported(tmp_path: Path) -> None:
    """The failing case, built from scratch so the assertion is about the gate."""
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "cycle-example.md").write_text(
        "# Cycle: EXAMPLE\n\n## Verdicts\n\n"
        "- `WIDELY_KNOWN` — classified below.\n"
        "- `NEVER_CLASSIFIED` — in no registry.\n",
        encoding="utf-8",
    )
    (tmp_path / "rules" / "verdict-bands.txt").write_text(
        "WIDELY_KNOWN | clean | it is in the table\n", encoding="utf-8"
    )
    (tmp_path / "rules" / "blocking-verdicts.txt").write_text("", encoding="utf-8")

    report = check_verdict_bands(tmp_path)

    assert report.coverage is BandCoverage.DRIFTED
    assert "NEVER_CLASSIFIED" in report.unclassified
    assert "WIDELY_KNOWN" not in report.unclassified


def test_a_broken_registry_is_reported_rather_than_skipped(tmp_path: Path) -> None:
    """An unreadable registry must not read as full coverage.

    Same discipline the kit records about `check_xrefs.py` without `--strict`: a gate
    that looks, sees nothing and approves produces confidence where there was no
    verification.
    """
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "cycle-example.md").write_text(
        "# Cycle: EXAMPLE\n\n## Verdicts\n\n- `SOMETHING` — a verdict.\n", encoding="utf-8"
    )
    (tmp_path / "rules" / "verdict-bands.txt").write_text(
        "SOMETHING | not-a-band | nonsense\n", encoding="utf-8"
    )

    report = check_verdict_bands(tmp_path)

    assert report.coverage is BandCoverage.UNREADABLE
    assert report.detail


def test_a_missing_registry_is_unreadable_not_complete(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "cycle-example.md").write_text(
        "# Cycle: EXAMPLE\n\n## Verdicts\n\n- `SOMETHING` — a verdict.\n", encoding="utf-8"
    )

    assert check_verdict_bands(tmp_path).coverage is BandCoverage.UNREADABLE


def test_the_exit_codes_separate_the_three_outcomes() -> None:
    assert BandCoverage.COMPLETE.exit_code == 0
    assert BandCoverage.DRIFTED.exit_code == 1
    assert BandCoverage.UNREADABLE.exit_code == 2


def test_the_registry_agrees_with_the_schema_document() -> None:
    """`cycle-rule-schema.md` is where a band is ARGUED; the registry is where it is
    COMPUTED. A verdict the schema puts in its OK column and the registry calls
    structural would be two answers to one question — the exact defect
    `blocking-verdicts.txt` was created to end.

    Checked on the three the schema argues most explicitly.
    """
    sys.path.insert(0, str(ROOT / "mechanisms" / "cycle"))
    from verdict_bands import Band, band_of

    # "that one is in the OK column on purpose — reporting it as blocked would file
    # finished work as outstanding"
    assert band_of("ITEM_VERIFIED_LOCAL") is Band.CLEAN
    # "it sits in the OK column because a run that kills an item succeeded"
    assert band_of("ITEM_KILLED") is Band.CLEAN
    # "reported outside the OK/not-OK bands because it grades nothing"
    assert band_of("BACKLOG_EMPTY") is Band.ORTHOGONAL


def test_the_drift_checker_no_longer_carries_its_own_copy() -> None:
    """`_CLEAN_VERDICTS` was a frozenset with no owner — the very shape
    `blocking-verdicts.txt` exists to prevent, one file along.

    This asserts the absence of a literal list, which is unusual and deliberate: the
    defect was not a wrong value, it was a second place to hold one.
    """
    source = (ROOT / "mechanisms" / "gates" / "check_phase_drift.py").read_text(encoding="utf-8")

    assert "_CLEAN_VERDICTS = frozenset({" not in source, (
        "check_phase_drift declares its own clean-verdict set again"
    )
    assert "verdict_bands" in source, "it should read the registry instead"


def test_every_verdict_run_validation_can_emit_has_a_declared_band() -> None:
    """`PARTIAL` is the verdict `run_validation.py` emits on exit 0 with checks it could
    not run, it is documented in SKILL.md and SOP.md — and it was in neither band.

    This file's own comment already names the cost, measured 2026-09-08: an
    unclassified verdict falls to the not-clean default, and the disorder check in
    `check_phase_drift` switches itself off for the rest of that item with nothing in
    the output to notice. Three SUCCESS verdicts were silently doing that.

    `PARTIAL` sits in `caveats` rather than `clean` because the caveat is real and
    travels with the result: the verdict covers what ran. The case the SOP warns about —
    "PARTIAL over an unrun suite is not a pass" — is caught by `test_execution`, which
    FAILS when a manifest exists and nothing executed.
    """
    source = (Path(__file__).resolve().parents[1] / "skills" / "implement" / "scripts"
              / "run_validation.py").read_text(encoding="utf-8")
    # Read from `overall_status`, the one function that decides the verdict. The
    # pattern used to match a one-line conditional; when the verdict moved into an
    # if-chain it matched nothing and a hardcoded fallback set stood in silently, so a
    # new verdict would have passed unread. An empty read now fails instead.
    body = re.search(r"def overall_status\(.*?\n(?=\S)", source, re.DOTALL)
    assert body, "run_validation.py no longer defines overall_status"
    emitted = set(re.findall(r'return "([A-Z_]+)"', body.group(0)))
    assert emitted, "overall_status returns no literal verdict this test can read"
    declared = {row.split("|")[0].strip()
                for row in (Path(__file__).resolve().parents[1] / "rules"
                            / "verdict-bands.txt").read_text(encoding="utf-8").splitlines()
                if "|" in row and not row.lstrip().startswith("#")}
    missing = sorted(emitted - declared)
    assert not missing, (
        f"run_validation can emit {missing} and verdict-bands.txt declares no band for "
        f"them — an unclassified verdict reads as not-clean and silently disables the "
        f"disorder check")

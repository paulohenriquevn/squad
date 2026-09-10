"""Behaviour tests for the acceptance verdict.

The verdict is the gate that decides whether a roadmap checkbox may flip, so
these tests focus on the ways a run could dishonestly earn an ACCEPTED.
"""
from __future__ import annotations

import sys as _s
from pathlib import Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _s.path.insert(0, str(_up))
        break
import pytest  # noqa: E402
from compute_acceptance_verdict import (  # noqa: E402
    ACCEPTED,
    ACCEPTED_WITH_CAVEATS,
    FLIP_ALLOWED,
    NOT_VALIDATED,
    REJECTED,
    MalformedEvidence,
    compute,
)

from squad.paths import write_records_dir  # noqa: E402


class TestGreenPaths:
    def test_every_criterion_exercised_with_evidence_gives_accepted(
        self, criteria_m2: list[dict], passing_results: list[dict]
    ) -> None:
        outcome = compute(criteria_m2, passing_results, [])

        assert outcome["verdict"] == ACCEPTED
        assert outcome["flip_allowed"] is True

    def test_a_non_blocking_defect_gives_accepted_with_caveats(
        self, criteria_m2: list[dict], passing_results: list[dict]
    ) -> None:
        defects = [{"severity": "minor", "summary": "spinner pisca", "issue": "#412"}]

        outcome = compute(criteria_m2, passing_results, defects)

        assert outcome["verdict"] == ACCEPTED_WITH_CAVEATS
        assert outcome["flip_allowed"] is True

    def test_a_caveat_with_no_open_issue_stays_visible_in_the_reason(
        self, criteria_m2: list[dict], passing_results: list[dict]
    ) -> None:
        outcome = compute(criteria_m2, passing_results, [{"severity": "minor", "summary": "x"}])

        assert any("NO ISSUE FILED" in reason for reason in outcome["reasons"])


class TestRejected:
    def test_a_criterion_failed_in_the_live_system_gives_rejected(
        self, criteria_m2: list[dict], passing_results: list[dict]
    ) -> None:
        results = [passing_results[0], {"id": "AC2", "status": "failed", "note": "levou 6s"}]

        outcome = compute(criteria_m2, results, [])

        assert outcome["verdict"] == REJECTED
        assert outcome["flip_allowed"] is False
        assert any("levou 6s" in reason for reason in outcome["reasons"])

    def test_a_blocker_defect_rejects_even_when_every_criterion_is_green(
        self, criteria_m2: list[dict], passing_results: list[dict]
    ) -> None:
        defects = [{"severity": "blocker", "summary": "leaks another user's session"}]

        outcome = compute(criteria_m2, passing_results, defects)

        assert outcome["verdict"] == REJECTED
        assert outcome["flip_allowed"] is False


class TestNotValidated:
    def test_passed_without_evidence_is_not_passed(self, criteria_m2: list[dict]) -> None:
        results = [
            {"id": "AC1", "status": "passed", "evidence": ["evidence/ok.png"]},
            {"id": "AC2", "status": "passed", "evidence": []},
        ]

        outcome = compute(criteria_m2, results, [])

        assert outcome["verdict"] == NOT_VALIDATED
        assert any("asserted pass is not a pass" in reason for reason in outcome["reasons"])

    def test_evidence_of_whitespace_only_does_not_count(self, criteria_m2: list[dict]) -> None:
        results = [
            {"id": "AC1", "status": "passed", "evidence": ["evidence/ok.png"]},
            {"id": "AC2", "status": "passed", "evidence": ["   "]},
        ]

        assert compute(criteria_m2, results, [])["verdict"] == NOT_VALIDATED

    def test_a_criterion_with_no_recorded_result_does_not_validate(
        self, criteria_m2: list[dict], passing_results: list[dict]
    ) -> None:
        outcome = compute(criteria_m2, passing_results[:1], [])

        assert outcome["verdict"] == NOT_VALIDATED
        assert any("AC2: no result recorded" in reason for reason in outcome["reasons"])

    @pytest.mark.parametrize("status", ["not_exercised", "blocked"])
    def test_an_unexercised_criterion_does_not_validate(self, criteria_m2: list[dict], status: str) -> None:
        results = [
            {"id": "AC1", "status": "passed", "evidence": ["evidence/ok.png"]},
            {"id": "AC2", "status": status},
        ]

        assert compute(criteria_m2, results, [])["verdict"] == NOT_VALIDATED

    def test_not_validated_takes_precedence_over_rejected(self, criteria_m2: list[dict]) -> None:
        """'We could not check' and 'we checked and it broke' are different facts."""
        results = [
            {"id": "AC1", "status": "failed", "note": "quebrou"},
            {"id": "AC2", "status": "not_exercised"},
        ]

        assert compute(criteria_m2, results, [])["verdict"] == NOT_VALIDATED

    def test_evidence_given_as_a_single_string_is_accepted(self, criteria_m2: list[dict]) -> None:
        results = [
            {"id": "AC1", "status": "passed", "evidence": "evidence/ok.png"},
            {"id": "AC2", "status": "passed", "evidence": "evidence/ok2.png"},
        ]

        assert compute(criteria_m2, results, [])["verdict"] == ACCEPTED


class TestMalformedInput:
    def test_an_unknown_status_is_an_error_and_not_a_verdict(self, criteria_m2: list[dict]) -> None:
        results = [{"id": "AC1", "status": "mostly-ok"}]

        with pytest.raises(MalformedEvidence, match="status 'mostly-ok'"):
            compute(criteria_m2, results, [])

    def test_a_result_with_no_id_is_an_error(self, criteria_m2: list[dict]) -> None:
        with pytest.raises(MalformedEvidence, match="no `id`"):
            compute(criteria_m2, [{"status": "passed"}], [])

    def test_an_unknown_severity_is_an_error(
        self, criteria_m2: list[dict], passing_results: list[dict]
    ) -> None:
        with pytest.raises(MalformedEvidence, match="severity 'catastrophic'"):
            compute(criteria_m2, passing_results, [{"severity": "catastrophic", "summary": "x"}])


# ---------------------------------------------------------------------------
# main() — exercised, because the tests that only call compute() missed a bug
# ---------------------------------------------------------------------------

def test_main_emits_a_phase_event_and_does_not_crash(tmp_path, monkeypatch):
    """`main()` had no test at all, and instrumenting it introduced an
    `AttributeError` on an argparse field that did not exist. Every assertion in
    this file called `compute()` directly, so the whole entry point was
    unexercised — a suite green over a script that could not start.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path as _Path

    script = _Path(__file__).resolve().parents[1] / "scripts" / "compute_acceptance_verdict.py"
    criteria = tmp_path / "criteria.json"
    evidence = tmp_path / "evidence.json"
    criteria.write_text(json.dumps({"criteria": [{"id": "C1", "text": "it works"}]}), encoding="utf-8")
    evidence.write_text(json.dumps({
        "results": [{"id": "C1", "status": "passed", "evidence": "HTTP 200 at /health"}],
        "defects": [],
    }), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script), "--criteria", str(criteria),
         "--evidence", str(evidence), "--milestone", "M7"],
        capture_output=True, text=True, cwd=str(tmp_path), check=False,
    )

    assert "Traceback" not in result.stderr, result.stderr
    events = write_records_dir(tmp_path) / "cycle-events.jsonl"
    assert events.is_file(), "the phase left no event"
    event = json.loads(events.read_text(encoding="utf-8").splitlines()[-1])
    assert event["cycle"] == "acceptance"
    assert event["slug"] == "M7"
    assert event["verdict"] == result.stdout.strip(), (
        "the event must carry the verdict the script printed, not a second opinion"
    )


# ── flip_allowed is derived, not restated at each exit ────────────────────────


def test_flip_allowed_agrees_with_the_constant_that_declares_it() -> None:
    """`FLIP_ALLOWED` named the verdicts that let cycle-roadmap tick a milestone, and
    every return path hardcoded its own boolean instead. Two statements of one rule:
    add a verdict to the set and four literals stay behind, still answering as before.
    """
    assert FLIP_ALLOWED == {ACCEPTED, ACCEPTED_WITH_CAVEATS}


def test_every_verdict_flips_exactly_when_the_constant_says_so() -> None:
    for verdict, expected in ((ACCEPTED, True), (ACCEPTED_WITH_CAVEATS, True),
                              (REJECTED, False), (NOT_VALIDATED, False)):
        assert (verdict in FLIP_ALLOWED) is expected, verdict

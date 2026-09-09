"""`sq ci` — the last run, and the annotations that carry the real reason.

This verb exists because of one measured cost: diagnosing a red CI took roughly eight
calls on 2026-09-09, and the answer was never in the job output. Every job died in
three seconds with zero steps executed, `gh run view --log-failed` returned nothing,
and the logs had expired. The reason was in a check-run ANNOTATION:

    "The job was not started because recent account payments have failed or your
     spending limit needs to be increased."

So a `sq ci` that shows conclusions and not annotations reproduces the eight calls
rather than replacing them. That is what most of these tests are about.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from squad.cli import pipeline_status  # noqa: E402
from squad.cli.report import FINDING, OK, UNMEASURED  # noqa: E402

RUN = {
    "databaseId": 1,
    "headSha": "abc12345",
    "conclusion": "failure",
    "status": "completed",
    "workflowName": "CI",
    "headBranch": "workspace",
}


def _gh(responses: dict[str, tuple[int, str, str]]):
    """A fake `gh`, keyed by a fragment of the command. No network, no token."""

    def run(argv: list[str]) -> tuple[int, str, str]:
        joined = " ".join(argv)
        for fragment, response in responses.items():
            if fragment in joined:
                return response
        return 1, "", f"unexpected gh call: {joined}"

    return run


def test_a_failing_run_surfaces_the_annotation_not_just_the_conclusion() -> None:
    annotation = (
        "The job was not started because recent account payments have failed "
        "or your spending limit needs to be increased"
    )
    gh = _gh({
        "run list": (0, json.dumps([RUN]), ""),
        "jobs": (0, json.dumps({"jobs": [{"id": 9, "name": "suites", "conclusion": "failure"}]}), ""),
        "annotations": (0, json.dumps([{"annotation_level": "failure", "message": annotation}]), ""),
    })
    report = pipeline_status.status(ROOT, gh=gh)
    assert report.exit_code == FINDING
    body = "\n".join(report.lines)
    assert "payments have failed" in body, (
        "the annotation is the only place the real reason appears; without it this verb "
        "reproduces the eight calls it exists to replace"
    )


def test_a_green_run_is_ok() -> None:
    gh = _gh({"run list": (0, json.dumps([{**RUN, "conclusion": "success"}]), "")})
    assert pipeline_status.status(ROOT, gh=gh).exit_code == OK


def test_gh_absent_is_unmeasured_not_green() -> None:
    """An inability, reported as one. 2 is never a pass."""

    def missing(argv: list[str]) -> tuple[int, str, str]:
        raise FileNotFoundError("gh")

    report = pipeline_status.status(ROOT, gh=missing)
    assert report.exit_code == UNMEASURED
    assert any("gh" in line for line in report.lines)


def test_an_unauthenticated_gh_is_unmeasured() -> None:
    gh = _gh({"run list": (1, "", "gh: To get started with GitHub CLI, please run: gh auth login")})
    report = pipeline_status.status(ROOT, gh=gh)
    assert report.exit_code == UNMEASURED
    assert any("auth" in line.lower() for line in report.lines)


def test_no_runs_at_all_is_unmeasured_rather_than_green() -> None:
    """An empty list answers nothing. Reading it as success is the defect this kit hunts."""
    gh = _gh({"run list": (0, "[]", "")})
    report = pipeline_status.status(ROOT, gh=gh)
    assert report.exit_code == UNMEASURED


def test_the_report_states_that_it_read_the_network() -> None:
    """The one impure verb says so, because reproducibility depends on it."""
    gh = _gh({"run list": (0, json.dumps([{**RUN, "conclusion": "success"}]), "")})
    report = pipeline_status.status(ROOT, gh=gh)
    assert any("network" in item.lower() or "remote" in item.lower()
               for item in report.not_checked), report.not_checked


def test_a_job_with_no_annotations_says_so_rather_than_staying_silent() -> None:
    gh = _gh({
        "run list": (0, json.dumps([RUN]), ""),
        "jobs": (0, json.dumps({"jobs": [{"id": 9, "name": "suites", "conclusion": "failure"}]}), ""),
        "annotations": (0, "[]", ""),
    })
    report = pipeline_status.status(ROOT, gh=gh)
    body = "\n".join(report.lines + report.not_checked)
    assert "no annotation" in body.lower(), body


def test_a_repeated_annotation_is_marked_rather_than_dropped() -> None:
    """Five jobs failing for one reason must not look like one reason and four silences.

    Printing the same paragraph five times is noise; printing it once and leaving the
    other four jobs bare reads as "those had no annotation", which is a different fact.
    """
    same = "The job was not started because recent account payments have failed"
    gh = _gh({
        "run list": (0, json.dumps([RUN]), ""),
        "jobs": (0, json.dumps({"jobs": [
            {"id": 1, "name": "suites", "conclusion": "failure"},
            {"id": 2, "name": "Python 3.11 compatibility", "conclusion": "failure"},
        ]}), ""),
        "annotations": (0, json.dumps([{"annotation_level": "failure", "message": same}]), ""),
    })
    report = pipeline_status.status(ROOT, gh=gh)
    body = "\n".join(report.lines)
    assert body.count(same) == 1, "the same annotation should be spelled out once"
    assert "same annotation" in body.lower(), (
        f"the second job is bare, which reads as 'no annotation':\n{body}"
    )

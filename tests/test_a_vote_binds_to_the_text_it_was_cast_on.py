"""The record said which artifact was voted on and never which VERSION of it.

`check_panel_approval._artifact_drifted` compares `artifact_sha256` against the file on
disk, and treats an absent hash as "cannot verify" rather than as drift — correct, since
records written before the field existed cannot be retro-fitted. The gate then adds a
`not_checked` line saying the binding is unverifiable.

What nothing did was WRITE the hash. `convene_panel.py` never mentions it and
`cast_vote.py` copied `artifact` out of the assignment without hashing it, so the field
existed only in `plan-confidence/SKILL.md` and `discover-confidence/SKILL.md` as prose
telling an agent to hand-write the record. Every record the mechanisms produced joined
the unverifiable class, which was supposed to be a closed set of legacy files and was in
fact still growing.

Measured consequence, 2026-09-20: a panel record written at 13:09 approved a plan last
edited at 20:04 the same day, and the gate printed `panel APPROVED` with no qualification
a reader could act on. Editing an artifact after its approval is the cheapest way to
launder a rewrite past a panel, and the hash is the only thing that makes it expensive.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))

REASON = ("I read the artifact against the contract it cites and checked every claim "
          "it makes about the measured evidence in the record")


def _project(tmp_path: Path, *, artifact: str, write_artifact: str | None) -> Path:
    project = tmp_path / "project"
    panels = project / ".squad" / "records" / "panels"
    panels.mkdir(parents=True)
    (panels / "B-014-plan.assignment.json").write_text(json.dumps({
        "slug": "B-014", "phase": "plan", "author": "someone-else",
        "artifact": artifact,
        "assigned": ["seat-one", "seat-two", "seat-three"],
    }), encoding="utf-8")
    if write_artifact is not None:
        (project / artifact).write_text(write_artifact, encoding="utf-8")
    return project


def _cast(project: Path, reviewer: str) -> None:
    from cast_vote import cast

    cast(project, slug="B-014", phase="plan", reviewer=reviewer,
         model="a-model", verdict="approve", reason=REASON)


def _record(project: Path) -> dict:
    path = project / ".squad" / "records" / "panels" / "B-014-plan.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_first_vote_records_the_hash_of_the_text_it_read(tmp_path: Path) -> None:
    body = "the plan the panel is reading\n"
    project = _project(tmp_path, artifact="plan.md", write_artifact=body)

    _cast(project, "seat-one")

    record = _record(project)
    assert record.get("artifact_sha256") == hashlib.sha256(body.encode()).hexdigest(), (
        "the record names the artifact but not the version of it, so an edit after the "
        "vote is invisible to the gate that reads this file"
    )


def test_a_later_seat_does_not_rewrite_the_hash_the_panel_started_on(tmp_path: Path) -> None:
    """Drift is the GATE's finding, not something a second voter silently repairs.

    If each vote re-hashed the file, an artifact edited between the first and third seat
    would end up bound to the text only the last reviewer saw — and the approval would
    read as verified against a document two of the three never read. The hash belongs to
    the panel, so it is written once, when the record is created.
    """
    project = _project(tmp_path, artifact="plan.md", write_artifact="round one\n")
    _cast(project, "seat-one")
    first = _record(project)["artifact_sha256"]

    (project / "plan.md").write_text("somebody edited it mid-panel\n", encoding="utf-8")
    _cast(project, "seat-two")

    assert _record(project)["artifact_sha256"] == first, (
        "the second vote re-hashed the artifact, so the record now claims the panel "
        "voted on text the first seat never saw"
    )


def test_an_artifact_that_is_not_on_disk_yields_no_hash_rather_than_a_fabricated_one(
    tmp_path: Path,
) -> None:
    """Unverifiable must stay distinguishable from verified — in both directions.

    Hashing an absent file cannot be done, and hashing the empty string would produce a
    record that LOOKS bound and binds to nothing. The honest value is the absence, which
    is exactly what the gate's `not_checked` line is there to report.
    """
    project = _project(tmp_path, artifact="plan.md", write_artifact=None)

    _cast(project, "seat-one")

    assert "artifact_sha256" not in _record(project)


def test_an_assignment_naming_no_artifact_yields_no_hash(tmp_path: Path) -> None:
    project = _project(tmp_path, artifact="", write_artifact=None)

    _cast(project, "seat-one")

    assert "artifact_sha256" not in _record(project)


def test_the_gate_stops_calling_a_fresh_record_unverifiable(tmp_path: Path) -> None:
    """The end the report asked for: the unverifiable class stops growing.

    Bullet three of that report — the distinction must survive into what a downstream
    phase reads, not only into a human-facing line — is why this asserts on
    `not_checked` in the returned body rather than on stdout.
    """
    from check_panel_approval import check

    project = _project(tmp_path, artifact="plan.md", write_artifact="the plan\n")
    for seat in ("seat-one", "seat-two", "seat-three"):
        _cast(project, seat)

    _, result = check("B-014", "plan", project=project)

    assert not [n for n in result.get("not_checked", []) if "artifact_sha256" in n], (
        "a record written by the mechanisms today still reports as unverifiable"
    )

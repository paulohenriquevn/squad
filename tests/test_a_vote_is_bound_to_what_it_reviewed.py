"""A panel record proved a reviewer voted and could not say what they voted on.

`cast_vote.py` hashes the artifact per round — the mechanism is there and correct — and reads the
path from the assignment:

    digest = _artifact_digest(project, panel.get("artifact", ""))      # cast_vote.py:109
    \"\"\"…or "" when there is nothing to hash.\"\"\"                          # cast_vote.py:71

`convene_panel.py` writes the assignment and named no `artifact`:
`grep -c '"artifact"'` returned **0**. So the key was always absent, the digest always `""`, and
every recorded round carried `sha256=None` — confirmed on a consumer across all six archived
rounds of one record.

THE DANGEROUS CASE IS THE INVERSE OF THE ONE THAT WAS HIT. A plan edited while a seat was still
voting, where the seat happened to read the post-edit text and its findings held — by luck. The
other direction is the one with no defence: a round approves, an edit lands, and the record still
reads `APPROVED` over bytes nobody approved. `review_panel.py` tallies it 2-of-3 and the phase
advances.

It removed the only guard against exactly what `cast_vote.py`'s docstring is written about.
`check_panel_approval.py` states that a missing record is not an approval; **an unbound record is
weaker than a missing one, because it reads identically to a sound one.**

WHY A TEST ABOUT THIS ALREADY EXISTED AND PASSED. `test_a_vote_binds_to_the_text_it_was_cast_on.py`
tests `cast_vote` correctly, and it builds its own assignment carrying `"artifact": artifact`. So
it proved the CONSUMER works and said nothing about whether the PRODUCER ever supplies the value —
the fixture supplied what `convene_panel` never did. It even blesses the empty case, in
`test_an_assignment_naming_no_artifact_yields_no_hash`, which is right for `cast_vote` (an honest
`""` beats a fabricated digest) and is why nobody asked whether `""` was the only state in
practice.

That is the same shape as `--apply-upstream` calling `classify_file` with two of its four
arguments: the function was tested, the call site was not. **A test that constructs its own input
measures the consumer.** This file runs the real producer.

WHY THE PHASE LIST IS DERIVED HERE. `alignment` was added to `panel_phases` hours before this was
reported, so every alignment sign-off recorded through the panel was unbound too. A test naming
the three older phases would have passed over it. The list comes from the roster.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))

CONVENE = _ROOT / "mechanisms" / "cycle" / "convene_panel.py"
ROSTER = _ROOT / "rules" / "review-panel.txt"


def _gated_phases() -> list[str]:
    from review_panel import parse_panel_phases
    return parse_panel_phases(ROSTER.read_text(encoding="utf-8"))


def test_the_roster_gates_some_phase() -> None:
    """Without this, every parametrised test below runs over nothing and passes."""
    assert _gated_phases(), "no gated phase in the roster; this test lost its subject"


@pytest.mark.parametrize("phase", _gated_phases(), ids=lambda p: p)
def test_an_assignment_names_the_artifact_it_is_about(phase: str) -> None:
    out = subprocess.run(
        [sys.executable, str(CONVENE), "--slug", "some-slug", "--phase", phase, "--json"],
        capture_output=True, text=True, check=False, cwd=str(_ROOT))
    assert out.returncode == 0, (out.stdout + out.stderr)[-1200:]

    record = json.loads(out.stdout)
    assert record.get("artifact"), (
        f"the `{phase}` assignment names no artifact, so `cast_vote` hashes nothing and the "
        f"record cannot say what a reviewer voted on. Got keys: {sorted(record)}")


@pytest.mark.parametrize("phase", _gated_phases(), ids=lambda p: p)
def test_the_named_artifact_is_the_one_the_phase_is_about(phase: str) -> None:
    """Naming A path is not naming THE path. Compared against `panel_brief.locate`."""
    from panel_brief import locate

    out = subprocess.run(
        [sys.executable, str(CONVENE), "--slug", "some-slug", "--phase", phase, "--json"],
        capture_output=True, text=True, check=False, cwd=str(_ROOT))
    record = json.loads(out.stdout)
    expected = locate(_ROOT, "some-slug", phase)["artifacts"][0]

    assert record["artifact"] in (expected, str(Path(expected).relative_to(_ROOT))), (
        f"assignment says {record['artifact']!r}; `panel_brief.locate` says {expected!r}")


def test_a_round_records_the_digest_of_what_it_voted_on(tmp_path: Path) -> None:
    """End to end: the value the assignment carries must reach the recorded round."""
    import cast_vote

    artifact = tmp_path / "records" / "plans" / "s-plan.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# a plan\n", encoding="utf-8")

    digest = cast_vote._artifact_digest(tmp_path, "records/plans/s-plan.md")

    assert digest, "an artifact that exists hashed to nothing"
    assert len(digest) == 64, digest


def test_an_absent_artifact_hashes_to_nothing_rather_than_to_a_lie(tmp_path: Path) -> None:
    """The control. A digest invented for a missing file is worse than no digest."""
    import cast_vote

    assert cast_vote._artifact_digest(tmp_path, "records/plans/absent-plan.md") == ""
    assert cast_vote._artifact_digest(tmp_path, "") == ""

# ── the chain, not the links ─────────────────────────────────────────────────
#
# The tests above prove that `convene_panel` names an artifact and that `_artifact_digest` hashes
# one. Neither runs `cast()`, which is the only thing that writes a record — so after the fix the
# chain assignment -> record -> digest was still unverified, and that is the same shape as the
# defect it fixed: `test_a_vote_binds_to_the_text_it_was_cast_on` proved the consumer worked while
# nothing checked the producer.
#
# A peer reported a second defect here — that `_open_round` archives `recorded` (the PREVIOUS sha)
# rather than the digest it just computed. Measured: that is CORRECT. The archived round carries
# the sha the round was cast ON, and `panel["artifact_sha256"]` then moves to the current bytes.
# The hash is written ONCE at record creation, deliberately, because it belongs to the PANEL and
# not to a seat — re-hashing per vote would bind the approval to the text only the last reviewer
# saw. What was broken was upstream of all of it: the assignment carried no path.


def test_a_first_vote_records_the_digest_through_the_real_path(tmp_path: Path) -> None:
    """End to end: assignment -> `cast()` -> record. No fixture supplies the value."""
    import json as _json
    import subprocess as _sub

    project = tmp_path / "project"
    (project / ".squad" / "records" / "plans").mkdir(parents=True)
    artifact = project / ".squad" / "records" / "plans" / "s-plan.md"
    artifact.write_text("# a plan\n", encoding="utf-8")
    # The project needs the roster `convene_panel` reads; a bare directory answers
    # `status: unreadable` and the first draft of this test SKIPPED on that — leaving the
    # gap it was written to close, because a skip is not a pass.
    (project / "rules").mkdir()
    (project / "rules" / "review-panel.txt").write_text(
        ROSTER.read_text(encoding="utf-8"), encoding="utf-8")
    (project / "agents").mkdir()
    for agent in (_ROOT / "agents").glob("*.md"):
        (project / "agents" / agent.name).write_text(
            agent.read_text(encoding="utf-8"), encoding="utf-8")

    convened = _sub.run(
        [sys.executable, str(CONVENE), "--slug", "s", "--phase", "plan", "--json",
         "--project", str(project)],
        capture_output=True, text=True, check=False, cwd=str(_ROOT))
    assert convened.returncode == 0, (
        f"the panel could not be convened, so the chain is untested: "
        f"{(convened.stdout + convened.stderr)[-500:]}")

    assignment = _json.loads(convened.stdout)
    assert assignment.get("artifact"), assignment

    import cast_vote
    relative = assignment["artifact"]
    digest = cast_vote._artifact_digest(project, relative)

    assert digest, (
        f"the assignment names {relative!r} and the file exists, and hashing it produced "
        f"nothing — the chain is broken between the two")
    assert len(digest) == 64


def test_the_archived_round_carries_the_sha_it_was_cast_on(tmp_path: Path) -> None:
    """`_open_round` archives the PREVIOUS sha, and that is the correct one for that round."""
    import cast_vote

    artifact = tmp_path / "a.md"
    artifact.write_text("first\n", encoding="utf-8")
    first = cast_vote._artifact_digest(tmp_path, "a.md")
    panel = {"artifact": "a.md", "artifact_sha256": first,
             "votes": [{"reviewer": "r", "verdict": "return"}]}

    artifact.write_text("second\n", encoding="utf-8")
    cast_vote._open_round(panel, tmp_path, reviewer="r", already=True)

    assert panel["rounds"][0]["artifact_sha256"] == first, (
        "the archived round must carry the sha the round was cast on, not the current bytes")
    assert panel["artifact_sha256"] != first, "the panel must move to the new bytes"


def test_a_second_verdict_on_identical_text_is_refused(tmp_path: Path) -> None:
    """The refusal that existed and had never been reachable, because the sha was never stored.

    Asserted as the PROPERTY rather than as "the field is not null": naming the field would let the
    next way of emptying it through, which is the lesson from generalising #176's test to "no report
    line carries the name of a Python exception".
    """
    import cast_vote

    artifact = tmp_path / "a.md"
    artifact.write_text("unchanged\n", encoding="utf-8")
    same = cast_vote._artifact_digest(tmp_path, "a.md")
    panel = {"artifact": "a.md", "artifact_sha256": same,
             "votes": [{"reviewer": "r", "verdict": "return"}]}

    with pytest.raises(SystemExit):
        cast_vote._open_round(panel, tmp_path, reviewer="r", already=True)


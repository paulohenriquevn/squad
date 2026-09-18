"""Where a phase's artifact lives is a question the kit can answer out loud.

`panel_brief.PHASE_SOURCES` already maps each phase to its artifact path and its
contract, and its own comment says why it exists:

    Read from here rather than guessed per call: a reviewer pointed at the wrong
    artifact returns an honest verdict about the wrong thing, which reads as
    coverage.

That is the failure it was written to prevent, and on 2026-09-18 it happened
anyway — to a reader that could not reach the table. The `judge-codex` plugin
hard-codes `knowledge-base/discoveries/blueprints/<slug>-blueprint.md` for all
four of its stages. The kit writes `.squad/records/discoveries/opportunities/
<slug>-opportunity.md`: `records-location.md` moved the root in 2026-08 and
`cycle-discover.md` renamed blueprint to opportunity. Both divergences are in
the same string, and every seat of every panel returned "artifact not found", so
a whole registry sat at ITEM_IN_FLIGHT — an incomplete panel being abstention,
never agreement.

The plugin did not duplicate the convention carelessly. There was nothing to
call: `main` demands `--slug` AND `--phase`, builds a whole brief, and REFUSES
when the artifact is absent — so a caller trying to FIND a file is answered with
a refusal for not having found it. Locating and judging are different questions
and only one of them may fail on absence.

`--locate` answers the first. It adds no convention: the table it reads is the
one the kit already keeps, so a later rename moves one string and every reader
follows. A phase the table does not hold exits 2 — this kit's word for could not
measure — rather than composing a plausible path nobody wrote.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_BRIEF = _REPO / "mechanisms" / "cycle" / "panel_brief.py"


def _locate(project: Path, phase: str, slug: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(_BRIEF), "--locate", "--phase", phase,
         "--slug", slug, "--project", str(project), "--json"],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout or proc.stderr


def test_it_answers_with_the_path_the_kit_actually_writes(tmp_path: Path) -> None:
    code, out = _locate(tmp_path, "discover", "b006-authorization")
    assert code == 0, out
    answer = json.loads(out)
    artifact = answer["artifacts"][0]
    assert ".squad/records/discoveries/opportunities" in artifact, artifact
    assert artifact.endswith("b006-authorization-opportunity.md"), artifact
    # Neither half of what the plugin guessed survives in the answer.
    assert "knowledge-base" not in artifact
    assert "blueprint" not in artifact


def test_an_absent_artifact_is_located_and_not_refused(tmp_path: Path) -> None:
    """Locating never fails on absence. That inversion is what hid the table.

    `--slug`/`--phase` without `--locate` exits 1 when the artifact is missing,
    which is right for convening a panel and backwards for finding a file.
    """
    code, out = _locate(tmp_path, "plan", "nothing-here")
    assert code == 0, out
    answer = json.loads(out)
    assert answer["artifacts"], "a location was asked for and none was given"
    assert answer["missing"] == answer["artifacts"], answer
    assert answer["present"] == []


def test_a_present_artifact_is_reported_present(tmp_path: Path) -> None:
    sys.path.insert(0, str(_REPO))
    from squad.paths import write_records_dir  # noqa: PLC0415

    plans = write_records_dir(tmp_path, "plans")
    plans.mkdir(parents=True)
    (plans / "real-slug-plan.md").write_text("# plan\n", encoding="utf-8")

    code, out = _locate(tmp_path, "plan", "real-slug")
    assert code == 0, out
    answer = json.loads(out)
    assert answer["missing"] == []
    assert len(answer["present"]) == 1
    assert answer["present"][0].endswith("real-slug-plan.md")


def test_a_phase_the_table_does_not_hold_is_unchecked_not_guessed(tmp_path: Path) -> None:
    """Exit 2, the kit's word for could not measure.

    The plugin runs four stages; this table holds three. Composing a path for
    `implementation` from the pattern of the others would be the kit inventing a
    convention on behalf of a caller, which is how the wrong path became load
    bearing the first time.
    """
    code, out = _locate(tmp_path, "implementation", "b006")
    assert code == 2, f"expected UNCHECKED, got {code}: {out}"
    assert "implementation" in out
    # It says what it CAN answer, so the caller is not left guessing twice.
    for known in ("discover", "plan", "design"):
        assert known in out, out


def test_it_names_the_contract_alongside_the_artifact(tmp_path: Path) -> None:
    """The other half of what a judge needs, and the other half the plugin got wrong.

    `cycle-judge-codex.md` already records that the plugin names a
    `discover-blueprint-golden-rule.md` which never existed here.
    """
    code, out = _locate(tmp_path, "discover", "b006")
    assert code == 0, out
    answer = json.loads(out)
    assert answer["contract"].endswith("rules/discover-opportunity-golden-rule.md"), answer

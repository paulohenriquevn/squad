"""The evidence dimension reports what it VERIFIED, and nothing more.

THE DEFECTS THIS CLOSES
-----------------------
G-E is the cycle's cardinal gate — `cycle-discover.md` calls fabricated evidence *"the
one unrecoverable defect in this cycle: everything downstream trusts it"* — and it
promised to block *"a URL never actually fetched, a trace id never observed"*.

Measured 2026-09-21, an opportunity whose entire Corner 1 was three HTTP observations
nobody executed:

    evidence_pointers_score: 100.0
    weighted_avg:            100.0
    hard_caps_triggered:     []

`check_evidence_pointers` is honest about why — an HTTP observation is not re-verifiable
on disk, so no code pointer could have failed — but `100.0` is not the honest way to say
that. It is the number a reader takes as "every pointer resolved". A dimension that
measured nothing must report itself unmeasured, which is what `active_dimensions` and
`weight_normalization_factor` were shaped for and never did: both were hardcoded.

And the `<!-- BLOCKED: … -->` marker removed a pointer from the count entirely, so the
author of the evidence could clear their own fabrications:

    1 resolving pointer + 4 non-existent ones, all marked BLOCKED  ->  100.0, no cap

A declared gap is not a fabrication and must not trigger the cap. It is also not a
verification, and it now costs what it is: a pointer that did not resolve.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCORER = REPO / "skills" / "discover-confidence" / "scripts" / "run_opportunity_score.py"
FIXTURE = REPO / "skills" / "discover-confidence" / "fixtures" / "good-opportunity.md"

sys.path.insert(0, str(REPO / "skills" / "discover-confidence" / "scripts"))


def _opportunity(tmp_path: Path, corner_one: str) -> Path:
    """The kit's own good fixture with Corner 1 replaced."""
    src = FIXTURE.read_text(encoding="utf-8")
    start = src.index("## Corner 1 — Evidence")
    end = src.index("## Corner 2 — Constraint Relation")
    (tmp_path / ".git").mkdir(exist_ok=True)
    path = tmp_path / "opportunity.md"
    path.write_text(src[:start] + corner_one + src[end:], encoding="utf-8")
    return path


def _score(path: Path) -> dict:
    proc = subprocess.run([sys.executable, str(SCORER), str(path)],
                          capture_output=True, text=True, cwd=path.parent, check=False)
    return json.loads(proc.stdout)


def _real_pointer(tmp_path: Path) -> str:
    target = tmp_path / "src" / "real" / "thing.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
    return "src/real/thing.ts:3"


RUNTIME_ONLY = """## Corner 1 — Evidence

Probed the declared live target:

- `GET https://app-dev.example/api/runs -> 500`
- `POST https://app-dev.example/api/runs -> 502`
- `GET https://app-dev.example/api/health -> 200`

"""


def test_runtime_only_evidence_is_not_scored_as_verified(tmp_path: Path) -> None:
    """Nothing was verified, so the dimension does not claim it was."""
    report = _score(_opportunity(tmp_path, RUNTIME_ONLY))

    assert "evidence_pointers" not in report["active_dimensions"], (
        "a dimension with nothing to verify must report itself unmeasured rather than "
        "scoring 100 over an empty denominator")
    assert report["evidence_pointers_score"] is None


def test_an_unmeasured_dimension_renormalises_the_weights(tmp_path: Path) -> None:
    """`weight_normalization_factor` was emitted as 1.0 always. A factor that never
    varies is a field computed for a reader and shown to nobody."""
    report = _score(_opportunity(tmp_path, RUNTIME_ONLY))

    assert report["weight_normalization_factor"] > 1.0
    assert report["weighted_avg"] <= 100.0


def test_the_report_says_the_observations_were_not_verifiable(tmp_path: Path) -> None:
    """Silence about it would read as absence of evidence, which is a different fact."""
    report = _score(_opportunity(tmp_path, RUNTIME_ONLY))

    blob = json.dumps(report).lower()
    assert "not re-verifiable" in blob or "not verifiable" in blob


def test_a_blocked_marker_does_not_erase_the_pointer_from_the_count(tmp_path: Path) -> None:
    """A declared gap is not a fabrication, and it is not a verification either."""
    pointer = _real_pointer(tmp_path)
    corner = (f"## Corner 1 — Evidence\n\nOne real pointer: {pointer}\n\n"
              "- src/does/not/exist.ts:42 <!-- BLOCKED: file moved -->\n"
              "- lib/also/missing.py:900 <!-- BLOCKED: not checked out -->\n"
              "- api/ghost/handler.go:7 <!-- BLOCKED: no access -->\n"
              "- core/phantom/thing.rs:1200 <!-- BLOCKED: build artefact -->\n\n")

    report = _score(_opportunity(tmp_path, corner))

    assert report["evidence_pointers_score"] < 100.0, (
        "one pointer in five resolved; reporting 100% lets the author of the evidence "
        "clear their own fabrications with a comment")
    assert "fabricated_evidence" not in report["hard_caps_triggered"], (
        "a declared gap is honest — it costs proportion, not the cardinal cap")


def test_an_unmarked_fabrication_still_trips_the_cardinal_cap(tmp_path: Path) -> None:
    corner = ("## Corner 1 — Evidence\n\n"
              f"One real pointer: {_real_pointer(tmp_path)}\n\n"
              "And one that does not exist: src/does/not/exist.ts:42\n\n")

    report = _score(_opportunity(tmp_path, corner))

    assert "fabricated_evidence" in report["hard_caps_triggered"]


def test_every_pointer_resolving_still_scores_full(tmp_path: Path) -> None:
    """The floor of the whole change: an honest opportunity is unaffected."""
    corner = f"## Corner 1 — Evidence\n\nIt resolves: {_real_pointer(tmp_path)}\n\n"

    report = _score(_opportunity(tmp_path, corner))

    assert report["evidence_pointers_score"] == 100.0
    assert "evidence_pointers" in report["active_dimensions"]

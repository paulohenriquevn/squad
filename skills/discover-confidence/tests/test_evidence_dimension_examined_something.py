"""The evidence dimension must not report that everything resolved when it read nothing.

`evidence_pointers` carries weight 0.30 and asks one question: do the citations resolve?
It computed `verified / total`, which is vacuous at zero, and returned a flat 100.0 —
so an opportunity citing NOTHING scored perfectly on the dimension that exists to
demand citation.

Measured 2026-09-16 across a 57-opportunity registry: zero of them tripped it, because
every real discovery cited something. This closes a latent hole. The hole matters
because DISCOVER now answers "is it possible / which technique / which pattern / where
in the system", and that answer can be written entirely as prose about an external
technique, with no pointer anywhere in it.

An inability to measure must never become a passing measurement.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parents[1] / "scripts"
           / "run_opportunity_score.py")


def _score(tmp_path: Path, body: str) -> dict:
    doc = tmp_path / "opportunity.md"
    doc.write_text("---\nitem: B-999\n---\n" + body, encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(_SCRIPT), str(doc), "--structural-only", "--no-warn"],
        capture_output=True, text=True, timeout=180,
     check=False).stdout
    return json.loads(out[out.index("{"):])


def test_an_opportunity_that_cites_nothing_does_not_score_perfectly(tmp_path: Path) -> None:
    result = _score(tmp_path, "# Nothing cited\n\nNo pointers. No observations.\n")
    assert result["evidence_pointers_score"] == 0.0, \
        "the dimension examined nothing and reported that everything resolved"
    assert "no_evidence_cited" in result["hard_caps_triggered"], \
        "citing nothing reached the same band as citing correctly"


def test_a_runtime_only_opportunity_keeps_its_score(tmp_path: Path) -> None:
    """An HTTP observation is not re-verifiable on disk, so no code pointer could have
    failed. That distinction is the checker's own design, not a loophole — the cap must
    not swallow it."""
    result = _score(
        tmp_path,
        "# Observed at runtime\n\nGET https://example.test/health -> 200\n",
    )
    assert result["evidence_pointers_score"] == 100.0
    assert "no_evidence_cited" not in result["hard_caps_triggered"]

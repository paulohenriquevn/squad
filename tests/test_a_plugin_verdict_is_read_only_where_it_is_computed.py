r"""A verdict a script computed may gate; one a model derived may not.

Negotiated with the session that owns the plugins, 2026-09-22, after it measured what
the seventeen actually do — and the measurement corrected what both of us assumed:

    5 of 17   compute the verdict in a SCRIPT      (`compute_verdict()`)
    12 of 17  derive it in the AGENT from a declared query over persisted findings

**None of the seventeen asserts a verdict freehand.** All derive from evidence. What
differs is who runs the derivation: a script, or a model following a written rule. Same
rule, different guarantees — and a gate that treated them alike would be doing the thing
this kit spent the session removing.

THE CONTRACT — `<output-dir>/verdict.json`, beside `final_report.md`

    {"schema": 1, "verdict": "<plugin's own token>",
     "source": "computed" | "derived-by-agent",
     "by": "scripts/devops_database.py:compute_verdict",
     "blocking_count": <int> | null, "generated_at": "<ISO-8601>"}

`source` is the whole field. Without it the file is markdown with quotes — easier to
read and carrying the same guarantee, which is the trap.

FOUR STATES, IN PRECEDENCE ORDER, and they are one enum rather than four flags:

    not_installed          the plugin is not here
    no_report              it ran nothing this run
    verdict_not_exposed    it reported, and exposes no decidable verdict
    covered                it reported, and the verdict is readable

Each question only makes sense if the previous one passed. A plugin that is not
installed has no missing report; one with no report has no verdict to expose.

WHAT `source: computed` DOES NOT PROVE — stated so the next reader does not overread it,
the way `check_wired_hooks` was overread this same day. It proves a script produced the
token. It does not prove the script is right. Correctness stays with the plugin, where
`verify_report_format.py` already says it stays.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "mechanisms" / "gates"))

from check_auditor_coverage import read_verdict  # noqa: E402


def _emit(tmp_path: Path, payload: dict | str) -> Path:
    out = tmp_path / "audit"
    out.mkdir(exist_ok=True)
    body = payload if isinstance(payload, str) else json.dumps(payload)
    (out / "verdict.json").write_text(body, encoding="utf-8")
    return out


_COMPUTED = {"schema": 1, "verdict": "INSUFFICIENT", "source": "computed",
             "by": "scripts/devops_database.py:compute_verdict",
             "blocking_count": 10, "generated_at": "2026-09-22T11:34:59Z"}


def test_a_computed_verdict_is_gateable(tmp_path: Path) -> None:
    """The real payload the pilot emits, byte for byte."""
    read = read_verdict(_emit(tmp_path, _COMPUTED))

    assert read["state"] == "computed"
    assert read["gateable"] is True
    assert read["verdict"] == "INSUFFICIENT"
    assert read["blocking_count"] == 10


def test_an_agent_derived_verdict_is_carried_and_not_gateable(tmp_path: Path) -> None:
    """The treatment `severity_signal` already has, for the same reason."""
    payload = dict(_COMPUTED, source="derived-by-agent", by="agents/report-writer.md")

    read = read_verdict(_emit(tmp_path, payload))

    assert read["state"] == "derived-by-agent"
    assert read["gateable"] is False
    assert read["verdict"] == "INSUFFICIENT", "carried, even though it cannot gate"


def test_computed_without_by_is_demoted_not_trusted(tmp_path: Path) -> None:
    """`computed` with no `by` is indistinguishable from `computed` typed by a model
    that read the contract — which is the confusion `source` exists to end."""
    payload = {k: v for k, v in _COMPUTED.items() if k != "by"}

    read = read_verdict(_emit(tmp_path, payload))

    assert read["gateable"] is False
    assert "by" in read["detail"]


def test_a_missing_file_is_not_a_clean_verdict(tmp_path: Path) -> None:
    """Sixteen plugins are in this state today. It is not 'no findings'."""
    out = tmp_path / "audit"
    out.mkdir()

    read = read_verdict(out)

    assert read["state"] == "verdict_not_exposed"
    assert read["gateable"] is False
    assert read.get("verdict") is None


def test_an_unknown_schema_is_not_read_field_by_field(tmp_path: Path) -> None:
    """A reader that meets `schema: 2` and takes the fields it recognises is guessing
    at the rest."""
    read = read_verdict(_emit(tmp_path, dict(_COMPUTED, schema=2)))

    assert read["state"] == "verdict_not_exposed"
    assert "schema" in read["detail"]


@pytest.mark.parametrize("bad", ["not json at all", "[]", '{"schema": 1}'])
def test_an_unreadable_file_is_unexposed_not_clean(tmp_path: Path, bad: str) -> None:
    assert read_verdict(_emit(tmp_path, bad))["state"] == "verdict_not_exposed"


def test_blocking_count_null_is_not_zero(tmp_path: Path) -> None:
    """A plugin with no notion of blocking must not read as one with none blocking."""
    read = read_verdict(_emit(tmp_path, dict(_COMPUTED, blocking_count=None)))

    assert read["blocking_count"] is None
    assert read["gateable"] is True, "no notion of blocking is not a reason to distrust"

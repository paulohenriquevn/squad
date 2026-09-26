"""An ImportError at module scope turned the code-quality gate off, silently.

`cq_invoke` is imported under `except ImportError: cq_invoke = None`, and both wrappers
begin `if cq_invoke is None: return`. So on any install where the sibling skill is not
resolvable — a partial copy, a renamed directory, a consumer that took `plan-confidence`
and not `code-quality` — the gate did nothing, said nothing, and the plan scored as if
it had been checked.

Nothing here makes the gate mandatory: a project may legitimately not ship the sibling.
What it must not do is disappear without a line saying so.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "plan-confidence" / "scripts"))
sys.path.insert(0, str(_ROOT))

import run_structural  # noqa: E402 — post-bootstrap import


def test_the_module_records_why_the_gate_is_off(monkeypatch) -> None:
    monkeypatch.setattr(run_structural, "cq_invoke", None)
    monkeypatch.setattr(run_structural, "CQ_UNAVAILABLE_BECAUSE",
                        "no module named 'cq_invoke'", raising=False)

    out: dict = {}
    run_structural._merge_code_quality_verdict(out, {"verdict": "PASS"})

    assert out.get("code_quality_unchecked"), (
        "the gate did nothing and left no trace that it had been skipped")
    assert "cq_invoke" in str(out["code_quality_unchecked"]), out


def test_an_available_gate_leaves_no_skip_note(monkeypatch) -> None:
    calls: list[tuple] = []

    class _Stub:
        @staticmethod
        def merge_verdict_into_plan_confidence(out, summary, **kw):
            calls.append((out, summary))

    monkeypatch.setattr(run_structural, "cq_invoke", _Stub)

    out: dict = {}
    run_structural._merge_code_quality_verdict(out, {"verdict": "PASS"})

    assert calls, "the gate was available and was not called"
    assert "code_quality_unchecked" not in out


def test_the_invoke_wrapper_reports_the_same_way(monkeypatch) -> None:
    monkeypatch.setattr(run_structural, "cq_invoke", None)

    result = run_structural._invoke_code_quality("a-slug", Path("."))

    assert result is None
    assert run_structural.CQ_UNAVAILABLE_BECAUSE is not None or result is None

"""Test: Fleet dispatch via Workflow.js (structured, not prose).

The workflow is the new transport layer for unit dispatch. It receives a JSON
payload describing the unit and its metadata, and produces a verification result.
"""
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_WORKFLOW_PATH = _REPO / "mechanisms" / "fleet" / "fleet_dispatch_workflow.js"


def test_fleet_dispatch_workflow_file_exists() -> None:
    """fleet_dispatch_workflow.js must exist."""
    assert _WORKFLOW_PATH.is_file(), f"Workflow not found at {_WORKFLOW_PATH}"


def test_workflow_declares_meta_and_phases() -> None:
    """Workflow must declare export const meta with name, description, phases."""
    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "export const meta = {" in content, "Workflow must export const meta"
    assert "name:" in content or '"name"' in content or "'name'" in content, "meta must have name"
    assert "description:" in content or '"description"' in content or "'description'" in content, "meta must have description"
    assert "phases:" in content or "'phases':" in content, "meta must define phases"
    # Check for the two phases
    assert "Repair" in content, "Workflow must have Repair phase"
    assert "Verify" in content, "Workflow must have Verify phase"


def test_workflow_uses_pipeline_and_agent() -> None:
    """Workflow must use pipeline() and agent() as primary orchestration."""
    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "pipeline(" in content, "Workflow should use pipeline()"
    assert "agent(" in content, "Workflow should spawn agents"
    assert "REPAIR" in content or "repair" in content, "Workflow should define REPAIR schema"
    assert "VERIFIED" in content or "verified" in content, "Workflow should define VERIFIED schema"


def test_workflow_respects_args_unit_branch_naming() -> None:
    r"""Workflow receives args.unit with a pre-computed branch name and must use it verbatim.

    The branch name comes from fleet_router.py and must match fleet_lander.py's
    regex: ^fix/kit\d+(?:-|$). This test documents the contract.
    """
    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # Workflow should reference args.unit and args.unit.branch
    assert "args" in content, "Workflow must read args"
    assert "args.unit" in content or "args?.unit" in content, "Workflow must reference args.unit"
    # The actual branch usage is verified in test_fleet_router_dispatch.py
    # Here we just check the workflow acknowledges the branch parameter


def test_workflow_defines_refusal_in_repair_phase() -> None:
    """REPAIR agent must support refusal (fixed=false, refused_because=...).

    A finding may be wrong or the fix may be larger than one branch should carry.
    Refusal is a real outcome.
    """
    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "refused_because" in content, "Workflow should allow refuse_because in REPAIR"
    assert "fixed" in content, "Workflow should track fixed status"


def test_workflow_verify_is_independent() -> None:
    """VERIFY agent must be independent (does not author the fix).

    Each verifier reads the branch AFTER the repairer commits.
    """
    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # The second stage uses the repair result as input and does not assume the
    # verifier is the same agent.
    assert "=> {" in content or ".then(" in content, "Workflow should pipe repair result to verify"

    lines = content.split("\n")
    repair_idx = next((i for i, ln in enumerate(lines) if "Repair" in ln or "REPAIR" in ln), -1)
    verify_idx = next((i for i, ln in enumerate(lines) if "Verify" in ln or "VERIFIED" in ln), -1)

    # The two phases are REQUIRED to be findable, not merely compared when they happen
    # to be. `if repair_idx >= 0 and verify_idx >= 0:` guarded the only assertion about
    # ordering — so a workflow that renamed either phase, or dropped one, satisfied
    # this test by making the comparison unreachable. A guard on the subject of the
    # assertion is a test that passes hardest when the subject is gone.
    assert repair_idx >= 0, "no Repair phase in the workflow"
    assert verify_idx >= 0, "no Verify phase in the workflow — nothing checks the fix"
    assert verify_idx > repair_idx, "Verify phase should come after Repair"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""The command an assignment prints is the invocation that resolves.

`command_for` printed `/loop-code-review …`. A plugin's command is registered under
its namespaced name, `loop-code-review:loop-code-review` — the form the Skill tool
takes and the one every installed `loop-*` plugin ships (`commands/<plugin>.md`,
checked for all seventeen on 2026-09-25). `/review` tells the agent to run each
command "exactly as printed", so a bare name is an instruction that does not run.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "tests"))
sys.path.insert(0, str(_REPO / "mechanisms" / "cycle"))

from select_auditors import Auditor, command_for  # noqa: E402
from test_select_auditors import _select  # noqa: E402


def test_the_printed_command_is_namespaced(tmp_path: Path) -> None:
    _, result = _select(tmp_path, [], diff_base="develop")

    assert result["required"][0]["command"].startswith(
        "/loop-code-review:loop-code-review . --output-dir ")


def test_a_row_that_already_names_its_namespace_is_not_doubled(tmp_path: Path) -> None:
    auditor = Auditor(domain="always", plugin="judge-codex:final-judge",
                      diff_mode="analysis-scoped")

    command = command_for(auditor, target=".", scope={}, project=tmp_path, slug="B-014")

    assert command.startswith("/judge-codex:final-judge . ")

"""Command text lifted from a document reaches `bash -c`, and two ways out were open.

`_refused_command` inspects the command NAMES on a line against an allowlist of readable
commands. It never looked at redirection, and it allowed `tee` outright:

    cat go.mod > /etc/hosts        # head is `cat`, which is allowed
    echo x | tee ~/.bashrc         # `tee` is on the allowlist
    go test ./... 2> /tmp/anything # a redirect the split never sees

The token split is `[|;&\\n(]|\\$\\(|\\)|`|\\{|\\}` — `>` is not in it, so a redirect is
glued to the operands of a command that already passed. Every one of those writes to a
path the document chose, on the machine running the check.

The criteria are authored by whoever wrote the plan. That is the trust boundary this
allowlist exists to hold.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "plan-alignment" / "scripts"))

from check_criteria_discriminate import (  # noqa: E402 — post-bootstrap import
    _refused_command,
)


@pytest.mark.parametrize("command", [
    "cat go.mod > /etc/hosts",
    "cat go.mod >> ~/.bashrc",
    "go test ./... 2> /tmp/captured",
    "grep -r thing . 1>/tmp/out",
    "echo done > result.txt",
])
def test_a_redirect_is_refused(command: str) -> None:
    refused = _refused_command(command)

    assert refused, f"{command!r} writes a file and was allowed"
    assert "redirect" in refused.lower() or "writes" in refused.lower(), refused


@pytest.mark.parametrize("command", [
    "echo x | tee ~/.bashrc",
    "go test ./... | tee -a /tmp/log",
])
def test_tee_is_refused(command: str) -> None:
    assert _refused_command(command), f"{command!r} writes a file and was allowed"


@pytest.mark.parametrize("command", [
    "grep -r 'thing' .",
    "go test ./...",
    "test -f go.mod",
    "(cd api && go test ./...)",
    "cat go.mod | grep module",
])
def test_a_reading_command_is_still_allowed(command: str) -> None:
    assert _refused_command(command) == "", _refused_command(command)


def test_a_comparison_operator_is_not_a_redirect() -> None:
    """`[ "$n" -gt 3 ]` and `awk '$1 > 2'` read; they do not write."""
    assert _refused_command("test $(wc -l < go.mod) -gt 3") == ""

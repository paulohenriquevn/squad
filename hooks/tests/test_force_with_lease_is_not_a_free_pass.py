"""The refusal named an authorization precondition that nothing enforced.

`FORCE_TOKEN_RE` matches `--force`, `-f` and the refspec `+` form, and the message says
"Use --force-with-lease only when explicitly authorized". Nothing in the hook asks about
authorization, and `--force-with-lease` matches none of the three alternatives — so it
was unconditionally allowed on every branch, including `main` and `develop`, where it
rewrites published history exactly as `--force` does whenever the lease happens to hold.

The user's rule is `NUNCA faça git push --force em main, develop ou workspace`, with
force-push permitted only on disposable branches. `--force-with-lease` is a safer force
push, not a different operation: the lease protects against clobbering a fetch you have
not seen, and protects nothing about a permanent branch.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / "validate-command.py"
_spec = importlib.util.spec_from_file_location("validate_command", _HOOK)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["validate_command"] = _mod
_spec.loader.exec_module(_mod)


def _verdict(command: str) -> str | None:
    return _mod.check_git(command)


def test_force_with_lease_on_a_permanent_branch_is_refused() -> None:
    for branch in ("main", "develop", "workspace"):
        blocked = _verdict(f"git push --force-with-lease origin {branch}")
        assert blocked and blocked.startswith("BLOCKED"), (
            f"--force-with-lease rewrites published history on {branch} exactly as "
            f"--force does: {blocked!r}")


def test_plain_force_is_still_refused() -> None:
    assert (_verdict("git push --force origin main") or "").startswith("BLOCKED")


def test_force_with_lease_on_a_disposable_branch_is_allowed() -> None:
    """The rule permits it there, and a guard that refuses everything gets bypassed."""
    assert _verdict("git push --force-with-lease origin an-experiment") is None


def test_an_ordinary_push_is_untouched() -> None:
    assert _verdict("git push origin main") is None

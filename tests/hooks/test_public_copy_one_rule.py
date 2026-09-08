"""One rule about public copy, asked by two hooks — not two rules that resemble.

`public-copy-lint` carries nine checks. `stop-validation` reimplemented two of
them (production-ready, the SLA number) with its own regexes, so the other seven
never reached the end of a session: 'battle-tested', 'enterprise-grade',
'drop-in replacement', 'zero downtime', 'lock-in free', '<X> killer' and the
unbacked 'faster than' all passed the Stop gate while the PostToolUse hook had
warned about them minutes earlier.

That shape is on record in this kit already — `_credential_globs` reads the deny
list from `settings.json` rather than keeping a second copy, because *"a rule
living in one file and missing from another is how that gap reopens"*.

The second defect is the scope each hook judges. `public-copy-lint` read
`new_string`, which for an `Edit` is the replaced fragment alone — so a claim was
flagged while the benchmark link that excuses it, two paragraphs above in the
same file, was invisible.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _lint():
    spec = importlib.util.spec_from_file_location(
        "public_copy_under_test", REPO / "hooks" / "public-copy-lint.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stop():
    spec = importlib.util.spec_from_file_location(
        "stop_validation_under_test", REPO / "hooks" / "stop-validation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_stop_gate_asks_the_same_question_the_edit_gate_asked() -> None:
    """Every check, not the two somebody happened to copy across."""
    assert _stop().public_copy_warnings is not None
    claims = ("This is battle-tested.", "Enterprise-grade throughput.",
              "A drop-in replacement for X.", "Zero downtime, always.",
              "Lock-in free by design.", "Faster than Y.",
              "It is production-ready.", "99.99% uptime.")
    for claim in claims:
        assert _stop().public_copy_warnings(claim), \
            f"the Stop gate does not check {claim!r}, which public-copy-lint does"


def test_the_wording_comes_from_the_shared_checks_not_from_a_second_list() -> None:
    """Asked of the messages, not of the source text.

    A grep for the patterns would be satisfied by a comment mentioning them and
    would fail on the comment explaining why they left. What proves there is one
    list is that every sentence the Stop gate emits is a sentence the list holds.
    """
    sys.path.insert(0, str(REPO))
    from squad.public_copy import CHECKS

    known = {check.message for check in CHECKS}
    emitted = _stop().public_copy_warnings(
        "Production-ready, battle-tested, a drop-in replacement, lock-in free, "
        "zero downtime, enterprise-grade, faster than X, 99.99% uptime.")

    assert emitted, "the Stop gate reported nothing about a paragraph of claims"
    assert set(emitted) <= known, \
        f"the Stop gate emits wording no shared check defines: {set(emitted) - known}"


def test_the_excuse_is_looked_for_in_the_whole_file_not_the_edited_fragment(
        tmp_path: Path) -> None:
    """A benchmark link two paragraphs up still excuses the claim below it."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Thing\n\nMeasured in docs/benchmarks/throughput.md.\n\n"
        "Squad is faster than the manual process.\n", encoding="utf-8")

    import os
    done = subprocess.run(  # noqa: PLW1510 — stdout is the assertion
        [sys.executable, str(REPO / "hooks" / "public-copy-lint.py")],
        input=json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Edit",
                          "tool_input": {"file_path": str(readme),
                                         "new_string": "Squad is faster than the "
                                                       "manual process."}}),
        capture_output=True, text=True, cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "HOME": str(tmp_path),
             "CLAUDE_PROJECT_DIR": str(tmp_path)})

    assert "faster than" not in done.stdout.lower(), \
        "the claim was flagged while its evidence sat in the same file"


def test_a_claim_with_no_evidence_anywhere_in_the_file_is_still_flagged(
        tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Thing\n\nSquad is faster than the manual process.\n",
                      encoding="utf-8")

    import os
    done = subprocess.run(  # noqa: PLW1510 — stdout is the assertion
        [sys.executable, str(REPO / "hooks" / "public-copy-lint.py")],
        input=json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Edit",
                          "tool_input": {"file_path": str(readme),
                                         "new_string": "Squad is faster than the "
                                                       "manual process."}}),
        capture_output=True, text=True, cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "HOME": str(tmp_path),
             "CLAUDE_PROJECT_DIR": str(tmp_path)})

    assert "faster than" in done.stdout.lower()

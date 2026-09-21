"""What each hook DOES, asked of the hook rather than of its implementation.

Five of the nine hooks shipped with no test at all: `english-only-check`,
`precompact-preserve`, `public-copy-lint`, `sessionstart-context` and
`userpromptsubmit-inject`. Migrating an untested hook is migrating blind — the
new one can differ from the old in any way and nothing says so.

So these were written FIRST, against the shell versions, by running them and
recording what came back. They resolve the hook by glob (`hooks/<name>.*`), so
the same test judges the shell script and whatever replaces it. That is the
point: the contract belongs to the hook, not to the language it is written in.

They pin exit codes, whether there is output at all, and the SHAPE of the JSON —
never the wording. `mechanisms/gates/check_prose_tests.py` refuses tests that
pin shipped prose, and it is right to: a test on the sentence fails when the
sentence improves and passes when the thing it describes breaks.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _hook(name: str) -> Path:
    found = sorted(p for p in (REPO / "hooks").glob(f"{name}.*") if p.suffix in (".sh", ".py"))
    assert len(found) == 1, f"expected exactly one implementation of {name}, found {found}"
    return found[0]


def _run(name: str, payload: dict) -> subprocess.CompletedProcess:
    hook = _hook(name)
    cmd = ["bash", str(hook)] if hook.suffix == ".sh" else [sys.executable, str(hook)]
    return subprocess.run(cmd, input=json.dumps(payload), capture_output=True,
                          text=True, cwd=REPO, check=False)


def _post(file_path: str | None = None, **extra) -> dict:
    tool_input = dict(extra)
    if file_path is not None:
        tool_input["file_path"] = file_path
    return {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": tool_input}


# ── english-only-check: an observer, so it must never block ───────────────────


@pytest.mark.parametrize("payload", [
    _post(),                                   # no path to look at
    _post("/nonexistent/definitely-not.md"),   # a path that is not a file
])
def test_english_only_says_nothing_when_there_is_nothing_to_read(payload) -> None:
    result = _run("english-only-check", payload)

    assert result.returncode == 0
    assert result.stdout.strip() == "", "silence is the report when there is no file"


def test_english_only_reports_non_english_without_blocking(tmp_path: Path) -> None:
    """It runs after the write. Blocking here would refuse an edit already made."""
    target = tmp_path / "prose.md"
    target.write_text(
        "# Titulo\n\nIsto nao esta em ingles, e voce nao deveria fazer isso.\n",  # english-only: the fixture MUST be Portuguese — it is what the hook detects
        encoding="utf-8")

    result = _run("english-only-check", _post(str(target)))

    assert result.returncode == 0, "an observer must not block"
    assert target.name in result.stdout, "the finding has to name the file"
    assert ":3" in result.stdout, "and the line, or it is not actionable"


def test_english_only_is_quiet_about_english(tmp_path: Path) -> None:
    target = tmp_path / "prose.md"
    target.write_text("# Title\n\nThis is English prose and nothing else.\n", encoding="utf-8")

    assert _run("english-only-check", _post(str(target))).stdout.strip() == ""


@pytest.mark.parametrize("name", ["diagram.png", "font.woff2", "poetry.lock"])
def test_english_only_skips_what_is_not_prose(tmp_path: Path, name: str) -> None:
    target = tmp_path / name
    # english-only: Portuguese on purpose — the point is that it is NOT scanned
    target.write_text("nao e prosa, e voce sabe disso\n", encoding="utf-8")

    assert _run("english-only-check", _post(str(target))).stdout.strip() == ""


def test_english_only_skips_third_party_material(tmp_path: Path) -> None:
    """The study zone is not ours to rewrite.

    `check_english_only` skips it by directory NAME, so it holds wherever the zone
    sits — the path below is the real one since the zone moved under the write root.
    """
    target = tmp_path / ".squad" / "study-material" / "vendor.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        "isto nao esta em ingles e voce nao deveria fazer isso\n",  # english-only: Portuguese on purpose — the point is that it is SKIPPED
        encoding="utf-8")

    assert _run("english-only-check", _post(str(target))).stdout.strip() == ""


# ── the two that inject context ───────────────────────────────────────────────


@pytest.mark.parametrize(("name", "payload", "event"), [
    ("sessionstart-context", {"hook_event_name": "SessionStart", "source": "startup"},
     "SessionStart"),
    ("userpromptsubmit-inject", {"hook_event_name": "UserPromptSubmit", "prompt": "hello"},
     "UserPromptSubmit"),
])
def test_the_injectors_emit_a_well_formed_envelope(name, payload, event) -> None:
    """The shape is the contract: a malformed envelope is silently dropped by the
    runtime, and the hook looks like it ran."""
    result = _run(name, payload)

    assert result.returncode == 0
    emitted = json.loads(result.stdout)
    specific = emitted["hookSpecificOutput"]
    assert specific["hookEventName"] == event
    assert specific["additionalContext"].strip(), "an empty injection is a no-op with a cost"


def test_session_start_answers_every_source_it_declares() -> None:
    """A source it does not handle would return nothing, and the session would
    start without the context the hook exists to provide."""
    for source in ("startup", "resume", "clear", "compact"):
        result = _run("sessionstart-context", {"hook_event_name": "SessionStart",
                                               "source": source})
        assert result.returncode == 0, source
        assert json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"], source


# ── the remaining two ─────────────────────────────────────────────────────────


def test_precompact_reports_and_never_blocks() -> None:
    """Blocking a compaction strands the session with a full context window."""
    result = _run("precompact-preserve", {"hook_event_name": "PreCompact",
                                          "trigger": "manual"})

    assert result.returncode == 0
    assert result.stdout.strip(), "it exists to record that compaction happened"


@pytest.mark.parametrize("payload", [
    _post(),
    _post("/nonexistent/x.md", new_string="anything"),
])
def test_public_copy_lint_is_silent_with_nothing_to_lint(payload) -> None:
    result = _run("public-copy-lint", payload)

    assert result.returncode == 0
    assert result.stdout.strip() == ""

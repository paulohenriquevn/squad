"""The pipeline's agents, written to disk before they run.

WHY MATERIALISE AT ALL
----------------------
The first pipeline run used ephemeral agents: the prompt lived in a workflow
script, went to the harness, and left no artefact. Six agents ran, three of them
reported defects in this kit — one found an id collision in `score_alignment.py`
with line numbers — and none of their prompts is recoverable. The transcript
records what they SAID; nothing records what they were ASKED.

`/review` solved this years of defects ago: `spawn_reviewers.py` instantiates
`templates/agent-*.md` into `.claude/agents/review-{slug}-{date}/`, and those
files are versioned. When a reviewer files a wrong finding you can read the
instruction that produced it. A pipeline meant to run unattended over 22 items
needs that more than `/review` does, not less.

WHAT THESE TESTS PIN
--------------------
Not the wording — `skills/_kit-rules/prompt-text-is-not-behaviour.md` forbids that, and the
lesson cost this kit a red suite on a refactor that improved the code. They pin
the CONTRACT: every stage gets a file, every placeholder is substituted, the
frontmatter parses, and the isolation posture matches what the spawn actually
does.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "spawn_stages.py"
STAGES = ("discover", "align", "plan")


def _run(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT),
         "--item", "B-014", "--repo", str(tmp_path / "repo"),
         "--date", "2026-08-30", "--output-dir", str(tmp_path / "agents"), *extra],
        capture_output=True, text=True,
    )


def test_every_stage_gets_a_file(tmp_path: Path) -> None:
    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stderr
    # A SET, not a sorted list: the directory has no order, and asserting the
    # alphabetical one would fail the day a stage is renamed while the contract —
    # one file per stage — still holds.
    written = {p.name for p in (tmp_path / "agents").glob("*.md")}
    assert written == {f"{s}.md" for s in STAGES}, sorted(written)


def test_no_placeholder_survives(tmp_path: Path) -> None:
    """A `{SLUG}` reaching an agent is an instruction with a hole in it.

    The agent does not error on it — it improvises around the brace, which is the
    failure mode that looks like a bad answer rather than a bad prompt.
    """
    _run(tmp_path)
    for path in (tmp_path / "agents").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        leftovers = [tok for tok in ("{ITEM}", "{REPO}", "{DATE}", "{MODEL}", "{STAGE}")
                     if tok in text]
        assert not leftovers, f"{path.name} still carries {leftovers}"


def test_the_frontmatter_parses_and_names_the_stage(tmp_path: Path) -> None:
    """A generated agent must be a valid agent, not a markdown file that looks
    like one — the harness reads the frontmatter, not the prose."""
    _run(tmp_path)
    for stage in STAGES:
        text = (tmp_path / "agents" / f"{stage}.md").read_text(encoding="utf-8")
        assert text.startswith("---\n")
        end = text.index("\n---\n", 4)
        fm = yaml.safe_load(text[4:end])
        assert fm["name"] == f"pipeline-b-014-{stage}"
        assert isinstance(fm["description"], str) and len(fm["description"]) > 40
        assert fm["tools"], "an agent with no tools cannot do its stage"


def test_the_read_only_stages_cannot_write(tmp_path: Path) -> None:
    """DISCOVER and ALIGN measure; they do not change the repository.

    The first run said this in prose inside the workflow script. Prose is what
    the agent reads, but the TOOL LIST is what the harness enforces — and only
    one of those two is a mechanism.
    """
    _run(tmp_path)
    for stage in ("discover", "align"):
        text = (tmp_path / "agents" / f"{stage}.md").read_text(encoding="utf-8")
        fm = yaml.safe_load(text[4:text.index("\n---\n", 4)])
        tools = fm["tools"] if isinstance(fm["tools"], list) else fm["tools"].split(", ")
        assert not ({"Write", "Edit", "NotebookEdit"} & set(tools)), (
            f"{stage} can write: prose asking it not to is not a mechanism")


def test_isolation_is_declared_where_the_spawn_uses_it(tmp_path: Path) -> None:
    """The `/review` templates still tell reviewers the tree is SHARED, which
    stopped being true when the spawn started passing `isolation="worktree"`.

    A prompt describing a world the code left behind is worse than no prompt: the
    agent takes precautions against a hazard that is gone and trusts nothing it
    should. These templates must not repeat that.
    """
    _run(tmp_path)
    for stage in STAGES:
        text = (tmp_path / "agents" / f"{stage}.md").read_text(encoding="utf-8").lower()
        assert "worktree" in text, f"{stage} does not tell the agent it is isolated"


def test_the_model_comes_from_the_routing_rule(tmp_path: Path) -> None:
    """Same mechanism `/review` has: a stage may run on a different model.

    `cycle-judge-codex.md` records why it matters — 5-7 reviewers of one model
    family share one set of blind spots.
    """
    rule = tmp_path / "routing.txt"
    rule.write_text("align | sonnet | a cheaper model reads its own draft\n", encoding="utf-8")
    _run(tmp_path, "--routing-rule", str(rule))
    align = (tmp_path / "agents" / "align.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(align[4:align.index("\n---\n", 4)])
    assert fm["model"] == "sonnet"

    discover = (tmp_path / "agents" / "discover.md").read_text(encoding="utf-8")
    fm2 = yaml.safe_load(discover[4:discover.index("\n---\n", 4)])
    assert fm2["model"] == "opus", "a stage with no routing entry must keep the default"


def test_rerunning_is_idempotent(tmp_path: Path) -> None:
    """A pipeline resumes. Regenerating must not append or duplicate."""
    _run(tmp_path)
    first = {p.name: p.read_text(encoding="utf-8") for p in (tmp_path / "agents").glob("*.md")}
    _run(tmp_path)
    second = {p.name: p.read_text(encoding="utf-8") for p in (tmp_path / "agents").glob("*.md")}
    assert first == second

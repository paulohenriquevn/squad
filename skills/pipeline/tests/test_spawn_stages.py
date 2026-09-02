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

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "spawn_stages.py"
def _stages_from_source() -> tuple[str, ...]:
    """The stage list the script actually has, not a copy of it kept here.

    JUDGE was added on 2026-09-02 and this assertion was the only thing that
    noticed the copy had gone stale — the good outcome, but a hand-kept list
    beside the one it mirrors only ever drifts, and the next stage drifts it
    again.
    """
    spec = importlib.util.spec_from_file_location("_spawn_stages_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.STAGES)


STAGES = _stages_from_source()


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


def test_no_template_promises_isolation_the_scheduler_does_not_give(tmp_path: Path) -> None:
    """The prose and the mechanism must describe the same world, in either
    direction.

    This test was written when the templates lagged BEHIND the code — `/review`'s
    still told reviewers the tree was shared after the spawn had started isolating
    it. On 2026-09-02 it caught the inverse: `isolation: 'worktree'` was removed
    from the scheduler (it isolated the kit's repository, not the consumer's, and
    every stage here is read-only), and three templates went on promising each
    agent a worktree of its own.

    Read from both sources rather than asserting a remembered answer, so whichever
    side moves next, this fails.
    """
    workflow = (Path(__file__).resolve().parents[3]
                / "mechanisms" / "fleet" / "pipeline_workflow.js").read_text(encoding="utf-8")
    code = "\n".join(line for line in workflow.splitlines()
                     if not line.lstrip().startswith("//"))
    scheduler_isolates = "isolation:" in code

    _run(tmp_path)
    for stage in STAGES:
        text = (tmp_path / "agents" / f"{stage}.md").read_text(encoding="utf-8").lower()
        promises = "your own worktree" in text or "you are alone in this tree" in text
        assert promises == scheduler_isolates, (
            f"{stage}.md and the scheduler disagree: the template "
            f"{'promises' if promises else 'does not promise'} isolation and the "
            f"scheduler {'gives' if scheduler_isolates else 'does not give'} it")


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



def _kit_at(root: Path) -> Path:
    """A directory `squad.layout` will recognise: the three trees plus `.claude/`."""
    for tree in ("skills", "rules", "hooks"):
        (root / ".claude" / tree).mkdir(parents=True)
    return root


def test_the_destination_is_the_projects_data_root_not_the_callers_cwd(tmp_path) -> None:
    """Three answers to "where do the stage agents live" were in circulation, and
    both written-down ones were relative to whoever ran the command. On a real
    consumer the documented form built a second `records/` tree at the repository
    root while the cycle's own sat in `.claude/records/` — putting the run's audit
    trail outside the tree that holds every other record of the cycle. The old
    code default was worse: `.claude/agents/`, where DECLARED agents live."""
    project = _kit_at(tmp_path / "consumer")

    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--item", "B-014", "--repo", str(project)],
        capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    written = project / ".claude" / "records" / "pipeline-agents" / "b-014"
    assert {p.name for p in written.glob("*.md")} == {f"{s}.md" for s in STAGES}
    assert not (project / ".claude" / "agents").exists(), \
        "generated per-item files do not go where the kit keeps its declared agents"
    assert not (project / "records").exists(), \
        "nor at the repository root, beside a data root that already exists"


def test_a_project_with_no_kit_is_refused_rather_than_guessed_at(tmp_path) -> None:
    """A guess writes the audit trail somewhere nobody looks, and being traceable
    back to the prompt is the entire reason these files are materialised."""
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--item", "B-014", "--repo", str(tmp_path)],
        capture_output=True, text=True, check=False)

    assert done.returncode != 0
    assert "no kit under" in done.stderr
    assert "--output-dir" in done.stderr, "and it says how to proceed deliberately"


def test_an_explicit_output_dir_is_still_honoured_verbatim(tmp_path) -> None:
    """The layout answers when nobody said; it does not overrule someone who did."""
    project = _kit_at(tmp_path / "consumer")
    chosen = tmp_path / "somewhere-else"

    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--item", "B-014", "--repo", str(project),
         "--output-dir", str(chosen)],
        capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    assert (chosen / "discover.md").is_file()
    assert not (project / ".claude" / "records").exists()


@pytest.mark.parametrize("bad", [
    "B-033 B-136 B-162",   # a whole queue, unsplit by the caller's shell
    "../../etc",           # a path, not an id
    "",                    # nothing at all
    "B-033/../B-999",      # an id with a way out of its directory
], ids=["a-whole-queue", "a-path", "empty", "traversal"])
def test_an_item_id_that_is_not_one_is_refused(tmp_path: Path, bad: str) -> None:
    """`--item` reaches the filesystem AND every generated prompt.

    Measured on 2026-09-02: a caller's shell did not split a queue variable, so
    `--item` received "B-033 B-136 B-162 B-171 B-172". The script created a
    directory with that name holding four stage agents, each of whose every
    mention of "the item" named five. Nothing objected. Those agents would have
    run and reported findings against an item that does not exist.
    """
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--item", bad,
         "--repo", str(tmp_path), "--output-dir", str(tmp_path / "agents")],
        capture_output=True, text=True, check=False)

    assert done.returncode != 0, f"accepted {bad!r}"
    assert not (tmp_path / "agents").exists(), "and wrote nothing before refusing"


def test_a_real_item_id_is_still_accepted(tmp_path: Path) -> None:
    """The guard must not eat the thing it guards."""
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--item", "B-014",
         "--repo", str(tmp_path), "--output-dir", str(tmp_path / "agents")],
        capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr

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

import sys as _s
from pathlib import Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _s.path.insert(0, str(_up))
        break
import importlib.util  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from squad.paths import write_records_dir  # noqa: E402

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


#: The lane's branch and worktree are named from this heading, so a repo without one
#: cannot be spawned into — deliberately, see `lane_name`.
_HEADING = "## B-014 — Refuse a chart name that resolves to two different charts   [ ]\n"
_LANE = "refuse-chart-name-resolves-two"


def _seed_registry(repo: Path, heading: str = _HEADING) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "BACKLOG.md").write_text(f"# Backlog\n\n{heading}\nstatus: approved\n",
                                     encoding="utf-8")
    return repo


def _run(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    _seed_registry(tmp_path / "repo")
    return subprocess.run(  # noqa: PLW1510 — returncode is read below
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

    # A template may INSTRUCT an agent to make a worktree — that is the repair for
    # the defect below, and IMPLEMENT does exactly that. What it may not do is
    # ASSERT it already has one, which is a claim about what the scheduler did.
    _ASSERTS_ISOLATION = ("you run in your own git worktree",
                          "in your own worktree over",
                          "you are alone in this tree")

    _run(tmp_path)
    for stage in STAGES:
        text = (tmp_path / "agents" / f"{stage}.md").read_text(encoding="utf-8").lower()
        promises = any(claim in text for claim in _ASSERTS_ISOLATION)
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
    _seed_registry(root)
    return root


def test_the_destination_is_the_projects_write_root_not_the_callers_cwd(tmp_path) -> None:
    """Three answers to "where do the stage agents live" were in circulation, and
    both written-down ones were relative to whoever ran the command. On a real
    consumer the documented form built a second `records/` tree at the repository
    root while the cycle's own sat in `.claude/records/`. The old code default was
    worse: `.claude/agents/`, where DECLARED agents live.

    All three are gone: there is one write root, so "where" has one answer.
    """
    project = _kit_at(tmp_path / "consumer")

    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--item", "B-014", "--repo", str(project)],
        capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    written = write_records_dir(project, "pipeline-agents") / "b-014"
    assert {p.name for p in written.glob("*.md")} == {f"{s}.md" for s in STAGES}
    assert not (project / ".claude" / "agents").exists(), \
        "generated per-item files do not go where the kit keeps its declared agents"
    assert not (project / "records").exists(), \
        "nor at the repository root, beside the write root that already exists"
    assert not (project / ".claude" / "records").exists(), \
        "nor inside the installed kit, which receives nothing this system writes"


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
    _seed_registry(tmp_path)
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--item", "B-014",
         "--repo", str(tmp_path), "--output-dir", str(tmp_path / "agents")],
        capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr


def test_only_the_implement_stage_can_write(tmp_path: Path) -> None:
    """The read-only stages share one tree safely and do. A writing stage is the
    reason worktrees exist, and giving `Write` to a stage that does not need it
    widens the blast radius of a prompt nobody has re-read lately.

    RELEASE joined the writers on 2026-09-14 and carries `Edit` only: it writes one
    changelog entry, on the lane's own branch, beside the change it describes. It does
    NOT carry `Write`, because creating a file is not something recording a release
    needs to do, and the narrower list is the one that stays true when nobody is
    watching.

    REVIEW deliberately stayed read-only. A reviewer who may edit cannot be trusted to
    report what they found, because the finding and the fix become one act nobody can
    separate afterwards.
    """
    _run(tmp_path)
    agents = tmp_path / "agents"

    writers = set()
    for stage in STAGES:
        front = (agents / f"{stage}.md").read_text(encoding="utf-8").split("---")[1]
        tools = {t.strip() for t in
                 next(line for line in front.splitlines()
                      if line.startswith("tools:")).split(":", 1)[1].split(",")}
        if tools & {"Write", "Edit", "NotebookEdit"}:
            writers.add(stage)

    assert writers == {"implement", "release"}, (
        f"unexpected writing stage(s): {writers - {'implement', 'release'}}")

    release_tools = {t.strip() for t in
                     next(line for line in
                          (agents / "release.md").read_text(encoding="utf-8")
                          .split("---")[1].splitlines()
                          if line.startswith("tools:")).split(":", 1)[1].split(",")}
    assert "Write" not in release_tools, "recording a release does not create files"

    review_tools = {t.strip() for t in
                    next(line for line in
                         (agents / "review.md").read_text(encoding="utf-8")
                         .split("---")[1].splitlines()
                         if line.startswith("tools:")).split(":", 1)[1].split(",")}
    assert not (review_tools & {"Write", "Edit"}), "a reviewer that edits is not a reviewer"


def test_the_writing_stage_makes_its_own_worktree_of_the_consumer(tmp_path: Path) -> None:
    """Not the harness's `isolation: 'worktree'`, which isolates the CWD's
    repository — the KIT on a consumer run, not the project under work. That
    defect was removed on 2026-09-02 rather than repaired; this is the repair."""
    _run(tmp_path)
    body = (tmp_path / "agents" / "implement.md").read_text(encoding="utf-8")

    assert "git -C" in body and "worktree add" in body, \
        "the stage must create a worktree of the repo it was pointed at"
    assert "pipeline/" in body, "on a branch named after the item"


def test_the_writing_stage_states_its_absolute_refusals(tmp_path: Path) -> None:
    """An unattended agent with Edit and Write needs the list where it works, not
    in a rule it may not read."""
    _run(tmp_path)
    body = (tmp_path / "agents" / "implement.md").read_text(encoding="utf-8")

    for refusal in ("git push", "--no-verify", "--force", "BACKLOG.md",
                    "threshold", "baseline"):
        assert refusal in body, f"the stage does not refuse {refusal}"


def test_the_writing_stage_runs_the_red_test_before_writing_code(tmp_path: Path) -> None:
    _run(tmp_path)
    body = (tmp_path / "agents" / "implement.md").read_text(encoding="utf-8")

    assert "before writing any production code" in body
    assert "record that it failed" in body, "a RED nobody watched fail is not a RED"


def test_the_chain_runs_to_release(tmp_path: Path) -> None:
    """Until 2026-09-14 it stopped at IMPLEMENT and the stages after it did not exist.

    That is why an unattended run kept producing nothing: whatever was fixed upstream,
    the chain ran five stages and stopped, and a consumer asking for autonomy got a
    scheduler that was never able to finish. The gates were not the obstacle; the chain
    ended before the work landed.
    """
    _run(tmp_path)
    agents = tmp_path / "agents"
    for stage in ("discover", "align", "judge", "plan", "implement", "review", "release"):
        assert (agents / f"{stage}.md").is_file(), f"{stage} has no materialised prompt"


def test_review_reruns_the_criteria_against_the_tree_at_review_time(tmp_path: Path) -> None:
    """A verification does not survive the tree it measured.

    A criterion that discriminated when the brief was written can be inert by review
    time because something else changed — measured when this kit wrote one config line
    into a consumer and turned one of its criteria inert in the same minute.
    """
    _run(tmp_path)
    body = (tmp_path / "agents" / "review.md").read_text(encoding="utf-8")
    assert "check_criteria_discriminate.py" in body
    assert "at review time" in body


def test_release_does_not_cut_a_version_or_merge(tmp_path: Path) -> None:
    """Both have blast radius beyond one item, and several items ship in one release."""
    _run(tmp_path)
    body = (tmp_path / "agents" / "release.md").read_text(encoding="utf-8")
    assert "do not cut a version" in body.lower()
    assert "backlog_status.py" in body, "the only writer of a status line"


# ── the lane's name and the lane's location ────────────────────────────────


def _module():
    """Loaded by path, like `_stages_from_source` — the script is not on sys.path."""
    spec = importlib.util.spec_from_file_location("_spawn_stages_lane", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _implement_brief(tmp_path: Path) -> str:
    assert _run(tmp_path).returncode == 0
    return (tmp_path / "agents" / "implement.md").read_text(encoding="utf-8")


def test_no_branch_or_worktree_is_named_by_a_ticket_number(tmp_path: Path) -> None:
    """`~/.claude/CLAUDE.md § 5.1` bans a ticket number in a branch or directory name:
    the number dies and the name stays, pointing at a tracker that may not resolve it.

    The pipeline was generating `pipeline/b-018` and `/tmp/squad-worktrees/b-018-…`, so a
    consumer that had just removed 5 branches and 5 worktree directories under that rule
    had them regenerated by the next run. A kit that reintroduces what a consumer cleans
    keeps every consumer doing the cleaning.

    The id still travels — in the commit message, where § 5.1 says it belongs.
    """
    brief = _implement_brief(tmp_path)
    for line in brief.splitlines():
        if "worktree add" in line or "pipeline/" in line:
            assert "b-014" not in line.lower(), line
    assert f"pipeline/{_LANE}" in brief


def test_the_lane_is_named_for_what_the_work_is(tmp_path: Path) -> None:
    lane_name = _module().lane_name
    assert lane_name("A bare chart name resolves to two different charts", "B-002") == \
        "bare-chart-name-resolves-two"
    assert lane_name("Wire an english-only gate that FAILS on the current tree", "B-003") == \
        "wire-english-only-gate-fails"


def test_a_title_quoting_an_id_does_not_smuggle_it_into_the_branch(tmp_path: Path) -> None:
    lane_name = _module().lane_name
    assert "b-047" not in lane_name("B-047 supersedes this: raise chi past the advisories",
                                    "B-081").lower()


def test_an_item_with_no_title_is_refused_rather_than_named_by_its_id(tmp_path: Path) -> None:
    """There is no fallback to the id, on purpose. A lane that cannot be named by its
    subject is a registry entry with no subject, and quietly calling it `b-014` is how
    the rule got broken in the first place."""
    _seed_registry(tmp_path / "repo", heading="## B-014 —    [ ]\n")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--item", "B-014", "--repo", str(tmp_path / "repo"),
         "--output-dir", str(tmp_path / "agents")],
        capture_output=True, text=True, check=False)
    assert done.returncode != 0
    assert "no title" in done.stderr.lower()
    assert "5.1" in done.stderr


def test_a_lane_holding_unmerged_commits_does_not_live_in_tmp(tmp_path: Path) -> None:
    """Measured on a consumer 2026-09-15: `/tmp` was wiped mid-session and took two
    in-progress measurement sweeps with it, while two lanes holding six commits between
    them sat in `/tmp/squad-worktrees/`. The objects survive in the shared `.git` — the
    checkout and the ref registration do not, and recovering by reflog is not what the
    next agent will think to do.
    """
    assert _run(tmp_path).returncode == 0
    checked = 0
    for stage in STAGES:
        lines = (tmp_path / "agents" / f"{stage}.md").read_text(
            encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "worktree add" not in line:
                continue
            # The command is written across a backslash continuation, so the path sits
            # on the line after the verb. Join them before looking for it.
            joined, cursor = line, index
            while joined.rstrip().endswith("\\") and cursor + 1 < len(lines):
                cursor += 1
                joined = joined.rstrip().rstrip("\\") + " " + lines[cursor].strip()
            assert "/tmp/squad" not in joined, f"{stage}: {joined.strip()}"
            assert "$HOME/.squad-worktrees" in joined, f"{stage}: {joined.strip()}"
            checked += 1
    assert checked >= 2, f"only {checked} worktree commands found across the chain"


# ── the records a worktree does not carry ──────────────────────────────────


def _briefs(tmp_path: Path) -> dict[str, str]:
    assert _run(tmp_path).returncode == 0
    return {s: (tmp_path / "agents" / f"{s}.md").read_text(encoding="utf-8")
            for s in STAGES}


def test_the_writing_stage_writes_the_checkpoint_every_gate_reads(tmp_path: Path) -> None:
    """Measured on a consumer 2026-09-15: five items produced implementation records and
    ZERO `.progress-{slug}.json` checkpoints, so four gates — progress schema, checkpoint
    consistency, wiring triad, phase review — answered SKIP with "implement may not have
    run" about work that was on disk with commits behind it.

    `/implement` had indeed not run. This stage had, and it is a different mechanism
    wearing the same name: its brief never mentioned the checkpoint at all.
    """
    brief = _briefs(tmp_path)["implement"]
    assert ".progress-" in brief, "the brief never names the checkpoint six gates read"
    assert "progress-schema.json" in brief, "nor the schema that makes it consumable"


def test_the_completion_promise_belongs_to_the_gate(tmp_path: Path) -> None:
    """`rules/cycle-implement.md`: the promise is emitted "EXCLUSIVELY when
    run_validation.py exits 0. There is no graceful-exit path that emits the promise on a
    partial pass." The pipeline's writing stage emitted its own completion without ever
    invoking that gate."""
    brief = _briefs(tmp_path)["implement"]
    assert "run_validation.py" in brief
    assert "EXCLUSIVELY" in brief or "exits 0" in brief


def test_no_stage_reaches_the_kit_or_a_record_by_a_worktree_relative_path(
        tmp_path: Path) -> None:
    """`.claude/` and `.squad/*` are gitignored in a consumer repository, so a worktree —
    which carries tracked files — contains neither. Measured on a consumer: `.claude` has
    0 tracked files, `.squad` tracks only `wiki/`, and a lane worktree carried 0 of the
    repository's 19 plans.

    A brief that resolves the kit with `[ -d .claude/skills ] && echo .claude || echo .`
    therefore resolves to the worktree root, where no kit exists, and the command fails
    with a missing file instead of a verdict. Every such path must be anchored at the
    repository.
    """
    repo = str(tmp_path / "repo")
    for stage, brief in _briefs(tmp_path).items():
        in_fence = False
        for line in brief.splitlines():
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            # Prose QUOTING the bad pattern to explain it is not the bad pattern; only
            # what an agent would actually run is checked.
            if not in_fence or "-d .claude/skills" not in line:
                continue
            # The ANCHOR must be the repository, not merely the repository appearing
            # somewhere on the line. The first version of this guard asserted `repo in
            # line` and passed on `$([ -d .claude/skills ] && ...) ... {REPO}/BACKLOG.md`
            # — where {REPO} is an argument and the kit probe is still relative. The
            # RELEASE stage carried exactly that shape and the guard called it clean.
            assert f"-d {repo}/.claude/skills" in line, (
                f"{stage}: resolves the kit relative to the caller, which in a worktree "
                f"is a tree with no kit in it — {line.strip()}")


def test_the_writing_stage_says_records_live_in_the_repository(tmp_path: Path) -> None:
    """Code goes in the worktree; records go in the repository. Writing a checkpoint into
    the worktree puts it in a directory the validation gate does not read, and the gate
    then reports "implement may not have run" about work that exists."""
    brief = _briefs(tmp_path)["implement"]
    assert "gitignored" in brief, "the brief does not say WHY records are not beside the code"
    assert f"{tmp_path / 'repo'}/.squad/records" in brief


def test_the_chain_records_the_hop_that_makes_shipping_legal(tmp_path: Path) -> None:
    """`approved -> shipped` is not a legal transition; `approved -> planned -> shipped`
    is. RELEASE moved an item to `shipped` and nothing moved it to `planned`, so RELEASE
    was refused after the work was done, with nothing about the work at fault.

    Measured on a consumer 2026-09-15: 87 items at `approved`, 9 with implementations
    behind them, zero at `shipped`.
    """
    briefs = _briefs(tmp_path)
    assert "--to planned" in briefs["implement"], \
        "nothing in the chain records that work started"
    assert "--to shipped" in briefs["release"]


def test_every_status_a_stage_writes_is_a_legal_hop_from_the_one_before(
        tmp_path: Path) -> None:
    """The durable half: a stage may only write a status the registry will accept from
    the status the previous stage left. Checked against `backlog_status.ALLOWED` rather
    than against a list kept here, which would drift the moment the contract changes."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"))
    import backlog_status  # noqa: PLC0415

    briefs = _briefs(tmp_path)
    per_stage = {stage: re.findall(r"--to\s+(\w+)", briefs[stage]) for stage in STAGES}
    assert any(per_stage.values()), "no stage writes a status at all"

    # A stage's FIRST write advances the chain; any further write is a recovery hop
    # from the status that stage just set — `planned -> approved` when a lane halts.
    # Modelling this as one linear sequence was wrong the moment a way back existed,
    # and the test said so by failing, which is the outcome worth having.
    current = "approved"
    for stage in STAGES:
        writes = per_stage[stage]
        if not writes:
            continue
        forward, recoveries = writes[0], writes[1:]
        assert forward in backlog_status.ALLOWED[current], (
            f"{stage} advances {current} -> {forward}, which the registry refuses; "
            f"from {current} it accepts {sorted(backlog_status.ALLOWED[current])}")
        for back in recoveries:
            assert back in backlog_status.ALLOWED[forward], (
                f"{stage} recovers {forward} -> {back}, which the registry refuses; "
                f"from {forward} it accepts {sorted(backlog_status.ALLOWED[forward])}")
        current = forward


def test_a_status_a_stage_writes_mid_flight_has_a_way_back(tmp_path: Path) -> None:
    """`planned` means work is in flight, and an item left there by a lane that stopped
    is invisible to SELECT entirely — measured on a consumer 2026-09-15, it appears in
    none of `queue`, `awaiting_plan` or `awaiting_human`. It is neither scheduled nor
    shipped nor listed anywhere a person would look.

    This was introduced the same afternoon the `planned` write was, by me, and found by
    the consumer session reasoning about the shape rather than by anything failing. The
    brief that writes a mid-flight status must also carry the way back.

    `planned -> approved` is the only legal return: `triaged` is not reachable from
    `planned`, so the obvious guess is refused by the registry.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"))
    import backlog_status  # noqa: PLC0415

    brief = _briefs(tmp_path)["implement"]
    assert "--to approved" in brief, \
        "the stage writes `planned` and never says how to leave it"
    assert "invisible to SELECT" in brief, \
        "the brief does not say what an abandoned `planned` costs"
    assert "approved" in backlog_status.ALLOWED["planned"]
    assert "triaged" not in backlog_status.ALLOWED["planned"], \
        "if this changes, the brief's claim about the only legal return is stale"


def test_an_already_planned_refusal_is_not_read_as_permission_to_proceed(
        tmp_path: Path) -> None:
    """`--to planned` refusing has two opposite causes: your own lane resuming, or a
    second lane already working the item. The brief said the refusal was benign and told
    the agent to carry on.

    Measured on a consumer 2026-09-15: two lanes implemented B-069 thirty minutes apart —
    the orchestrator dispatched an agent directly and then ran the pipeline over the same
    item — and the only signal available to the second was that refusal. Their production
    code came out byte-identical, which is a remarkable corroboration and an entirely
    wasted lane.

    The item's own checkpoint distinguishes the two, and it is addressed by item id,
    which a lane branch is not any more: lanes are named by subject under § 5.1.
    """
    brief = _briefs(tmp_path)["implement"]
    assert ".progress-" in brief
    assert "another lane has it" in brief.lower(), \
        "the brief does not name the case where a second lane already holds the item"
    assert "stop" in brief.lower().split("already planned")[1][:600], \
        "the brief still reads the refusal as permission to proceed"


def test_the_judge_reads_the_brief_at_its_path_in_the_repository(tmp_path: Path) -> None:
    """Measured on a consumer 2026-09-15: a judge scored a scratchpad COPY of a 34 KB
    brief and wrote its refusal into it, so two briefs existed for one item and the
    refusal landed in a file nobody downstream can open.

    The judge named the problem itself — "a signature on a file that exists only in a
    session is the class of evidence the judge contract names as unacceptable" — which is
    why the path is stated in the brief rather than left to inference. A signature is only
    worth what the file carrying it outlives.

    Third stage in the same family: IMPLEMENT and REVIEW both resolved the kit relative to
    the caller, and a stage running in a worktree has neither `.claude/` nor `.squad/`.
    """
    brief = _briefs(tmp_path)["judge"]
    repo = str(tmp_path / "repo")
    assert f"{repo}/.squad/records/alignment/" in brief
    assert "scratchpad" in brief, "the brief does not name the failure it is preventing"


def test_the_lane_is_discovered_not_assumed(tmp_path: Path) -> None:
    """Work reaches an item by more than one path. This pipeline creates
    `pipeline/<subject>`; a direct dispatch creates `impl/<subject>`; and a template that
    hardcodes one prefix looks for a branch that does not exist.

    Measured on a consumer 2026-09-15: the item furthest along had its keeper lane at
    `impl/audit-read-failure-is-observable` while REVIEW and RELEASE both named
    `pipeline/{LANE}`. RELEASE would have written its changelog entry to a branch that was
    not there.
    """
    for stage in ("review", "release"):
        brief = _briefs(tmp_path)[stage]
        assert "pipeline/" not in brief.split("## What you return")[0] or \
            "branch --contains" in brief, f"{stage} assumes a branch prefix"
        assert "branch --contains" in brief, f"{stage} does not discover the lane"


def test_the_stage_refuses_to_pick_when_the_two_sources_disagree(tmp_path: Path) -> None:
    """The checkpoint and the implementation record are written by different steps, and on
    that consumer they disagreed — two lanes implemented one item thirty minutes apart, and
    the adjudication of which one survives was made by a person.

    A stage that picks is deciding an adjudication that is not its to make. Picking the
    checkpoint's answer would have released the discarded lane.
    """
    for stage in ("review", "release"):
        brief = _briefs(tmp_path)[stage]
        assert "STOP and report both" in brief, f"{stage} does not refuse the collision"


def test_the_discovery_command_does_not_depend_on_the_shell(tmp_path: Path) -> None:
    """`for sha in $SHAS` does not word-split in zsh: the whole list arrives as one
    malformed object name. Found by running the generated command in the shell this
    machine actually uses, rather than the one the snippet was written in."""
    for stage in ("review", "release"):
        brief = _briefs(tmp_path)[stage]
        assert "while read -r sha" in brief, f"{stage} relies on word-splitting"
        # The COMMENT names the broken form to explain why it went. A line that starts
        # with `#` is documentation, not a command — third time today a guard of mine
        # failed on its own explanation, which is the same shape as reading a fenced
        # heading as document structure.
        commands = [line for line in brief.splitlines()
                    if not line.lstrip().startswith("#")]
        assert not any("for sha in $SHAS" in line for line in commands), \
            f"{stage} still runs the word-splitting form"


def test_the_lane_is_read_from_the_record_before_it_is_inferred(tmp_path: Path) -> None:
    """The implementation record DECLARES the lane in its frontmatter — 5 of 6 records on
    a consumer carry `branch:`. The first version of this block skipped it and inferred
    the lane from `git branch --contains` over SHAs in the body.

    It got the wrong answer, and the way it got it is the lesson: the body correctly
    documents BOTH dispatch attempts, 15 SHAs split 5 keeper / 5 discarded / 5 shared, and
    the one the rule happened to reach was discarded-only. A rule that picks one SHA out
    of fifteen picked against the `## Commits` table, which is the section that answers
    the question.

    Reconstructing a fact a document states is how you get an answer that disagrees with
    the document while looking derived.
    """
    for stage in ("review", "release"):
        brief = _briefs(tmp_path)[stage]
        head = brief.split("branch --contains")[0]
        assert "^branch:" in head, \
            f"{stage} infers the lane before reading the field that declares it"
        assert "Frontmatter first" in brief


def test_the_writing_stage_produces_the_audit_the_next_phase_reads(tmp_path: Path) -> None:
    """Three files, each correct alone, meeting where nothing ran:

        cycle-phases.txt     code-quality | nested-in: implement
        cq_invoke.py:62      passes --no-audit-write
        check_upstream_gate  requires {slug}-code-quality-*.md, BLOCKER when absent

    The nested run executes and returns a verdict; it is told not to write the one file
    the next phase reads. Measured on a consumer 2026-09-15: 8 audit files in the whole
    registry, every one a `deps-audit`, ZERO `code-quality`. Five of six implemented items
    were refused at REVIEW for an artifact the nested run was instructed not to produce,
    nothing had ever reached `shipped`, and the items were being blamed for it.

    Suppressing the write inside validate is right — validate runs many times per item.
    What was missing is the standalone run, and without it the chain needs a person per
    item, which is not a chain.
    """
    brief = _briefs(tmp_path)["implement"]
    assert "run_code_quality.py" in brief, \
        "the writing stage never produces the audit /review requires"
    assert "--no-audit-write" in brief, \
        "the brief does not say why the nested run left no file"


def test_the_declaration_does_not_read_as_already_done() -> None:
    """`nested-in: implement` alone reads as "already handled" — which is how the marker
    added this same afternoon made the gap harder to see, not easier. The declaration has
    to say which HALF is nested."""
    phases = (Path(__file__).resolve().parents[3] / "rules" / "cycle-phases.txt"
              ).read_text(encoding="utf-8")
    line = next(l for l in phases.splitlines() if l.startswith("code-quality"))
    assert "VERDICT" in line and "AUDIT FILE" in line, \
        f"the declaration does not separate the nested verdict from the written file: {line}"


def test_the_plan_stage_writes_a_plan_and_scores_it(tmp_path: Path) -> None:
    """`rules/cycle-plan.md` puts `/plan-confidence` between PLAN and IMPLEMENT: INVALID
    returns to rewrite, a low band goes to `/plan-improve`, and only
    SHIPPABLE_WITH_CAVEATS or better is ready.

    The pipeline's PLAN stage was 24 lines of prose carrying no command at all — while
    the stage after it carries 276 — so it wrote no plan and ran no gate. Measured on a
    consumer 2026-09-16: 27 substantive plans on disk, 773 to 2025 lines and 8 to 15
    tasks each, and ZERO plan-confidence artifacts. The first one scored afterwards came
    back INVALID at 51.4 with two hard caps.

    A gate nobody runs is indistinguishable from a gate that passed. Same shape as the
    code-quality audit the nested run was told not to write, one phase earlier.
    """
    brief = _briefs(tmp_path)["plan"]
    assert "run_structural.py" in brief, "the PLAN stage runs no confidence gate"
    assert "records/plans/" in brief, "the PLAN stage names no path for the plan"
    assert "INVALID" in brief, "the brief does not say what a failing score means"


def test_discover_answers_the_four_questions(tmp_path: Path) -> None:
    """DISCOVER's contract, set by the owner 2026-09-16: is it possible, what is the
    technique, what is the pattern, where in the system — implemented, modified or
    removed.

    Measured before the change: 57 opportunity documents, 503 lines median, 31,281 lines
    in total, for 6 items that reached implementation. The four questions are what the
    later phases actually consume; the rest was written and not read.
    """
    brief = _briefs(tmp_path)["discover"]
    for question in ("Is it possible", "What is the technique", "What is the pattern",
                     "Where in the system"):
        assert question in brief, f"DISCOVER does not answer: {question}"
    assert "`NEW`, `MODIFY` or `DELETE`" in brief, \
        "a path with no verb leaves the next phase guessing"


def test_plan_is_executable_by_someone_who_does_not_know_the_project(tmp_path: Path) -> None:
    """PLAN's contract, set by the owner 2026-09-16: a developer who has never seen this
    project must be able to follow it and finish.

    That justifies length the earlier measurement made look wasteful — 1,276 lines median
    — and it also sets the limit. The plan carries what the reader lacks, which is
    knowledge of THIS codebase, and not what a competent developer brings.
    """
    brief = _briefs(tmp_path)["plan"]
    assert "never seen this project" in brief
    # The prose is wrapped, so the sentence spans two lines. Asserting on a phrase that
    # crosses a wrap point tests the line width, not the content — fourth time in two days
    # a check of mine read the rendering instead of the text.
    flat = " ".join(brief.split())
    assert "does NOT carry what a competent developer brings" in flat, \
        "the contract has no upper bound, and length is not rigour"

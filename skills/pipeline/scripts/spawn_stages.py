#!/usr/bin/env python3
"""Write the pipeline's stage agents to disk before any of them runs.

WHY, AND WHAT THE EPHEMERAL VERSION COST
----------------------------------------
The first pipeline run used ephemeral agents: each prompt lived inside a workflow
script, went to the harness, and left nothing behind. Six agents ran over a real
backlog. Three of them reported defects in this kit — one located an id collision
in `score_alignment.py` with line numbers and the real-versus-reported figures —
and **not one of their prompts is recoverable**. The transcript records what they
said; nothing records what they were asked.

`/review` solved this long ago: `spawn_reviewers.py` instantiates
`templates/agent-*.md` into a dated directory that lives in git, so when a
reviewer files a wrong finding you can read the instruction that produced it. A
pipeline meant to run unattended over 22 items needs that more than `/review`
does, not less.

WHAT IS ENFORCED HERE AND WHAT IS ONLY SAID
-------------------------------------------
The read-only stages carry no writing tool. That is the mechanism. The paragraph
in each template explaining why is the explanation, and the difference matters:
the first run asked the agents in prose not to write, which the harness does not
read.

WHERE THE FILES GO, AND WHY THE CALLER SHOULD NOT SAY
------------------------------------------------------
`--output-dir` is optional and should stay unused. Three answers to "where do the
stage agents live" were in circulation and all three were wrong in a consumer:
SKILL.md's `records/pipeline-agents/b-014` and this script's old default of
`.claude/agents/pipeline-b-014` were both relative to the CWD — the caller's, not
the project's — and the second wrote generated per-item files into the directory
where the kit keeps its DECLARED agents. Measured on a real consumer: the
documented form created a second `records/` tree at the repository root while the
cycle's real one sat in `.claude/records/`, so the run's audit trail landed
outside the tree that holds every other record of the cycle.

`squad.layout` answers this and has since 2026-08-26. `resolve(repo).eco` is the
cycle's data root for THAT project, whichever of the three install shapes it uses,
and it is what this script now asks. A `--output-dir` given explicitly is still
honoured verbatim, relative to the caller's CWD like any other CLI path.

Usage:
    python3 spawn_stages.py --item B-014 --repo <path> [--output-dir DIR]
                            [--date YYYY-MM-DD] [--routing-rule FILE]

Exit codes:
    0 — every stage written
    1 — a template is missing, or a placeholder survived substitution
    2 — no `--output-dir` and no kit under `--repo`, so there is no data root
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

from squad.layout import resolve

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import data_root, write_records_dir  # noqa: E402

#: The stages this script materialises. IMPLEMENT and beyond are not here yet —
#: they write to the repository, and a writing stage needs its own review of what
#: the tool list should be. Naming the gap rather than shipping a template whose
#: permissions nobody thought about.
#: JUDGE sits between ALIGN and PLAN and is not optional. The alignment rule
#: requires two independent things — a machine score AND a sign-off from someone
#: who is not the brief's author — and ALIGN can only ever produce the first,
#: because its own template forbids it from emitting `ALIGNED`. With no stage for
#: the second, the scheduler read `AWAITING_REVIEW` as permission: measured on a
#: real backlog on 2026-09-02, five of seven items scored `AWAITING_REVIEW` and
#: all five were sent to PLAN unsigned. Three of those five PLAN agents refused
#: the work themselves, which is the gate holding only where an agent chose to
#: hold it.
#: IMPLEMENT is the first stage that WRITES, and it took until 2026-09-02 to add
#: because a writing stage needed the question this file used to defer: what tool
#: list, and writing WHERE. Both are answered in `stage-implement.md` — `Edit` and
#: `Write` on top of the read-only four, and every edit inside a git worktree the
#: agent makes itself, of the CONSUMER's repository, on a branch named after the
#: item. The read-only stages can share one tree and do; two writers in one tree
#: produce a diff neither of them authored.
#: REVIEW and RELEASE land 2026-09-14, and the reason they were missing is the reason
#: the loop kept stopping: the chain ran to IMPLEMENT and ended there, so a consumer
#: asking for an unattended run got five stages and a stop, every time, whatever was
#: fixed upstream.
#:
#: REVIEW is read-only on purpose — a reviewer who may edit cannot be trusted to report
#: what they found, because the finding and the fix become one act nobody can separate
#: afterwards. RELEASE carries `Edit` for the changelog and moves the status through
#: `backlog_status.py`, which stays the only writer of a status line.
#:
#: CODE-QUALITY has no stage of its own because it is not one: `run_validation.py`
#: invokes it inside IMPLEMENT, and `cycle-phases.txt` says so. A stage here would run
#: it twice and make the second run look like an independent confirmation of the first.
#:
#: ACCEPTANCE is still absent, and that absence is honest: it validates a MILESTONE
#: rather than an item, several items close one, and a per-item stage would be
#: answering a question nobody asked at this granularity.
STAGES = ("discover", "align", "judge", "plan", "implement", "review", "release")

DEFAULT_MODEL = "opus"

#: `align | sonnet | reason` — same shape as `skills/_kit-rules/review-model-routing.txt`.
#: A stage with no entry keeps the default, so an empty file changes nothing.
_ROUTING_RE = re.compile(r"^\s*([a-z-]+)\s*\|\s*([a-z0-9.-]+)\s*\|", re.IGNORECASE)

_PLACEHOLDER_RE = re.compile(r"\{[A-Z_]+\}")

#: What a backlog item id looks like. Validated because `--item` reaches the
#: filesystem: it becomes a directory name and it is substituted into every
#: generated prompt.
#:
#: Measured on 2026-09-02 — a caller's shell did not split a queue variable, so
#: `--item` received the string "B-033 B-136 B-162 B-171 B-172" and this script
#: created a directory with that name, holding four stage agents whose every
#: mention of "the item" named five. Nothing objected. The agents would have run
#: and reported findings against an item that does not exist.
#:
#: `squad.plan` has validated its own slug since it was written, for the same
#: reason and against the same hazard.
_ITEM_RE = re.compile(r"^[A-Za-z]+-\d+$")


def _parse_routing_rule(path: Path | None) -> dict[str, str]:
    """Parse routing rule file into model assignments by stage.

    Returns empty dict if file does not exist or is malformed.
    """
    if not path or not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _ROUTING_RE.match(line)
        if m:
            out[m.group(1).lower()] = m.group(2)
    return out


#: Words that carry no subject. Dropped so a five-word lane name spends its budget on
#: what the item is about rather than on grammar.
_LANE_FILLER = frozenset({
    "a", "an", "the", "to", "and", "or", "of", "for", "in", "on", "at", "by", "with",
    "that", "this", "is", "are", "be", "its", "it", "as", "not", "no", "from", "into",
    "what", "when", "where", "which", "than", "then", "so", "but",
})
#: A backlog id ANYWHERE in the title. `~/.claude/CLAUDE.md § 5.1` bans a ticket number
#: from a branch or a directory name, and a title that quotes one would smuggle it in.
_ID_IN_TEXT_RE = re.compile(r"\b[A-Z]{1,4}-\d+\b", re.IGNORECASE)
#: Five words is what fits in a branch listing without wrapping, measured against the
#: consumer's own headings.
_LANE_WORDS = 5
_LANE_MAX_CHARS = 48


def lane_name(title: str, item: str) -> str:
    """The branch and worktree name, derived from what the item IS.

    `~/.claude/CLAUDE.md § 5.1` bans a ticket number from a branch or directory name:
    "the name has to say what the thing DOES, not where it came from", and the number
    dies while the branch stays. The pipeline was generating `pipeline/b-018` and
    `/tmp/squad-worktrees/b-018-…`, so every consumer running it regenerated exactly
    what a consumer had just finished cleaning out by hand.

    There is NO fallback to the id. A lane that cannot be named by its subject is a
    registry entry with no subject, and silently naming it `b-018` is how the rule got
    broken in the first place — the caller is told to fix the title instead.
    """
    text = _ID_IN_TEXT_RE.sub(" ", title.replace("`", " "))
    words = [w for w in re.split(r"[^\w]+", text.lower()) if w and w not in _LANE_FILLER]
    name = "-".join(words[:_LANE_WORDS])[:_LANE_MAX_CHARS].strip("-")
    if not name:
        raise SystemExit(
            f"FATAL: {item} has no title to name its lane from. A branch is named by "
            f"what the work IS — `~/.claude/CLAUDE.md § 5.1` bans naming it `{item.lower()}`, "
            f"and falling back to the id would reintroduce exactly what the rule removes. "
            f"Give the item a heading in the registry and re-run.")
    return name


def title_of(repo: Path, item: str) -> str:
    """The item's heading text, read from the registry the consumer keeps."""
    for candidate in (repo / "BACKLOG.md", data_root(repo) / "BACKLOG.md"):
        if not candidate.is_file():
            continue
        pattern = re.compile(rf"^#+\s*{re.escape(item)}\s*[-—:]*\s*(?P<title>.+)$", re.MULTILINE)
        match = pattern.search(candidate.read_text(encoding="utf-8"))
        if match:
            # Trailing checkbox / status markers are decoration on the heading line.
            return re.sub(r"\s*\[[ xX~]\]\s*$", "", match.group("title")).strip()
    raise SystemExit(
        f"FATAL: no heading for {item} in {repo}/BACKLOG.md — the lane's branch and "
        f"worktree are named from it.")


def spawn(item: str, repo: Path, output_dir: Path,
          date: str | None = None, routing_rule: Path | None = None) -> list[Path]:
    if not _ITEM_RE.match(item):
        raise SystemExit(
            f"FATAL: {item!r} is not a backlog item id (expected e.g. `B-014`). "
            f"It would become a directory name and be substituted into every "
            f"generated prompt. A whole queue arriving here as one string is how "
            f"this was found — check that the caller's shell split it.")
    templates = Path(__file__).resolve().parent.parent / "templates"
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    models = _parse_routing_rule(routing_rule)
    # Resolved before any file is written: a lane that cannot be named must fail here,
    # not halfway through generating seven prompts that name a branch nobody will cut.
    lane = lane_name(title_of(repo, item), item)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for stage in STAGES:
        template = templates / f"stage-{stage}.md"
        if not template.is_file():
            raise SystemExit(f"FATAL: missing template {template}")
        text = template.read_text(encoding="utf-8")
        for token, value in (
            ("{ITEM}", item),
            ("{ITEM_SLUG}", item.lower()),
            ("{LANE}", lane),
            ("{REPO}", str(repo)),
            ("{DATE}", date),
            ("{MODEL}", models.get(stage, DEFAULT_MODEL)),
            ("{STAGE}", stage),
        ):
            text = text.replace(token, value)

        leftover = _PLACEHOLDER_RE.findall(text)
        if leftover:
            # A `{SLUG}` reaching an agent is an instruction with a hole in it.
            # The agent does not error on it; it improvises around the brace, and
            # the result reads as a bad answer rather than a bad prompt.
            raise SystemExit(
                f"FATAL: {template.name} still carries {sorted(set(leftover))} "
                f"after substitution")

        target = output_dir / f"{stage}.md"
        # Written whole, every time: a pipeline resumes, and regenerating must
        # replace rather than append.
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


def _default_output_dir(repo: Path, item: str) -> Path:
    """The cycle's data root for `repo`, not the caller's working directory.

    Exits rather than guessing. A guess here writes an audit trail somewhere
    nobody looks, and the whole point of materialising these files is that a
    wrong finding can be traced back to the prompt that produced it.
    """
    layout = resolve(repo)
    if layout is None:
        raise SystemExit(
            f"FATAL: no kit under {repo}, so there is no data root to write to. "
            f"Pass --output-dir explicitly if that is deliberate.")
    return write_records_dir(layout.project_dir, "pipeline-agents") / item.lower()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--item", required=True, help="backlog item id, e.g. B-014")
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--routing-rule", type=Path, default=None)
    args = ap.parse_args(argv)

    out = args.output_dir or _default_output_dir(args.repo, args.item)
    written = spawn(args.item, args.repo, out, args.date, args.routing_rule)
    print(f"wrote {len(written)} stage agent(s) to {out}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

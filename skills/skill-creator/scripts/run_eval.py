#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes Claude to trigger (read the skill)
for a set of queries. Outputs results as JSON.
"""

import argparse
import json
import os
import select
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Resolve the sibling import against THIS file rather than the caller's cwd.
#
# `from scripts.utils import …` only works when the process happens to start in
# `skills/skill-creator/`, so running or importing the module from anywhere else —
# a test, a CI step, the repo root — died on `ModuleNotFoundError: No module named
# 'scripts'`. The runner is a tool; a tool that only works from one directory is a
# tool nobody runs from the place they are standing.
_SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from scripts.utils import parse_skill_md  # noqa: E402


def find_project_root() -> Path:
    """Find the project root by walking up from cwd looking for .claude/.

    Mimics how Claude Code discovers its project root, so the command file
    we create ends up where claude -p will look for it.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


class TriggerDetector:
    """Folds `claude -p` stream events into one verdict: did THIS skill get used?

    Extracted from the read loop so it can be tested at all. Until 2026-09-01 the
    logic lived inline, had no test, and carried three instances of one defect —
    each deciding the whole turn from its first observation:

      1. `content_block_start` returned False the moment a tool that was not
         Skill/Read appeared. Measured: with `deps-audit`'s real description the
         model ran `Bash` three times to orient itself and invoked `Skill`
         correctly at position four. That run scored as "did not trigger".
      2. `content_block_stop` returned `clean_name in accumulated` for the first
         tool block, so a Skill call for a DIFFERENT skill ended the turn.
      3. `message_stop` returned False after the FIRST assistant message, and a
         turn routinely has five.

    Each one can only fail in one direction — it can call a trigger a miss, never
    a miss a trigger. A trigger rate from that instrument is a lower bound
    reported as a measurement, which is the worst kind of wrong number: it looks
    like a result about the skill.

    Paired against the same streams on 2026-09-01, five runs of one query: the old
    logic scored 4/5, this one 5/5, and the single divergence was the run whose
    first tool was `Bash`.

    The verdict is `True` as soon as a matching invocation is seen — the early
    return was always the right idea, and only the early NEGATIVE was wrong — and
    `False` only when the turn is over.
    """

    #: The tools that count as reaching for a skill. `Read` is here because a
    #: model that opens the SKILL.md has used it, whatever tool it used to do so.
    USING_TOOLS = ("Skill", "Read")

    def __init__(self, clean_name: str, skill_name: str | None = None) -> None:
        #: BOTH names count as reaching for the skill, and missing the second one is
        #: what made this instrument lie.
        #:
        #: The runner isolates a description by writing a command file under a unique
        #: name (`<skill>-skill-<uuid>`), and the detector matched only that. But in a
        #: repository where the skill ITSELF is discoverable, the model invokes the
        #: real one — `Skill(skill='backlog-item')` — and `"backlog-item-skill-9f2a"
        #: in "backlog-item"` is False.
        #:
        #: Measured 2026-09-01 on `backlog-item`: the battery scored 0/5 while a
        #: hand-run of the same query showed the model calling the skill at tool
        #: position five, after four `Bash` calls to orient itself. Every case was a
        #: trigger and every case was recorded as a miss — the shape this class's own
        #: docstring warns about, surviving in the one place it did not look.
        self.clean_name = clean_name
        self.skill_name = skill_name or clean_name
        self._names = tuple(n for n in {clean_name, self.skill_name} if n)
        self._pending_tool: str | None = None
        self._accumulated = ""

    def feed(self, event: dict) -> bool | None:
        """One event in; `True`/`False` when decided, `None` while undecided."""
        kind = event.get("type")

        if kind == "stream_event":
            return self._feed_stream(event.get("event", {}))

        # Fallback for a stream without partial messages: the whole message at
        # once. Every content item is scanned — the old code returned on the
        # first, which is defect (1) again in another shape.
        if kind == "assistant":
            for item in event.get("message", {}).get("content", []):
                if item.get("type") != "tool_use":
                    continue
                if self._names_this_skill(item.get("name", ""), item.get("input", {})):
                    return True
            return None

        # The turn ended without a matching invocation. This is the ONLY place a
        # negative verdict is allowed to come from.
        if kind == "result":
            return False
        return None

    def _feed_stream(self, stream_event: dict) -> bool | None:
        kind = stream_event.get("type", "")

        if kind == "content_block_start":
            block = stream_event.get("content_block", {})
            self._pending_tool = (block.get("name", "")
                                  if block.get("type") == "tool_use" else None)
            self._accumulated = ""
            return None

        if kind == "content_block_delta" and self._pending_tool in self.USING_TOOLS:
            delta = stream_event.get("delta", {})
            if delta.get("type") == "input_json_delta":
                self._accumulated += delta.get("partial_json", "")
                if any(n in self._accumulated for n in self._names):
                    return True
            return None

        if kind == "content_block_stop":
            # A block that was not this skill proves nothing about the next one.
            self._pending_tool = None
            self._accumulated = ""
        return None

    def _names_this_skill(self, tool_name: str, tool_input: dict) -> bool:
        if tool_name not in self.USING_TOOLS:
            return False
        target = tool_input.get("skill", "") if tool_name == "Skill" \
            else tool_input.get("file_path", "")
        return any(n in target for n in self._names)


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    Creates a command file in .claude/commands/ so it appears in Claude's
    available_skills list, then runs `claude -p` with the raw query.
    Uses --include-partial-messages to detect triggering early from
    stream events (content_block_start) rather than waiting for the
    full assistant message, which only arrives after tool execution.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    project_commands_dir = Path(project_root) / ".claude" / "commands"
    command_file = project_commands_dir / f"{clean_name}.md"

    try:
        project_commands_dir.mkdir(parents=True, exist_ok=True)
        # Use YAML block scalar to avoid breaking on quotes in description
        indented_desc = "\n  ".join(skill_description.split("\n"))
        command_content = (
            f"---\n"
            f"description: |\n"
            f"  {indented_desc}\n"
            f"---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {skill_description}\n"
        )
        command_file.write_text(command_content)

        cmd = [
            "claude",
            "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Remove CLAUDECODE env var to allow nesting claude -p inside a
        # Claude Code session. The guard is for interactive terminal conflicts;
        # programmatic subprocess usage is safe.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=project_root,
            env=env,
        )

        start_time = time.time()
        buffer = ""
        detector = TriggerDetector(clean_name, skill_name)

        try:
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break

                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if not ready:
                    continue

                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    verdict = detector.feed(event)
                    if verdict is not None:
                        return verdict

            # Drain whatever the last read left behind. The loop breaks the
            # moment the process has exited, and until 2026-09-01 the tail it had
            # just appended was dropped unparsed — a fast turn could put the
            # deciding event in exactly that chunk.
            for line in buffer.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                verdict = detector.feed(event)
                if verdict is not None:
                    return verdict
        finally:
            # Clean up process on any exit path (return, exception, timeout)
            if process.poll() is None:
                process.kill()
                process.wait()

        # Timed out, or the stream ended with no `result` event. Neither is evidence
        # the skill was not used; it is evidence nothing was observed — and this
        # comment said exactly that while the next line returned False, which the
        # caller counts as a miss.
        #
        # Measured 2026-09-01: a query where the model orients with several `Bash`
        # calls before invoking the skill runs past a 120s budget, and scored 0.0 —
        # a timeout published as a trigger rate. `None` now means undetermined, and
        # the caller keeps those out of the denominator instead of scoring them.
        return None
    finally:
        if command_file.exists():
            command_file.unlink()


def summarise_runs(
    query_triggers: dict[str, list],
    query_items: dict[str, dict],
    trigger_threshold: float,
) -> list[dict]:
    """Fold per-run verdicts into one row per query.

    Extracted so it can be tested: it used to live inside `run_eval`, which spawns
    subprocesses, so the rule that a timeout must not count as a miss could not be
    checked without invoking a model.

    `None` is a run that observed nothing — timeout, dead stream, exception. It
    leaves the ratio rather than diluting it, and is reported in its own column,
    because 3/5 with two timeouts and 3/5 with two real misses are different facts.
    """
    results: list[dict] = []
    for query, triggers in query_triggers.items():
        item = query_items[query]
        # `None` is a run that observed nothing — a timeout, a dead stream, an
        # exception. It is neither a trigger nor a miss, so it leaves the ratio
        # rather than diluting it, and is reported in its own column.
        observed = [x for x in triggers if x is not None]
        inconclusive = len(triggers) - len(observed)
        should_trigger = item["should_trigger"]

        if not observed:
            results.append({
                "query": query,
                "should_trigger": should_trigger,
                "trigger_rate": None,
                "triggers": 0,
                "runs": 0,
                "inconclusive": inconclusive,
                "pass": None,
                "verdict": "NOT_OBSERVED",
            })
            continue

        trigger_rate = sum(observed) / len(observed)
        did_pass = (trigger_rate >= trigger_threshold) if should_trigger \
            else (trigger_rate < trigger_threshold)
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(observed),
            "runs": len(observed),
            "inconclusive": inconclusive,
            "pass": did_pass,
        })

    return results


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    str(project_root),
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                query_triggers[query].append(future.result())
            except Exception as e:  # noqa: BLE001
                # An exception is also an inability, not an observation.
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(None)

    results = summarise_runs(query_triggers, query_items, trigger_threshold)

    passed = sum(1 for r in results if r["pass"] is True)
    total = len([r for r in results if r["pass"] is not None])

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            # `total` counts only the cases that were OBSERVED. A case nothing could
            # observe is reported separately rather than folded in as a failure —
            # 3/5 with two timeouts and 3/5 with two real misses are different facts.
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "not_observed": len([r for r in results if r["pass"] is None]),
        },
    }


def _normalise_eval_set(raw) -> list[dict]:
    """Accept the kit's own battery shape, not only upstream's.

    THE DEFECT THIS CLOSES
    ----------------------
    Upstream expects a LIST of `{query, should_trigger}`. Every battery this kit
    ships is a DICT of `{skill_name, notes, evals:[{prompt, assertions, …}]}` — so
    all four of them (`backlog-item`, `discover-plan`, `discover-edge-cases`,
    `discover-execute`) died on `TypeError: string indices must be integers`,
    iterating the dict's KEYS as if they were cases.

    They had therefore never been executed by anything, while
    `check_intake_gates.py` justified leaving gates G3/G4/G5 conversational on the
    grounds that *"the eval battery covers exactly that"*. A coverage claim resting
    on a file nothing can run is the contract-without-mechanism shape this kit exists
    to catch.

    WHAT THIS MAKES RUNNABLE, AND WHAT IT DOES NOT
    ----------------------------------------------
    This runner measures ONE thing: does the description make the model reach for the
    skill (`did THIS skill get used?`). Every case in a kit battery is a prompt where
    the skill SHOULD trigger, so `should_trigger` is True for all of them.

    It does **not** evaluate `assertions` — those describe BEHAVIOUR (did gate G5
    fire, was the block withheld) and no runner here checks them. Saying so is the
    point: `expected_output` and `assertions` remain a human-or-agent judgement, and
    calling this run a behaviour check would restate the very overclaim above.
    """
    if isinstance(raw, dict):
        cases = raw.get("evals", [])
    else:
        cases = raw
    out = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        query = case.get("query") or case.get("prompt")
        if not query:
            continue
        out.append({
            "query": query,
            "should_trigger": case.get("should_trigger", True),
            "name": case.get("name", ""),
        })
    return out


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default=None, help="Model to use for claude -p (default: user's configured model)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    eval_set = _normalise_eval_set(json.loads(Path(args.eval_set).read_text()))
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, _content = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = find_project_root()

    # MEASURING SOMETHING THAT IS NOT THERE PRODUCES A NUMBER, NOT A RESULT.
    #
    # `claude -p` discovers skills under `<project>/.claude/skills/`. Run against a
    # standalone kit — skills at the repo root, no `.claude/skills/` — the model
    # cannot reach the skill however good the description is, and every case scores
    # 0.0. Measured on 2026-09-01 against `backlog-item`: 5 of 5 "failed", with the
    # skill simply absent from the session.
    #
    # `skills/map.md` names this exact trap: a trigger rate "that reads low and looks
    # like a fact about the skill". So refuse rather than report: an inability is not
    # a measurement, which is the same distinction `check_intake_gates.py` was fixed
    # for and `check_opportunity_completeness.py` before it.
    discoverable = project_root / ".claude" / "skills" / skill_path.name / "SKILL.md"
    if not discoverable.is_file():
        print(json.dumps({
            "verdict": "SKILL_NOT_DISCOVERABLE",
            "skill": name,
            "expected_at": str(discoverable),
            "message": (
                "claude -p loads skills from <project>/.claude/skills/. This skill is "
                "not there, so the model cannot reach it and every case would score "
                "0.0 — an inability, not a trigger rate. Install the kit into a "
                "consumer, or symlink .claude/skills -> skills, then re-run."
            ),
        }, indent=2))
        sys.exit(2)

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=project_root,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

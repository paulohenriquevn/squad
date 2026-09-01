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

from scripts.utils import parse_skill_md


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

    def __init__(self, clean_name: str) -> None:
        self.clean_name = clean_name
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
                if self.clean_name in self._accumulated:
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
        return self.clean_name in target


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
        detector = TriggerDetector(clean_name)

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

        # Timed out, or the stream ended with no `result` event. Neither is
        # evidence the skill was not used; it is evidence nothing was observed.
        return False
    finally:
        if command_file.exists():
            command_file.unlink()


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
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


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

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, _content = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = find_project_root()

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

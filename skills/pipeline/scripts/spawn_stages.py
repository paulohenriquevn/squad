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

Usage:
    python3 spawn_stages.py --item B-014 --repo <path> [--output-dir DIR]
                            [--date YYYY-MM-DD] [--routing-rule FILE]

Exit codes:
    0 — every stage written
    1 — a template is missing, or a placeholder survived substitution
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

#: The stages this script materialises. IMPLEMENT and beyond are not here yet —
#: they write to the repository, and a writing stage needs its own review of what
#: the tool list should be. Naming the gap rather than shipping a template whose
#: permissions nobody thought about.
STAGES = ("discover", "align", "plan")

DEFAULT_MODEL = "opus"

#: `align | sonnet | reason` — same shape as `rules/review-model-routing.txt`.
#: A stage with no entry keeps the default, so an empty file changes nothing.
_ROUTING_RE = re.compile(r"^\s*([a-z-]+)\s*\|\s*([a-z0-9.-]+)\s*\|", re.IGNORECASE)

_PLACEHOLDER_RE = re.compile(r"\{[A-Z_]+\}")


def _routing(path: Path | None) -> dict[str, str]:
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


def spawn(item: str, repo: Path, output_dir: Path,
          date: str | None = None, routing_rule: Path | None = None) -> list[Path]:
    templates = Path(__file__).resolve().parent.parent / "templates"
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    models = _routing(routing_rule)
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--item", required=True, help="backlog item id, e.g. B-014")
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--routing-rule", type=Path, default=None)
    args = ap.parse_args(argv)

    out = args.output_dir or Path(".claude/agents") / f"pipeline-{args.item.lower()}"
    written = spawn(args.item, args.repo, out, args.date, args.routing_rule)
    print(f"wrote {len(written)} stage agent(s) to {out}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

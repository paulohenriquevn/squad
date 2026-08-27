#!/usr/bin/env python3
"""Gates G1 e G2 do intake, executados em vez de lembrados.

WHY THIS SCRIPT EXISTS
----------------------
`rules/cycle-backlog.md` declares five hard gates and the skill shipped not a
single script. G3 (single domain), G4 (verifiable DoD) and G5 (no prior-art
justification) are judgement and stay conversational — that is the right design,
and the eval battery covers exactly that. G1 and G2 are not judgement:

  G1 — the `repo` resolves to a domain with a specialist on disk.
       `scripts/route_domain.py` already did that, with 23 tests, and the skill
       did not call it: it instructed an inline `python3 -c`.
  G2 — the dedup search RAN. The skill instructed a `grep` whose execution nobody
       verified afterwards. A gate that depends on the agent remembering is not a
       gate; it is an intention.

What this script does NOT do: decide. It routes, searches, and returns the
candidates with the action the rule prescribes for each status. The choice between
`ITEM_MERGED`, `supersedes` and `regression_of` stays with the human in the grill
— a keyword hit is a candidate, not a verdict, and automating that decision would
invent wrong merges.

Uso:
    python3 check_intake_gates.py --backlog BACKLOG.md --repo theo-lens \\
        --term ingest --term latencia

Exit codes:
    0 — G1 and G2 passed, no dedup candidate
    1 — G1 refused the item (repo outside the routing table)
    2 — execution error (BACKLOG.md missing, table unreadable)
    3 — G2 encontrou candidatos: leia cada bloco antes de alocar um id novo
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


#: One definition of the block format, imported from whoever already maintains it.
#: A second regex here would diverge silently, and the two would disagree about
#: what the registry contains — the exact defect the backlog index exists to expose.
def _load_block_re() -> Any:
    for base in (
        Path(__file__).resolve().parents[2] / "backlog-review" / "scripts",
        Path(__file__).resolve().parents[4] / "skills" / "backlog-review" / "scripts",
    ):
        if (base / "check_backlog_structure.py").is_file():
            sys.path.insert(0, str(base))
            from check_backlog_structure import BLOCK_RE

            return BLOCK_RE
    raise FileNotFoundError(
        "check_backlog_structure.py not found — the BACKLOG block parser is "
        "maintained there and is not duplicated here"
    )


STATUS_RE = re.compile(r"^status:\s*`?([a-z_]+)`?", re.MULTILINE)

#: What the rule prescribes for each status the search hits
#: (`rules/cycle-backlog.md § Chain`, Step 2 do SKILL).
ACTION_BY_STATUS = {
    "raw": "ITEM_MERGED",
    "triaged": "ITEM_MERGED",
    "planned": "ITEM_MERGED",
    "killed": "supersedes",
    "shipped": "regression_of",
}


def _route(repo: str, project_root: Path) -> dict[str, Any]:
    """G1 — delegates to the routing table, which is the single source."""
    for candidate in (project_root / "scripts" / "route_domain.py",
                      project_root / ".claude" / "scripts" / "route_domain.py"):
        if candidate.is_file():
            script = candidate
            break
    else:
        return {"routed": False, "error": "route_domain.py not found"}

    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(script), repo, "--json"],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"routed": False, "error": result.stderr.strip() or "unreadable output"}
    payload.setdefault("routed", False)
    return payload


def _dedup(backlog_text: str, terms: list[str]) -> list[dict[str, Any]]:
    """G2 — every block whose title or body matches any term (case-insensitive)."""
    block_re = _load_block_re()
    matches = list(block_re.finditer(backlog_text))
    lowered = [t.lower() for t in terms if t.strip()]
    candidates: list[dict[str, Any]] = []

    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(backlog_text)
        body = backlog_text[start:end]
        haystack = f"{match.group(2)}\n{body}".lower()

        hits = [term for term in lowered if term in haystack]
        if not hits:
            continue
        status_match = STATUS_RE.search(body)
        status = status_match.group(1) if status_match else "unknown"
        candidates.append({
            "id": match.group(1),
            "title": match.group(2).strip(),
            "status": status,
            "matched_terms": hits,
            "recommended_action": ACTION_BY_STATUS.get(status, "read the block before deciding"),
        })
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backlog", type=Path, required=True)
    parser.add_argument("--repo", required=True, help="o campo `repo:` do item (gate G1)")
    parser.add_argument("--term", action="append", default=[],
                        help="meaningful noun from the description (repeatable)")
    parser.add_argument("--project-root", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.backlog.is_file():
        print(json.dumps({
            "verdict": "ERROR",
            "message": f"BACKLOG.md not found at {args.backlog} — run /backlog-init first",
        }, indent=2, ensure_ascii=False))
        return 2

    project_root = args.project_root or Path.cwd()
    g1 = _route(args.repo, project_root)

    # The repo name is ALWAYS a search term. Leaving that to the caller is how the
    # repo dropped out of the search with nobody noticing — and the repo is the term
    # that collides most in a registry covering 21 of them.
    terms = list(dict.fromkeys([*args.term, args.repo]))
    try:
        candidates = _dedup(args.backlog.read_text(encoding="utf-8-sig"), terms)
    except FileNotFoundError as exc:
        print(json.dumps({"verdict": "ERROR", "message": str(exc)}, indent=2, ensure_ascii=False))
        return 2

    if not g1.get("routed"):
        verdict, code = "ITEM_REJECTED", 1
    elif candidates:
        verdict, code = "DEDUP_CANDIDATES", 3
    else:
        verdict, code = "GATES_PASS", 0

    print(json.dumps({
        "verdict": verdict,
        "g1": g1,
        "g2": {"searched": True, "terms": terms, "candidates": candidates},
    }, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())

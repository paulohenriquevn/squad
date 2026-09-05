#!/usr/bin/env python3
"""Intake gates G1 and G2, executed rather than remembered.

WHY THIS SCRIPT EXISTS
----------------------
`rules/cycle-backlog.md` declares SEVEN hard gates and the skill shipped not a
single script. Four of them are mechanizable and are mechanized: G1 and G2 here,
G6 and G7 (impediment edges) in `check_backlog_structure.py`. G3 (single domain),
G4 (verifiable DoD) and G5 (no prior-art justification) are judgement and stay
conversational — that is the right design.

**What covers them, precisely.** `evals/evals.json` carries one case per judgement
gate, and `tests/test_check_intake_gates.py` checks mechanically that no gate claimed
here goes without one. What a run measures is TRIGGER — whether the description makes
the model reach for this skill — because that is what `run_eval.py` evaluates. The
`assertions` in each case describe BEHAVIOUR (did G5 fire, was the block withheld)
and **no runner checks them**; they are a reader's judgement.

That distinction is stated because the earlier wording — *"the eval battery covers
exactly that"* — read as behavioural coverage, and until 2026-09-01 the battery could
not be executed at all: every one of this kit's four batteries died on
`TypeError: string indices must be integers`, the runner expecting upstream's list
shape. A coverage claim resting on a file nothing could run is the
contract-without-mechanism failure this script was itself fixed for once.

  G1 — the `repo` resolves to a domain with a specialist on disk.
       `mechanisms/cycle/route_domain.py` already did that, with 23 tests, and the skill
       did not call it: it instructed an inline `python3 -c`.
  G2 — the dedup search RAN. The skill instructed a `grep` whose execution nobody
       verified afterwards. A gate that depends on the agent remembering is not a
       gate; it is an intention.

What this script does NOT do: decide. It routes, searches, and returns the
candidates with the action the rule prescribes for each status. The choice between
`ITEM_MERGED`, `supersedes` and `regression_of` stays with the human in the grill
— a keyword hit is a candidate, not a verdict, and automating that decision would
invent wrong merges.

"COULD NOT JUDGE" IS NOT "REFUSED"
----------------------------------
Every error path used to collapse into `ITEM_REJECTED`, exit 1 — the verdict the
contract defines as *the item was refused*. An unreadable routing table produced
it, so a filer whose project had never derived a table was told to reformulate a
perfectly good item.

The two actions are opposite: a refused item is reworded, an unreadable table is
derived with `detect_domains.py --write`. So an inability now returns
`GATE_INCONCLUSIVE` and exit 2, which the docstring had promised and no code path
produced.

`check_backlog_structure.py` had already reasoned this through for the same
question and left the argument in its own source: *"None is not an empty set: an
unreadable table means we cannot judge routing, and reporting every repo as
unroutable from missing data would assert a violation the evidence does not
support."* This file now follows its sibling.

Usage:
    python3 check_intake_gates.py --backlog BACKLOG.md --repo web-console \\
        --term ingest --term latency

Exit codes:
    0 — GATES_PASS: G1 and G2 passed, no dedup candidate
    1 — ITEM_REJECTED: G1 judged and refused — see `g1.reason`
    2 — GATE_INCONCLUSIVE: the gate could not run. Nothing was judged
    3 — DEDUP_CANDIDATES: read every block before allocating a new id
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

#: What to DO about each refusal or inability. A verdict that does not say how to fix
#: it just gets re-filed verbatim tomorrow (`skills/backlog-item/SKILL.md` § Step 7).
_ACTION_BY_REASON = {
    "unroutable_repo":
        "the repo is in no domain. Add it to rules/domain-routing.txt, or file the "
        "item against a repo the table knows.",
    "broken_route":
        "the table routes this repo to a specialist nobody wrote. Write "
        "agents/<domain>.md — do NOT stand in for it (agents/README.md).",
    "routing_table_unreadable":
        "the routing table could not be parsed. Derive it: "
        "detect_domains.py --root . --write rules/domain-routing.txt. "
        "The ITEM was not judged.",
    "route_domain_missing":
        "route_domain.py is not installed. The ITEM was not judged; fix the "
        "installation before reading this as a verdict about it.",
}

#: What the rule prescribes for each status the search hits
#: (`rules/cycle-backlog.md § Chain`, Step 2 do SKILL).
ACTION_BY_STATUS = {
    "raw": "ITEM_MERGED",
    "triaged": "ITEM_MERGED",
    # `approved` is open, so a duplicate folds into it exactly as it does into a
    # triaged or planned item. It was missing from 2026-09-04, when the status
    # entered the contract, until 2026-09-05 — a new item duplicating an approved
    # one fell through this table and got its own id, which is how one piece of
    # work becomes two rows nobody reconciles.
    "approved": "ITEM_MERGED",
    "planned": "ITEM_MERGED",
    "killed": "supersedes",
    "shipped": "regression_of",
}


#: `route_domain.py`'s exit codes, and what each one means for the ITEM.
#:
#: The distinction that matters is judged-vs-could-not-judge. Exits 1 and 3 are
#: judgements about routing — the table was read and the answer is no. Exit 2 is an
#: inability: nothing about the item was assessed, so calling it a refusal states a
#: verdict no evidence supports.
_ROUTE_OUTCOME = {
    0: ("routed", None),
    1: ("rejected", "unroutable_repo"),
    2: ("inconclusive", "routing_table_unreadable"),
    3: ("rejected", "broken_route"),
}


def _route(repo: str, project_root: Path) -> dict[str, Any]:
    """G1 — delegates to the routing table, which is the single source.

    Reads the EXIT CODE, not only the JSON body. The previous version parsed stdout
    and inferred everything from the `routed` field, so an error — which writes to
    stderr and leaves stdout empty — became `{"routed": False}`, indistinguishable
    from a repo legitimately outside the table.
    """
    for candidate in (project_root / "mechanisms" / "cycle" / "route_domain.py",
                      project_root / ".claude" / "mechanisms" / "cycle" / "route_domain.py"):
        if candidate.is_file():
            script = candidate
            break
    else:
        # The tool is absent, so routing was never assessed. Not a refusal.
        return {"routed": False, "outcome": "inconclusive", "reason": "route_domain_missing",
                "error": "route_domain.py not found under scripts/ or .claude/scripts/"}

    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(script), repo, "--json"],
        capture_output=True, text=True,
    )
    outcome, reason = _ROUTE_OUTCOME.get(
        result.returncode, ("inconclusive", f"route_domain_exit_{result.returncode}")
    )

    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    payload["routed"] = outcome == "routed"
    payload["outcome"] = outcome
    if reason:
        payload["reason"] = reason
    if outcome != "routed":
        detail = result.stderr.strip() or result.stdout.strip()
        if detail:
            payload["error"] = detail
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
    parser.add_argument("--repo", required=True, help="the item's `repo:` field (gate G1)")
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

    # No silent default. A missing `outcome` means `_route` returned a shape it was
    # not supposed to, and defaulting would hide that behind a plausible verdict —
    # the failure this whole fix is about, one level up. Fail loudly instead.
    outcome = g1.get("outcome")
    if outcome not in ("routed", "rejected", "inconclusive"):
        print(json.dumps({
            "verdict": "GATE_INCONCLUSIVE",
            "g1": g1,
            "action": f"_route returned no usable outcome ({outcome!r}). This is a bug in "
                      "check_intake_gates.py, not a judgement about the item.",
        }, indent=2, ensure_ascii=False))
        return 2
    if outcome == "inconclusive":
        # Nothing about the item was judged. Saying ITEM_REJECTED here sends the
        # filer to reword a good item when the fix is to derive the routing table.
        verdict, code = "GATE_INCONCLUSIVE", 2
    elif outcome == "rejected":
        verdict, code = "ITEM_REJECTED", 1
    elif candidates:
        verdict, code = "DEDUP_CANDIDATES", 3
    else:
        verdict, code = "GATES_PASS", 0

    payload: dict[str, Any] = {
        "verdict": verdict,
        "g1": g1,
        "g2": {"searched": True, "terms": terms, "candidates": candidates},
    }
    action = _ACTION_BY_REASON.get(g1.get("reason", ""))
    if action:
        payload["action"] = action
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Intake gates G1 and G2, executed rather than remembered.

WHY THIS SCRIPT EXISTS
----------------------
`rules/cycle-backlog.md` declares SEVEN hard gates and the skill shipped not a
single script. Five of them are mechanized: G1 and G2 here, G6 and G7 (impediment edges) in
`check_backlog_structure.py`, and G5 for the items the SYSTEM creates — `g5_route`
below answers "can this be decided without a person" and routes only the ones that can.

G3 (single domain) and G4 (verifiable DoD) are judgement and stay conversational —
that is the right design.

This paragraph said G5 was conversational too, and kept saying it after `g5_route`
shipped. `evals/evals.json` repeated it. A gate described as unmechanized is a gate
nobody looks for in the code, so the mechanism that exists went unused by any reader
who trusted the description.

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
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import subprocess  # noqa: E402 — post-bootstrap import
import sys  # noqa: E402 — post-bootstrap import
from pathlib import Path  # noqa: E402 — post-bootstrap import
from typing import Any  # noqa: E402 — post-bootstrap import

from squad.paths import (  # noqa: E402 — post-bootstrap import
    DATA_DIRNAME,
    LEGACY_RECORDS_ROOTS,
)


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
        "the repo is in no domain. Add it to `domain-routing.txt`, or file the "
        "item against a repo the table knows.",
    "broken_route":
        "the table routes this repo to a specialist nobody wrote. Write "
        "agents/<domain>.md — do NOT stand in for it (agents/README.md).",
    "routing_table_unreadable":
        "the routing table could not be parsed. Derive it: "
        "detect_domains.py --root . --write. "
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


#: A `why_now` that names a phase, its verdict and the item it ended. Deliberately
#: narrow: prose ABOUT a halt is still prose, and only a citation can be looked up.
_HALT_CITATION = re.compile(
    r"(?P<cycle>[a-z][a-z-]{2,})\s+(?:phase\s+)?ended\s+(?P<verdict>[A-Z][A-Z_]{3,})"
    r"\s+for\s+(?P<slug>[A-Za-z][\w.-]{1,60})"
)


def _events_path(project_root: Path) -> Path | None:
    for base in (f"{DATA_DIRNAME}/records", *LEGACY_RECORDS_ROOTS):
        candidate = project_root / base / "cycle-events.jsonl"
        if candidate.is_file():
            return candidate
    return None


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
                "error": "route_domain.py not found under mechanisms/cycle/ or "
                          ".claude/mechanisms/cycle/ — the two paths searched above"}

    # The project is NAMED, never inferred. This used to rely on `route_domain.py`
    # deducing its root from `Path(__file__)` — which only worked because the copy
    # install puts the mechanism inside the project being judged, and silently read
    # the wrong table anywhere else (#37).
    result = subprocess.run(
        [sys.executable, str(script), repo, "--json",
         "--project-root", str(project_root)],
        capture_output=True, text=True,
     check=False)
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


def _dedup_reach(backlog: Path) -> dict[str, Any]:
    """How far the G2 search could see, so `no candidates` is not read as `no duplicate`.

    `_dedup` searches the registry FILE and nothing else. An id whose block was removed from
    it is invisible here however loudly the rest of the project cites it — measured on a
    consumer 2026-09-20: 64 blocks in `BACKLOG.md` against 187 distinct `B-NNN` cited across
    `.squad/`, `docs/`, `CHANGELOG.md` and the packages, leaving **138** ids the search cannot
    reach. The gap is a contiguous run, so those items existed and were deleted rather than
    closed in place.

    Reported rather than closed, and the distinction is the point: scanning the whole project
    for citations would make intake pay for a graph walk on every filed item, and the ids it
    found would be mentions rather than blocks — there is nothing to compare a new item
    against. What a filer can act on is knowing the search had a horizon. An empty result that
    does not say where it looked reads as "no duplicate exists", which is the silence
    `check_reference_leakage.py` refuses when it reports PARTIAL coverage instead of a clean
    run.
    """
    try:
        text = backlog.read_text(encoding="utf-8-sig")
    except OSError:
        return {"searched_blocks": 0, "not_searched": ["the registry file could not be read"]}
    blocks = len(_load_block_re().findall(text))
    return {
        "searched_blocks": blocks,
        "not_searched": [
            f"only the {blocks} block(s) in {backlog.name}. An id cited elsewhere in the "
            "project but no longer carrying a block here is not reachable by this gate, so "
            "`candidates: []` means none was found IN THE FILE — not that none exists.",
        ],
    }


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


def g5_route(why_now: str, project_root: Path) -> dict[str, Any]:
    """Can G5 be answered without a person, for THIS item?

    G5 asks whether `why_now` justifies the item by what another project does or by
    something that changed in OUR system, and `cycle-backlog.md` says the human decides.
    That is right for an item somebody typed. It is the wrong owner for an item the
    system itself created.

    A reviewer found the consequence: halts return work to the registry, so an
    autonomous run can reach a human decision by coming back to the entrance. "Zero
    interventions after BACKLOG" does not survive the recirculation.

    An item born from a halt has a `why_now` that is a gate id and a run — a LOOKUP, not
    a claim. When the event is on disk, G5 is answered by reading it; the class of
    justification G5 refuses (an appeal to another project) cannot be what a phase of
    ours emitted. When it is not on disk, this returns `human` and nothing is assumed:
    a `why_now` that merely SAYS a gate fired is exactly the fabricated local reason
    G5's second half was written about.
    """
    text = (why_now or "").strip()
    if not text:
        return {"outcome": "human", "reason": "no `why_now` to evaluate"}

    match = _HALT_CITATION.search(text)
    if match is None:
        return {"outcome": "human",
                "reason": "`why_now` cites no phase verdict from this system, so the "
                          "prior-art question is a judgement about language"}

    cycle, verdict, slug = match.group("cycle"), match.group("verdict"), match.group("slug")
    events = _events_path(project_root)
    if events is None:
        return {"outcome": "human",
                "reason": f"`why_now` cites {cycle}/{verdict} for {slug} and no event "
                          "stream is on disk to confirm it. An unconfirmed citation is "
                          "the fabricated local reason G5 exists to refuse"}

    for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if (ev.get("cycle") == cycle and ev.get("verdict") == verdict
                and ev.get("slug") == slug):
            return {"outcome": "mechanized",
                    "reason": f"`why_now` cites {cycle} ending {verdict} for {slug}, and "
                              "that event is in this project's own stream. The "
                              "justification is ours by construction — G5 needs no "
                              "person here",
                    "evidence": {"cycle": cycle, "verdict": verdict, "slug": slug,
                                 "stream": str(events)}}

    return {"outcome": "human",
            "reason": f"`why_now` cites {cycle}/{verdict} for {slug} and the stream does "
                      "not carry it. A citation nobody can confirm is worse than none"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backlog", type=Path, required=True)
    parser.add_argument("--repo", required=True, help="the item's `repo:` field (gate G1)")
    parser.add_argument("--term", action="append", default=[],
                        help="meaningful noun from the description (repeatable)")
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--why-now", default="",
                        help="the item's `why_now` field. When it cites a phase verdict "
                             "this project's own stream carries, G5 is answered by "
                             "lookup instead of by a person (gate G5)")
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

    # G5 stays a judgement for an item somebody typed, and stops being one for an item
    # a halt produced: `why_now` is then a citation into this project's own stream.
    # Reported either way, so a reader sees which of the two this was.
    g5 = g5_route(args.why_now, project_root)
    payload: dict[str, Any] = {
        "verdict": verdict,
        "g1": g1,
        "g2": {"searched": True, "terms": terms, "candidates": candidates, **_dedup_reach(args.backlog)},
        "g5": g5,
    }
    if g5["outcome"] == "human":
        payload["not_checked"] = [
            "G5 (prior-art justification) — " + g5["reason"],
        ]
    action = _ACTION_BY_REASON.get(g1.get("reason", ""))
    if action:
        payload["action"] = action
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())

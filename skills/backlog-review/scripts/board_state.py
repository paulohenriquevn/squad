#!/usr/bin/env python3
"""The whole picture, as one JSON document: every item, where it is, what holds it.

Two sources, and they answer different questions:

  BACKLOG.md              WHERE each item stands right now — the state that survives
                          the session, and the only one that exists for work done
                          before the cycle was instrumented.
  cycle-events.jsonl      WHAT HAPPENED and when — the phase transitions, with the
                          verdict each one reached.

The second is the richer one and the one that is usually empty. It is per-machine and
per-session by decision (`.gitignore` carries the reason: one machine's run history
does not belong in everyone's diff), and it starts empty in every clone. So the board
must be legible from the registry ALONE, and treat the stream as detail it may or may
not have — a board that needs the stream shows an empty screen in the exact situation
someone first opens it.

Position is therefore derived twice, in order of confidence:

  1. the last phase the stream says finished, when there is a stream
  2. otherwise the phase implied by `status`, which is all the registry can say

`stream` vs `derived` is reported per item, because a board that presents an inference
and a measurement in the same typeface is doing the thing this ecosystem caps plans
at 49 for.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

from check_backlog_structure import (
    OPEN_STATUS,
    _parse_items,
    declares_impediment,
    parse_blocked_by,
)

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import (  # noqa: E402 — post-bootstrap import
    DATA_DIRNAME,
    LEGACY_RECORDS_ROOTS,
    rules_dir,
)


#: The board's columns, in cycle order, READ FROM THE DECLARATION rather than copied.
#: `killed` is a lane rather than a column: it is a terminal OUTCOME, and the contract
#: is explicit that it is a successful one, so burying it after `release` would put a
#: success at the end of a pipeline it left early.
#:
#: This was a literal tuple of eight names. `cycle-phases.txt` gained `brainstorm` on
#: 2026-09-01 and the tuple did not, so the board drew a chain that had nine phases as
#: if it had eight — silently, because nothing compares a hardcoded list to the file
#: that declares the chain. `check_phase_drift.py` reads that file, `check_squad_map.py`
#: reads that file, and this was the one reader carrying its own copy.
#:
#: Found by exercising `board_server.py` for real: `/api/state` reported eight phases
#: starting at `backlog`. No test caught it because every test asserted against
#: `PHASES` itself, which agrees with itself no matter what it says.
def _declared_phases() -> tuple[tuple[str, ...], str]:
    """The chain from `rules/cycle-phases.txt`, in declared order.

    Falls back to the historical eight only when the file cannot be read — a board
    that renders nothing is worse than one rendering a stale chain, and the fallback
    is narrow enough to be obvious when it fires.
    """
    for base in (Path(__file__).resolve().parents[3], Path.cwd(), Path.cwd() / ".claude"):
        path = base / "rules" / "cycle-phases.txt"
        if not path.is_file():
            continue
        names = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            if line and "|" in line:
                names.append(line.split("|")[0].strip())
        if names:
            return tuple(names), "declared"
    # The fallback is NAMED. `PHASES` drives what the board draws and which events are
    # placed, so a chain nobody read produced a board that looks exactly like a board
    # drawn from the contract — and the eight names here are a snapshot of one moment
    # in a file that changes.
    return (("backlog", "discover", "plan", "implement", "code-quality", "review",
             "release", "acceptance"), "fallback")


PHASES, PHASES_SOURCE = _declared_phases()

#: What a registry status implies about position when no stream exists: the last
#: phase the status proves ENDED. Not the next one — entering a phase is a guess.
#:
#: `shipped` and `killed` are the exception, and deliberately so. They are not
#: positions in the cycle, they are OUTCOMES: the work left. Drawing `shipped` in
#: `release` put 133 of 170 items in one column and left `done` — a column the board
#: has always rendered — permanently empty. The operator could not read the board,
#: and the reason was that the column meaning "finished" was never given anyone.
#: `approved` maps to `discover`, the same as `triaged`, and that is not an
#: oversight. This map answers "what is the last phase this status PROVES ended",
#: and approval is a decision, not a phase — `rules/cycle-phases.txt` declares
#: nine and none of them is where a sponsor says yes. An approved item has ended
#: discover and has not entered plan, which is exactly what `triaged` also means
#: positionally. The two differ in commitment, not in position, and inventing a
#: column for the difference would draw a phase the cycle does not have.
STATUS_PHASE = {
    "raw": "backlog",
    "triaged": "discover",
    "approved": "discover",
    "planned": "plan",
    "shipped": "done",
    "killed": "killed",
}


#: An item id anywhere in a slug, with or without the hyphen.
_SLUG_ITEM_RE = re.compile(r"\bb-?(\d{3,})\b", re.IGNORECASE)


def item_id_of(slug: str) -> str:
    """The `B-NNN` a stream slug refers to, normalised.

    Two conventions reach the stream and both are correct in their own phase. The
    phases instrumented for the maintenance chain emit the ITEM id — `B-033` — because
    that is what the registry keys on. The phases that were already emitting
    (`implement`, `code-quality`, `review`) emit the PLAN slug — `b033-prometheus-url-
    dev-public` — because that is what names the artefact they produced.

    Matching on the raw string loses the second kind entirely. Measured on the first
    real run: 12 events, 6 of them plan slugs, and every one of those six invisible on
    the board — half the execution, missing from the view built to show it.
    """
    match = _SLUG_ITEM_RE.search(slug or "")
    return f"B-{match.group(1)}" if match else (slug or "").upper()


def _events_path(project_root: Path) -> Path | None:
    for rel in (f"{b}/cycle-events.jsonl"
                for b in (f"{DATA_DIRNAME}/records", *LEGACY_RECORDS_ROOTS)):
        candidate = project_root / rel
        if candidate.is_file():
            return candidate
    return None


def read_events(project_root: Path) -> list[dict]:
    path = _events_path(project_root)
    if path is None:
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # A truncated last line is normal in an append-only file being written
            # right now. Dropping it beats refusing to render the board.
            continue
    return events


#: Mirrors `squad_lead.py`'s own `--stalled` default. Below this the session has moved
#: recently enough that the lead would not call it stalled, so any stall in the log is
#: one it already recovered from.
_STALL_HORIZON_SECONDS = 900



#: Where each phase leaves its work. Globbed by the item's slug rather than named
#: exactly, because a slug is `b033-prometheus-url-dev-public` while the id is `B-033`
#: and several artefacts carry a date as well.
_ARTEFACT_DIRS = (
    ("discover", "discoveries/opportunities"),
    ("discover", "discoveries/plans"),
    ("plan", "plans"),
    ("plan", "alignment"),
    ("implement", "implementations"),
    ("code-quality", "audits"),
    ("review", "reviews"),
    ("release", "releases"),
)

#: Where the shared list lives. The board used to keep its own copy, and the copies
#: disagreed: the drift checker called `implement FAIL` a verdict that forbids
#: advancing while this panel said "no gate is holding this item" about the same
#: event. One repository must not give two answers about one item.
_VERDICTS_RULE = "blocking-verdicts.txt"


def blocking_verdicts(project_root: Path) -> frozenset[str] | None:
    """The verdicts `rules/blocking-verdicts.txt` declares, or None when it is absent.

    The docstring promised this and the code did the opposite: an absent file returned
    `frozenset()`, and an empty set makes `verdict.upper() in blocking` false for every
    verdict — so the panel rendered "nothing is holding this item" over a rule file it
    never found. None is what lets the caller tell the two apart, which is the whole
    sentence below.

    An absent file returns nothing and the panel says so, rather than claiming the
    item is unheld: the board reports what it can read, and a missing rule file is
    something it could not read — not evidence that no gate is closed.
    """
    # `squad.paths.rules_dir` owns the order; six sites used one and three the other.
    directory = rules_dir(project_root)
    for candidate in ([directory / _VERDICTS_RULE] if directory else []):
        if candidate.is_file():
            verdicts = {
                line.split("#", 1)[0].strip().upper()
                for line in candidate.read_text(encoding="utf-8",
                                                errors="replace").splitlines()
            }
            verdicts.discard("")
            return frozenset(verdicts)
    return None


#: The progress file is named `.progress-<slug>.json`, so the slug is not simply the
#: stem: stripping only the suffix leaves `progress-b033-…`, which matches no plan and
#: no artefact. Latent in `_slug_for` too — it happened to look in `plans` first.
_PROGRESS_PREFIX = "progress-"


#: Directory a phase writes into -> the phase's name on the board.
_PHASE_OF_DIR = {"implementations": "implement", "reviews": "review",
                 "releases": "release"}


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="seconds")


def _slug_from_filename(name: str, suffix: str) -> str:
    slug = name.lstrip(".")[: -len(suffix)]
    return slug[len(_PROGRESS_PREFIX):] if slug.startswith(_PROGRESS_PREFIX) else slug


def _slug_for(item_id: str, records: Path) -> str | None:
    """The plan slug an item goes by on disk, e.g. `b033-prometheus-url-dev-public`.

    Derived from what exists rather than constructed, because only the phase that
    wrote the artefact knows the words after the number.
    """
    #: Two spellings are in use for one thing, and a reader that knows only one finds
    #: nothing. `b033-prometheus-url-dev-public` is the form this docstring was written
    #: for; `B-022-plan.md` — the bare id — is what a consumer's own PLAN stage writes.
    #:
    #: The old match lowercased and stripped the hyphen (`B-022` -> `b022`) and globbed
    #: `*b022*`. On a case-sensitive filesystem that never matches `B-022-plan.md`.
    #: Measured on a consumer 2026-09-16: `slug` was None for ALL 35 items holding a
    #: plan, so `item_detail` never opened one — `phases: []`, `tasks: []`,
    #: `done_ratio: None` — and the implementation view drew 35 blocks whose only
    #: content was the fallback sentence. A list of empty items, which is exactly what
    #: it looked like.
    #:
    #: Matched on the FILENAME rather than by constructing a slug, because only the
    #: phase that wrote the artefact knows the words after the number — that part of the
    #: original reasoning was right and is kept.
    candidates = (item_id.lower(), item_id.replace("-", "").lower())
    for base in ("plans", "implementations", "alignment"):
        directory = records / base
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            name = entry.name.lstrip(".")
            lowered = name.lower()
            if not any(c in lowered for c in candidates):
                continue
            for suffix in ("-plan.md", "-implementation.md", "-alignment.md", ".json"):
                if name.endswith(suffix):
                    return _slug_from_filename(entry.name, suffix)
    return None


#: Task statuses that mean the work is finished. `committed` is what this cycle
#: writes; anything else counts as outstanding rather than being guessed at.
_DONE_TASK_STATUS = frozenset({"committed", "done", "completed", "merged"})


def _records_dir(project_root: Path) -> Path | None:
    for rel in (f"{DATA_DIRNAME}/records", *LEGACY_RECORDS_ROOTS):
        candidate = project_root / rel
        if candidate.is_dir():
            return candidate
    return None


def halted_items(project_root: Path) -> set[str]:
    """Items a phase stopped on and wrote a BLOCKED report for.

    Separate from the registry's `blocked_by`, and deliberately so: that field is a
    person declaring an impediment, this is a phase declaring it stopped. Both hold
    the item; different things must be done about them, so the board counts them
    apart rather than folding one into the other.

    The scan itself lives in `scripts/squad_boss.py`, which is the single reader of
    these files. Two scans of one directory drift the way two copies of a
    blocking-verdict list already did in this repository.
    """
    try:
        from squad_boss import halt_reports
    except ImportError:
        return set()
    return set(halt_reports(project_root))


#: Item id -> the furthest stage whose RECORD exists on disk.
#:
#: `STATUS_PHASE` maps `approved` to `discover`, which is where an approved item is
#: until something writes a plan for it. Nothing writes the status when that happens:
#: `planned` is issued by the stage that STARTS work, so between PLAN and IMPLEMENT the
#: registry says nothing at all about a plan that exists.
#:
#: Measured on a consumer 2026-09-16: 35 plans written, 34 belonging to items still
#: `approved` — every one of them drawn in `discover`, a phase they had left. The board
#: showed 82 items in `discover` and the true figure was 57. An operator reading that
#: column saw work nobody had started sitting where finished plans were.
#:
#: Records, not status, for the same reason `select_backlog_item` reads them: a file on
#: disk is a fact about what happened, and the status is a claim somebody has to
#: remember to write. The ladder stops at implementations — `reviews/` names files
#: `{ITEM}-{phase}-{date}.md`, and reading one as "REVIEW finished" would assign a
#: meaning the filename does not carry.
_RECORD_STAGE = (("implementations", "-implementation.md", "implement"),
                 ("plans", "-plan.md", "plan"))


def stage_on_disk(project_root: Path) -> dict[str, str]:
    """Item id -> `implement` or `plan`, whichever record exists. One listing each."""
    records = _records_dir(project_root)
    if records is None:
        return {}
    # Through `squad_boss.records_by_item`, the one reader that knows both filename
    # spellings. This carried its own prefix glob — `entry.name[: -len(suffix)]` — which
    # matched `B-022-plan.md` and missed `b022-descriptive-words-plan.md`, so this MODULE
    # held two readers of one question and only `_slug_for` had been corrected.
    try:
        from squad_boss import records_by_item
    except ImportError:
        return {}
    reached: dict[str, str] = {}
    for base, suffix, stage in _RECORD_STAGE:
        for item_id in records_by_item(records, base, suffix):
            # First writer wins: the tuple is ordered furthest-stage-first, so an item
            # with both records is reported at the later one.
            reached.setdefault(item_id, stage)
    return reached


#: `B-NNN` as a plan body writes it.
_ITEM_CITATION_RE = re.compile(r"\bB-\d{3,}\b")


def planned_items(project_root: Path) -> dict[str, str]:
    """Item id -> plan slug, for every item the cycle has actually planned on disk.

    One directory listing for the whole registry. The alternative — asking
    `item_detail` per item — reads every plan and progress file to answer a yes/no
    question, and this registry holds 170 of them.
    """
    records = _records_dir(project_root)
    if records is None:
        return {}
    found: dict[str, str] = {}
    for base, suffix in (("plans", "-plan.md"), ("implementations", ".json")):
        directory = records / base
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            name = entry.name.lstrip(".")
            if not entry.is_file() or not name.endswith(suffix):
                continue
            slug = _slug_from_filename(entry.name, suffix)
            item = item_id_of(slug)
            # `item_id_of` upper-cases whatever it cannot parse, so a file with no
            # item number in its name would land here under its own name.
            if item.startswith("B-"):
                found.setdefault(item, slug)
                continue
            # The filename did not carry one. The BODY usually does: a plan realising
            # B-003 and B-011 names them, and reading it costs one file per plan.
            #
            # Measured on a consumer 2026-09-18: two plans, `composition-di-plan.md` and
            # `ci-coverage-plan.md`, neither carrying an item number in its name, and 37
            # of the stream's 38 events invisible on the board because of it. The owner
            # opened the page while a review was ending READY_TO_MERGE_WITH_FOLLOWUPS and
            # saw no work at all.
            #
            # `item_id_of`'s own docstring records the smaller version of this from an
            # earlier run and fixed it by teaching one more filename shape. A third
            # pattern would postpone the next occurrence rather than end it; the body is
            # where the link actually lives.
            for cited in _items_cited_in(entry):
                found.setdefault(cited, slug)
    return found


def _items_cited_in(path: Path) -> list[str]:
    """Every `B-NNN` a plan names in its body, in order of appearance.

    Deliberately not filtered by section or proximity: a plan that mentions an item at
    all is evidence of a link the filename lost, and over-linking shows work on the
    board while under-linking hides it. The two failures are not symmetric.
    """
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return list(dict.fromkeys(_ITEM_CITATION_RE.findall(body)))


def _item_block(project_root: Path, item_id: str) -> str | None:
    """The registry block for one item, or None."""
    backlog = project_root / "BACKLOG.md"
    if not backlog.is_file():
        return None
    body = backlog.read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(rf"^## {re.escape(item_id)} — .*?(?=^## B-|\Z)", body,
                      re.MULTILINE | re.DOTALL)
    return match.group(0) if match else None


def _in_registry(project_root: Path, item_id: str) -> bool:
    """Does `BACKLOG.md` define a block for this id?

    Read through the shared parser rather than a local regex: a second definition of
    the block format would disagree with the first about what the registry contains,
    which is the defect the index exists to expose.
    """
    backlog = project_root / "BACKLOG.md"
    if not backlog.is_file():
        return False
    try:
        return any(i.item_id == item_id for i in _parse_items(backlog.read_text(encoding="utf-8")))
    except OSError:
        return False


def _detail_plan_phases(out: dict, records: Path | None, slug: str | None) -> None:
    """the plan's own phases, and the tasks under them

    Extracted from `item_detail`, which measured cyclomatic complexity 44 across 180
    lines holding six independent readings of one item. Pure code movement: the block
    below is the block that was there. Each fills its own keys on `out`, which is what
    it did before — through a shared scope rather than through an argument.
    """
    # ── the plan's own phases, and the tasks under them ────────────────────
    if slug:
        plan = records / "plans" / f"{slug}-plan.md"
        if plan.is_file():
            body = plan.read_text(encoding="utf-8", errors="replace")
            out["phases"] = [
                {"key": m.group(1).strip(), "title": m.group(2).strip()}
                for m in re.finditer(r"^##+\s*(?:Phase|Fase)\s*([0-9]+)\s*[:—-]\s*(.+?)\s*$",
                                     body, re.MULTILINE)
            ]

        progress = records / "implementations" / f".progress-{slug}.json"
        if progress.is_file():
            try:
                data = json.loads(progress.read_text(encoding="utf-8", errors="replace"))
                for task in data.get("tasks", []):
                    out["tasks"].append({
                        "id": task.get("id"),
                        "phase": str(task.get("phase", "")),
                        "status": task.get("status", "unknown"),
                        "files": task.get("files") or [],
                        "iterations": task.get("iterations_used"),
                        "commit": task.get("commit_sha"),
                    })
            except (json.JSONDecodeError, OSError):
                pass

        # ── what each phase left on disk ──────────────────────────────────
        seen: set[str] = set()
        for phase, base in _ARTEFACT_DIRS:
            directory = records / base
            if not directory.is_dir():
                continue
            for entry in sorted(directory.glob(f"*{slug}*")):
                if not entry.is_file() or entry.name.startswith("."):
                    continue
                rel = str(entry.relative_to(records.parent))
                if rel in seen:
                    continue
                seen.add(rel)
                out["artefacts"].append({
                    "phase": phase, "path": rel, "name": entry.name,
                    "bytes": entry.stat().st_size,
                })


def _detail_halt_report(out: dict, records: Path | None, slug: str | None) -> None:
    """a phase that halted and wrote down why

    Extracted from `item_detail`, which measured cyclomatic complexity 44 across 180
    lines holding six independent readings of one item. Pure code movement: the block
    below is the block that was there. Each fills its own keys on `out`, which is what
    it did before — through a shared scope rather than through an argument.
    """
    # ── a phase that halted and wrote down why ────────────────────────────
    # `/implement` writes `{slug}-BLOCKED.md` when it stops and needs a person. That
    # file is the phase's own statement of what holds the item — stronger evidence
    # than a verdict token, and the only one that says WHY.
    #
    # Measured on 2026-08-31: B-033 had such a report, naming three pre-existing test
    # failures it cannot fix and three paths for a sponsor to choose between. The
    # board listed the file among seven artefacts and said nothing. The item sat for
    # 85 minutes waiting for a person while the page showed a verdict token.
    if slug:
        for base in ("implementations", "reviews", "releases"):
            report = records / base / f"{slug}-BLOCKED.md"
            if report.is_file():
                first = ""
                for line in report.read_text(encoding="utf-8", errors="replace").splitlines():
                    stripped = line.strip()
                    # The report's own one-line reason, not a summary invented here.
                    if stripped.startswith("**Emitted by:**"):
                        first = stripped[len("**Emitted by:**"):].strip()
                        break
                out["halted"] = {
                    "phase": _PHASE_OF_DIR.get(base, base),
                    "path": str(report.relative_to(records.parent)),
                    "reason": first,
                    "at": _iso(report.stat().st_mtime),
                }
                break


def _detail_attestation_drift(out: dict, records: Path | None, slug: str | None) -> None:
    """was the plan changed after it was attested?

    Extracted from `item_detail`, which measured cyclomatic complexity 44 across 180
    lines holding six independent readings of one item. Pure code movement: the block
    below is the block that was there. Each fills its own keys on `out`, which is what
    it did before — through a shared scope rather than through an argument.
    """
    # ── was the plan changed after it was attested? ───────────────────────
    # The implementation record states the sha it was built against. If the plan on
    # disk hashes to something else, the work was done against a plan that has since
    # moved — which is exactly what attesting exists to catch, and nothing was
    # catching it. B-033: attested 4c7ae5d5…, plan now 88e243ab….
    if slug:
        impl = records / "implementations" / f"{slug}-implementation.md"
        plan_file = records / "plans" / f"{slug}-plan.md"
        if impl.is_file() and plan_file.is_file():
            match = re.search(r"\*\*Attest sha:\*\*\s*`?([0-9a-f]{16,})`?",
                              impl.read_text(encoding="utf-8", errors="replace"))
            if match:
                current = hashlib.sha256(plan_file.read_bytes()).hexdigest()
                out["attest"] = {
                    "attested": match.group(1),
                    "current": current,
                    "drifted": match.group(1) != current,
                }


def _detail_progress(out: dict) -> None:
    """how much of the plan is finished

    Extracted from `item_detail`, which measured cyclomatic complexity 44 across 180
    lines holding six independent readings of one item. Pure code movement: the block
    below is the block that was there. Each fills its own keys on `out`, which is what
    it did before — through a shared scope rather than through an argument.
    """
    # ── how much of the plan is finished ──────────────────────────────────
    # Counted from task status, which is the only place that knows. `committed` is the
    # terminal one this repository writes; the others are treated as not-done rather
    # than guessed at, because a status nobody has seen must not round up.
    if out["tasks"]:
        done = sum(1 for t in out["tasks"] if t["status"] in _DONE_TASK_STATUS)
        out["done_ratio"] = round(done / len(out["tasks"]), 3)


def _detail_owner(out: dict, project_root: Path, item_id: str) -> None:
    """who owns this work

    Extracted from `item_detail`, which measured cyclomatic complexity 44 across 180
    lines holding six independent readings of one item. Pure code movement: the block
    below is the block that was there. Each fills its own keys on `out`, which is what
    it did before — through a shared scope rather than through an argument.
    """
    # ── who owns this work ────────────────────────────────────────────────
    # The item's `domain` routes to a specialist, and that file is the closest thing
    # to a name. It is the ASSIGNED specialist, not proof of who ran the last command:
    # nothing in the stream carries an author, and inventing one from the session that
    # happens to be open would be a guess dressed as a record.
    block = _item_block(project_root, item_id)
    if block:
        match = re.search(r"^domain:\s*(\S+)\s*$", block, re.MULTILINE)
        if match:
            out["domain"] = match.group(1)
            for base in (".claude/agents", "agents"):
                candidate = project_root / base / f"{match.group(1)}.md"
                if candidate.is_file():
                    out["specialist"] = f"{base}/{match.group(1)}.md"
                    break


def _detail_verdicts(out: dict, project_root: Path, item_id: str, blocking: frozenset[str] | None) -> None:
    """every verdict, not only the last

    Extracted from `item_detail`, which measured cyclomatic complexity 44 across 180
    lines holding six independent readings of one item. Pure code movement: the block
    below is the block that was there. Each fills its own keys on `out`, which is what
    it did before — through a shared scope rather than through an argument.
    """
    # ── every verdict, not only the last ──────────────────────────────────
    # The board's card shows one. This item ended `code-quality` ten times, and a
    # single FAIL_SOFT hides that it was iterating rather than advancing.
    for event in read_events(project_root):
        if event.get("type") != "cycle:phase:end":
            continue
        if item_id_of(event.get("slug") or "") != item_id:
            continue
        verdict = event.get("verdict")
        out["verdicts"].append({
            "phase": event.get("cycle"), "verdict": verdict, "at": event.get("timestamp"),
        })
        if verdict and blocking is not None and verdict.upper() in blocking:
            out["blocking"].append({"phase": event.get("cycle"), "verdict": verdict,
                                    "at": event.get("timestamp")})

    # Only the LAST blocking verdict per phase still applies: an earlier INVALID that a
    # later run cleared is history, and listing it would report a gate that is open.
    latest: dict[str, dict] = {}
    for entry in out["blocking"]:
        latest[entry["phase"]] = entry
    still_blocking = []
    for phase, entry in latest.items():
        last_for_phase = [v for v in out["verdicts"] if v["phase"] == phase]
        last = last_for_phase[-1]["verdict"] if last_for_phase else None
        if last and last.upper() in blocking:
            still_blocking.append(entry)
    out["blocking"] = still_blocking
    return out


def item_detail(project_root: Path, item_id: str) -> dict:
    """Everything the cycle left behind for one item.

    Loaded on demand rather than folded into the board: one registry here carries 167
    items, and reading every plan and every progress file to render a column of cards
    would spend the whole page budget on work nobody asked to see.
    """
    records = _records_dir(project_root)
    out: dict = {"id": item_id, "slug": None, "phases": [], "tasks": [],
                 "artefacts": [], "verdicts": [], "blocking": [],
                 "done_ratio": None, "specialist": None, "domain": None,
                 "halted": None, "attest": None,
                 # Whether the REGISTRY carries this id at all. Without it the shape
                 # above is returned for an id nobody ever filed, and a caller cannot
                 # tell "no records yet" from "no such item" — the two states this
                 # board exists to keep apart, since it draws position by evidence and
                 # labels derived what it inferred.
                 "in_registry": _in_registry(project_root, item_id)}

    # Determined BEFORE the early return below. Whether the blocking-verdicts rule could
    # be read has nothing to do with whether this item has records, and a reader of the
    # early-return payload sees the same empty `blocking` list — which renders as "no
    # gate is holding this item" rather than as "the rule was not found".
    blocking = blocking_verdicts(project_root)
    if blocking is None:
        out["blocking_unknown"] = (
            f"no {_VERDICTS_RULE} under {project_root} — whether a verdict holds this "
            f"item was not determined")

    if records is None:
        return out

    slug = _slug_for(item_id, records)
    out["slug"] = slug

    _detail_plan_phases(out, records, slug)
    _detail_halt_report(out, records, slug)
    _detail_attestation_drift(out, records, slug)
    _detail_progress(out)
    _detail_owner(out, project_root, item_id)
    _detail_verdicts(out, project_root, item_id, blocking)

    return out


def read_lead(log_path: Path | None, marker_path: Path | None) -> dict:
    """What the supervisor decided, and whether the executing session is moving.

    This exists because of a question that had no answer on the board: the session had
    handed its turn back and sat still for two hours, and the only way to find out was
    to attach to a tmux pane and read it. A board that shows every item and not whether
    anything is working shows the shape of the work and not its state.

    Both sources are optional. A board with no supervisor is the normal case — the
    fields come back empty rather than absent, so the page renders one way.
    """
    out: dict = {"decisions": [], "idle_seconds": None, "watching": False}

    if marker_path is not None and marker_path.exists():
        out["watching"] = True
        try:
            out["idle_seconds"] = max(0, int(time.time() - marker_path.stat().st_mtime))
        except OSError:
            pass

    if log_path is None or not log_path.is_file():
        return out
    entries = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    decisions = list(reversed(entries))

    # A stall the session already recovered from is history, not news. It stays in the
    # log — that file is the audit trail and nothing is removed from it — but the board
    # answers "what is true now", and a resolved stall shown beside a live decision
    # says the opposite of the truth.
    #
    # Recovered is measured, not guessed: the session's own marker moved recently
    # enough that the lead would no longer call it stalled. When the idle time is
    # unknown, the stall is kept — dropping it would be asserting a recovery nobody
    # observed.
    idle = out["idle_seconds"]
    if idle is not None and idle < _STALL_HORIZON_SECONDS:
        decisions = [d for d in decisions if d.get("event") != "stalled"]

    # Newest first: the question is always "what just happened", never "what happened
    # first". Capped because a long-running lead's log outgrows a page.
    out["decisions"] = decisions[:12]
    return out


def _closes(open_phase: dict | None, ended: str) -> bool:
    """Does an end for `ended` close this open start?

    Same phase, or one further along `PHASES`. An end for an earlier phase is a trailing
    event; an item whose LATER phase finished has demonstrably left the one it opened,
    whatever the stream failed to say about leaving it.

    A phase outside `PHASES` closes nothing: an unknown cycle is not evidence of order.
    """
    if not open_phase:
        return False
    started = open_phase.get("phase") or ""
    if started == ended:
        return True
    order = list(PHASES)
    if started not in order or ended not in order:
        return False
    return order.index(ended) >= order.index(started)


#: Which ITEM is being worked on, and what makes that claim true.
#:
#: Two sources, in order of strength. A phase that started and has not ended is the
#: cycle saying so itself. Failing that, a commit whose message names an item is the
#: author saying so — weaker, because a commit is finished work rather than work under
#: way, but it is evidence and it is dated.
#:
#: `why` travels with the answer so the page never shows a highlight a reader cannot
#: check. And `None` is a real answer: measured on a consumer 2026-09-16, the session
#: had sixteen unpushed commits and NOT ONE of the twelve most recent named a backlog
#: item. There was no item being worked on — the work was real and none of it was
#: backlog work. A board that guessed one from the busiest column would have invented
#: the one fact the owner was asking for.
_ITEM_IN_TEXT = re.compile(r"\b([A-Z]-\d{2,})\b")
#: `type(B-069): subject` — the scope slot of a conventional commit.
#:
#: Read, but not relied on. A consumer's own `contribution-overrides.txt` records that
#: **the scope is the AREA, not the item**, so a commit spelling an id there is a
#: violation of the convention rather than an instance of it. Measured 2026-09-16: of
#: that session's sixteen commits, ZERO put an id in the scope — they are `fix(quality)`,
#: `fix(security)`, `style(<a package>)`. A reader tied to this slot alone would report
#: quieter registry the better the convention took hold, which is this kit's own finding
#: about lists-instead-of-properties arriving at its own mechanism.
_COMMIT_SCOPE = re.compile(r"^[a-z]+\(([A-Z]-\d{2,})\)!?:")

#: `Refs B-069` / `Closes B-069` on its own line in the body — a TRAILER.
#:
#: The slot that survives the convention above: unbounded, structured, and not competing
#: with the scope for meaning. Anchored to the start of a line and to a small set of
#: verbs, which is what keeps it a position rather than prose — the same sentence
#: mentioning the id mid-paragraph does not match.
_COMMIT_TRAILER = re.compile(
    r"^\s*(?:refs?|closes?|fixes|item|part-of)\s*[: ]\s*([A-Z]-\d{2,})\b",
    re.IGNORECASE | re.MULTILINE)


def _working_item(items: list[dict], project_root: Path) -> dict | None:
    """The item under way, with the evidence for it, or None when nothing supports one."""
    for item in items:
        if item.get("running_phase"):
            return {"item": item["id"], "why": "phase_started",
                    "detail": f"{item['running_phase']} started and has not ended",
                    "since": item.get("running_since")}

    known = {i["id"] for i in items}
    try:
        out = subprocess.run(
            ["git", "log", "-20", "--format=%h\x1f%ct\x1f%s%n%b\x1e"],
            cwd=str(project_root), capture_output=True, text=True, timeout=10,
            check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    for chunk in out.stdout.split("\x1e"):
        if "\x1f" not in chunk:
            continue
        sha, _, rest = chunk.strip().partition("\x1f")
        when, _, message = rest.partition("\x1f")
        # The SUBJECT only. A body cannot tell you what is being worked on, because any
        # prose mention looks exactly like work.
        #
        # Two drafts failed here, each one narrower than the last and both wrong. The
        # first took any id anywhere and picked B-001 out of "four debts that pointed at
        # a registry nobody gets" — four items mentioned, none of them the subject. The
        # second required exactly one and picked B-069 out of a sentence explaining that
        # `merge(B-069):` had been REFUSED as a commit scope. An example of a rejected
        # message read as a claim of work on the item it named.
        #
        # The subject line is a structured position: `fix(B-069): ...` is an author
        # saying which item this commit belongs to. Prose is not, and no amount of
        # narrowing makes it one.
        subject = message.splitlines()[0] if message.strip() else ""
        # The conventional-commit SCOPE, `type(B-069): …`, and nowhere else.
        #
        # "The subject line is a structured position" was the right idea and the wrong
        # implementation: matching anywhere in the subject is prose again, one line up.
        # `docs(debt): B-001 and B-048 both point at a registry nobody gets` names two
        # items in a sentence, and filtering to the ones this registry knows left
        # exactly one — so the badge would have claimed work on an item the commit was
        # only listing. Fourth narrowing of this reader, and the first that looks at
        # WHERE the id sits rather than how many there are.
        scope = _COMMIT_SCOPE.match(subject)
        named = {scope.group(1)} & known if scope else set()
        if not named:
            # The trailer, which is where the link belongs once the scope names the area.
            # Still exactly one: a body listing several items is discussing them, and
            # that is as true of trailers as it was of prose.
            # COUNT first, filter second. Intersecting with the registry before
            # counting let a commit trailing two items pass whenever only one of them
            # was filed here — the commit is discussing two either way, and what this
            # registry happens to know does not change what its author was doing.
            trailers = {m.group(1) for m in _COMMIT_TRAILER.finditer(message)}
            if len(trailers) == 1 and trailers <= known:
                return {"item": trailers.pop(), "why": "commit",
                        "detail": f"commit {sha} refers to it in a trailer",
                        "since": int(when) if when.isdigit() else None}
        # EXACTLY one, or the commit is discussing items rather than working on one.
        #
        # The first draft took the first id it found anywhere in the message and would
        # have lit a WORKING badge from prose. Measured on a consumer 2026-09-16:
        # `10e463349` names B-001, B-048, B-058 and B-074 in the sentence "four debts
        # that pointed at a registry nobody gets" — four items MENTIONED, none of them
        # the subject of the commit. The badge would have claimed B-001 was under way
        # because it was first in a list of things that were not.
        #
        # Eighth instance this day of a reader matching a pattern inside prose that
        # merely quotes it.
        if len(named) == 1:
            return {"item": named.pop(), "why": "commit",
                    "detail": f"commit {sha} declares it in its scope",
                    "since": int(when) if when.isdigit() else None}
    return None


#: What the repository itself says about whether anyone is working, right now.
#:
#: `read_lead` was written for this question — "the session had handed its turn back and
#: sat still for two hours, and the only way to find out was to attach to a tmux pane" —
#: and it needs a supervisor writing a marker. A board pointed at a repository nobody
#: supervises answers `watching: false` and nothing else.
#:
#: The repository answers it with no infrastructure at all. Measured on a consumer
#: 2026-09-16: the cycle stream had been silent for two hours while the session had
#: fifteen unpushed commits, the newest from minutes earlier. The work was real, visible
#: in git, and invisible on the board — so the page reported a quiet registry and the
#: owner read it as a quiet session.
#:
#: A commit is NOT a phase, and this is reported beside cycle activity rather than mixed
#: into it. Conflating them would let a busy repository make an untouched backlog look
#: like progress, which is the error this board exists to refuse.
#:
#: All three reads together cost ~130ms on a 3000-file repository, which is affordable
#: at the poll interval. Each degrades to None on its own rather than failing the state.
def _repo_activity(project_root: Path) -> dict:
    def git(*args: str) -> str | None:
        try:
            out = subprocess.run(["git", *args], cwd=str(project_root),
                                 capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    head = git("log", "-1", "--format=%h\x1f%s\x1f%ct")
    out: dict = {"head": None, "subject": None, "committed_at": None,
                 "dirty_files": None, "unpushed": None, "branch": git("rev-parse",
                                                                      "--abbrev-ref",
                                                                      "HEAD")}
    if head and "\x1f" in head:
        sha, _, rest = head.partition("\x1f")
        subject, _, when = rest.rpartition("\x1f")
        out["head"] = sha
        out["subject"] = subject
        out["committed_at"] = int(when) if when.isdigit() else None

    # `--untracked-files=no`: an untracked file is not work in progress the way a
    # modified tracked one is, and counting build output as activity would report every
    # repository as busy forever.
    status = git("status", "--porcelain", "--untracked-files=no")
    if status is not None:
        out["dirty_files"] = len([ln for ln in status.splitlines() if ln.strip()])

    ahead = git("rev-list", "--count", "@{upstream}..HEAD")
    if ahead is not None and ahead.isdigit():
        out["unpushed"] = int(ahead)
    return out


def _last_activity(events: list[dict]) -> dict | None:
    """The newest event that names an item, or None when the stream names none.

    None rather than a zero or a placeholder: a stream with no item-attributed event is
    not a cycle that just went quiet, and the page must be able to tell those apart.
    """
    for event in reversed(events):
        slug = item_id_of(event.get("slug") or "")
        if not slug:
            continue
        return {
            "item": slug,
            "at": event.get("timestamp"),
            "cycle": event.get("cycle"),
            "verdict": event.get("verdict"),
            "type": event.get("type"),
        }
    return None


def _wall_owner(wall: str) -> tuple[str, str]:
    """`(owner, class)` for a `blocked_by` line — who can clear it, and what kind it is.

    The board drew seven identical amber cards for seven held items, and the reader's
    real question — *which of these is waiting on ME* — had no answer on screen. On the
    consumer measured 2026-09-18, three of those seven were the queue's own work and
    four needed a person. Reading "7 blocked" as "7 things I must do" is how an owner
    concludes the system is stuck when it is not.

    `delegated_decision.classify_wall` already answers it, against
    `rules/decision-delegation.txt`. This renders what it said and decides nothing: an
    unmatched wall stays `unclassified` and belongs to the person, because
    `on_no_match = retain` is the registry's rule and a view that softened it would be
    claiming a consent nobody gave.

    Returns `("", "")` when the classifier is unavailable — a board that cannot ask must
    not answer, and drawing every wall as the system's would be the worst of the three
    possible wrong answers.
    """
    if not wall or not wall.strip():
        return "", ""
    # `delegated_decision` lives in `mechanisms/cycle/`, which is not on the path a
    # skill script starts with. Located by walking up for the directory rather than by
    # a fixed number of `parents[N]`: the kit sits at the root in its own repository
    # and under `.claude/` in a consumer, and a hardcoded depth is right in exactly one
    # of the two.
    for up in Path(__file__).resolve().parents:
        cycle_dir = up / "mechanisms" / "cycle"
        if cycle_dir.is_dir():
            if str(cycle_dir) not in sys.path:
                sys.path.insert(0, str(cycle_dir))
            break
    try:
        from delegated_decision import classify_wall
    except ImportError:
        return "", ""
    try:
        verdict = classify_wall(wall)
    except Exception:  # noqa: BLE001 — a classifier that raises must not take the board down
        return "", ""
    return ("system" if verdict.delegated else "person"), verdict.klass.value


def _unattributed_work(events: list[dict], known: set[str],
                       plan_slugs: set[str]) -> list[dict]:
    """Stream slugs that match no item, with what the stream says about each.

    A board that silently discards what it cannot place reports an idle system while
    the system is working — this kit's governing defect, rendered in HTML. Measured on
    one consumer 2026-09-18: **37 of 38 events dropped**, the page blank, and a `review`
    phase ending `READY_TO_MERGE_WITH_FOLLOWUPS` at that exact minute.

    Shown rather than resolved, deliberately. An unattributable event is a fact about
    the STREAM — a plan whose name carries no item number, a slug nobody registered —
    and inventing an owner for it would replace a visible gap with an invisible lie.
    What the reader needs is the slug, so they can go and look.
    """
    seen: dict[str, dict] = {}
    for event in events:
        raw = event.get("slug") or ""
        # Attributed two ways, and both count. Either the slug carries the item number
        # in its name (`b003-something`), or it is a plan slug the registry links to an
        # item through the plan's body. Checking only the first is what made a linked
        # plan's work look orphaned.
        if not raw or item_id_of(raw) in known or raw in plan_slugs:
            continue
        entry = seen.setdefault(raw, {
            "slug": raw, "events": 0, "phases": [],
            "last_verdict": None, "last_at": None, "since": event.get("timestamp"),
        })
        entry["events"] += 1
        cycle = event.get("cycle")
        if cycle and cycle not in entry["phases"]:
            entry["phases"].append(cycle)
        # Last write wins: the stream is append-only and ordered, so the final verdict
        # for a slug is the one a reader is asking about.
        if event.get("verdict"):
            entry["last_verdict"] = event["verdict"]
        if event.get("timestamp"):
            entry["last_at"] = event["timestamp"]
    return sorted(seen.values(), key=lambda e: e["last_at"] or "", reverse=True)


#: How long a column may go untouched before it is called stalled rather than queued.
#: Thirty minutes because a phase that is running emits something inside that window —
#: a start, an end, a verdict — so silence past it is silence about work, not a gap
#: between two events. Not a threshold anybody has to tune: it separates two readings
#: of the same fact and both readings are shown.
STALL_AFTER_MINUTES = 30

#: How long a start may stay open before the board stops calling it work.
#:
#: Four hours, not thirty minutes: a phase legitimately runs longer than the stall
#: window — an implement slice can occupy an afternoon — and calling it abandoned
#: because it went quiet would hide the one thing the board exists to show. Past four
#: hours with no end and nothing else on the stream, "still running" is a claim the
#: evidence stopped supporting.
ABANDON_AFTER_HOURS = 4


def _delivery(items: list[dict], events: list[dict], now: datetime) -> dict:
    """Has anything shipped, how fast, and over what window.

    A reader could see ten lanes, eight blockers and a WIP figure and still not answer
    the question the person paying for the work has: *are we delivering?* On one consumer
    the answer was nothing in twenty-two hours — fifteen items, zero shipped — and no
    field said so. Absence read as an empty column, which looks the same as a column
    nobody has reached yet.

    NONE IS NOT ZERO, and the distinction is the point. `0 items/day` is a measurement:
    the system ran and delivered nothing. `None` says nothing has finished yet, which on
    a three-day-old registry is a different and far less alarming fact. Collapsing them
    would make a young project look like a failing one and a failing one look measured.

    `killed` is counted apart. `cycle-backlog.md` is explicit that "killing one is the
    cycle working" — the item leaves the queue and nobody received anything, so folding
    it into delivery would inflate the figure with work that was correctly abandoned.
    """
    shipped = [i for i in items if i.get("status") == "shipped"]
    killed = [i for i in items if i.get("status") == "killed"]

    stamps = sorted(
        t for t in (_parse_stamp(e.get("timestamp")) for e in events) if t is not None)
    window_days = ((stamps[-1] - stamps[0]).total_seconds() / 86400) if len(stamps) > 1 else None

    throughput = None
    if shipped and window_days and window_days > 0:
        throughput = round(len(shipped) / window_days, 2)

    # LEAD TIME, from the date the registry already carried. `registered_on` is a DATE —
    # midnight — and the end is a real timestamp, so the arithmetic is exact and the INPUT
    # is not: every figure carries ±1 day from the start side. Days rather than hours for
    # that reason, and NOT rounded to whole days, which would hide the arithmetic without
    # removing the uncertainty.
    #
    # The end is the item's last recorded event, because half a measurement is not one —
    # an item with an entry date and no event on the stream is not measured rather than
    # measured as zero. `killed` is excluded for the reason it is excluded above: nobody
    # received anything, and timing how long the system took to abandon something is not
    # delivery.
    last_event: dict[str, datetime] = {}
    for e in events:
        slug = str(e.get("slug") or "")
        stamp = _parse_stamp(e.get("timestamp"))
        if slug and stamp and (slug not in last_event or stamp > last_event[slug]):
            last_event[slug] = stamp
    spans: list[float] = []
    for i in shipped:
        raw = i.get("registered_on")
        end = last_event.get(str(i.get("id") or ""))
        if not raw or end is None:
            continue
        try:
            start = datetime.fromisoformat(str(raw)).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        spans.append(round((end - start).total_seconds() / 86400, 2))
    spans.sort()
    p50 = None
    if spans:
        mid = len(spans) // 2
        p50 = spans[mid] if len(spans) % 2 else round((spans[mid - 1] + spans[mid]) / 2, 2)

    return {
        "shipped": len(shipped),
        "killed": len(killed),
        #: Days, not hours — see the note above. None while nothing could be measured,
        #: which is a different fact from a lead time of zero.
        "lead_time_p50_days": p50,
        #: The subset the p50 is over. Most items predate the registration line, so a
        #: median over "the ones that had a date" is a median over a subset, and a number
        #: that travels without its coverage is read as a number about everything.
        "lead_time_measured_over": len(spans),
        "lead_time_terminal_total": len(shipped),
        #: None while nothing has shipped — see the docstring. Never rendered as 0.
        "throughput_per_day": throughput,
        "window_days": round(window_days, 1) if window_days else None,
    }


def _headline(items: list[dict], columns: list[dict], wip: dict) -> dict:
    """One state and one sentence: what a reader with four minutes needs first.

    The page opened with ten lanes and a search box. Everything on it was true and none
    of it was a conclusion, so the reader had to assemble one — count the amber cards,
    notice which lanes had not moved, remember that four items in review with no
    implement event is not ordinary. Somebody who opens a board between meetings does
    not assemble; they read the top line.

    ORDERED BY URGENCY, NOT BY COUNT. The first match wins:

        blocked    something needs a person, and nothing downstream moves until it comes
        at_risk    the record disagrees with itself — work happened that nothing logged
        working    a phase is running right now
        stalled    items are sitting and nobody is on them
        idle       nothing here to do

    One item waiting on a person outranks nine sitting in backlog, because the nine will
    move on their own and the one will not. `idle` on an empty registry is deliberate:
    a page that shouts about having no work trains its reader to ignore the headline.

    Asserts nothing the rest of the page does not already show — every input is a field
    computed above, and the detail names where to look rather than summarising it away.
    """
    needs_person = [i for i in items if i.get("blocked_owner") == "person"]
    gaps = {p for i in items for p in (i.get("phases_without_record") or [])}
    working = [c for c in columns if c["activity"] == "working"]
    stalled = [c for c in columns if c["activity"] == "stalled"]
    live = sum(c["items"] for c in columns)

    if needs_person:
        ids = ", ".join(i["id"] for i in needs_person[:3])
        more = f" and {len(needs_person) - 3} more" if len(needs_person) > 3 else ""
        return {"state": "blocked", "needs_person": len(needs_person),
                "detail": f"{len(needs_person)} item(s) wait on a person — {ids}{more}. "
                          f"Nothing behind them moves until those are answered."}
    stale = (wip or {}).get("abandoned_detail") or []
    if stale and not gaps:
        first = stale[0]
        more = f" and {len(stale) - 1} more" if len(stale) > 1 else ""
        return {"state": "at_risk", "needs_person": 0,
                "detail": f"{first['cycle']} opened on {first['slug']} {first['hours']}h "
                          f"ago and never closed{more} — not counted as work, and the "
                          f"phase owes an end."}
    if gaps:
        named = ", ".join(sorted(gaps))
        return {"state": "at_risk", "needs_person": 0,
                "detail": f"items have moved past {named} with no event on the stream — "
                          f"either those phases ran without emitting, or they were "
                          f"skipped. The record cannot say which."}
    if working:
        where = ", ".join(c["phase"] for c in working)
        flight = wip.get("current") or 0
        return {"state": "working", "needs_person": 0,
                "detail": f"{flight} in flight · {where}"}
    if stalled and live:
        oldest = max((c for c in stalled if c["idle_minutes"] is not None),
                     key=lambda c: c["idle_minutes"], default=None)
        when = (f", longest {round(oldest['idle_minutes'])} min in {oldest['phase']}"
                if oldest else "")
        return {"state": "stalled", "needs_person": 0,
                "detail": f"{live} item(s) sitting and no phase running{when}."}
    return {"state": "idle", "needs_person": 0,
            "detail": "nothing registered to work on."}


def _wip(events: list[dict], now: datetime) -> dict:
    """Items in flight over the window, and the smallest concurrency that kept it fed.

    WIP is not a card count. It is how many items are INSIDE a phase at a moment —
    started and not ended — and it was uncomputable until the emitters recorded starts:
    the stream held 37 ends against 1 start, so every instant read as zero in flight.

    `minimum` answers one question and refuses the others. Over the measured window, it
    is the smallest concurrency at which no idle gap appeared. When the window HAS an
    idle gap there is no such number, and this returns None rather than the lowest
    non-zero level — a system that stopped was not kept fed by any concurrency it ran at,
    and naming one would be an assertion dressed as a measurement.

    It is DERIVED, never prescribed. Four items waiting on a work tenant are not helped
    by starting a fifth, and a figure that implied otherwise would be worse than none.
    `peak` and `observed` travel with it so the reader can judge where it came from.
    """
    spans: list[tuple[datetime, int]] = []
    open_at: dict[tuple[str, str], datetime] = {}
    opened_by: dict[tuple[str, str], dict] = {}
    for event in events:
        slug = event.get("slug") or ""
        cycle = event.get("cycle") or ""
        when = _parse_stamp(event.get("timestamp"))
        if not slug or not cycle or when is None:
            continue
        key = (item_id_of(slug), cycle)
        if event.get("type") == "cycle:phase:start":
            open_at[key] = when
            opened_by[key] = {"slug": slug, "cycle": cycle, "at": when}
            spans.append((when, +1))
        elif event.get("type") == "cycle:phase:end" and key in open_at:
            del open_at[key]
            opened_by.pop(key, None)
            spans.append((when, -1))

    # A start older than the window is not work in flight. It is a phase that died
    # without emitting its end, and counting it as WIP makes the figure grow
    # monotonically as lanes die — the opposite of what it measures.
    #
    # `_phases_running` already learned this: "B-001 opened `plan` on 09-12 and never
    # closed it… Four days later the board still reported `running plan`, and the owner
    # read the column as where the work was." This pass counted raw starts and did not
    # inherit it. Measured 2026-09-18: a `brainstorm` opened 22 hours earlier held the
    # board at "1 in flight" while no item was being worked at all.
    abandoned = []
    for key, opened in sorted(opened_by.items()):
        # `_abandoned`, not a second age computation. This pass and `_phases_running`
        # both decide "is this start still work", and computing it twice is how the
        # headline and the notices panel came to disagree about B-184.
        if not _abandoned(opened["at"], now):
            continue
        age_hours = (now - opened["at"]).total_seconds() / 3600
        abandoned.append({"slug": opened["slug"], "cycle": opened["cycle"],
                          "hours": round(age_hours, 1)})
        # Withdraw its +1 so neither `current` nor `peak` carries it. Removing the span
        # rather than adding a -1: a phantom close would put a fake drop on the series
        # and invent an idle gap that never happened.
        for i, (when, delta) in enumerate(spans):
            if delta == +1 and when == opened["at"]:
                spans.pop(i)
                break

    if not spans:
        # No start ever reached the stream. Absence, never zero-in-flight: the two look
        # identical in a number and mean opposite things about the system.
        return {"measured": False, "current": 0, "peak": 0, "minimum": None,
                "idle_gaps": 0, "observed": [], "abandoned": len(abandoned),
                "abandoned_detail": abandoned}

    spans.sort(key=lambda p: p[0])
    level = 0
    peak = 0
    seen: set[int] = set()
    idle_gaps = 0
    for i, (_, delta) in enumerate(spans):
        level += delta
        peak = max(peak, level)
        seen.add(level)
        # A drop to zero with more work after it is a window where the system stopped
        # and then started again. The final drop to zero is not a gap — it is now.
        if level == 0 and i < len(spans) - 1:
            idle_gaps += 1

    observed = sorted(x for x in seen if x > 0)
    return {
        "measured": True,
        "current": level,
        "peak": peak,
        #: None when the window idled: no concurrency it ran at avoided stopping.
        "minimum": (observed[0] if observed else None) if idle_gaps == 0 else None,
        "idle_gaps": idle_gaps,
        "observed": observed,
        #: Starts the stream never closed and that are too old to be work. Named, not
        #: just counted: the reader's next move is to close them, which needs the slug.
        "abandoned": len(abandoned),
        "abandoned_detail": abandoned,
    }


def _parse_stamp(raw) -> datetime | None:
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _columns(items: list[dict], phases: tuple[str, ...] | list[str],
             uncarded: list[dict], now: datetime) -> list[dict]:
    """Per phase: how many items sit there, and whether anything is happening.

    The board drew ten lanes and left the reader to infer activity from card count. On
    one consumer that inference was wrong in the direction that matters — `plan` held
    four cards and nothing had touched them in over two hours. "There is work in plan"
    and "plan is where the work is" are different claims, and the page supported only
    the first while looking like it supported the second.

        working   a phase started here and has not ended, OR uncarded work moved recently
        queued    items here, none running, something moved inside the stall window
        stalled   items here, none running, nothing moved — or nothing ever did
        empty     no items and no uncarded work

    Undated counts as stalled, never as fresh: an item the stream has never mentioned has
    not just moved, and treating "never" as "recently" would mark a registry nobody has
    touched as a queue in flight.
    """
    orphan_by_phase: dict[str, list[dict]] = {}
    for entry in uncarded:
        for phase in entry.get("phases") or []:
            orphan_by_phase.setdefault(phase, []).append(entry)

    out: list[dict] = []
    for phase in phases:
        here = [i for i in items if i.get("phase") == phase]
        orphans = orphan_by_phase.get(phase, [])
        running = sum(1 for i in here if i.get("running_phase") == phase)

        ages = [_minutes_since(i.get("last_at"), now) for i in here]
        dated = [a for a in ages if a is not None]
        orphan_ages = [_minutes_since(o.get("last_at"), now) for o in orphans]
        fresh_orphan = any(a is not None and a <= STALL_AFTER_MINUTES for a in orphan_ages)

        if running or fresh_orphan:
            activity = "working"
        elif not here and not orphans:
            activity = "empty"
        elif dated and min(dated) <= STALL_AFTER_MINUTES:
            activity = "queued"
        else:
            activity = "stalled"

        out.append({
            "phase": phase,
            "activity": activity,
            "items": len(here),
            "running": running,
            #: Work the stream records in this phase under no item. Counted separately
            #: because it is real and belongs to nobody — hiding it is what made the
            #: board report an idle system while the system was working.
            "uncarded": len(orphans),
            #: Minutes since anything here last moved; None when nothing ever has.
            #: None is NOT zero, and the page must not render it as recent.
            "idle_minutes": round(min(dated)) if dated else None,
        })
    return out


def _minutes_since(stamp: str | None, now: datetime) -> float | None:
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (now - when).total_seconds() / 60)


def _fan_out_by_plan(events: list[dict], plans: dict[str, str]) -> list[dict]:
    """Every event, plus a copy addressed to each item its plan slug realises.

    `planned_items` learned to read the plan body, so the board knows B-003's plan is
    `composition-di`. The stream passes carry the link no further: they resolve a slug
    through `item_id_of`, which sees no item number in `composition-di` and drops all
    twenty-two of its events. The visible symptom is a card that cannot say when it last
    moved — and "how long has this been sitting" is the difference between a queue moving
    and a queue stopped.

    Copies rather than rewrites: one plan can realise several items and each of them is
    genuinely at that phase. Rewriting the slug would pick one and silently orphan the
    rest, which is the shape of the defect this whole review started from.
    """
    if not plans:
        return events
    by_slug: dict[str, list[str]] = {}
    for item, slug in plans.items():
        by_slug.setdefault(slug, []).append(item)
    out: list[dict] = []
    for event in events:
        out.append(event)
        raw = event.get("slug") or ""
        if item_id_of(raw).startswith("B-"):
            continue          # already addressed to an item; nothing to fan out
        for item in by_slug.get(raw, ()):
            out.append({**event, "slug": item})
    return out


def _abandoned(since, now: datetime) -> bool:
    """Whether a start that old has stopped being evidence of work.

    One predicate, used by everything that has to make this call. `_wip` computed the
    same age inline and `_working_item` never computed it at all — which is how the two
    came to disagree about B-184 on one screen.

    An unparseable or absent stamp is NOT abandoned: the window is a claim about
    elapsed time, and without a time there is nothing to elapse. Guessing `True` would
    silently drop real work whose timestamp a producer wrote badly.
    """
    started = _parse_stamp(since)
    if started is None:
        return False
    return (now - started).total_seconds() / 3600 > ABANDON_AFTER_HOURS


def _phases_running(events: list[dict], now: datetime | None = None) -> dict[str, dict]:
    """Which item is inside which phase right now, from the event stream.

    Extracted from `build_state`, which measured cyclomatic complexity 41 across 206
    lines. Pure code movement: the block below is the block that was there, reading the
    same stream. What changed is that each pass declares what it reads and what it
    produces, instead of leaving both in a shared scope.

    ## The window is applied HERE, and that placement is the fix

    A start with no end is a fact about the STREAM; calling it running is a claim about
    the WORK. Two defences against that claim already existed and both sat in consumers:
    the orphan-close below, and `ABANDON_AFTER_HOURS` inside `_wip`. Neither covered
    `_working_item`, and on 2026-09-21 a consumer's board headlined `WORKING B-184` over
    a start that had died 20 hours and 26 events earlier — while its own notices panel
    said the same start was "not counted as work in flight".

    Eleven readers consume `running_phase`: two here and nine in `board.html`. Any of
    them could have been the fourth to miss the lesson. So a start past the window is
    not reported as running to ANY of them — the field is built without it, and no
    consumer can disagree about a value none of them is given.
    """
    now = now or datetime.now(timezone.utc)
    running: dict[str, dict] = {}
    for event in events:
        slug = item_id_of(event.get("slug") or "")
        cycle = event.get("cycle") or ""
        if not slug or cycle not in PHASES:
            continue
        if event.get("type") == "cycle:phase:start":
            running[slug] = {"phase": cycle, "since": event.get("timestamp")}
        elif event.get("type") == "cycle:phase:end" and _closes(running.get(slug), cycle):
            # An end closes an open start when it names the SAME phase or one FURTHER
            # ALONG the chain, and not when it names an earlier one.
            #
            # A lane that stops without emitting its own end leaves a start hanging, and
            # the item then goes on to finish LATER phases — which is proof it moved on,
            # whatever the stream failed to say about the phase it left. Requiring the
            # matching cycle meant the board kept drawing the abandoned one as live work.
            #
            # Measured on a consumer 2026-09-16: B-001 opened `plan` on 09-12 and never
            # closed it, then ended `code-quality` on 09-14, 09-15 and again that
            # morning. Four days later the board still reported `running plan`, and the
            # owner read the column as where the work was. Seventeen events for that item
            # and the page named the one phase none of them had finished.
            #
            # A start with no end is a fact about the STREAM. Drawing it as running is a
            # claim about the WORK, and the two stop agreeing the moment a lane dies.
            #
            # The first attempt closed on ANY later end, and a sibling test refused it
            # for a case that is genuinely different: `implement` starts, then a trailing
            # `plan` end arrives. An end for an EARLIER phase is an event catching up,
            # not evidence the item moved on, and clearing on it would hide work actually
            # in flight. Later-or-equal is the line, and the chain order is what decides.
            running.pop(slug, None)
    # Past the window, a start is not work. `_wip` reports it under `abandoned` so the
    # reader's next move — close it, or emit the end it owes — still has the slug.
    for slug in [s for s, open_phase in running.items()
                 if _abandoned(open_phase.get("since"), now)]:
        running.pop(slug, None)

    # Last finished phase per item, from the stream.
    return running


def _phases_reached(events: list[dict]) -> dict[str, dict]:
    """Last FINISHED phase per item, from the same stream.

    Extracted from `build_state`, which measured cyclomatic complexity 41 across 206
    lines. Pure code movement: the block below is the block that was there, reading the
    same stream. What changed is that each pass declares what it reads and what it
    produces, instead of leaving both in a shared scope.
    """
    reached: dict[str, dict] = {}
    for event in events:
        slug = item_id_of(event.get("slug") or "")
        cycle = event.get("cycle") or ""
        if not slug or cycle not in PHASES or event.get("type") != "cycle:phase:end":
            continue
        if cycle in PHASES:
            # The LAST phase observed, not the furthest one. "Furthest wins" assumes the
            # cycle only moves forward, and it does not: a plan that review rejects goes
            # back, and an implementation that fails its own gate is worked again.
            #
            # Measured on 2026-08-31: an item's last event was `implement FAIL` at
            # 16:36:01 and the board showed `code-quality`, because code-quality sits
            # later in the sequence. The operator asked whether that was right. It was
            # not — the item had gone back, and hiding that is the same defect as
            # predicting the next phase, one step removed.
            #
            # The stream is append-only, so file order is chronological.
            reached[slug] = {"phase": cycle, "verdict": event.get("verdict"),
                             "at": event.get("timestamp")}

    return reached


#: Phases whose absence is never an item's gap.
#:
#: `brainstorm` and `design` belong to a SCOPE, not to an item — `cycle-phases.txt`
#: marks both "absent for a scope aligned in an earlier session, and for a repo that
#: adopted the kit before this phase existed". Every item in such a repository would
#: carry both as findings, on two phases that were correctly never run for it.
#:
#: `backlog` is where an item is registered rather than worked, and a registry holding
#: the item is its own evidence. Flagging it would fire on every item ever filed.
_NOT_PER_ITEM = frozenset({"brainstorm", "design", "backlog"})


def _phases_recorded(events: list[dict]) -> dict[str, set[str]]:
    """Which chain phases the stream has an event for, per item."""
    seen: dict[str, set[str]] = {}
    for event in events:
        slug = item_id_of(event.get("slug") or "")
        cycle = event.get("cycle") or ""
        if slug.startswith("B-") and cycle in PHASES:
            seen.setdefault(slug, set()).add(cycle)
    return seen


def _gaps_behind(phase: str, recorded: set[str]) -> list[str]:
    """Chain phases BEHIND this item that the stream never recorded.

    `rules/cycle-phases.txt` states the dependency in its own column — *"review |
    conditional | absent when implement never ran"* — and the board drew an item in
    review with no implement event as an ordinary card. On one consumer four items sat
    there while the stream held no implement, plan, backlog, release or acceptance event
    at all, and 53 lines of TypeScript on disk said code had been written.
    "Four items are in review" and "four items are in review and the phase that produces
    what review reads left no trace" are different sentences, and only the page could
    tell the reader which one was true.

    Phases AHEAD are never flagged: one the item has not reached is not a gap, and
    flagging them would turn every card into a wall of findings nobody reads.

    This reports what the STREAM shows and says so in those words. A conditional phase
    can be legitimately absent — implement is "absent for a killed item, and for an item
    whose fix is documentation only" — and nothing here can tell that from a phase that
    ran and emitted nothing. Both are worth surfacing; neither is called a defect.
    """
    if phase not in PHASES:
        return []
    behind = PHASES[:PHASES.index(phase)]
    return [p for p in behind if p not in recorded and p not in _NOT_PER_ITEM]


def _board_items(items: list, statuses: dict, running: dict, reached: dict,
                 plans: set, halted: set, on_disk: dict,
                 recorded: dict[str, set[str]] | None = None) -> list[dict]:
    """One row per registry item: its status, its phase, and what holds it.

    Extracted from `build_state`, which measured cyclomatic complexity 41 across 206
    lines. Pure code movement: the block below is the block that was there, reading the
    same stream. What changed is that each pass declares what it reads and what it
    produces, instead of leaving both in a shared scope.
    """
    out_items: list[dict] = []
    out_items = []
    for item in items:
        iid = item.item_id
        status = item.fields.get("status", "")
        # `_parse_items` already reads `Registrado|registered YYYY-MM-DD` into this, and
        # this function dropped it — so `_delivery` measured lead time against a field it
        # could not see and reported None with a comment saying the item had no entry
        # date. It had one, two calls up.
        registered_on = item.registered_on.isoformat() if item.registered_on else None
        raw_block = item.fields.get("blocked_by", "")
        blockers = parse_blocked_by(raw_block)
        live = [b for b in blockers if statuses.get(b, "") in OPEN_STATUS]
        # `bool(...)`, because `and` yields its last truthy operand: without it the
        # field carried the blocker LIST where the contract says boolean. The page
        # happened to work — a non-empty array is truthy in JS — which is the kind of
        # accident that survives until someone reads the JSON and believes the type.
        impeded = bool(status in OPEN_STATUS and declares_impediment(raw_block)
                       and (live or not blockers))

        # NOT `live`: that name already holds this item's live blockers a few lines up,
        # and shadowing it silently emptied every `blockers` list on the board.
        in_flight = running.get(iid)
        hit = reached.get(iid)
        if in_flight:
            # Observed: a phase started and has not ended.
            phase, source = in_flight["phase"], "running"
        elif hit:
            # Observed: a phase ENDED. The item is drawn there, not in the one after.
            #
            # It used to advance to the next phase, and that was a prediction dressed as
            # a fact. Measured on 2026-08-31: an item had sixteen events, all `end`, with
            # `code-quality` appearing TEN times — it was iterating against that gate,
            # not moving past it. The board put it in `review`, which it had never
            # entered, and the operator read the column as where the work was.
            #
            # Ending a phase is a fact; entering the next one is a guess, and a board
            # that guesses is a board nobody can check against reality.
            phase, source = hit["phase"], "stream"
        elif on_disk.get(iid) and status in ("approved", "planned"):
            # A record on disk beats a status nobody advanced. `position_from` says
            # `disk` rather than `derived`, so a reader can tell a position read off a
            # file from one inferred from a status field.
            #
            # `disk` and not `records`: `check_write_containment` reserves that literal
            # for `squad/paths.py`, and it refused this line — correctly. A bare
            # "records" in a module that also builds paths is ambiguous to any scan, and
            # the gate cannot know this one was a label. Sixth time it has caught this
            # hand; the shorter word is also the more accurate one here.
            phase, source = on_disk[iid], "disk"
        else:
            phase = STATUS_PHASE.get(status, "backlog")
            source = "derived"

        out_items.append({
            "id": iid,
            "registered_on": registered_on,
            # The phase being worked on NOW, if any.
            "running_phase": (in_flight or {}).get("phase"),
            "running_since": (in_flight or {}).get("since"),
            "title": item.title,
            "status": status,
            "phase": phase,
            "position_from": source,
            "blocked": impeded,
            "blockers": live,
            "blocked_note": raw_block.strip() if impeded and not live else "",
            #: Who can clear it, and the class the delegation file puts it in. Empty
            #: when nothing is in the way, so a card with no blocker draws no chip.
            #: Chain phases behind this one with no event on the stream. Named rather
            #: than counted: "implement" tells the reader what to go and look at.
            "phases_without_record": _gaps_behind(
                phase, (recorded or {}).get(iid, set())),
            "blocked_owner": _wall_owner(raw_block)[0] if impeded else "",
            "blocked_class": _wall_owner(raw_block)[1] if impeded else "",
            "domain": item.fields.get("domain", ""),
            "repo": item.fields.get("repo", ""),
            "evidence": item.fields.get("evidence", ""),
            "last_verdict": (hit or {}).get("verdict"),
            "last_at": (hit or {}).get("at"),
            # Present only when a plan for this item exists on disk. It is what makes
            # the implementation view a measurement: an item with no plan has no
            # steps to show, and inventing a placeholder would be a drawing of a
            # process rather than a report of one.
            "plan_slug": plans.get(iid),
            # A phase stopped here and said so in writing.
            "halted": iid in halted,
        })

    return out_items


def build_state(project_root: Path, lead_log: Path | None = None,
                lead_marker: Path | None = None) -> dict:
    backlog = project_root / "BACKLOG.md"
    if not backlog.is_file():
        return {"error": f"no BACKLOG.md under {project_root}", "items": [],
                "phases": list(PHASES), "phases_source": PHASES_SOURCE,
                "lead": read_lead(lead_log, lead_marker)}

    items = _parse_items(backlog.read_text(encoding="utf-8-sig"))
    statuses = {i.item_id: i.fields.get("status", "") for i in items}
    events = read_events(project_root)
    plans = planned_items(project_root)
    halted = halted_items(project_root)
    on_disk = stage_on_disk(project_root)

    # A phase that STARTED and has not ended is work happening right now. Without it
    # the board can only draw what finished, which is a picture of the past: an item
    # under active work showed the verdict of a phase that was already over, and
    # nothing on the page said anything was running.
    # Fanned out first: an event under a plan slug belongs to every item that plan
    # realises, and both passes below key on the item.
    addressed = _fan_out_by_plan(events, plans)
    running = _phases_running(addressed)
    reached = _phases_reached(addressed)
    out_items = _board_items(items, statuses, running, reached, plans, halted, on_disk,
                             _phases_recorded(addressed))

    # ── what the stream carries and this board cannot place ──────────────
    # Measured on 2026-08-31 against theo: 3 of 28 events had `slug: null` and two
    # more named cycles outside the declared chain. All five were dropped in silence.
    # A board that discards an eighth of its evidence without saying so is reporting
    # a stream it did not read — the same defect as predicting a phase, one step
    # earlier in the pipeline.
    unplaced_no_item = 0
    unplaced_off_chain: dict[str, int] = {}
    # Starts count too. A phase that BEGAN and cannot be placed is work the board
    # shows nobody doing — `idea-to-release` opened on this stream and no card moved.
    for event in events:
        if event.get("type") not in ("cycle:phase:start", "cycle:phase:end"):
            continue
        raw = event.get("slug") or ""
        slug = item_id_of(raw)
        cycle = event.get("cycle") or ""
        # A plan slug the registry links to an item through the plan's body IS placed —
        # the card for that item carries it. Counting it as unplaced made the page warn
        # about 38 of 38 events while 36 of them had a home, which teaches the reader
        # that the warning means nothing.
        if (not slug or not slug.startswith("B-")) and raw not in set(plans.values()):
            unplaced_no_item += 1
        elif cycle not in PHASES:
            unplaced_off_chain[cycle] = unplaced_off_chain.get(cycle, 0) + 1

    out_items.sort(key=lambda d: _number(d["id"]))
    unattributed = _unattributed_work(
        events, {d["id"] for d in out_items}, set(plans.values()))
    _now = datetime.now(timezone.utc)
    columns = _columns(out_items, PHASES, unattributed, _now)
    wip = _wip(addressed, _now)
    return {
        "project": project_root.name,
        "project_path": str(project_root),
        "phases": list(PHASES),
        #: `declared` when `rules/cycle-phases.txt` was read, `fallback` when it was not
        #: found and the eight hardcoded names are being drawn instead. A board drawn
        #: from a chain nobody read looks exactly like one drawn from the contract.
        "phases_source": PHASES_SOURCE,
        "items": out_items,
        "events": events[-200:],
        "event_total": len(events),
        "lead": read_lead(lead_log, lead_marker),
        "running": sorted(running.keys()),
        "has_stream": _events_path(project_root) is not None,
        #: Work the stream records under a slug that resolves to no item. NEVER empty
        #: for convenience: an empty list is the claim that every event on the stream
        #: found its item, and it has to be true.
        "unattributed": unattributed,
        #: One row per phase, in chain order, saying whether work is happening there.
        "columns": columns,
        #: Items in flight, and the smallest concurrency the window shows kept the
        #: system fed. Derived from start/end pairs — never a limit, never advice.
        "wip": wip,
        #: One state and one sentence, first thing on the page.
        "headline": _headline(out_items, columns, wip),
        #: Has anything shipped, how fast, over what window.
        "delivery": _delivery(out_items, events, _now),
        #: When the cycle last did something to an ITEM, and what it was.
        #:
        #: The board drew positions and never said WHEN. A registry four days idle and
        #: one working this minute rendered identically, so "where is each item" was
        #: answerable and "is anything happening" was not — and the second is the
        #: question someone opens a live board to ask.
        #:
        #: Item-attributed deliberately. Measured on a consumer 2026-09-16: 369 events,
        #: of which 223 named no item. Counting those as activity would let a run that
        #: touched nothing report the cycle as busy, which is the same error as a gate
        #: passing on a sweep that examined nothing.
        "last_activity": _last_activity(events),
        #: The repository's own pulse, beside the cycle's. Two different questions:
        #: "has the cycle moved an item" and "is anyone working in this tree at all".
        "repo": _repo_activity(project_root),
        #: The item under way and the evidence for it, or null when nothing supports
        #: one. Never guessed from a column count.
        "working": _working_item(out_items, project_root),
        "unplaced": {
            "without_item": unplaced_no_item,
            "off_chain": dict(sorted(unplaced_off_chain.items())),
        },
    }


def _number(item_id: str) -> int:
    match = re.search(r"(\d+)", item_id)
    return int(match.group(1)) if match else 1 << 30


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(build_state(root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

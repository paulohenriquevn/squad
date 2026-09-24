"""The one place that knows where this project's data lives.

    from squad.paths import records_dir, wiki_dir, write_records_dir

## The rule

**Everything the system writes goes under `<project>/.squad/`.** Nothing else. The
kit itself is an installed dependency and stays where the installer put it; `.squad/`
holds only what the system PRODUCES, and nothing executes from it.

That separation is what makes the versioning question answerable at all. Until
2026-09-09 the kit wrote its output into `.claude/` — the same directory that holds the
installed plugin — so a project could not un-version the dependency without also
un-versioning its own decision records. Measured across 20 consumer repositories: 17
had the kit committed, every one of them carried between 348 and 566 permanently dirty
files, and every one of those files was inside `.claude/`. Nothing outside it was dirty
anywhere. A `git status` nobody can read is a `git status` nobody reads.

## Why the two kinds stay apart INSIDE `.squad/`

`records/` is the dated trail; `wiki/` is the OKF bundle of durable knowledge. That
split is argued in `rules/records-location.md` and enforced by
`check_wiki_migration.py`, and centralising the root must not collapse it: a reader
looking for a decision and a reader looking for what happened on a Tuesday want
different things, and mixing them is the failure that split was written about.

## Readers fall back; writers never do

A consumer that updates the kit without migrating keeps working, because readers
resolve `.squad/` first and then the legacy roots in order. Writers only ever produce
`.squad/`. That asymmetry is the whole migration strategy — the same one the
`wiki/` bundle already used — and it exists because **the kit cannot run anything
inside another project's repository.** It reports; a person moves.

## Why every literal lives here

Six modules held their own copy of this list, in four different orders, and a reader
resolving one order found a directory a writer using another had never filled.
`check_write_containment.py` now fails any kit file outside this module that names a
data root, so the copies cannot come back. One owner, or the drift returns silently.
"""
from __future__ import annotations

import re
from pathlib import Path

#: The single write root. A folder, under the project, holding only produced data.
DATA_DIRNAME = ".squad"

#: The dated trail and the durable bundle, kept apart inside the one root.
RECORDS = "records"
WIKI = "wiki"

#: Session state the system writes and later reads back. These used to sit beside the
#: installed kit — `<eco>/session-state/`, `<project>/.attestations/` — which is the
#: same mixing the trail suffered: machine-written state inside the dependency's
#: directory. They are named here so `check_write_containment.py` can police them.
SESSION_STATE = "session-state"
SNAPSHOTS = "compaction-snapshots"
ATTESTATIONS = "attestations"
ACTIVE_PLAN = "active-plan"

#: Bytecode is SUPPRESSED rather than relocated, via `PYTHONDONTWRITEBYTECODE` in
#: `settings.plugin.json`. Python writes `__pycache__/` NEXT TO the source, and the
#: kit's source lives in the consumer's `.claude/` — so running any mechanism wrote
#: into the dependency. Measured in a clean sandbox: eight `.pyc` files after four
#: commands.
#:
#: `PYTHONPYCACHEPREFIX` would MOVE the cache here instead of losing it, and was the
#: first choice. It takes a path, and the only way to spell "this project" in a
#: `settings.json` env block is `${CLAUDE_PROJECT_DIR}` — which the hooks expand
#: because a shell runs them, and which nothing was verified to expand in `env`. An
#: unexpanded value would create a directory literally named `${CLAUDE_PROJECT_DIR}`,
#: which is worse than the problem.
#:
#: The cost of suppressing is what made the choice cheap. Measured over five runs of
#: `check_panel_capability.py`: 415 ms/run with a warm cache, 360 ms without one —
#: inside the noise. On the heaviest import in the kit: 314 ms against 339 ms.
#: The names these state files carried when they sat beside the installed kit. Kept so
#: `check_write_containment.py` can police them and a migration can find them — a
#: legacy name nobody names is a legacy name nobody moves.
LEGACY_STATE_NAMES: tuple[str, ...] = (
    ".compaction-snapshots", ".attestations", ".active_plan", "session-state",
)

#: Read-only fallbacks, in resolution order, for a project that has not migrated.
#: `.claude/` first because that is where a plugin install used to write, then the
#: bare names for the standalone layout, then the pre-2026-08 `knowledge-base` name.
LEGACY_RECORDS_ROOTS: tuple[str, ...] = (
    ".claude/records", "records", ".claude/knowledge-base", "knowledge-base",
)
LEGACY_WIKI_ROOTS: tuple[str, ...] = (".claude/wiki", "wiki")

#: What the bundle calls a leaf, mapped to where the dated trail used to keep it.
DURABLE_LEAVES: dict[str, str] = {
    "sops": "sops",
    "decisions": "adrs",
    "references": "references",
    "opportunities": "discoveries/opportunities",
}


def is_cycle_generated_skill(name: str) -> bool:
    """A skill the CYCLES wrote, not a phase anybody maintains.

    `/review` emits `review-{slug}-{role}-knowledge` per reviewer, per run. These
    are output. Asking one for a row in the kit's map, a cycle contract, or an
    `SOP.md` asks an artifact to behave like an input.

    It lives HERE, with the rest of what this kit knows about its own produced
    data, because it has been hoisted once already and the hoist was not far
    enough. `check_xrefs.py` pulled it out of an inline check after a first
    version exempted `no_orphan_skills` and left `skill_has_cycle_contract`
    charging — 26 WARN traded for 3, which looked like a fix. Its docstring closed
    with "One definition, two consumers: that is what stops the next half from
    escaping." A third sweep, `check_skill_map.py`, never learned it, and warned
    about this exact shape in its own prose while doing it: measured on a consumer
    2026-09-18, 13 `missing_from_map` plus `missing_sop` and a disagreeing count,
    every finding about a file `/review` had just written. The only exemption on
    offer was a hand-maintained list, so the remedy was to re-list after every
    review what the kit generates by itself.

    Two consumers inside one directory was the ceiling. From here a fourth sweep
    inherits the answer rather than re-deriving it.

    `*-sepa-knowledge` is BACKWARD COMPATIBILITY and has no producer any more.
    `/implement` generated one per plan until 2026-09-01 and now routes to the
    project's own domain specialist. The pattern stays because consumers still
    hold what was written to their disks, and dropping it would turn those files
    into orphans and fail repositories that did nothing wrong. Remove it once no
    consumer carries one.
    """
    return name.endswith("-knowledge") and (name.startswith("review-")
                                            or "-sepa-" in name)


def data_root(project_root: Path | str) -> Path:
    """`<project>/.squad` — where every write goes, whether or not it exists yet."""
    return Path(project_root) / DATA_DIRNAME


#: What may appear in a path segment built from a CLI argument. Deliberately narrow:
#: a slug is an item id or a plan name, and a phase is a word from `cycle-phases.txt`.
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


class UnsafeSegment(ValueError):
    """A CLI string was going to become part of a path and is not a single safe name."""


def safe_segment(value: str, *, what: str) -> str:
    """`value`, or a refusal naming what was wrong with it.

    Four mechanisms built a filename by interpolating `--slug` and `--phase` straight
    into an f-string and then `mkdir -p`'d the parent: `convene_panel.assignment_path`,
    `cast_vote`, `critic_round` and the record writer beside them. A slug containing
    `../` escaped the write root and CREATED the directories on the way, so a mechanism
    whose whole contract is "everything this system writes goes under `.squad/`" wrote
    outside the tree it owns. `.` and `..` are refused by name: both match the character
    class and neither is a filename.
    """
    if not value or not _SAFE_SEGMENT.match(value) or value in (".", ".."):
        raise UnsafeSegment(
            f"{what} must be a single name of letters, digits, dot, dash or underscore "
            f"— got {value!r}. It becomes part of a path, and `../` in one is how a "
            f"writer leaves the write root.")
    return value


def confined(path: Path, root: Path, *, what: str) -> Path:
    """`path`, once it is proved to resolve inside `root`.

    The second half of the same guard. `safe_segment` refuses the spelling; this refuses
    the RESULT, so a future caller composing segments some other way is still held.
    """
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise UnsafeSegment(f"{what} resolves to {resolved}, outside {root}")
    return path


def write_records_dir(project_root: Path | str, leaf: str = "") -> Path:
    """Where a dated artifact is WRITTEN. Never falls back, never guesses."""
    base = data_root(project_root) / RECORDS
    return base / leaf if leaf else base


def write_wiki_dir(project_root: Path | str, leaf: str = "") -> Path:
    """Where durable knowledge is WRITTEN. Never falls back, never guesses."""
    base = data_root(project_root) / WIKI
    return base / leaf if leaf else base


def write_state_dir(project_root: Path | str, leaf: str) -> Path:
    """Where session state is WRITTEN: `<project>/.squad/<leaf>`.

    Directly under the root rather than inside `records/`, because it is neither a
    dated artifact nor durable knowledge — it is what one session leaves for the next,
    and filing it as a record would put working state into the audit trail.
    """
    return data_root(project_root) / leaf


def lead_log_path(project_root: Path | str) -> Path:
    """Where a fleet's lead writes its decisions, scoped to the PROJECT it leads.

    The default was `/tmp/squad-lead.jsonl`, spelled identically in three places, so two
    fleets on one machine wrote their decisions into ONE file and every reader — the
    board's lead panel, `fleet_idle`, `fleet_status` — saw them interleaved.

    Not hypothetical. Measured on this machine 2026-09-16: two sessions writing one
    `/tmp/<short-name>.log` from their push wrappers, and one of them read the OTHER's
    push output — different repository, different SHAs, same filename — and reported it
    as its own for a turn. What caught it was checking the claim against the repository
    instead of against the log.

    A lead log belongs to a project the way records do, so it lives beside them. `LOG=`
    still overrides for anyone who wants it elsewhere.
    """
    return data_root(project_root) / "lead.jsonl"


def assignment_log_path(project_root: Path | str) -> Path:
    """Where the router records which unit is held by which lane, scoped to the PROJECT.

    The default was `~/.squad-fleet/assignments.jsonl`, which is scoped to the MACHINE.
    Every `fleet_supervisor.sh --project X` and `--project Y` on one host replayed and
    appended to the same file, and `in_flight()` keys the held set by unit slug alone —
    so `B-014` in one consumer and `B-014` in another are one key. A unit held in one
    project therefore read as held in the other, and the second fleet skipped work that
    nothing was doing.

    Same failure and same fix as `lead_log_path` above, one file along. `--log` still
    overrides for anyone who wants it elsewhere.
    """
    return data_root(project_root) / "assignments.jsonl"


#: The active sprint's record. One name, one place, for the same reason as the plan
#: pointer: a second spelling of a data-root path is a second answer to where state lives.
SPRINT_RECORD = "sprint.md"


def sprint_record(project_root: Path | str) -> Path:
    """The file naming the active block of work, its goal, and what it admitted.

    Directly under the data root rather than in `records/`, because it is what one
    session leaves for the next rather than a dated artifact — the same argument
    `write_state_dir` makes. It becomes a record only when it CLOSES, and the closing
    verdicts are what make it worth keeping.
    """
    return data_root(project_root) / SPRINT_RECORD


def active_plan_pointer(project_root: Path | str) -> Path:
    """The file naming which plan is active. One name, one place."""
    return data_root(project_root) / ACTIVE_PLAN


def active_plan_candidates(project_root: Path | str) -> list[Path]:
    """Where to LOOK for the active-plan pointer, canonical first, then legacy.

    A reader — the status line, most visibly — has to try the old name too, or a
    project that has not migrated shows no plan while a plan is active. Those old
    names are data-root literals, and `check_write_containment.py` fails any kit file
    outside this module that spells one. That is the rule working: the shell had
    `.active_plan` typed into it, which is exactly the second spelling this module
    exists to prevent. So the LIST is published here and the reader iterates it.
    """
    root = Path(project_root)
    candidates = [active_plan_pointer(root)]
    for name in LEGACY_STATE_NAMES:
        if name == ACTIVE_PLAN or name.lstrip(".").replace("_", "-") == ACTIVE_PLAN:
            candidates.append(root / name)
    return candidates


def plans_dir_candidates(project_root: Path | str) -> list[Path]:
    """Where to LOOK for written plans, canonical first, then the legacy roots."""
    root = Path(project_root)
    return [write_records_dir(root, "plans"),
            *(root / base / "plans" for base in LEGACY_RECORDS_ROOTS)]


#: The routing table: which repositories exist here, and who owns each. DERIVED by
#: `detect_domains.py` and read by `route_domain.py`, so it is PRODUCED data and
#: belongs under the write root with everything else the system makes.
#:
#: It lived in `<eco>/rules/` because that is where the kit keeps configuration a
#: project may edit, and `install.sh` learned to preserve it there across reinstalls.
#: But nothing outside this kit reads it — measured 2026-09-10 across every `.json`,
#: `.yml`, `.yaml` and `.toml` in the tree: zero references. A file only the kit reads
#: and only the kit writes is not configuration for a tool; it is our own output, and
#: keeping it inside the dependency is what made `.claude/` un-deletable.
ROUTING_TABLE = "domain-routing.txt"

#: Read-only fallbacks for the table, newest first. Readers fall back, writers never
#: do — the same rule the wiki migration follows, for the same reason: the kit cannot
#: run anything inside another project's repository, so a hard cut breaks every
#: consumer that updates without migrating.
LEGACY_ROUTING_ROOTS: tuple[str, ...] = (".claude/rules", "rules")


#: The two places a rules directory can be, in the ONE order this module declares.
#: Exported because some readers iterate the BASES rather than asking for a directory —
#: the file they want may live in either — and a second spelling of this pair is the
#: defect `rules_dir` was written to remove.
RULE_BASES: tuple[str, ...] = (".claude/rules", "rules")


def rules_dir(project_root: Path | str) -> Path | None:
    """Where this project's rule tables are READ from, or None when there are none.

    ONE order, declared once. Nine sites resolved this pair by hand and they disagreed:
    six tried `("rules", ".claude/rules")` and three tried `(".claude/rules", "rules")`.
    In a plugin install BOTH directories exist — `.claude/rules/` is the installed kit's
    and `rules/` may be the project's own — so the same question got two answers
    depending on which module asked it, and a table edited in one was invisible to half
    the readers.

    `.claude/rules` wins, for the case where the disagreement is observable: in a
    consumer, the kit's tables are the ones under `.claude/`. In the kit's own checkout
    only `rules/` exists and the order never comes up. This matches `LEGACY_ROUTING_ROOTS`
    above, which settled the same question for the routing table first.
    """
    root = Path(project_root)
    for relative in RULE_BASES:
        candidate = root / relative
        if candidate.is_dir():
            return candidate
    return None


def write_routing_table(project_root: Path | str) -> Path:
    """Where the derived routing table is WRITTEN. Never falls back."""
    return data_root(project_root) / ROUTING_TABLE


def routing_table(project_root: Path | str) -> Path | None:
    """The table to READ: the write root first, then where installs used to keep it."""
    root = Path(project_root)
    primary = write_routing_table(root)
    if primary.is_file():
        return primary
    for relative in LEGACY_ROUTING_ROOTS:
        candidate = root / relative / ROUTING_TABLE
        if candidate.is_file():
            return candidate
    return None


def _first_existing(project_root: Path, roots: tuple[str, ...], leaf: str) -> Path | None:
    for relative in roots:
        candidate = project_root / relative / leaf if leaf else project_root / relative
        if candidate.is_dir():
            return candidate
    return None


def records_dir(project_root: Path | str, leaf: str = "") -> Path | None:
    """Where this project's dated trail for `leaf` actually is, or None.

    `.squad/` first, then the legacy roots. A consumer that has not migrated keeps
    working; one that has never reads a stale copy, because the new root wins.
    """
    root = Path(project_root)
    current = write_records_dir(root, leaf)
    if current.is_dir():
        return current
    return _first_existing(root, LEGACY_RECORDS_ROOTS, leaf)


def wiki_dir(project_root: Path | str, leaf: str = "") -> Path | None:
    """Where this project's durable bundle for `leaf` actually is, or None."""
    root = Path(project_root)
    current = write_wiki_dir(root, leaf)
    if current.is_dir():
        return current
    return _first_existing(root, LEGACY_WIKI_ROOTS, leaf)


#: Where a project keeps documents PEOPLE wrote, versioned with the product. Distinct
#: from the write root on purpose, and kept a separate function rather than a third
#: entry in `LEGACY_WIKI_ROOTS`: making it a fallback of `wiki_dir()` would put authored
#: documents and run output back behind one name, which is the ambiguity the 2026-09-21
#: move removed.
AUTHORED_WIKI_ROOT = "docs/wiki"


def authored_wiki_dir(project_root: Path | str, leaf: str = "") -> Path | None:
    """The project's AUTHORED bundle for `leaf`, or None when it keeps none.

    WHY THIS IS NOT `wiki_dir`. `wiki_dir` answers from `.squad/`, the write root — what
    a cycle produced for this project. This answers from `docs/wiki/`, where a person
    sat down and wrote something that ships with the product.

    The kit is the case that made the distinction necessary: it is itself a product, so
    its eleven ADRs and SOPs are authored documents, and they lived in the write root
    until 2026-09-21 on the argument that "this kit's durable knowledge IS its source".
    The argument was true and the location taught, by example, that writing authored
    documents into a consumer's write root was normal.

    A project with no `docs/wiki/` gets None, which is not an error: most projects keep
    no authored bundle, and their `.squad/wiki/` is the only one they have.
    """
    root = Path(project_root)
    candidate = root / AUTHORED_WIKI_ROOT
    if leaf:
        candidate = candidate / leaf
    return candidate if candidate.is_dir() else None


def resolve_knowledge_dir(project_root: Path | str, leaf: str) -> Path | None:
    """Where this project's `leaf` knowledge lives — bundle first, then the trail.

    A leaf outside `DURABLE_LEAVES` never resolves to the bundle. Accepting
    `wiki/sop-runs/` because someone created it would invite exactly the mixing the
    split exists to prevent.
    """
    root = Path(project_root)
    legacy_leaf = DURABLE_LEAVES.get(leaf)
    if legacy_leaf is None:
        return records_dir(root, leaf)
    found = wiki_dir(root, leaf)
    return found if found is not None else records_dir(root, legacy_leaf)


def contains(project_root: Path | str, path: Path | str) -> bool:
    """Is `path` inside this project's write root?

    The question `check_write_containment.py` asks of a real run, and the reason
    `data_root` is a function rather than a constant a caller may join by hand.
    """
    try:
        Path(path).resolve().relative_to(data_root(project_root).resolve())
    except ValueError:
        return False
    return True

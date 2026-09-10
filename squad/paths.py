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


def data_root(project_root: Path | str) -> Path:
    """`<project>/.squad` — where every write goes, whether or not it exists yet."""
    return Path(project_root) / DATA_DIRNAME


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


def active_plan_pointer(project_root: Path | str) -> Path:
    """The file naming which plan is active. One name, one place."""
    return data_root(project_root) / ACTIVE_PLAN


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


def legacy_data_dirs(project_root: Path | str) -> list[Path]:
    """Legacy roots this project still has on disk, for a migration to report.

    Nothing here moves them. A migration the kit performed inside a consumer's
    repository would be the kit writing to a project it does not own.
    """
    root = Path(project_root)
    seen: list[Path] = []
    for relative in (*LEGACY_RECORDS_ROOTS, *LEGACY_WIKI_ROOTS):
        candidate = root / relative
        if candidate.is_dir() and candidate not in seen:
            seen.append(candidate)
    return seen


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

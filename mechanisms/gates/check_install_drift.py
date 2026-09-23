#!/usr/bin/env python3
"""Has a consumer's install drifted from this kit, and which way?

WHY THIS EXISTS
---------------
Twenty-two fixes to this kit lived for weeks inside one consumer's gitignored `.claude/` install
and nowhere else. Nobody hid them. Nothing looked. They surfaced only because someone diffed the
two trees by hand, and the diff took an afternoon to classify.

`sync_consumers.py` answers the other direction — "is the consumer behind the kit" — and refuses
to auto-merge a `LOCAL_CHANGE`. That refusal is right, and it is also where the work went to die:
a file the script correctly declined to overwrite is a file whose improvement nobody carried back.

So this reports the direction the other script cannot, and it fails when there is unharvested work,
because a report nobody is required to read is a report that goes unread.

WHAT IT COMPARES, AND WHY NOT A DIFF
------------------------------------
Line SETS, ignoring blank lines. The question is not "are these byte-identical" — they stop being
that the moment a comment is reworded — but "does one side hold work the other lacks".

    IDENTICAL       the same non-blank lines, in any arrangement
    INSTALL_AHEAD   the install holds lines the kit does not; the kit holds none the install lacks
    KIT_AHEAD       the mirror image
    DIVERGED        BOTH hold unique lines

DIVERGED is the only class that needs a human, and it is the class a blind copy destroys. Measured
on `run_code_quality.py`: copying the install over the kit would have deleted 's
zero-detector check, the one fix that had already made it home.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not merge, and it does not rank. A file where a comment was reworded reads as INSTALL_AHEAD
exactly like a file where a bug was fixed, because from a line set the two are indistinguishable —
saying otherwise would be a guess wearing a verdict's clothes.

`only_in_kit` is reported and never fails the run: a consumer missing a file is simply a consumer
that has not reinstalled, which is `sync_consumers.py`'s question.
"""
from __future__ import annotations

import argparse
import enum
import subprocess
import sys

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import Path as _Path_bootstrap

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
)


class Drift(enum.Enum):
    IDENTICAL = "identical"
    INSTALL_AHEAD = "install_ahead"
    KIT_AHEAD = "kit_ahead"
    DIVERGED = "diverged"
    #: The install carries content the kit ONCE HAD. It is behind, not modified —
    #: and a `git checkout` of the kit resolves it without losing anything.
    STALE = "stale"
    #: The consumer's own file, which the kit ships a starting point for and the
    #: project then tunes. A difference here is the SYSTEM WORKING, not drift.
    #:
    #: `squad/boundaries.py` declares these — `rules/*.txt`, `agents/`, `settings.json`
    #: — and says why: "a consumer tunes these and the installer preserves them across
    #: an update." This gate did not ask, and reported all six of a real consumer's
    #: configured files as needing a human: its language table, its allowlist, its
    #: domain routing, its acceptance target. Measured 2026-09-16.
    #:
    #: An alarm that fires on the normal case is an alarm people scroll past — which is
    #: this kit's own sentence, about a different gate, in `verify_ecosystem`.
    YOURS = "yours"


def _lines(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {line for line in text.split("\n") if line.strip()}


def _historical_contents(kit_root: Path, rel: str) -> set[str] | None:
    """Every content this path has ever had in the kit's history.

    Without asking this, a consumer installed from an older version shows up as
    local work in every file the kit has evolved since. Measured on an adopter:
    11 files reported as "need a human", of which 4 were merely older kit versions
    — `install.sh`, `check_xrefs.py`, `code-quality-golden-rule.md` and
    `code-quality-allowlist.txt`. The lesson was already in `sync_consumers` (231
    false `local-change` became 119) and was not here.
    """
    try:
        listed = subprocess.run(
            ["git", "-C", str(kit_root), "rev-list", "--all", "--", rel],
            capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        # None, not `set()`. An empty set makes `body in history` false for every body,
        # so a git failure reclassified every stale file as "needs a human" — the exact
        # false-positive class this function was written to remove. The caller now tells
        # "no history" from "could not ask".
        print(f"check_install_drift: could not read the history of {rel}: {exc}. "
              f"Whether this file is an older kit version was NOT determined.",
              file=sys.stderr)
        return None
    if listed.returncode != 0:
        print(f"check_install_drift: `git rev-list` exited {listed.returncode} for {rel}: "
              f"{(listed.stderr or '').strip()[:160]}. Staleness NOT determined.",
              file=sys.stderr)
        return None

    revisions = listed.stdout.split()
    if not revisions:
        return set()

    # ONE process for every revision, not one process PER revision. `git show` was spawned
    # in a loop with no cap and no early exit, so a file with forty revisions cost forty
    # processes — per file, per consumer. `cat-file --batch` reads the same blobs over a
    # single pipe.
    request = "\n".join(f"{revision}:{rel}" for revision in revisions) + "\n"
    try:
        batch = subprocess.run(
            ["git", "-C", str(kit_root), "cat-file", "--batch"],
            input=request, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"check_install_drift: could not read the blobs of {rel}: {exc}. "
              f"Staleness NOT determined.", file=sys.stderr)
        return None

    return _blobs_from_batch(batch.stdout)


def _blobs_from_batch(stream: str) -> set[str]:
    """The contents in a `git cat-file --batch` answer.

    Each object arrives as `<sha> <type> <size>\n<size bytes>\n`; a missing one as
    `<name> missing\n`. Parsed by the declared size rather than by scanning for the next
    header, because a blob may contain a line that looks exactly like one.
    """
    contents: set[str] = set()
    at = 0
    while at < len(stream):
        end_of_header = stream.find("\n", at)
        if end_of_header == -1:
            break
        header = stream[at:end_of_header]
        at = end_of_header + 1
        parts = header.split()
        if len(parts) != 3 or parts[1] != "blob":
            continue  # `missing`, or an object that is not a blob
        try:
            size = int(parts[2])
        except ValueError:
            continue
        contents.add(stream[at:at + size])
        at += size + 1  # the trailing newline git adds after the payload
    return contents


def _is_project_owned(rel: str) -> bool:
    """Through `squad.boundaries`, which is where ownership is declared.

    A local copy of that list is what `check_write_containment` refuses for data roots
    and what this kit has removed from three readers today. False on ImportError rather
    than a second implementation: reporting a tuned file as drift is noise, and guessing
    ownership without the declaration is worse.
    """
    try:
        from squad.boundaries import PROJECT_OWNED
    except ImportError:
        return False
    if not any(pattern.search(rel) for pattern in PROJECT_OWNED):
        return False
    # `agents/` is EXCLUDED here, and that exclusion is a finding rather than a
    # preference. `boundaries.PROJECT_OWNED` calls the whole directory the consumer's;
    # `tests/test_install_drift_scope.py` asserts `agents/README.md` belongs to the kit
    # because it describes the routing mechanism; and `install.sh` says why both are
    # right — "`agents/` carries BOTH: the kit's four roles and the project's domain
    # specialists", with the MANIFEST as the discriminator.
    #
    # `is_project_owned` uses the manifest for `skills/` and not for `agents/`. Which
    # reader should change is a decision about the ownership contract, and resolving it
    # from inside a drift gate would be the fourth reader of that question inventing an
    # answer. So this narrows to what was measured — the six `rules/*.txt` files a real
    # consumer had tuned — and leaves `agents/` reported exactly as before.
    return not rel.startswith("agents/")


def classify_file(install_file: Path, kit_file: Path,
                  kit_root: Path | None = None, rel: str | None = None) -> Drift:
    """Which side, if either, holds lines the other lacks."""
    a, b = _lines(install_file), _lines(kit_file)
    install_only, kit_only = a - b, b - a
    if not install_only and not kit_only:
        return Drift.IDENTICAL
    # Ask the one declaration of ownership before calling a difference drift. Two
    # mechanisms answering "whose file is this" is how they come to disagree, and this
    # one was not asking at all.
    if rel and _is_project_owned(rel):
        return Drift.YOURS
    verdict = Drift.DIVERGED if (install_only and kit_only) else (
        Drift.INSTALL_AHEAD if install_only else Drift.KIT_AHEAD)
    if verdict in (Drift.DIVERGED, Drift.INSTALL_AHEAD) and kit_root is not None and rel:
        try:
            body = install_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return verdict
        history = _historical_contents(kit_root, rel)
        if history is None:
            # Could not ask. The verdict stands as it was — reporting STALE would claim a
            # match nothing found, and reporting the default silently would hide that the
            # question went unanswered. The reason is already on stderr.
            return verdict
        if body in history:
            return Drift.STALE
    return verdict


# Directories a consumer generates for itself. They are that project's artifacts, not kit code,
# and reporting them would bury the signal under 38 rows of noise (measured on an adopter).
#: Directories neither side is expected to match on. `records/` is the cycle's
#: data and `.benchmarks/` is a consumer's; the rest are tool caches.
#:
#: The cache list MUST agree with `KIT_EXCLUDES` in `install.sh` — files the
#: installer refuses to copy cannot be missing from an install in any meaningful
#: sense, and reporting them fills the report with noise nobody reads. Measured
#: on 2026-09-02, right after the scope was widened to all six trees: 43 of 64
#: only-in-kit entries were `.ruff_cache/`, `.hypothesis/` and `.mypy_cache/`
#: files. Two thirds of a report whose own docstring says "a report nobody is
#: required to read is a report that goes unread".
#:
#: `test_install_drift_scope.py` fails when the two lists disagree — fourth time
#: in one day that a rule lived in one file and was missing from another.
_CACHE_DIRS = ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
               ".hypothesis")
#: `.git` joined on 2026-09-17. When `_installed_scope` returns None the walk covers the
#: whole install root, and a target whose `.claude/` is itself a repository — a consumer
#: that versions its install — had every object under `.git/` walked and reported as a
#: consumer-local file. Thousands of rows, and the signal underneath them invisible.
_CONSUMER_LOCAL = (*_CACHE_DIRS, ".git", ".benchmarks", DATA_DIRNAME, *LEGACY_RECORDS_ROOTS)

#: Files that belong to the PROJECT even while living in a directory the kit also has.
#: `agents/<domain>.md` describes the consumer's repository — harvesting it into the kit
#: is the opposite of what it is (grill kit-domain-agents-install, decision 5). The
#: `README.md` stays in scope: it describes the routing mechanism, not a domain.
def _is_consumer_owned(rel: str) -> bool:
    parts = Path(rel).parts
    return len(parts) == 2 and parts[0] == "agents" and parts[1] != "README.md"


#: The consumer receives `settings.plugin.json` AS `settings.json` — the kit's own
#: `settings.json` is the development one, with different hook paths. Comparing the two
#: reports DIVERGED on every install, forever. Measured on `speculative`: identical as
#: JSON, reported as divergent.
_INSTALL_TO_KIT_ALIAS = {"settings.json": "settings.plugin.json"}


#: What `install.sh` actually carries into a consumer, and therefore the only
#: thing a drift report between the two roots should compare.
#:
#: The default used to be `skills/` alone, which is where the noise is lowest and
#: also where four of the six trees became invisible. Measured on 2026-09-02: two
#: mechanisms the kit had and the consumer did not — `kit_issues.py` and
#: `session_ready.py` — sat undetected, because nothing looked outside `skills/`.
#: Widening it to the whole root is the other failure: that reports 5994 files
#: only-in-kit, since the kit also holds tests, wiki, images and study material
#: that no consumer ever receives.
INSTALLED_TREES = ("skills", "rules", "hooks", "commands", "mechanisms", "squad")

#: `agents/` is not a tree the kit owns (a domain specialist describes the
#: project), but the routing README inside it is.
INSTALLED_FILES = ("agents/README.md",)


def _installed_scope(root: Path) -> tuple[str, ...] | None:
    """The trees to compare under `root`, or None to compare everything.

    None is for the case where `root` IS one of the trees — `--kit ./rules`
    against a consumer's `rules/`. Restricting then would match nothing and
    report a clean sweep over an empty comparison, which is the exact shape of
    defect this file exists to catch.
    """
    present = tuple(t for t in INSTALLED_TREES if (root / t).is_dir())
    return present or None


def _relevant(root: Path, scope: tuple[str, ...] | None = None) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _CONSUMER_LOCAL for part in rel.parts):
            continue
        if _is_consumer_owned(str(rel)):
            continue
        if scope is not None and rel.parts[0] not in scope \
                and str(rel) not in INSTALLED_FILES:
            continue
        found[str(rel)] = path
    return found


@dataclass
class DriftReport:
    counts: dict[Drift, int] = field(default_factory=dict)
    by_class: dict[Drift, list[str]] = field(default_factory=dict)
    only_in_install: list[str] = field(default_factory=list)
    only_in_kit: list[str] = field(default_factory=list)
    _kit_dirs: frozenset[str] = frozenset()

    @property
    def unharvested_files(self) -> list[str]:
        """Install-only files sitting in a directory this repository ALSO has.

        The distinction is what keeps the check readable. 's `_layout.py` and
        `bump_version.py` were whole files present in one tree only, under `implement/scripts/`
        and `release/scripts/` — directories the kit has — and missing them would have cost three
        items. Whereas `review-b052-…-knowledge/` is a directory the kit does not have at all,
        because the CONSUMER generates one per review; there were 38 of them, and failing on those
        would make this red on every project that runs /review. A check that is always red is a
        check nobody reads.
        """
        return [
            rel for rel in self.only_in_install
            if str(Path(rel).parent) in self._kit_dirs
        ]

    @property
    def consumer_local_files(self) -> list[str]:
        """Install-only files in a directory this repository does NOT have.

        The complement of `unharvested_files` within `only_in_install`, and the
        bucket a project's own work falls into: a push gate it wrote, a directory
        `/review` generates per run. The kit has no business harvesting either.

        This was computed as a COUNT at the print site and the paths discarded
        (kit#33). A consumer's `hooks/delivery-gate.sh` was deleted three times by
        cleanups of `.claude/`; the classification was already right each time and
        had nowhere to be read. `--consumer-local` is where it is read now.
        """
        unharvested = set(self.unharvested_files)
        return [rel for rel in self.only_in_install if rel not in unharvested]

    @property
    def needs_attention(self) -> bool:
        """The install holds work this repository does not."""
        return bool(
            self.counts.get(Drift.INSTALL_AHEAD)
            or self.counts.get(Drift.DIVERGED)
            or self.unharvested_files
        )


def scan(install_root: Path, kit_root: Path) -> DriftReport:
    # The scope comes from the KIT side: it is the kit that decides which trees
    # it ships. Taking it from the consumer would let a consumer missing a whole
    # tree hide that fact by simply not having it.
    scope = _installed_scope(kit_root)
    install, kit = _relevant(install_root, scope), _relevant(kit_root, scope)
    # The consumer receives `settings.plugin.json` AS `settings.json`; comparing it
    # against the kit's `settings.json` (the development one) reports DIVERGED on
    # every install.
    resolved_kit = dict(kit)
    for install_name, kit_name in _INSTALL_TO_KIT_ALIAS.items():
        if install_name in install and kit_name in kit:
            resolved_kit[install_name] = kit[kit_name]
            resolved_kit.pop(kit_name, None)

    report = DriftReport(
        counts={d: 0 for d in Drift},
        by_class={d: [] for d in Drift},
        only_in_install=sorted(set(install) - set(resolved_kit)),
        only_in_kit=sorted(set(resolved_kit) - set(install)),
        _kit_dirs=frozenset(str(Path(rel).parent) for rel in resolved_kit),
    )
    for rel in sorted(set(install) & set(resolved_kit)):
        verdict = classify_file(install[rel], resolved_kit[rel], kit_root, rel)
        report.counts[verdict] += 1
        report.by_class[verdict].append(rel)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", type=Path, required=True,
                        help="a consumer's install root (…/.claude), or one tree inside it")
    # The kit ROOT, not its `skills/`. The old default silently narrowed every
    # invocation to one of the six trees an install carries.
    # `--root` is an alias for `--kit`, per the contract in `_contract.py`. This gate
    # compares TWO trees, so it is the one place where "the tree to sweep" needed
    # saying which: `--kit` is the reference and `--install` is the copy under test.
    parser.add_argument("--root", "--kit", dest="kit", type=Path,
                        default=Path(__file__).resolve().parents[2],
                        help="this kit's root (default: the repository this file lives in)")
    # Asking is not auditing: this lists what the install owns and exits 0, so a
    # cleanup can diff against it. Folding it into the default output would put a
    # normally-healthy list in front of everyone on every run, and kit#33 argued
    # the right moment is the destructive one, not every session.
    parser.add_argument("--consumer-local", action="store_true",
                        help="list the files this install holds that the kit does not ship, "
                             "and exit — consult this BEFORE deleting anything under .claude/")
    args = parser.parse_args(argv)

    for label, root in (("install", args.install), ("kit", args.kit)):
        if not root.is_dir():
            print(f"check-install-drift: {label} path is not a directory: {root}", file=sys.stderr)
            return 2

    report = scan(args.install, args.kit)

    if args.consumer_local:
        local = report.consumer_local_files
        print(f"consumer-local: {len(local)}   (files this install holds and the kit does not ship)")
        for rel in local:
            print(f"    {rel}")
        if not local:
            # An empty answer stated is not the same artifact as no answer at all.
            print("    no files — everything here came from the kit")
        return 0

    #: What each class COSTS, printed beside its count. All four used to render as
    #: `<class>: <count>` and a file list, so `install_ahead: 3` sat next to
    #: `kit_ahead: 38` and a reader compared magnitudes — two sizes of one thing.
    #:
    #: They are not one thing. `install.sh --force` snapshots `.claude/` into
    #: `.install-backups/` and replaces it, so INSTALL_AHEAD is the ONLY class whose
    #: lines are gone after an upgrade. KIT_AHEAD is pure gain, IDENTICAL is nothing,
    #: and DIVERGED at least survives on both sides until somebody chooses.
    #:
    #: Measured 2026-09-22 on a real consumer: `install_ahead: 3` — three hooks carrying
    #: the wiring for a 94-line module the kit does not have. The number printed on every
    #: run, was read twice that day by the session maintaining the kit, and nobody opened
    #: the files. A count in the same voice as a count that loses nothing reads as
    #: inventory.
    _COST = {
        Drift.INSTALL_AHEAD: ("lines only this install has — ERASED by the next "
                              "`install.sh --force`, which is true of no other class "
                              "here. Harvest upstream before upgrading"),
        Drift.DIVERGED: ("both sides hold unique lines — a copy in either direction "
                         "deletes the other's fix"),
        # These two are the only classes where this install holds NO line the kit lacks,
        # which is the whole reason `--apply-upstream` accepts them and refuses the two
        # above. Naming the command here and nowhere else is deliberate: it was reachable
        # only by replacing the whole tree, and a reader who saw the count had no smaller
        # answer than reinstalling everything.
        Drift.STALE: ("the kit moved on and this copy did not — one file at a time with "
                      "`install.sh <target> --apply-upstream <path>`"),
        Drift.KIT_AHEAD: ("the kit holds lines this install lacks — an upgrade adds them, "
                          "as does `install.sh <target> --apply-upstream <path>` per file"),
    }
    for verdict in (Drift.DIVERGED, Drift.INSTALL_AHEAD, Drift.STALE, Drift.KIT_AHEAD):
        files = report.by_class[verdict]
        if files:
            print(f"{verdict.value}: {len(files)} — {_COST[verdict]}")
            for rel in files:
                print(f"    {rel}")
    if report.unharvested_files:
        print(f"install-only, in a directory the kit has (yours, or work to harvest — this check cannot tell): {len(report.unharvested_files)}")
        for rel in report.unharvested_files:
            print(f"    {rel}")
    consumer_local = len(report.consumer_local_files)
    print(f"identical: {report.counts[Drift.IDENTICAL]}   only_in_kit: {len(report.only_in_kit)}"
          f"   consumer-local: {consumer_local}")

    if report.needs_attention:
        # Name the class that actually fired. This said "DIVERGED files need a human"
        # whenever ANY of three conditions held, including runs with zero diverged
        # files — a message about an empty class, which sends a reader looking for a
        # conflict that is not there. Measured 2026-09-16 on a consumer: 0 diverged,
        # 0 install-ahead, 2 unharvested, and the line still named DIVERGED.
        why = []
        if report.counts.get(Drift.DIVERGED):
            why.append(f"{report.counts[Drift.DIVERGED]} DIVERGED — both sides hold "
                       "unique lines, and a copy in either direction deletes the "
                       "other's fix")
        if report.counts.get(Drift.INSTALL_AHEAD):
            # DIVERGED's entry above names what it COSTS. This one named only what it
            # IS, and the cost is the reason to act: these lines are the only ones the
            # upgrade takes away.
            why.append(f"{report.counts[Drift.INSTALL_AHEAD]} INSTALL_AHEAD — the "
                       "install holds lines the kit does not, and they are erased by "
                       "the next install")
        if report.unharvested_files:
            why.append(f"{len(report.unharvested_files)} install-only file(s) in a "
                       "directory the kit has — yours, or work to harvest")
        print("\ncheck-install-drift: " + "; ".join(why) + ".", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

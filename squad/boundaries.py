"""Where the kit ends and the project begins — asked once, by both guards.

Two hooks enforce this boundary and they used to know it in one place only.
`boundary-check` refused `Edit`/`Write` into an installed kit; `validate-command`
refused shell writes into `study-material/` and knew nothing about the kit. So
`sed -i` reached the file `Edit` had just been refused, which is the boundary
holding against the careful tool and not against the quick one.

Keeping the answer here rather than in either hook is the rule the kit already
learned twice: a rule living in one file and missing from another is how the gap
reopens (`squad/plan.py`, `_credential_globs`). The two hooks now differ in what
they DO about a violation — one denies a tool call, the other refuses a command —
and not in where they think the line is.
"""
from __future__ import annotations

import re
from pathlib import Path

from .layout import Layout
from .paths import DATA_DIRNAME

#: The read-only study zone, as `rules/reference-provenance.md` § 1 declares it.
#:
#: WHY IT LIVES IN THE WRITE ROOT. The zone was a top-level `study-material/`, which put
#: third-party code in the tree the project versions — so `.gitignore` had to carry
#: `study-material/**` to keep a literal copy, and the licence it brings with it, out of
#: the index. Inside `.squad/` the question does not arise: the write root is the
#: project's own run area, ignored whole, and nothing under it is ever committed. The
#: guard is unchanged; what changed is that it now guards a path nobody can commit by
#: accident.
#:
#: WHY IT LIVES HERE. It was spelled three times in three shapes — `(^|/)(\.claude/)?…`
#: in `boundary-check`, `(\./)?(\.claude/)?…` in `validate-command`, and a bare
#: directory name in `check_reference_leakage`. This module's own docstring records what
#: that costs: two hooks knowing one boundary differently is how `sed -i` reached a file
#: `Edit` had just refused.
#: The literal comes from `squad.paths`, which owns every data-root spelling — writing
#: `.squad` here was refused by `test_no_kit_module_outside_the_owner_spells_a_data_root`
#: within the hour, which is the gate working.
STUDY_ZONE = f"{DATA_DIRNAME}/study-material"


def study_zone_re() -> re.Pattern[str]:
    """Matches a path inside the study zone, in every shape a caller passes one.

    Absolute, `./`-prefixed, nested under an installed kit's `.claude/`, or sitting mid
    sentence in a commit message. The guards feed this free text — a shell command line,
    a `-m` body — not just a clean path, so anchoring it to start-or-slash silently
    stopped matching `git commit -m "see .squad/study-material/x"`. A lookbehind gives
    the same protection without the anchor: `mine.squad/study-material/` does not match,
    and neither does the `squad/` PACKAGE, which has no leading dot.
    """
    return re.compile(rf"(?<![\w.-]){re.escape(STUDY_ZONE)}/")


#: Paths inside an installed kit that belong to the PROJECT, not the kit. A
#: consumer tunes these and the installer preserves them across an update.
PROJECT_OWNED = (
    re.compile(r"^rules/[^/]+\.txt$"),
    re.compile(r"^agents/"),
    re.compile(r"^records/"),
    re.compile(r"^settings\.json$"),
    re.compile(r"^\.kit-manifest\.txt$"),
    re.compile(r"^\.install-backups/"),
)


#: Directories the kit ships WHOLE, where the manifest is not consulted at all.
#: Nobody else creates `.claude/mechanisms/` — everything under one of these names
#: arrived with the kit, and structure says so more reliably than any file.
#:
#: This is a LIMIT on the manifest's authority, and it exists because the manifest
#: has not always been complete. `install.sh` recorded in its own comment that the
#: file once "covers only `agents/`, `rules/` and `skills/` — for `hooks/` and
#: `scripts/` it is blind, so consulting it would answer by omission". Every
#: consumer installed before it widened still holds one of those. Reading absence
#: there as a concession would unlock `hooks/` and `mechanisms/` on all of them,
#: which is a far worse error than the one being fixed — and it is not theoretical:
#: `test_kit_is_read_only` builds exactly that manifest and caught this.
#:
#: `skills/` and the kit ROOT are deliberately NOT here. Both are shared ground —
#: a project writes its own skills, and every installed plugin writes loose files
#: beside the kit's — so there the manifest is the only thing that can tell them
#: apart, and the measured defect lived at the root.
KIT_TREES = ("hooks/", "mechanisms/", "squad/", "commands/", "rules/")


def _claimed(kit_dir: Path) -> set[str] | None:
    """What the install manifest says the kit brought, or `None` if it cannot say."""
    manifest = kit_dir / ".kit-manifest.txt"
    if not manifest.is_file():
        return None
    try:
        text = manifest.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    return {line.split("#", 1)[0].strip() for line in text.splitlines()} - {""}


def is_project_owned(rel: str, kit_dir: Path) -> bool:
    """Is this kit-relative path the consumer's to change?

    The manifest's own header states the rule — "Anything not here is the
    project's" — and this function used to apply it to `skills/` alone. So a path
    the kit never installed was refused anyway, on the grounds that it sat in the
    kit's directory. That directory is shared: every plugin a project installs
    writes into `.claude/`. Measured on a consumer 2026-09-18, the boundary
    claimed `code-review-loop.local.md`, `code-review-loop.completed.md` and
    `test-audit-loop.local.md` — three files belonging to two other plugins, one
    of which must be deleted to cancel a run, by that plugin's documented
    procedure. The refusal was not merely inconvenient, it was FALSE about why:
    a guard that misstates its own reason teaches people to route around it.

    The manifest lists things at three granularities — `skills/<name>` by
    directory, `rules/<file>` and the rest by file — so the question asked is
    whether ANY prefix of the path is claimed. One rule covers all three, and a
    fourth granularity added later needs no change here.

    No manifest means the kit cannot MEASURE ownership, so it concedes nothing
    and the old refusal stands. Treating an unreadable manifest as a blanket
    unlock would be this kit's most-repeated defect, inverted: a check that could
    not measure its subject, reporting the answer nobody verified.
    """
    if any(pattern.search(rel) for pattern in PROJECT_OWNED):
        return True
    if rel.startswith(KIT_TREES):
        return False
    claimed = _claimed(kit_dir)
    if claimed is None:
        return False
    parts = rel.split("/")
    return not any("/".join(parts[:i]) in claimed for i in range(1, len(parts) + 1))


def kit_relative(target: Path, layout: Layout) -> str | None:
    """This path's location inside the kit, or `None` when it is outside it.

    `None` covers three different situations that need the same answer — the path
    is the project's, the kit is this repository itself, or the path does not
    resolve — because in all three the kit boundary has nothing to say.
    """
    if layout.kind == "standalone":
        return None  # the kit's own repository: these files ARE the work
    if not target.is_absolute():
        target = layout.project_dir / target
    try:
        return str(target.resolve().relative_to(layout.kit_dir.resolve()))
    except (ValueError, OSError):
        return None


def violation(target: Path, layout: Layout) -> str | None:
    """The refusal for writing to `target`, or `None` when the write is fine."""
    rel = kit_relative(target, layout)
    if rel is None or is_project_owned(rel, layout.kit_dir):
        return None
    return (
        f"BOUNDARY VIOLATION: {rel} belongs to the installed Squad kit, which is "
        f"read-only here. A fix written inside an installed kit protects exactly "
        f"one machine and is erased by the next install.\n\n"
        f"WHERE IT GOES: open an issue on the kit's repository. `mechanisms/fleet/"
        f"kit_issues.py` is the registry that reads them, and an issue travels "
        f"without anyone joining a working tree — which `git-safety.md` forbids a "
        f"second agent from doing, and which is why 'send it upstream' is not the "
        f"same instruction as 'go and commit there'. Include what you measured and "
        f"where, so the fix does not start by re-measuring.\n\n"
        f"Project-owned paths under the same tree stay writable: rules/*.txt "
        f"(config), agents/ (your domain specialists), records/ (cycle output) and "
        f"settings.json."
    )

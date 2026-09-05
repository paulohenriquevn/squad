#!/usr/bin/env python3
"""SessionStart — put the chain, the roles and the current state in front of the agent.

A fresh session knows nothing about where the work stands. This injects the small
set of facts every later decision rests on: which branch, whether the tree is
dirty, which plan is active, and the shape of the cycle it is inside.

The map itself lives in `rules/squad-map.md`, and this points at it rather than
restating it — two copies of one map drift, and the copy injected at SessionStart
is the one nobody notices going stale. `check_squad_map.py` compares that file to
the directory; nothing could compare a here-document to anything.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import SessionStartContext, create_context
from squad.layout import Layout, has_kit, resolve
from squad.plan import resolve as resolve_plan

#: The prefixes of every count line `check_install_drift` prints. Kept in one
#: place so a new class the gate learns to name lands in this summary the same
#: way the others do, rather than silently going missing here.
_DRIFT_COUNT_PREFIXES = (
    "diverged:",
    "install_ahead:",
    "stale:",
    "kit_ahead:",
    "unharvested (install-only",
    "identical:",
)

#: A count line the gate emits when there is drift to report. `identical:` is on
#: the summary line, not a header, so it is treated separately below.
_DRIFT_ATTENTION_PREFIXES = (
    "diverged:", "install_ahead:", "stale:", "kit_ahead:",
    "unharvested (install-only",
)


def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True,  # noqa: PLW1510
                              timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def git_line() -> str | None:
    if not Path(".git").is_dir():
        return None
    branch = _git("branch", "--show-current") or "(detached)"
    porcelain = _git("status", "--porcelain")
    if porcelain is None:
        return None
    dirty = len([ln for ln in porcelain.splitlines() if ln.strip()])
    ahead = _git("rev-list", "--count", "@{upstream}..HEAD") or "0"
    state = "clean" if dirty == 0 else f"{dirty} uncommitted files"
    return f"Git: branch={branch} ({state}, {ahead} ahead of upstream)"


def plan_line(eco: Path) -> str | None:
    """The active plan, saying WHICH way it was found — pinned is a decision,
    newest-by-mtime is a guess that happens to be usually right."""
    active = resolve_plan(eco)
    if active is None:
        return None
    if active.how == "pinned":
        return (f"Active plan: {active.slug} ({active.path}) "
                f"— pinned via {eco}/.active_plan")
    return f"Active plan: {active.slug} (resolved by mtime — set {eco}/.active_plan to pin)"



def _source_from_manifest(layout) -> str | None:
    """The path `install.sh` copied from, recorded in `.kit-manifest.txt`.

    `SQUAD_KIT_SOURCE` wins when it is set: exporting it is an explicit choice —
    usually a second checkout — and a fallback that overrode it would be a defect
    of its own. This is for the consumer who never heard of the variable, which
    is every consumer, because it is documented in no README and no rule (#23).

    A `#`-prefixed line, so the manifest's existing readers, which all skip
    comments, are unaffected by its presence.
    """
    manifest = Path(layout.eco) / ".kit-manifest.txt"
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.startswith("# kit-source:"):
                value = line.split(":", 1)[1].strip()
                return value or None
    except OSError:
        return None
    return None

def drift_line(layout: Layout) -> str | None:
    """A stale install learns it, without a person remembering to ask.

    Compares `layout.kit_dir` against `$SQUAD_KIT_SOURCE` via `check_install_drift`
    and reports the counts as one context line. **Never blocks and never fails
    the session**: a consumer may deliberately pin an older kit, and a session
    stopped over that is worse than the drift; the report is a signal, not a
    gate.

    The source comes from `$SQUAD_KIT_SOURCE`, or from the manifest when the
    variable is unset — so a consumer who never heard of the variable, which is
    every consumer, still gets the report. WHICH of the two answered is carried
    through to the message: naming the env var for a value that came from the
    manifest sends the reader to check something that is empty.

    Wired in for #23: `check_install_drift` was cited nine times in prose and
    executed by nothing; a consumer ran ten hours on a stale kit missing three
    merged repairs. The diagnostic was correct, available, and in a drawer.
    """
    source_env = os.environ.get("SQUAD_KIT_SOURCE")
    if source_env:
        origin = "SQUAD_KIT_SOURCE"
    else:
        source_env = _source_from_manifest(layout)
        origin = ".kit-manifest.txt"
    if not source_env:
        return None
    source = Path(source_env)
    if not has_kit(source):
        # A path that names a wrong directory is worth saying so — silence would
        # look like a clean bill of health. The origin matters most here: it is
        # the one line that tells the reader WHERE to go correct it.
        return (f"Kit drift: {origin}={source_env} does not contain "
                "skills/, rules/, hooks/ — cannot compare")
    try:
        if source.resolve() == layout.kit_dir.resolve():
            # `standalone` layout, or SQUAD_KIT_SOURCE pointing at the same
            # directory the session is running. There is no drift to report
            # between a tree and itself; silence is correct.
            return None
    except OSError:
        return None
    checker = layout.kit_dir / "mechanisms" / "gates" / "check_install_drift.py"
    if not checker.is_file():
        return None
    try:
        result = subprocess.run(  # noqa: PLW1510
            [sys.executable, str(checker),
             "--install", str(layout.kit_dir),
             "--kit", str(source)],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # The gate exits 1 when there is unharvested work and 2 on argument errors;
    # both are informational here. Never gate on this hook.
    counts = [ln for ln in result.stdout.splitlines()
              if ln.startswith(_DRIFT_COUNT_PREFIXES)]
    attention = [ln for ln in counts if ln.startswith(_DRIFT_ATTENTION_PREFIXES)]
    if not attention:
        return None
    # Compact the multi-line summary into one line the SessionStart context can
    # carry. The full per-file listing is a `check_install_drift` invocation away.
    return ("Kit drift (vs " + origin + "=" + source_env + "): "
            + " · ".join(attention)
            + " — report only, never blocks; run `check_install_drift --install "
            + str(layout.kit_dir) + " --kit " + source_env + "` for the file list")


def loop_line(eco: Path) -> str | None:
    marker = eco / "ralph-loop.local.md"
    if not marker.is_file():
        return None
    fields = {}
    for line in marker.read_text(encoding="utf-8", errors="replace").splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    if fields.get("active") != "true":
        return None
    return (f"ralph-loop: ACTIVE (iter {fields.get('iteration', '?')}) — if stale "
            f"(>24h, no progress), cancel via /ralph-loop:cancel-ralph or delete the file")


def chain_lines(eco: Path) -> list[str]:
    return [
        "",
        f"SQUAD — the chain, and who decides (full map: {eco}/rules/squad-map.md)",
        "  BRAINSTORM -> BACKLOG -> DISCOVER -> PLAN -> IMPLEMENT -> CODE-QUALITY -> "
        "REVIEW -> RELEASE -> ACCEPTANCE",
        "  BRAINSTORM is the ONLY phase that requires a person; everything after it "
        "runs unattended, merge included.",
        "  ITEM_KILLED ends the chain and is a SUCCESSFUL outcome.",
        "  Roles: kairos=what work exists & in what order | iris=what the user "
        "experiences | daedalus=one item's technical path | hermes=flow & halts",
        "  Domain specialists are the PROJECT's, never the kit's. Reach them with "
        "mechanisms/cycle/route_domain.py <repo>;",
        "    exit 3 (BROKEN ROUTE) means the domain names a specialist nobody wrote "
        "— stop, do NOT stand in for them.",
        "  No verdict is asserted in prose: a script computes it. Read the cycle rule "
        "before running a phase.",
        "",
        "Unbreakable principles apply (see ~/.claude/CLAUDE.md): 95% confidence, "
        "TDD-first, no commits to main, CHANGELOG discipline.",
    ]


def build_context(layout: Layout) -> str:
    lines = [line for line in (git_line(), plan_line(layout.eco),
                                loop_line(layout.eco), drift_line(layout))
             if line]
    lines.extend(chain_lines(layout.eco))
    return "\n".join(lines) + "\n"


def main() -> None:
    c = create_context(SessionStartContext)
    layout = resolve()
    if layout is None:
        # No kit here, or a broken install that already said so. Injecting the
        # chain into a project that does not run it would be noise.
        return
    c.output.add_context(build_context(layout))


if __name__ == "__main__":
    main()

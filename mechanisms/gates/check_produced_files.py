#!/usr/bin/env python3
"""Nothing the mechanisms PRODUCE lands outside `<project>/.squad/`. Proved by running them.

    python3 mechanisms/gates/check_produced_files.py
    python3 mechanisms/gates/check_produced_files.py --json

## Why a second containment gate

`check_write_containment.py` proves a static property: no module outside
`squad/paths.py` may spell a data root, so every path a writer BUILDS came from the
owner. That is a real guarantee and it is not the whole one. It says nothing about a
writer whose destination never passes through `squad.paths` at all — a path taken from
argv, joined onto the installed kit's directory, or handed down from a caller.

Attempting the static version of this question is what motivated the runtime one.
Tracing 135 write call sites through the AST to their originating root left 64 of them
UNKNOWN: the destination arrives as a parameter, or is built across functions. A proof
with a 47% hole is not a proof, and widening the tracer indefinitely produces a
mechanism only its author can re-run — the objection `check_write_containment.py`
already raises against reading call sites by hand.

So this one runs the mechanisms and looks at the disk. Whatever appears is what they
produce, whatever the code path was.

## What it does

Copies the kit into a scratch project, snapshots every file, runs the mechanisms that
produce artifacts, and snapshots again. Every path that appeared or changed is checked
against `<project>/.squad/`. Anything else must match a row in
`rules/write-exemptions.txt`, which requires a class and a reason.

## What it does NOT prove, named rather than left to be discovered

  - COVERAGE. It exercises the mechanisms listed in `PROBES` below, and reports how
    many ran. A writer no probe reaches is not examined, and the report says so with a
    count rather than implying the sweep was exhaustive. Growing `PROBES` is how this
    gate gets stronger; a green run over three probes is worth what three probes are
    worth.
  - AGENT BEHAVIOUR. A skill is a document an agent follows, and an agent that decides
    to write somewhere is not running any code this can call. Only mechanisms — the
    scripts — are exercised.
  - THE HOME DIRECTORY AND `/tmp`. Deliberately out of scope, and out of scope is not
    the same as allowed: `skills/code-quality/scripts/_registry.py` caches under
    `~/.cache/` on purpose, because the registry it caches is about a tool version and
    not about any one project. A per-project cache would re-fetch once per repository
    for data that is identical in all of them.

Exit codes:
  0  every produced file is contained, or exempt with a declared reason
  1  a produced file escaped and nothing declares it
  2  the sweep could not run; nothing was checked, and that is not a pass
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import (  # noqa: E402 — post-bootstrap import
    DATA_DIRNAME,
    write_records_dir,
)

#: What the kit copies into a consumer. Mirrors `install.sh`'s own list; a directory
#: missing here is a directory the probes cannot exercise, which shows up as a probe
#: that could not run rather than as a pass.
KIT_DIRS = ("skills", "rules", "hooks", "commands", "mechanisms", "squad", "agents")

#: One probe is (label, argv-template). `{eco}` is the installed kit, `{proj}` the
#: project. Each must PRODUCE something — a probe that only reads proves nothing here.
PROBES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("detect_domains --write",
     ("{eco}/skills/backlog-init/scripts/detect_domains.py",
      "--root", "{proj}", "--write")),
    ("scaffold_specialists --write",
     ("{eco}/skills/backlog-init/scripts/scaffold_specialists.py",
      "--root", "{proj}", "--write")),
    ("cycle_events end",
     ("{eco}/mechanisms/cycle/cycle_events.py", "end",
      "--cycle", "discover", "--slug", "probe", "--verdict", "SHIPPABLE",
      "--project-root", "{proj}")),
    ("convene_panel",
     ("{eco}/mechanisms/cycle/convene_panel.py",
      "--slug", "probe", "--phase", "discover", "--project", "{proj}")),
    ("select_auditors --write",
     ("{eco}/mechanisms/cycle/select_auditors.py",
      "--slug", "probe", "--domains", "testing", "--project", "{proj}", "--write")),
    ("backlog_index --write",
     ("{eco}/skills/backlog-review/scripts/backlog_index.py",
      "{proj}/BACKLOG.md", "--write")),
    #: The writer that surprised this sweep's author: `/review` generates one
    #: knowledge skill PER REVIEWER PER PLAN, into the installed kit's own
    #: `skills/`. Five of them were sitting in a measured consumer.
    ("spawn_reviewers",
     ("{eco}/skills/review/scripts/spawn_reviewers.py",
      "--plan", "{plan}", "--slug", "probe",
      "--primary-domain", "backend")),
    ("promote_unreleased",
     ("{eco}/skills/release/scripts/promote_unreleased.py",
      "--changelog", "{proj}/CHANGELOG.md", "--version", "9.9.9",
      "--date", "2026-09-10")),
    ("build_walkthrough",
     ("{eco}/skills/plan-alignment/scripts/build_walkthrough.py", "{plan}")),
    ("check_intake_gates",
     ("{eco}/skills/backlog-item/scripts/check_intake_gates.py",
      "--backlog", "{proj}/BACKLOG.md", "--repo", "project", "--project", "{proj}")),
    ("run_code_quality",
     ("{eco}/skills/code-quality/scripts/run_code_quality.py",)),
    ("mini_review",
     ("{eco}/skills/implement/scripts/mini_review.py",
      "--slug", "probe", "--plan", "{plan}", "--progress", "{plan}",
      "--phase", "REFACTOR", "--project-root", "{proj}")),
    ("inject_milestone_id",
     ("{eco}/skills/idea-to-release/scripts/inject_milestone_id.py",
      "--plan", "{plan}", "--milestone-id", "M1")),
    ("flip_milestone_checkbox",
     ("{eco}/skills/release/scripts/flip_milestone_checkbox.py",
      "--roadmap", "{proj}/ROADMAP.md", "--milestone-id", "M1", "--version", "9.9.9")),
    ("backlog_status --to",
     ("{eco}/mechanisms/cycle/backlog_status.py", "{proj}/BACKLOG.md", "B-001",
      "--to", "triaged", "--because", "the probe moved it")),
    #: Writers whose destination is a `--output-dir` or `--output`: the CALLER decides,
    #: which is exactly the shape static tracing could not resolve. Probed with the
    #: flag omitted, so what gets exercised is each script's own default.
    ("spawn_stages",
     ("{eco}/skills/pipeline/scripts/spawn_stages.py",
      "--item", "B-001", "--repo", "project")),
    ("apply_plan_fixes (plan-improve)",
     ("{eco}/skills/plan-improve/scripts/apply_plan_fixes.py", "{plan}")),
    ("consolidate_findings",
     ("{eco}/skills/review/scripts/consolidate_findings.py",
      "--findings-dir", "{proj}", "--output", "{plan}", "--slug", "probe",
      "--repo-root", "{proj}")),
)


#: Exit codes a probe may legitimately reach. 0 is success; the others are verdicts
#: mechanisms in this kit return about the artifact they examined — BROKEN ROUTE,
#: NEEDS_REVISION, a gate that found something. All of them mean the mechanism RAN.
#: 2 is deliberately absent: across this kit it means "could not measure", and a
#: probe that could not measure did not exercise its writer.
ACCEPTED_EXITS = frozenset({0, 1, 3})


@dataclass
class Exemption:
    glob: str
    klass: str
    reason: str


@dataclass
class Report:
    contained: bool
    probes_run: int
    probes_total: int
    probes_failed: list[str] = field(default_factory=list)
    produced: list[str] = field(default_factory=list)
    escaped: list[dict] = field(default_factory=list)
    exempted: list[dict] = field(default_factory=list)
    home_writers: list[str] = field(default_factory=list)
    unmeasured_because: str = ""


def parse_exemptions(path: Path) -> list[Exemption]:
    """Rows of `<glob> | <class> | <reason>`. A row missing either is refused.

    The refusal is the point. "We made an exception" and "the platform gave us no
    choice" are different claims, and only the second survives review — so the row
    has to say which it is, in a field, not in a comment somebody may delete.
    """
    out: list[Exemption] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                f"{path}:{lineno}: an exemption needs `<path> | <class> | <reason>`; "
                f"got {len(parts)} field(s). An exemption with no reason is a hole "
                "nobody can argue with")
        if parts[1] not in {"platform", "tool", "human"}:
            raise ValueError(
                f"{path}:{lineno}: class `{parts[1]}` is not one of platform/tool/human. "
                "The class is what says whether the exception was forced or chosen")
        if len(parts[2].split()) < 5:
            raise ValueError(
                f"{path}:{lineno}: the reason is {len(parts[2].split())} word(s). "
                "Name the thing that forces the location, not that one exists")
        out.append(Exemption(*parts))
    return out


#: Modules allowed to write outside the project entirely. The snapshot below only
#: sees inside the scratch project, so a mechanism writing to `$HOME` would never
#: appear in it — this closes that by reading the code instead.
HOME_WRITERS: dict[str, str] = {
    "skills/code-quality/scripts/_registry.py":
        "caches the tool registry under `~/.cache/`, deliberately: what it caches is "
        "about a TOOL VERSION and is identical in every repository, so a per-project "
        "copy would re-fetch the same bytes once per repo",
    "mechanisms/fleet/fleet_router.py":
        "appends the fleet's assignment log to `~/.squad-fleet/`. The router allocates "
        "lanes ACROSS projects and its log is about the fleet, not about any one of "
        "them; filing it under one project's write root would hide the other lanes",
    "mechanisms/conventions/installed_plugins.py":
        "READS `~/.claude/plugins/installed_plugins.json`, which is where Claude Code "
        "records what the user installed. Reading the user's own configuration is not "
        "a write, and there is no other copy of that fact",
}

#: `Path.home()` CONSTRUCTS a destination. `x.expanduser()` NORMALISES a path a person
#: typed — `--project ~/repo` — and flagging it reported four call sites that only
#: resolve an argument, which is the shape of a check people learn to ignore.
_HOME_CALL = re.compile(r"Path\.home\(\)|os\.path\.expanduser\(")


def scan_home_writers(kit_root: Path) -> list[dict]:
    """Modules that reach for the home directory and are not declared to.

    Static, and deliberately so. The runtime sweep snapshots the scratch PROJECT; a
    write to `$HOME` lands outside it and leaves no trace there. Snapshotting the real
    home directory would make the gate slow, noisy and destructive to run.
    """
    findings = []
    for path in sorted(kit_root.rglob("*.py")):
        rel = path.relative_to(kit_root).as_posix()
        if "/tests/" in rel or rel.startswith("tests/") or "__pycache__" in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            code = line.split("#")[0]
            if _HOME_CALL.search(code) and rel not in HOME_WRITERS:
                findings.append({"file": rel, "line": lineno,
                                 "why": "reaches for the home directory and is not in "
                                        "HOME_WRITERS. Either write under the project's "
                                        "write root, or declare it there with the reason"})
    return findings


def _snapshot(root: Path) -> dict[str, str]:
    """Path -> content hash, for every file under `root`, skipping git internals."""
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file() or ".git/" in str(path.relative_to(root)) + "/":
            continue
        try:
            out[str(path.relative_to(root))] = hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
        except OSError:
            continue
    return out


def _matches(relpath: str, exemption: Exemption, eco_name: str) -> bool:
    """`<eco>` in a glob stands for wherever the kit was installed."""
    pattern = exemption.glob.replace("<eco>", eco_name) if eco_name else exemption.glob
    return Path(relpath).match(pattern) or Path(relpath).match(pattern.lstrip("./"))


def _seed(proj: Path, kit: Path) -> Path:
    """A minimal consumer: a git repo, one source file, and the kit under `.claude/`."""
    (proj / "src").mkdir(parents=True, exist_ok=True)
    (proj / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    (proj / "BACKLOG.md").write_text(
        "# Backlog\n\n## Index\n\n## Items\n\n"
        "## B-001 — a probe item   [ ]\n"
        "- status: raw\n- domain: project\n- repo: project\n"
        "- why_now: the sweep needs an item to move\n", encoding="utf-8")
    (proj / "ROADMAP.md").write_text(
        "# Roadmap\n\n## M1 — a milestone\n\n- [ ] it works\n", encoding="utf-8")
    (proj / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added\n- a thing (#1)\n", encoding="utf-8")
    #: Under the write root, because a probe's INPUT must not itself be a file
    #: appearing outside it — the sweep would then report its own fixture.
    plans = write_records_dir(proj, "plans")
    plans.mkdir(parents=True, exist_ok=True)
    (plans / "probe.md").write_text(
        "# Probe plan\n\n## Critical paths\n\n- src/main.py\n", encoding="utf-8")
    eco = proj / ".claude"
    eco.mkdir(exist_ok=True)
    for d in KIT_DIRS:
        src = kit / d
        if src.is_dir():
            shutil.copytree(src, eco / d, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"))
    subprocess.run(["git", "init", "-q", str(proj)], check=False,
                   capture_output=True)
    return eco


def check(kit_root: Path) -> Report:
    exemptions_path = kit_root / "rules" / "write-exemptions.txt"
    if not exemptions_path.is_file():
        return Report(False, 0, len(PROBES),
                      unmeasured_because=f"no exemption registry at {exemptions_path}")
    try:
        exemptions = parse_exemptions(exemptions_path)
    except ValueError as exc:
        return Report(False, 0, len(PROBES), unmeasured_because=str(exc))

    with tempfile.TemporaryDirectory(prefix="squad-produced-") as tmp:
        proj = Path(tmp) / "project"
        proj.mkdir()
        try:
            eco = _seed(proj, kit_root)
        except OSError as exc:
            return Report(False, 0, len(PROBES),
                          unmeasured_because=f"could not seed the scratch project: {exc}")

        before = _snapshot(proj)

        env = dict(os.environ)
        #: The suppression this kit ships. Without it the probes write bytecode next
        #: to the copied kit and the gate reports its own interpreter's droppings.
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        ran, failed = 0, []
        for label, argv in PROBES:
            cmd = [sys.executable] + [
                a.format(eco=eco, proj=proj, plan=write_records_dir(proj, "plans") / "probe.md")
                for a in argv]
            if not Path(cmd[1]).is_file():
                failed.append(f"{label} — {Path(cmd[1]).name} not in this install")
                continue
            try:
                done = subprocess.run(cmd, cwd=proj, env=env, capture_output=True,
                                      timeout=120, text=True, check=False)
            except (OSError, subprocess.SubprocessError) as exc:
                failed.append(f"{label} — {type(exc).__name__}")
                continue
            #: A PROBE THAT ERRORED EXERCISED NOTHING. Counting it as run is how a
            #: sweep reports twelve mechanisms and examines six — the substitution
            #: this gate exists to prevent, committed by the gate itself. Exit codes
            #: in this kit are load-bearing, so a non-zero exit is not necessarily a
            #: crash: the accepted ones are the verdicts a mechanism reaches on a
            #: healthy tree. Anything else means the probe did not get to write.
            if done.returncode in ACCEPTED_EXITS:
                ran += 1
            else:
                tail = (done.stderr or done.stdout or "").strip().splitlines()
                failed.append(f"{label} — exit {done.returncode}"
                              + (f": {tail[-1][:110]}" if tail else ""))

        after = _snapshot(proj)

    produced = sorted(p for p, h in after.items() if before.get(p) != h)
    data_prefix = DATA_DIRNAME + os.sep
    escaped, exempted = [], []
    for rel in produced:
        if rel.startswith(data_prefix):
            continue
        hit = next((e for e in exemptions if _matches(rel, e, ".claude")), None)
        if hit:
            exempted.append({"path": rel, "class": hit.klass, "reason": hit.reason})
        else:
            escaped.append({"path": rel, "why": (
                "produced outside the write root and declared by no exemption. Either "
                "route it through `squad.paths`, or add a row to "
                "`rules/write-exemptions.txt` naming what forces the location")})

    #: A sweep where NO probe ran examined nothing. Reporting containment from that is
    #: the substitution this whole kit is written against.
    if ran == 0:
        return Report(False, 0, len(PROBES), probes_failed=failed,
                      unmeasured_because="no probe ran; nothing was exercised")

    for finding in scan_home_writers(kit_root):
        escaped.append({"path": f"{finding['file']}:{finding['line']}", "why": finding["why"]})

    return Report(not escaped, ran, len(PROBES), failed, produced, escaped, exempted,
                  home_writers=sorted(HOME_WRITERS))


def render(r: Report) -> str:
    out = ["produced-file containment"]
    if r.unmeasured_because:
        out += [f"  NOT MEASURED — {r.unmeasured_because}", "",
                "  A sweep that ran nothing must not report a verdict about everything."]
        return "\n".join(out)

    out.append(f"  probes: {r.probes_run}/{r.probes_total} ran · "
               f"{len(r.produced)} file(s) produced or changed")
    for f in r.probes_failed:
        out.append(f"    skipped: {f}")
    if r.exempted:
        out.append(f"  exempt ({len(r.exempted)}), each naming what forces it:")
        for e in sorted(r.exempted, key=lambda e: e["path"]):
            out.append(f"    [{e['class']}] {e['path']}")
    if r.escaped:
        out.append(f"  ESCAPED ({len(r.escaped)}):")
        for e in r.escaped:
            out.append(f"    {e['path']}")
            out.append(f"        {e['why']}")
    out.append("")
    out.append(f"  {'CONTAINED' if r.contained else 'ESCAPED'} — everything produced is "
               f"under {DATA_DIRNAME}/ or declared" if r.contained else
               f"  ESCAPED — {len(r.escaped)} produced file(s) outside {DATA_DIRNAME}/ "
               "that nothing declares")
    out.append(f"  Coverage: {r.probes_run} mechanism(s) exercised. A writer no probe "
               "reaches was not examined.")
    if r.home_writers:
        out.append(f"  Outside the project: {len(r.home_writers)} declared home-writer(s) "
                   f"— {', '.join(Path(w).name for w in r.home_writers)}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", "--kit", dest="kit", type=Path, default=None,
                help="the kit root to sweep (default: this repo)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    # A DEFAULT on the `next()`. Without one it raises StopIteration when no ancestor
    # holds `squad/paths.py` — a copy of this file somewhere else in the tree, or an
    # install whose layout shifted — and a StopIteration out of `main` is a traceback
    # that names neither what was searched for nor where.
    kit = args.kit or next(
        (p for p in Path(__file__).resolve().parents
         if (p / "squad" / "paths.py").is_file()), None)
    if kit is None:
        print(f"UNCHECKED: no ancestor of {Path(__file__).resolve()} holds "
              f"squad/paths.py, so the kit root could not be resolved. Pass --kit. "
              f"Nothing was measured.", file=sys.stderr)
        return 2
    r = check(kit)
    print(json.dumps(r.__dict__, indent=2, default=str) if args.json else render(r))

    if r.unmeasured_because:
        return 2
    return 0 if r.contained else 1


if __name__ == "__main__":
    raise SystemExit(main())

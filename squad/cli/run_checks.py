"""`sq check` — replay what CI verifies, and name what it does not reach.

WHY THIS DOES NOT GLOB AND RUN
------------------------------
The obvious design is to glob `mechanisms/gates/check_*.py` and invoke each one. It is
not implementable: the root-path flag is not uniform across the 23 gates — eight take
`--root`, four `--repo-root`, three `--project-root`, one `--repo`, one
`--ecosystem-dir`, one a positional, `check_install_drift` needs both `--install` and
`--kit`, and three take none. `check_xrefs` also passes while printing WARN unless it
is given `--strict`.

So a glob-and-run would carry a table of seven flag conventions plus a special case —
a second list of what "verified" means, diverging from CI on the next gate added.
That is precisely what the ADR forbids.

Instead the invocations are REPLAYED from `.github/workflows/ci.yml`. `check_xrefs`
arrives with `--strict` because the flag lives in the workflow. "The CLI reaches
everything CI reaches" stops being a property somebody has to maintain and becomes
true by construction, and the glob is used only for the opposite question: which gates
CI never invokes.

WHEN CI EVENTUALLY CALLS THIS COMMAND
-------------------------------------
The ADR intends `ci.yml` to become `run: sq check --all`, at which point this
derivation eats itself. The reader is behind `gate_commands()` for that day: the
source of truth moves to a machine-readable file both sides read — the shape
`rules/cycle-phases.txt` already uses — and exactly one function changes. A reader who
meets the circularity in six months should not have to re-derive this paragraph.

Exit codes:
    0 — every replayed command passed
    1 — at least one failed
    2 — the workflow could not be read, or no command survived the filter
"""
from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from squad.cli.paths import resolve_roots
from squad.cli.provenance import describe
from squad.cli.render import emit
from squad.cli.report import FINDING, OK, UNMEASURED, Report


@dataclass(frozen=True)
class Command:
    """One command CI runs, with the step that carries it."""

    step: str
    argv: list[str]


@dataclass(frozen=True)
class Result:
    command: Command
    returncode: int
    tail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


#: Docstrings and comments, which is where PROSE lives. Short string literals are
#: deliberately KEPT: `verify_ecosystem.py` invokes its siblings by building a path —
#: `ecosystem_dir / "mechanisms" / "gates" / "check_skill_map.py"` — so the call site
#: IS a string, and stripping strings hid every one of them.
#:
#: `test_every_gate_is_reachable.py` strips more than this, and correctly: it is
#: answering "does anything call this gate", where a mention in a comment is a false
#: positive. This asks the narrower question "which gates does this script name in
#: code", where a filename in a string is the answer rather than the noise.
_PROSE_RE = re.compile(
    "|".join([
        r'"' * 3 + r"(?:.|\n)*?" + r'"' * 3,
        r"'" * 3 + r"(?:.|\n)*?" + r"'" * 3,
        r"#[^\n]*",
    ])
)


def reached_within(root: Path, scripts: list[str]) -> set[str]:
    """Gates named in the CODE of the scripts CI invokes — one level deep.

    `verify_ecosystem.py` runs eleven other gates, so reporting those as "not reached"
    because the workflow does not name them would be a half-truth in the direction
    this kit cares about most.

    One level, deliberately. A full call graph is a different tool, and stopping at a
    stated depth is honest where a partial graph presented as complete would not be.
    """
    gates = known_gates(root)
    found: set[str] = set()
    for script in scripts:
        path = root / script
        if not path.is_file() or path.suffix != ".py":
            continue
        try:
            code = _PROSE_RE.sub(" ", path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        found.update(name for name in gates if f"{name}.py" in code)
    return found


def known_gates(root: Path) -> set[str]:
    """Every gate on disk, by glob — never a list, which would go stale on the next one."""
    gates = root / "mechanisms" / "gates"
    return {
        p.stem
        for p in sorted(gates.glob("*.py"))
        if p.is_file() and not p.name.startswith("_")
    }


def gate_commands(workflow: Path, root: Path) -> list[Command]:
    """The workflow steps that invoke something tracked in this repository.

    Parsed as YAML rather than read line by line, because `run: |` is a multi-line
    scalar — `test_ci_targets_exist.py` reads lines and therefore cannot see the
    code-quality step at all.
    """
    try:
        import yaml
    except ImportError:
        # An inability, reported as one. Falling back to a hard-coded list here would
        # be the second list arriving through the back door.
        print("sq check: pyyaml is not installed, so the workflow could not be read",
              file=sys.stderr)
        return []

    try:
        data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"sq check: {workflow} could not be read: {exc}", file=sys.stderr)
        return []

    commands: list[Command] = []
    for job in (data or {}).get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            run = step.get("run")
            if not run:
                continue
            name = step.get("name", "(unnamed step)")
            for line in _statements(run):
                argv = _tokens(line)
                if argv and _names_a_tracked_file(argv, root):
                    commands.append(Command(step=name, argv=argv))
    return commands


def _statements(run: str) -> list[str]:
    """One shell statement per line, with continuations joined."""
    joined = run.replace("\\\n", " ")
    return [ln.strip() for ln in joined.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def _tokens(line: str) -> list[str]:
    # Command substitution and pipelines are not replayable as argv, and this command
    # replays rather than interprets. Skipping them is honest; the caller reports the
    # step as unreached rather than pretending it ran.
    if any(marker in line for marker in ("$(", "`", "|", "&&", ";")):
        return []
    try:
        return shlex.split(line)
    except ValueError:
        return []


def _names_a_tracked_file(argv: list[str], root: Path) -> bool:
    return any((root / token).is_file() for token in argv)


#: Tokens that are an interpreter rather than the thing being run.
_INTERPRETERS = frozenset({"python", "python3", "bash", "sh"})


def _label(command: Command) -> str:
    """The most useful name for a replayed command.

    The PROGRAM, not any argument that happens to end in `.py`: for
    `ruff check mechanisms squad skills hooks tests conftest.py` the only `.py` token is
    the last ARGUMENT, and showing it pointed a reader chasing a failure at a file that
    is not the subject. So the program is the first token, or the one after an
    interpreter — and when that is not a script this repository owns (`ruff`), the
    workflow's own step name says more than the binary does.
    """
    argv = command.argv
    program = argv[1] if len(argv) > 1 and argv[0] in _INTERPRETERS else argv[0]
    return program if program.endswith((".py", ".sh")) else command.step


def build_report(root: Path, *, results: list[Result], unreached: list[str]) -> Report:
    report = Report(
        verb="check",
        observed=[f"{len(results)} CI command(s) replayed", *describe(root)],
    )

    for result in results:
        verdict = "ok" if result.returncode == 0 else "FAIL"
        report.lines.append(f"  {verdict:>4}  {_label(result.command)}")
        if result.returncode != 0 and result.tail:
            report.lines.extend(f"          {ln}" for ln in result.tail.splitlines()[-3:])

    if unreached:
        report.not_checked.append(
            f"{len(unreached)} gate(s) THIS COMMAND does not reach — not invoked by the "
            f"workflow and not named in a script it invokes: {', '.join(sorted(unreached))}. "
            f"That is not the same as unreachable: hooks, the installer and other scripts "
            f"run some of them, and tests/test_every_gate_is_reachable.py answers THAT "
            f"question"
        )
    else:
        report.not_checked.append(
            "nothing — every gate on disk is reached, directly or one level in"
        )

    report.not_checked.append(
        "reachability is resolved ONE level deep: a gate a replayed script calls counts, "
        "a gate that script's callee calls does not"
    )
    report.not_checked.append(
        "the workflow's own correctness — this replays what ci.yml says, so a step "
        "missing from the workflow is missing here too"
    )

    failed = [r for r in results if r.returncode != 0]
    report.exit_code = FINDING if failed else OK
    report.detail["failed"] = [" ".join(r.command.argv) for r in failed]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sq check", description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list", action="store_true", help="the commands, without running them")
    parser.add_argument("--root", type=Path, default=_repo_root())
    parser.add_argument("--workflow", type=Path, default=None)
    args = parser.parse_args(argv)

    root: Path = args.root
    # The mechanisms live in the kit; the workflow lives in the PROJECT. Under a copy
    # install those are `<project>/.claude` and `<project>` — conflating them is how a
    # gate ends up reporting on a tree that is not there.
    where = resolve_roots(root)
    workflow = args.workflow or where.workflow()

    if workflow is None:
        print(f"sq check: no .github/workflows/ci.yml under {where.project} — "
              f"nothing to replay, so nothing was checked", file=sys.stderr)
        print("    this is expected in a consumer install, where the kit ships no workflow",
              file=sys.stderr)
        return UNMEASURED

    commands = gate_commands(workflow, where.kit)
    if not commands:
        # An empty list is not a pass. `run_gates.sh` carries the same refusal, for the
        # same reason: a sweep over nothing that reports success is the defect this kit
        # finds more than any other.
        print(f"sq check: no runnable command found in {workflow} — nothing was checked",
              file=sys.stderr)
        return UNMEASURED

    # Two jobs invoke the same runner; replaying it twice doubles the wall clock and
    # says nothing new.
    seen: set[tuple[str, ...]] = set()
    deduped: list[Command] = []
    for command in commands:
        key = tuple(command.argv)
        if key not in seen:
            seen.add(key)
            deduped.append(command)
    commands = deduped

    invoked = " ".join(" ".join(c.argv) for c in commands)
    scripts = [t for c in commands for t in c.argv if t.endswith(".py")]
    indirect = reached_within(where.kit, scripts)
    unreached = sorted(
        name for name in known_gates(where.kit) if name not in invoked and name not in indirect
    )

    if args.list:
        report = Report(verb="check", observed=[f"{len(commands)} command(s)", *describe(where.kit)])
        report.lines = [f"  {' '.join(c.argv)}" for c in commands]
        report.not_checked.append(
            f"{len(unreached)} gate(s) not reached directly or one level in: "
            f"{', '.join(unreached)}"
            if unreached else "nothing — every gate is reached"
        )
        return emit(report, as_json=args.json)

    results: list[Result] = []
    for command in commands:
        done = subprocess.run(  # noqa: PLW1510
            command.argv, capture_output=True, text=True, cwd=where.kit
        )
        results.append(Result(command, done.returncode, (done.stdout + done.stderr).strip()))

    return emit(build_report(where.kit, results=results, unreached=unreached), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())

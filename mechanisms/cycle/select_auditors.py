#!/usr/bin/env python3
"""Which independent auditors must run on this change, derived rather than chosen.

    python3 mechanisms/cycle/select_auditors.py --slug B-014 \
        --domains security,testing --diff-base develop --write

## The rule this exists to hold

The reviewing agent does not pick its own auditor. `detect_domain.py` already derives
the domain from the plan and the changed paths; that derivation selects the auditors,
and the agent may only WIDEN it.

The reason is the one the review panel already enforces by refusing to seat an author:
the CHOICE is itself a judgement. Point a concurrency change at `loop-doc-audit` and
the report comes back clean, honestly, having examined nothing that mattered — and an
independent report about the wrong thing is worse than no report, because it reads as
coverage.

## What it produces, and what it cannot

It produces the assignment: which plugins must audit this change, with the exact
command each one takes, the scope flag, and where its report must land. It does NOT
run them. A `loop-*` plugin is an agentic halt-loop driven by a stop hook, so a Python
mechanism can decide what must run and refuse to accept its absence, but it cannot be
the thing that runs it — the same split `convene_panel.py` takes with the panel.

`check_auditor_coverage.py` is the other half, and it is where the refusal lives.

## Scope

Every plugin accepts `--diff-base` / `--pr` / `--commits`, and REVIEW audits a change,
not a repository. So the scope is passed — but which ref is NEVER guessed. Guessing a
base is how `sq test --touched` once selected 792 files on a branch 335 commits ahead;
an unscoped run is a defensible answer and a silently wrong scope is not. Without
`--diff-base` the assignment says the audit covers the whole tree, in writing.

Exit codes, matching the rest of the cycle:
  0  selected (including "nothing declared", which is stated, never silent)
  1  the registry is wrong — a row that does not describe an auditor
  2  the registry could not be read; nothing was selected, and that is not a pass
  3  a required plugin is not installed HERE — an `access` impediment, not a defect
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conventions"))

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from installed_plugins import Plugin
from installed_plugins import load as load_plugins

from squad.paths import write_records_dir

OK, INVALID, UNREADABLE, NOT_INSTALLED = 0, 1, 2, 3

#: An auditor mapped to this pseudo-domain runs whatever the change is about.
ALWAYS = "always"

#: Declared by each plugin; recorded so a scoped REVIEW is never read as a full audit.
DIFF_MODES = ("analysis-scoped", "report-filtered")

DEFAULT_REPORT_GLOB = "final_report.md"


@dataclass(frozen=True)
class Auditor:
    """One declared mapping: this domain is audited by this plugin, that way."""

    domain: str
    plugin: str
    diff_mode: str
    report_glob: str = DEFAULT_REPORT_GLOB

    def output_dir(self, project: Path) -> Path:
        """Where this auditor's report must land.

        DERIVED, not declared. The registry used to carry each plugin's own default
        (`code-review-output/`, `security-output/`), which put a third party's output at
        the project root — outside the one write root, on the kit's own instruction.
        A tool the kit tells where to write is a tool the kit is responsible for.
        """
        return write_records_dir(project, "audits") / self.plugin


def registry_path(project: Path) -> Path:
    """The registry is a RULE, so it lives with the kit — not under the write root.

    `.squad/` holds only what the system produces; a rule the project configures is an
    input, and putting it there would make the one write root a mixed directory.
    """
    for base in (project / ".claude" / "rules", project / "rules"):
        if (base / "review-auditors.txt").is_file():
            return base / "review-auditors.txt"
    return project / "rules" / "review-auditors.txt"


def parse_registry(text: str) -> list[Auditor]:
    """Every declared auditor, in file order.

    Raises ValueError on a row that announces an auditor and does not describe one: a
    half-written row must never parse to "no auditor" and read as a domain nobody
    needed to audit.
    """
    out: list[Auditor] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or not line.startswith("auditor"):
            continue
        _, _, value = line.partition("=")
        parts = [p.strip() for p in value.split("|")]
        if len(parts) not in (3, 4) or not all(parts[:3]):
            raise ValueError(
                f"malformed auditor row: {raw.strip()!r} — expected `auditor = "
                "<domain> | <plugin> | <diff-mode> | [report glob]`")
        if parts[2] not in DIFF_MODES:
            raise ValueError(
                f"unknown diff mode {parts[2]!r} in {raw.strip()!r}; the plugin "
                f"declares one of {DIFF_MODES}. Recording the wrong one would let a "
                "diff-only analysis be read as a whole-tree one")
        out.append(Auditor(domain=parts[0].lower(), plugin=parts[1],
                           diff_mode=parts[2],
                           report_glob=parts[3] if len(parts) == 4 else DEFAULT_REPORT_GLOB))
    return out


def required_for(auditors: list[Auditor], domains: list[str]) -> list[Auditor]:
    """The auditors this change must face: its domains, plus the always-on ones.

    De-duplicated by plugin, because two domains mapping to one plugin is one audit —
    `database` and `concurrency` both reach `loop-performance-audit`, and running it
    twice would buy a second copy of the same report.
    """
    wanted = {d.strip().lower() for d in domains if d.strip()} | {ALWAYS}
    seen: dict[str, Auditor] = {}
    for a in auditors:
        if a.domain in wanted:
            seen.setdefault(a.plugin, a)
    return [seen[k] for k in sorted(seen)]


#: The three ways a change can be named, in the plugins' own vocabulary. Naming two at
#: once is a usage error there — which would win is undefined — so it is one here too.
SCOPE_FLAGS = ("diff_base", "pr", "commits")


def scope_flag(scope: dict) -> str:
    """The plugin flag for this scope, or empty for a whole-tree run."""
    if scope.get("diff_base"):
        return f" --diff-base {scope['diff_base']}"
    if scope.get("pr"):
        return f" --pr {scope['pr']}"
    if scope.get("commits"):
        return f" --commits {scope['commits']}"
    return ""


def command_for(a: Auditor, *, target: str, scope: dict, project: Path) -> str:
    """The exact invocation, so nobody has to reconstruct it from prose."""
    return (f"/{a.plugin} {target} --output-dir {a.output_dir(project)}"
            f"{scope_flag(scope)}")


def select(
    slug: str,
    domains: list[str],
    *,
    project: Path,
    diff_base: str | None = None,
    pr: str | None = None,
    commits: str | None = None,
    target: str = ".",
    config_dir: Path | None = None,
) -> tuple[int, dict]:
    named = [n for n, v in (("--diff-base", diff_base), ("--pr", pr),
                            ("--commits", commits)) if v]
    if len(named) > 1:
        return INVALID, {
            "status": "invalid",
            "detail": f"the change is named twice ({', '.join(named)}). Which one wins "
                      "is undefined in the plugins and would be undefined here — pick "
                      "the one that describes the change",
        }

    path = registry_path(project)
    try:
        auditors = parse_registry(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return UNREADABLE, {"status": "unreadable", "detail": f"{path}: {exc}"}
    except ValueError as exc:
        return INVALID, {"status": "invalid", "detail": str(exc)}

    if not auditors:
        return OK, {
            "status": "none_declared", "slug": slug, "domains": domains,
            "detail": f"{path} declares no auditor. No independent audit is required "
                      "for this REVIEW — stated here rather than left to be inferred "
                      "from an empty result",
        }

    required = required_for(auditors, domains)
    installed = load_plugins(config_dir)

    scope_spec = {"diff_base": diff_base, "pr": pr, "commits": commits}

    def row(a: Auditor, p: Plugin | None) -> dict:
        return {
            "plugin": a.plugin, "domain": a.domain, "diff_mode": a.diff_mode,
            "output_dir": str(a.output_dir(project)),
            "report_glob": a.report_glob,
            "installed": p is not None,
            "install_path": str(p.install_path) if p else None,
            "version": p.version if p else None,
            "command": command_for(a, target=target, scope=scope_spec,
                                   project=project),
        }

    rows = [row(a, installed.get(a.plugin)) for a in required]
    missing = [r["plugin"] for r in rows if not r["installed"]]

    scope = ({"kind": "change", **scope_spec,
              "named_by": named[0],
              "detail": "each auditor applies its own declared diff_mode to this scope"}
             if named else
             {"kind": "whole_tree", **scope_spec, "named_by": None,
              "detail": "the change was not named, so this audit covers the WHOLE TREE "
                        "and must not be reported as a review of the change"})

    body = {
        "status": "selected", "slug": slug, "domains": sorted(set(domains)),
        "scope": scope, "required": rows,
        "missing_plugins": missing,
        "derived_by": "rules/review-auditors.txt — widening is allowed, narrowing is not",
    }
    if missing:
        body["status"] = "not_installed"
        body["detail"] = (
            f"{len(missing)} required auditor(s) are not installed here: "
            f"{', '.join(missing)}. That is a coverage gap and an `access` impediment "
            "for halt_disposition.py — NOT a clean review, and not a defect in the code")
        return NOT_INSTALLED, body
    return OK, body


def assignment_path(project: Path, slug: str) -> Path:
    return write_records_dir(project, "audits") / f"{slug}-auditors.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--domains", default="",
                    help="comma-separated, from detect_domain.py. The agent may add, "
                         "never remove")
    ap.add_argument("--diff-base", default=None,
                    help="audit the change against this ref. Omit every scope flag for "
                         "a whole-tree audit, which the assignment then says in writing")
    ap.add_argument("--pr", default=None, help="audit pull request N")
    ap.add_argument("--commits", default=None, help="audit the range A..B")
    ap.add_argument("--target", default=".")
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--config-dir", type=Path, default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, result = select(args.slug, args.domains.split(","), project=args.project,
                          diff_base=args.diff_base, pr=args.pr, commits=args.commits,
                          target=args.target, config_dir=args.config_dir)

    if args.write and result["status"] in ("selected", "not_installed"):
        out = assignment_path(args.project, args.slug)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["written_to"] = str(out)

    if args.json:
        print(json.dumps(result, indent=2))
        return code

    status = result["status"]
    if status in ("selected", "not_installed"):
        print(f"{len(result['required'])} auditor(s) required for {args.slug} "
              f"[{', '.join(result['domains']) or 'no domain'}]")
        print(f"scope: {result['scope']['kind']} — {result['scope']['detail']}")
        for r in result["required"]:
            mark = "•" if r["installed"] else "✗"
            print(f"  {mark} {r['plugin']:<24} {r['diff_mode']:<16} {r['command']}")
        if "written_to" in result:
            print(f"assignment: {result['written_to']}")
        if status == "not_installed":
            print(result["detail"], file=sys.stderr)
    else:
        stream = sys.stdout if status == "none_declared" else sys.stderr
        print(f"{status}: {result['detail']}", file=stream)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

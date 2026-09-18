#!/usr/bin/env python3
"""Refuse a REVIEW whose required independent audits did not happen.

    python3 mechanisms/gates/check_auditor_coverage.py --slug B-014

## Absence is not coverage

The failure this exists to stop is the one the review panel's missing record stops, in
a different phase: a REVIEW that skipped its auditors must not be indistinguishable
from one where every auditor came back clean. A required audit that left no report did
not pass — it did not run.

## The report contract is the plugins', not a copy of it

Every `loop-*` plugin already validates its own report against a nine-section contract
(`scripts/lib/report_schema.md`) with a per-plugin catalog config
(`report-schema.local.txt`, under that plugin's own rules directory). This gate runs
THAT checker, from THAT plugin's install path, rather than reimplementing the sections
here.

The paths above are the PLUGIN's, never this repository's — spelled without a leading
directory because `check_xrefs` reads such a token in a `.py` file as a path here, and
would report a broken reference for a file that correctly lives somewhere else.

A second copy of a contract is a second source of truth, and the two diverge on the
day the contract changes — which for THIS contract would mean the kit accepting a
report shape the plugin itself rejects. `installed_plugins.py` makes the plugin's own
checker reachable, so there is no reason to guess.

## What travels, and what would be lost at the seam

Two sections are carried out of every report on purpose:

  `## What Was NOT Analyzed`   never omitted by contract, and the single thing that
                               stops partial coverage reading as complete. An
                               integration that drops it turns two honest halves into
                               a dishonest whole.
  `## Verdict`                 the plugin's own computed token, quoted rather than
                               re-asserted. This gate does not re-grade another tool's
                               finding; it reports what that tool concluded.

## Why severity is a signal here and not a gate

An earlier draft blocked on Critical findings, read from the report's fixed
`### Critical` subsection. That is a parse of another tool's markdown, and the smoke
run showed it immediately: a subsection holding an empty table plus the sentence
"_(none)_ unless critical findings were registered" is not decidable by prefix, and a
gate that guesses wrong here is either permanently red or silently permissive.

The finding stores would be decidable — the plugins persist to SQLite — but the
database name and schema differ per plugin and are not declared to consumers, so
reading them would be a second copy of another project's internals, drifting silently.
That is the same trap this gate refuses in the report contract.

So severity is EXTRACTED, carried, and labelled a signal. This kit's governing
sentence cuts both ways: an inability to measure must not become a passing
measurement, and it must not become a failing one either.

What still has teeth is fully decidable: a required audit that left no report, and a
report the plugin's OWN checker rejects.

## What this gate does NOT judge

Whether the audit had teeth. A plugin whose tools were all absent still writes a
well-formed report — the contract requires `## Scope & Methodology` to name what was
requested and unavailable, so the body is carried out verbatim for a reader, and this
gate says plainly that it did not assess it. A gate that examined nothing must not
print a verdict about everything.

Exit codes:
  0  every required audit produced a well-formed report
  1  a required report is missing or malformed
  2  the assignment or a checker could not be read; nothing was verified, not a pass
  3  a required plugin is not installed HERE — an `access` impediment

Severity is CARRIED, never gated. Rows 0 and 1 said "and none reports Critical" and
"or carries Critical findings" until 2026-09-17, describing a gate the section above
argues against and the code never had: `severity_counts()` becomes `severity_signal`
in the result and `main` prints it as "(not a gate)", and nothing appends to `failing`
because of it. A reader who trusted the table believed a Critical finding would stop
a review here; it does not, and the row that says so is the only thing that changed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cycle"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conventions"))

from installed_plugins import load as load_plugins
from select_auditors import assignment_path, parse_registry, registry_path

COVERED, NOT_COVERED, UNCHECKED, NOT_INSTALLED = 0, 1, 2, 3

#: The contract's sentinel for a subsection that found nothing. Matched as a prefix
#: because plugins append a reason ("_(none — no findings above Low)_").
_NONE_SENTINEL = "_(none"

_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_H3 = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)

SEVERITIES = ("Critical", "High", "Medium", "Low", "Info")


def section(text: str, header: str, pattern: re.Pattern[str] = _H2) -> str | None:
    """The body under one header, or None when the header is absent."""
    marks = [(m.start(), m.end(), m.group(1)) for m in pattern.finditer(text)]
    for i, (_, end, name) in enumerate(marks):
        if name.strip().lower() == header.strip().lower():
            stop = marks[i + 1][0] if i + 1 < len(marks) else len(text)
            return text[end:stop].strip()
    return None


def severity_counts(text: str) -> dict[str, bool]:
    """Which severity subsections carry findings.

    Presence, not a count: the contract fixes the five subsections and the sentinel
    for an empty one, so "has findings" is decidable without parsing each finding —
    and parsing another tool's findings by regex is exactly the fragile join this
    integration must not build.
    """
    body = section(text, "Findings by Severity") or ""
    out: dict[str, bool] = {}
    for sev in SEVERITIES:
        sub = section(body, sev, _H3)
        out[sev] = bool(sub) and not sub.lstrip().startswith(_NONE_SENTINEL)
    return out


def validate_with_plugin(install_path: Path, report: Path) -> tuple[bool, str]:
    """Run the plugin's own report checker. (ok, detail)."""
    checker = install_path / "scripts" / "lib" / "verify_report_format.py"
    config = install_path / "rules" / "report-schema.local.txt"
    if not checker.is_file() or not config.is_file():
        return False, (f"the plugin ships no report checker at {checker} — its report "
                       "cannot be validated against its own contract, and accepting it "
                       "unchecked would be the copy this gate refuses to make")
    try:
        proc = subprocess.run(
            [sys.executable, str(checker), "--report", str(report),
             "--schema-config", str(config)],
            capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run the plugin's checker: {exc}"
    if proc.returncode == 0:
        return True, "valid against the plugin's own report contract"
    detail = (proc.stdout or proc.stderr or "").strip()
    return False, f"the plugin's own checker rejected the report: {detail[:400]}"


def find_report(project: Path, output_dir: str, glob: str) -> Path | None:
    # The assignment carries an absolute path derived from the write root; a relative
    # one is still accepted so an older assignment on disk keeps resolving.
    base = Path(output_dir)
    if not base.is_absolute():
        base = project / output_dir
    if not base.is_dir():
        return None
    hits = sorted(base.glob(glob))
    return hits[-1] if hits else None


def check(slug: str, *, project: Path, config_dir: Path | None = None) -> tuple[int, dict]:
    # The REGISTRY is consulted first, and the order matters. A project that declares
    # no auditor has no coverage to be missing, whatever the assignment says — asking
    # for the assignment first turned "this project requires no independent audit" into
    # "this review skipped one", and every consumer without the registry would have
    # been blocked for a step nobody asked it to take.
    reg = registry_path(project)
    try:
        declared = parse_registry(reg.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # The one OSError that means what the branch below says: the project never
        # wrote a registry. Every OTHER OSError used to land here too — a permission
        # bit, a directory in the file's place, an I/O error — and an empty list two
        # lines down became COVERED with the detail "Stated, never inferred from an
        # empty result". It was inferred from an empty result, and the gate that exists
        # to prove an audit happened answered "none required" when it could not read
        # which audits are required.
        declared = []
    except OSError as exc:
        return UNCHECKED, {"status": "unchecked", "slug": slug,
                           "detail": f"cannot read {reg}: {type(exc).__name__}: {exc}"}
    except ValueError as exc:
        return UNCHECKED, {"status": "unchecked", "slug": slug,
                           "detail": f"cannot read {reg}: {exc}"}
    if not declared:
        return COVERED, {
            "status": "none_declared", "slug": slug,
            "detail": f"{reg} declares no auditor, so this REVIEW requires no "
                      "independent audit. Stated, never inferred from an empty result",
        }

    path = assignment_path(project, slug)
    if not path.is_file():
        return UNCHECKED, {
            "status": "no_assignment", "slug": slug, "expected": str(path),
            "detail": "no auditor assignment. Nothing states which independent audits "
                      "this change required, so nothing can say they happened. Run "
                      "`select_auditors.py --write` before the audits, not after",
        }
    try:
        assignment = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return UNCHECKED, {"status": "unchecked", "slug": slug,
                           "detail": f"cannot read {path}: {exc}"}

    if assignment.get("status") == "none_declared":
        return COVERED, {"status": "none_declared", "slug": slug,
                         "detail": assignment.get("detail", "")}

    installed = load_plugins(config_dir)
    results, missing_plugin, failing = [], [], []

    for req in assignment.get("required", []):
        name = req["plugin"]
        plugin = installed.get(name)
        entry = {"plugin": name, "domain": req.get("domain"),
                 "diff_mode": req.get("diff_mode")}

        if plugin is None:
            entry.update(state="not_installed",
                         detail="the plugin is not installed on this machine")
            missing_plugin.append(name)
            results.append(entry)
            continue

        report = find_report(project, req["output_dir"], req.get("report_glob", "final_report.md"))
        if report is None:
            entry.update(state="no_report",
                         expected=str(project / req["output_dir"] / req.get("report_glob", "final_report.md")),
                         detail="the audit was required and left no report. It did not "
                                "pass — it did not run")
            failing.append(name)
            results.append(entry)
            continue

        ok, detail = validate_with_plugin(plugin.install_path, report)
        text = report.read_text(encoding="utf-8", errors="replace")
        sev = severity_counts(text)
        entry.update(
            report=str(report),
            well_formed=ok,
            validation=detail,
            verdict=(section(text, "Verdict") or "").strip()[:300],
            not_analyzed=(section(text, "What Was NOT Analyzed") or "").strip()[:800],
            methodology=(section(text, "Scope & Methodology") or "").strip()[:800],
            # A SIGNAL, not a measurement — see the module docstring. Reported so a
            # reader acts on it, never used to pass or fail this gate.
            severity_signal=[s for s, has in sev.items() if has],
        )
        if not ok:
            entry["state"] = "malformed"
            failing.append(name)
        else:
            entry["state"] = "covered"
        results.append(entry)

    body = {
        "slug": slug,
        "scope": assignment.get("scope"),
        "auditors": results,
        "not_checked": [
            "SEVERITY — `severity_signal` is read off the report's markdown, and the "
            "contract's empty-subsection sentinel is not decidable by prefix. It is "
            "carried for a reader and never gates this result",
            "whether the audit had TEETH — a plugin whose tools were all absent still "
            "writes a well-formed report; `methodology` carries what each one says it "
            "used, unread by this gate",
            "the findings themselves — they are the plugin's, quoted rather than "
            "re-graded here",
        ],
    }
    if missing_plugin:
        body.update(status="not_installed", missing=missing_plugin,
                    detail=f"{len(missing_plugin)} required auditor(s) not installed: "
                           f"{', '.join(missing_plugin)}. A coverage gap and an "
                           "`access` impediment — never a clean review")
        return NOT_INSTALLED, body
    if failing:
        body.update(status="not_covered", failing=failing,
                    detail=f"{len(failing)} required audit(s) did not clear: "
                           f"{', '.join(failing)}")
        return NOT_COVERED, body
    body.update(status="covered",
                detail=f"{len(results)} independent audit(s) ran and reported")
    return COVERED, body


def _finding(title: str, evidence: str, remediation: str) -> dict:
    return {
        "severity": "BLOCKER",
        "category": "auditor-coverage",
        "title": title,
        "evidence": evidence,
        "remediation": remediation,
        "source": "check_auditor_coverage",
    }


def auditor_coverage_findings(project: Path, slug: str,
                              config_dir: Path | None = None) -> list[dict]:
    """The coverage gap as BLOCKER findings, for `consolidate_findings.py`.

    The shape `check_upstream_gate.py` established, and for the reason it argued: a
    pre-condition returned as findings means the review verdict CANNOT be computed
    while ignoring it. A separate step would have the same weakness as the prose it
    replaced — somebody has to remember to invoke it.
    """
    code, result = check(slug, project=project, config_dir=config_dir)
    status = result.get("status")

    if status == "none_declared":
        # The project declared, in writing, that it requires no independent audit.
        # Visible opt-out, not a silent one.
        return []

    if status in ("no_assignment", "unchecked"):
        return [_finding(
            "The required independent audits are unaccounted for",
            result.get("detail", ""),
            "Run `select_auditors.py --slug <slug> --domains <from detect_domain.py> "
            "--diff-base <ref> --write` BEFORE the audits, then run each command it "
            "prints. Nothing can say an audit happened if nothing said it was required.",
        )]

    out: list[dict] = []
    for a in result.get("auditors", []):
        state = a.get("state")
        if state == "covered":
            continue
        if state == "not_installed":
            out.append(_finding(
                f"Required auditor `{a['plugin']}` is not installed",
                f"domain `{a.get('domain')}` maps to `{a['plugin']}` in "
                "rules/review-auditors.txt, and this machine does not have it. The "
                "audit did not happen; it did not pass.",
                f"Install `{a['plugin']}`, or remove its row from "
                "`rules/review-auditors.txt` — that file is the project's, the "
                "installer preserves it, and dropping a row is a visible decision to "
                "stop requiring that audit rather than a silent gap.",
            ))
        elif state == "no_report":
            out.append(_finding(
                f"Required audit `{a['plugin']}` left no report",
                f"expected at {a.get('expected')}",
                f"Run the command the assignment prints for `{a['plugin']}`. A "
                "required audit with no report did not pass — it did not run.",
            ))
        elif state == "malformed":
            out.append(_finding(
                f"Report from `{a['plugin']}` fails that plugin's own contract",
                f"{a.get('report')}: {a.get('validation')}",
                "Re-run the audit to completion. A report its own checker rejects "
                "cannot be read as evidence the audit finished.",
            ))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument(
        "--root", "--project", dest="root", type=Path, default=Path.cwd())
    ap.add_argument("--config-dir", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    code, result = check(args.slug, project=args.root, config_dir=args.config_dir)
    if args.json:
        print(json.dumps(result, indent=2))
        return code

    status = result["status"]
    if status in ("no_assignment", "unchecked", "none_declared"):
        print(f"{status}: {result['detail']}",
              file=sys.stdout if status == "none_declared" else sys.stderr)
        return code

    print(f"auditor coverage: {status.upper()} — {result['detail']}")
    for a in result["auditors"]:
        mark = {"covered": "✓", "malformed": "✗",
                "no_report": "✗", "not_installed": "⊘"}.get(a["state"], "?")
        print(f"  {mark} {a['plugin']:<24} {a['state']}")
        if a.get("verdict"):
            print(f"      verdict: {a['verdict'].splitlines()[0][:100]}")
        if a.get("severity_signal"):
            print(f"      severity signal (not a gate): {', '.join(a['severity_signal'])}")
        if a.get("not_analyzed"):
            first = a["not_analyzed"].splitlines()[0][:100]
            print(f"      NOT analyzed: {first}")
    print("\nNOT CHECKED:")
    for n in result["not_checked"]:
        print(f"  {n}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

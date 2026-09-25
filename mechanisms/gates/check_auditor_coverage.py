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

What still has teeth is fully decidable: a required audit that left no report, a
report the plugin's OWN checker rejects, and a report that says its own run stopped
before the report phase (`Status: INCOMPLETE`, written by the plugins' shared
termination guard). The last one is well-formed by design, which is exactly why
structural validity alone recorded an audit stopped on its iteration cap as covered.

## What this gate does NOT judge

Whether the audit had teeth. A plugin whose tools were all absent still writes a
well-formed report — the contract requires `## Scope & Methodology` to name what was
requested and unavailable, so the body is carried out verbatim for a reader, and this
gate says plainly that it did not assess it. A gate that examined nothing must not
print a verdict about everything.

Exit codes:
  0  every required audit produced a well-formed report
  1  a required report is missing, malformed, or says its run stopped INCOMPLETE
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from installed_plugins import load as load_plugins
from select_auditors import assignment_path, parse_registry, registry_path

from squad.paths import rules_dir

COVERED, NOT_COVERED, UNCHECKED, NOT_INSTALLED = 0, 1, 2, 3

#: The contract's sentinels for a subsection that holds no finding. Matched as a prefix
#: because plugins append a reason ("_(none — no findings above Low)_"). The second is
#: the termination guard's: a run stopped on its cap writes "_(not enumerated — run did
#: not reach the report phase)_" under every severity, and reading that as a finding
#: labelled a report that enumerated nothing with all five severities.
_EMPTY_SENTINELS = ("_(none", "_(not enumerated")

#: How the plugins' shared termination guard (`terminal_report.py`, `render_fallback`)
#: marks a run that stopped before its report phase: `- **Status:** INCOMPLETE` in the
#: metadata, and a `## Verdict` that opens with the token. Either is enough.
_STATUS_INCOMPLETE = re.compile(r"^\s*-\s*\*\*Status:\*\*\s*`?INCOMPLETE\b", re.MULTILINE)
_VERDICT_INCOMPLETE = re.compile(r"^`?INCOMPLETE\b")
_STOP_CONDITION = re.compile(r"on condition\s+`([^`]+)`")

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
        out[sev] = bool(sub) and not sub.lstrip().startswith(_EMPTY_SENTINELS)
    return out


def stopped_before_its_report(text: str) -> str | None:
    """The stop condition when this report says its run did not finish, else None.

    This is the one reading of another tool's markdown this gate makes a decision on,
    and it is narrow on purpose: the marker is written by ONE shared function, copied
    bit-for-bit into every plugin and drift-checked there, and it is the report saying
    about itself that no verdict was computed. Structural validity cannot see it — the
    fallback is well-formed by design, so an honest "I did not finish" passed as a
    finished audit. Returns "unknown" when the run says it stopped and not why.
    """
    verdict = section(text, "Verdict") or ""
    if not (_STATUS_INCOMPLETE.search(text) or _VERDICT_INCOMPLETE.match(verdict.lstrip())):
        return None
    found = _STOP_CONDITION.search(verdict)
    return found.group(1) if found else "unknown"


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


#: The contract the plugin side emits, negotiated 2026-09-22. Version bumps when the
#: SHAPE changes; a reader that meets an unknown one refuses rather than taking the
#: fields it recognises, because reading part of an unknown shape is guessing at the rest.
VERDICT_FILE = "verdict.json"
VERDICT_SCHEMA = 1


def read_verdict(output_dir: Path) -> dict:
    """What the plugin says its verdict is, and whether this gate may act on it.

    THE DISTINCTION THIS EXISTS FOR. The plugins session measured all seventeen: five
    compute the verdict in a script, twelve derive it in the agent from a declared query
    over persisted findings. **None asserts one freehand** — that correction came from
    the measurement and neither of us had assumed it. What differs is who runs the
    derivation, and the two carry different guarantees:

        source: computed          a script produced it. Gateable.
        source: derived-by-agent  a model produced it, following the rule in its `.md`.
                                  Carried and reported, never gated on — the treatment
                                  `severity_signal` already has, for the same reason.

    `computed` WITHOUT `by` IS DEMOTED. The plugin's `emit_verdict.py` requires `--by`
    with `--source computed` and refuses the emit without it, so a file carrying
    `computed` and no `by` was not written by that emitter; it is indistinguishable
    from one typed by a model that read the contract, which is the confusion `source`
    exists to end.

    AN ABSENT FILE IS `verdict_not_exposed`, never "no findings". Sixteen of seventeen
    plugins are in that state today. That is the same distinction this gate already
    draws between `not_installed` and `no_report`: did not happen, versus happened and
    passed.

    WHAT THIS DOES NOT CLAIM. `computed` proves a script produced the token. It does not
    prove the script is right — correctness stays with the plugin, where
    `verify_report_format.py` says it stays. Written down because a gate of this kit was
    overread exactly that way on the same day.
    """
    path = Path(output_dir) / VERDICT_FILE
    if not path.is_file():
        return {"state": "verdict_not_exposed", "gateable": False, "verdict": None,
                "detail": f"no {VERDICT_FILE} beside the report; this plugin exposes no "
                          f"decidable verdict, which is not the same as reporting none"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"state": "verdict_not_exposed", "gateable": False, "verdict": None,
                "detail": f"{VERDICT_FILE} could not be read: {error}"}
    if not isinstance(payload, dict):
        return {"state": "verdict_not_exposed", "gateable": False, "verdict": None,
                "detail": f"{VERDICT_FILE} is not an object"}
    if payload.get("schema") != VERDICT_SCHEMA:
        return {"state": "verdict_not_exposed", "gateable": False, "verdict": None,
                "detail": f"{VERDICT_FILE} declares schema {payload.get('schema')!r} and "
                          f"this gate reads {VERDICT_SCHEMA}; reading the fields it "
                          f"recognises would be guessing at the rest"}

    source = payload.get("source")
    verdict = payload.get("verdict")
    if not verdict or source not in ("computed", "derived-by-agent"):
        return {"state": "verdict_not_exposed", "gateable": False, "verdict": None,
                "detail": f"{VERDICT_FILE} names source {source!r} and verdict "
                          f"{verdict!r}; both are required"}

    by = payload.get("by")
    if source == "computed" and not by:
        return {"state": "derived-by-agent", "gateable": False, "verdict": verdict,
                "blocking_count": payload.get("blocking_count"),
                "detail": "declares `computed` and names no `by`, so the stronger "
                          "guarantee is not demonstrated and this reads as the weaker one"}

    return {"state": source, "gateable": source == "computed", "verdict": verdict,
            "by": by, "blocking_count": payload.get("blocking_count"),
            "detail": f"{source}" + (f" by {by}" if by else "")}


def find_report(project: Path, output_dir: str, glob: str,
                *, commissioned_at: float | None = None) -> Path | None:
    """The audit report for this run, or None.

    `commissioned_at` is when the ASSIGNMENT was written — when somebody asked for the
    audit. A report older than that cannot be the audit that was asked for: it existed
    before the request. That is an ordering fact this gate already holds both sides of.

    It was globbing a directory and taking a hit, with no mtime, no commit and no diff
    base. Measured on a consumer 2026-09-18: the gate reported COVERED with "2 blocking
    findings" by reading a report written **2h45 earlier** by a different run, while the
    audit for the change under review sat in a sibling directory with 4.

    `cycle-review.md` names the neighbouring risk exactly — "an independent report about
    the wrong thing is worse than no report, because it reads as coverage". This is that
    sentence with the axis swapped: right report, wrong change.

    WHAT THIS DOES NOT CLAIM. A report newer than the assignment may still be about the
    wrong change, and proving otherwise needs a `diff_base` the plugin would have to
    declare — and the report contract is the plugin's, which `cycle-review.md` protects
    on purpose. The gate verifies the half it can and reports that half, rather than the
    stronger claim it cannot support.

    `commissioned_at=None` keeps the old behaviour for callers that have no assignment
    time. A gate that started refusing every report it could not date would be routed
    around, and routed-around is worse than narrow.
    """
    # The assignment carries an absolute path derived from the write root; a relative
    # one is still accepted so an older assignment on disk keeps resolving.
    base = Path(output_dir)
    if not base.is_absolute():
        base = project / output_dir
    if not base.is_dir():
        return None
    hits = sorted(base.glob(glob))
    if not hits:
        return None
    report = hits[-1]
    if commissioned_at is None:
        return report
    try:
        written = report.stat().st_mtime
    except OSError:
        # Cannot date it, so cannot refuse it on age. Same reasoning as the None case.
        return report
    return report if written >= commissioned_at else None


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
        #
        # That argument was made for every OSError EXCEPT this one, and the exception
        # had a hole: an absent file usually means the project declined to declare
        # auditors, and sometimes means the gate was handed a root that is not a
        # project. WHERE it was absent from separates the two. A tree carrying no
        # `rules/` at all is not a project that declined — it is a root nobody should
        # be asking, and answering "none required" for it is the same false clearance
        # one level up.
        #
        # Measured on a consumer 2026-09-18: `_project_root_for` returned
        # `<project>/.squad`, the registry was looked for under `.squad/rules/`, and
        # `/review` emitted READY_TO_MERGE_WITH_FOLLOWUPS on a change whose two
        # required audits had never run — with no mention of them in the report.
        if not _looks_like_a_project(project):
            return UNCHECKED, {
                "status": "unchecked", "slug": slug,
                "detail": f"{project} carries no `rules/` directory, so this is not a "
                          f"project root and {reg} being absent proves nothing. The "
                          f"gate was pointed at the wrong tree — it has NOT established "
                          f"that no audit is required"}
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
        # When the audit was COMMISSIONED. A report older than this existed before
        # anyone asked for it, so it cannot be the audit the assignment describes.
        try:
            commissioned_at = path.stat().st_mtime
        except OSError:
            commissioned_at = None
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

        report = find_report(project, req["output_dir"],
                             req.get("report_glob", "final_report.md"),
                             commissioned_at=commissioned_at)
        if report is None:
            entry.update(state="no_report",
                         expected=str(project / req["output_dir"] / req.get("report_glob", "final_report.md")),
                         detail="the audit was required and left no report from this "
                                "run. It did not pass — it did not run, or what is "
                                "there predates the assignment that asked for it")
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
        # The decidable verdict, when the plugin exposes one. Read from a file beside
        # the report rather than parsed out of it: this gate has never parsed another
        # project's markdown for a decision, and the contract exists so it never has to.
        entry["verdict_record"] = read_verdict(project / req["output_dir"])
        # A script that COUNTED blocking findings is a decision this gate may act on;
        # a model's derivation, or a plugin with no notion of blocking (`null`), is
        # not. Kept beside `state` rather than folded into it: the audit ran and
        # reported either way, and what it found is a separate fact from that.
        record = entry["verdict_record"]
        count = record.get("blocking_count")
        entry["blocking_verdict"] = bool(
            record.get("gateable") and isinstance(count, int) and count > 0)
        stopped_on = stopped_before_its_report(text)
        if stopped_on is not None:
            # Checked BEFORE `ok`. A run that stopped on its cap did not happen in the
            # sense that matters, whatever the checker says about its shape: three
            # plugins reject the fallback today over an unrelated Scoring Card defect,
            # and the finding then blamed a malformed report. Fixing that plugin-side
            # must not turn them into `covered`.
            entry["state"] = "incomplete"
            entry["stopped_on"] = stopped_on
            failing.append(name)
        elif not ok:
            entry["state"] = "malformed"
            failing.append(name)
        else:
            # `covered` answers "the audit ran and its report is well-formed", and that
            # stays true whether or not a decidable verdict came with it. The verdict is
            # a SEPARATE fact and lives in `verdict_record`.
            #
            # An earlier draft of this overwrote `state` with `verdict_not_exposed` and
            # a sibling test refused it within the minute — correctly. Sixteen of the
            # seventeen plugins expose no verdict today and every one of them covers its
            # audit; folding the two would have turned a real coverage report into a
            # failure, which is the same collapse of two facts into one field that this
            # gate's own `not_installed` / `no_report` split exists to avoid.
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


def _looks_like_a_project(project: Path) -> bool:
    """Does this tree carry the marker every squad project has?

    `rules/` — the directory the installer creates and the consumer tunes. Checked
    through `rules_dir`, which owns the order and knows the `.claude/` layout, so a
    plugin install answers yes on the same evidence a standalone one does.

    Deliberately ONE marker and a cheap one. The question is not "is this a healthy
    project" — it is "could this plausibly be the root somebody meant", and a richer
    check would start refusing real projects for unrelated reasons.
    """
    return rules_dir(project) is not None


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
            if a.get("blocking_verdict"):
                record = a["verdict_record"]
                out.append(_finding(
                    f"Audit `{a['plugin']}` computed a blocking verdict",
                    f"{a.get('report')}: verdict `{record.get('verdict')}` with "
                    f"{record.get('blocking_count')} blocking finding(s), computed by "
                    f"`{record.get('by')}` (verdict.json, source: computed).",
                    f"Resolve the blocking findings in `{a['plugin']}`'s report and "
                    "re-run the audit. A verdict a script computed is the plugin's own "
                    "decision; this review cannot pass over it.",
                ))
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
        elif state == "incomplete":
            out.append(_finding(
                f"Required audit `{a['plugin']}` stopped before it finished",
                f"{a.get('report')}: the run stopped on `{a.get('stopped_on')}` and "
                "its report says INCOMPLETE — no verdict was computed. A well-formed "
                "report of an unfinished run is not coverage of the change.",
                "Read that report's `## What Was NOT Analyzed` for what never ran, "
                "address the stop condition (an iteration cap: re-run with a higher "
                "`max_iterations`, or narrow the scope), and re-run the audit to "
                "completion.",
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
        mark = {"covered": "✓", "malformed": "✗", "incomplete": "✗",
                "no_report": "✗", "not_installed": "⊘"}.get(a["state"], "?")
        print(f"  {mark} {a['plugin']:<24} {a['state']}")
        if a.get("verdict"):
            print(f"      verdict: {a['verdict'].splitlines()[0][:100]}")
        if a.get("blocking_verdict"):
            rec = a["verdict_record"]
            print(f"      computed verdict BLOCKS: {rec.get('verdict')} "
                  f"({rec.get('blocking_count')} blocking, by {rec.get('by')})")
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

#!/usr/bin/env python3
"""Orchestrator entrypoint for /code-quality skill.

T5.1 implementation: CLI + auto-detect + per-language detector dispatch.

Modes:
  Mode 1 (no plan slug): repo-wide audit; JSON to stdout, no Markdown file.
  Mode 2 (plan slug):    bind audit to the plan's `## Critical paths` (if any);
                         write Markdown audit to .claude/records/audits/
                         {slug}-code-quality-{date}.md unless --no-audit-write.

CLI flags:
  {plan-slug} (positional, optional)
  --json-out PATH         (default: stdout; use `-` for stdout explicitly)
  --audit-out PATH        (default: derived from slug + date)
  --no-audit-write        (skip Markdown report; JSON only — used by T6.5 wiring)
  --languages-rule PATH   (default: .claude/rules/code-quality-languages.txt)
  --thresholds-rule PATH  (default: .claude/rules/code-quality-thresholds.txt)
  --allowlist PATH        (default: .claude/rules/code-quality-allowlist.txt)
  --no-network            (disable D2 entirely; single INFO Finding per language — EC-25)
  --repo-root PATH        (default: walk up from cwd looking for .git or .claude)

Exit codes:
  0  PASS or PASS_WITH_CAVEATS (no HARD findings)
  1  FAIL_HARD or INVALID (HARD findings present)
  2  Error (slug not found, malformed config, orchestrator crash)
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Make `scripts.*` importable when this file is run directly (not via -m).
_SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from scripts._detector_contract import (  # noqa: E402
    Finding,
    compute_verdict,
    emit_json_summary,
    load_allowlist,
    load_baseline,
    load_languages_config,
    load_thresholds,
)
from scripts.detectors.go import GoDetector  # noqa: E402
from scripts.detectors.python import PythonDetector  # noqa: E402
from scripts.detectors.rust import RustDetector  # noqa: E402
from scripts.detectors.typescript import TypescriptDetector  # noqa: E402

_DETECTOR_CLASSES = {
    "python": PythonDetector,
    "typescript": TypescriptDetector,
    "rust": RustDetector,
    "go": GoDetector,
}


def _find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(20):
        if (cur / ".claude").exists() or (cur / ".git").exists():
            return cur
        if cur == cur.parent:
            break
        cur = cur.parent
    return start.resolve()


def _resolve_plan_path(slug: str, repo_root: Path) -> Path:
    """EC-6 — strict slug resolution. Refuse discovery plans."""
    candidates = [
        repo_root / ".claude" / "records" / "plans" / f"{slug}-plan.md",
        repo_root / ".claude" / "records" / "plans" / "completed" / f"{slug}-plan.md",
    ]
    for p in candidates:
        if p.is_file():
            return p
    discovery_alt = (
        repo_root / ".claude" / "records" / "discoveries" / "plans" / f"{slug}-plan.md"
    )
    if discovery_alt.is_file():
        raise FileNotFoundError(
            f"plan_not_found: slug {slug!r} matches a discovery plan at {discovery_alt}, "
            f"not an implementation plan. /code-quality validates implementation plans only. "
            f"Use /discover-confidence for discovery plans."
        )
    raise FileNotFoundError(
        f"plan_not_found: looked in plans/{slug}-plan.md and plans/completed/{slug}-plan.md"
    )


def _build_detector(language: str, thresholds: dict | None = None):
    cls = _DETECTOR_CLASSES.get(language)
    if cls is None:
        return None
    detector = cls()
    # Os knobs do projeto chegam ao detector. Antes, `load_thresholds()` era chamado
    # for the side effect of validating the file and the result was discarded — every
    # `vulture.min_confidence` ou `mutation.score_floor_low` declarado em
    # `code-quality-thresholds.txt` era inerte.
    detector.thresholds = thresholds or {}
    if language == "python" and "vulture.min_confidence" in detector.thresholds:
        detector.min_confidence = int(detector.thresholds["vulture.min_confidence"])
    return detector


def _safe_call(label: str, func, *args, language: str = "") -> tuple[list[Finding], Finding | None]:
    """Wrap a detector call; on any exception emit a detector_crash Finding."""
    try:
        return list(func(*args)), None
    except NotImplementedError as error:
        # A detector that did not run is not a clean detector.  Returning an empty list here used
        # to turn missing D3/D4 implementations into evidence of absence.  Keep the orchestrator
        # isolated, but make the unavailable audit visible and verdict-capping.
        finding_type = {
            "d3": "orphan_export",
            "d4": "mutation_low",
        }.get(label, "dead_code")
        unavailable = Finding(
            detector=f"{label}_unavailable",
            language=language or "unknown",
            severity="SOFT_CAP",
            file_path=".",
            symbol_or_line=label,
            message=f"auditor unavailable: {error}",
            allowlist_key=(
                f"{language or 'unknown'}|.|{finding_type}|auditor_unavailable_{label}"
            ),
        )
        return [unavailable], None
    except Exception as e:  # noqa: BLE001 — orchestrator isolation
        tb = traceback.format_exc(limit=3).strip().replace("\n", " | ")
        crash = Finding(
            detector="d1_dead_code",
            language=language or "unknown",
            severity="SOFT_CAP",
            file_path=".",
            symbol_or_line=label,
            message=f"detector crash: {type(e).__name__}: {e}; tb={tb[:200]}",
            allowlist_key=f"{language or 'unknown'}|.|dead_code|detector_crash_{label}",
        )
        return [], crash


def _enumerate_source_files(repo_root: Path, language: str) -> list[Path]:
    """Delega a `_detector_contract.enumerate_source_files`.

    The implementation lived here and the detectors came to need it (D3 looks for
    consumers across the whole repository). Two copies of the same walk diverge the
    first time someone fixes the pruning in only one — which is exactly the defect
    the CHANGELOG records between `check_wiring.py` and this file.
    """
    from scripts._detector_contract import enumerate_source_files

    return enumerate_source_files(repo_root, language)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Multi-language code-quality gate")
    parser.add_argument("slug", nargs="?", default=None, help="plan slug (Mode 2 binding)")
    parser.add_argument("--json-out", default="-")
    parser.add_argument("--audit-out", default=None)
    parser.add_argument("--no-audit-write", action="store_true")
    parser.add_argument("--languages-rule", default=None)
    parser.add_argument("--thresholds-rule", default=None)
    parser.add_argument("--allowlist", default=None)
    parser.add_argument("--baseline", default=None,
                        help="findings recorded as pre-existing; removed from the verdict, "
                             "kept in the report (default: .claude/rules/code-quality-baseline.txt)")
    parser.add_argument("--write-baseline", action="store_true",
                        help="record every finding of this run as pre-existing and exit. "
                             "An explicit act: the baseline never grows by itself.")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--repo-root", default=None)
    args = parser.parse_args(argv)

    # A baseline recorded with the network on is worthless, so it cannot be recorded
    # that way. Measured on a real repository on 2026-08-31: the Go symbol detector
    # resolves imports against the module proxy, and with the network reachable it
    # reported 4777 fabrications; with `--no-network`, ONE. Two consecutive runs even
    # disagreed with each other — 4818 then 4777 — because the result depends on what
    # the proxy answered that second.
    #
    # Baselining that would have frozen ~4800 network failures into the repository as
    # if they were debt, hidden a real defect behind them, and still failed the gate,
    # because the next run produces a slightly different set that the baseline does
    # not cover. The honest baseline is the deterministic one.
    if getattr(args, "write_baseline", False):
        args.no_network = True

    repo_root = Path(args.repo_root) if args.repo_root else _find_repo_root(Path.cwd())

    rules_dir = repo_root / ".claude" / "rules"
    languages_rule = Path(args.languages_rule) if args.languages_rule else rules_dir / "code-quality-languages.txt"
    thresholds_rule = Path(args.thresholds_rule) if args.thresholds_rule else rules_dir / "code-quality-thresholds.txt"
    allowlist_rule = Path(args.allowlist) if args.allowlist else rules_dir / "code-quality-allowlist.txt"

    try:
        cfg = load_languages_config(languages_rule)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: cannot load languages config: {e}", file=sys.stderr)
        return 2

    thresholds: dict = {}
    try:
        if thresholds_rule.exists():
            thresholds = load_thresholds(thresholds_rule)
    except ValueError as e:
        print(f"ERROR: thresholds malformed: {e}", file=sys.stderr)
        return 2

    try:
        allowlist = load_allowlist(allowlist_rule) if allowlist_rule.exists() else []
    except ValueError as e:
        # EC-4 — surface as HARD Finding instead of crashing.
        allowlist_malformed_finding = Finding(
            detector="d1_dead_code",
            language="unknown",
            severity="HARD",
            file_path=str(allowlist_rule.relative_to(repo_root) if allowlist_rule.is_absolute() else allowlist_rule),
            symbol_or_line="code-quality-allowlist.txt",
            message=f"allowlist_malformed_entry: {e}",
            allowlist_key="unknown|.|dead_code|allowlist_malformed_entry",
        )
        return _emit_and_exit([allowlist_malformed_finding], args, repo_root, plan_path=None)

    # Plan resolution (Mode 2)
    plan_path = None
    if args.slug:
        try:
            plan_path = _resolve_plan_path(args.slug, repo_root)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2

    findings: list[Finding] = []

    # Phase 1: D1 + D2 per enabled language
    enabled_languages = [
        lang for lang, meta in cfg.items() if meta["status"] == "ENABLED"
    ]
    languages_audited: list[str] = []
    languages_skipped: dict[str, str] = {}

    for language in enabled_languages:
        manifest_marker = cfg[language]["manifest"]
        manifest_present = (repo_root / manifest_marker).exists()
        detector = _build_detector(language, thresholds)
        if detector is None:
            languages_skipped[language] = "no detector implementation"
            continue
        if not manifest_present:
            languages_skipped[language] = f"manifest {manifest_marker!r} not found"
            continue
        languages_audited.append(language)

        # D1 — dead code
        # The dead-code CLIs resolve their project from the cwd, and the manifest marker is a
        # repo-relative path — so a crate at `theodb_rs/Cargo.toml` or a package under `web/` must
        # send the detector to the manifest's directory. Passing repo_root made cargo-udeps exit
        # with "could not find `Cargo.toml`", which the detector honestly reported as
        # `auditor_unavailable_cargo-udeps` — a soft cap blocking the cycle over a path assumption
        # rather than over the code (measured on theo-db 2026-07-23, usetheoai/theo-db#175).
        # Collapses to repo_root when the manifest sits at the root, which is the common case.
        manifest_dir = (repo_root / manifest_marker).parent
        d1_findings, d1_crash = _safe_call(
            "d1", detector.detect_dead_code, manifest_dir, language=language
        )
        if d1_crash:
            findings.append(d1_crash)
        findings.extend(d1_findings)

        # D3 — exported symbols/packages that are not wired into a consumer.  An unavailable
        # implementation must remain a SOFT_CAP rather than disappearing from the report.
        d3_findings, d3_crash = _safe_call(
            "d3", detector.detect_orphan_exports, manifest_dir, language=language
        )
        if d3_crash:
            findings.append(d3_crash)
        findings.extend(d3_findings)

        # D4 — mutation score. The scope is what the PROJECT declared in the runner's
        # config (`[mutmut] source_paths`, `stryker.config.json`); neither accepts a file
        # list as scope, and the list built here never reached anywhere.
        d4_findings, d4_crash = _safe_call(
            "d4", detector.detect_mutation_score, manifest_dir, language=language
        )
        if d4_crash:
            findings.append(d4_crash)
        findings.extend(d4_findings)

        # D2 — symbol fabrication (skip when --no-network per EC-25)
        if args.no_network:
            findings.append(
                Finding(
                    detector="d2_symbol_fab",
                    language=language,
                    severity="INFO",
                    file_path=".",
                    symbol_or_line="d2",
                    message="D2 disabled by --no-network flag",
                    allowlist_key=f"{language}|.|symbol_fab|d2_disabled_no_network",
                )
            )
        else:
            source_files = _enumerate_source_files(repo_root, language)
            d2_findings, d2_crash = _safe_call(
                "d2", detector.detect_symbol_fabrication, source_files, language=language
            )
            if d2_crash:
                findings.append(d2_crash)
            findings.extend(d2_findings)

        # D5 — architecture rules the REPO declared, plus the meta-gate that they can still fire.
        # Runs against the manifest's directory for the same reason D1 does: the linters resolve
        # their project from the cwd.
        d5_findings, d5_crash = _safe_call(
            "d5", detector.detect_architecture_violations, manifest_dir, language=language
        )
        if d5_crash:
            findings.append(d5_crash)
        findings.extend(d5_findings)

    # Apply allowlist (downgrade severities by 1 level when ACTIVE entry matches)
    findings = _apply_allowlist(findings, allowlist, repo_root)

    baseline_path = Path(args.baseline) if args.baseline else _default_baseline(repo_root)
    if args.write_baseline:
        return _write_baseline(findings, baseline_path)

    return _emit_and_exit(findings, args, repo_root, plan_path,
                          languages_audited=languages_audited,
                          languages_skipped=languages_skipped,
                          cfg=cfg,
                          baseline=load_baseline(baseline_path))


def _apply_allowlist(findings: list[Finding], allowlist: list, repo_root: Path) -> list[Finding]:
    from datetime import date as _date

    from scripts._detector_contract import AllowlistMatch, is_allowlisted

    today = _date.today()
    downgrade = {"HARD": "SOFT_CAP", "SOFT_CAP": "SOFT_FLOOR", "SOFT_FLOOR": "INFO", "INFO": "INFO"}
    out: list[Finding] = []
    for f in findings:
        match = is_allowlisted(f, allowlist, today)
        if match == AllowlistMatch.ACTIVE:
            out.append(
                Finding(
                    detector=f.detector,
                    language=f.language,
                    severity=downgrade.get(f.severity, f.severity),
                    file_path=f.file_path,
                    symbol_or_line=f.symbol_or_line,
                    message=f"{f.message} [allowlisted]",
                    allowlist_key=f.allowlist_key,
                )
            )
        else:
            out.append(f)
    return out


def _default_baseline(repo_root: Path) -> Path:
    """Where the baseline lives, in either layout."""
    for rel in (".claude/rules/code-quality-baseline.txt", "rules/code-quality-baseline.txt"):
        candidate = repo_root / rel
        if candidate.is_file():
            return candidate
    return repo_root / ".claude/rules/code-quality-baseline.txt"


def _write_baseline(findings: list[Finding], path: Path) -> int:
    """Record this run's findings as pre-existing, and say what was recorded.

    An explicit act, never a side effect of a normal run. A baseline that grew by
    itself would absorb every new defect the moment it appeared, which is the failure
    mode that turns a gate into decoration.
    """
    # Only real code debt. A baseline is a record of findings ABOUT THE CODE, and a run
    # also emits findings about the GATE — a detector disabled for want of a network, a
    # linter with no config, a mutation pass deferred, a crash. Measured on a real
    # repository on 2026-08-31: the first honest baseline held five entries and every
    # one of them was of that second kind, including `d2_disabled_no_network`.
    #
    # Recording those would silence the warnings that say the gate is not working —
    # the one outcome worse than a gate that fails, because it looks like a gate that
    # passed. They are identified by what they cannot have: a real file. A finding
    # about the code names one; a finding about the tooling says `.` or `<unknown>`.
    skipped = [f for f in findings if f.file_path in (".", "<unknown>", "")]
    keys = sorted({f.allowlist_key for f in findings if f not in skipped})
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "# Code-quality baseline — findings that already existed.",
        "#",
        "# Written by `run_code_quality.py --write-baseline`. One `allowlist_key` per line.",
        "# A key here is REMOVED FROM THE VERDICT and still reported: the debt stays",
        "# countable, and a change is not failed for debt it did not cause.",
        "#",
        "# This is a FACT, not a decision — that is what separates it from",
        "# `code-quality-allowlist.txt`, where a person exempts one finding with a reason",
        "# and a sunset. Regenerating this file is an explicit act; it never grows by",
        "# itself, so a NEW finding in a baselined file still fails.",
        "",
    ]
    path.write_text("\n".join(header + keys) + "\n", encoding="utf-8")
    print(f"baseline written: {len(keys)} finding(s) recorded as pre-existing at {path}",
          file=sys.stderr)
    if skipped:
        names = ", ".join(sorted({f.allowlist_key.split("|")[-1] for f in skipped}))
        print(f"  {len(skipped)} finding(s) about the GATE were NOT baselined and still "
              f"apply: {names}", file=sys.stderr)
    return 0


def _emit_and_exit(
    findings: list[Finding],
    args,
    repo_root: Path,
    plan_path: Path | None,
    languages_audited: list[str] | None = None,
    languages_skipped: dict[str, str] | None = None,
    # The language table, so the guard below can ask what is on disk rather than what the gate
    # happened to look at. Optional so existing callers keep working; absent means the tree cannot
    # be consulted, and the guard falls back to the narrower "audited nothing at all" question.
    cfg: dict | None = None,
    #: Finding keys recorded as pre-existing. Removed from the verdict, kept in the report.
    baseline: frozenset[str] = frozenset(),
) -> int:
    verdict, stable_ids = compute_verdict(findings, baseline)
    baselined = [f for f in findings if f.allowlist_key in baseline] if baseline else []

    # B-084 / B-092 — an audit that ran zero detectors is not a clean audit.
    #
    # Before this check, an empty or misconfigured `code-quality-languages.txt` — or a config whose
    # every ENABLED language was skipped for a missing manifest — produced `findings == []`, and
    # `compute_verdict([])` reports PASS. That PASS is consumed as a HARD gate by `cycle-review.md`
    # (which admits on PASS / PASS_WITH_CAVEATS) and by `skills/implement/scripts/run_validation.py`
    # (which fails on FAIL_HARD / INVALID). Both were reading a constant.
    #
    # This is the umbrella defect B-084 names, in the gate that surfaced it: the gate reports on the
    # set it managed to see, and nothing verified that set was the right one — or, here, that it was
    # non-empty at all.
    #
    # It does NOT close B-060. That item is "audits TypeScript only, so 220 Python files pass a gate
    # that never looked at them": the gate looked at SOMETHING, just not at Python. This fires only
    # when it looked at nothing. B-060's fix is enabling `python` in the languages file; this guard
    # is what stops that configuration regressing silently to a PASS afterwards.
    # Two different questions, and the gate needs both.
    #
    # "Did I audit anything?" — a run with an empty `languages_audited` cannot distinguish "looked
    # at nothing" from "looked and found nothing", and `cycle-review` admits on PASS. That guard is
    # unchanged.
    if verdict not in ("FAIL_HARD", "INVALID") and not languages_audited:
        verdict = "INVALID"
        stable_ids = list(stable_ids)
        if "no_languages_audited" not in stable_ids:
            stable_ids.append("no_languages_audited")

    # "Was there anything to audit that I did not?" — the one the first question cannot reach. A
    # repository that audits TypeScript while holding an unaudited `pyproject.toml` had a non-empty
    # `languages_audited`, so it passed: "looked at something, just not at that" was
    # indistinguishable from a clean run. The gate reported on the set it managed to see, and
    # nothing verified that set was the right one.
    #
    # Answered by looking at the TREE rather than at the gate's own list: every language the config
    # knows carries its manifest marker, so a marker present for a language nobody audited is a file
    # the gate skipped while the report says PASS.
    if verdict not in ("FAIL_HARD", "INVALID") and cfg:
        unaudited = sorted(
            lang
            for lang, meta in cfg.items()
            if lang not in (languages_audited or []) and (repo_root / meta["manifest"]).exists()
        )
        if unaudited:
            verdict = "INVALID"
            stable_ids = list(stable_ids)
            if "unaudited_manifest_present" not in stable_ids:
                stable_ids.append("unaudited_manifest_present")
            findings = list(findings) + [
                Finding(
                    detector="orchestrator",
                    language=lang,
                    severity="HARD",
                    file_path=cfg[lang]["manifest"],
                    symbol_or_line="-",
                    message=(
                        f"{cfg[lang]['manifest']} is present but {lang} was not audited "
                        f"({(languages_skipped or {}).get(lang, 'not enabled')}). A PASS here would "
                        "report on the set the gate managed to see, with nothing verifying that set "
                        "was the right one."
                    ),
                    allowlist_key=f"unaudited_manifest_present|{cfg[lang]['manifest']}|-|{lang}",
                )
                for lang in unaudited
            ]

    summary = emit_json_summary(findings, verdict, stable_ids)
    summary["languages_audited"] = languages_audited or []
    # Reported, always. A baseline that silences findings without saying how many it is
    # holding is indistinguishable from a gate that found nothing.
    summary["baselined"] = len(baselined)
    summary["languages_skipped"] = list((languages_skipped or {}).keys())
    summary["skip_reasons"] = languages_skipped or {}
    summary["mode"] = "plan-bound" if plan_path else "standalone"
    if plan_path:
        summary["plan_path"] = str(plan_path.relative_to(repo_root))

    # JSON output
    json_text = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.json_out and args.json_out != "-":
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json_text, encoding="utf-8")
    else:
        sys.stdout.write(json_text + "\n")

    # Markdown audit (Mode 2 only, unless --no-audit-write)
    if args.slug and not args.no_audit_write:
        audit_path = (
            Path(args.audit_out)
            if args.audit_out
            else repo_root
            / ".claude"
            / "records"
            / "audits"
            / f"{args.slug}-code-quality-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
        )
        _write_markdown_report(findings, summary, audit_path, args.slug)
        summary["report_path"] = str(audit_path.relative_to(repo_root))

    # The phase leaves an event, not only a file. A missing audit cannot say
    # whether the gate was skipped or ran and wrote nothing; an absent event can.
    _emit_phase_end(
        repo_root,
        cycle="code-quality",
        slug=args.slug or "",
        verdict=verdict,
        languages=languages_audited or [],
        findings=len(findings),
    )

    # Exit code
    if verdict in ("FAIL_HARD", "INVALID"):
        return 1
    return 0


def _emit_phase_end(project_root, *, cycle: str, slug: str, verdict, **extra) -> None:
    """Record the phase transition; never let bookkeeping fail the phase.

    `scripts/` resolves against THIS FILE, not the audited project: in a plugin
    install the kit lives under `.claude/` while the project is elsewhere.
    `ImportError` is caught alone — a bare `except Exception` would swallow a
    real emitter bug into a silence indistinguishable from a phase that never
    ran, which is the defect the stream exists to remove.
    """
    from pathlib import Path as _Path
    tooling = _Path(__file__).resolve().parents[3] / "scripts"
    if str(tooling) not in sys.path:
        sys.path.insert(0, str(tooling))
    try:
        from cycle_events import emit_phase_end, project_root_for
    except ImportError as error:
        print(f"cycle-events: emitter unavailable ({error})", file=sys.stderr)
        return
    emit_phase_end(project_root_for(project_root), cycle=cycle, slug=slug,
                   verdict=verdict, **extra)


def _write_markdown_report(findings: list[Finding], summary: dict, audit_path: Path, slug: str) -> None:
    """T5.3 — render Markdown report from template skeleton."""
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    by_severity: dict[str, list[Finding]] = {"HARD": [], "SOFT_CAP": [], "SOFT_FLOOR": [], "INFO": []}
    for f in findings:
        by_severity.setdefault(f.severity, []).append(f)

    def _table(items: list[Finding]) -> str:
        if not items:
            return "_No findings._"
        rows = ["| File | Symbol | Severity | Message |", "|---|---|---|---|"]
        for f in items:
            msg = f.message.replace("|", "\\|")
            rows.append(f"| `{f.file_path}` | `{f.symbol_or_line}` | {f.severity} | {msg} |")
        return "\n".join(rows)

    by_detector: dict[str, list[Finding]] = {"d1_dead_code": [], "d2_symbol_fab": [], "d3_orphan_export": [], "d4_mutation": [], "d5_architecture": []}
    for f in findings:
        by_detector.setdefault(f.detector, []).append(f)

    content = f"""# Code Quality Audit: {slug}

**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
**Mode:** {summary.get('mode', 'standalone')}
**Verdict:** {summary['verdict']}
**Score cap:** {summary['score_cap']}
**Hard caps triggered:** {', '.join(summary['hard_caps_triggered']) or '_none_'}
**Soft caps triggered:** {', '.join(summary['soft_caps_triggered']) or '_none_'}

## Summary

- Languages audited: {', '.join(summary.get('languages_audited', [])) or '_none_'}
- Languages skipped: {', '.join(summary.get('languages_skipped', [])) or '_none_'}
- Total findings: {len(findings)} ({len(by_severity['HARD'])} HARD, {len(by_severity['SOFT_CAP'])} SOFT_CAP, {len(by_severity['SOFT_FLOOR'])} SOFT_FLOOR, {len(by_severity['INFO'])} INFO)

## Findings by detector

### D1 — Dead code
{_table(by_detector['d1_dead_code'])}

### D2 — Symbol fabrication
{_table(by_detector['d2_symbol_fab'])}

### D3 — Cross-package orphan exports
{_table(by_detector['d3_orphan_export'])}

### D4 — Mutation testing
{_table(by_detector['d4_mutation'])}

### D5 — architecture

{_table(by_detector['d5_architecture'])}

## Related

- Golden rule: [`.claude/rules/code-quality-golden-rule.md`](../../rules/code-quality-golden-rule.md)
- Allowlist: [`.claude/rules/code-quality-allowlist.txt`](../../rules/code-quality-allowlist.txt)
- Thresholds: [`.claude/rules/code-quality-thresholds.txt`](../../rules/code-quality-thresholds.txt)
"""
    audit_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — EC-30 top-level safety
        print(f"ORCHESTRATOR_CRASH: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(2)

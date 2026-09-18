"""Cross-detector utilities for the /code-quality skill.

Centralizes parsing of config files, allowlist matching with sunset logic,
Finding dataclass with invariants, atomic writes, safe JSON parsing, and
path/symbol normalization helpers.

Per plan v1.3 § T0.4 — consumed by all detectors (Phase 1-4) plus the
orchestrator (Phase 5). Edge-case absorptions documented inline with EC-N
markers.
"""
from __future__ import annotations

import enum
import fnmatch
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# EC-10 — file enumeration skip list
# ---------------------------------------------------------------------------

DEFAULT_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".claude",  # meta-tooling — /code-quality audits the PRODUCT, not its own skills
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "target",  # Rust + Java
        "dist",
        "build",
        "out",
        "references",  # read-only zone (third-party study material) per cycle-discover.md
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        "vendor",  # Go vendored deps
        ".cache",
    }
)


# ---------------------------------------------------------------------------
# Finding dataclass + invariants (EC-12)
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """Single detection result emitted by a Detector method.

    Invariants (per EC-12):
      - `file_path` MUST be repo-relative (never absolute) — enforced by __post_init__.
      - `allowlist_key` MUST have its symbol portion sanitized (pipes escaped) —
        enforced by __post_init__.
    """

    detector: str  # "d1_dead_code" / "d2_symbol_fab" / "d3_orphan_export" / "d4_mutation"
    language: str
    severity: str  # "HARD" / "SOFT_CAP" / "SOFT_FLOOR" / "INFO"
    file_path: str
    symbol_or_line: str
    message: str
    allowlist_key: str

    def __post_init__(self) -> None:
        assert not self.file_path.startswith("/"), (
            f"Finding.file_path must be repo-relative, got absolute: {self.file_path}"
        )
        # allowlist_key format: {language}|{file_path}|{finding_type}|{sanitized_symbol}
        # MUST have exactly 3 unescaped pipes (4 segments). More pipes => symbol unsanitized.
        unescaped = self.allowlist_key.replace("\\|", "\x00")  # mask escapes
        pipe_count = unescaped.count("|")
        assert pipe_count == 3, (
            f"Finding.allowlist_key must have exactly 3 unescaped pipes "
            f"(symbol must be sanitized); got {pipe_count} in {self.allowlist_key!r}"
        )


@dataclass
class AllowlistEntry:
    ecosystem: str
    file_path: str
    finding_type: str
    symbol: str
    reason: str
    sunset_date: date


class AllowlistMatch(enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    NOT_LISTED = "not_listed"


# ---------------------------------------------------------------------------
# Config file loaders
# ---------------------------------------------------------------------------

_VALID_STATUSES = frozenset({"ENABLED", "DISABLED", "DEFER"})


def load_languages_config(rule_file: Path) -> dict[str, dict[str, str]]:
    """Parse .claude/rules/code-quality-languages.txt.

    Format: LANGUAGE | MANIFEST-MARKER | STATUS | NOTES
    Returns: {language: {"manifest": ..., "status": ..., "notes": ...}}
    """
    config: dict[str, dict[str, str]] = {}
    for raw_line in rule_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            raise ValueError(f"languages.txt malformed line: {raw_line!r}")
        language, manifest, status = parts[0], parts[1], parts[2]
        notes = parts[3] if len(parts) > 3 else ""
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"languages.txt invalid STATUS {status!r} for {language}; "
                f"must be one of {_VALID_STATUSES}"
            )
        config[language] = {"manifest": manifest, "status": status, "notes": notes}
    return config


def load_thresholds(rule_file: Path) -> dict[str, Any]:
    """Parse key=value thresholds; coerce int / float / bool / str."""
    thresholds: dict[str, Any] = {}
    for raw_line in rule_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"thresholds.txt malformed line: {raw_line!r}")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        thresholds[key] = _coerce_value(raw_value)
    return thresholds


def _coerce_value(raw: str) -> Any:
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# ---------------------------------------------------------------------------
# Allowlist parsing (EC-4 — strict date validation)
# ---------------------------------------------------------------------------

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_ECOSYSTEMS = frozenset({"python", "typescript", "rust", "go"})
# `architecture` is D5. The detectors in `detectors/_arch.py` have always emitted an
# `allowlist_key` whose FINDING-TYPE column is literally "architecture" — only this set and
# `_detector_to_finding_type` below were never updated to match, so every D5 finding resolved
# to `finding_type == ""`, matched no entry, and was structurally unallowlistable (#343).
_VALID_FINDING_TYPES = frozenset(
    {"dead_code", "symbol_fab", "orphan_export", "mutation_low", "architecture"}
)


def load_allowlist(rule_file: Path) -> list[AllowlistEntry]:
    """Parse pipe-separated allowlist with strict sunset date validation.

    Format: ECOSYSTEM|FILE-PATH|FINDING-TYPE|SYMBOL-OR-LINE|REASON|SUNSET-DATE

    Per EC-4: malformed sunset dates raise ValueError. The golden rule's
    `allowlist_malformed_entry` HARD Finding is emitted by the orchestrator
    (run_code_quality.py) when load_allowlist raises — it does NOT silently
    drop malformed entries.
    """
    entries: list[AllowlistEntry] = []
    for line_num, raw_line in enumerate(rule_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 6:
            raise ValueError(
                f"allowlist.txt line {line_num}: malformed entry (expected 6 pipe-separated "
                f"fields, got {len(parts)}): {raw_line!r}"
            )
        ecosystem, file_path, finding_type, symbol, reason, sunset_str = parts
        if ecosystem not in _VALID_ECOSYSTEMS:
            raise ValueError(
                f"allowlist.txt line {line_num}: invalid ECOSYSTEM {ecosystem!r}"
            )
        if finding_type not in _VALID_FINDING_TYPES:
            raise ValueError(
                f"allowlist.txt line {line_num}: invalid FINDING-TYPE {finding_type!r}"
            )
        if not reason:
            raise ValueError(f"allowlist.txt line {line_num}: REASON is empty")
        if not _ISO_DATE_RE.match(sunset_str):
            raise ValueError(
                f"allowlist.txt line {line_num}: malformed sunset date {sunset_str!r} "
                f"(expected YYYY-MM-DD)"
            )
        try:
            sunset = datetime.strptime(sunset_str, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(
                f"allowlist.txt line {line_num}: malformed sunset date {sunset_str!r}: {e}"
            ) from e
        entries.append(
            AllowlistEntry(
                ecosystem=ecosystem,
                file_path=file_path,
                finding_type=finding_type,
                symbol=symbol,
                reason=reason,
                sunset_date=sunset,
            )
        )
    return entries


def _allowlist_key_symbol(allowlist_key: str) -> str:
    """The fourth field of `{language}|{file}|{type}|{symbol}`, unescaped.

    Parsed rather than split naively: the symbol portion escapes its pipes, and a
    `str.split("|")` on a symbol containing one would silently return the wrong field.
    """
    masked = allowlist_key.replace("\\|", "\x00")
    parts = masked.split("|")
    if len(parts) != 4:
        return ""
    return parts[3].replace("\x00", "|")


def is_allowlisted(
    finding: Finding, allowlist: list[AllowlistEntry], today: date
) -> AllowlistMatch:
    """Match a Finding against the allowlist; return ACTIVE / EXPIRED / NOT_LISTED."""
    for entry in allowlist:
        # Patch 2026-05-30 — file_path uses fnmatch (literal-match still works when entry has no wildcards;
        # glob patterns like `examples/**/lib/*.ts` now match real findings). Symbol stays substring-match
        # for backward compat (entries without `*` continue to work as before; entries with `*` now glob).
        # Two haystacks, and the second is the fix for a trap the gate set itself.
        #
        # The gate PUBLISHES `allowlist_key` — `go|.|mutation_low|soft_cap_mutation_
        # deferred_go` — in the finding, the JSON and the report. The obvious thing to
        # do with a key a tool hands you is copy its fields into the allowlist. That
        # produced a well-formed six-column row that matched NOTHING, because matching
        # ran against `symbol_or_line`, which for this finding is `d4`.
        #
        # Measured on a consumer with a control: an allowlist carrying the published
        # key and one carrying `ZZZ_NO_SUCH_SYMBOL` produced byte-identical JSON. The
        # advertised key was indistinguishable from an invented symbol, `load_allowlist`
        # validated all six columns without complaint, and the false claim that it
        # worked reached a brief AND a panel vote before anyone tested it.
        #
        # `symbol_or_line` stays first so every existing entry keeps working unchanged.
        haystacks = [finding.symbol_or_line]
        key_symbol = _allowlist_key_symbol(finding.allowlist_key)
        if key_symbol and key_symbol != finding.symbol_or_line:
            haystacks.append(key_symbol)
        if any(c in entry.symbol for c in "*?["):
            symbol_match = any(fnmatch.fnmatch(h, f"*{entry.symbol}*") for h in haystacks)
        else:
            symbol_match = any(entry.symbol in h for h in haystacks)
        if (
            entry.ecosystem == finding.language
            and fnmatch.fnmatch(finding.file_path, entry.file_path)
            and finding.detector.startswith("d") and _detector_to_finding_type(finding.detector) == entry.finding_type
            and symbol_match
        ):
            if today <= entry.sunset_date:
                return AllowlistMatch.ACTIVE
            return AllowlistMatch.EXPIRED
    return AllowlistMatch.NOT_LISTED


def _detector_to_finding_type(detector: str) -> str:
    """Map detector identifier to the allowlist FINDING-TYPE column."""
    mapping = {
        "d1_dead_code": "dead_code",
        "d2_symbol_fab": "symbol_fab",
        "d3_orphan_export": "orphan_export",
        "d4_mutation": "mutation_low",
        # #343 — the detector side already writes "architecture" into its allowlist_key; this was
        # the missing half of that agreement.
        "d5_architecture": "architecture",
        # The names the detectors ACTUALLY emit beside the five above. `is_allowlisted`
        # requires this mapping to equal the entry's FINDING-TYPE, and these resolved to
        # `""` — so a finding saying the auditor was unavailable, or that a dimension was
        # skipped, could not be allowlisted by any entry a project could write, while the
        # contract says every exemption goes through the allowlist. An exemption that
        # cannot be granted is a finding a project has to live with forever or silence
        # some other way, which is how an allowlist stops being the one door.
        "d1_unavailable": "dead_code",
        "d2_unavailable": "symbol_fab",
        "d3_unavailable": "orphan_export",
        "d3_orphan_export_skipped": "orphan_export",
        "d4_unavailable": "mutation_low",
        "d4_mutation_score": "mutation_low",
        "d5_unavailable": "architecture",
    }
    return mapping.get(detector, "")


# ---------------------------------------------------------------------------
# safe_parse_json (EC-1) — never let JSONDecodeError bubble
# ---------------------------------------------------------------------------


def safe_parse_json(stdout: str, tool_name: str) -> tuple[Any | None, Finding | None]:
    """Wrap json.loads with explicit error handling.

    Returns:
        (parsed_data, None) on success.
        (None, Finding(severity=SOFT_CAP, allowlist_key=auditor_output_malformed_{tool}))
            on JSONDecodeError. Orchestrator must isolate per detector — never crash
            the loop because one tool emitted bad JSON.
    """
    try:
        return json.loads(stdout), None
    except (json.JSONDecodeError, ValueError) as e:
        return (
            None,
            Finding(
                detector="d1_dead_code",  # caller may override; default conservative
                language="",
                severity="SOFT_CAP",
                file_path="",
                symbol_or_line=f"{tool_name} stdout (len={len(stdout)})",
                message=f"Failed to parse {tool_name} JSON output: {e}",
                allowlist_key=f"|auditor|auditor_output_malformed_{tool_name}|tool",
            ),
        )


# ---------------------------------------------------------------------------
# write_atomic (EC-9)
# ---------------------------------------------------------------------------


def write_atomic(target: Path, content: str | bytes) -> None:
    """Write `content` to `target` atomically (tempfile + rename).

    POSIX guarantees `os.replace` atomicity within the same filesystem. Concurrent
    writers see either the OLD or NEW state — never a partial truncation.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    encoding = None if isinstance(content, bytes) else "utf-8"
    with tempfile.NamedTemporaryFile(
        mode=mode,
        dir=str(target.parent),
        delete=False,
        prefix=f".{target.name}.",
        suffix=".tmp",
        encoding=encoding,
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target)


# ---------------------------------------------------------------------------
# Path + symbol helpers (EC-12)
# ---------------------------------------------------------------------------


#: Source extensions per language, for the shared enumeration.
_SOURCE_EXTS = {
    "python": (".py",),
    "typescript": (".ts", ".tsx"),
    "rust": (".rs",),
    "go": (".go",),
}


def enumerate_source_files(root: Path, language: str) -> list[Path]:
    """Every source file of the language under `root`, pruning during the walk.

    It lives here, not in the orchestrator, because the DETECTORS need it (D3
    walks the repository looking for consumers). A detector importing the
    orchestrator would invert the dependency of the module that instantiates it.

    PRUNE DURING THE WALK, DO NOT FILTER AFTERWARDS. `rglob("*")` followed by a
    filter gives the right answer the wrong way: it has already descended into all
    of `node_modules`, `.git` and `.venv` before discarding them. Measured
    2026-08-26 on a 56,128-file repository (40k in node_modules): 326 ms against
    0.4 ms — 832x, once per enabled language.
    """
    exts = _SOURCE_EXTS.get(language, ())
    if not exts:
        return []
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_SKIP_DIRS]
        for name in filenames:
            if name.endswith(exts):
                out.append(Path(dirpath) / name)
    return out


def make_relative(path: Path, repo_root: Path) -> str:
    """Return path relative to repo_root using forward slashes."""
    rel = path.resolve().relative_to(repo_root.resolve())
    return rel.as_posix()


def sanitize_symbol(symbol: str) -> str:
    """Escape pipe characters in symbol names for unambiguous allowlist_key parsing."""
    return symbol.replace("|", "\\|")


def to_rel_path(p: Path) -> str:
    """Strip leading slash so absolute paths satisfy Finding's repo-relative invariant.

    Detectors invoked with `tmp_path` from tests pass absolute paths; production
    orchestrator (T5.1) passes already-relative paths so this is a no-op there.
    """
    s = p.as_posix()
    return s.lstrip("/") if s.startswith("/") else s


# ---------------------------------------------------------------------------
# JSON summary emission
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = "0.1.0"


def emit_json_summary(
    findings: list[Finding],
    verdict: str,
    hard_caps_triggered: list[str],
) -> dict[str, Any]:
    """Build the JSON object emitted by /code-quality for /plan-confidence consumption."""
    severity_counts: dict[str, int] = {"HARD": 0, "SOFT_CAP": 0, "SOFT_FLOOR": 0, "INFO": 0}
    by_detector: dict[str, dict[str, int]] = {}
    soft_caps: list[str] = []
    languages_set: set[str] = set()
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
        by_detector.setdefault(f.detector, {})
        by_detector[f.detector][f.language] = by_detector[f.detector].get(f.language, 0) + 1
        if f.severity == "SOFT_CAP":
            # The STABLE identifier, not the allowlist_key's tail — in D3 the tail is
            # the found symbol's name (`flush_caches`), and publishing it here tells
            # whoever reads the report to allowlist something that is not a cap. Golden
            # rule § 1.4 requires stable identifiers: they are what two runs are
            # compared by.
            sid = _finding_to_stable_identifier(f) or f.allowlist_key.rsplit("|", 1)[-1]
            if sid and sid not in soft_caps:
                soft_caps.append(sid)
        if f.language:
            languages_set.add(f.language)

    # `hard_caps_triggered` carries HARD caps only. `compute_verdict` returns every
    # triggered identifier — including the soft ones, when the verdict is FAIL_SOFT —
    # and publishing them under this name made a dismissible cap (with an ADR) look
    # like a blocker, and would hide a real HARD in the middle of the list when both
    # coexist.
    hard_only = [sid for sid in hard_caps_triggered if not sid.startswith("soft_")]

    return {
        "verdict": verdict,
        "score_cap": _verdict_to_cap(verdict),
        "hard_caps_triggered": hard_only,
        "soft_caps_triggered": soft_caps,
        "findings_by_detector": by_detector,
        # The findings THEMSELVES, not only how many there were. Until 2026-09-09 this
        # summary published counts per detector per language and nothing else: a
        # FAIL_HARD on three dead symbols arrived with no file, no symbol and no
        # allowlist key, so the only way to act on it was to re-derive the tool
        # invocation by hand (kit#61). `Finding` has carried all three the whole time.
        #
        # Sorted so two runs of the same tree produce the same report, and a diff
        # between them is about the findings rather than about dict ordering.
        "findings": sorted(
            (
                {
                    "detector": f.detector,
                    "language": f.language,
                    "severity": f.severity,
                    "file_path": f.file_path,
                    "symbol_or_line": f.symbol_or_line,
                    "message": f.message,
                    "allowlist_key": f.allowlist_key,
                }
                for f in findings
            ),
            key=lambda d: (d["detector"], d["file_path"], d["symbol_or_line"]),
        ),
        "severity_counts": severity_counts,
        "languages_audited": sorted(languages_set),
        "schema_version": _SCHEMA_VERSION,
    }


def _verdict_to_cap(verdict: str) -> int:
    return {
        "PASS": 100,
        "PASS_WITH_CAVEATS": 89,
        "FAIL_SOFT": 70,
        "FAIL_HARD": 49,
        "INVALID": 0,  # structural integrity broken — golden rule § 1 caps INVALID at 0
    }.get(verdict, 49)


def load_baseline(path: Path | str | None) -> frozenset[str]:
    """Finding keys recorded as pre-existing. Empty when there is no baseline.

    One `allowlist_key` per line, `#` comments. The key is reused rather than invented
    because it is already the stable, sanitized identity of a finding — a second
    identity scheme would drift from the first.
    """
    if path is None:
        return frozenset()
    file = Path(path)
    if not file.is_file():
        return frozenset()
    keys = set()
    for raw in file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            keys.add(line)
    return frozenset(keys)


def compute_verdict(findings: list[Finding],
                    baseline: frozenset[str] = frozenset()) -> tuple[str, list[str]]:
    """Compute the verdict + stable_identifiers list from a list of Findings.

    Returns:
        (verdict, hard_caps_triggered) — where verdict is one of
        PASS / PASS_WITH_CAVEATS / FAIL_SOFT / FAIL_HARD / INVALID.

    Cap precedence (smallest cap wins):
      1. Any HARD finding -> FAIL_HARD (49)
      2. Else any SOFT_CAP -> FAIL_SOFT (70)
      3. Else any SOFT_FLOOR -> PASS_WITH_CAVEATS (89)
      4. Else -> PASS (100)

    ## Why a baseline exists

    A verdict is one per language, and the gate had no way to tell debt that was
    already there from a defect the change introduced. A consumer wrote the
    consequence into its own config on 2026-08-19, as the reason Go stayed disabled:

        the D1 pass brings 36 REAL dead-code findings, and the verdict is one per
        language — turning it on before paying them fails the delivery over legitimate
        debt, which is how a gate becomes something people work around

    That is exactly what happened. Every language ended up DEFER or DISABLED, the gate
    then audited nothing, `no_languages_audited` fired, and every plan came back
    INVALID. The gate was right at each step and the system was deadlocked.

    A baselined finding is REMOVED FROM THE VERDICT and kept in the report. It is not
    forgiven and not hidden — the run still names it, and `run_code_quality.py` prints
    how many the baseline is holding, so the debt stays countable. What it stops doing
    is failing a change that did not cause it.

    The baseline is a FACT, not a decision, which is what separates it from the
    allowlist next door: that one is a person exempting a specific finding with a
    reason and a sunset, one entry at a time. This is a generated record of what was
    already true, and regenerating it is an explicit act — it never grows by itself,
    so a new finding in a baselined file still fails.
    """
    if baseline:
        findings = [f for f in findings if f.allowlist_key not in baseline]
    severities = {f.severity for f in findings}
    stable_ids: list[str] = []
    for f in findings:
        sid = _finding_to_stable_identifier(f)
        if sid and sid not in stable_ids:
            stable_ids.append(sid)

    if "HARD" in severities:
        return "FAIL_HARD", [sid for sid in stable_ids if not sid.startswith("soft_")]
    if "SOFT_CAP" in severities:
        return "FAIL_SOFT", stable_ids
    if "SOFT_FLOOR" in severities:
        return "PASS_WITH_CAVEATS", stable_ids
    return "PASS", []


#: Prefixes marking the `allowlist_key` tail as an already-formed stable
#: identifier rather than a found symbol.
_STABLE_ID_PREFIXES = ("auditor_", "soft_cap_", "soft_floor_", "mutation_score_ok_")


def _finding_to_stable_identifier(f: Finding) -> str:
    """Map a Finding to the stable identifier from code-quality-golden-rule.md.

    When the detector has ALREADY named the cap in the `allowlist_key` tail, that
    tail wins — D4 distinguishes `soft_cap_mutation_score_low_*` (the suite does not
    detect) from `soft_cap_mutation_unconfigured_*` (the runner was not declared) and
    `soft_cap_mutation_deferred_*` (the language is outside the contract). Collapsing
    the three into "low score" would tell people to write tests where a runner needs
    configuring — a report that names the wrong action costs more than one that names
    none.
    """
    tail = f.allowlist_key.rsplit("|", 1)[-1]
    if f.detector.startswith(("d3_", "d4_")) and tail.startswith(_STABLE_ID_PREFIXES):
        return tail
    if f.detector == "d1_dead_code" and f.severity == "HARD":
        return f"dead_code_unallowlisted_{f.language}"
    if f.detector == "d1_dead_code" and f.severity == "SOFT_CAP":
        # auditor_unavailable lives in allowlist_key tail
        return tail if tail.startswith(("auditor_", "soft_")) else f"soft_cap_{f.language}"
    if f.detector == "d2_symbol_fab" and f.severity == "HARD":
        return f"symbol_fabrication_{f.language}"
    if f.detector == "d2_symbol_fab" and f.severity == "SOFT_FLOOR":
        return f"symbol_fab_unverifiable_{f.language}"
    if f.detector == "d3_orphan_export" and f.severity == "SOFT_CAP":
        return f"soft_cap_orphan_export_{f.language}"
    if f.detector == "d4_mutation" and f.severity == "SOFT_CAP":
        return f"soft_cap_mutation_score_low_{f.language}"
    if f.detector == "d4_mutation" and f.severity == "SOFT_FLOOR":
        return f"soft_floor_mutation_score_medium_{f.language}"
    # D5 fell through to `""` until 2026-09-17. `_arch.violation` and `_arch.vacuous_rule`
    # both emit HARD findings, and every language detector runs D5 — so a FAIL_HARD
    # verdict could be reached by a finding whose stable identifier was the empty string.
    # Nothing downstream can allowlist, cite or dismiss an identifier that is empty, and
    # a cap nobody can name is a cap nobody can act on. The two are separated because they
    # take different actions: fix the code, versus delete the rule that can no longer fire.
    if f.detector == "d5_architecture":
        # `vacuous_rule` puts the RULE in symbol_or_line and points file_path at the
        # config; `violation` points at the offending source. The allowlist tail carries
        # the rule name in both, so the shape is told apart by the message it built.
        if "names something that is not in the tree" in f.message:
            return f"vacuous_architecture_rule_{f.language}"
        return f"architecture_violation_{f.language}"
    return ""


__all__ = [
    "AllowlistEntry",
    "AllowlistMatch",
    "Finding",
    "compute_verdict",
    "emit_json_summary",
    "enumerate_source_files",
    "is_allowlisted",
    "load_allowlist",
    "load_languages_config",
    "load_thresholds",
    "make_relative",
    "safe_parse_json",
    "sanitize_symbol",
    "to_rel_path",
    "write_atomic",
]

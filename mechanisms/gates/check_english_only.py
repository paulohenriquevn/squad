#!/usr/bin/env python3
"""Refuse Portuguese in a repository that is English by policy.

WHAT IT CATCHES, AND WHAT IT MISSES
-----------------------------------
It matches a list of common Portuguese function words, so it finds prose and misses
phrases built from words the list does not carry. Demonstrated on 2026-08-31, by this
kit against itself: `mechanisms/distribution/install.sh` carried the comment *"exigindo a spec Agent
Skills; com o kit instalado"* and the sweep reported clean — none of `exigindo`,
`com`, `kit` or `instalado` is on the list.

The file was scanned; the words were not recognised. That is the honest shape of the
limit, and it is stated here because a gate reporting `clean` over real Portuguese
gives a confidence it has not earned. Widening the list is an endless game and would
start matching English; what this check buys is that the ordinary case cannot pass
quietly, not that nothing can.

WHY THIS EXISTS
---------------
The policy was real and nothing enforced it. Measured on 2026-08-27, before this
landed: 334 Portuguese markers across 21 versioned files in this kit and 93
across 17 in the sibling — including a `CHANGELOG.md` most of whose recent
entries were written in Portuguese by the maintainer of the day.

`skills/plan-confidence/scripts/check_adr_completeness.py` went further: it
MATCHED Portuguese, accepting "alternativa" and "rejeitada" beside the English
terms. A kit that accommodates a second language in its checkers has decided the
policy is advisory.

The cost is not aesthetic. Consumers' agents read these files as instructions,
and a contract written half in one language is a contract whose exact wording
nobody can grep for. It also spreads by example: one consumer wrote an entire
`BACKLOG.md` in Portuguese inside an English-by-policy repository, having read
four sibling registries and copied none of them, because nothing said no.

PRECISION OVER RECALL, DELIBERATELY
-----------------------------------
The markers below are function words that cannot plausibly appear in English
technical prose. `para`, `com`, `de`, `mode` and `data` are English, or appear
inside identifiers, paths and URLs; matching them would fire on clean files.

A gate that cries wolf is a gate somebody disables, and this one is meant to run
in every consumer — where the person who sees the false positive did not write
the gate and has no reason to trust it. Missing some Portuguese is recoverable.
Being ignored is not.

Usage:
    python3 check_english_only.py [--root PATH] [--json]

Exit codes:
    0 — clean
    1 — Portuguese found outside an exemption
    2 — the root is not a git repository
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

#: Unambiguous markers. Accented forms carry themselves; unaccented ones appear
#: only where they cannot be English.
_MARKER_RE = re.compile(
    r"(?<![\w-])("
    # accented function words — no English equivalent spelling
    r"não|são|está|estão|também|então|porém|já|até|três|é|"  # english-only: the gate must name what it detects
    r"você|vocês|nós|"  # english-only: the gate must name what it detects
    # unambiguous unaccented function words
    r"isso|essa|esse|aquele|aquilo|nenhum|nenhuma|porque|"  # english-only: the gate must name what it detects
    r"deve|pode|precisa|foi|serão|fica|ficou|"  # english-only: the gate must name what it detects
    # nouns that would be written in English in this codebase
    r"arquivo|arquivos|pasta|linha|razão|motivo|erro|"  # english-only: the gate must name what it detects
    r"exemplo|somente|apenas|sempre|nunca\s+é|"  # english-only: the gate must name what it detects
    # Verbs and nouns a docstring reaches for. A line like
    # "Classify ... the delta against ONE consumer", written in Portuguese, survived every
    # marker above for weeks: no accent, and none
    # of its words was on the list. A word-frequency heuristic was the other option and
    # was rejected — it guesses, and a gate that guesses about language teaches people to
    # ignore it. These are spellings that cannot be English.
    r"classifica|aplica|retorna|devolve|recebe|escreve|verifica|valida|"  # english-only: the gate must name what it detects
    r"consumidor|consumidores|delta\s+em|entrada|saída|chamada|"  # english-only: the gate must name what it detects
    r"opcionalmente|obrigatório|ausente|presente|falha|sucesso|"  # english-only: the gate must name what it detects
    # Added 2026-09-17. `install.sh:203` carried a Portuguese section header for
    # four months and this gate called the tree clean across 997 files:  # english-only: naming the marker it adds
    # no accent on any word, and none of them on the list above. Found by a human
    # reading the file for another reason, which is the detection method this gate
    # exists to replace.
    #
    # TWO words, not the dozen the first draft added. `entregue`, `vazio`, `antes`,
    # `cada`, `todos` and `abaixo` each fired on fixtures that carry Portuguese on
    # purpose — this gate's own test data, a plan-confidence rubric, a backlog
    # fixture — 22 hits in 14 files, of which one was a defect. A gate whose output
    # is mostly noise is a gate people learn to scroll past, and that costs more
    # than the words it would have caught.
    r"tabela|roteamento"  # english-only: the gate must name what it detects
    r")(?![\w-])",
    re.IGNORECASE,
)

#: A line may keep Portuguese when it says why, on the line itself. The reason is
#: the point: an exemption with no reason is a silent opt-out, which is the thing
#: the gate exists to prevent.
_EXEMPT_RE = re.compile(r"english-only:\s*\S+")

#: Never scanned. Third-party material is not ours to rewrite, and caches and
#: binaries are not prose.
_SKIP_PARTS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", ".mypy_cache",
    ".pytest_cache", ".hypothesis", ".benchmarks",
    "study-material", "tools", "images", "media",
})
_SKIP_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".ico",
    ".woff", ".woff2", ".ttf", ".pyc", ".lock", ".bin",
})


def find_markers(line: str) -> list[str]:
    """The Portuguese markers on this line, or an empty list."""
    return [m.group(1) for m in _MARKER_RE.finditer(line)]


def is_exempt(line: str) -> bool:
    """True when the line declares a reason to keep its Portuguese."""
    return bool(_EXEMPT_RE.search(line))


def scan_text(text: str) -> list[tuple[int, list[str]]]:
    """`(line number, markers)` for every offending line, 1-indexed."""
    findings: list[tuple[int, list[str]]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if is_exempt(line):
            continue
        markers = find_markers(line)
        if markers:
            findings.append((number, markers))
    return findings


def _versioned_files(root: Path) -> list[Path] | None:
    """What git tracks. None when `root` is not a repository.

    Tracked files rather than a directory walk, for the reason
    `tests/test_clean_install.py` already learned the hard way: a walk measures
    the machine it runs on, and `.gitignore` hides exactly the directories that
    would drown the signal.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    files: list[Path] = []
    for rel in result.stdout.splitlines():
        path = Path(rel)
        if _SKIP_PARTS & set(path.parts) or path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        files.append(root / rel)
    return files


#: How many tracked files the LAST `scan_repository` actually read. `_versioned_files`
#: answers None only when `git ls-files` exits non-zero; a repository that TRACKS nothing
#: — a fresh `git init`, a sub-tree passed as `--root`, a worktree whose index is not
#: populated — returns an empty list, and an empty report then printed "english-only:
#: clean" and exited 0. Nothing carried the count out, so the caller could not tell a
#: clean sweep from a sweep of zero files.
_last_scan_file_count = 0


def scan_repository(root: Path) -> dict[str, list[tuple[int, list[str]]]]:
    """Every tracked file with Portuguese outside an exemption."""
    global _last_scan_file_count

    tracked = _versioned_files(root)
    if tracked is None:
        raise ValueError(f"{root} is not a git repository")
    _last_scan_file_count = len(tracked)

    report: dict[str, list[tuple[int, list[str]]]] = {}
    for path in tracked:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings = scan_text(text)
        if findings:
            report[str(path.relative_to(root))] = findings
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = scan_repository(args.root.resolve())
    except ValueError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "files": {
                name: [{"line": n, "markers": m} for n, m in findings]
                for name, findings in report.items()
            },
            "file_count": len(report),
            "files_examined": _last_scan_file_count,
            "line_count": sum(len(f) for f in report.values()),
        }, indent=2, ensure_ascii=False))
        return 1 if report else (0 if _last_scan_file_count else 2)

    if not _last_scan_file_count:
        print(f"english-only: UNCHECKED — 0 tracked file(s) under {args.root}. A repository "
              f"that tracks nothing is not a repository whose prose is in English.",
              file=sys.stderr)
        return 2

    if not report:
        print(f"english-only: clean — {_last_scan_file_count} tracked file(s) examined")
        return 0

    lines = sum(len(f) for f in report.values())
    print(f"english-only: {lines} line(s) in {len(report)} file(s) are not in English\n")
    for name, findings in sorted(report.items()):
        print(f"  {name}")
        for number, markers in findings[:5]:
            print(f"    :{number}  {', '.join(sorted(set(markers)))}")
        if len(findings) > 5:
            print(f"    … and {len(findings) - 5} more line(s)")
    print(
        "\nTranslate them, or — when the Portuguese is the point, as in a quoted "
        "error message or a verbatim citation — keep it and say why on the line:"
        "\n  <text>  # english-only: quoting the tool's own output"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

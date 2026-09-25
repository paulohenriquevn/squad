#!/usr/bin/env python3
"""Refuse Portuguese in a repository that is English by policy.

WHAT IT DECIDES, AND HOW
------------------------
Every tracked file is English except the paths `rules/english-only-allowlist.txt`
declares, each with a reason — product copy, the fixtures of a detector whose input
is Portuguese. Inside every other file, each line is SCORED: the words that are
evidence of Portuguese (its function words, its suffixes, its diacritics) against
the English function words on the same line. A line is Portuguese when that
evidence reaches a floor AND outweighs the English around it.

WHY IT SCORES INSTEAD OF MATCHING A LIST
----------------------------------------
Until 2026-09-25 it matched a closed list of spellings that "cannot be English",
and a closed list over an open vocabulary has no bound on what it misses. The
record of that bound:

  - `install.sh` carried *"exigindo a spec Agent Skills; com o kit instalado"*  # english-only: quoting the line the old list missed
    (2026-08-31) and, for four months, the section header
    *"tabela de roteamento: entregue VAZIA"* — reported clean across 997 files.  # english-only: quoting the line the old list missed
  - `docs/ADR/0025` carried two bold headers of the same shape.
  - Widening the list was measured and did not converge: twelve ordinary words
    produced 22 findings in 14 files, one of them a defect. The other 21 were
    files that carry Portuguese ON PURPOSE, and nothing could say so except a
    per-line marker on every line.

The issue (#130) named the missing signal: WHICH FILES may carry Portuguese is
knowable and belongs in a declaration, and once it is declared the detector can
afford a vocabulary broad enough to catch the next header nobody listed.

MEASURED, 2026-09-25, before the allowlist and the translations landed
----------------------------------------------------------------------
  - This repository, 1200 scanned files (~190k non-blank lines): 130 lines in 43
    files flagged. Every one, read by hand, was Portuguese — fixtures, quoted
    consumer text, and lapses the list never saw (a CHANGELOG line, test
    docstrings, a comment, the other ADR 0025 header). English lines flagged: 0,
    after one (`"sort": "o"`) taught it that a quoted letter is a literal.
  - `~/.claude/CLAUDE.md`, 485 non-blank lines of Portuguese prose: 408 flagged
    (84%). The misses are single-word headers with no Portuguese suffix
    (`**Regras:**`, `### 5. Nomenclatura`) and table rows made of code spans —  # english-only: quoting what the detector misses
    the FILE is caught hundreds of times over, which is what a gate needs.

WHAT IT STILL MISSES, AND WHAT IT CAN MISTAKE
---------------------------------------------
A one-word Portuguese line with no accent and no Portuguese suffix scores one
point and passes; two such words in a row are caught. The other direction: a line
made only of a Portuguese proper name ending in `-ção` scores like a Portuguese
word, because it is one. Keep it with a per-line marker saying why.

WHY THIS EXISTS
---------------
The policy was real and nothing enforced it. Measured on 2026-08-27, before this
landed: 334 Portuguese markers across 21 versioned files in this kit and 93
across 17 in the sibling — including a `CHANGELOG.md` most of whose recent
entries were written in Portuguese by the maintainer of the day.

The cost is not aesthetic. Consumers' agents read these files as instructions,
and a contract written half in one language is a contract whose exact wording
nobody can grep for. It also spreads by example: one consumer wrote an entire
`BACKLOG.md` in Portuguese inside an English-by-policy repository, having read
four sibling registries and copied none of them, because nothing said no.

Usage:
    python3 check_english_only.py [--root PATH] [--json]

Exit codes:
    0 — clean
    1 — Portuguese found outside an exemption
    2 — the root is not a git repository, tracks nothing, or its allowlist is malformed
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

#: A prose word: letters only, and not part of a path, an identifier, an option, a
#: URL or a code span. `com` inside `example.com`, `de` inside `de-duplicate` and `e`
#: in `e.g.` are not words of a sentence.
_WORD_RE = re.compile(r"(?<![\w/\\.\-@$`'])[^\W\d_]+(?![\w/\\\-@(]|\.\w)")

#: English function words. Each one on a line is evidence the line is English, and
#: Portuguese evidence has to outweigh twice their count to call the line Portuguese.
#: Words spelled the same in both languages (`a`, `as`, `do`, `no`, `se`, `e`)
#: are on neither list: `except ValueError as e:` must stay silent.
_ENGLISH_WORDS = frozenset("""
the of and to is in that it for with was on be by this are not or from an which at
have has were but if when what its can will would should must into than then there
their they we you one all any each only also so how why where who does did been
being i he she his her our your my me us them these those such more most other
some no nor here just like over under after before about because while until
through between without within
""".split())

#: Portuguese function words that are also English, or live inside English
#: technical prose: `de facto`, `para-virtualisation`, `em dash`, `Big O`. One point
#: each. (`O(n)` never reaches here: a word followed by `(` is not a prose word.)
_WEAK_PT_WORDS = frozenset("o de para em com que por ou".split())  # english-only: the gate must name what it detects

#: Portuguese function words with no English reading. Two points each: two of them,
#: or one and any other evidence, make a line. One string per line so each line can
#: carry its own exemption — the gate's vocabulary is the one place Portuguese is the
#: point of the code.
_STRONG_PT_WORDS = frozenset((
    "não nao são sao está esta estão estao também tambem então entao porém porem "  # english-only: the gate must name what it detects
    "já até três é você voce vocês voces nós isso isto essa esse essas esses "  # english-only: the gate must name what it detects
    "aquele aquela aquilo nenhum nenhuma porque pelo pela pelos pelas deve devem "  # english-only: the gate must name what it detects
    "pode podem precisa precisam foi foram serão será ser estar ter tem têm há "  # english-only: the gate must name what it detects
    "fica ficou quando onde como mais mas muito muita muitos muitas cada toda "  # english-only: the gate must name what it detects
    "todos todas qual quais seu sua seus suas ele ela eles elas sem sobre entre "  # english-only: the gate must name what it detects
    "após antes depois ainda só aqui ali agora sempre nunca apenas somente um uma "  # english-only: the gate must name what it detects
    "uns umas da dos das na nos nas ao aos à às este estes estas outro outra "  # english-only: the gate must name what it detects
    "outros outras mesmo mesma algum alguma alguns algumas nem pois assim tudo "  # english-only: the gate must name what it detects
    "nada lá cá deste desta disso disto neste nesta nisso numa"  # english-only: the gate must name what it detects
).split())

#: Suffixes English does not produce: `-ção`, `-amento`, `-ável`, `-mente`. Two points,
#: so a lone header like `Descrição` or `Roteamento` is caught.  # english-only: the gate must name what it detects
_STRONG_PT_SUFFIX = re.compile(
    r"(ção|ções|ões|ães|amento|amentos|imento|imentos|ável|ível|áveis|íveis|mente|agem|agens)$"  # english-only: the gate must name what it detects
)

#: Suffixes both languages produce — `tornado`, `libido`, `commando` — worth one point.
_WEAK_PT_SUFFIX = re.compile(r"(ado|ada|ados|adas|ido|ida|idos|idas|ando|endo|indo|eiro|eira|inho|inha)$")

_PT_DIACRITIC = re.compile(r"[ãõçâêôáéíóúà]")

#: Strong words that, capitalised, are the start of a place name instead.
_SAINT_PREFIXES = frozenset({"são", "sao"})  # english-only: the gate must name what it detects

#: How much Portuguese evidence a line needs, whatever the English around it.
_MIN_EVIDENCE = 2


def _word_weight(word: str) -> float:
    """The Portuguese evidence one word carries, 0 when it carries none."""
    lower = word.lower()
    if lower in _SAINT_PREFIXES and word[0].isupper():
        # `são` is a verb ("are"), and `São` is the saint every other Brazilian
        # city is named after. The capital decides which one the line is using.
        return 0.25
    if lower in _STRONG_PT_WORDS:
        return 2
    if lower in _WEAK_PT_WORDS:
        return 1
    if len(lower) > 4 and _STRONG_PT_SUFFIX.search(lower):
        return 2
    weak = bool(_PT_DIACRITIC.search(lower)) or (len(lower) > 5 and bool(_WEAK_PT_SUFFIX.search(lower)))
    if not weak:
        return 0
    # A capitalised word whose only evidence is an accent or a shared suffix is
    # almost always a name — José, Antônio, Ribeiro, Janeiro — and a name inside an
    # English line is English. A quarter point: four names on one line still decide
    # nothing, and a lowercase `café` still counts as the loanword it is.
    return 0.25 if word[0].isupper() else 1


def _is_quoted(line: str, start: int, end: int) -> bool:
    """True when the span is wrapped in a matching pair of quotes."""
    return (0 < start and end < len(line)
            and line[start - 1] == line[end] and line[end] in "\"'")


def find_markers(line: str) -> list[str]:
    """The words that make this line Portuguese, or an empty list when it is not.

    Portuguese evidence must reach `_MIN_EVIDENCE` and exceed twice the English
    function words on the same line — so one loanword, or one quoted term, inside
    an English sentence decides nothing.
    """
    evidence = 0.0
    english = 0
    markers: list[str] = []
    for match in _WORD_RE.finditer(line):
        word = match.group(0)
        if len(word) == 1 and _is_quoted(line, match.start(), match.end()):
            # `"sort": "o"` is a string literal, not the article. Measured: the one
            # English line this repository produced once `o` joined the weak words.
            continue
        if word.lower() in _ENGLISH_WORDS:
            english += 1
            continue
        weight = _word_weight(word)
        if weight:
            evidence += weight
            markers.append(word)
    if evidence >= _MIN_EVIDENCE and evidence > 2 * english:
        return markers
    return []


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


#: How many tracked files the last `scan_repository` left unread because the
#: allowlist declares them. Reported beside the examined count, so a clean verdict
#: says how much of the tree it did not look at.
_last_allowlisted_count = 0

#: The declaration of which paths may carry Portuguese, inside the project's rules
#: directory (`squad.paths.rules_dir` decides which one).
ALLOWLIST_NAME = "english-only-allowlist.txt"


class AllowlistError(ValueError):
    """An allowlist row the gate refuses to honour — named by file and line."""


def load_allowlist(root: Path) -> list[str]:
    """The path globs `<rules>/english-only-allowlist.txt` declares for `root`.

    Each row is `<glob> | <reason>`, matched with `fnmatch` against the tracked
    path relative to the root — so `*` crosses `/`, and `web/locales/pt-BR/*`
    covers the whole tree below it. A missing file is an empty allowlist: every
    path must be English, which is the policy. A row with no reason raises, for the
    reason the per-line marker needs one — an opt-out that says nothing is the
    silent exception this gate exists to prevent.
    """
    for up in Path(__file__).resolve().parents:
        if (up / "squad" / "paths.py").is_file():
            sys.path.insert(0, str(up))
            break
    from squad.paths import rules_dir

    rules = rules_dir(root)
    if rules is None:
        return []
    path = rules / ALLOWLIST_NAME
    if not path.is_file():
        return []
    globs: list[str] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        row = raw.strip()
        if not row or row.startswith("#"):
            continue
        glob, _, reason = (part.strip() for part in row.partition("|"))
        if not glob or not reason:
            raise AllowlistError(
                f"{path.name}:{number}: {row!r} — a row is `<path-glob> | <reason>`, and "
                f"both halves are required. Say why this path may carry Portuguese."
            )
        globs.append(glob)
    return globs


def scan_repository(root: Path) -> dict[str, list[tuple[int, list[str]]]]:
    """Every tracked file with Portuguese outside an exemption or the allowlist."""
    global _last_scan_file_count, _last_allowlisted_count

    tracked = _versioned_files(root)
    if tracked is None:
        raise ValueError(f"{root} is not a git repository")
    allowed = load_allowlist(root)
    scanned = [
        path for path in tracked
        if not any(fnmatch.fnmatchcase(path.relative_to(root).as_posix(), glob) for glob in allowed)
    ]
    _last_scan_file_count = len(scanned)
    _last_allowlisted_count = len(tracked) - len(scanned)

    report: dict[str, list[tuple[int, list[str]]]] = {}
    for path in scanned:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings = scan_text(text)
        if findings:
            report[path.relative_to(root).as_posix()] = findings
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
            "files_allowlisted": _last_allowlisted_count,
            "line_count": sum(len(f) for f in report.values()),
        }, indent=2, ensure_ascii=False))
        return 1 if report else (0 if _last_scan_file_count else 2)

    if not _last_scan_file_count:
        print(f"english-only: UNCHECKED — 0 tracked file(s) under {args.root}. A repository "
              f"that tracks nothing is not a repository whose prose is in English.",
              file=sys.stderr)
        return 2

    if not report:
        print(f"english-only: clean — {_last_scan_file_count} tracked file(s) examined, "
              f"{_last_allowlisted_count} allowlisted in {ALLOWLIST_NAME}")
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
        f"\nA file that is Portuguese BY DESIGN (product copy) is declared instead, in "
        f"{ALLOWLIST_NAME}:\n  <path-glob> | <why this path ships Portuguese>"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

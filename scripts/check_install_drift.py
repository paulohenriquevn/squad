#!/usr/bin/env python3
"""B-103 — has a consumer's install and this kit drifted, and which way?

WHY THIS EXISTS
---------------
Twenty-two fixes to this kit lived for weeks inside one consumer's gitignored `.claude/` install
and nowhere else. Nobody hid them. Nothing looked. They surfaced only because someone diffed the
two trees by hand, and the diff took an afternoon to classify.

`sync_consumers.py` answers the other direction — "is the consumer behind the kit" — and refuses
to auto-merge a `LOCAL_CHANGE`. That refusal is right, and it is also where the work went to die:
a file the script correctly declined to overwrite is a file whose improvement nobody carried back.

So this reports the direction the other script cannot, and it fails when there is unharvested work,
because a report nobody is required to read is a report that goes unread.

WHAT IT COMPARES, AND WHY NOT A DIFF
------------------------------------
Line SETS, ignoring blank lines. The question is not "are these byte-identical" — they stop being
that the moment a comment is reworded — but "does one side hold work the other lacks".

    IDENTICAL       the same non-blank lines, in any arrangement
    INSTALL_AHEAD   the install holds lines the kit does not; the kit holds none the install lacks
    KIT_AHEAD       the mirror image
    DIVERGED        BOTH hold unique lines

DIVERGED is the only class that needs a human, and it is the class a blind copy destroys. Measured
on `run_code_quality.py`: copying the install over the kit would have deleted B-092's
zero-detector check, the one fix that had already made it home.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not merge, and it does not rank. A file where a comment was reworded reads as INSTALL_AHEAD
exactly like a file where a bug was fixed, because from a line set the two are indistinguishable —
saying otherwise would be a guess wearing a verdict's clothes.

`only_in_kit` is reported and never fails the run: a consumer missing a file is simply a consumer
that has not reinstalled, which is `sync_consumers.py`'s question.
"""
from __future__ import annotations

import argparse
import enum
import sys
from dataclasses import dataclass, field
from pathlib import Path


class Drift(enum.Enum):
    IDENTICAL = "identical"
    INSTALL_AHEAD = "install_ahead"
    KIT_AHEAD = "kit_ahead"
    DIVERGED = "diverged"


def _lines(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {line for line in text.split("\n") if line.strip()}


def classify_file(install_file: Path, kit_file: Path) -> Drift:
    """Which side, if either, holds lines the other lacks."""
    a, b = _lines(install_file), _lines(kit_file)
    install_only, kit_only = a - b, b - a
    if not install_only and not kit_only:
        return Drift.IDENTICAL
    if install_only and kit_only:
        return Drift.DIVERGED
    return Drift.INSTALL_AHEAD if install_only else Drift.KIT_AHEAD


# Directories a consumer generates for itself. They are that project's artifacts, not kit code,
# and reporting them would bury the signal under 38 rows of noise (measured on theokit-tui).
_CONSUMER_LOCAL = ("__pycache__", ".pytest_cache", ".benchmarks", "knowledge-base")

#: Arquivos que pertencem ao PROJETO mesmo vivendo num diretório que o kit também tem.
#: `agents/<domínio>.md` descreve o repositório do consumidor — colhê-lo para o kit é o
#: oposto do que ele é (grill kit-domain-agents-install, decisão 5). O `README.md` fica
#: no escopo: descreve o mecanismo de roteamento, não um domínio.
def _is_consumer_owned(rel: str) -> bool:
    parts = Path(rel).parts
    return len(parts) == 2 and parts[0] == "agents" and parts[1] != "README.md"


#: O consumidor recebe `settings.plugin.json` COMO `settings.json` — o `settings.json`
#: do kit é o de desenvolvimento, com outros caminhos de hook. Comparar os dois acusa
#: DIVERGED em toda instalação, para sempre. Medido no `speculative`: idênticos como
#: JSON, reportados como divergentes.
_INSTALL_TO_KIT_ALIAS = {"settings.json": "settings.plugin.json"}


def _relevant(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _CONSUMER_LOCAL for part in rel.parts):
            continue
        if _is_consumer_owned(str(rel)):
            continue
        found[str(rel)] = path
    return found


@dataclass
class DriftReport:
    counts: dict[Drift, int] = field(default_factory=dict)
    by_class: dict[Drift, list[str]] = field(default_factory=dict)
    only_in_install: list[str] = field(default_factory=list)
    only_in_kit: list[str] = field(default_factory=list)
    _kit_dirs: frozenset[str] = frozenset()

    @property
    def unharvested_files(self) -> list[str]:
        """Install-only files sitting in a directory this repository ALSO has.

        The distinction is what keeps the check readable. B-103's `_layout.py` and
        `bump_version.py` were whole files present in one tree only, under `implement/scripts/`
        and `release/scripts/` — directories the kit has — and missing them would have cost three
        items. Whereas `review-b052-…-knowledge/` is a directory the kit does not have at all,
        because the CONSUMER generates one per review; there were 38 of them, and failing on those
        would make this red on every project that runs /review. A check that is always red is a
        check nobody reads.
        """
        return [
            rel for rel in self.only_in_install
            if str(Path(rel).parent) in self._kit_dirs
        ]

    @property
    def needs_attention(self) -> bool:
        """The install holds work this repository does not."""
        return bool(
            self.counts.get(Drift.INSTALL_AHEAD)
            or self.counts.get(Drift.DIVERGED)
            or self.unharvested_files
        )


def scan(install_root: Path, kit_root: Path) -> DriftReport:
    install, kit = _relevant(install_root), _relevant(kit_root)
    # O consumidor recebe `settings.plugin.json` COMO `settings.json`; comparar com o
    # `settings.json` do kit (o de desenvolvimento) acusa DIVERGED em toda instalação.
    resolved_kit = dict(kit)
    for install_name, kit_name in _INSTALL_TO_KIT_ALIAS.items():
        if install_name in install and kit_name in kit:
            resolved_kit[install_name] = kit[kit_name]
            resolved_kit.pop(kit_name, None)

    report = DriftReport(
        counts={d: 0 for d in Drift},
        by_class={d: [] for d in Drift},
        only_in_install=sorted(set(install) - set(resolved_kit)),
        only_in_kit=sorted(set(resolved_kit) - set(install)),
        _kit_dirs=frozenset(str(Path(rel).parent) for rel in resolved_kit),
    )
    for rel in sorted(set(install) & set(resolved_kit)):
        verdict = classify_file(install[rel], resolved_kit[rel])
        report.counts[verdict] += 1
        report.by_class[verdict].append(rel)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", type=Path, required=True,
                        help="a consumer's installed skills directory (…/.claude/skills)")
    parser.add_argument("--kit", type=Path, default=Path(__file__).parent.parent / "skills",
                        help="this repository's skills directory")
    args = parser.parse_args(argv)

    for label, root in (("install", args.install), ("kit", args.kit)):
        if not root.is_dir():
            print(f"check-install-drift: {label} path is not a directory: {root}", file=sys.stderr)
            return 2

    report = scan(args.install, args.kit)

    for verdict in (Drift.DIVERGED, Drift.INSTALL_AHEAD, Drift.KIT_AHEAD):
        files = report.by_class[verdict]
        if files:
            print(f"{verdict.value}: {len(files)}")
            for rel in files:
                print(f"    {rel}")
    if report.unharvested_files:
        print(f"unharvested (install-only, in a directory the kit has): {len(report.unharvested_files)}")
        for rel in report.unharvested_files:
            print(f"    {rel}")
    consumer_local = len(report.only_in_install) - len(report.unharvested_files)
    print(f"identical: {report.counts[Drift.IDENTICAL]}   only_in_kit: {len(report.only_in_kit)}"
          f"   consumer-local: {consumer_local}")

    if report.needs_attention:
        print(
            "\ncheck-install-drift: the install holds work this repository does not. "
            "DIVERGED files need a human — a copy in either direction deletes the other side's fix.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

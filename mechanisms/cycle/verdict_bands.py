#!/usr/bin/env python3
"""Which band each verdict is in, read from the one table that declares it.

    python3 mechanisms/cycle/verdict_bands.py --verdict PRE_RELEASED
    python3 mechanisms/cycle/verdict_bands.py --band clean

## What this replaces

`rules/blocking-verdicts.txt` exists because the list of "what holds an item" had
been written twice and the two copies disagreed. Its complement — what counts as
CLEAN — was then born as `_CLEAN_VERDICTS`, a frozenset hardcoded inside
`mechanisms/gates/check_phase_drift.py`, with no file and no owner.

Measured 2026-09-08: of 47 verdicts reachable in the event stream, 14 were in the
blocking list, 16 in the frozenset, and **23 in neither**. The consequence was a
silent one — `check_phase_drift` reads "was the previous verdict clean?" to tell
legitimate rework from a step out of sequence, and an unclassified verdict was
assumed not-clean, so the disorder check switched itself off for half the
vocabulary with nothing in the output to notice.

## This is not a renaming

`cycle-rule-schema.md § Why each vocabulary differs` argues per cycle why the tokens
diverge, and those arguments hold — collapsing `ITEM_KILLED` into `INVALID` would
file the cycle's most valuable result as a failure. The names carry domain meaning a
band cannot. Only the classification is unified.

That document is where a band is ARGUED; this table is where it is COMPUTED, and
`check_verdict_bands.py` fails when a verdict declared in a rule is missing here.

## Band and blocking are independent

Deriving one from the other is wrong in both directions: `FAIL_SOFT` is `redo` and
does not block (blocking it would wall every rework loop that is working), while
`NEEDS_FIXES` is `redo` and does block. `blocking-verdicts.txt` keeps its own answer
to its own question.

## An unknown verdict raises

The failure this module replaces was a silent default. Answering confidently about a
token the registry has never seen would rebuild it one layer down.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Band(Enum):
    """What kind of outcome a verdict reports."""

    CLEAN = "clean"
    CAVEATS = "caveats"
    REDO = "redo"
    STRUCTURAL = "structural"
    #: Grades nothing. Its own band precisely because forcing these into a scoring
    #: column is what produced a classification nobody could state.
    ORTHOGONAL = "orthogonal"


#: Declared order, for reports that group by band.
BANDS: tuple[Band, ...] = (
    Band.CLEAN, Band.CAVEATS, Band.REDO, Band.STRUCTURAL, Band.ORTHOGONAL,
)

_BY_NAME = {b.value: b for b in BANDS}

#: For the drift question, a caveated pass is a pass: a return after one is disorder
#: exactly as much as a return after a plain pass. `orthogonal` is NOT clean — it
#: graded nothing, so it cannot report that anything succeeded.
_CLEAN_BANDS = frozenset({Band.CLEAN, Band.CAVEATS})

REGISTRY_FILENAME = "verdict-bands.txt"


@dataclass(frozen=True)
class BandEntry:
    """One verdict's classification, with the reasoning a reader can disagree with."""

    verdict: str
    band: Band
    reason: str


def default_registry() -> Path:
    return Path(__file__).resolve().parents[2] / "rules" / REGISTRY_FILENAME


def load_bands(path: Path | None = None) -> dict[str, BandEntry]:
    """Parse the registry.

    Raises ValueError on a malformed row, an unknown band, a missing reason, or a
    verdict classified twice — that last one being the disagreement
    `blocking-verdicts.txt` was created to end, reappearing inside its successor.
    """
    registry = path or default_registry()
    entries: dict[str, BandEntry] = {}

    for raw in registry.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            raise ValueError(f"malformed row in {registry.name}: {raw.strip()!r}")
        verdict, band_name, reason = parts
        if band_name not in _BY_NAME:
            raise ValueError(
                f"{verdict}: unknown band {band_name!r}. "
                f"One of {', '.join(_BY_NAME)}"
            )
        if not reason:
            raise ValueError(
                f"{verdict} is classified with no reason. A classification nobody "
                "can argue with is a table, not a decision"
            )
        if verdict in entries:
            raise ValueError(
                f"{verdict} is classified twice ({entries[verdict].band.value} and "
                f"{band_name}). One token, one band"
            )
        entries[verdict] = BandEntry(verdict, _BY_NAME[band_name], reason)

    return entries


def load_local_bands(registry: Path) -> tuple[dict[str, BandEntry], list[str]]:
    """The consumer's own classifications, and the names it tried to take from the kit.

    A project with a cycle of its own emits verdicts of its own, and `check_verdict_bands`
    blocks until every declared verdict names a band. The only registry was the kit's, and
    `install.sh` overwrites it — so the consumer could classify, go green, and have the
    edit reverted by the next update. Measured on one consumer: four verdicts, registered
    by hand, gone after `--merge`.

    The kit's file stays authoritative for the kit's own entries. A local row naming a
    verdict the kit already classifies is returned as a CLASH rather than applied: quietly
    reclassifying `PASS` is the drift a single registry was protecting against, and moving
    to two files must not buy the extension at that price.
    """
    local = registry.with_name(registry.stem + ".local" + registry.suffix)
    if not local.is_file():
        return {}, []
    entries = load_bands(local)
    kit = load_bands(registry)
    clashes = sorted(name for name in entries if name in kit)
    return {k: v for k, v in entries.items() if k not in kit}, clashes


def band_of(verdict: str, path: Path | None = None) -> Band:
    """The band `verdict` belongs to. Raises KeyError if it is not classified."""
    entries = load_bands(path)
    key = verdict.strip().upper()
    if key not in entries:
        raise KeyError(
            f"{key} is not classified in rules/{REGISTRY_FILENAME}. Classify it "
            "there rather than defaulting: a silent default is what this registry "
            "replaced"
        )
    return entries[key].band


def clean_verdicts(path: Path | None = None) -> frozenset[str]:
    """The verdicts that count as a clean pass — what `check_phase_drift` reads."""
    return frozenset(
        v for v, e in load_bands(path).items() if e.band in _CLEAN_BANDS
    )


def by_band(path: Path | None = None) -> dict[Band, list[str]]:
    grouped: dict[Band, list[str]] = {b: [] for b in BANDS}
    for verdict, entry in sorted(load_bands(path).items()):
        grouped[entry.band].append(verdict)
    return grouped


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Look up a verdict's band.")
    ap.add_argument("--registry", type=Path, default=None)
    ap.add_argument("--verdict", help="report the band of one verdict")
    ap.add_argument("--band", choices=[b.value for b in BANDS],
                    help="list every verdict in one band")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        entries = load_bands(args.registry)
    except (OSError, ValueError) as exc:
        print(f"verdict_bands: {exc}", file=sys.stderr)
        return 2

    if args.verdict:
        try:
            band = band_of(args.verdict, args.registry)
        except KeyError as exc:
            print(f"verdict_bands: {exc}", file=sys.stderr)
            return 1
        entry = entries[args.verdict.strip().upper()]
        if args.json:
            print(json.dumps({"verdict": entry.verdict, "band": band.value,
                              "reason": entry.reason}, indent=2))
        else:
            print(f"{entry.verdict}: {band.value}")
            print(f"  {entry.reason}")
        return 0

    grouped = by_band(args.registry)
    wanted = [_BY_NAME[args.band]] if args.band else list(BANDS)
    if args.json:
        print(json.dumps({b.value: grouped[b] for b in wanted}, indent=2))
    else:
        for b in wanted:
            print(f"{b.value} ({len(grouped[b])})")
            for v in grouped[b]:
                print(f"  {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Five stacked bands pushed the work below the fold.

Each strip added to the top answered a real question — the verdict, delivery, WIP,
orphaned work — and each was added on its own merits. Together they took the screen: the
owner's words were *"o header tomou conta da tela"*, and a board whose cards need
scrolling to reach has traded the thing it exists for.

Two of them were also duplicates. `#tallies` already carried `done`, `killed` and
`running now`; the delivery strip repeated the first two and the WIP strip repeated the
third in different words. A number shown twice in two shapes is worse than a number shown
once: the reader has to decide whether they disagree.

WHAT THE PAGE LEADS WITH NOW

One band — the verdict — because it is the only line a reader with four minutes will
finish. Everything else joins `#tallies`, which is one row of counters and was already
there. Orphaned work joins the notices, where the other "this could not be placed"
messages live.

The count is asserted rather than described. A limit in prose is a limit nobody notices
crossing, and this file exists because four separate good decisions crossed it together.
"""
from __future__ import annotations

import re
from pathlib import Path

_HTML = Path(__file__).resolve().parents[1] / "scripts" / "board.html"

#: Blocks between `<body>` and the board itself. Five was the state that pushed the work
#: below the fold; the ceiling is set at the count after consolidation so the next
#: addition has to argue for itself rather than arrive unnoticed.
MAX_BANDS_ABOVE_THE_BOARD = 12


def _blocks_above_the_board() -> list[str]:
    html = _HTML.read_text(encoding="utf-8")
    body = html[html.index("<body"):html.index('<main class="board"')]
    return [f"{tag}.{cls.split()[0]}"
            for tag, cls in re.findall(r'<(div|header|section|nav)[^>]*(?:class|id)="([^"]+)"', body)]


def test_the_page_does_not_bury_the_board() -> None:
    blocks = _blocks_above_the_board()

    assert len(blocks) <= MAX_BANDS_ABOVE_THE_BOARD, (
        f"{len(blocks)} blocks sit above the board: {blocks}. Each one may be worth "
        f"showing and together they push the cards below the fold — which is the one "
        f"thing the page cannot afford to do")


def test_the_verdict_is_the_only_band_of_its_own() -> None:
    """Everything else earns its place inside an existing row."""
    html = _HTML.read_text(encoding="utf-8")
    body = html[html.index("<body"):html.index('<main class="board"')]

    for gone in ('id="delivery"', 'id="wip"', 'id="orphan"'):
        assert gone not in body, (
            f'{gone} is still a band of its own; its numbers belong in `#tallies` '
            f'(delivery, wip) or in `#notice` (orphan), where the page already has a '
            f'row for that kind of fact')
    assert 'id="headline"' in body, "the verdict lost its band"


def test_the_numbers_still_reach_the_page() -> None:
    """Consolidating must not drop them. Each has a renderer that writes into the row
    it now shares."""
    html = _HTML.read_text(encoding="utf-8")

    for token in ("throughput_per_day", "wip", "unattributed", "phases_without_record"):
        assert token in html, f"{token} stopped reaching the page during consolidation"

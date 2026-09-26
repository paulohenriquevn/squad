r"""The columns are the content, and the chrome may not take the screen from them.

MEASURED ON A CONSUMER, 2026-09-21, at 1850×876:

    header + notices   761px
    tabs                37px
    the columns         17px   <- what the board exists to show
    footer              37px

Ten notices, each a full-width row for one line of text, pushed the lanes to two
percent of the viewport. Every one of those notices is worth keeping — each names work
the stream could not place, and the reader's next move needs the slug — but a panel
that grows without a ceiling takes the screen from the thing it annotates.

So the panel is `<details>`, collapsed by default and capped at a third of the
viewport when open. These tests hold the structure rather than the pixels: a layout
test that asserts heights is a test that fails when a font changes, and this file has
to survive a restyle to be worth keeping.
"""
from __future__ import annotations

import re
from pathlib import Path

BOARD = Path(__file__).resolve().parents[1] / "scripts" / "board.html"
HTML = BOARD.read_text(encoding="utf-8")


def test_the_notices_are_collapsible() -> None:
    """Not deleted, not always-open: one line when quiet, full list on demand."""
    assert "<details class=\"notices\"" in HTML


def test_the_open_panel_is_capped() -> None:
    """A ceiling in VIEWPORT units, so it holds at any window size."""
    body = re.search(r"\.notices-body\s*\{[^}]*\}", HTML, re.S)

    assert body, "the notices body has no rule of its own"
    assert "max-height" in body.group(0), "an uncapped panel is the original defect"
    assert "vh" in body.group(0), (
        "a cap in px stops being a fraction of the screen the moment the window changes"
    )
    assert "overflow-y: auto" in body.group(0), (
        "capped without scrolling hides notices instead of collapsing them"
    )


def test_the_count_is_visible_while_collapsed() -> None:
    """Eight problems must never look like none."""
    summary = re.search(r"<summary><b>\$\{notices\.length\}</b>", HTML)

    assert summary, "the collapsed panel does not say how many notices it holds"


def test_the_lanes_still_take_the_remaining_space() -> None:
    """The flex contract that makes the cap mean something."""
    zone = re.search(r"\.zone\s*\{[^}]*\}", HTML, re.S)

    assert zone and "flex: 1 1 auto" in zone.group(0)
    assert "min-height: 0" in zone.group(0), (
        "without min-height:0 a flex child refuses to shrink below its content and the "
        "cap on the panel buys nothing"
    )


def test_the_panel_state_survives_a_re_render() -> None:
    """The page re-renders on every stream event; a reader working through the list
    would have it shut under them several times a minute."""
    assert "localStorage.setItem(\"board.notices\"" in HTML
    assert "NOTICES_OPEN" in HTML

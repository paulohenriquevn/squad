"""A document nobody wrote does not become one by being touched.

`score_product_alignment.score()` asks the filesystem whether each of the four
cascade documents exists and never asks what is in it:

    if not path.is_file():
        rep.missing_docs.append(name)
        texts[name] = ""          # the absent one becomes an empty string

The line below the cap already makes the two cases identical for every criterion
that follows — a missing document and an empty one are scored from the same `""`.
Only the cap separates them, and it separates them on the wrong question.

Measured 2026-09-19 with four files each containing one heading line:

    verdict: NEEDS_REVISION | score: 35.3% | hard_caps: []

`touch` converts `INVALID` into a recoverable verdict and publishes "a third of
this is done" over nothing. The 35.3% is not noise either — it is six criteria
that are vacuously true of emptiness (`no placeholder` ×4, `0 dangling
citation(s)` ×2). Those six are legitimate penalty criteria and stay as they are;
a real document can fail them. What must not stand is a cascade of four empty
files reaching a verdict that says revise rather than one that says there is
nothing here.

This is the defect this repository names most often, at the level of the cap: a
check that could not measure its subject reported the recoverable answer.

WHAT "EMPTY" MEANS HERE, and the line is drawn narrowly on purpose. A document is
empty when nothing remains after removing whitespace and heading lines — the
shape a scaffold leaves behind. A document with a heading AND a paragraph is a
PARTIAL document, and partial is exactly what `NEEDS_REVISION` is for. Widening
this to "scores zero everywhere" would call a badly structured but genuinely
written document missing, which is a different and worse lie.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCORER = _REPO / "skills" / "brainstorm-pieces" / "scripts" / "score_product_alignment.py"
sys.path.insert(0, str(_REPO))

from squad.paths import write_wiki_dir  # noqa: E402

_DOCS = ("product-vision.md", "objectives.md", "trd.md", "technical-pieces.md")


def _tree(tmp_path: Path, body: str | dict[str, str]) -> Path:
    product = write_wiki_dir(tmp_path, "product")
    product.mkdir(parents=True, exist_ok=True)
    for name in _DOCS:
        text = body[name] if isinstance(body, dict) else body
        (product / name).write_text(text, encoding="utf-8")
    return tmp_path


def _run(root: Path) -> tuple[int, dict]:
    import json

    proc = subprocess.run([sys.executable, str(_SCORER), "--root", str(root), "--json"],
                          capture_output=True, text=True, check=False)
    return proc.returncode, json.loads(proc.stdout)


@pytest.mark.parametrize("body", ["", "\n\n  \n", "# Product vision\n",
                                  "# Title\n\n## Another heading\n\n"],
                         ids=["zero-bytes", "whitespace", "one-heading", "headings-only"])
def test_a_scaffold_of_empty_files_is_invalid(tmp_path: Path, body: str) -> None:
    code, report = _run(_tree(tmp_path, body))
    assert report["verdict"] == "INVALID", (
        f"four empty documents scored {report['score_pct']}% and asked for a "
        f"revision of something nobody has written")
    assert code == 2, code
    assert "empty_document" in report["hard_caps"], report["hard_caps"]


def test_the_report_names_which_documents_were_empty(tmp_path: Path) -> None:
    """Named, not counted. "One of four is empty" sends the reader to open all four."""
    _, report = _run(_tree(tmp_path, {**dict.fromkeys(_DOCS, "# x\n\nreal prose here\n"),
                                      "trd.md": "# TRD\n"}))
    assert report["empty_documents"] == ["trd.md"], report.get("empty_documents")


def test_an_empty_document_is_reported_apart_from_an_absent_one(tmp_path: Path) -> None:
    """`missing_documents` must keep meaning what it says: the file is not there.

    Calling a file that exists "missing" would send somebody to create a file they
    already have, which is the one thing worse than not reporting it.
    """
    root = _tree(tmp_path, "# x\n")
    (write_wiki_dir(root, "product") / "trd.md").unlink()
    _, report = _run(root)
    assert report["missing_documents"] == ["trd.md"], report["missing_documents"]
    assert "trd.md" not in report["empty_documents"], report["empty_documents"]
    assert sorted(report["empty_documents"]) == sorted(
        [d for d in _DOCS if d != "trd.md"]), report["empty_documents"]


def test_a_partial_document_is_still_a_revision_and_not_an_absence(tmp_path: Path) -> None:
    """The line, pinned from the other side. Partial is what NEEDS_REVISION is for."""
    _, report = _run(_tree(tmp_path, "# Vision\n\nSomebody wrote a paragraph here.\n"))
    assert "empty_document" not in report["hard_caps"], report["hard_caps"]
    assert report["verdict"] in ("NEEDS_REVISION", "AWAITING_REVIEW"), report["verdict"]

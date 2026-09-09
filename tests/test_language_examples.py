"""The languages the config offers must be the ones the detectors implement.

WHY THIS EXISTS
---------------
`rules/code-quality-languages.txt` listed nine languages in its commented
examples while `check_symbol_fab._SUPPORTED_LANGUAGES` held four. Enabling one
of the other five does not degrade gracefully: it produces `languages_skipped`
with `no detector implementation`, then the hard cap `no_languages_audited`,
then `verdict: INVALID` — on every run, with no configuration that recovers.

Measured on a consumer whose repository is JavaScript (11 `.mjs`, zero `.ts`).
It followed the commented `javascript` example, got permanent INVALID, and the
only available workaround was declaring `typescript` on a tree with no
TypeScript in it — a false declaration kept honest by an eight-line comment.

The file now marks the unimplemented ones. This test is what keeps the marking
true: a detector added or removed without touching the config makes it fail,
because a comment nothing recomputes is a claim that rots. That sentence is the
kit's own, from `pyproject.toml`, about a count that said 64 while the tree held
80.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "skills" / "code-quality" / "scripts"))

from check_symbol_fab import _SUPPORTED_LANGUAGES  # noqa: E402

CONFIGS = (
    PROJECT_ROOT / "rules" / "code-quality-languages.txt",
    PROJECT_ROOT / "rules" / "templates" / "code-quality-languages.txt",
)

#: An example line a reader could copy: `# python | pyproject.toml | ENABLED`.
#: The `[NO DETECTOR …]` prefix deliberately breaks this shape, which is how the
#: marking works — a marked line is no longer copyable as an example.
_COPYABLE_EXAMPLE_RE = re.compile(r"^#\s*([a-z]+)\s*\|", re.MULTILINE)


@pytest.mark.parametrize("config", CONFIGS, ids=lambda p: p.parent.name + "/" + p.name)
def test_no_example_offers_a_language_without_a_detector(config: Path) -> None:
    """Every copyable example names a language the detectors implement."""
    offered = set(_COPYABLE_EXAMPLE_RE.findall(config.read_text(encoding="utf-8")))
    unimplemented = sorted(offered - _SUPPORTED_LANGUAGES)
    assert unimplemented == [], (
        f"{config.name} offers {unimplemented} as copyable examples and no detector "
        "implements them — enabling one yields permanent INVALID, not a soft failure"
    )


@pytest.mark.parametrize("config", CONFIGS, ids=lambda p: p.parent.name + "/" + p.name)
def test_the_note_lists_exactly_the_implemented_languages(config: Path) -> None:
    """The header's IMPLEMENTED list matches the detectors.

    Without this, adding a detector leaves the file telling readers the language
    is unavailable — the same defect in the opposite direction, and the one that
    is harder to notice because nothing fails.
    """
    text = config.read_text(encoding="utf-8")
    match = re.search(r"^#\s*IMPLEMENTED:\s*(.+)$", text, re.MULTILINE)
    assert match, f"{config.name} lost its IMPLEMENTED note"
    listed = {lang.strip() for lang in match.group(1).split(",") if lang.strip()}
    assert listed == set(_SUPPORTED_LANGUAGES), (
        f"{config.name} says {sorted(listed)}; the detectors implement "
        f"{sorted(_SUPPORTED_LANGUAGES)}"
    )

"""The gate carried link-checking machinery and never ran it.

`check_xrefs.py` runs in CI and in `verify_ecosystem`. It defined `LINK_RE` and a
function that used it, and that function had ZERO callers — a checker that
existed and did not run, which is this kit's most-found defect.

Turning it on as written would have been worse than leaving it off. Measured
before replacing it: it also resolved every backtick-quoted token that looked
like a path, and reported **1451** broken references — nearly all a bare filename
(`alignment_judge.py`) resolved against whichever directory cited it. A gate with
that signal-to-noise gets switched off, and the silence after that is
indistinguishable from a clean repository.

Markdown links are unambiguous about their target. On the same tree: 234 relative
links, 21 broken, every one real — three rule files pointing at a document that
moved to `skills/_kit-rules/`, a template off by one directory level, and a
`_kit-rules` file reaching for `../skills/` from inside `skills/`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

from check_xrefs import broken_markdown_links  # noqa: E402


def test_this_repository_has_no_broken_markdown_links() -> None:
    """The 21 found on 2026-09-02 are fixed; this keeps them fixed."""
    broken = broken_markdown_links(_REPO)

    assert not broken, "\n".join(f"  {f} -> {t}" for f, t in broken)


def test_a_broken_link_is_found(tmp_path: Path) -> None:
    """Without this the assertion above passes on an empty sweep."""
    (tmp_path / "a.md").write_text("see [the rule](rules/gone.md)\n", encoding="utf-8")

    assert broken_markdown_links(tmp_path) == [("a.md", "rules/gone.md")]


def test_an_external_link_is_not_a_path(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "[x](https://example.com) [y](#anchor) [z](mailto:a@b.c) [w](file://~/x.md)\n",
        encoding="utf-8")

    assert broken_markdown_links(tmp_path) == []


def test_an_anchor_on_a_real_file_still_resolves(tmp_path: Path) -> None:
    (tmp_path / "b.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("[b](b.md#section)\n", encoding="utf-8")

    assert broken_markdown_links(tmp_path) == []


def test_the_wiki_resolves_absolute_links_from_its_own_root(tmp_path: Path) -> None:
    """Wiki links are written `/sops/index.md` because the wiki is served from
    that directory. Reading them as filesystem paths reported ten false positives
    at once — and ten false positives is how a gate gets disabled."""
    (tmp_path / "wiki" / "sops").mkdir(parents=True)
    (tmp_path / "wiki" / "sops" / "index.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "wiki" / "index.md").write_text("[sops](/sops/index.md)\n", encoding="utf-8")

    assert broken_markdown_links(tmp_path) == []


def test_an_absolute_link_outside_the_wiki_is_left_alone(tmp_path: Path) -> None:
    """A filesystem path in a document is not this gate's business, and guessing
    at one is how a checker earns findings nobody can act on."""
    (tmp_path / "a.md").write_text("[etc](/etc/hosts)\n", encoding="utf-8")

    assert broken_markdown_links(tmp_path) == []


def test_backticked_filenames_are_not_treated_as_links() -> None:
    """The 1451. A bare name in prose says what a thing is called, not where it
    lives, and resolving it against the citing directory invents a path nobody
    wrote."""
    import inspect

    from check_xrefs import broken_markdown_links as fn
    source = inspect.getsource(fn)

    assert "BACKTICK_PATH_RE" not in source
    assert "1451" in source, "the measurement that decided this belongs beside it"


def test_a_document_the_kit_keeps_but_does_not_install_is_not_reported(tmp_path: Path) -> None:
    """`install.sh` copies skills, rules, hooks, commands, mechanisms and squad —
    not README, CONTRIBUTING, SECURITY, LICENSE or wiki/. A link to one of those
    resolves where it is written and cannot resolve where the kit is installed.

    Measured on a fresh install on 2026-09-02, which is how this was found: the
    check's first run against one produced nine identical WARNs, for something no
    consumer can fix. A finding nobody can act on is how a gate loses its reader.
    """
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "a.md").write_text(
        "see [contributing](../CONTRIBUTING.md) and [wiki](../wiki/x.md)\n",
        encoding="utf-8")

    assert broken_markdown_links(tmp_path) == []


def test_the_same_link_IS_reported_where_the_document_should_exist(tmp_path: Path) -> None:
    """The exemption is for absence by design, not a blanket pardon: in a tree
    that has a `wiki/`, a link into it that misses is still a broken link."""
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "real.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "wiki" / "a.md").write_text("[gone](/missing.md)\n", encoding="utf-8")

    assert broken_markdown_links(tmp_path) == [("wiki/a.md", "/missing.md")]

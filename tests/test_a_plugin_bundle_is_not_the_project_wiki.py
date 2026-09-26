"""A bare `wiki/` is read as this project's bundle only when it has the kit's shape.

`squad.paths.wiki_dir` falls back to the legacy roots `.claude/wiki` and `wiki` for a
consumer that has not moved its bundle into `.squad/wiki/`. The fallback asked only
whether the directory existed. Two plugins write their own OKF bundle to exactly
`<project>/wiki/` by default — `loop-system-cartography` (`--wiki-dir`, default
`<TARGET>/wiki`) and `loop-project-purge` (`WIKI_DIR=wiki`) — so after either one ran,
the kit's readers took that plugin's bundle for the project's durable knowledge, and
`check_data_root` reported it as Squad data the project had not migrated.

The kit's own legacy bundle carries no marker file: it was written before one could be
asked for. What it does carry is a shape. Across the whole history of this repository,
the kit wrote exactly six leaves into a bundle — `product`, `decisions`, `sops`,
`design`, `references`, `opportunities` — plus the two files every OKF bundle reserves,
`index.md` and `log.md`. A plugin bundle is organised by its own concept types
(`components/`, `entities/`, `flows/` for cartography) or holds concepts at its root.
So the positive evidence is: at least one of the kit's leaves, and nothing the kit never
writes.

`.claude/wiki` is not held to that test. It sits inside the installed kit's directory,
where no plugin writes by default, and its location is the evidence.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))
sys.path.insert(0, str(_REPO))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
from check_data_root import check_project, main  # noqa: E402 — post-bootstrap import

from squad.paths import wiki_dir  # noqa: E402 — post-bootstrap import


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _cartography_bundle(root: Path) -> Path:
    """The shape `loop-system-cartography` writes: a root index naming its producer,
    and concepts grouped by the plugin's own types."""
    wiki = root / "wiki"
    _write(wiki / "index.md", '---\nokf_version: "0.2"\n---\n\n# as-is knowledge bundle\n'
                              "- **Producer:** `loop-system-cartography/0.2.4`\n")
    _write(wiki / "log.md", "# Log\n")
    _write(wiki / "components" / "store.md", "---\ntype: component\n---\n# store\n")
    _write(wiki / "flows" / "checkout.md", "---\ntype: flow\n---\n# checkout\n")
    return wiki


def _purge_bundle(root: Path) -> Path:
    """The shape `loop-project-purge` writes: an index and concepts at the root."""
    wiki = root / "wiki"
    _write(wiki / "index.md", '---\nokf_version: "0.2"\n---\n\n# Project knowledge\n')
    _write(wiki / "log.md", "# Log\n")
    _write(wiki / "architecture.md", "---\ntype: concept\n---\n# architecture\n")
    return wiki


# ── readers ──────────────────────────────────────────────────────────────────


def test_a_cartography_bundle_is_not_the_project_wiki(tmp_path: Path) -> None:
    _cartography_bundle(tmp_path)

    assert wiki_dir(tmp_path) is None


def test_a_leaf_inside_a_plugin_bundle_is_not_the_project_leaf(tmp_path: Path) -> None:
    """The repro the issue gives: a leaf the project never wrote, answered from the
    plugin's bundle because a directory of that name happened to exist in it."""
    wiki = _cartography_bundle(tmp_path)
    _write(wiki / "decisions" / "adr-0001.md", "---\ntype: decision\n---\n")

    assert wiki_dir(tmp_path, "decisions") is None


def test_a_purge_bundle_is_not_the_project_wiki(tmp_path: Path) -> None:
    _purge_bundle(tmp_path)

    assert wiki_dir(tmp_path) is None


def test_a_bundle_the_kit_wrote_still_resolves(tmp_path: Path) -> None:
    """An unmigrated consumer keeps working: the fallback exists for it."""
    _write(tmp_path / "wiki" / "product" / "objectives.md")
    _write(tmp_path / "wiki" / "decisions" / "adr-0001.md")
    _write(tmp_path / "wiki" / "index.md", '---\nokf_version: "0.2"\n---\n')

    assert wiki_dir(tmp_path, "product") == tmp_path / "wiki" / "product"
    assert wiki_dir(tmp_path) == tmp_path / "wiki"


def test_the_installed_kit_directory_is_its_own_evidence(tmp_path: Path) -> None:
    """No plugin writes under `.claude/wiki` by default; the location is the marker."""
    _write(tmp_path / ".claude" / "wiki" / "components" / "x.md")

    assert wiki_dir(tmp_path, "components") == tmp_path / ".claude" / "wiki" / "components"


def test_the_write_root_still_wins_over_everything(tmp_path: Path) -> None:
    _cartography_bundle(tmp_path)
    _write(tmp_path / ".squad" / "wiki" / "product" / "objectives.md")

    assert wiki_dir(tmp_path, "product") == tmp_path / ".squad" / "wiki" / "product"


# ── the migration report ─────────────────────────────────────────────────────


def test_a_plugin_bundle_is_reported_as_foreign_not_unmigrated(tmp_path: Path) -> None:
    _cartography_bundle(tmp_path)

    states = {r.relative: r.state for r in check_project(tmp_path)}

    assert states["wiki"] == "FOREIGN"


def test_a_foreign_bundle_alone_does_not_fail_the_migration_gate(tmp_path: Path) -> None:
    """There is nothing of the kit's to move, so the gate has nothing to demand."""
    _cartography_bundle(tmp_path)

    assert main(["--root", str(tmp_path)]) == 0


def test_kit_leaves_sharing_a_plugin_bundle_are_reported_loudly(tmp_path: Path) -> None:
    """A consumer whose kit-written `wiki/product` later had a plugin bundle written
    around it. Readers can no longer tell whose `wiki/` it is and stop falling back to
    it, so the kit's leaves there became unreachable — the gate must say so and name
    them, or the project loses its bundle in silence."""
    wiki = _cartography_bundle(tmp_path)
    _write(wiki / "product" / "objectives.md")

    report = {r.relative: r for r in check_project(tmp_path)}

    assert report["wiki"].state == "SHARED"
    assert "product" in report["wiki"].detail
    assert main(["--root", str(tmp_path)]) == 1

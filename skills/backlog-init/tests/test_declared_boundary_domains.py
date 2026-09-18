"""Domains derive from the boundary the project already declared, not from a guess.

A module manifest — `go.mod`, `Cargo.toml`, a workspace `package.json` — is a
compilation and versioning boundary somebody committed to. Reading it beats both
alternatives: one domain per repository is too coarse to carry "a root `go build ./...`
does not cover this repo", and one domain per package is the shape `agents/README.md`
argues against with a measured case.

Measured on `engine` (2026-09-10) before this rule existed: 8 modules with their own
`go.mod`, and 13 of the 17 live items touching a module (76%) touch exactly one.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from detect_domains import (  # noqa: E402 — post-bootstrap import
    _group_by_declared_boundary,
    detect_domains,
)


def _repo(root: Path, *modules: str, manifest: str = "go.mod") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    uses = "\n".join(f"\t./{m}" for m in modules)
    (root / "go.work").write_text(f"go 1.22\n\nuse (\n{uses}\n)\n", encoding="utf-8")
    for m in modules:
        (root / m).mkdir(parents=True, exist_ok=True)
        (root / m / manifest).write_text(f"module example.com/{m}\n", encoding="utf-8")
    return root


# ------------------------------------------------------------------ the grouping rule


def test_top_level_modules_become_separate_domains() -> None:
    grouped = _group_by_declared_boundary(["api", "pkg", "operators"])

    assert grouped == [("api", ["api"]), ("operators", ["operators"]), ("pkg", ["pkg"])]


def test_a_module_nested_under_another_joins_its_ancestor() -> None:
    """`operators/api` is part of `operators`, not a peer of it. Splitting them puts
    one Go module's sub-module in a different domain from the code that compiles it."""
    grouped = dict(_group_by_declared_boundary(["operators", "operators/api", "api"]))

    assert grouped["operators"] == ["operators", "operators/api"]
    assert "operators/api" not in grouped


def test_modules_under_a_shared_parent_become_one_domain() -> None:
    """The rule that stops this regressing to one-domain-per-package.

    `agents/README.md` records the cost: an SDK with six thin packages sharing a stack
    produced six specialists repeating the same facts, rotting once per copy.
    """
    grouped = _group_by_declared_boundary(
        [f"packages/{name}" for name in ("core", "cli", "http", "types", "utils", "sdk")])

    assert len(grouped) == 1
    assert grouped[0][0] == "packages"
    assert len(grouped[0][1]) == 6


def test_a_single_binary_under_cmd_takes_the_parent_segment() -> None:
    grouped = _group_by_declared_boundary(["cmd/service-ops", "tools/gen-keys"])

    assert dict(grouped) == {"cmd": ["cmd/service-ops"], "tools": ["tools/gen-keys"]}


def test_no_modules_means_no_boundaries() -> None:
    assert _group_by_declared_boundary([]) == []


# ------------------------------------------------------------------ the whole derivation


def test_the_root_domain_is_always_present_when_boundaries_exist(tmp_path: Path) -> None:
    """NOT optional. `route()` matches a repo EXACTLY, never by path prefix, so with
    only module domains an item about `charts/` or `docs/` has no domain at all — and
    neither does any existing item whose `repo:` is the repository's own name.

    Measured on an adopter: 224 items declaring `repo: theo` would have gone unroutable
    the moment the table stopped naming `engine`.
    """
    root = _repo(tmp_path / "engine", "api", "pkg")

    domains = detect_domains(root)

    assert domains[0].name == "engine"
    assert domains[0].repos == ["engine"]
    assert {d.name for d in domains} == {"engine", "api", "pkg"}


def test_a_repo_with_no_modules_keeps_the_single_domain_shape(tmp_path: Path) -> None:
    """The rule only fires where a boundary was declared. Everywhere else the old
    derivation stands, so a consumer with no workspace sees no change."""
    root = tmp_path / "plain"
    root.mkdir()
    (root / "README.md").write_text("# plain\n", encoding="utf-8")

    domains = detect_domains(root)

    assert [d.name for d in domains] == ["plain"]


def test_every_domain_names_a_specialist_path(tmp_path: Path) -> None:
    root = _repo(tmp_path / "engine", "api", "operators", "operators/api")

    for domain in detect_domains(root):
        assert domain.agent == f"agents/{domain.name}.md"


def test_no_repo_is_claimed_by_two_domains(tmp_path: Path) -> None:
    """`route()` iterates a dict, so a repo in two rows makes the answer depend on
    insertion order — the same item reaching a different specialist on a different
    run, with nothing having changed. `parse_routing_table` refuses it outright."""
    root = _repo(tmp_path / "engine", "api", "pkg", "operators", "operators/api",
                 "cmd/service-ops", "infra/scripts", "infra/tests")

    seen: dict[str, str] = {}
    for domain in detect_domains(root):
        for repo in domain.repos:
            assert repo not in seen, f"{repo} claimed by {seen.get(repo)} and {domain.name}"
            seen[repo] = domain.name


def test_the_theo_shape_derives_the_expected_seven(tmp_path: Path) -> None:
    """A real measured topology, pinned so a refactor cannot quietly change it."""
    root = _repo(tmp_path / "engine", "api", "pkg", "operators", "operators/api",
                 "cmd/service-ops", "infra/scripts", "infra/tests",
                 "tools/gen-service-auth-ed25519")

    domains = {d.name: d.repos for d in detect_domains(root)}

    assert domains == {
        "engine": ["engine"],
        "api": ["api"],
        "pkg": ["pkg"],
        "operators": ["operators", "operators/api"],
        "cmd": ["cmd/service-ops"],
        "infra": ["infra/scripts", "infra/tests"],
        "tools": ["tools/gen-service-auth-ed25519"],
    }

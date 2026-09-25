"""A package the workspace declares is not a fabricated npm import.

THE DEFECT, MEASURED
--------------------
Measured 2026-09-19 on a consumer whose `pnpm-workspace.yaml` declares
`apps/*/packages/*`: `run_code_quality.py <slug> --network` returned **98 HARD
findings**, every one of them `Fabricated npm package 'X' (not found on registry)`
for two packages that exist in the tree and are depended on as `workspace:*`.

    apps/<app>/packages/<pkg>/package.json      name: "@<scope>/<pkg>"
    apps/<app>/packages/<other>/package.json:8  "@<scope>/<pkg>": "workspace:*"

The consumer is deliberately not named. This kit describes whatever product adopts it,
and a named repository map is one every other consumer inherits without having it —
`tests/test_no_origin_ecosystem_leak.py` enforces that over the tracked surface. The
measurement is unchanged; only the identity is dropped.

`_find_workspace_package_names` collects names with two fixed globs — `*/package.json`
and `*/*/package.json` — so it sees depth 1 and depth 2 and nothing below. The packages
above sit at depth 4. Every import of them fell through to the npm registry, took a 404,
and was reported as fabricated.

WHY THE FIXED GLOBS ARE THE DEFECT AND NOT THE DEPTH
----------------------------------------------------
The method's own docstring says it walks "one level down over the **declared workspace
globs**". It reads no globs. It guesses two depths and hopes the repository agrees.

A note in the method claims the identical failure at the previous depth in August 2026.
Treat that as self-report: `git log -S 'root.glob("*/*/package.json")'` over this file
returns exactly one commit — the squashed inherited base — so no glob level was added
anywhere in this history, and the note describes work this repository cannot check. This
docstring asserted "fixed by adding a glob level" as observed until 2026-09-19.

The argument does not need it. The same file already states, about three OTHER
false-positive families it carries, that their shared root is resolving names against the
registry "without consulting what the project itself declares (workspaces, exports,
paths)", and that the fix "reads the declaration instead of guessing". Workspaces are named
in that sentence and are the family that still guesses.

The declaration is on disk and is the authority: `pnpm-workspace.yaml` lists exactly
which directories hold packages. Reading it replaces the guess with the fact, and the
docstring stops describing a mechanism that does not exist.

WHAT MUST NOT REGRESS
---------------------
A package NOBODY declares must still be reported. A fix that widens the net until every
import is "local" removes the detector rather than repairing it — which is why the second
test here is not optional.
"""

from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/code-quality"))

from scripts.detectors.typescript import TypescriptDetector  # noqa: E402


def _workspace(tmp_path: Path, globs: list[str], packages: dict[str, str]) -> Path:
    """A repo root declaring `globs`, holding `packages` as path -> package name."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "pnpm-workspace.yaml").write_text(
        "packages:\n" + "".join(f"  - '{g}'\n" for g in globs), encoding="utf-8"
    )
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "the-private-root", "private": True}), encoding="utf-8"
    )
    for rel, name in packages.items():
        d = tmp_path / rel
        d.mkdir(parents=True)
        (d / "package.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return tmp_path


@pytest.fixture
def detector() -> TypescriptDetector:
    return TypescriptDetector()


def test_a_package_declared_by_a_nested_workspace_glob_is_found(
    tmp_path: Path, detector: TypescriptDetector
) -> None:
    """The regression. Depth 4, declared by `apps/*/packages/*`, invisible to fixed globs."""
    root = _workspace(
        tmp_path,
        globs=["packages/*", "apps/*", "apps/*/packages/*"],
        packages={"apps/app-one/packages/agent": "@scope/agent"},
    )
    changed = root / "apps/app-one/packages/cli/src/main.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { x } from '@scope/agent'\n", encoding="utf-8")

    names = detector._find_workspace_package_names([changed])

    assert "@scope/agent" in names, (
        "a package the workspace file declares at `apps/*/packages/*` was not collected, so "
        "every import of it falls through to the npm registry and is reported as a fabricated "
        f"package. Collected: {sorted(names)}"
    )


def test_a_package_at_the_shallow_depths_is_still_found(
    tmp_path: Path, detector: TypescriptDetector
) -> None:
    """What the fixed globs already did right must survive reading the declaration."""
    root = _workspace(
        tmp_path,
        globs=["packages/*"],
        packages={"packages/core": "@scope/core"},
    )
    changed = root / "packages/other/src/index.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { y } from '@scope/core'\n", encoding="utf-8")

    names = detector._find_workspace_package_names([changed])

    assert "@scope/core" in names, f"collected: {sorted(names)}"


def test_a_package_nobody_declares_is_not_collected(
    tmp_path: Path, detector: TypescriptDetector
) -> None:
    """The half that keeps the detector a detector.

    A fix that collects every `package.json` anywhere would make this pass too — and would
    silently retire D2, because nothing would ever be fabricated again.
    """
    root = _workspace(
        tmp_path,
        globs=["packages/*"],
        packages={"packages/core": "@scope/core"},
    )
    stray = root / "scratch/not-a-member"
    stray.mkdir(parents=True)
    (stray / "package.json").write_text(
        json.dumps({"name": "@nobody/declared-me"}), encoding="utf-8"
    )
    changed = root / "packages/other/src/index.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { z } from '@nobody/declared-me'\n", encoding="utf-8")

    names = detector._find_workspace_package_names([changed])

    assert "@nobody/declared-me" not in names, (
        "a package in a directory the workspace file does not declare was collected as a "
        "workspace member. D2 would then never report a fabricated import from such a "
        f"directory. Collected: {sorted(names)}"
    )


# ---------------------------------------------------------------------------
# The dialect. Required by the plan's AC-003, and by the PLAN panel unanimously:
# without these, the whole item is executable end to end — every criterion green —
# by a matcher that has never met a negation or a `**`, which then raises
# `ValueError` on the first consumer that declares one and halts the cycle under
# `rules/cycle-code-quality.md § Stop conditions`.
#
# The four patterns below are pnpm's own documented example, verbatim. Do not
# paraphrase them: the grep half of AC-003 checks this file for the literals, and
# a paraphrase passes the grep while testing something else.
# ---------------------------------------------------------------------------

#: pnpm's documented example, verbatim — `my-app`, `packages/*`, `components/**`, `!**/test/**`.
PNPM_DOCUMENTED_PATTERNS = ["my-app", "packages/*", "components/**", "!**/test/**"]


def test_a_literal_member_path_is_found(tmp_path: Path, detector: TypescriptDetector) -> None:
    """`my-app` — a member named outright, with no glob at all."""
    root = _workspace(tmp_path, PNPM_DOCUMENTED_PATTERNS, {"my-app": "@scope/my-app"})
    changed = root / "packages/other/src/index.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { a } from '@scope/my-app'\n", encoding="utf-8")

    assert "@scope/my-app" in detector._find_workspace_package_names([changed]), (
        "a literal member path is the simplest pattern pnpm documents and must resolve"
    )


def test_a_recursive_glob_reaches_depth_and_stops_at_node_modules(
    tmp_path: Path, detector: TypescriptDetector
) -> None:
    """`components/**` — reaches any depth, and must NOT collect installed dependencies.

    `Path.glob("components/**/package.json")` descends `node_modules`, so every installed
    package would be registered as a workspace member and D2 would stop reporting anything
    as fabricated. Measured 2026-09-19; it is why the fix prunes during the walk.
    """
    root = _workspace(
        tmp_path,
        PNPM_DOCUMENTED_PATTERNS,
        {"components/deep/widget": "@scope/widget",
         "components/deep/node_modules/vendor": "vendor-from-the-registry"},
    )
    changed = root / "packages/other/src/index.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { b } from '@scope/widget'\n", encoding="utf-8")

    names = detector._find_workspace_package_names([changed])

    assert "@scope/widget" in names, f"`components/**` did not reach depth: {sorted(names)}"
    assert "vendor-from-the-registry" not in names, (
        "a package inside `node_modules` was collected as a workspace member. Every installed "
        f"dependency would then be un-fabricatable and D2 would report nothing: {sorted(names)}"
    )


def test_negation_excludes_what_it_names(tmp_path: Path, detector: TypescriptDetector) -> None:
    """`!**/test/**` — the pattern that decides whether the dialect is executed at all.

    Three ways to fail this, all measured on Python 3.10.12 and all silent or fatal:
      * `Path.glob` raises `ValueError: Invalid pattern: '**' can only be an entire path
        component` — the detector CRASHES, which halts the cycle;
      * a negation that does not crash is a silent no-op, so the excluded package is
        collected anyway;
      * `fnmatch`'s `*` crosses `/`, so the positive alone over-collects.

    The package under `test/` is declared by `packages/*`'s sibling reach AND removed by the
    negation. Order-independence is the rule: `@manypkg/tools` passes the whole array to one
    matcher call, measured over tinyglobby 0.2.17 in the plan's ADR-1.
    """
    root = _workspace(
        tmp_path,
        PNPM_DOCUMENTED_PATTERNS,
        {"components/keep/thing": "@scope/keep",
         "components/test/fixture": "@scope/excluded-by-the-negation"},
    )
    changed = root / "packages/other/src/index.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { c } from '@scope/keep'\n", encoding="utf-8")

    names = detector._find_workspace_package_names([changed])

    assert "@scope/keep" in names, f"the positive pattern did not collect: {sorted(names)}"
    assert "@scope/excluded-by-the-negation" not in names, (
        "`!**/test/**` did not exclude what it names, so the negation is a no-op and this "
        f"matcher has never executed the dialect it is fed: {sorted(names)}"
    )


def test_a_single_star_does_not_cross_a_separator(
    tmp_path: Path, detector: TypescriptDetector
) -> None:
    """`packages/*` names the children of `packages`, not everything beneath it.

    Added after a canary found nothing. Replacing the matcher's `[^/]*` with `.*` — which is
    verbatim what `fnmatch.translate` produces, and the reason `fnmatch` was rejected — left
    ALL SIX cases green, because the only over-collection the others could see is
    `node_modules`, and the walk prunes that before the filter ever runs.

    So the prune was covering for the matcher, and a defect measured in the plan's own ADR-1
    had no test. This is that test: a nested directory the pattern does not name.
    """
    root = _workspace(
        tmp_path,
        ["packages/*"],
        {"packages/real": "@scope/real",
         "packages/real/nested/deeper": "@scope/not-a-member"},
    )
    changed = root / "packages/other/src/index.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { d } from '@scope/real'\n", encoding="utf-8")

    names = detector._find_workspace_package_names([changed])

    assert "@scope/real" in names, f"the pattern's own child was missed: {sorted(names)}"
    assert "@scope/not-a-member" not in names, (
        "`packages/*` collected a package two levels down, so `*` crossed a separator. Every "
        f"nested directory becomes a declared member: {sorted(names)}"
    )


# ---------------------------------------------------------------------------
# T1.3 — the root marker, and the guarded parser.
# ---------------------------------------------------------------------------


def test_a_settings_only_workspace_file_does_not_stop_the_walk(
    tmp_path: Path, detector: TypescriptDetector
) -> None:
    """pnpm 10 moved non-workspace settings into `pnpm-workspace.yaml`.

    So the filename no longer implies a declaration, and a file holding only `allowBuilds:`
    must not end the upward walk. Reading the declaration is what makes the old marker unsound:
    before this change a wrong root still globbed generically; after it, a wrong root reads a
    file that declares nothing and collects NOTHING.

    Such a file exists in a real consumer, under a scaffolding package's default template, and
    this fixture is WRITTEN rather than pointed at — that path is in the consumer and this test
    runs in the kit. The consumer is not named for the reason
    `tests/test_no_origin_ecosystem_leak.py` enforces: the kit describes whatever product
    adopts it, and a named repository is a map every other consumer inherits without having.
    """
    root = _workspace(tmp_path, ["packages/*"], {"packages/core": "@scope/core"})
    inner = root / "packages/scaffold/templates/default"
    inner.mkdir(parents=True)
    (inner / "pnpm-workspace.yaml").write_text(
        "# settings only — pnpm 10 keeps build approvals here\nallowBuilds:\n  - esbuild\n",
        encoding="utf-8",
    )
    changed = inner / "src/page.tsx"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { e } from '@scope/core'\n", encoding="utf-8")

    names = detector._find_workspace_package_names([changed])

    assert "@scope/core" in names, (
        "the walk stopped at a `pnpm-workspace.yaml` that declares no members, so the real "
        f"root was never reached and nothing was collected: {sorted(names)}"
    )


def test_workspaces_declared_in_package_json_are_read_in_both_shapes(
    tmp_path: Path, detector: TypescriptDetector
) -> None:
    """npm takes an array; yarn classic and bun also take `{packages: [...]}`.

    `data.get("workspaces")` handled as a list yields NOTHING, silently, on the object form —
    so a yarn or bun monorepo would keep every one of its findings.
    """
    members = ["apps/*/packages/*"]
    for shape, value in (("array", members), ("object", {"packages": members})):
        root = tmp_path / shape
        # Depth 3 ON PURPOSE. A canary caught this test passing for the wrong reason: with the
        # package at depth 2, dropping the object-shape read entirely still left it GREEN,
        # because the no-declaration fallback globs depth 1 and 2 and rescued it. The fixture
        # has to sit where only the declaration can reach.
        (root / "apps/one/packages/lib").mkdir(parents=True)
        (root / ".git").mkdir()
        (root / "package.json").write_text(
            json.dumps({"name": "root", "private": True, "workspaces": value}), encoding="utf-8"
        )
        (root / "apps/one/packages/lib/package.json").write_text(
            json.dumps({"name": "@scope/lib"}), encoding="utf-8"
        )
        changed = root / "apps/one/packages/app/src/index.ts"
        changed.parent.mkdir(parents=True)
        changed.write_text("import { f } from '@scope/lib'\n", encoding="utf-8")

        names = TypescriptDetector()._find_workspace_package_names([changed])

        assert "@scope/lib" in names, (
            f"`workspaces` declared as an {shape} was not read: {sorted(names)}"
        )


def test_an_unreadable_declaration_is_not_an_empty_workspace(
    tmp_path: Path, detector: TypescriptDetector
) -> None:
    """Without PyYAML the collector keeps the OLD behaviour; it does not report no members.

    PyYAML is under `[project.optional-dependencies]`, so an install without the extra has no
    parser. Falling silently to "this workspace declares nothing" would read exactly like a
    repository with no workspace — the silent pass this whole change exists to remove. The
    fallback is the pre-2026-09 fixed globs, which is a weaker answer rather than a wrong one.
    """

    root = _workspace(tmp_path, ["apps/*/packages/*"], {"packages/near": "@scope/near"})
    changed = root / "packages/app/src/index.ts"
    changed.parent.mkdir(parents=True)
    changed.write_text("import { g } from '@scope/near'\n", encoding="utf-8")

    real_import = builtins.__import__

    def _no_yaml(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("PyYAML is not installed")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = _no_yaml
    try:
        names = TypescriptDetector()._find_workspace_package_names([changed])
    finally:
        builtins.__import__ = real_import

    assert "@scope/near" in names, (
        "with no YAML parser the collector reported an empty workspace instead of falling back "
        f"to the behaviour that predates this change: {sorted(names)}"
    )

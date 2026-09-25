#!/usr/bin/env python3
"""Report the version a release should be computed FROM.

B-043 — `skills/release/SKILL.md` derived this with `git describe --tags --abbrev=0`, which walks
the ANCESTRY of HEAD. In this branching model (`rules/git-safety.md` § 1:
`workspace → develop → main`) a release tag is created on the merge commit that lands on `main`, so
it is never an ancestor of `workspace`. Measured on this repository:

    git describe --tags --abbrev=0             ->  v0.52.1
    git tag --sort=-v:refname | head -1        ->  v0.64.0
    npm view @acme/tui version              ->  0.64.0

Twelve versions stale, structurally rather than by a forgotten fetch. A release cut from `workspace`
would have computed 0.53.0 — BELOW what was published — and the cycle's "tag already exists" stop
condition could not fire, because v0.53.0 was never tagged. Nothing between the derivation and
`gh release create` would have caught it.

**The base is the maximum of the highest tag and supported manifest versions** (`package.json`,
`pyproject.toml`, `Cargo.toml`), because each alone has a measured failure mode. Go modules are
tag-only because `go.mod` contains no release version. Cross-major disagreement is refused rather
than maximized because a stray high tag is not safely recoverable.

Querying npm was rejected: version derivation must not depend on the network, or on a registry a
fork or private mirror may not have.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "semver.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Below the bootstrap: `squad` is importable only after sys.path is extended.
from squad.semver import (  # noqa: E402 — post-bootstrap import
    Version,
    highest,
    parse as _parse,
)

#: How a version this kit cannot order is described to a reader. NOT "not semver":
#: `0.3.0-beta.1` is valid semver, and saying otherwise sent people looking for a typo
#: in a tag that was spelled correctly.
_UNORDERABLE = "not a version this kit cuts (X.Y.Z or X.Y.Z-rc.N)"


def _toplevel(start: Path) -> Path:
    """Where `git tag` is actually answering from.

    F-3 — `git tag` walks UP to the repository toplevel; `package.json` does not. Called from a
    subdirectory, the two sources described different places: `_tags(Path("src"))` returned 62 tags
    while `_manifest(Path("src"))` returned None, silently killing the B-050 case (a published
    version with no tag) that `max()` exists for.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start, capture_output=True, text=True, check=False,
    )
    return Path(result.stdout.strip()) if result.returncode == 0 else start


def _tags(repo_root: Path) -> tuple[list[Version], int]:
    """Every parseable tag, plus a COUNT of the ones skipped.

    Pre-releases are NOT skipped — `-rc.N` is a version this chain cuts by default, and
    reading it is the whole point of `squad.semver`. What is skipped is a pre-release
    identifier the kit cannot order (`-beta.1`, `-alpha`), counted rather than dropped so
    a repository made entirely of them cannot look like a fresh project.
    """
    result = subprocess.run(
        ["git", "tag"], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return [], 0
    parsed: list[Version] = []
    skipped = 0
    for line in result.stdout.split():
        version = _parse(line)
        if version is None:
            skipped += 1
        else:
            parsed.append(version)
    return parsed, skipped


def _manifest_versions(repo_root: Path) -> list[tuple[str, Version]]:
    """Read version-bearing manifests for TypeScript, Python, and Rust.

    Go modules have no manifest version and therefore use semver tags as their source of truth.
    """
    versions: list[tuple[str, Version]] = []
    package_json = repo_root / "package.json"
    if package_json.exists():
        try:
            declared = json.loads(package_json.read_text(encoding="utf-8")).get("version")
        except (json.JSONDecodeError, OSError) as error:
            raise SystemExit(f"detect_current_version: cannot read {package_json}: {error}") from error
        parsed = _parse(str(declared)) if declared else None
        if parsed:
            versions.append(("package.json", parsed))

    for relative, section in (("pyproject.toml", "project"), ("Cargo.toml", "package")):
        path = repo_root / relative
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise SystemExit(f"detect_current_version: cannot read {path}: {error}") from error
        block = re.search(
            rf"^\[{section}\]\s*$\n(.*?)(?=^\[|\Z)", text, re.MULTILINE | re.DOTALL
        )
        match = (
            re.search(r'^version\s*=\s*["\']([^"\']+)["\']', block.group(1), re.MULTILINE)
            if block
            else None
        )
        parsed = _parse(match.group(1)) if match else None
        if parsed:
            versions.append((relative, parsed))
    return versions


def detect_current_version(repo_root: Path) -> str:
    root = _toplevel(repo_root)
    tags, skipped = _tags(root)
    manifests = _manifest_versions(root)

    candidates = list(tags)
    candidates.extend(version for _, version in manifests)

    if not candidates:
        # F-2 — do NOT return 0.0.0 here. A repository whose tags are all pre-release, with no
        # manifest, would look like a fresh project and derive a base BELOW everything published —
        # which is the defect B-043 exists to close, reintroduced by its own fallback. The count was
        # already computed and then dropped on the floor.
        raise SystemExit(
            "detect_current_version: no semver tag and no manifest version"
            + (f" ({skipped} tag(s) skipped: {_UNORDERABLE})" if skipped else "")
            + " — pass --current explicitly rather than releasing from a guessed base"
        )

    best = highest(candidates)
    assert best is not None  # `candidates` was checked non-empty above

    # F-1 — "a base that is too high is safe" was MY claim, and review disproved it. There is no
    # upper bound on `git tag`: it lists whatever any `git fetch --tags` ever brought in. Measured —
    # [v0.64.0, v1.0.0] derived 1.0.0; [v0.64.0, v9.9.9] derived 9.9.9; a manifest typo of 1.64.0
    # derived 1.64.0.
    #
    # The cost is not symmetric with a base that is too low, and it is not recoverable: npm versions
    # are IMMUTABLE, so a burned range is burned permanently; a major bump leaves every consumer's
    # `^0.64.0` behind, so they silently stop receiving updates; and shipping 1.x is a v1.0 claim
    # that `rules/honesty-gate-golden-rule.md` gates and this chain never checks.
    #
    # Within one major, disagreement is NORMAL and `max()` is right: the manifest lags the tag
    # between the release commit and the merge, and the tag lags the manifest for the 13 published
    # versions B-050 found with no tag at all. ACROSS majors it is not normal, so it refuses and
    # names both rather than guessing which is real.
    if manifests and tags:
        highest_tag = highest(tags)
        disagreeing = [(name, v) for name, v in manifests if highest_tag.major != v.major]
        if disagreeing:
            raise SystemExit(
                "detect_current_version: highest tag "
                f"{highest_tag} and manifest version "
                + ", ".join(f"{name}={version}" for name, version in disagreeing)
                + " disagree on the MAJOR component. "
                "One of them is wrong — a stray tag or an edited manifest — and releasing from "
                "either would be irreversible. Pass --current explicitly."
            )

    return str(best)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    # The release step assigns this command's stdout to CURRENT_VERSION and feeds it
    # straight to `bump_version.py --from`. Under `--quiet` the note about skipped tags
    # is suppressed rather than merely redirected: a caller capturing both streams gets
    # the version and nothing else, which is the whole reason the flag is documented.
    parser.add_argument("--quiet", action="store_true",
                        help="print the version alone; suppress the non-semver-tag note")
    args = parser.parse_args()
    _, skipped = _tags(args.repo_root)
    if skipped and not args.quiet:
        print(f"note: {skipped} tag(s) skipped: {_UNORDERABLE}", file=sys.stderr)
    print(detect_current_version(args.repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

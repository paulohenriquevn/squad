#!/usr/bin/env python3
"""Report the version a release should be computed FROM.

B-043 — `skills/release/SKILL.md` derived this with `git describe --tags --abbrev=0`, which walks
the ANCESTRY of HEAD. In this branching model (`rules/git-safety.md` § 1:
`workspace → develop → main`) a release tag is created on the merge commit that lands on `main`, so
it is never an ancestor of `workspace`. Measured on this repository:

    git describe --tags --abbrev=0             ->  v0.52.1
    git tag --sort=-v:refname | head -1        ->  v0.64.0
    npm view @theokit/tui version              ->  0.64.0

Twelve versions stale, structurally rather than by a forgotten fetch. A release cut from `workspace`
would have computed 0.53.0 — BELOW what was published — and the cycle's "tag already exists" stop
condition could not fire, because v0.53.0 was never tagged. Nothing between the derivation and
`gh release create` would have caught it.

**The base is the maximum of the highest tag and the manifest version**, because each alone has a
measured failure mode: B-050 found 13 of 43 published versions with no tag at all (including the one
npm served as `latest` for three days), and the manifest is bumped BY the release commit, so it lags
a tag that already exists. Whichever is ahead reflects reality. A base that is too high is safe — it
produces a version nobody has used; a base that is too low is this item.

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

_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _parse(version: str) -> tuple[int, int, int] | None:
    """A tuple of INTS, never the string.

    As strings `"0.9.0" > "0.10.0"` is true, which is how a naive fix ships a release below the last
    one for the first time the minor reaches double digits.
    """
    match = _SEMVER.match(version.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


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


def _tags(repo_root: Path) -> tuple[list[tuple[int, int, int]], int]:
    """Every parseable tag, plus a COUNT of the ones skipped.

    Skipped tags are counted rather than silently dropped: a repository whose tags are all
    pre-release would otherwise report "no tags" and look like a fresh project.
    """
    result = subprocess.run(
        ["git", "tag"], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return [], 0
    parsed: list[tuple[int, int, int]] = []
    skipped = 0
    for line in result.stdout.split():
        version = _parse(line)
        if version is None:
            skipped += 1
        else:
            parsed.append(version)
    return parsed, skipped


def _manifest(repo_root: Path) -> tuple[int, int, int] | None:
    path = repo_root / "package.json"
    if not path.exists():
        return None
    try:
        declared = json.loads(path.read_text(encoding="utf-8")).get("version")
    except (json.JSONDecodeError, OSError) as error:
        # FAIL LOUD. A release must not proceed on a guess about its own version, and a manifest
        # that cannot be read is a condition somebody has to look at (`rules/error-handling.md` § 2).
        raise SystemExit(f"detect_current_version: cannot read {path}: {error}") from error
    return _parse(str(declared)) if declared else None


def detect_current_version(repo_root: Path) -> str:
    root = _toplevel(repo_root)
    tags, skipped = _tags(root)
    manifest = _manifest(root)

    candidates = list(tags)
    if manifest is not None:
        candidates.append(manifest)

    if not candidates:
        # F-2 — do NOT return 0.0.0 here. A repository whose tags are all pre-release, with no
        # manifest, would look like a fresh project and derive a base BELOW everything published —
        # which is the defect B-043 exists to close, reintroduced by its own fallback. The count was
        # already computed and then dropped on the floor.
        raise SystemExit(
            "detect_current_version: no semver tag and no manifest version"
            + (f" ({skipped} tag(s) skipped as non-semver)" if skipped else "")
            + " — pass --current explicitly rather than releasing from a guessed base"
        )

    best = max(candidates)

    # F-1 — "a base that is too high is safe" was MY claim, and review disproved it. There is no
    # upper bound on `git tag`: it lists whatever any `git fetch --tags` ever brought in. Measured —
    # [v0.64.0, v1.0.0] derived 1.0.0; [v0.64.0, v9.9.9] derived 9.9.9; a manifest typo of 1.64.0
    # derived 1.64.0.
    #
    # The cost is not symmetric with a base that is too low, and it is not recoverable: npm versions
    # are IMMUTABLE, so a burned range is burned permanently; a major bump leaves every consumer's
    # `^0.64.0` behind, so they silently stop receiving updates; and shipping 1.x is a v1.0 claim
    # that `rules/dogfood-golden-rule.md` gates and this chain never checks.
    #
    # Within one major, disagreement is NORMAL and `max()` is right: the manifest lags the tag
    # between the release commit and the merge, and the tag lags the manifest for the 13 published
    # versions B-050 found with no tag at all. ACROSS majors it is not normal, so it refuses and
    # names both rather than guessing which is real.
    if manifest is not None and tags:
        highest_tag = max(tags)
        if highest_tag[0] != manifest[0]:
            raise SystemExit(
                "detect_current_version: highest tag "
                f"{highest_tag[0]}.{highest_tag[1]}.{highest_tag[2]} and manifest version "
                f"{manifest[0]}.{manifest[1]}.{manifest[2]} disagree on the MAJOR component. "
                "One of them is wrong — a stray tag or an edited manifest — and releasing from "
                "either would be irreversible. Pass --current explicitly."
            )

    return f"{best[0]}.{best[1]}.{best[2]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    _, skipped = _tags(args.repo_root)
    if skipped:
        print(f"note: {skipped} tag(s) not semver, skipped", file=sys.stderr)
    print(detect_current_version(args.repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

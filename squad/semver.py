"""One reading of a version string, for every script that cuts or reads a release.

WHY THIS MODULE EXISTS. The release slice parsed semver in three places with three
different regexes, and they disagreed about the only shape this kit cuts by default:

    detect_current_version  ^v?(\\d+)\\.(\\d+)\\.(\\d+)$              — no pre-release at all
    compute_next_version    ^v?(\\d+)\\.(\\d+)\\.(\\d+)(?:-rc\\.(\\d+))?  — only `-rc.N`
    promote_unreleased      \\d+\\.\\d+\\.\\d+(?:-[0-9A-Za-z.-]+)?      — any pre-release

`cycle-release.md` makes `--pre` the default because "most cuts are pre-releases", so
the disagreement landed on the common path: `detect` called every `-rc.N` tag "not
semver" and skipped it, the chain recomputed `-rc.1` over a tag that already existed,
and the rc series never reached `rc.3`. A repository whose only tags were rc was
refused outright with "no semver tag" — the release cycle unable to read the releases
it had itself cut.

The fix is not a fourth regex. It is one reading, here, that everything shares.

WHAT IS AND IS NOT A VERSION HERE. `parse` accepts the semver shapes this kit can
order: `X.Y.Z`, optionally `-rc.N`, optionally `+build`. It deliberately does NOT
accept `-beta.1` or `-alpha`, because ordering arbitrary pre-release identifiers is a
problem this kit does not have — `compute_next_version` cuts `rc` and nothing else.
A version it cannot order is refused rather than ranked wrongly, and `RC` is the one
identifier the kit writes.
"""
from __future__ import annotations

import re
from typing import NamedTuple

#: The pre-release identifier this kit cuts. Kept here so the spelling has one home.
RC = "rc"

#: `X.Y.Z`, an optional `-rc.N`, an optional `+build` that carries no ordering weight.
SEMVER_RE = re.compile(rf"^v?(\d+)\.(\d+)\.(\d+)(?:-{RC}\.(\d+))?(?:\+[0-9A-Za-z.-]+)?$")


class Version(NamedTuple):
    """A version that can be COMPARED, which is the whole reason it is a tuple of ints.

    As strings `"0.9.0" > "0.10.0"` is true, which is how a naive comparison ships a
    release below the last one the first time a minor reaches double digits.

    `rc` is None for a final version, and that is what `sort_key` has to translate:
    semver orders a pre-release BELOW its own final (`0.3.0-rc.2 < 0.3.0`), so the key
    carries a SEPARATE final-flag rather than a sentinel rc number. A sentinel cannot
    work: any number chosen for "final" is either below some real rc or above it, and
    `None` does not compare against int at all.
    """

    major: int
    minor: int
    patch: int
    rc: int | None = None

    @property
    def core(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    @property
    def is_prerelease(self) -> bool:
        return self.rc is not None

    def sort_key(self) -> tuple[int, int, int, int, int]:
        """Orders finals above their own pre-releases, never below."""
        return (*self.core, 0 if self.rc is not None else 1, self.rc or 0)

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return base if self.rc is None else f"{base}-{RC}.{self.rc}"


def parse(version: str) -> Version | None:
    """The version, or None when this kit cannot order what it was given.

    None is not "invalid semver" — `0.3.0-beta.1` is perfectly valid semver and still
    returns None here. Callers that report a skipped tag must say what they mean:
    "not a version this kit cuts", never "not semver".
    """
    match = SEMVER_RE.match(version.strip())
    if not match:
        return None
    major, minor, patch, rc = match.groups()
    return Version(int(major), int(minor), int(patch), None if rc is None else int(rc))


def parse_release(line: str) -> list[tuple[str | None, Version]] | None:
    """A release line: one bare version, or `<package> <version>` components separated by commas.

    A monorepo cuts several packages at once, and Keep-a-Changelog has no opinion about
    it — the heading is free text between brackets. Measured 2026-09-22: the promotion
    mechanism took ONE semver, while the three sections below the one being written read
    `## [create-theokit 3.0.1, @theokit/http 2.2.0, theokit 0.68.0]` and two more like it.
    The mechanism could not perform the promotion its own cycle rule prescribes, for the
    shape that repository releases in most of the time.

    EVERY component is validated, and one bad component refuses the whole line. Partial
    acceptance would write a typo into a heading nobody edits again, and
    `render_release_notes.py` looks the section up by exact string — so the reader who
    cannot find it later is told their argument is wrong rather than that the record is.

    Parsing only. Whether a pre-release may be promoted is `promote_unreleased`'s rule and
    stays there: `render_release_notes.py` legitimately reads an rc heading, and a refusal
    here would stop it sharing this reader.

    Returns None when nothing usable is in the line — empty, a component with no version,
    a version this kit cannot order, or a leading `v` (refused here as everywhere).
    """
    components: list[tuple[str | None, Version]] = []
    for raw in line.split(","):
        part = raw.strip()
        if not part:
            return None
        name: str | None = None
        text = part
        if " " in part:
            name, _, text = part.rpartition(" ")
            name = name.strip() or None
        text = text.strip()
        if text.startswith("v"):
            return None
        version = parse(text)
        if version is None:
            return None
        components.append((name, version))
    return components or None


def highest(versions: list[Version]) -> Version | None:
    """The greatest version, ordering pre-releases below their own final."""
    return max(versions, key=Version.sort_key) if versions else None

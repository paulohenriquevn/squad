"""No ecosystem's own repository names travel with the kit.

THE DEFECT THIS FIXES
---------------------
`rules/cycle-backlog.md` carries the per-domain routing table, and the version
versioned here was once one specific ecosystem's: eight domains pointing at
repositories only that organisation had.

The file itself already described the consequence, with a measurement:

    "A consumer that keeps this table inherits a map of repos it does not have,
     and gate G1 then refuses every item it files. Measured on an adopter
     (2026-08-18): 88 items with measured file:line evidence, all
     BLOCKER/unroutable_repo."

WHY THIS TEST GREW
------------------
Its first version measured only what `install.sh` COPIES — `rules/*.txt` and the
routing section of `cycle-backlog.md`. That is where the refusal originates, so it
was the right place to start and the wrong place to stop: the origin ecosystem's
name also sat in `README.md`, in the plugin manifest's `description`, and in the
frontmatter `description` of two skills, which is the text Claude Code reads when
deciding whether to reach for a skill at all.

Those are not routing failures. They are identity: a kit that says it maintains
one named product, shipped to somebody maintaining a different one. So the sweep
now covers the whole versioned surface, and the install assertions stay as the
narrower, sharper case underneath it.

WHAT THE PATTERN DELIBERATELY DOES NOT MATCH
--------------------------------------------
`cap-theorem-specialist` is a skill in this kit and `theory of mind` appears in
`skills/skill-creator/SKILL.md`. A case-insensitive search for the origin token
flags both. The pattern below is anchored so that it cannot: the token must be
followed by `-` plus a lowercase letter, or by `kit`, or preceded by `use`, or
capitalised and followed by another capital (`TheoCode`).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Anchored so `theorem` and `theory` never match. See the module docstring.
#:
#: THIS LINE IS THE DEFINITION, and a sweep that rewrites the origin name across the
#: tree must exclude this file. Rewritten here on 2026-09-21 by exactly such a sweep,
#: the pattern became the replacement text and then matched 200+ files — the checker
#: turned into an accusation of everything, which reads the same as a checker that
#: found nothing real. A pattern that edits itself is not a narrower bug than a bad
#: pattern; it is the same bug with the evidence destroyed.
ORIGIN_RE = re.compile(r"theo-[a-z]|theokit|usetheo|Theo[A-Z]")

#: Generated, vendored or historical trees. The study zone is third-party and read-only
#: by contract (`hooks/boundary-check.py` blocks writes to it), and the caches hold
#: compiled copies of files this sweep already reads at source.
#:
#: These are path PARTS, matched by directory name, so `study-material` covers the zone
#: at `.squad/study-material/` and at the retired top-level path both.
SKIP_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".benchmarks",
    "study-material",
    "records",
}

#: Files that must NAME the token in order to FORBID it. A guard against a string
#: cannot avoid containing that string, and exempting them is what lets three
#: independent guards coexist instead of one deleting the others.
#:
#: The exemption is by exact path and each entry is a guard — never a file that
#: merely happens to mention the name. Widening this set is how the sweep stops
#: working, so a new entry needs the same justification these three carry.
GUARD_FILES = {
    "tests/test_no_origin_ecosystem_leak.py",
    "skills/plan-confidence/tests/test_audit_findings.py",
    "skills/plan-confidence/tests/test_portability.py",
}

#: The address of a real external dependency, which is not the same thing as this
#: kit claiming to maintain somebody's product.
#:
#: `cycle-judge-codex` is delivered by a plugin that lives outside this repository.
#: Its coordinates appear in an install instruction (`/plugin marketplace add …`) and
#: in the links a reader follows to check the contract this kit consumes. Replacing
#: the org with a placeholder does not make the kit more portable — it makes the
#: install instruction wrong, and a broken instruction is a worse outcome than a
#: generic one.
#:
#: The exemption is the exact repository slug and nothing else, so it cannot widen:
#: any OTHER use of the token still fails, in this file or any future one. That is
#: the difference between exempting an address and exempting a name.
#: BOTH slugs, because the repository was renamed (`…-plugin-cc` → `judge-codex`,
#: 2026-09) and the old one still resolves by GitHub redirect — which is precisely
#: how a stale install instruction survives unnoticed. The old name stays because
#: released CHANGELOG entries carry it and a released entry is never edited.
EXTERNAL_DEPENDENCIES = ("usetheodev/judge-codex-plugin-cc",
                         "usetheodev/judge-codex")


def _leaks(text: str) -> list[str]:
    """Matches, with the declared external-dependency addresses removed first.

    Removing them from the TEXT rather than filtering the matches is what keeps the
    exemption narrow: `usetheodev/other-thing` still leaks, because only the exact
    declared slug is elided before the pattern runs.

    The elision is right-anchored, and that is not a detail. A plain substring
    replace also elides the slug when it is a PREFIX of something longer, so
    `usetheodev/judge-codex-plugin-cc-fork` — a different repository — passed as
    though it were the declared one. Caught by
    `test_the_external_dependency_exemption_does_not_widen`, which is the whole
    reason that test exists: an exemption nobody probes is a door.
    """
    for dep in EXTERNAL_DEPENDENCIES:
        text = re.sub(rf"{re.escape(dep)}(?![A-Za-z0-9_.-])", "", text)
    return sorted(set(ORIGIN_RE.findall(text)))


def committable_files(repo: Path | None = None) -> list[Path]:
    """Everything a commit from this tree would carry: tracked, plus not-yet-added.

    It read `git ls-files` — tracked only — so a file not in the index yet was
    invisible. Somebody writing a new test in this kit got a pass at exactly the
    moment they made the mistake, and the finding arrived one commit later, on a
    branch two sessions share.

    Measured 2026-09-19: a peer wrote a new test carrying ten occurrences of a
    consumer's app and scope names, ran this gate, and it passed. The file was `??`.

    Scanning untracked files sounds expensive and is not, because
    `--exclude-standard` honours `.gitignore`. Measured here at the same moment:

        --others --exclude-standard      1 path — the one about to land
        --others                      2277 paths — scratch, caches, venvs

    So the repository's own ignore rules draw the line and this function carries no
    second list of what to skip. `--cached` was the other candidate: it sees the
    file one step later, at `git add`, which is still after the author has stopped
    looking at it.

    A tracked path deleted from disk is dropped — reading it would be reading
    nothing.
    """
    root = REPO if repo is None else repo
    paths: list[Path] = []
    for args in (["ls-files"], ["ls-files", "--others", "--exclude-standard"]):
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, check=False)
        assert out.returncode == 0, out.stderr
        for line in out.stdout.splitlines():
            if not line or SKIP_PARTS.intersection(Path(line).parts):
                continue
            path = root / line
            if path.is_file():
                paths.append(path)
    return paths


def test_no_versioned_file_names_the_origin_ecosystem():
    """The whole tracked surface, not only what the installer copies.

    This is the assertion that keeps the name from coming back. A single
    `SKILL.md` description reintroducing it is enough to tell every consumer
    that this kit maintains somebody else's product.
    """
    dirty: dict[str, list[str]] = {}
    for path in committable_files():
        rel = str(path.relative_to(REPO))
        if rel in GUARD_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found = _leaks(text)
        if found:
            dirty[rel] = found

    assert not dirty, (
        "versioned files name a specific ecosystem's repositories or org: "
        f"{dirty}. The kit describes ANY product that adopts it; a named one "
        "makes every consumer inherit a map of repos they do not have."
    )


def test_the_external_dependency_exemption_does_not_widen():
    """The declared slug passes; anything else wearing the same org does not.

    An exemption nobody probes is a door. This is the probe: the plugin's real
    address is allowed because a broken install instruction is worse than a generic
    one, and that argument covers exactly one string.
    """
    allowed = "install it with `/plugin marketplace add usetheodev/judge-codex-plugin-cc`"
    assert _leaks(allowed) == []

    for smuggled in (
        "usetheodev/judge-codex-plugin-cc-fork",  # a suffix on the real slug
        "usetheodev/some-other-repo",             # same org, different repo
        "https://usetheo.dev",                    # the org's domain
        "theo-cloud and theo-rag",                # plain repository names
    ):
        assert _leaks(smuggled), f"{smuggled!r} slipped through the exemption"


def test_no_versioned_path_names_the_origin_ecosystem():
    """A fixture DIRECTORY carries the name just as loudly as a line of prose."""
    dirty = [
        str(p.relative_to(REPO)) for p in committable_files() if ORIGIN_RE.search(str(p))
    ]
    assert not dirty, f"paths naming the origin ecosystem: {dirty}"


@pytest.fixture(scope="module")
def installed_rules(versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("consumer")
    proc = subprocess.run(
        ["bash", str(versioned_kit / "mechanisms" / "distribution" / "install.sh"), str(target)],
        capture_output=True,
        text=True,
     check=False)
    assert proc.returncode == 0, proc.stderr
    return target / ".claude" / "rules"


def test_routing_table_ships_empty(installed_rules: Path):
    """A clean install must not name another ecosystem's repositories.

    Narrower than the sweep above and kept separate on purpose: this is the
    path where the consequence was actually measured, and it must keep failing
    for its own reason even if the sweep is ever relaxed.
    """
    backlog = installed_rules / "cycle-backlog.md"
    assert backlog.is_file()
    found = _leaks(backlog.read_text(encoding="utf-8"))
    assert not found, (
        f"the shipped cycle-backlog.md names origin-ecosystem repositories: {found}. "
        "Every item the consumer files will be refused by G1 as unroutable_repo."
    )


def test_routing_table_still_tells_the_consumer_what_to_do(installed_rules: Path):
    """Emptying without instructing merely trades one failure for another.

    The section must still exist and point at the command that derives it —
    otherwise the consumer finds a void without knowing they are the one to fill it.
    """
    body = (installed_rules / "cycle-backlog.md").read_text(encoding="utf-8")
    section = re.search(r"^##\s+Domain routing\b.*?(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    assert section, "the `## Domain routing` section vanished from the shipped file"
    assert "detect_domains.py" in section.group(0), (
        "the section does not name the script that derives the table for the project"
    )


@pytest.mark.parametrize("name", ["live-target.txt", "acceptance-target.txt"])
def test_target_declarations_ship_undeclared(installed_rules: Path, name: str):
    """An inherited target makes the kit probe somebody else's product.

    `/discover-execute` in live-test mode and `/acceptance` exercise what these
    files declare. Inheriting the origin declaration is not just noise: it produces
    "evidence" about a system that is not the consumer's.
    """
    found = _leaks((installed_rules / name).read_text(encoding="utf-8"))
    assert not found, f"the shipped {name} cites the origin ecosystem: {found}"


def test_every_shipped_config_file_is_clean(installed_rules: Path):
    """A sweep over ALL shipped configuration, not only the known files.

    A new `rules/*.txt` created after this test joins the sweep by itself —
    that is the difference between a test that pins today's list and one that
    pins the rule.
    """
    dirty = {
        p.name: _leaks(p.read_text(encoding="utf-8", errors="replace"))
        for p in sorted(installed_rules.glob("*.txt"))
    }
    dirty = {k: v for k, v in dirty.items() if v}
    assert not dirty, f"shipped configuration citing the origin ecosystem: {dirty}"


#: An absolute path under a user's home. `/home/<name>/` on Linux, `/Users/<name>/`
#: on macOS. Anchored on the separator so a word like "homes" cannot match.
WORKSTATION_PATH_RE = re.compile(r"(?:^|[\s'\"=(`])(/home/[a-z][a-z0-9_-]*|/Users/[A-Za-z][A-Za-z0-9_-]*)/")


def test_no_versioned_file_carries_a_workstation_path():
    """A path under somebody's home directory is one machine's, and this repository
    ships to every consumer.

    Found the hard way on 2026-09-02: a workflow definition under `mechanisms/fleet/`
    defaulted its repository argument to an author's home directory, naming both the
    workstation and the origin ecosystem. (The file is not named here: "a test names
    the file" is one of the signals `stop-validation` reads as coverage, and writing
    it would mark an untested file as tested.) It travelled into an adopter's history and was caught by
    THAT project's publish-hygiene gate — the kit had no check of its own, and
    `ORIGIN_RE` did not fire because it matches `theo-[a-z]`, not `theo` followed
    by a slash.

    History is public retroactively: a path removed tomorrow is still in the commit
    that shipped it.

    A line that must carry the shape — a fixture reproducing a tool's own error
    message — declares it with `workstation-path: <why>` on that line or in the comment block above it,
    the way `rules/english-only.md` handles a quote that must be Portuguese —
    except that accepting the line above spares a reformat when the offending
    string is long, which that rule does not.
    """
    dirty: dict[str, list[str]] = {}
    for path in committable_files():
        rel = str(path.relative_to(REPO))
        if rel in GUARD_FILES or rel == "CHANGELOG.md":
            continue  # released entries record what was true on their day
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Same escape hatch `rules/english-only.md` uses, and for the same reason:
        # a line that MUST carry the shape — a fixture reproducing a tool's own
        # error message — says why, on the line, where the next reader sees it.
        # A silent allow-list elsewhere is a door nobody rereads.
        lines = text.splitlines()
        # The mark counts on the line itself OR the one above it. `english-only`
        # accepts it only inline, and that costs a reformat whenever the offending
        # string is long enough to wrap — measured while writing this file.
        def marked(index: int) -> bool:
            """The line itself, or the contiguous comment block above it.

            A one-line lookback is not enough: a reason worth writing rarely fits
            on one line, and a rule that forces it to is a rule people answer with
            a shorter reason.
            """
            if "workstation-path:" in lines[index]:
                return True
            back = index - 1
            while back >= 0 and lines[back].lstrip().startswith(("#", "//")):
                if "workstation-path:" in lines[back]:
                    return True
                back -= 1
            return False

        exempt = {i for i in range(len(lines)) if marked(i)}
        hits = sorted({
            m.group(1) for i, line in enumerate(lines) if i not in exempt
            for m in WORKSTATION_PATH_RE.finditer(line)
        })
        if hits:
            dirty[rel] = hits

    assert not dirty, (
        f"versioned files carry a workstation path: {dirty}. That path exists on "
        "one machine; every consumer gets the string and none of them get the "
        "directory. Take it from an argument, an environment variable, or the "
        "script's own location."
    )


def test_the_workstation_probe_catches_what_it_is_for():
    """A guard nobody probes is a guard that may already be broken."""
    caught = [
        "const REPO = args?.repo ?? '/home/paulo/Projetos/theo/platform/theo'",
        'PROJECT="/home/someone/dev/app"',
        "path = /Users/dev/Projects/thing",
        "cd /home/ci-runner/work && make",
    ]
    for line in caught:
        assert WORKSTATION_PATH_RE.search(line), f"missed: {line}"

    allowed = [
        "$HOME/dev/theo-cloud",          # the variable, not the resolved path
        "~/dev/project",                 # tilde is not a machine
        "homes/index.md",                # a word containing 'home'
        "/home",                         # no user, no trailing segment
        "look under /homelab/notes",     # different word entirely
    ]
    for line in allowed:
        assert not WORKSTATION_PATH_RE.search(line), f"false positive: {line}"

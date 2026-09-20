#!/usr/bin/env python3
"""Derive THE PROJECT's routing table instead of inheriting someone else's.

O PROBLEMA
----------
`rules/cycle-backlog.md § Domain routing` used to embed the 8 domains of the
ecosystem the kit was written in. Every install carried that table along, and
`backlog-init` instructed people to fit the target's repos *inside* those 8, with
an explicit instruction not to "invent a ninth domain". In a project that is not
that ecosystem, no repo fits.

Measured on an adopter on 2026-08-18: 88 backlog items with measured
`file:line` evidence, all rejected as `BLOCKER/unroutable_repo` — 68 citing
`packages/sdk`, 14 an adopter, and four more packages. The gate was right in
what it said (*"I do not know who to send this to"*); what was wrong was the
table, which belonged to
one project's data living inside the template every project receives.

THE DERIVATION RULE
-------------------
The unit of ownership is the repository, so:

- **Umbrella** (subdirectories with their own `.git`): one domain per repo. That
  is the shape of a multi-repo ecosystem, where each repo has a distinct owner.
- **Single repo**: ONE domain, named after the repository. If it is a monorepo,
  each package enters as a path-addressed `repo` (`packages/sdk`) — the form the
  kit already supports and documents. One domain per package would create six
  specialists where a single SDK exists.

What is NOT derived: who the specialist is. The `agents/<domain>.md` file is named
here, but writing it is human work — a specialist with no content would route the
item into an empty prompt, and `route_domain.py` exits 3 when the file does not
exist, on purpose.

TWO SOURCES, AND THE SECOND ONE WINS
------------------------------------
`--from-backlog` derives from the (domain, repo) pairs the items ALREADY declare.
Use it whenever the registry exists: topology says what exists, not who owns it.
Measured on an adopter — the registry separates `sdk-core`, `repo-platform`,
`sdk-satellites`, `edge-cli-acp` and `memory-adapters`, five domains no directory
layout reveals and no detector should guess.

Usage:
    python3 detect_domains.py                       # print the proposed table
    python3 detect_domains.py --from-backlog BACKLOG.md
    python3 detect_domains.py --write
    python3 detect_domains.py --json

Exit codes:
    0 — table derived (and written, when --write is passed)
    1 — no derivable domain (a directory with no repo and no manifest)
    2 — write error (file without a `## Domain routing` section)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import sys as _sys_bootstrap
from dataclasses import dataclass
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import write_routing_table as _write_root_table  # noqa: E402
from squad import backlog as _shared_backlog  # noqa: E402 — post-bootstrap import

#: Directories that are never an architectural unit, in any ecosystem.
_IGNORED_DIRS = {
    "node_modules", "vendor", "dist", "build", "target", "coverage",
    ".git", ".claude", "__pycache__", ".venv", "venv", ".tox", "testdata",
}

#: Where a monorepo keeps its packages, by each ecosystem's convention.
_WORKSPACE_PARENTS = ("packages", "apps", "services", "crates", "libs", "modules")

#: A manifest proving a subdirectory is a publishable unit.
_PACKAGE_MANIFESTS = ("package.json", "pyproject.toml", "Cargo.toml", "go.mod", "composer.json")

_GO_USE_BLOCK_RE = re.compile(r"^use\s*\((.*?)^\)", re.MULTILINE | re.DOTALL)
_GO_USE_SINGLE_RE = re.compile(r"^use\s+(\S+)\s*$", re.MULTILINE)
_ROUTING_SECTION_RE = re.compile(
    r"^##\s+Domain routing\b.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
)


@dataclass(frozen=True)
class Domain:
    name: str
    repos: list[str]
    agent: str
    #: Repos the registry cites and disk does not have. They stay IN the table,
    #: named — deleting them would hide the divergence, and an item filed against
    #: them routes to code nobody opens. Same decision as the "Repos an inventory
    #: names but disk does not" section kept by hand.
    # None is the "never filled" sentinel `__post_init__` replaces with a list; the
    # annotation states what callers see AFTER construction, which mypy cannot follow.
    missing_on_disk: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.missing_on_disk is None:
            object.__setattr__(self, "missing_on_disk", [])


def _is_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _child_repos(root: Path) -> list[Path]:
    return sorted(
        (p for p in root.iterdir()
         if p.is_dir() and p.name not in _IGNORED_DIRS and not p.name.startswith(".")
         and _is_repo(p)),
        key=lambda p: p.name,
    )


def detect_scope(root: Path) -> str:
    """`umbrella` when more than one governed repository sits below; else `single-repo`.

    `backlog-init` refused to run without an umbrella — *"no umbrella detected: run
    at the workspace root"* — which, in an autonomous project, means creating the
    `BACKLOG.md` at the umbrella root, **outside the project**. Measured on
    an adopter: ten independent repos, each with its own cycle, and the kit
    pushed all ten registries into a directory that is nobody's repository.

    The principle the rule defends ("one question, one place to look") does not
    require an umbrella: it requires **one registry per governed scope**. An
    autonomous repo is a scope.
    """
    root = root.resolve()
    # The root BEING a repository is what decides: a project with a vendored clone
    # below is still a project. An umbrella is the directory that is nobody's
    # repository and exists to group the ones that are.
    if _is_repo(root):
        return "single-repo"
    return "umbrella" if _child_repos(root) else "single-repo"


def _go_workspace_members(root: Path) -> list[str]:
    work = root / "go.work"
    if not work.is_file():
        return []
    text = work.read_text(encoding="utf-8")
    entries: list[str] = []
    for block in _GO_USE_BLOCK_RE.findall(text):
        entries.extend(line.strip() for line in block.splitlines() if line.strip())
    entries.extend(_GO_USE_SINGLE_RE.findall(text))

    members: list[str] = []
    for entry in entries:
        entry = entry.strip().strip('"')
        # A path that leaves the repository belongs to another repository, with
        # gates of its own — a `go.work` may list `../sibling-repo`.
        if not entry or entry.startswith(".."):
            continue
        rel = entry.removeprefix("./")
        if rel and (root / rel).is_dir() and rel not in members:
            members.append(rel)
    return members


def _workspace_packages(root: Path) -> list[str]:
    """A monorepo's packages, addressed by path relative to the root."""
    found: list[str] = []
    for parent_name in _WORKSPACE_PARENTS:
        parent = root / parent_name
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir(), key=lambda p: p.name):
            if not child.is_dir() or child.name in _IGNORED_DIRS or child.name.startswith("."):
                continue
            if any((child / manifest).is_file() for manifest in _PACKAGE_MANIFESTS):
                found.append(f"{parent_name}/{child.name}")
    return found + [m for m in _go_workspace_members(root) if m not in found]


#: Anything that says a directory holds a project rather than being an empty one.
#: Deliberately broad — the question is "is there anything here at all", not
#: "which ecosystem is this".
_PROJECT_SIGNS = (
    ".git", "package.json", "go.mod", "pyproject.toml", "setup.py", "Cargo.toml",
    "pom.xml", "build.gradle", "Gemfile", "composer.json", "Makefile", "Taskfile.yml",
    "requirements.txt", "README.md",
)


def _looks_like_a_project(root: Path) -> bool:
    return any((root / sign).exists() for sign in _PROJECT_SIGNS)


def _group_by_declared_boundary(packages: list[str]) -> list[tuple[str, list[str]]]:
    """Group modules into domains by the boundary the project ALREADY declared.

    A module manifest — `go.mod`, `Cargo.toml`, a workspace `package.json` — is a
    compilation and versioning boundary the project committed to. Deriving domains from
    it reads a line somebody drew rather than inventing one.

    TWO RULES, AND EACH ANSWERS A CASE THAT BROKE THE OTHER SHAPE.

    A module nested UNDER another module joins its ancestor: `operators/api` is part of
    `operators`, not a peer of it. Splitting them would put one Go module's own
    sub-module in a different domain from the code that compiles it.

    What remains groups by its FIRST path segment. This is what keeps the rule from
    regressing to one-domain-per-package, which `agents/README.md` argues against with
    a measured case: an SDK with six thin packages sharing a stack produced six
    specialists repeating the same facts, rotting once per copy. Under this rule those
    six sit at `packages/*` and become ONE domain, while `theo`'s modules — `api`,
    `pkg`, `operators` at the top level — stay separate, because the repository put
    them at separate roots.

    Measured on `theo` (2026-09-10): 17 live items touch a Go module, 13 of them (76%)
    touch exactly one. The obvious fear — `pkg` is imported by four modules, so every
    change there fragments under gate G3 — does not appear in the work: one live item
    touches `pkg`.
    """
    if not packages:
        return []

    module_paths = set(packages)
    grouped: dict[str, list[str]] = {}
    for module in packages:
        parts = module.split("/")
        # Nested under another module -> the ancestor owns it.
        ancestor = next((("/".join(parts[:i]))
                         for i in range(len(parts) - 1, 0, -1)
                         if "/".join(parts[:i]) in module_paths), None)
        domain = (ancestor or module).split("/")[0]
        grouped.setdefault(domain, []).append(module)

    return [(domain, sorted(members)) for domain, members in sorted(grouped.items())]


def detect_domains(root: Path) -> list[Domain]:
    """Derive the domains from the project's real topology."""
    root = root.resolve()
    children = _child_repos(root)

    if children:
        # Umbrella: the unit of ownership is the repository.
        return [
            Domain(name=repo.name, repos=[repo.name], agent=f"agents/{repo.name}.md")
            for repo in children
        ]

    packages = _workspace_packages(root)
    if not packages and not _looks_like_a_project(root):
        # Nothing to derive a topology FROM. The single-repo branch below names
        # the domain after the directory, which is right for a real repository
        # and is fabrication for an empty one: run against an empty temp dir it
        # emitted a routing table for `tmp.ICTIKtMB5K` and demanded a specialist
        # be written for it. A table nobody can act on, derived from a folder
        # name, presented as "derived from this project".
        return []

    name = root.name
    boundaries = _group_by_declared_boundary(packages)
    if not boundaries:
        return [Domain(name=name, repos=[name, *packages],
                       agent=f"agents/{name}.md")]

    #: The root domain is NOT optional when boundaries exist. `route()` matches a repo
    #: EXACTLY (`repo in entry["repos"]`), never by path prefix — so with only module
    #: domains, an item about `charts/`, `docs/` or the Taskfile has no domain at all,
    #: and so does every existing item whose `repo:` is the repository's own name.
    #: Measured on an adopter: 224 items declaring `repo: theo` would have gone
    #: unroutable the moment the table stopped naming `theo`.
    domains = [Domain(name=name, repos=[name], agent=f"agents/{name}.md")]
    domains += [Domain(name=domain, repos=members, agent=f"agents/{domain}.md")
                for domain, members in boundaries]
    return domains


#: Imported, not compiled — `squad/backlog.py` owns what an item header is.
#: Six readers each carried one and they disagreed about the separator.
_ITEM_BLOCK_RE = _shared_backlog.BLOCK_RE
_FIELD_RE = re.compile(r"^(domain|repo):\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)


def domains_from_backlog(backlog_path: Path, root: Path) -> list[Domain]:
    """Derive the table from the (domain, repo) pairs the items ALREADY declare.

    Topology says what exists; it does not say the semantics of ownership.
    Measured on an adopter: the registry separates `sdk-core`, `repo-platform`,
    `sdk-satellites`, `edge-cli-acp` and `memory-adapters` — five domains no
    directory layout reveals and no detector should guess. The items already carry
    the answer; this merely reads it.

    Raises ValueError when a repo appears in two domains: `route_domain` requires
    one-repo-one-domain, and an ambiguous table would route by iteration order —
    the same item going to different places on different runs.
    """
    content = backlog_path.read_text(encoding="utf-8-sig")
    blocks = list(_ITEM_BLOCK_RE.finditer(content))

    by_domain: dict[str, list[str]] = {}
    owner_of: dict[str, str] = {}
    for i, match in enumerate(blocks):
        start = match.end()
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(content)
        fields = dict(_FIELD_RE.findall(content[start:end]))
        domain, repo = fields.get("domain"), fields.get("repo")
        if not domain or not repo:
            continue
        if repo in owner_of and owner_of[repo] != domain:
            raise ValueError(
                f"`{repo}` is declared in two domains ({owner_of[repo]} and {domain}). "
                "route_domain requires one repo, one domain — fix the items before deriving."
            )
        owner_of[repo] = domain
        by_domain.setdefault(domain, [])
        if repo not in by_domain[domain]:
            by_domain[domain].append(repo)

    domains: list[Domain] = []
    for name in sorted(by_domain):
        repos = sorted(by_domain[name])
        missing = [r for r in repos if not (root / r).exists() and r != root.name]
        domains.append(Domain(name=name, repos=repos, agent=f"agents/{name}.md",
                              missing_on_disk=missing))
    return domains


#: Marks that the section needs a human. `check_xrefs` reports WARN while it is in
#: the file — a skeleton that looks like a finished specialist is worse than a broken
#: route, because the broken route at least warns.
UNREVIEWED_MARKER = "<!-- TO BE FILLED IN: only a human knows this -->"


# `render_specialist()` stood here: a second 87-line template for `agents/<domain>.md`,
# called by nothing but its own tests. `scaffold_specialists.render()` does this work and
# is what `SKILL.md` Step 1 names as the live path. Two templates for one artefact is two
# places to update and one that nobody does; the reachable one stays.

def render_table(domains: list[Domain]) -> str:
    lines = [
        "## Domain routing",
        "",
        "`domain` is what assigns the item to a specialist. This table is **derived from this",
        "project** by `skills/backlog-init/scripts/detect_domains.py` — never copied from another",
        "ecosystem's inventory. Re-run it when a repo or package is added; edit it by hand when",
        "ownership does not follow the directory layout.",
        "",
        "| Domain | Repos (present on disk) | Specialist |",
        "|---|---|---|",
    ]
    for domain in domains:
        repos = ", ".join(f"`{r}`" for r in domain.repos)
        lines.append(f"| `{domain.name}` | {repos} | `{domain.agent}` |")
    lines.append("")
    return "\n".join(lines)


#: Header for a routing file that does not have one yet. Kept out of the rows so
#: a re-derive replaces data and leaves the explanation standing — losing it on
#: every `--write` would repeat, one file over, the defect that moved this table
#: out of `cycle-backlog.md` in the first place.
_ROUTING_HEADER = """\
# Domain routing — WHICH REPOSITORIES EXIST HERE, and who owns each.
#
# This file is the PROJECT'S, not the kit's. It lives in `rules/*.txt` for that
# reason: the boundary guard allows the project to edit it, and a reinstall
# preserves it. It used to be a section inside `rules/cycle-backlog.md`, which is
# the kit's contract — so the kit prescribed writing to a file its own guard
# blocked, and the section had to be replaced by regex, which took the invariants
# next to it along.
#
# Format:  domain | repo[, repo...] | agents/<specialist>.md
#
# Derive it:
#   python3 .claude/skills/backlog-init/scripts/detect_domains.py --root . \\
#     --write
#
# Edit by hand when ownership does not follow the directory layout — that case is
# why this is a file you own rather than one the kit overwrites.
#
# The invariants this table must satisfy are NOT repeated here. They are the
# kit's contract and live in `rules/cycle-backlog.md` under `## Routing
# invariants` — `mechanisms/cycle/route_domain.py` enforces them and its own header calls
# that rule the source of truth it refuses to copy. This file is yours and could
# be edited to say anything; the rule that governs it is not.
#
# In short: one repo belongs to exactly one domain, and a repo the inventory
# names but disk does not have stays listed rather than deleted. Read the rule
# for why each is so.
"""


def render_rows(domains: list[Domain]) -> str:
    """The data lines — `domain | repos | specialist`, aligned."""
    if not domains:
        return "# (no domain yet — run detect_domains.py --write)\n"
    width = max(len(d.name) for d in domains)
    lines = []
    for domain in domains:
        repos = ", ".join(domain.repos)
        if domain.missing_on_disk:
            repos += "".join(f", {r} (no checkout)" for r in domain.missing_on_disk)
        lines.append(f"{domain.name:<{width}} | {repos} | {domain.agent}")
    return "\n".join(lines) + "\n"


def write_routing_table(path: Path, domains: list[Domain]) -> None:
    """Write the derived rows to the project's own routing file.

    The comment header is preserved when the file already has one, so re-deriving
    replaces DATA and leaves the explanation. No regex, no adjacent section: the
    file holds one thing, which is the whole point of moving it here.
    """
    header = ""
    if path.is_file():
        kept = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                break
            # The empty-file placeholder is data pretending to be a comment: it
            # says there is no domain, and on the next write it would sit
            # directly above the domains. Keeping it makes the file contradict
            # itself in its first screen.
            if "no domain yet" in stripped:
                continue
            kept.append(line)
        header = "\n".join(kept).rstrip("\n")
    if not header.strip():
        header = _ROUTING_HEADER.rstrip("\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{header}\n\n{render_rows(domains)}", encoding="utf-8")


def rewrite_routing_section(rule_path: Path, domains: list[Domain]) -> None:
    """Replace the `## Domain routing` section, preserving the rest of the file."""
    content = rule_path.read_text(encoding="utf-8-sig")
    if not _ROUTING_SECTION_RE.search(content):
        raise ValueError(f"{rule_path}: no '## Domain routing' section to replace")
    rule_path.write_text(
        _ROUTING_SECTION_RE.sub(lambda _: render_table(domains) + "\n", content, count=1),
        encoding="utf-8",
    )


#: Distinguishes "bare --write" from "--write <path>". A plain default cannot: the
#: destination depends on --root, which argparse has not parsed yet when defaults are
#: built.
_DEFAULT_WRITE = Path("\0default")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--from-backlog", type=Path, default=None,
                        help="derive from the (domain, repo) pairs the items already "
                             "declare — use it when the registry exists: the semantics of "
                             "ownership live there, and no directory layout reveals them")
    #: Bare `--write` writes where the table BELONGS, which the caller should not have
    #: to know. It used to be mandatory to spell the path, so every doc, SKILL.md and
    #: README repeated `rules/domain-routing.txt` — and moving the table meant finding
    #: every copy. An explicit path is still honoured for a consumer mid-migration.
    parser.add_argument("--write", type=Path, nargs="?", const=_DEFAULT_WRITE, default=None,
                        help="write the table. Bare: to the write root, where it belongs. "
                             "With a path: there instead — a `.md` rewrites the legacy "
                             "section, for a consumer that has not migrated")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.write == _DEFAULT_WRITE:
        args.write = _write_root_table(args.root.resolve())

    try:
        domains = (domains_from_backlog(args.from_backlog, args.root.resolve())
                   if args.from_backlog else detect_domains(args.root))
    except ValueError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2
    if not domains:
        print("no derivable domain — the directory is neither a repo nor has a manifest",
              file=sys.stderr)
        return 1

    missing = [d.agent for d in domains if not (args.root / ".claude" / d.agent).is_file()
               and not (args.root / d.agent).is_file()]

    if args.json:
        print(json.dumps({
            "domains": [{"name": d.name, "repos": d.repos, "agent": d.agent} for d in domains],
            "scope": detect_scope(args.root),
            "specialists_missing": missing,
            "repos_missing_on_disk": sorted(
                {r for d in domains for r in d.missing_on_disk}),
        }, indent=2, ensure_ascii=False))
    else:
        print(render_table(domains))
        absent = sorted({r for d in domains for r in d.missing_on_disk})
        if absent:
            print("Repos the registry cites and disk does not have "
                  "(they stay in the table, named, so the divergence does not vanish):")
            for repo in absent:
                print(f"  - {repo}")
        if missing:
            print("Specialists that need writing (route_domain exits 3 without them):")
            for agent in missing:
                print(f"  - {agent}")

    if args.write:
        # Dispatch on the target's format. A `.txt` is the project's own file and
        # is written whole; a `.md` is the legacy section and is replaced in
        # place, so a consumer that has not migrated is not broken by an upgrade.
        try:
            if args.write.suffix == ".md":
                rewrite_routing_section(args.write, domains)
                where = "`## Domain routing` rewritten in"
            else:
                write_routing_table(args.write, domains)
                where = "routing table written to"
        except (ValueError, OSError) as exc:
            print(f"FATAL: {exc}", file=sys.stderr)
            return 2
        print(f"\n==> {where} {args.write}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

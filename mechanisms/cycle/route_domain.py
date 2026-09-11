#!/usr/bin/env python3
"""Route a repo (or a B-NNN item) to its domain specialist.

Deterministic, not heuristic. `/review`'s `detect_domain.py` guesses a technical domain
from keywords because it runs against an arbitrary plan. Here the item already declares
`repo:`, and a repo belongs to exactly one domain — so guessing would only add a way to
be wrong.

The routing table is PARSED from `rules/cycle-backlog.md § Domain routing` rather than
duplicated here. One table, one truth: a copy in code drifts from the rule the moment
someone edits one of them, and the drift is silent — work routes to a specialist who
cannot open the repo, and nothing errors.

Exit codes:
  0 — routed
  1 — repo not in the routing table (gate G1 refuses the item)
  2 — the routing table could not be read or parsed
  3 — routed to a specialist that does not exist on disk (a defect in the table itself)

Exit 3 used to be exit 0 printing `(none declared)`. The invariant behind it lived only in
`tests/test_route_domain.py`, and `install.sh` does not copy `tests/` — so in every consumer
repo the guard was absent and a domain pointing at a missing specialist answered `routed: true`
with `agent: null`. Measured while installing into a TypeScript monorepo: a second three-column table inside
the `## Domain routing` section parses as routing, which invented two domains whose specialist
files were never written, and nothing objected. A resolution that names nobody is the same
vacuous gate D5 exists to catch — so the check belongs in the tool, which always runs, rather
than in a test suite that ships to nowhere.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|(.+?)\|(.+?)\|\s*$", re.MULTILINE)
# `/` is allowed so a repo split across domains can be addressed by path
# (`control-plane/dashboard`). Without it that row parsed to an EMPTY repo list and the
# domain became silently unreachable — every other check still passed.
REPO_RE = re.compile(r"`([A-Za-z0-9_./-]+)`")
# `.claude/` is accepted and stripped: in a plugin install that IS the correct
# path, and it is what `/backlog-init` prints there. Requiring the bare form read
# every such specialist as absent — measured on an adopter, two domains whose
# specialist files were on disk and parsed as `agent: None`, which is the same
# signal as a table nobody finished.
AGENT_RE = re.compile(r"`(?:\.claude/)?(agents/[a-z0-9-]+\.md)`")
# `/` is accepted for the same reason as in REPO_RE: a monorepo is addressed by
# path (`packages/sdk`, `alpha-cloud/dashboard`). Without it the extractor stopped
# at the slash and returned `packages`, routing by a repo nobody wrote.
ITEM_REPO_RE = re.compile(r"^repo:\s*`?([A-Za-z0-9_./-]+)`?", re.MULTILINE)


def _find_project_root(start: Path) -> Path:
    current = start.resolve() if start.is_dir() else start.resolve().parent
    while current != current.parent:
        if (current / "rules").is_dir() or (current / ".git").exists():
            return current
        current = current.parent
    return start.resolve()


def _candidate_roots(declared_root: Path | None = None) -> list[Path]:
    """Where the CONSUMER's table might be, in the order it should be trusted.

    Derived from the INVOCATION, never from this file's own location. Deriving it
    from `Path(__file__)` is what broke the plugin-native layout: the kit lives
    outside the project there, the kit has a `rules/`, so the walk stopped on its
    first step and parsed the empty table the kit ships. Measured 2026-09-08
    (#37) — a consumer with a valid table and its specialist on disk got
    `FATAL: <kit>/rules/domain-routing.txt: has no routing row`, which reads as
    "you never derived your table" and sends the reader to fix something that is
    already correct.

    `.claude-plugin/plugin.json` states why the project is the right subject:
    "the kit's CODE lives outside the project ... and the project keeps only the
    cycle's DATA (records/, rules/*.txt, agents/*.md)".

    The walk up from the working directory stops at the first `.git`, so a
    mechanism run inside a subdirectory finds its own project and never a parent
    project's table.
    """
    roots: list[Path] = []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in roots:
            roots.append(resolved)

    # `--project-root` is a caller naming its subject, and nothing may second-guess
    # it. `check_intake_gates.py` judges a project it was pointed at, which is not
    # necessarily the one the shell is standing in — before this existed it relied
    # on the `__file__` walk to infer it, which is the defect one level up.
    if declared_root is not None:
        return [declared_root.resolve()]

    declared = os.environ.get("CLAUDE_PROJECT_DIR")
    if declared:
        add(Path(declared))

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        add(candidate)
        if (candidate / ".git").exists():
            break

    # Last: the walk this function used to be. It is what makes the standalone
    # repository and the copy install keep behaving exactly as they did.
    add(_find_project_root(Path(__file__)))
    return roots


from pathlib import Path as _Path_bootstrap  # noqa: E402


def _load_paths():
    """The data-root owner, loaded as a FILE rather than through the package.

    `import squad.paths` runs `squad/__init__.py`, which imports the rest of the
    package — so a mechanism copied next to `squad/paths.py` and nothing else dies on
    a dependency it never uses. This module needs two strings from that file.

    It is loaded rather than copied because `check_write_containment.py` refuses a
    second module that spells a data root, and it refuses it for a reason: six lists
    in four different orders is what the single owner replaced.
    """
    import importlib.util

    for up in _Path_bootstrap(__file__).resolve().parents:
        candidate = up / "squad" / "paths.py"
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("_squad_paths", candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # `install.sh` copies `squad/` beside `mechanisms/`, so the two always travel
    # together in a real install. Name the missing file rather than raising
    # `No module named 'squad'` at whoever moved one mechanism on its own.
    raise SystemExit(
        "route_domain.py needs `squad/paths.py`, which owns every data-root name and "
        "is not on disk near this file. `install.sh` copies it beside `mechanisms/`; "
        "a mechanism moved out of an install alone cannot resolve where this project "
        "keeps its routing table."
    )


_paths = _load_paths()

#: `.squad/` first: the table is DERIVED data and belongs with everything else the
#: system produces. The two `rules/` entries are where installs kept it before
#: 2026-09-10 and stay readable indefinitely — a consumer that updates the kit
#: without migrating keeps routing.
_TABLE_LOCATIONS = (
    (_paths.DATA_DIRNAME, _paths.ROUTING_TABLE),
    ("rules", _paths.ROUTING_TABLE),
    (".claude/rules", _paths.ROUTING_TABLE),
    ("rules", "cycle-backlog.md"),
    (".claude/rules", "cycle-backlog.md"),
)


def _routing_table_path(project_root: Path) -> Path | None:
    for parent, name in _TABLE_LOCATIONS:
        candidate = project_root.joinpath(*parent.split("/")) / name
        if candidate.is_file():
            return candidate
    return None


#: A line that LOOKS like a routing row: `| `name` | … |`. Deliberately looser
#: than ROW_RE — the point is to count what a reader would call a domain row,
#: including the ones the strict parser rejects.
_CANDIDATE_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|", re.MULTILINE)


def count_candidate_rows(content: str) -> int:
    """How many rows of the section's FIRST table look like domain rows.

    Exists so a caller can tell a complete parse from a partial one. Migration
    makes that a correctness question: measured on `website`, a four-domain table
    parsed to one, and writing that one out would have presented a third of a map
    as the whole of it.

    Only the first contiguous run of `|` lines under the heading is counted. A
    second table below it — exclusions, most commonly — is not a failed routing
    table, and counting its rows would refuse migrations that are complete.
    """
    section = re.search(
        r"^##\s+Domain routing\b(.*?)(?=^##\s|\Z)", content, re.MULTILINE | re.DOTALL
    )
    if not section:
        return 0
    block: list[str] = []
    for line in section.group(1).splitlines():
        if line.lstrip().startswith("|"):
            block.append(line)
        elif block:
            break   # the first table ended
    return len(_CANDIDATE_ROW_RE.findall("\n".join(block)))


def _rows_from_txt(content: str) -> dict[str, dict[str, Any]]:
    """`domain | repos | specialist`, one per line, `#` starts a comment.

    The same shape every other `rules/*.txt` uses. One convention across the
    kit's configuration files, not two.
    """
    table: dict[str, dict[str, Any]] = {}
    for raw in content.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [cell.strip() for cell in line.split("|")]
        if len(parts) < 3:
            continue
        domain, repos_cell, agent_cell = parts[0], parts[1], parts[2]
        if not domain:
            continue
        table[domain] = {
            "repos": [r.strip() for r in repos_cell.split(",") if r.strip()],
            "agent": agent_cell or None,
        }
    return table


def _rows_from_markdown(content: str, rule_path: Path) -> dict[str, dict[str, Any]]:
    """The legacy `## Domain routing` section, for consumers that have not migrated."""
    section = re.search(
        r"^##\s+Domain routing\b(.*?)(?=^##\s|\Z)", content, re.MULTILINE | re.DOTALL
    )
    if not section:
        raise ValueError(f"{rule_path}: no '## Domain routing' section")

    table: dict[str, dict[str, Any]] = {}
    for match in ROW_RE.finditer(section.group(1)):
        domain, repos_cell, agent_cell = match.groups()
        if domain in {"domain"}:  # header row, if it ever gets backticked
            continue
        agent = AGENT_RE.search(agent_cell)
        table[domain] = {
            "repos": REPO_RE.findall(repos_cell),
            "agent": agent.group(1) if agent else None,
        }
    return table


def parse_routing_table(rule_path: Path) -> dict[str, dict[str, Any]]:
    """Return {domain: {"repos": [...], "agent": "agents/x.md"}} from the table.

    Two formats, one invariant check. `rules/domain-routing.txt` is the project's
    own file; a `.md` is the legacy section, still read so a consumer that has
    not migrated keeps routing.
    """
    content = rule_path.read_text(encoding="utf-8-sig")
    # Dispatch on CONTENT, not on the filename. A `.md` copied to a temp path
    # loses its suffix, and the `.txt` parser then reads a markdown document as
    # pipe-delimited rows — every example table in the file becomes a domain.
    # Measured during the migration: it recovered a domain named `bug` from the
    # kit's own contract file and reported it as the consumer's routing.
    table = (_rows_from_markdown(content, rule_path)
             if re.search(r"^##\s+Domain routing\b", content, re.MULTILINE)
             else _rows_from_txt(content))

    if not table:
        # Name what the reader will actually open. Telling someone their `.txt`
        # has an unparseable `## Domain routing` section sends them looking for a
        # markdown heading that is not in the file.
        where = ("'## Domain routing' parsed to zero rows" if rule_path.suffix == ".md"
                 else "has no routing row — derive one with detect_domains.py --write")
        raise ValueError(f"{rule_path}: {where}")

    # One repo, one domain — enforced HERE rather than in tests/, for the same reason exit 3
    # moved into the tool (see the module docstring). `install.sh` does not copy `tests/`, so a
    # check that lives only there is absent in every consumer install, which is where the tables
    # people actually edit live. `tests/test_route_domain.py::test_no_repo_belongs_to_two_domains`
    # asserts this for THIS repository's table and can only ever do that: it hard-codes the rule
    # path and the domain count.
    #
    # A repo in two rows makes `route()` depend on dict iteration order — the same item routing to
    # a different specialist on a different run, with nothing having changed. That is worse than
    # an unroutable item, because it looks like it worked.
    #
    # Repetition WITHIN one row is not a duplicate: both mentions route identically, so nothing is
    # ambiguous. Rejecting it would turn a cosmetic edit into a broken install.
    seen: dict[str, str] = {}
    for domain, entry in table.items():
        for repo in dict.fromkeys(entry["repos"]):
            if repo in seen:
                raise ValueError(
                    f"{rule_path}: `{repo}` is routed by two domains, `{seen[repo]}` and "
                    f"`{domain}` — routing would depend on dict iteration order. "
                    f"One repo belongs to exactly one domain."
                )
            seen[repo] = domain

    return table


def _specialist_path(agent: str, rule_path: Path, project_root: Path | None) -> Path:
    """Where the specialist file lives, asked of the project rather than of the table.

    This used to be `rule_path.parent.parent / agent`, which worked only because the
    table sat at `<eco>/rules/` — two levels up landed on the installed kit, and the
    specialists sit beside it. Moving the table to the write root on 2026-09-10 broke
    that silently: two levels up became the PROJECT, and every domain reported BROKEN
    ROUTE while the files were on disk the whole time. Found by writing seven
    specialists and watching all seven fail to resolve.

    The location of the routing table and the location of the specialists are two
    independent facts, and deriving one from the other is what coupled them.
    `convene_panel.agents_dir` already owns the second question.
    """
    root = project_root or rule_path.parent.parent
    name = Path(agent).name

    try:
        from convene_panel import agents_dir  # type: ignore
        return agents_dir(root) / name
    except ImportError:
        nested = root / ".claude" / "agents"
        return (nested if nested.is_dir() else root / "agents") / name


def route(repo: str, table: dict[str, dict[str, Any]]) -> tuple[str, str | None] | None:
    for domain, entry in table.items():
        if repo in entry["repos"]:
            return domain, entry["agent"]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route a repo to its domain specialist.")
    parser.add_argument("target", help="repo name, or a path to a B-NNN item file")
    parser.add_argument("--rule", type=Path, default=None, help="override the routing table path")
    parser.add_argument("--project-root", type=Path, default=None,
                        help="the project whose table to read; without it the root is "
                             "resolved from CLAUDE_PROJECT_DIR, then the working directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rule_path = args.rule
    #: The project the table was found UNDER — the specialists are resolved against
    #: this, never against the table's own directory. Keeping the two independent is
    #: what stopped moving the table from silently unrouting every domain.
    found_under = args.project_root
    if rule_path is None:
        for candidate in _candidate_roots(args.project_root):
            rule_path = _routing_table_path(candidate)
            if rule_path is not None:
                found_under = candidate
                break
    if rule_path is None or not rule_path.is_file():
        # Name where it looked. "not found" over an unstated search is what makes
        # a layout defect read as a missing file the reader is supposed to create.
        looked = ", ".join(str(r) for r in _candidate_roots(args.project_root)[:4])
        print(f"FATAL: no routing table (nor a legacy cycle-backlog.md) "
              f"under any of: {looked} — cannot route", file=sys.stderr)
        return 2

    try:
        table = parse_routing_table(rule_path)
    except ValueError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2

    repo = args.target
    candidate = Path(args.target)
    if candidate.is_file():
        found = ITEM_REPO_RE.search(candidate.read_text(encoding="utf-8-sig"))
        if not found:
            print(f"FATAL: no `repo:` field in {candidate}", file=sys.stderr)
            return 2
        repo = found.group(1)

    result = route(repo, table)
    if result is None:
        known = sorted(r for entry in table.values() for r in entry["repos"])
        payload = {"repo": repo, "routed": False, "known_repos": known}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"UNROUTED: `{repo}` is not in the routing table.")
            print("An item nobody owns is an item nobody does — gate G1 refuses it.")
            print(f"Known repos: {', '.join(known)}")
        return 1

    domain, agent = result
    # The specialist has to EXIST. Routing to a filename nobody wrote reads as success at every
    # downstream step — the item looks owned, and the failure only surfaces when someone tries to
    # open the file. See the exit-code note at the top of this module for how it was measured.
    resolved = _specialist_path(agent, rule_path, found_under) if agent else None
    if resolved is None or not resolved.is_file():
        payload = {"repo": repo, "routed": False, "domain": domain, "agent": agent}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"BROKEN ROUTE: `{repo}` routes to domain `{domain}`, whose specialist is")
            print(f"{'  ' + agent if agent else '  not declared at all'} — and that file is not on disk.")
            print("The table names an owner who does not exist. Fix the table or write the specialist.")
            # Say what goes in the file. The kit deliberately does NOT generate
            # it — `agents/README.md` requires build commands *that were
            # checked*, and its closing line notes that a derived skeleton
            # "routes correctly and judges nothing, which reads as a specialist
            # that is ready". But declining to fabricate the invariants is not
            # the same as declining to say what an invariant is, and a message
            # that names only the absence leaves the reader at a dead end.
            if agent:
                repos = table.get(domain, {}).get("repos", [])
                print()
                print(f"What `{agent}` has to carry (agents/README.md § What each agent is")
                print("required to carry):")
                print("  1. Repos verified on disk — with their commit counts, not an inventory")
                print("  2. Build commands THAT WERE RUN, with the manifest that proves them")
                print("  3. The domain's invariants — what is never done here, and why")
                print("  4. The shape of a real finding, and this domain's false positives")
                print("  5. Blast radius — what a change here typically reaches")
                print()
                print(f"Already derived for `{domain}`: {', '.join(repos) or '(no repo listed)'}")
                print("The rest is reading and judgement — 3 and 4 are the file's whole value,")
                print("and a plausible guess at them is worse than an empty file.")
        return 3

    payload = {"repo": repo, "routed": True, "domain": domain, "agent": agent}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"repo   : {repo}")
        print(f"domain : {domain}")
        print(f"agent  : {agent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

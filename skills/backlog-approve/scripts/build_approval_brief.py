#!/usr/bin/env python3
"""One page a person can read, so that `approved` stops being a status nobody writes.

    python3 build_approval_brief.py <project> [--out PATH] [--status triaged]

## The measurement this exists because of

`rules/cycle-backlog.md` calls `approved` a **commitment**: *"somebody decided"*. Across
four real registries on 2026-09-11 there were 325 items and **zero** in `approved` —
and 243 in `shipped`. The path actually walked is `triaged → shipped`, straight past the
gate. The only mention of `--to approved` anywhere in the kit was a line of prose.

This is the same shape the ecosystem already fixed once. `planned` was also zero
everywhere, and the recorded cause was that *"nothing wrote to BACKLOG.md at all, so
every transition was a human editing a line, and the middle one quietly stopped
happening."* `backlog_status.py` closed it for `planned`. Nothing closed it for
`approved`, because a status is not written by declaring that it should be — something
has to ASK, and nothing did.

## What the brief is, and what it is not

It is **not** a review of whether each item is well formed; `check_backlog_structure.py`
already does that and does it better. It is the one question that mechanism cannot ask:
*is this the work you want done?*

So it renders, per item, the four things a person needs in order to answer that and
nothing else: what the item claims, what changed that makes it worth doing now, how
anyone will know it is finished, and whether the evidence it cites can still be found on
disk. Then it puts a box in front of it.

## Why the evidence is checked rather than quoted

An item saying `evidence: infra/helm/x.yaml:91` is making a claim about a file. Quoting
it back would render a broken pointer and a live one identically, and the reader would
have no way to tell which they were looking at. So each pointer is resolved, and the
count is stated — measured against the theo registry, 64 pointers across 28 items, all
of which resolved. A brief that cannot verify says so rather than implying it checked.

**Pointer extraction is deliberately conservative.** An early version counted `10.0.0.0`
and `Status.Reachable` as unresolvable files and reported twelve items as having broken
evidence; all twelve were fine. Over-reporting a broken pointer costs more than missing
one, because the reader loses trust in the whole column.

## Every box starts empty, and that is the design

Approving is a positive act. An unticked item stays `triaged` and loses nothing — it is
simply work nobody has committed to yet, which is the honest state. Pre-ticking would
make the default "yes to everything" and turn the signature into a formality, which is
precisely the failure this brief exists to end.

The per-item boxes sit ABOVE `## Sign-off` on purpose: `/sign` ticks every unticked box
in the section that follows it, so an item box placed below would be approved by the act
of signing rather than by anyone deciding.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
from squad.paths import DATA_DIRNAME, WIKI, write_records_dir  # noqa: E402

#: File extensions an evidence pointer may plausibly name. The allowlist is the guard
#: against the false-positive class described in the module docstring: `10.0.0.0` parses
#: as a dotted name, and `0` is not in here.
CODE_EXT = frozenset({
    "go", "py", "ts", "tsx", "js", "jsx", "mjs", "yaml", "yml", "json", "md", "sh",
    "bash", "tf", "html", "css", "sql", "toml", "ini", "cfg", "txt", "proto", "rs",
    "java", "rb", "php", "c", "h", "cpp", "hpp", "kt", "swift", "xml", "env",
})

#: The leading `(?<![\w.-])` rather than `\b` is what lets a dotted directory start a
#: path. With `\b`, `.squad/wiki/x.md` matched as `squad/wiki/x.md`, which resolves
#: against no root and reported eleven live pointers as missing.
CANDIDATE_RE = re.compile(
    r"(?<![\w.-])((?:\.?[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.([A-Za-z0-9]{1,5})"
    r"|[A-Za-z0-9_][A-Za-z0-9_.-]*\.([A-Za-z0-9]{1,5}))(?![\w-])")
ITEM_SPLIT_RE = re.compile(r"\n(?=## B-\d+)")
ITEM_HEAD_RE = re.compile(r"^## (B-\d+)\s*[—-]\s*(.*?)\s*(?:\[[ x]\])?\s*$", re.M)


@dataclass
class Item:
    item_id: str
    title: str
    fields: dict
    pointers_found: int = 0
    pointers_resolved: int = 0
    unresolved: list = field(default_factory=list)

    @property
    def evidence_verdict(self) -> str:
        """Three outcomes, and the third is not a failure of the item.

        `not verifiable` means the evidence names no file this checker could test — a
        measurement in prose, a conversation, a dashboard. Reporting that as a broken
        pointer would accuse the item of something it did not do.
        """
        if not self.pointers_found:
            return "not verifiable"
        if self.pointers_resolved == self.pointers_found:
            return "checks out"
        return "does not check out"


def _field_block(block: str, name: str) -> str:
    """Read a field that may be a YAML literal block (`name: |`) or a single line."""
    literal = re.search(rf"^{name}:\s*\|\s*\n((?:(?:[ \t]+.*)?\n)*?)(?=^\S|\Z)",
                        block, re.M)
    if literal:
        return "\n".join(line.strip() for line in literal.group(1).splitlines()
                         if line.strip())
    plain = re.search(rf"^{name}:\s*(.*)$", block, re.M)
    if not plain:
        return ""
    first = plain.group(1).strip()
    # A wrapped plain scalar: continuation lines are indented and carry no `key:`.
    #
    # `lstrip("\n")` is load-bearing. `$` under re.M stops BEFORE the newline, so the
    # slice begins with it and `splitlines()[0]` is the empty string — which the
    # blank-line break below read as "the field ended here", truncating every wrapped
    # why_now to its first line.
    tail = block[plain.end():].lstrip("\n")
    for line in tail.splitlines():
        if not line.strip() or re.match(r"^\S", line) or re.match(r"^\s+[A-Za-z_][\w-]*:", line):
            break
        first += " " + line.strip()
    return first.strip()


def _bullets(block: str, name: str) -> list[str]:
    m = re.search(rf"^{name}:\s*\n((?:\s+-\s+.*\n(?:\s{{4,}}.*\n)*)+)", block, re.M)
    if not m:
        return []
    out, current = [], ""
    for line in m.group(1).splitlines():
        if re.match(r"^\s+-\s+", line):
            if current:
                out.append(current.strip())
            current = re.sub(r"^\s+-\s+", "", line)
        elif line.strip():
            current += " " + line.strip()
    if current:
        out.append(current.strip())
    return out


def _search_roots(project: Path) -> list[Path]:
    """Where an evidence pointer may be rooted.

    Items routinely cite a sibling repository or a path under the data root, because the
    thing measured lives there. Resolving only against the project root would report
    those as missing, which is the over-reporting this module refuses to do.
    """
    # Measured against the theo registry: without `.claude` and `.squad/wiki`, three
    # live pointers (`agents/trust.md`, `rules/cycle-design.md`,
    # `decisions/eks-via-awsmanagedcontrolplane.md`) were reported missing. Items cite
    # a path as the writer saw it, and the writer's working directory is not always
    # the project root.
    roots = [project, project / DATA_DIRNAME, project / DATA_DIRNAME / WIKI,
             project / ".claude", project / "docs"]
    umbrella = project.parent
    # A sibling counts only if it is itself a repository. Without this test the parent
    # of a project living directly under $HOME is treated as an umbrella, every dotdir
    # in the home directory becomes a search root, and the first unreadable one
    # (`~/.openclaw`) raised PermissionError out of a read-only checker.
    if umbrella != project and (umbrella / project.name).is_dir():
        siblings = []
        try:
            for entry in sorted(umbrella.iterdir()):
                if entry == project or not entry.is_dir() or entry.name.startswith("."):
                    continue
                if (entry / ".git").exists() or (entry / "BACKLOG.md").is_file():
                    siblings.append(entry)
        except OSError:
            siblings = []
        if siblings:
            roots.append(umbrella)
            roots += siblings
    return roots


def _verify(evidence: str, roots: list[Path]) -> tuple[int, int, list[str]]:
    seen, missing = set(), []
    for match in CANDIDATE_RE.finditer(evidence):
        path = match.group(1)
        ext = (match.group(2) or match.group(3) or "").lower()
        if ext not in CODE_EXT:
            continue
        # A bare name is a MENTION, not a pointer. "build_walkthrough.py" in
        # prose names a script; it does not claim a file at a location, and
        # resolving it project-wide would either miss or match the wrong one.
        # Measured: of 27 bare names in this registry, 2 resolved.
        if "/" not in path:
            continue
        seen.add(path)
    for rel in sorted(seen):
        if not any(_exists(root / rel) for root in roots):
            missing.append(rel)
    return len(seen), len(seen) - len(missing), missing


def _exists(path: Path) -> bool:
    """`Path.exists()` raises on a directory this process may not stat.

    A verifier that dies on an unreadable neighbour reports nothing about the registry
    it was asked to check. Unreadable is not the same as absent, but for this question
    — can the reader follow this pointer — the answers coincide.
    """
    try:
        return path.exists()
    except OSError:
        return False


def parse(backlog: Path, project: Path, wanted_status: str | None) -> list[Item]:
    text = backlog.read_text(encoding="utf-8-sig")
    # Only the section after `## Items`: the index above it repeats every id in a table
    # and would otherwise be parsed as a second copy of the registry.
    body = text.split("\n## Items", 1)[-1]
    roots = _search_roots(project)
    items = []
    for block in ITEM_SPLIT_RE.split(body):
        head = ITEM_HEAD_RE.match(block)
        if not head:
            continue
        fields = {name: _field_block(block, name)
                  for name in ("domain", "repo", "status", "source", "evidence",
                               "why_now", "suggested_mode", "blocked_by")}
        fields["dod"] = _bullets(block, "dod")
        if wanted_status and fields["status"] != wanted_status:
            continue
        item = Item(head.group(1), head.group(2).strip(), fields)
        found, resolved, missing = _verify(fields["evidence"], roots)
        item.pointers_found, item.pointers_resolved = found, resolved
        item.unresolved = missing
        items.append(item)
    return items


def render(items: list[Item], project: Path, wanted_status: str | None) -> str:
    by_domain: dict[str, list[Item]] = {}
    for it in items:
        by_domain.setdefault(it.fields.get("domain") or "(none)", []).append(it)

    checks = sum(1 for i in items if i.evidence_verdict == "checks out")
    fails = sum(1 for i in items if i.evidence_verdict == "does not check out")
    unverifiable = sum(1 for i in items if i.evidence_verdict == "not verifiable")

    out = [
        f"# Backlog approval brief — {project.name}",
        "",
        f"{len(items)} item(s)"
        + (f" at `{wanted_status}`" if wanted_status else "")
        + ", each waiting for one decision that no mechanism in this kit can make: "
        "**is this the work you want done?**",
        "",
        "Structure is checked elsewhere. `check_backlog_structure.py` already refuses a "
        "malformed item, a dangling impediment and an impediment cycle. None of that "
        "answers whether the right work was written down, which is why this page exists.",
        "",
        "## How to use it",
        "",
        "Tick an item to commit to it. Leave it unticked and it stays `triaged` — not "
        "rejected, not killed, simply work nobody has committed to yet. Then sign at the "
        "bottom and run `--apply`, which moves only the ticked items to `approved`.",
        "",
        "Every box starts empty on purpose. Approving is a positive act; a pre-ticked "
        "list would make the default yes-to-everything and turn the signature into a "
        "formality.",
        "",
        "## What the evidence column means",
        "",
        "| Verdict | Items | Means |",
        "|---|---|---|",
        f"| checks out | {checks} | every file the item cites was found on disk |",
        f"| does not check out | {fails} | the item cites a file that is not there — "
        "read this one twice |",
        f"| not verifiable | {unverifiable} | the evidence names no file, so this "
        "checker could not test it. **Not the same as wrong** |",
        "",
        "## Coverage by domain",
        "",
        "Who would do this work, and how it is spread. A domain with nothing in it is "
        "worth a moment: either nothing is needed there, or nobody looked.",
        "",
        "| Domain | Items |",
        "|---|---|",
    ]
    for domain, group in sorted(by_domain.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append(f"| `{domain}` | {len(group)} |")
    out += ["", "---", "", "## The items", ""]

    for it in items:
        out.append(f"- [ ] **{it.item_id}** — {it.title}")
        out.append("")
        why = it.fields.get("why_now") or ""
        if why:
            out.append(f"  **Why now.** {why}")
            out.append("")
        ev = it.evidence_verdict
        if ev == "checks out":
            note = (f"{it.pointers_resolved} of {it.pointers_found} cited file(s) found "
                    "on disk")
        elif ev == "does not check out":
            note = (f"{it.pointers_resolved} of {it.pointers_found} found — MISSING: "
                    + ", ".join(f"`{p}`" for p in it.unresolved[:4]))
        else:
            note = "cites no file this checker can resolve"
        out.append(f"  **Evidence — {ev}.** {note}")
        out.append("")
        dod = it.fields.get("dod") or []
        if dod:
            out.append("  **Done when.**")
            for bullet in dod:
                out.append(f"  - {bullet}")
        else:
            out.append("  **Done when.** _nothing stated — this item has no closing "
                       "criterion._")
        out.append("")
        meta = [f"`{it.fields.get('domain') or '?'}`",
                f"repo `{it.fields.get('repo') or '?'}`",
                f"mode `{it.fields.get('suggested_mode') or '?'}`"]
        blocked = (it.fields.get("blocked_by") or "").strip()
        if blocked and blocked not in ("none", "-", "—"):
            meta.append(f"**blocked on {blocked}**")
        out.append("  " + " · ".join(meta))
        out.append("")

    out += [
        "---",
        "",
        "## Sign-off",
        "",
        "Signing says the ticked items are the work you want done, and that the unticked "
        "ones are deliberately not committed to yet. It does not say the items are well "
        "formed — a machine checked that — and it does not say the work will succeed.",
        "",
        "- [ ] I read the items above and the ticked ones are the work I want done",
        "",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a backlog into one page a person can approve.")
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--out", type=Path, default=None,
                        help="where to write; defaults under the data root")
    parser.add_argument("--status", default="triaged",
                        help="only items at this status (default: triaged); "
                             "pass 'any' for the whole registry")
    parser.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = parser.parse_args()

    project = args.project.resolve()
    backlog = project / "BACKLOG.md"
    if not backlog.is_file():
        print(f"NOT MEASURED: no BACKLOG.md under {project}", file=sys.stderr)
        # 2, because nothing was examined — the kit-wide meaning of "could not measure".
        return 2

    wanted = None if args.status == "any" else args.status
    items = parse(backlog, project, wanted)
    if not items:
        print(f"NOTHING TO APPROVE: no item at status '{args.status}' in {backlog}")
        return 1

    body = render(items, project, wanted)
    if args.stdout:
        print(body)
        return 0
    out = args.out or (write_records_dir(project) / "backlog-approval.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    fails = sum(1 for i in items if i.evidence_verdict == "does not check out")
    print(f"wrote {out}")
    print(f"  {len(items)} item(s) awaiting a decision"
          + (f" · {fails} cite a file that is not on disk" if fails else ""))
    print("  tick what you want done, then:")
    print(f"    /sign {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Squad domain specialists

One agent per domain of the project this kit governs. Each knows the repos it covers, the build commands **verified on disk** rather than copied from a table, the invariants of its domain, and the shapes a real finding takes there.

`domain` on a `B-NNN` item routes to exactly one of them (`rules/cycle-backlog.md § Domain routing`). Work spanning two domains is two items — gate G3.

**This directory ships empty on purpose.** A specialist file describes repositories that exist in *one* ecosystem; shipping someone else's makes gate G1 refuse every item a consumer files, because the map genuinely does not name their repos. Measured on an adopter in 2026-08-18: 88 items carrying real `file:line` evidence, all `BLOCKER/unroutable_repo`. What travels is this README — the mechanism — and the script that derives the routing table.

## Deriving yours

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)   # plugin vs standalone
python3 "$ECO/skills/backlog-init/scripts/detect_domains.py" --root . \
  --write "$ECO/rules/domain-routing.txt"
```

The script reads the topology from disk — not from an inventory, not from a `CLAUDE.md` — and writes the routing table. Then write one file here per domain it names, and `route_domain.py` will resolve them: a domain naming a specialist that is not on disk exits 3 (`BROKEN ROUTE`) rather than reporting a route to nobody.

## Choosing the granularity

One agent per repo duplicates the same facts across every repo that shares a stack, and rots once per copy. One agent per role (backend / frontend / SRE) is too coarse to carry an invariant like "this RDS instance is a protected unit" or "a root `go build ./...` covers nothing here, the repo is multi-module". **The domain is the granularity at which the invariants differ** — that is the line to cut on.

## What each agent is required to carry

1. **Repos verified on disk** — `find -maxdepth 2 -name .git` plus `git -C <repo> rev-list --count HEAD`, never an inventory table.
2. **Build commands that were checked**, with the manifest that proves them.
3. **The domain's invariants** — what is never done here, and why.
4. **The shape of a real finding**, and the false positives this domain generates.
5. **Blast-radius heuristics** — what a change here typically reaches.

Requirement 1 is the one that pays for itself. Two failures found while deriving a real map, both live in that ecosystem's own `CLAUDE.md`: a CLI documented under `pnpm` that actually uses `npm` (a test run under the wrong package manager resolves a different dependency graph than the lockfile pins — green, and testing something other than what ships), and five repos the inventory named that had no checkout a week after it claimed to be verified. Documentation drifts; a routing table naming a repo nobody cloned sends work to a specialist who cannot open the code.

`scripts/check_xrefs.py` emits a WARN for any agent here still carrying unfilled sections — a derived skeleton routes correctly and judges nothing, which reads as a specialist that is ready.

## Related

- Routing table: [`rules/cycle-backlog.md`](../rules/cycle-backlog.md)
- Evidence contracts per mode: [`rules/cycle-discover.md`](../rules/cycle-discover.md)
- Live environments: [`rules/live-target.txt`](../rules/live-target.txt)
- Constraint lens: [`rules/current-constraint.md`](../rules/current-constraint.md)

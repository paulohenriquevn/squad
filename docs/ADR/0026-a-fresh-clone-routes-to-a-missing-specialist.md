# ADR-0026: A fresh clone routes to a missing specialist, and says so

**Status:** Accepted
**Date:** 2026-09-22 (decided by the sponsor; recorded 2026-09-25)
**Issue:** #152

## Context

The domain routing table lives in `.squad/domain-routing.txt`, which is versioned. The
specialist files it names live under `.claude/agents/`, which is not: `.claude/` is the
installed kit plus the project's own agents, and the kit's rule is that `.claude/` never
enters a repository (see `rules/records-location.md`).

So a fresh clone carries a table that names specialists the clone does not have.
`route_domain.py` resolves the route, finds no file, and exits 3 (`BROKEN ROUTE`).

## Decision

This is correct behaviour. A route to a file that is not there is reported as broken,
loudly, rather than resolved to something that is not the specialist the table names.
`route_domain.py` tells the reader, at the point they meet the exit, that this is what a
fresh clone looks like and that `/backlog-init` derives the table and names the files to
write.

## Alternatives declined

- **Version `.claude/agents/` alone.** It makes one subdirectory of an unversioned tree an
  exception that nobody downstream can explain, and every future reader of the
  `.gitignore` has to rediscover why.
- **Have the installer generate the specialists.** The kit would author content that is
  the project's. A specialist's value is the invariants and false positives of its
  domain, which a derived skeleton cannot know; it would route correctly and judge
  nothing, and the installer would overwrite a hand-edited specialist on every install.

## Consequences

- A fresh clone cannot route until its specialists are written. The exit code and the
  message make that visible instead of silent.
- The message is pinned by
  `tests/test_route_domain.py::test_a_fresh_clone_without_specialists_exits_3_and_says_why`.

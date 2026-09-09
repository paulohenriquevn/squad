"""Verb dispatch for `sq`, deliberately not `argparse.add_subparsers`.

WHY NOT SUBPARSERS
------------------
No CLI in this repository uses `add_subparsers` — all 109 of them are flat
`main(argv) -> int` with `parse_args(argv)`. Keeping each verb in that shape means
every verb stays a normal citizen: directly runnable as
`python3 -m squad.cli.run_suites --json`, directly testable in-process, and readable
by anyone who has read any other script here.

Subparsers would also have given away two things that matter:

- **`sq` with no verb would exit 0.** argparse prints help and succeeds. A command
  that did nothing and reported success is the doctrine violation this whole CLI was
  built to prevent, so a bare `sq` exits 2 — it could not measure anything.
- **The unknown-verb message could not name the verbs.** "wrong argument form twice;
  the usage text arrives only after exit 2" is on the measured friction list that
  justified this tool. Guessing wrong should cost one call, not two.

Verb modules are imported INSIDE the dispatch so that `sq where` does not pay for
whatever `sq check` needs.

Exit codes:
    0 — the verb ran and its subject held
    1 — the verb ran and found something, or refused
    2 — no verb, an unknown verb, or the verb could not measure
"""
from __future__ import annotations

import sys
from collections.abc import Callable

#: verb -> "module:function". A dict rather than a parser, so the verb list lives in
#: one place. Two verbs may share a module (`where` and `run` both read the same
#: index) and each still names its own entry point, so no callee has to re-parse the
#: verb out of its own argv.
VERBS: dict[str, str] = {
    "test": "squad.cli.run_suites:main",
    "check": "squad.cli.run_checks:main",
    "where": "squad.cli.locate:main_where",
    "run": "squad.cli.locate:main_run",
}

USAGE = """sq — find, check and run the kit, without knowing where anything lives

usage: sq <verb> [options]

verbs:
  test [--touched]  run the suites, and name the ones that did not run
  check             replay what CI verifies, and name what it does not reach
  where <name>      where a mechanism lives, what it does, how to invoke it
  run <name> [...]  run a mechanism by name, without knowing its path

  sq <verb> --help  the options for one verb

Every verb states what it did NOT check. A report with no such line is a bug."""


def _load(verb: str) -> Callable[[list[str]], int]:
    from importlib import import_module

    module_path, _, function_name = VERBS[verb].partition(":")
    return getattr(import_module(module_path), function_name)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        # Help on stderr, exit 2: nothing was asked, so nothing was measured.
        print(USAGE, file=sys.stderr)
        return 2

    verb, rest = argv[0], argv[1:]

    if verb in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    if verb not in VERBS:
        print(f"sq: unknown verb {verb!r}", file=sys.stderr)
        print(f"    known verbs: {', '.join(sorted(VERBS))}", file=sys.stderr)
        print("    sq --help for what each one does", file=sys.stderr)
        return 2

    return _load(verb)(rest)


if __name__ == "__main__":
    raise SystemExit(main())

"""`python3 -m squad.cli` — the entry point that reaches a consumer.

`mechanisms/distribution/install.sh` copies DIRECTORIES (`skills rules hooks commands
mechanisms squad`), so the root `sq` file is a convenience for this repository alone
and never travels. `squad/` does travel, which makes this module the form of the CLI
a consumer actually gets.
"""
from __future__ import annotations

from squad.cli.router import main

raise SystemExit(main())

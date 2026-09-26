"""B-198 — `install.sh` composed the routing table's destination by hand.

`squad/paths.py` owns where data is written, and `rules/records-location.md` states the reason
in its own words: "every data-root literal lives in `squad/paths.py`", so that a reader
resolving one root cannot find a directory a writer using another never filled.

`detect_domains.py` obeys it — it imports `write_routing_table` from the owner. `install.sh`
did not: it set `target="$ECO/rules/domain-routing.txt"` in shell and handed that string to the
write, so a REINSTALL recreated the legacy path in a project that had already migrated.

Measured 2026-09-21: `install.sh:513` composed the path and `:619` wrote to it, while the
heredoc three lines above had already imported the owner's resolver.

## Why the assertion is over the SOURCE

The migration only runs with a consumer tree, a legacy table and a `BACKLOG.md` in place, so
exercising it end to end means building a fixture consumer per case. What can be asserted
cheaply and without rotting is the property that matters: the destination is RESOLVED, never
spelled. A spelled path is the defect itself, whatever the surrounding logic does with it.
"""

from __future__ import annotations

import re
from pathlib import Path

INSTALLER = Path(__file__).parent.parent / "mechanisms" / "distribution" / "install.sh"

#: The data-root literal this file must not compose. `.md` is the TEMPLATE that ships with the
#: kit and is legitimately named; `.txt` is the consumer's derived data, which the owner places.
SPELLED_DESTINATION = re.compile(r"""["'][^"'\n]*rules/domain-routing\.txt["']""")


def test_the_installer_does_not_spell_the_tables_destination() -> None:
    source = INSTALLER.read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in source.splitlines()
        if SPELLED_DESTINATION.search(line) and not line.lstrip().startswith("#")
    ]
    assert offenders == [], (
        "install.sh composes the routing table's destination instead of resolving it from "
        f"`squad.paths`: {offenders}. A reinstall then recreates the legacy path in a project "
        "that migrated, and `rules/records-location.md` exists to prevent exactly that."
    )


def test_the_installer_still_names_the_template_it_ships() -> None:
    """The counter-case. `domain-routing.md` is the kit's own template and MUST be named — an
    assertion that banned the whole phrase would pass by deleting the migration."""
    source = INSTALLER.read_text(encoding="utf-8")
    assert "domain-routing.md" in source, (
        "the installer no longer names the template it copies; the rule above is about the "
        "consumer's DATA path, not about the kit's own file"
    )

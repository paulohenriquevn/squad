#!/usr/bin/env python3
"""PostToolUse — flag claims in public copy that measurement has not earned.

`rules/public-copy.md` is the contract. What it guards is narrow: a README says
things to people who cannot check them, and the cheapest sentence to write is the
one nobody has measured. `production-ready`, `battle-tested`, `99.99% uptime` —
each is a claim about sustained evidence, and writing it before the evidence
exists spends credibility that is hard to get back.

**Advisory, never blocking.** Some of these are the right words sometimes, and a
gate that blocks a README is a gate somebody switches off. It warns, names the
rule, and lets the writer decide.

Two of the checks are conditional rather than absolute: a comparative claim is
fine WITH a benchmark link, and an SLA number is fine when qualified as a target.
Those are the cases where the sentence and its evidence travel together — which
is why this reads the whole file rather than the fragment an `Edit` replaced.

The checks themselves live in `squad.public_copy`, because `stop-validation` asks
the same question at the end of the session and a second list is how the two
answers drift apart.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import PostToolUseContext, create_context
from squad.layout import resolve
from squad.public_copy import is_public, warnings as lint


def main() -> None:
    c = create_context(PostToolUseContext)
    path = c.tool_input.get("file_path") or c.tool_input.get("filePath")
    if not path or not is_public(path):
        return
    # The FILE, not the edited fragment. `excused_by` asks whether the evidence
    # travels with the claim, and an `Edit` hands over the replaced text alone —
    # so a benchmark link two paragraphs up was invisible and the claim it
    # excuses was reported anyway. Falling back to the fragment keeps the check
    # alive for a path that cannot be read.
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        content = c.tool_input.get("new_string") or c.tool_input.get("content") or ""
    if not content:
        return

    found = lint(content)
    if not found:
        return

    layout = resolve()
    reference = f"{layout.kit_dir}/rules/public-copy.md" if layout else "rules/public-copy.md"
    print(f"Public copy lint — advisory warnings on {path}:")
    print()
    for warning in found:
        print(f"  [WARN] {warning}")
        print()
    print(f"Reference: {reference}.")


if __name__ == "__main__":
    main()

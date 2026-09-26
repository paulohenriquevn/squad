"""`sq` — the kit's task-oriented surface.

`rules/README.md` places a file by who OWNS it, which is what lets an installer
preserve a consumer's configuration and overwrite the kit's contracts. It is also
what makes the tree unsearchable by task, because ownership and task are different
axes. This package is the projection of one onto the other.

It computes no verdict. Every command here reads what the mechanisms already
produce, and the moment one of them starts deciding something, it belongs in
`mechanisms/` instead — see `docs/wiki/decisions/the-cli-navigates-mechanisms-compute.md`.
"""
from __future__ import annotations

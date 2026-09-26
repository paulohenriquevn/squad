"""One reading of a git remote URL as `owner/name`.

WHY THIS MODULE EXISTS. `gh` cannot resolve an SSH host alias, so two callers read the
slug out of `git remote get-url origin` themselves to pass `gh -R OWNER/NAME`:
`mechanisms/cycle/promote_to_develop.py` and the board's issues panel. Each carried its
own parse, and they disagreed on the commonest remote there is. The board's kept only
what followed a `:` in the host part, so `https://github.com/owner/name.git` gave
nothing and its issues panel went dark; its test passed only on a machine whose global
git config rewrote HTTPS remotes to SSH (measured 2026-09-25, on the first CI run in
eleven days).

THE SHAPES. The slug is the tail, never the host:

    https://host/owner/name(.git)      scheme, host, path
    ssh://user@host:22/owner/name      same, with a port
    git@host:owner/name(.git)          scp-like: the path follows the first `:`
    alias:owner/name(.git)             scp-like with the user in ssh config

A local path or `file://` URL names no hosted repository, and answers None rather than
its last two directories.
"""
from __future__ import annotations

import re

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def owner_repo(url: str) -> str | None:
    """`owner/name` for a hosted remote, None for anything else."""
    url = url.strip()
    if not url or url.startswith(("/", ".", "~")) or url.lower().startswith("file:"):
        return None
    if _SCHEME.match(url):
        # Everything up to the first `/` after the scheme is the authority.
        _, _, path = _SCHEME.sub("", url).partition("/")
    elif ":" in url.split("/", 1)[0]:
        path = url.split(":", 1)[1]
    else:
        return None
    parts = [p for p in path.rstrip("/").removesuffix(".git").split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else None

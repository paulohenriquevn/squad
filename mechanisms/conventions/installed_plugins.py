#!/usr/bin/env python3
"""Which Claude Code plugins this machine has, and where they live.

    python3 mechanisms/conventions/installed_plugins.py --list
    python3 mechanisms/conventions/installed_plugins.py --resolve loop-security-audit

## Why this is a convention and not a gate

It computes no verdict. It answers *where does this live* for a class of thing the kit
does not ship — and that is the question `mechanisms/README.md` gives this family.

## Why it can be answered at all

`rules/review-panel.txt` recorded, on 2026-09-09, that closing the judge-codex seat's
verification "means asking Claude Code which plugins are installed, which nothing in
this kit does yet". That was true of the kit and false of the machine: Claude Code
keeps `~/.claude/plugins/installed_plugins.json`, and every entry carries an
`installPath`. Measured here — 31 plugins, of which 17 are the loop family, and 152
agent files reachable underneath them.

So a plugin-supplied reviewer or auditor is verifiable from disk, deterministically,
with no new dependency and no process to interrogate.

## What it deliberately does not do

It does not decide whether a plugin SHOULD be used, and it does not run one. A caller
that cannot find a plugin it needs has a coverage gap to report — never a silence to
keep.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

#: Claude Code's own manifest. Overridable so a test never depends on what happens to
#: be installed on the machine running it.
_ENV_HOME = "CLAUDE_CONFIG_DIR"


def manifest_path(config_dir: Path | None = None) -> Path:
    base = config_dir or Path(os.environ.get(_ENV_HOME, Path.home() / ".claude"))
    return base / "plugins" / "installed_plugins.json"


@dataclass(frozen=True)
class Plugin:
    """One installed plugin, and the tree it was installed into."""

    name: str          #: bare name, without the `@marketplace` suffix
    qualified: str     #: `name@marketplace`, as the manifest keys it
    version: str
    install_path: Path
    #: The revision the INSTALLED copy was built from, as Claude Code recorded it, or
    #: None when the manifest entry carries none. `install_path` points into a CACHE, so
    #: this is the only field that says WHICH revision is actually running —
    #: `check_plugin_freshness.py` compares it against the source repository's HEAD.
    commit: str | None = None

    @property
    def marketplace(self) -> str:
        """The half of `qualified` after `@` — the key `known_marketplaces.json` uses."""
        return self.qualified.split("@", 1)[-1]

    @property
    def agents_dir(self) -> Path:
        return self.install_path / "agents"

    def agents(self) -> list[str]:
        """Agent names this plugin supplies, addressable as `<plugin>:<agent>`."""
        d = self.agents_dir
        return sorted(f.stem for f in d.glob("*.md")) if d.is_dir() else []

    def has_agent(self, agent: str) -> bool:
        return (self.agents_dir / f"{agent}.md").is_file()

    def agent_model(self, agent: str) -> str | None:
        """The `model:` this agent's frontmatter declares, or None if it declares none.

        This is the model a `builtin` seat actually runs on: naming a `plugin:agent`
        spawns the sub-agent, and the frontmatter is what selects its model. A roster
        that declares a different one is describing something else.

        None is NOT a disagreement. An agent with no `model:` inherits the caller's,
        which no static read can name, so the only honest answer is that nothing was
        said. Returning a default here would manufacture the contradiction the caller
        is asking about.

        Only the frontmatter block is read — a `model:` line in the prose below it is
        documentation, not configuration.
        """
        path = self.agents_dir / f"{agent}.md"
        if not path.is_file():
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            return None
        for line in lines[1:]:
            if line.strip() == "---":
                return None
            key, sep, value = line.partition(":")
            if sep and key.strip() == "model":
                return value.strip() or None
        return None


def load(config_dir: Path | None = None) -> dict[str, Plugin]:
    """Every installed plugin, keyed by bare name.

    A manifest that cannot be read yields NOTHING rather than raising: a machine with
    no plugins and a machine whose manifest moved are the same fact to a caller — it
    cannot reach a plugin — and both must be reported by that caller rather than
    turned into an exception it did not ask for.

    When one name is installed from two marketplaces the first entry wins and the
    other is reachable by its qualified name, because silently preferring one would
    hide that the ambiguity exists.
    """
    path = manifest_path(config_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    out: dict[str, Plugin] = {}
    for qualified, entries in (data.get("plugins") or {}).items():
        if not entries:
            continue
        entry = entries[0]
        install = entry.get("installPath")
        if not install:
            continue
        bare = qualified.split("@", 1)[0]
        plugin = Plugin(name=bare, qualified=qualified,
                        version=entry.get("version", "unknown"),
                        install_path=Path(install),
                        commit=entry.get("gitCommitSha") or None)
        out.setdefault(bare, plugin)
        out[qualified] = plugin
    return out


def resolve(name: str, config_dir: Path | None = None) -> Plugin | None:
    """The plugin by bare or qualified name, or None when it is not installed."""
    return load(config_dir).get(name)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # Declared so the documented invocation is accepted, and the listing is the
    # default anyway — `args.list` was referenced nowhere, so the flag was taken,
    # ignored, and indistinguishable from one that works. Naming it here makes it
    # the explicit spelling of what happens with no flag at all.
    ap.add_argument("--list", action="store_true",
                    help="list installed plugins (the default with no other flag)")
    ap.add_argument("--resolve", metavar="NAME")
    ap.add_argument("--agents", metavar="NAME", help="agents this plugin supplies")
    ap.add_argument("--config-dir", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    plugins = load(args.config_dir)
    bare = {p.name: p for p in plugins.values()}

    if args.resolve or args.agents:
        want = args.resolve or args.agents
        p = plugins.get(want)
        if p is None:
            print(f"not installed: {want}", file=sys.stderr)
            return 1
        body = {"name": p.name, "qualified": p.qualified, "version": p.version,
                "install_path": str(p.install_path), "agents": p.agents()}
        if args.json:
            print(json.dumps(body, indent=2))
        elif args.agents:
            print("\n".join(body["agents"]) or "(no agents)")
        else:
            print(f"{p.qualified} {p.version}\n{p.install_path}")
        return 0

    if args.json:
        print(json.dumps(
            {n: {"version": p.version, "install_path": str(p.install_path),
                 "agents": len(p.agents())}
             for n, p in sorted(bare.items())}, indent=2))
    else:
        for n, p in sorted(bare.items()):
            print(f"{n:34} {p.version:10} {len(p.agents()):3} agent(s)")
        print(f"\n{len(bare)} plugin(s) installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def marketplace_source(marketplace: str, config_dir: Path | None = None) -> dict:
    """Where a marketplace's plugins come FROM, per `known_marketplaces.json`.

    It lives here rather than in its caller for the reason the exemption in
    `check_produced_files.HOME_WRITERS` already states about this module: reading the
    user's own configuration under `~/.claude/plugins/` is this module's job, and a second
    spelling of that path in a gate would be a second place to get it wrong — and a second
    module needing the same exemption for the same reason.

    An empty dict when the file cannot be read or the marketplace is unknown. A caller
    that cannot tell WHERE a plugin came from must report that it could not tell, never
    assume a default.
    """
    path = manifest_path(config_dir).with_name("known_marketplaces.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entry = data.get(marketplace) if isinstance(data, dict) else None
    source = (entry or {}).get("source") if isinstance(entry, dict) else None
    return source if isinstance(source, dict) else {}

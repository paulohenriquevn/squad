#!/usr/bin/env python3
"""PreToolUse — refuse Bash commands that break a rule nobody gets to break once.

Everything here guards an action whose cost is asymmetric: `git checkout` loses
uncommitted work, a force-push rewrites what others pulled, a commit on the trunk
skips every gate between it and a release, `rm -rf /home` needs no explanation.
Each is cheap to prevent and expensive to undo, which is the whole case for a
hook rather than a convention.

FAIL-CLOSED
-----------
A payload that cannot be read blocks. `squad.create_context` does that, and the
shell version said the same in its own header — *"F5: fail CLOSED if jq is
unavailable"*. A validator that cannot parse its input has not approved the
command; it has failed to look at it, and those must not produce the same exit.

THE BRANCH IS PART OF THE DECISION
-----------------------------------
Half of these refusals depend on where HEAD is, and on where the command is about
to MOVE it: `git switch main && git commit` is refused from anywhere, because by
the time the commit runs the branch has changed. Quoted text is stripped before
matching, so a commit MESSAGE mentioning `main` is not read as a branch.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from squad import PreToolUseContext, create_context  # noqa: E402

# ── the read-only zone (rules/reference-provenance.md § 1) ────────────────────
ZONE = r"(\./)?(\.claude/)?study-material/"
ZONE_RE = re.compile(ZONE)

# ── git ───────────────────────────────────────────────────────────────────────
_GIT_GLOBALS = re.compile(
    r"(^|[^\w.])git\s+(--git-dir=\S+|--work-tree=\S+|-[cC]\s+\S+|--paginate|-p)\s+")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_SEGMENTS = re.compile(r"\|\||&&|;")
_SEGMENTS_WITH_PIPE = re.compile(r"\|\||&&|;|\|")

FORCE_TOKEN_RE = re.compile(r"(--force(\s|$)|(^|\s)-[a-z]*f(\s|$)|\s\+[^\s-]\S*)")

RM_INVOCATION_RE = re.compile(r"(^|\s|;|&&|\|\||\||\()\s*rm\s")
RM_RECURSIVE_RE = re.compile(r"(^|\s)(-[a-zA-Z]*[rR][a-zA-Z]*(\s|$)|--recursive(\s|=|$))")
DANGEROUS_PATH_RE = re.compile(
    r"(/(\s|$)|(^|\s)/\*|~/?(\s|$)|\$HOME/?(\s|$)|/home(\s|$)|/home/(\s|$)"
    r"|/home/[^/\s]+/?(\s|$)|(/etc|/usr|/var|/bin|/lib|/opt|/boot|/root)(\s|/|$))")

EXPORT_VERB_RE = re.compile(r"(^|\s|\()\s*(cp|mv|rsync|scp|install|tar|zip|dd)(\s|$)")
EXPORT_REDIRECT_RE = re.compile(r">{1,2}\s*[^\s&>]")
EXPORT_PIPE_RE = re.compile(r"\|\s*(tee|dd)(\s|$)")
ZONE_WRITE_RE = re.compile(
    rf"(^|\s|;|&&|\|\||\||\()\s*((rm|mv|cp|sed\s+-i|tee)\s+[^;&|]*{ZONE}|>{{1,2}}\s+{ZONE})")

PKG_INSTALL_RE = re.compile(
    r"(pip|poetry|uv|npm|pnpm|yarn|cargo|go\s+(get|mod))\s+(install|add|tidy|download)")


def _git_out(*args: str) -> str:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, timeout=5)  # noqa: PLW1510
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def strip_git_globals(command: str) -> str:
    """`git -C /x commit` reads as `git commit`, so a global flag cannot hide it."""
    previous = None
    while command != previous:
        previous = command
        command = _GIT_GLOBALS.sub(r"\1git ", command)
    return command


def segments(command: str, *, with_pipe: bool = False) -> list[str]:
    """Judged per segment, so an unrelated `cp` in a compound is not blamed on
    a zone path that appears elsewhere in the same line."""
    pattern = _SEGMENTS_WITH_PIPE if with_pipe else _SEGMENTS
    return pattern.split(command)


def trunks() -> list[str]:
    """`main`, `master`, and whatever the remote actually calls its default.

    F12: a project whose trunk is `trunk` or `release` installed this kit, read
    Rule 4, and got no protection because the rule named `main`. The remote's
    HEAD is the honest source; `workspace` and `develop` are excluded because
    they have their own rules and are never the trunk.
    """
    names = ["main", "master"]
    default = _git_out("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    default = default.removeprefix("origin/")
    if default and default not in ("workspace", "develop") and default not in names:
        names.append(default)
    return names


def _targets(unquoted: str, branch: str) -> bool:
    """Does the command move HEAD onto `branch`? `switch -c` and `checkout -b` too."""
    return bool(re.search(rf"git\s+switch\s+(-[cC]\s+)?{re.escape(branch)}(\s|$)", unquoted)
                or re.search(rf"git\s+checkout\s+(-b\s+)?{re.escape(branch)}(\s|$)", unquoted))


def check_git(command: str) -> str | None:
    cmd = strip_git_globals(command)

    if re.search(r"git\s+checkout(\s|$)", cmd):
        return ("BLOCKED: 'git checkout' is forbidden by Unbreakable Rule 4. "
                "Use 'git switch' or 'git restore' instead.")
    if re.search(r"git\s+revert(\s|$)", cmd):
        return ("BLOCKED: 'git revert' is forbidden by Unbreakable Rule 4. "
                "Create a new commit that reverses the change explicitly.")
    for segment in segments(cmd, with_pipe=True):
        if re.search(r"git\s+push(\s|$)", segment) and FORCE_TOKEN_RE.search(segment):
            return ("BLOCKED: force push is forbidden. Use --force-with-lease only "
                    "when explicitly authorized.")
    if re.search(r"git\s+reset\s+--hard", cmd):
        return ("BLOCKED: 'git reset --hard' is forbidden. Use 'git stash' or create "
                "a branch instead.")

    # Quoted text is not a branch name: a commit MESSAGE saying "main" must not
    # read as switching to it.
    unquoted = _QUOTED.sub("", cmd)
    branch = _git_out("branch", "--show-current") or "unknown"
    names = trunks()

    on_trunk = branch in names
    moving_to_trunk = any(_targets(unquoted, name) for name in names)
    if on_trunk or moving_to_trunk:
        if re.search(r"git\s+commit(\s|$)", unquoted):
            return (f"BLOCKED: never commit directly to the trunk '{branch}' "
                    f"(Unbreakable Rule 4). Work is born on 'workspace' "
                    f"(workspace → develop → trunk); develop integrates, it never "
                    f"originates.")
        if re.search(r"git\s+(merge|rebase|reset|cherry-pick)(\s|$)", unquoted):
            return (f"BLOCKED: never mutate the trunk '{branch}' directly (Unbreakable "
                    f"Rule 4). It receives release merges only, via a develop→trunk PR. "
                    f"Switch to 'workspace' first.")

    if branch == "develop" or _targets(unquoted, "develop"):
        if re.search(r"git\s+commit(\s|$)", unquoted):
            return ("BLOCKED: never commit directly to 'develop' (git-safety.md § 1). "
                    "Work is born on 'workspace' and reaches develop through a "
                    "workspace→develop PR. Switch to 'workspace' first.")
        if re.search(r"git\s+(rebase|reset|cherry-pick)(\s|$)", unquoted):
            return ("BLOCKED: never rewrite 'develop' history (git-safety.md § 1). "
                    "develop integrates work, it never originates it. Do the work on "
                    "'workspace' and promote it via PR.")
        if re.search(r"git\s+merge(\s|$)", unquoted) and not re.search(
                r"git\s+merge(\s+-\S+)*\s+((origin|upstream)/)?workspace(\s|$)", unquoted):
            return ("BLOCKED: 'develop' only accepts the promotion merge from "
                    "'workspace' (git-safety.md § 1). Merging anything else into "
                    "develop bypasses the workspace→develop gate.")
    return None


def check_rm(command: str) -> str | None:
    if (RM_INVOCATION_RE.search(command) and RM_RECURSIVE_RE.search(command)
            and DANGEROUS_PATH_RE.search(command)):
        return ("BLOCKED: 'rm -r' on a system/home-root path. Scope recursive deletions "
                "to project-relative paths, deep project subdirectories, or /tmp/.")
    return None


def check_zone(command: str, project_dir: Path) -> str | None:
    """Nothing goes in, nothing comes out, and the history does not cite it."""
    if (project_dir / ".references-bootstrap").is_file():
        return None  # the documented escape hatch, for initial population only

    if ZONE_WRITE_RE.search(command):
        return ("BLOCKED: 'study-material/' is read-only third-party material. Capture "
                "findings in 'records/discoveries/blueprints/'. For initial bootstrap, "
                "create '.references-bootstrap' at project root AND cite the source in "
                "CHANGELOG.md; remove the marker when done.")

    # Reading, grepping and listing stay allowed — that is what the zone is FOR.
    # The pipe does not split here: `cat <zone-file> | tee <dest>` is an export.
    for segment in segments(command):
        if not ZONE_RE.search(segment):
            continue
        if (EXPORT_VERB_RE.search(segment) or EXPORT_REDIRECT_RE.search(segment)
                or EXPORT_PIPE_RE.search(segment)):
            return ("BLOCKED: copying content OUT of 'study-material/' is forbidden — "
                    "that is third-party study material and a literal copy carries its "
                    "licence into this project. Read it, learn from it, and write your "
                    "own version; record the finding in 'records/discoveries/blueprints/' "
                    "citing the source.")
    return None


def commit_text(command: str) -> str:
    """The message as written, plus a `-F <file>` body — that is how a long one
    reaches git, and a guard reading only `-m` would miss it entirely."""
    text = command
    found = re.search(r"(-F|--file)\s+(\S+)", command)
    if found:
        candidate = Path(found.group(2))
        if candidate.is_file():
            text += "\n" + candidate.read_text(encoding="utf-8", errors="replace")
    return text


def check_commit_message(command: str) -> str | None:
    if not re.search(r"git\s+commit", command):
        return None
    text = commit_text(command)
    if ZONE_RE.search(text):
        return ("BLOCKED: the commit message cites a path under 'study-material/'. That "
                "zone is third-party study material and must not be referenced in this "
                "repository's public history. Describe the behaviour you implemented, "
                "not the material you studied.")
    if re.search(r"co-authored-by", text, re.IGNORECASE):
        return ("BLOCKED: 'Co-Authored-By:' trailers are forbidden on this project's "
                "commits (user policy). Remove the trailer from the commit message body.")
    return None


def check_package_install(command: str, cwd: Path) -> str | None:
    if PKG_INSTALL_RE.search(command) and ZONE_RE.search(str(cwd) + "/"):
        return ("BLOCKED: never install dependencies inside study-material/. "
                "Those are read-only third-party trees.")
    return None


#: Commands that put a file's CONTENT somewhere the session can see it. Not
#: exhaustive and cannot be — `python3 -c "print(open('.env').read())"` is not
#: here and will not be caught. See `check_credential_read`.
_READERS_RE = re.compile(
    r"(^|\s|\||;|&&|\()\s*(sudo\s+)?"
    r"(cat|bat|less|more|head|tail|nl|strings|xxd|od|hexdump|base64|"
    r"grep|rg|ag|awk|sed|cut|sort|uniq|tee|cp|scp|rsync|curl|wget)(\s|$)")


def _credential_globs(project_dir: Path) -> list[str]:
    """The path shapes `settings.json` already refuses to Read.

    Read from that file rather than restated here, and the reason is the defect
    this whole guard exists for. `permissions.deny` refused `Read` on these paths
    and nothing else, so `cat` returned them and `Edit` rewrote them. A second
    list of the same shapes, kept by hand in Python beside the JSON one, is how
    that gap reopens: on 2026-09-02 this kit found FOUR separate cases of a rule
    living in one file and missing from another, and stopped adding new ones.
    """
    for candidate in (project_dir / ".claude" / "settings.json",
                      project_dir / "settings.json",
                      Path(__file__).resolve().parent.parent / "settings.json"):
        try:
            rules = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        deny = rules.get("permissions", {}).get("deny", [])
        globs = [r[5:-1] for r in deny if r.startswith("Read(") and r.endswith(")")]
        if globs:
            return globs
    return []


def check_credential_read(command: str, project_dir: Path) -> str | None:
    """Refuse a shell command that reads a path `settings.json` denies to `Read`.

    WHAT THIS IS AND IS NOT
    -----------------------
    The deny list refused ONE tool. `permissions.allow` carries `Bash(*)`, so
    `cat .env` returned the file that `Read(.env)` had just refused, and `Edit`
    was not denied at all — an agent could not read a credential file and could
    rewrite it blind. Measured in a consumer on 2026-09-02: 157 versioned paths
    refused to `Read`, 79 of them source code, and not one refusal a session
    could not step around in a single command.

    This closes the common door. It does NOT make the deny list a sandbox, and
    saying otherwise would make it the thing it replaces — a guard that reads as
    protection and is not. A determined session reaches the same bytes through
    `python3 -c`, a heredoc, an editor, or a path this pattern does not spell.
    What it stops is the accident and the habit, which is most of what happens.
    """
    globs = _credential_globs(project_dir)
    if not globs or not _READERS_RE.search(command):
        return None

    for token in re.findall(r"[\w./~@+-]+", command):
        name = token.rsplit("/", 1)[-1]
        for glob in globs:
            bare = glob.removeprefix("**/")
            if fnmatch.fnmatch(token, glob) or fnmatch.fnmatch(token, bare) \
                    or fnmatch.fnmatch(name, bare):
                return (
                    f"`{token}` matches `{glob}`, which `settings.json` refuses to "
                    f"Read. A shell command that reads it returns the same bytes "
                    f"the deny rule exists to withhold.\n\n"
                    f"If the file genuinely holds no credential, the glob is wrong "
                    f"and belongs narrowed in `settings.json` — not stepped around "
                    f"here. If it does hold one, nothing in this session needs it.")
    return None


def main() -> None:
    c = create_context(PreToolUseContext)
    command = c.tool_input.get("command", "")
    if not command.strip():
        return

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())

    # Cheap pre-filters. Each MUST name what its guards actually match: while the
    # zone filter tested for `records/` and the guards had moved to
    # `study-material/`, every zone guard was unreachable and its silence read
    # as a clean pass.
    for reason in (
        check_git(command) if "git" in command else None,
        check_rm(command) if "rm" in command else None,
        check_zone(command, project_dir) if "study-material/" in command else None,
        check_commit_message(command) if "git" in command else None,
        check_package_install(command, Path.cwd()),
        check_credential_read(command, project_dir),
    ):
        if reason:
            c.output.exit_block(reason)


if __name__ == "__main__":
    main()

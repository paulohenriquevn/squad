#!/usr/bin/env python3
"""PreToolUse — refuse Bash commands that break a rule nobody gets to break once.

Everything here guards an action whose cost is asymmetric: `git checkout` loses
uncommitted work, a force-push rewrites what others pulled, a commit on the trunk
skips every gate between it and a release, `git stash` in one of several
worktrees pops another worktree's entry, `rm -rf /home` needs no explanation.
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

# The one owner of every data-root literal. A local copy is what produced six lists in
# four different orders, and `check_write_containment.py` refuses a second one.
import sys as _sys_bootstrap
from pathlib import Path as _Path_bootstrap

from squad import PreToolUseContext, create_context
from squad.boundaries import violation
from squad.layout import resolve

for _up in _Path_bootstrap(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _sys_bootstrap.path.insert(0, str(_up))
        break
from squad.paths import DATA_DIRNAME, RECORDS  # noqa: E402

# ── the read-only zone (rules/reference-provenance.md § 1) ────────────────────
ZONE = r"(\./)?(\.claude/)?study-material/"
ZONE_RE = re.compile(ZONE)

# ── git ───────────────────────────────────────────────────────────────────────
_GIT_GLOBALS = re.compile(
    r"(^|[^\w.])git\s+(--git-dir=\S+|--work-tree=\S+|-[cC]\s+\S+|--paginate|-p)\s+")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
#: A NEWLINE separates two commands exactly as `;` does, and the Bash tool is
#: handed multi-line blocks routinely. Leaving it out kept every such block as a
#: single segment, which is where the recursive-delete false positive survived its
#: first fix: `rm -f x_test.go\ngrep -rn foo cmd` is two commands, and judging it
#: as one assembled an `rm -r` out of parts belonging to neither.
_SEGMENTS = re.compile(r"\|\||&&|;|\n")
_SEGMENTS_WITH_PIPE = re.compile(r"\|\||&&|;|\n|\|")

FORCE_TOKEN_RE = re.compile(r"(--force(\s|$)|(^|\s)-[a-z]*f(\s|$)|\s\+[^\s-]\S*)")

#: Everything that writes to or consumes the stack. `list` and `show` only read
#: it, and refusing those would teach an agent the guard is noise.
STASH_MUTATION_RE = re.compile(r"git\s+stash\b(?!\s+(list|show)\b)")
DASH_C_RE = re.compile(r"git\s+-C\s+(\S+)")

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

#: The two branches the flow depends on existing. `workspace` is a single
#: permanent branch and `develop` is where promotion lands; deleting either
#: discards work that was never promoted and leaves the next `git switch` to
#: recreate the name with none of the history every rule refers to.
BRANCH_DELETE_RE = re.compile(r"git\s+branch\s+(-\S*\s+)*-\S*[dD]\S*\s+"
                              r"(?P<name>(origin/)?(workspace|develop))(\s|$)")

#: A command that writes to a file, and the tokens it writes to. `>`/`>>` name
#: their target directly; the verbs take theirs as operands. Not exhaustive and
#: cannot be — the same honest limit `check_credential_read` states.
WRITE_VERB_RE = re.compile(
    r"(^|\s|;|&&|\|\||\||\()\s*(sudo\s+)?"
    r"(sed\s+-i\S*|rm|mv|cp|tee|truncate|chmod|chown|install|dd|touch)(\s|$)")
REDIRECT_TARGET_RE = re.compile(r">{1,2}\s*(?P<target>[^\s&>|;]+)")

PKG_INSTALL_RE = re.compile(
    r"(pip|poetry|uv|npm|pnpm|yarn|cargo|go\s+(get|mod))\s+(install|add|tidy|download)")


#: Seconds per git call, against the 10s `hooks.json` gives this hook. Three run
#: in sequence on the worst path — the worktree listing, the current branch and
#: the remote's default. At the old 5s each that path could not fit, and a
#: PreToolUse hook killed at its limit blocks nothing while looking like it ran.
#: Local git answers these in milliseconds; the budget is for a cold cache.
_GIT_TIMEOUT = 2


def _git_prefix(command: str) -> list[str]:
    """The `-C <path>` the command itself carries, as arguments for `git`.

    The repository a command acts on is the one it NAMES, not the one the session
    happens to sit in. `working_trees()` has honoured this since kit#31; the
    branch guards did not, so `strip_git_globals` correctly saw `git commit` and
    then asked the wrong repository which branch it was on. That read a trunk as
    `workspace` and `workspace` as a trunk, one release apart.
    """
    where = DASH_C_RE.search(command)
    return ["-C", where.group(1).strip("'\"")] if where else []


def _git_out(*args: str) -> str:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True,  # noqa: PLW1510
                              timeout=_GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def working_trees(command: str) -> int:
    """How many working trees share this repository's ONE stash stack.

    `git worktree` gives each tree its own index, HEAD and checkout, and that is
    what makes the omission expensive: the stash is not among them. `refs/stash`
    lives in the common git dir, so every tree pushes and pops the same stack and
    `git stash pop` returns the top entry no matter which tree pushed it.

    The command's own `-C <path>` is honoured before the cwd, because the fleet's
    briefs drive git that way (`git -C {repo} worktree add …`) and a guard that
    only ever asks the current directory misses the form the kit itself uses.

    WHAT THIS DOES NOT COVER
    ------------------------
    A listing that cannot be read counts as zero trees and the stash is allowed —
    outside a repository there is no stack to share, and refusing there would
    block a command that cannot do the damage. The same fail-open applies if git
    itself is unavailable. And like every guard in this file it matches the
    command as written: `bash -c 'git stash'`, an alias, or a script that stashes
    on the agent's behalf reaches the stack unread. It closes the accident and the
    habit, which is what happened on 2026-09-04; it is not a sandbox.
    """
    listing = _git_out(*_git_prefix(command), "worktree", "list", "--porcelain")
    return sum(1 for line in listing.splitlines() if line.startswith("worktree "))


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


def trunks(prefix: list[str] | None = None) -> list[str]:
    """`main`, `master`, and whatever the remote actually calls its default.

    F12: a project whose trunk is `trunk` or `release` installed this kit, read
    Rule 4, and got no protection because the rule named `main`. The remote's
    HEAD is the honest source; `workspace` and `develop` are excluded because
    they have their own rules and are never the trunk.
    """
    names = ["main", "master"]
    default = _git_out(*(prefix or []), "symbolic-ref", "--short",
                       "refs/remotes/origin/HEAD")
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
    deleting = BRANCH_DELETE_RE.search(_QUOTED.sub("", cmd))
    if deleting:
        return (f"BLOCKED: '{deleting.group('name')}' is a permanent branch of the "
                f"flow (git-safety.md § 1) and is never deleted. Deleting it "
                f"discards whatever was not promoted, and the next 'git switch' "
                f"recreates the name with none of the history the rules refer to. "
                f"Delete the disposable branch instead, or leave it.")
    for segment in segments(cmd, with_pipe=True):
        if re.search(r"git\s+push(\s|$)", segment) and FORCE_TOKEN_RE.search(segment):
            return ("BLOCKED: force push is forbidden. Use --force-with-lease only "
                    "when explicitly authorized.")
    if re.search(r"git\s+reset\s+--hard", cmd):
        return ("BLOCKED: 'git reset --hard' is forbidden. Use 'git reset --soft', or "
                "commit on a branch, instead.")

    # Quoted text is not a branch name: a commit MESSAGE saying "main" must not
    # read as switching to it — nor one that merely mentions the stash.
    unquoted = _QUOTED.sub("", cmd)

    # The stash is the one thing a worktree does NOT isolate, and the cost is
    # asymmetric in the way this whole hook is for: measured 2026-09-04 (kit#31),
    # two agents in separate worktrees stashed concurrently and each popped the
    # other's entry, swapping uncommitted work. With a single working tree there
    # is nobody to swap with and the stash stays allowed.
    if STASH_MUTATION_RE.search(unquoted) and working_trees(command) > 1:
        return ("BLOCKED: this repository has more than one working tree, and they "
                "SHARE one stash stack — 'refs/stash' lives in the common git dir, "
                "so 'git stash pop' returns the top entry whichever tree pushed it. "
                "Two agents swapped their uncommitted work this way (kit#31). To "
                "reach a clean tree: copy the files aside with 'cp', or commit them "
                "on your own branch, then 'git restore'.")

    prefix = _git_prefix(command)
    branch = _git_out(*prefix, "branch", "--show-current") or "unknown"
    names = trunks(prefix)

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


CD_RE = re.compile(r"(^|\s)cd\s+(?P<path>[^\s;&|]+)")


def _dangerous_cwd(segment: str) -> bool:
    """Did this segment move the shell onto a system or home root?

    A `cd` carries its path to every segment after it, so `cd /etc && rm -rf *`
    is the deletion `rm -rf /etc/*` spells out. Judging segments in isolation is
    right — it is what stopped an `rm` from one command being read against a path
    from another — but the isolation has to end where the shell's own state
    crosses the boundary.
    """
    found = CD_RE.search(segment)
    return bool(found and DANGEROUS_PATH_RE.search(found.group("path").rstrip("/") + " "))


def check_rm(command: str) -> str | None:
    """The three conditions have to hold in the SAME segment.

    Searching each of them over the whole line and ANDing the results assembles a
    deletion nobody typed: the `rm` from one command, the `-r` from a `grep -rn`,
    the root path from a third. `rm nota.txt && grep -rn padrao /etc/hosts` was
    refused as "'rm -r' on a system/home-root path" with no `rm -r` and no root
    path anywhere in it.

    This regressed once before. A consumer measured it, fixed it in the bash
    hook, and the Python rewrite reintroduced it — which nobody caught, because
    that consumer's own guard test sent an incomplete payload and every row of it
    was measuring the fail-closed path rather than this function.

    `segments()` already states the rule in its docstring, and `check_zone` was
    already the only caller honouring it: *"judged per segment, so an unrelated
    `cp` in a compound is not blamed on a zone path that appears elsewhere in the
    same line"*. Blocking a real `rm -rf /etc` inside a compound still works,
    because there all three conditions live in one segment.
    """
    at_risk = False
    for segment in segments(command):
        if RM_INVOCATION_RE.search(segment) and RM_RECURSIVE_RE.search(segment) \
                and (DANGEROUS_PATH_RE.search(segment) or at_risk):
            return ("BLOCKED: 'rm -r' on a system/home-root path. Scope recursive deletions "
                    "to project-relative paths, deep project subdirectories, or /tmp/.")
        # Evaluated after the `rm`, because a `cd` in the SAME segment runs after
        # it too — `rm -rf * ; cd /etc` deletes the current directory's contents.
        if _dangerous_cwd(segment):
            at_risk = True
    return None


def check_zone(command: str, project_dir: Path) -> str | None:
    """Nothing goes in, nothing comes out, and the history does not cite it."""
    if (project_dir / ".references-bootstrap").is_file():
        return None  # the documented escape hatch, for initial population only

    if ZONE_WRITE_RE.search(command):
        return ("BLOCKED: 'study-material/' is read-only third-party material. Capture "
                f"findings in '{DATA_DIRNAME}/{RECORDS}/discoveries/blueprints/'. For "
                "initial bootstrap, "
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
                    f"own version; record the finding in "
                f"'{DATA_DIRNAME}/{RECORDS}/discoveries/blueprints/' "
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


def check_kit_boundary(command: str, project_dir: Path) -> str | None:
    """Refuse a shell write into the installed kit — the same line `Edit` holds.

    `boundary-check` guards `Edit`/`Write` and this guards the shell; both ask
    `squad.boundaries` where the line is, so the two halves cannot drift apart.
    While only the first existed, `sed -i` reached the file the other had just
    refused, and the reason the boundary exists — a fix inside an installed kit
    protects one machine and the next install erases it — says nothing about
    which tool did the writing.

    Reading stays allowed everywhere: an agent that cannot read its own contracts
    cannot follow them.
    """
    # `warn` stays on. `squad.layout` says why in its own docstring — *"a hook
    # that silences the broken-install warning reproduces the exact failure the
    # warning was added for"* — and a broken install is precisely when this
    # guard is not running while the session looks protected. The repetition is
    # the point: it only fires when something is wrong.
    layout = resolve(project_dir)
    if layout is None or layout.kind == "standalone":
        return None

    for segment in segments(command, with_pipe=True):
        targets: list[str] = []
        if WRITE_VERB_RE.search(segment):
            targets += re.findall(r"(?<!\S)(/[^\s;&|>]+|\.{1,2}/[^\s;&|>]+)", segment)
        targets += [m.group("target") for m in REDIRECT_TARGET_RE.finditer(segment)]
        for token in targets:
            reason = violation(Path(token.strip("'\"")), layout)
            if reason:
                return reason
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


def _names_a_path(token: str, project_dir: Path) -> bool:
    """Is this token a FILE the command opens, or a WORD it searches for?

    Every token used to be compared against the deny globs, so the term being
    searched for was read as the file being opened: `grep -rn credentials src/`
    was refused because `credentials` matches `**/credentials`. The globs with no
    separator and no suffix — `credentials`, `kubeconfig`, `id_rsa` — are exactly
    the shape a search term has, and looking for where credentials are USED is
    one of the commonest reviews there is. The refusal then sent the reader to
    narrow a glob that was correct.

    A separator, a suffix or a leading dot means path, and stays refused:
    `secret.yaml` as a search term is collateral this gate accepts, because the
    doubt is real and the cost of guessing wrong runs one way. The leading dot is
    not decoration — `Path(".env").suffix` is empty, so a dotfile reads as a bare
    word and the commonest credential file of all would walk straight through.
    A bare word is prose unless a file by that name is actually there.
    """
    if "/" in token or Path(token).suffix or token.startswith(("~", ".")):
        return True
    try:
        return (project_dir / token).exists()
    except OSError:
        return False


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
        if not _names_a_path(token, project_dir):
            continue
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
    #
    # Deferred rather than evaluated into a tuple, so the first refusal is the
    # last work done. Three of these shell out to git and one resolves the
    # layout from disk; a tuple ran all of them for a command the first guard
    # had already refused, inside the 10s this hook gets before the runtime
    # kills it — and a PreToolUse hook killed at its limit blocks nothing.
    checks = (
        lambda: check_git(command) if "git" in command else None,
        lambda: check_rm(command) if "rm" in command else None,
        lambda: check_zone(command, project_dir) if "study-material/" in command else None,
        lambda: check_commit_message(command) if "git" in command else None,
        lambda: check_package_install(command, Path.cwd()),
        lambda: check_credential_read(command, project_dir),
        lambda: check_kit_boundary(command, project_dir),
    )
    for check in checks:
        reason = check()
        if reason:
            c.output.exit_block(reason)


if __name__ == "__main__":
    main()

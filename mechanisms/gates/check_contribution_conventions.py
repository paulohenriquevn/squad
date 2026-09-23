#!/usr/bin/env python3
"""Do the commits follow the conventions this project declares?

    python3 mechanisms/gates/check_contribution_conventions.py
    python3 mechanisms/gates/check_contribution_conventions.py --range origin/develop..HEAD --json
    python3 mechanisms/gates/check_contribution_conventions.py --message-file .git/COMMIT_EDITMSG

## Why the conventions needed a mechanism

A convention nobody can check is a preference, and a preference drifts from the
repository within a release. Measured here on 2026-09-11: `CONTRIBUTING.md` instructed
contributors to end commit messages with a co-authorship trailer while **zero of the
last 200 commits carried one**. The document and the practice had disagreed long enough
that nobody noticed — and an open-source consumer reading the document would have
followed it.

## What it reads, and in which order

`rules/contribution-overrides.txt` first, then the kit's defaults for anything the
project did not declare. The overrides file ships empty and a reinstall preserves it,
which is why customisation lives there rather than in the contract.

## The two things an override cannot reach

  - THE CO-AUTHORSHIP REFUSAL. The author of a commit is one person; a trailer
    crediting a tool misattributes the accountability authorship carries.
  - THE SECRETS RULE for issues.

An overrides file attempting either is REFUSED rather than ignored, because a
silently-dropped override reads as an accepted one.

## What it does NOT check

  - WHETHER THE BODY IS ANY GOOD. It checks that `feat` and `fix` have one. A body
    restating the subject in more words passes, and that is the convention's most
    valuable rule — stated in the contract precisely because no mechanism holds it.
  - WHETHER A SCOPE IS THE RIGHT ONE. Only that it is in the declared set when a set
    is declared.
  - ISSUES AND PULL REQUESTS. They live on a forge this does not call. The conventions
    for them are in the contract; only commits are computed here.

Exit codes:
  0  every commit in range follows the conventions
  1  at least one does not
  2  the range could not be read, or the overrides file does not parse — nothing checked
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

#: The kit's defaults, measured from this repository's own history rather than copied
#: from a standard: fix 61 of the last 120, feat 24, test 8, docs 7.
DEFAULT_TYPES = ("fix", "feat", "docs", "test", "refactor", "chore",
                 "perf", "build", "ci", "revert", "style", "merge")
#: 85, not 72. The number is DERIVED from this repository's own history rather than
#: copied from the convention every style guide repeats. Measured over 300 subjects
#: on 2026-09-11: median 71, p75 78, **p90 85**, p95 90, max 124.
#:
#:     limit 50  → 93% of history violates
#:     limit 72  → 44%
#:     limit 85  →  5%   ← the tail, which is what a limit is for
#:
#: A check that fails 44% of what a repository has always done is not a convention; it
#: is a preference nobody follows, and it teaches people to ignore the checker. This is
#: the same calibration `quality-init` performs — thresholds from the project's real p90,
#: never generic defaults — applied to the kit's own default.
DEFAULT_SUBJECT_MAX = 85
DEFAULT_BODY_REQUIRED = ("feat", "fix")

#: Refused in any spelling, for any second party. `re.I` and the flexible separator
#: catch `Co-authored-by`, `CO-AUTHORED_BY`, and the spacing variants a template emits.
COAUTHOR_RE = re.compile(r"^\s*co[-_ ]?authored[-_ ]?by\s*:", re.IGNORECASE | re.MULTILINE)

#: `<type>(<scope>): <subject>` — scope optional, `!` allowed for a breaking change.
#:
#: A scope may name MORE THAN ONE AREA, comma-separated and no space: `fix(gates,board):`.
#: The single-segment pattern refused those as `header_shape` — not for the scope's
#: content but for the comma — which left a change genuinely touching two areas with
#: three bad options: name one and be incomplete, invent a portmanteau nobody greps for,
#: or drop the scope. All three lose what the field exists to carry. Each segment is
#: still lowercase kebab-case, so the rule about a scope did not loosen; there may now
#: be more than one of them.
#: A SEGMENT MAY ALSO NAME A PATH. The argument above is the whole of this one: measured
#: 2026-09-23 on a consumer, five commits scoped `infra/tests` — a directory and its tests
#: — were refused as `header_shape`, and reachable by no override, because `commit_scopes`
#: is consulted only after this pattern matches. The three options left were the same
#: three: name `infra` and be incomplete, write `infra-tests` and invent a portmanteau
#: that stops matching the path it names, or drop the scope.
#:
#: The segment rule did NOT loosen. Each part is still lowercase kebab-case; what changed
#: is that a scope may be several of them separated by `/`, the way the comma made it
#: several separated by `,`. `infra//tests`, `infra/` and `Infra/tests` still fail.
_SCOPE_PART = r"[a-z0-9][a-z0-9-]*"
_SCOPE_SEGMENT = rf"{_SCOPE_PART}(?:/{_SCOPE_PART})*"
HEADER_RE = re.compile(
    rf"^(?P<type>[a-z]+)"
    rf"(?:\((?P<scope>{_SCOPE_SEGMENT}(?:,{_SCOPE_SEGMENT})*)\))?"
    rf"(?P<bang>!)?: (?P<subject>.+)$")

#: Overrides a project may set. An unknown key is refused: a typo that is ignored is a
#: convention the project thinks it declared and did not.
#: `branch_trunk` was here and is not: this checker's subject is COMMITS — header shape,
#: subject length, body — and it never read a branch name at all. Accepting the key made
#: `rules/contribution-overrides.txt` document a setting a project could write, have
#: parsed, have validated as known, and have applied to nothing. Which branch is the trunk
#: matters to `hooks/validate-command.py`, which refuses work on it; that is where such a
#: key belongs if it is ever wanted.
KNOWN_KEYS = {"commit_types", "commit_scopes", "subject_max", "body_required"}
#: Keys that would reach a rule the contract says cannot be overridden.
FORBIDDEN_KEYS = {"allow_coauthor", "coauthor", "allow_secrets", "secrets"}


@dataclass
class Conventions:
    types: tuple[str, ...] = DEFAULT_TYPES
    scopes: tuple[str, ...] = ()
    subject_max: int = DEFAULT_SUBJECT_MAX
    body_required: tuple[str, ...] = DEFAULT_BODY_REQUIRED
    source: str = "kit defaults"


@dataclass
class Finding:
    sha: str
    code: str
    detail: str


@dataclass
class Report:
    conventions: Conventions = field(default_factory=Conventions)
    commits_checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    unmeasured_because: str = ""
    #: Shas in the checked range that are already reachable from the upstream. A finding
    #: on one of these cannot be fixed by the author who is pushing: amending it would
    #: rewrite shared history. Empty when there is no upstream to compare against.
    already_pushed: set[str] = field(default_factory=set)
    #: The range as RESOLVED, so a report never claims to have graded a range the caller
    #: only asked for.
    resolved_range: str = ""


def load_conventions(overrides: Path) -> Conventions:
    """The project's declarations, then the kit's defaults for whatever it did not set."""
    conv = Conventions()
    if not overrides.is_file():
        return conv

    declared: dict[str, str] = {}
    for lineno, raw in enumerate(overrides.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" not in line:
            raise ValueError(f"{overrides}:{lineno}: expected `key = value`, got `{line}`")
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key in FORBIDDEN_KEYS:
            raise ValueError(
                f"{overrides}:{lineno}: `{key}` would override a rule the contract says "
                "cannot be overridden. The co-authorship refusal and the secrets rule "
                "are not project decisions — refused rather than ignored, because a "
                "silently-dropped override reads as an accepted one")
        if key not in KNOWN_KEYS:
            raise ValueError(
                f"{overrides}:{lineno}: unknown key `{key}`. Known: "
                f"{', '.join(sorted(KNOWN_KEYS))}. A typo that is ignored is a "
                "convention the project thinks it declared and did not")
        declared[key] = value

    if "commit_types" in declared:
        conv.types = tuple(t.strip() for t in declared["commit_types"].split(",") if t.strip())
    if "commit_scopes" in declared:
        conv.scopes = tuple(s.strip() for s in declared["commit_scopes"].split(",") if s.strip())
    if "subject_max" in declared:
        conv.subject_max = int(declared["subject_max"])
    if "body_required" in declared:
        conv.body_required = tuple(t.strip() for t in declared["body_required"].split(",") if t.strip())
    if declared:
        conv.source = f"{overrides} ({len(declared)} override(s))"
    return conv


def check_message(sha: str, message: str, conv: Conventions) -> list[Finding]:
    out: list[Finding] = []
    lines = message.splitlines()
    header = lines[0] if lines else ""
    body = "\n".join(lines[1:]).strip()

    #: Checked on the WHOLE message, before anything else. It is the one rule no
    #: override reaches and the one a template adds without anyone deciding to.
    if COAUTHOR_RE.search(message):
        out.append(Finding(sha, "coauthor_trailer",
                           "carries a co-authorship trailer. The author of a commit is "
                           "one person; a trailer crediting a tool misattributes the "
                           "accountability authorship carries. No override reaches this"))

    #: A merge commit's header is generated by git and is not the author's to shape.
    if header.startswith("Merge "):
        return out

    match = HEADER_RE.match(header)
    if match is None:
        out.append(Finding(sha, "header_shape",
                           f"`{header[:60]}` is not `<type>(<scope>): <subject>`"))
        return out

    ctype = match.group("type")
    scope = match.group("scope")
    subject = match.group("subject")

    if ctype not in conv.types:
        out.append(Finding(sha, "unknown_type",
                           f"`{ctype}` is not a declared type. Declared: "
                           f"{', '.join(conv.types)}. Add it to "
                           "`rules/contribution-overrides.txt` if this project uses it"))
    # Segment by segment, because a scope may name two areas. Comparing the whole
    # string would make a declared scope list stop applying the moment a commit named
    # two of them — the check would pass `gates,ghost` while refusing `ghost`.
    undeclared = [s for s in (scope or "").split(",") if s and s not in conv.scopes]
    if conv.scopes and undeclared:
        out.append(Finding(sha, "unknown_scope",
                           f"`{', '.join(undeclared)}` is not in the declared scopes: "
                           f"{', '.join(conv.scopes)}"))
    if len(subject) > conv.subject_max:
        out.append(Finding(sha, "subject_too_long",
                           f"{len(subject)} characters; the declared limit is {conv.subject_max}"))
    if subject.endswith("."):
        out.append(Finding(sha, "subject_trailing_period",
                           "ends with a period. The subject is a title, not a sentence"))
    if ctype in conv.body_required and not body:
        out.append(Finding(sha, "body_missing",
                           f"`{ctype}` requires a body. The subject says WHAT changed; "
                           "the body says what was true that made it necessary, which is "
                           "the only durable record of why the code is the way it is"))
    return out


#: The range a PRE-PUSH caller means: what this push would introduce, and nothing else.
#:
#: The default `-40` grades the last forty commits, which is right for a standalone
#: audit — there, grading history IS the question. It is wrong for a hook, and the
#: wrongness is a deadlock rather than a nuisance. Measured on a consumer 2026-09-16:
#: four violations in the window, THREE of them already on `origin/workspace`. No amend
#: reaches a pushed commit and only a force-push would; the two nearest left the window
#: in eleven and thirteen commits, which could not happen, because the gate refused the
#: commits that would have moved it. Nine verified commits sat behind that wall.
#:
#: Every part was individually right — the gate reported a true fact, the hook correctly
#: refused, and the floor forbids switching either off. What was wrong is that two
#: callers shared one range. A convention check that grades history it cannot change is
#: grading the wrong thing; graded over the introduced range, every violation is fixable
#: by the author who is pushing, which is what makes refusing it legitimate.
INTRODUCED = "@introduced"


def _resolve_range(repo: Path, rev_range: str) -> str:
    """`@introduced` -> `<upstream>..HEAD`. Anything else is returned unchanged."""
    if rev_range != INTRODUCED:
        return rev_range
    out = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=repo, capture_output=True, text=True, check=False)
    upstream = out.stdout.strip()
    if out.returncode != 0 or not upstream:
        # A branch with no upstream introduces everything it has. Grading its whole
        # history is the honest reading, and it is also fixable: nothing is pushed.
        return "HEAD"
    return f"{upstream}..HEAD"


def _pushed_shas(repo: Path) -> set[str]:
    """Short shas reachable from the upstream — the commits an amend cannot reach."""
    out = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=repo, capture_output=True, text=True, check=False)
    upstream = out.stdout.strip()
    if out.returncode != 0 or not upstream:
        return set()
    log = subprocess.run(["git", "log", "--format=%H", upstream],
                         cwd=repo, capture_output=True, text=True, check=False)
    if log.returncode != 0:
        return set()
    return {line[:9] for line in log.stdout.split() if line}


def _commits(repo: Path, rev_range: str) -> list[tuple[str, str]]:
    sep = "\x1e"
    out = subprocess.run(
        ["git", "log", f"--format=%H%x1f%B{sep}", rev_range],
        cwd=repo, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise ValueError(out.stderr.strip() or f"`git log {rev_range}` failed")
    commits = []
    for chunk in out.stdout.split(sep):
        if "\x1f" not in chunk:
            continue
        sha, _, message = chunk.strip().partition("\x1f")
        if sha:
            commits.append((sha[:9], message.strip()))
    return commits


def check(repo: Path, rev_range: str, message_file: Path | None = None) -> Report:
    rep = Report()
    try:
        rep.conventions = load_conventions(repo / "rules" / "contribution-overrides.txt")
    except (ValueError, OSError) as exc:
        rep.unmeasured_because = str(exc)
        return rep

    if message_file is not None:
        try:
            rep.commits_checked = 1
            rep.findings = check_message("(pending)", message_file.read_text(encoding="utf-8"),
                                         rep.conventions)
        except OSError as exc:
            rep.unmeasured_because = f"could not read {message_file}: {exc}"
        return rep

    resolved = _resolve_range(repo, rev_range)
    rep.resolved_range = resolved
    try:
        commits = _commits(repo, resolved)
    except ValueError as exc:
        rep.unmeasured_because = (
            f"{exc}. Nothing was checked, and a range that does not resolve is not a "
            "range where every commit is clean")
        return rep

    rep.commits_checked = len(commits)
    for sha, message in commits:
        rep.findings.extend(check_message(sha, message, rep.conventions))
    pushed = _pushed_shas(repo)
    rep.already_pushed = {sha for sha, _ in commits if sha in pushed}
    return rep


NOT_CHECKED = (
    "whether a body is any GOOD — a body restating the subject passes, and that is the "
    "convention's most valuable rule",
    "whether a scope is the RIGHT one, only that it is declared",
    "issues and pull requests, which live on a forge this does not call",
)


def render(rep: Report) -> str:
    if rep.unmeasured_because:
        return ("contribution conventions\n"
                f"  NOT MEASURED — {rep.unmeasured_because}")

    out = ["contribution conventions",
           f"  conventions from: {rep.conventions.source}",
           f"  checked: {rep.commits_checked} commit(s) over {rep.resolved_range}"]
    if rep.findings:
        out.append("")
        for f in rep.findings:
            # A finding on a pushed commit cannot be amended — only force-pushed over.
            # Printing them identically is what made a deadlock look like a to-do list.
            mark = "  [already pushed]" if f.sha in rep.already_pushed else ""
            out.append(f"  [{f.code}] {f.sha}{mark}")
            out.append(f"      {f.detail}")
    out.append("")
    out.append(f"  {'CLEAN' if not rep.findings else 'VIOLATIONS'} — "
               f"{len(rep.findings)} finding(s) over {rep.commits_checked} commit(s)")

    stuck = sorted({f.sha for f in rep.findings} & rep.already_pushed)
    if stuck:
        out.append("")
        out.append(f"  {len(stuck)} of these sit on commits already reachable from the"
                   f" upstream: {', '.join(stuck)}")
        out.append("  An amend cannot reach them and only a force-push would, so no"
                   " author can clear them by writing a better commit.")
        out.append("  If this ran as a PRE-PUSH gate, re-run it with --introduced:"
                   " grading history that cannot change refuses work for a fact about")
        out.append("  the past, and the only remedy the arithmetic allows is more"
                   " commits — which is what the refusal prevents.")
    out.append("  NOT CHECKED:")
    for line in NOT_CHECKED:
        out.append(f"    · {line}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--root", "--repo", dest="root", type=Path, default=Path("."))
    ap.add_argument("--range", dest="rev_range", default="-40",
                    help="a git range, or -N for the last N commits (default: -40)")
    # Registered AFTER `--range` on purpose: argparse applies a default only when the
    # dest is not already set, so the FIRST registration wins. With this one first its
    # implicit `None` stuck and the default range became None, which crashed inside
    # `git log` with `TypeError: expected str, bytes or os.PathLike object, not NoneType`
    # — a stack trace where the honest answer was "the last forty commits".
    ap.add_argument("--introduced", dest="rev_range", action="store_const",
                    const=INTRODUCED,
                    help="grade only what this push would introduce"
                         " (`<upstream>..HEAD`) — the range a pre-push hook means")
    ap.add_argument("--message-file", type=Path, default=None,
                    help="check one pending message instead of history")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rep = check(args.root.resolve(), args.rev_range, args.message_file)
    if args.json:
        print(json.dumps({**rep.__dict__,
                          "conventions": rep.conventions.__dict__,
                          "findings": [f.__dict__ for f in rep.findings],
                          "not_checked": list(NOT_CHECKED)}, indent=2, default=str))
    else:
        print(render(rep))

    if rep.unmeasured_because:
        return 2
    return 1 if rep.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

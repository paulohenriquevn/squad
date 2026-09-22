r"""A rule's identity, which is not its filename.

WHY THIS EXISTS

The only handle a rule had was its path, and paths move. Measured across this kit:
**1209 citations** of the form `rules/<name>.md`. Measured on one consumer's registry:
33 of 109 backlog items cite a path inside this kit — including items about that
project's own product, such as an Error-boundary defect citing `rules/error-handling.md`.
Of the 6 dead pointers a freshness check found there, **5 were paths that had moved**.

Twice in one session this repository moved a directory and spent the afternoon chasing
its own citations. A consumer cannot chase ours at all: it learns the path is dead when
somebody follows it and finds nothing.

ESLint settled this shape years ago and its docs give the three reasons: portability
across versions, freedom to reorganise internals without breaking consumers, and one
namespace that covers core and plugin rules alike. Ruff, Semgrep and Pylint do the same.
The independent auditor the consumer already runs cites `LCR0101`. This kit was the only
thing in that registry asking to be cited by filename.

WHAT AN ID IS, AND IS NOT

    SQ-ERR-01    stable for the life of the rule, through any rename
    error-handling.md    where it happens to live today

The id never encodes the path, the phase, or the order — encoding any of those makes the
id move when they do, which is the defect with an extra step. It encodes an AREA and a
number, and nothing else.

RETIREMENT KEEPS THE ID. A retired rule stays in the index naming its successor, because
`replaced_by` answers the question a 404 cannot: not "is something wrong" but "where did
this go". An id is never reused — reuse would make an old citation resolve to a rule that
is not the one it meant, which is worse than not resolving at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .paths import rules_dir as _owner_rules_dir

#: `SQ-<AREA>-<NN>`. Upper case so a citation is visibly an id and not a filename; the
#: area is two to four letters so it stays readable; the number is two digits so the
#: index sorts without a natural-sort helper.
ID_RE = re.compile(r"SQ-[A-Z]{2,4}-\d{2}")

#: How a rule declares its id, on its own line near the top of the file. A comment in
#: `.txt`, an HTML comment in `.md` — invisible when rendered, greppable, and needing no
#: frontmatter parser in a repository that has deliberately avoided adding one.
DECLARATION_RE = re.compile(
    r"^(?:#|<!--)\s*rule-id:\s*(SQ-[A-Z]{2,4}-\d{2})\s*(?:-->)?\s*$", re.MULTILINE)

#: A retired rule points at what replaced it, the way ESLint's `meta.replacedBy` does.
REPLACED_RE = re.compile(
    r"^(?:#|<!--)\s*replaced-by:\s*(SQ-[A-Z]{2,4}-\d{2})\s*(?:-->)?\s*$", re.MULTILINE)

RETIRED_RE = re.compile(r"^(?:#|<!--)\s*retired:\s*(\S.*?)\s*(?:-->)?\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Rule:
    id: str
    filename: str
    retired: str | None = None
    replaced_by: str | None = None


def _rules_dir(project_root: Path) -> Path:
    """Where the rule files are, asked of the module that owns the question.

    This rolled the `rules/` vs `.claude/rules/` pair by hand for about an hour, and
    `test_no_module_rolls_the_pair_by_hand_again` refused it — correctly, and in the
    order it declares: nine sites once resolved that pair themselves, six in one order
    and three in the other, so a table edited in one place was invisible to half its
    readers. The fallback below is for a tree with no rules directory at all, where
    `rules_dir` answers None and the caller still needs a path to report as empty.
    """
    return _owner_rules_dir(project_root) or Path(project_root) / "rules"


def catalogue(project_root: Path | str) -> list[Rule]:
    """Every rule that declares an id, in id order.

    A file with no declaration is simply absent: this reads what is there rather than
    inventing an id from a filename, which would put the path back inside the identity.
    """
    found: list[Rule] = []
    for path in sorted(_rules_dir(Path(project_root)).glob("*")):
        if path.suffix not in (".md", ".txt") or path.name == "README.md":
            continue
        try:
            head = path.read_text(encoding="utf-8")[:4000]
        except OSError:
            continue
        declared = DECLARATION_RE.search(head)
        if not declared:
            continue
        retired = RETIRED_RE.search(head)
        replaced = REPLACED_RE.search(head)
        found.append(Rule(
            id=declared.group(1),
            filename=path.name,
            retired=retired.group(1) if retired else None,
            replaced_by=replaced.group(1) if replaced else None,
        ))
    return sorted(found, key=lambda r: r.id)


def resolve(rule_id: str, project_root: Path | str) -> Path | None:
    """The file holding `rule_id` today, or None when nothing claims it.

    None rather than a guess: a citation that cannot be resolved must read as unresolved,
    never as some nearby rule the reader did not mean.
    """
    for rule in catalogue(project_root):
        if rule.id == rule_id:
            return _rules_dir(Path(project_root)) / rule.filename
    return None

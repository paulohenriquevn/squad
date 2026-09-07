"""Two claims in `rules/README.md` that nothing recomputed, and both had rotted.

`pyproject.toml` states the doctrine this file enforces, after a count there said 64
while the tree held 80: *"a number nothing recomputes is a claim that rots."*

1. THE COUNT. The README argues that the injected pointer is the whole interface and
   that "a pointer at fifty-four files is not one". Measured 2026-09-07: `rules/` holds
   52 files. The argument survives the correction — it is the number that did not.

2. THE ADR DESTINATION. `cycle-rule-schema.md § Golden Rule Change Protocol` required,
   as step 1, "An ADR in `records/adrs/`". `records/` is gitignored wholesale
   (`.gitignore:66`), so the protocol governing the kit's most locked contracts sent
   their justification to a directory that never reaches anyone who clones. The
   contradiction was already load-bearing: `plan-confidence-golden-rule.md` extended a
   gate in 2026-08-26 and wrote its reasoning into the golden rule instead, saying so
   in the file — *"the files under `records/adrs/` are gitignored and do not reach
   whoever clones, so the record lives here, in the file that travels."* Somebody
   following the protocol had to break it to be useful.

   The kit's own ADRs live in `docs/ADR/`, which is versioned. A consumer's run-local
   ADRs stay under `records/adrs/`, which is what the allowlist files mean when they
   require one for an exemption — that is their repository and their trail.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_README = _ROOT / "rules" / "README.md"
_SCHEMA = _ROOT / "rules" / "cycle-rule-schema.md"

_NUMBER_WORDS = {
    "forty-eight": 48, "forty-nine": 49, "fifty": 50, "fifty-one": 51, "fifty-two": 52,
    "fifty-three": 53, "fifty-four": 54, "fifty-five": 55, "fifty-six": 56,
}


def _rule_file_count() -> int:
    return len([p for p in (_ROOT / "rules").iterdir() if p.is_file()])


def test_the_pointer_argument_counts_the_files_that_are_there() -> None:
    # Scoped to the sentence making the claim, not the whole file: a document is
    # allowed to quote a number it has since corrected, and the first version of this
    # test failed on exactly that.
    text = _README.read_text(encoding="utf-8-sig")
    claim = re.search(r"a pointer at ([a-z-]+) files is\s*\nnot one", text)
    assert claim, "the pointer argument no longer cites a count — update this test with it"
    word = claim.group(1)
    assert word in _NUMBER_WORDS, f"unrecognised count word {word!r} — extend _NUMBER_WORDS"
    actual = _rule_file_count()
    assert _NUMBER_WORDS[word] == actual, (
        f"rules/README.md claims {word} ({_NUMBER_WORDS[word]}) files, rules/ holds {actual}"
    )


def test_the_golden_rule_protocol_sends_adrs_somewhere_that_travels() -> None:
    """Step 1 must not name a path git ignores — the record has to reach who clones."""
    schema = _SCHEMA.read_text(encoding="utf-8-sig")
    protocol = schema.split("## Golden Rule Change Protocol")[1].split("\n## ")[0]
    # Only the destination step 1 REQUIRES. The step also names `records/adrs/` twice —
    # once as the location it used to name, once as where a consumer's own ADRs go —
    # and both are legitimately gitignored. A sweep over every path in the section
    # failed on those, which is the finding restated as a false positive.
    required = re.search(r"^1\.\s+An ADR in `([^`]+)`", protocol, re.MULTILINE)
    assert required, "step 1 no longer names an ADR destination"
    path = required.group(1)
    ignored = subprocess.run(  # noqa: PLW1510
        ["git", "check-ignore", "-q", f"{path.rstrip('/')}/probe.md"], cwd=_ROOT
    ).returncode == 0
    assert not ignored, (
        f"the Golden Rule Change Protocol requires an ADR in `{path}`, which git "
        "ignores — the justification for changing a LOCKED rule would not reach anyone "
        "who clones"
    )

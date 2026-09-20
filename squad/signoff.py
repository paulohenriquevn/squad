"""Who signed a document, and whether that closes the gate — read one way.

WHY THIS EXISTS
===============
Three gates read the same `<!-- signed-by: … -->` marker and each carried its own
pattern and its own rule about what the captured name means. Measured 2026-09-20:

    score_alignment.py            ([^>]+?)     allowlist: `human` / `human/…`
    score_product_alignment.py    ([^\\s>]+)    denylist of one: `judge/`
    check_design_completeness.py  ([^\\s>]+)    denylist of one: `judge/`

The two spellings disagreed in opposite directions at once. The DESIGN gate returned
`DESIGN_AGREED`, exit 0, for `<!-- signed-by: daedalus-tech-lead -->` — the agent that
draws the diagrams, signing its own work through the gate a person is supposed to hold
— and in the same run refused `<!-- signed-by: human/paulo (approved in session) -->`,
because a pattern that stops at the first space could not see the route and captured
nothing. A gate that accepts the author and rejects the reviewer is worse than no gate.

This module is the one reader. `tests/test_one_signature_reader_for_every_gate.py`
refuses a second.

WHAT IT DOES NOT DECIDE
=======================
Whether a judge MAY sign. That is policy and it differs by level, on purpose:
`alignment-threshold.md § Amended 2026-09-01` lets a judge sign an ITEM's brief because
the judge reads evidence that exists independently of it, and `cycle-brainstorm.md` and
`cycle-design.md` refuse one at product and system level for the same reason read the
other way. This module reports WHO signed and how many boxes carry a mark; each gate
applies its own rule to that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Captures to the closing marker, spaces included, because the ROUTE is part of the
#: provenance: `human/paulo (approved in session)` says more than `human/paulo`, and a
#: pattern stopping at the first space silently drops exactly that.
#:
#: The name must start AND end on a non-space, so the unsigned marker every template
#: ships — `<!-- signed-by: -->` — names nobody rather than a signer called `" "`.
SIGNED_BY_RE = re.compile(r"<!--\s*signed-by:\s*([^>\s](?:[^>]*[^>\s])?)\s*-->")

#: A reviewer-owned checkbox, in the `- [ ] …` / `- [x] …` form every scorer in this
#: kit reads. Both are counted: "nothing is unticked" is also true of a checklist with
#: NO boxes, and a sign-off section whose boxes were DELETED scored as reviewed.
TICKED_RE = re.compile(r"^\s*-\s*\[[xX]\]\s+\S", re.MULTILINE)
UNTICKED_RE = re.compile(r"^\s*-\s*\[\s*\]\s+\S", re.MULTILINE)

#: The prefix a person's signature carries. An ALLOWLIST, and that is the whole gate:
#: refusing the single prefix `judge/` accepts every other name an agent could sign
#: under, which is how `iris-product-designer` aligned a product and
#: `daedalus-tech-lead` agreed a system design.
HUMAN_PREFIX = "human/"


def is_human(signer: str) -> bool:
    """A NAMED human is still a human — `score_alignment.py`'s rule, stated once.

    Provenance must not cost the distinction it exists to protect: treating anything
    other than the bare word `human` as an agent would downgrade a person who recorded
    WHO they are, so the prefix keeps both the route and the meaning.
    """
    return bool(signer) and (signer == "human" or signer.startswith(HUMAN_PREFIX))


@dataclass(frozen=True)
class SignOff:
    """What a sign-off section says, before any gate decides what it is worth."""

    signers: list[str] = field(default_factory=list)
    ticked: int = 0
    unticked: int = 0
    #: True when the document holding the section was not there at all. An absent gate
    #: is not a passed one, and the two are different reports to a reader: one sends
    #: them to create a file, the other to open one they already have.
    absent: bool = False

    @property
    def human_signed(self) -> bool:
        """Every signer is a person. The WEAKEST signer decides, so one human tick
        cannot launder an agent's beside it."""
        return bool(self.signers) and all(is_human(s) for s in self.signers)

    @property
    def non_human_signers(self) -> list[str]:
        """Named rather than merely refused: a person who signed as `paulo` and a judge
        that signed as itself get the same verdict for different reasons, and only one
        of the two is a typo away from passing."""
        return [s for s in self.signers if not is_human(s)]

    @property
    def complete(self) -> bool:
        """A reviewer marked every box, and there was a box to mark."""
        return self.ticked > 0 and self.unticked == 0


ABSENT = SignOff(absent=True)


def read(body: str) -> SignOff:
    """Parse a sign-off section. `read("")` is an empty sheet, not an absent one —
    callers that can tell the difference pass `ABSENT` themselves."""
    return SignOff(signers=SIGNED_BY_RE.findall(body),
                   ticked=len(TICKED_RE.findall(body)),
                   unticked=len(UNTICKED_RE.findall(body)))

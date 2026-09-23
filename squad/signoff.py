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

#: The prefix another SESSION signs under — a second agent that independently measured
#: something about this document. Added 2026-09-22, after three sessions spent a day
#: finding defects in each other's work with no way to record that it had happened: a
#: gate exercised only where its defect cannot occur, a waiver whose reason had never
#: been measured, a status file that outlived the run that wrote it. All of it reached
#: the record as issue comments and nothing else.
#:
#: A peer is NOT a human and never becomes one. What makes the category worth having is
#: the clause it must carry, below.
PEER_PREFIX = "peer/"

#: What the peer VERIFIED, in parentheses after the name, at least four words. A person
#: is accountable by being a person; a judge is named by the contract it ran against. A
#: peer is another agent with no contract binding it to this document, so the measurement
#: beside the name is the entire value of the signature — without it the marker says
#: "somebody else looked", which is a rubber stamp with provenance.
PEER_CLAIM_RE = re.compile(r"\((\s*\S+(?:\s+\S+){3,}\s*)\)\s*$")
MIN_PEER_CLAIM_WORDS = 4


def is_human(signer: str) -> bool:
    """A NAMED human is still a human — `score_alignment.py`'s rule, stated once.

    Provenance must not cost the distinction it exists to protect: treating anything
    other than the bare word `human` as an agent would downgrade a person who recorded
    WHO they are, so the prefix keeps both the route and the meaning.
    """
    return bool(signer) and (signer == "human" or signer.startswith(HUMAN_PREFIX))


def is_peer(signer: str) -> bool:
    """Signed by another session. Says nothing yet about whether the signature QUALIFIES."""
    return bool(signer) and signer.startswith(PEER_PREFIX)


def peer_claim(signer: str) -> str | None:
    """What this peer says it verified, or None when it did not say.

    The clause is read from the END of the marker so a package name or a route with its
    own parentheses earlier in the line cannot be mistaken for it.
    """
    if not is_peer(signer):
        return None
    match = PEER_CLAIM_RE.search(signer.strip())
    return match.group(1).strip() if match else None


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
    def peer_signers(self) -> list[str]:
        """Peer signatures that SAID what they verified. The others are not signatures."""
        return [s for s in self.signers if peer_claim(s) is not None]

    @property
    def unqualified_peers(self) -> list[str]:
        """Named rather than silently dropped: a peer that signed without saying what it
        checked is a correctable mistake, and a reader who sees nothing cannot correct it."""
        return [s for s in self.signers if is_peer(s) and peer_claim(s) is None]

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

#: A box's opening line. The TEXT is deliberately not captured here: a box's text may run
#: over several lines, and a signature marker's natural home is a line of its own once the
#: `(verified: …)` clause is long. `score_alignment.py` kept its own `^…$` reader under
#: `re.MULTILINE` and so captured one line, which made a marker on the next line invisible
#: and fell back to `"human"` — reporting an AGENT's sign-off as a PERSON's (#174). Measured:
#: the same marker, same judge, on the box line gives `judge/alignment-judge`; one line down
#: it gave `human`.
_BOX_OPEN_RE = re.compile(r"^(?P<indent>[ \t]*)-\s*\[(?P<mark>[ xX])\]\s*(?P<head>.*)$")


@dataclass(frozen=True)
class Box:
    """One reviewer checkbox, with every line of its text and the signer it names."""

    mark: str
    text: str
    signer: str | None

    @property
    def ticked(self) -> bool:
        return self.mark in ("x", "X")


def boxes(body: str) -> tuple[Box, ...]:
    """Every checkbox in `body`, each carrying its CONTINUATION LINES.

    A continuation is any non-blank line that does not open a box and is not a heading. That
    is looser than markdown's own list rules on purpose: this reads a reviewer's sign-off,
    where the failure to avoid is losing a marker somebody wrote, and a line wrongly attached
    to the box above can only ever ATTRIBUTE a signature that is present — never invent one,
    because `SIGNED_BY_RE` has to match for anything to be attributed at all.

    A heading closes the section: a marker under `## Next thing` belongs to no box here.
    """
    found: list[Box] = []
    pending: list[str] | None = None
    mark = ""
    for line in body.splitlines():
        opening = _BOX_OPEN_RE.match(line)
        if opening:
            if pending is not None:
                found.append(_seal(mark, pending))
            mark, pending = opening.group("mark"), [opening.group("head")]
            continue
        if pending is None:
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            found.append(_seal(mark, pending))
            pending = None
            continue
        pending.append(line.strip())
    if pending is not None:
        found.append(_seal(mark, pending))
    return tuple(found)


def _seal(mark: str, lines: list[str]) -> Box:
    text = "\n".join(lines).strip()
    match = SIGNED_BY_RE.search(text)
    return Box(mark=mark, text=text, signer=match.group(1) if match else None)


@dataclass(frozen=True)
class Attribution:
    """Who signed a sign-off section, and how much of that was ASSUMED.

    `signed_by` follows the weakest-wins rule: any non-human signer in the set makes the whole
    set that signer's, because a mixed set is only as trustworthy as its weakest signature.

    `unattributed` is the count of ticks carrying no marker. Those resolve to `"human"` by
    contract — a person editing the file by hand ticks without writing one, and that default
    is documented rather than accidental. The count exists because the default is an
    ASSUMPTION, and a mechanism that assumes must not assume silently: a report saying
    "signed by human" over four bare ticks looks identical to one over four signed ticks.
    """

    pending: tuple[str, ...] = ()
    box_count: int = 0
    signed_by: str | None = None
    unattributed: int = 0


def attribute(body: str) -> Attribution:
    """The one reader for `(pending, box_count, signed_by, unattributed)`."""
    parsed = boxes(body)
    pending = tuple(b.text for b in parsed if not b.ticked)
    ticked = [b for b in parsed if b.ticked]
    if not ticked or pending:
        return Attribution(pending, len(parsed), None, sum(1 for b in ticked if not b.signer))

    signers = {b.signer or "human" for b in ticked}
    if len(signers) == 1:
        signed_by = signers.pop()
    else:
        non_human = sorted(s for s in signers if not is_human(s))
        signed_by = non_human[0] if non_human else sorted(signers)[0]
    return Attribution(pending, len(parsed), signed_by,
                       sum(1 for b in ticked if not b.signer))


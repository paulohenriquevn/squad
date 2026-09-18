#!/usr/bin/env python3
"""Put a person's signature on a document, on the one condition that they read it.

    python3 skills/sign/scripts/sign_document.py --list
    python3 skills/sign/scripts/sign_document.py <path-or-slug>
    python3 skills/sign/scripts/sign_document.py <path-or-slug> --confirm --as paulo

## Why this exists

Four points in the chain stop until a person signs, and until now a person had no
tool for it. `alignment_judge.py` can sign an item's brief — it writes
`<!-- signed-by: judge/alignment-judge -->` and appends a note saying a judge
signature is worth less than a human one. `score_product_alignment.py` states its own
limit plainly: *"It can compute the 90%; it cannot supply the signature, and there is
no flag that makes it."*

Both are right. The consequence was that the ONLY act reserved for a person was also
the only one with no mechanism: open the markdown, find the section, change `[ ]` to
`[x]` in the right place, and add an HTML comment whose syntax lives in a regex inside
someone else's script.

## Why it shows the document before it signs

A tool that makes signing frictionless is a tool that turns a signature into a stamp,
which is the failure the machine's own refusal exists to prevent. So the default run
PRINTS what is being signed and writes nothing; `--confirm` is a second, deliberate
act. There is no `--yes`, and adding one would remove the only thing this skill
contributes over `sed`.

## What it refuses, and why each refusal is not an inconvenience

  - NO SIGN-OFF SECTION. Nothing to sign. The document is not at that stage.
  - ALREADY SIGNED. Re-signing hides who signed first.
  - THE AUTHOR SIGNING THEIR OWN WORK. The same rule that keeps a judge off a brief
    it wrote and an author off their own review panel. Read from git, so it holds
    without anyone declaring it.
  - A THIN OVERRIDE REASON. `--despite-authorship` preserves the fact of self-signing
    rather than dismissing it; under five words is a reason nobody can argue with,
    which is the same as no reason.

    What stood here instead was a claim that this tool refuses a document below the
    score floor. It does not, and never did: `check()` returns exactly these four
    Refusals, and none of them reads a score. The deterministic gate is what refuses
    below the floor — a separate claim, made by a separate process — and `preview()`
    has said so all along. A refusal listed and not implemented is worse than one
    never written down: the reader stops looking for the check that would catch it.

## What it does NOT do

  - It does not decide WHAT to sign. `--list` reports what is waiting; the choice is
    the person's.
  - It does not verify that the document is TRUE. Nothing can. It records who is
    willing to say so, which is the whole point of the signature being a person's.
  - It does not sign on behalf of anyone. `--as` names the signer, and the name goes
    in the file next to what they signed.

Exit codes:
  0  signed, or the preview printed
  1  refused — the reason names which of the four it was
  2  the document could not be read or has no sign-off section; nothing was signed
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        sys.path.insert(0, str(_up))
        break
# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import records_dir, wiki_dir  # noqa: E402 — post-bootstrap import

#: The marker every scorer already reads. `human` / `human/<name>` is a person;
#: anything else is an agent — `score_alignment.signed_by_is_human` owns that rule and
#: this writes what it expects rather than inventing a second spelling.
SIGNED_BY_RE = re.compile(r"<!--\s*signed-by:\s*([^\s>]+)\s*-->")
HUMAN_PREFIX = "human/"

#: Both spellings in the kit. `alignment_judge.py` matches the first; the product
#: documents use the second. A signer should not have to know which.
SECTION_RE = re.compile(r"^(##+\s+(?:Reviewer sign-off|Sign-off)\s*)$",
                        re.MULTILINE | re.IGNORECASE)
#: The `(\s+.*)$` tail matters: capturing only the first character after `]` put
#: the marker INSIDE the sentence — `- [x] T  <!-- signed-by: … -->he problem is`.
UNTICKED_RE = re.compile(r"^(\s*-\s*)\[\s*\](\s+.*)$", re.MULTILINE)
TICKED_RE = re.compile(r"^\s*-\s*\[[xX]\]\s+\S", re.MULTILINE)


@dataclass
class Document:
    path: Path
    body: str
    section_at: int
    unticked: int
    signers: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)

    @property
    def already_signed(self) -> bool:
        return self.unticked == 0 and bool(self.signers)


class Unreadable(OSError):
    """The file could not be read, which is not the same as having nothing to sign.

    `load` returned None for both, and the docstring below claims the value means one
    thing: "None when there is nothing here to sign". A document the tool could not open
    was therefore reported as "not at the stage where a signature applies" — and in
    `--list`, a directory of unreadable documents simply did not appear, so the list of
    what is waiting silently excluded everything the tool could not read.
    """


def load(path: Path) -> Document | None:
    """None when there is nothing here to sign — never an exception, never a guess.

    Raises `Unreadable` when the file itself could not be opened. That is a different
    fact and the caller decides what to do with it.
    """
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise Unreadable(f"{path} could not be read: {exc}") from exc
    match = SECTION_RE.search(body)
    if match is None:
        return None
    tail = body[match.end():]
    return Document(path=path, body=body, section_at=match.end(),
                    unticked=len(UNTICKED_RE.findall(tail)),
                    signers=SIGNED_BY_RE.findall(tail))


def git_authors(path: Path, *, run=subprocess.run) -> list[str]:
    """Who wrote this, from git. Empty when git cannot say — which is not "nobody".

    The author check is the one refusal that cannot be self-declared, so it is read
    from the record rather than from a field the signer fills in. An untracked file
    has no authors and the check cannot fire; `authorship_unknown` says so instead of
    letting absence read as a clean bill.
    """
    try:
        done = run(["git", "log", "--format=%an%n%ae", "--", str(path.name)],
                   cwd=path.parent, capture_output=True, text=True, timeout=30,
                   check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    if done.returncode != 0:
        return []
    return sorted({line.strip().lower() for line in done.stdout.splitlines() if line.strip()})


def is_author(signer: str, authors: list[str]) -> bool:
    """Does this signer appear in the file's authorship? Compared loosely on purpose.

    `paulo`, `Paulo Henrique` and `paulo@example.com` are one person, and a check that
    only matched exactly would be a check that never fires.
    """
    needle = signer.removeprefix(HUMAN_PREFIX).strip().lower()
    if not needle or not authors:
        return False
    return any(needle in author or author.split("@")[0] == needle for author in authors)


@dataclass
class Refusal:
    code: str
    detail: str


def check(doc: Document, signer: str, *, despite: str = "") -> Refusal | None:
    if doc.unticked == 0 and not doc.signers:
        return Refusal("nothing_to_tick",
                       "the sign-off section has no unticked box. Either it was never "
                       "written with one, or the boxes are not in the `- [ ] ...` form "
                       "every scorer in this kit reads")
    if doc.already_signed:
        return Refusal("already_signed",
                       f"signed by {', '.join(doc.signers)}. Re-signing would hide who "
                       "signed first; untick a box to overturn it, which is what the "
                       "judge's own note tells the operator to do")
    if is_author(signer, doc.authors) and not despite.strip():
        return Refusal("author_signing_own_work",
                       f"`{signer}` appears in this file's git authorship "
                       f"({', '.join(doc.authors[:3])}). The same rule keeps a judge off "
                       "a brief it wrote and an author off their own review panel — a "
                       "reviewer who is not the author is the whole content of the check. "
                       "On a project with ONE author this refusal blocks every signature, "
                       "so it can be overridden with `--despite-authorship \"<why>\"` — "
                       "which does not silence it, it RECORDS it in the document")
    if despite.strip() and len(despite.split()) < 5:
        return Refusal("thin_override_reason",
                       f"`--despite-authorship` was given {len(despite.split())} word(s). "
                       "The override exists to preserve the fact, not to dismiss it; a "
                       "reason nobody can argue with is the same as no reason")
    return None


def sign(doc: Document, signer: str, *, today: date | None = None,
         despite: str = "") -> str:
    """The signed body. Ticks every box in the section and marks the FIRST one.

    The marker goes on one box rather than on each: the scorers read the section for a
    `signed-by` anywhere in it, and repeating the comment on every line would make a
    single signature look like several.
    """
    name = signer if signer.startswith(HUMAN_PREFIX) else HUMAN_PREFIX + signer
    head, tail = doc.body[:doc.section_at], doc.body[doc.section_at:]

    marked = [False]

    def tick(match: re.Match) -> str:
        if marked[0]:
            return f"{match.group(1)}[x]{match.group(2)}"
        marked[0] = True
        return f"{match.group(1)}[x]{match.group(2)}  <!-- signed-by: {name} -->"

    tail = UNTICKED_RE.sub(tick, tail)
    stamp = (today or date.today()).isoformat()
    tail += (f"\n**Signed {stamp} by `{name}` — a person, not a judge.**\n\n"
             "What a signature asserts is that someone read this and is willing to say "
             "it holds. It does not assert that a machine checked it: the deterministic "
             "score sits above, and the two are separate claims on purpose.\n")
    if despite.strip():
        #: Written INTO the document, not into a log. The next reader has to see that
        #: the reviewer and the author were the same person; that is the whole value
        #: of a check that can be overridden.
        tail += (f"\n**The signer is also an author of this document.** The reviewer and "
                 f"the author are normally separate, and here they are not. Reason "
                 f"given: {despite.strip()}\n\n"
                 "This signature is weaker than one from a reviewer who did not write "
                 "the document, and the record says so rather than blurring it.\n")
    return head + tail


def _agents_dir(project: Path) -> Path | None:
    """Where domain specialists live — inside the installed kit, not the write root.

    `rules/write-exemptions.txt` classes that location `platform`: Claude Code resolves
    a subagent by reading the directory, so the location IS the interface. A signable
    document therefore lives outside `.squad/`, and a listing that only swept the write
    root reported "nothing waiting" while seven specialists sat unsigned.
    """
    for candidate in (project / ".claude" / "agents", project / "agents"):
        if candidate.is_dir():
            return candidate
    return None


def waiting(project: Path) -> list[Path]:
    """Documents with an unticked sign-off box, wherever the kit keeps them."""
    roots = [d for d in (wiki_dir(project, "product"), wiki_dir(project, "design"),
                         records_dir(project, "alignment"),
                         records_dir(project, "discoveries"), records_dir(project, "plans"),
                         _agents_dir(project))
             if d is not None and d.is_dir()]
    found: list[Path] = []
    unreadable: list[str] = []
    for root in roots:
        for path in sorted(root.rglob("*.md")):
            try:
                doc = load(path)
            except Unreadable as exc:
                # Counted, not skipped. A document this tool cannot open is not a
                # document with nothing to sign, and dropping it makes the list of what
                # is waiting quietly shorter than the truth.
                unreadable.append(str(exc))
                continue
            if doc is not None and not doc.already_signed:
                found.append(path)
    if unreadable:
        print(f"{len(unreadable)} document(s) could not be read and are NOT in this list:",
              file=sys.stderr)
        for line in unreadable[:10]:
            print(f"  {line}", file=sys.stderr)
    return found


def resolve_target(target: str, project: Path) -> Path | None:
    """The document `target` names — as a path, or as a slug.

    The usage block advertised `<path-or-slug>` while `main` resolved a path only, so a
    slug became `./<slug>` and the user was told the document has no sign-off section.
    That sends them to read a file that is not the one they meant.

    A path that exists wins, always. Otherwise the slug is matched against the stems of
    the documents `--list` would have shown, with and without the `-plan` suffix the
    plans carry. Returns None when nothing matches, so the caller can say "unknown
    slug" rather than blaming a document.
    """
    as_path = Path(target)
    if as_path.exists():
        return as_path.resolve()

    slug = as_path.name.removesuffix(".md")
    for candidate in waiting(project):
        stem = candidate.stem
        if slug in (stem, stem.removesuffix("-plan")):
            return candidate
    return None


#: A heading the reader is not being asked to judge: it holds the boxes, and it is
#: printed verbatim below the summary anyway.
_SIGNOFF_HEADINGS = ("sign-off", "reviewer sign-off", "signoff")


def outline(doc: Document) -> tuple[str, list[str], int]:
    """`(title, sections, lines)` — everything EXTRACTED, nothing generated.

    The preview showed the box to tick and never what the document says. Four product
    documents wait at once and their sign-off sections read alike, so a batch preview
    distinguished them by path alone — which puts the operator in the position this gate
    exists to prevent: ticking a box whose subject they are taking on trust.

    A model-written one-line summary was the other option and is refused on purpose: a
    summary the reader has to verify is worse than none, because the signature already
    asserts that they read the document. What comes back is the document's own title,
    its own headings, and a count — three things a reader can check against the file in
    a second. `tests/test_a_preview_says_what_the_document_is.py` holds that line: any
    word in this header that is not in the document fails it.
    """
    title = ""
    sections: list[str] = []
    for raw in doc.body.splitlines():
        line = raw.strip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("## "):
            heading = line[3:].strip()
            if heading.lower() not in _SIGNOFF_HEADINGS:
                sections.append(heading)
    return title, sections, len(doc.body.splitlines())


def preview(doc: Document, signer: str, *, closing: bool = True) -> str:
    title, sections, lines = outline(doc)
    out = [f"ABOUT TO SIGN: {doc.path}", ""]
    # Absence stated, never left blank. An empty line here reads as "nothing to see"
    # when it means "this tool found no heading", and those are different facts — the
    # same distinction `--list` already refuses to blur.
    out.append(f"  {title}" if title else "  (untitled — no `# ` heading)")
    if sections:
        out.append(f"  {lines} lines · {len(sections)} section(s): "
                   + " · ".join(sections))
    else:
        out.append(f"  {lines} lines · no section headings found")
    out.append("")
    section = doc.body[doc.section_at:].strip()
    out.append("  The sign-off section, verbatim:")
    for line in section.splitlines()[:20]:
        out.append(f"    {line}")
    if len(section.splitlines()) > 20:
        out.append(f"    … {len(section.splitlines()) - 20} more line(s)")
    out += ["",
            f"  Signing as:  human/{signer.removeprefix(HUMAN_PREFIX)}",
            f"  Authors on record: {', '.join(doc.authors) or '(git could not say)'}",
            f"  Unticked boxes:    {doc.unticked}",
            "",
            "  WHAT YOUR SIGNATURE ASSERTS: that you read this and are willing to say "
            "it holds.",
            "  WHAT IT DOES NOT: that a machine verified it. The deterministic score is "
            "a separate claim,",
            "  and this tool neither reads it nor stands in for it.",
            "",
            ]
    if closing:
        # Said by the single-document path, where this preview IS the whole run. The
        # batch says it once at the end instead: repeating "re-run with --confirm" under
        # each of four documents reads as four separate decisions to make.
        out.append("  Nothing was written. Re-run with --confirm to sign.")
    return "\n".join(out)


def _sign_all(args) -> int:
    """Every document waiting, previewed together and signed on a second command.

    WHY THIS IS NOT A `--yes`
    -------------------------
    `SKILL.md` argues that a tool making signatures frictionless turns a signature into
    a stamp, and that there is deliberately no flag which skips the preview. This one
    does not skip it: the default run prints EVERY document's sign-off section, exactly
    what the single-document path prints, and writes nothing. What `--all` removes is
    typing the same command once per document — the four product documents are written
    together and read together — and nothing else.

    A batch that stopped at the first refusal would leave the earlier documents signed
    and the later ones untouched, with nothing on screen saying where it stopped. So a
    refusal is reported against its own document and the run carries on; the exit code
    says whether every one of them was signed.
    """
    project = args.project.resolve()
    signer = args.signer.strip()
    if not signer.removeprefix(HUMAN_PREFIX).strip():
        print("REFUSED [no_signer_named]: --as must name the person signing. A "
              "signature is worth exactly the name on it, and `human` is not a name. "
              "Nothing was signed.", file=sys.stderr)
        return 1

    pending = waiting(project)
    if not pending:
        # The same distinction `--list` draws, in the same words, because they are
        # different facts: no document is waiting, which is not everything being signed.
        print(f"nothing is waiting for a signature under {project}\n\n"
              "  That is not the same as everything being signed — it means no document "
              "with an\n  unticked `## Sign-off` box was found in the places the kit "
              "keeps them.")
        return 0

    signable: list[tuple[Path, Document]] = []
    refused: list[tuple[Path, Refusal]] = []
    for path in pending:
        try:
            doc = load(path)
        except Unreadable as exc:
            # Reported, never skipped: `waiting()` already refuses to let an unreadable
            # document shorten its list, and dropping it here would undo that one step
            # further along.
            refused.append((path, Refusal("unreadable", str(exc))))
            continue
        if doc is None:
            continue
        doc.authors = git_authors(path)
        refusal = check(doc, signer, despite=args.despite)
        if refusal is not None:
            refused.append((path, refusal))
            continue
        signable.append((path, doc))

    for index, (path, doc) in enumerate(signable, start=1):
        print(f"[{index}/{len(signable)}] {path}")
        print(preview(doc, signer, closing=False))
        print()

    for path, refusal in refused:
        print(f"REFUSED [{refusal.code}] {path}: {refusal.detail}", file=sys.stderr)

    if not signable:
        print(f"nothing signable: all {len(refused)} document(s) waiting were refused "
              f"above. Nothing was written.", file=sys.stderr)
        return 1

    if not args.confirm:
        print(f"Nothing written. Re-run with --confirm to sign all {len(signable)}.")
        if refused:
            print(f"  {len(refused)} other document(s) were refused and would stay "
                  f"unsigned — see above.")
        return 0

    for path, doc in signable:
        path.write_text(sign(doc, signer, despite=args.despite), encoding="utf-8")
    print(f"SIGNED {len(signable)} document(s) by "
          f"human/{signer.removeprefix(HUMAN_PREFIX)}:")
    for path, _ in signable:
        print(f"  {path}")
    print("\n  Run the scorer that gates each document to see the verdict move. This "
          "tool wrote\n  signatures; it did not compute anything.")
    # Exit 1 when some were refused: a caller that asked for "all" and got some did not
    # get what it asked for, and a 0 here would say otherwise.
    return 1 if refused else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", nargs="?", help="path to the document to sign")
    ap.add_argument("--list", action="store_true", help="what is waiting for a signature")
    ap.add_argument("--all", dest="all_waiting", action="store_true",
                    help="every document `--list` reports, previewed in one run")
    ap.add_argument("--confirm", action="store_true", help="write the signature")
    ap.add_argument("--as", dest="signer", default="", help="who is signing")
    ap.add_argument("--despite-authorship", dest="despite", default="",
                    help="sign a document you also authored, giving the reason. Does "
                         "not silence the check — writes the fact into the document")
    ap.add_argument("--project", type=Path, default=Path("."), help="project root")
    args = ap.parse_args(argv)

    if args.list:
        pending = waiting(args.project.resolve())
        if not pending:
            print("nothing is waiting for a signature under "
                  f"{args.project.resolve()}\n\n"
                  "  That is not the same as everything being signed — it means no "
                  "document with an\n  unticked `## Sign-off` box was found in the "
                  "places the kit keeps them.")
            return 0
        print(f"waiting for a signature ({len(pending)}):")
        for path in pending:
            print(f"  {path}")
        return 0

    if args.all_waiting:
        if args.target:
            # Two intentions in one command. Picking either one silently is how a tool
            # signs something nobody asked it to, and the cost of guessing wrong here is
            # a signature on a document the caller never named.
            ap.error("--all signs everything that is waiting; a target names one "
                     "document. Give one or the other, not both")
        return _sign_all(args)

    if not args.target:
        ap.error("give a document to sign, or --list to see what is waiting")

    path = resolve_target(args.target, args.project.resolve())
    if path is None:
        print(f"FATAL: `{args.target}` is neither a path that exists nor a slug of any "
              f"document waiting for a signature under {args.project.resolve()}. "
              f"Run with --list to see what is waiting. Nothing was signed.",
              file=sys.stderr)
        return 2
    try:
        doc = load(path)
    except Unreadable as exc:
        print(f"FATAL: {exc}. Nothing was signed, and this is NOT "
              f"'the document is not at the stage where a signature applies' — the tool "
              f"could not open it at all.", file=sys.stderr)
        return 2
    if doc is None:
        print(f"NOT SIGNABLE: {path} — no `## Sign-off` or `## Reviewer sign-off` "
              "section. Nothing was signed, and that is not a refusal: the document is "
              "not at the stage where a signature applies.", file=sys.stderr)
        return 2

    # A NAME is required. `--as` used to default to the bare string "human", which
    # `sign()` expanded to `signed-by: human/human` and the footer to "Signed by
    # `human/human` — a person, not a judge". `score_alignment.signed_by_is_human`
    # accepts anything starting with `human/`, so the strongest verdict the chain can
    # carry was produced by a run that named nobody — and the whole point of a human
    # signature is which human. The prefix alone is not a name either.
    signer = args.signer.strip()
    if not signer.removeprefix(HUMAN_PREFIX).strip():
        print("REFUSED [no_signer_named]: --as must name the person signing. A "
              "signature is worth exactly the name on it, and `human` is not a name. "
              "Nothing was signed.", file=sys.stderr)
        return 1
    doc.authors = git_authors(path)

    refusal = check(doc, signer, despite=args.despite)
    if refusal is not None:
        print(f"REFUSED [{refusal.code}]: {refusal.detail}", file=sys.stderr)
        return 1

    if not args.confirm:
        print(preview(doc, signer))
        return 0

    path.write_text(sign(doc, signer, despite=args.despite), encoding="utf-8")
    print(f"SIGNED: {path}\n  by human/{signer.removeprefix(HUMAN_PREFIX)}\n\n"
          "  Run the scorer that gates this document to see the verdict move. This "
          "tool wrote a\n  signature; it did not compute anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

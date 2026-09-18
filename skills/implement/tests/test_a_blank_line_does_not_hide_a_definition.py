"""A blank line above a declaration made pillar (a) pass on a symbol nobody calls.

Every `_DEFINITION_PATTERN` opens `^\\s*` under `MULTILINE`. `\\s` includes the newline,
so on

    import x
    ⏎
    export function createContainer() {

the match starts at the newline ENDING the blank line, not at `export`. Then
`text.count("\\n", 0, match.start())` counts one fewer newline and records the definition
on line 1 — the blank one — while the declaration is on line 2.

Line 2 therefore never enters `definition_lines`, the `export function createContainer`
line counts as an ordinary occurrence, `_is_definition_only` returns False, and the file
is credited as a CALLER of the symbol it declares. Pillar (a) — "no production caller" —
reports PASS on a symbol whose only appearance is its own declaration.

Reproduced in isolation:

    match.group(0) = '\\nexport function createContainer'
    match.start()  = 9  →  line 1   (the declaration is on line 2)

The exclusion is the whole reason the function exists: its own docstring says a
`grep -l` "will match the file that declares `function foo` even if no one else calls
it, producing a false PASS". The blank line put that false PASS back.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_wiring import _is_definition_only  # after the path bootstrap above


def test_a_declaration_after_a_blank_line_is_still_a_declaration(tmp_path: Path) -> None:
    """The shape every real file has: imports, a blank line, the export."""
    f = tmp_path / "composition.ts"
    f.write_text("import { x } from './x'\n\n"
                 "export function createContainer() {\n  return x\n}\n", encoding="utf-8")

    assert _is_definition_only(f, "createContainer"), (
        "the file declaring the symbol was credited as a caller of it — pillar (a) "
        "passes on a symbol nobody calls")


def test_a_declaration_on_the_first_line_still_works(tmp_path: Path) -> None:
    """The case that always worked, kept so the fix cannot trade one for the other."""
    f = tmp_path / "composition.ts"
    f.write_text("export function createContainer() {\n  return 1\n}\n", encoding="utf-8")

    assert _is_definition_only(f, "createContainer")


def test_a_real_caller_is_still_a_caller(tmp_path: Path) -> None:
    """The half that must not go quiet. A file that declares AND uses the symbol is a
    caller, and a fix that swallowed that would make pillar (a) unfailable."""
    f = tmp_path / "composition.ts"
    f.write_text("import { x } from './x'\n\n"
                 "export function createContainer() {\n  return 1\n}\n\n"
                 "const c = createContainer()\n", encoding="utf-8")

    assert not _is_definition_only(f, "createContainer"), (
        "a file that calls the symbol it declares was excluded from the caller count")


def test_indentation_before_a_declaration_is_handled(tmp_path: Path) -> None:
    """`^\\s*` exists for indented declarations, and they must keep working — the fix
    cannot be to drop the leading whitespace class."""
    f = tmp_path / "composition.ts"
    f.write_text("namespace N {\n\n  export function createContainer() {\n    return 1\n  }\n}\n",
                 encoding="utf-8")

    assert _is_definition_only(f, "createContainer")

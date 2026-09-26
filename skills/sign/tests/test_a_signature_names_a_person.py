"""A signature attributed to nobody carried the weight of one attributed to a person.

`--as` defaults to `""`, and `main` turned that into the bare string `"human"`. `sign()`
expands it to `<!-- signed-by: human/human -->` and the footer to "Signed <date> by
`human/human` — a person, not a judge". `score_alignment.signed_by_is_human` accepts
anything equal to `human` or starting with `human/`, so the strongest verdict the chain
can carry was produced by a run that named nobody.

The module's own docstring says the opposite: "`--as` names the signer, and the name
goes in the file next to what they signed."
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "sign" / "scripts" / "sign_document.py"


def _document(tmp_path: Path) -> Path:
    path = tmp_path / "a-design.md"
    path.write_text("# A design\n\n## Sign-off\n\n- [ ] Reviewed by:\n", encoding="utf-8")
    return path


def _sign(document: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_SCRIPT), str(document), "--confirm", *extra],
                          cwd=document.parent, capture_output=True, text=True,
                          timeout=120, check=False)


def test_signing_with_no_name_is_refused(tmp_path: Path) -> None:
    document = _document(tmp_path)

    result = _sign(document)

    assert result.returncode != 0, result.stdout
    assert "--as" in result.stderr, result.stderr
    assert "human/human" not in document.read_text(encoding="utf-8"), (
        "a signature naming nobody was written into the document")


def test_signing_as_human_with_no_name_is_refused(tmp_path: Path) -> None:
    """The prefix alone is not a name either."""
    document = _document(tmp_path)

    result = _sign(document, "--as", "human/")

    assert result.returncode != 0, result.stdout


def test_a_named_signer_signs(tmp_path: Path) -> None:
    document = _document(tmp_path)

    result = _sign(document, "--as", "paulo")

    assert result.returncode == 0, result.stderr
    assert "human/paulo" in document.read_text(encoding="utf-8")

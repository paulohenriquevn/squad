"""The kit ships in English, and so does every repository that installs it.

WHY THIS GATE EXISTS
--------------------
The policy was real and unenforced. Measured before this landed: 334 Portuguese
markers across 21 versioned files in this kit, 93 across 17 in the sibling — and
nothing anywhere checked. `check_adr_completeness.py` went further and *accepted*
Portuguese, matching "alternativa" and "rejeitada" alongside the English terms.

The cost is not aesthetic. A consumer's agents read these files as instructions;
a rule half in one language and half in another is a rule whose exact wording
nobody can grep for. And it spreads: one consumer wrote an entire `BACKLOG.md` in
Portuguese inside an English-by-policy repository, because nothing said no.

WHY THE DETECTOR SCORES INSTEAD OF MATCHING A LIST
--------------------------------------------------
It used to match a closed list of spellings that "cannot be English", and a closed
list over an open vocabulary has no bound on what it misses: `install.sh` carried the
section header `tabela de roteamento: entregue VAZIA` for four months while the gate
reported clean over 997 files. The detector now weighs every word on the line for
Portuguese evidence against English evidence. The precision half of the old promise
still holds and is tested below: `para`, `de`, `em`, a café in São Paulo, a name with
an accent — none of them makes an English line Portuguese.

Files that carry Portuguese on purpose — product copy, fixtures of a Portuguese
detector — are declared by path in the allowlist, with a reason, instead of widening
or narrowing the detector until they stop firing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "mechanisms" / "gates"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_english_only import (  # noqa: E402 — post-bootstrap import
    find_markers,
    is_exempt,
    scan_text,
)


@pytest.mark.parametrize("line", [
    "Este arquivo não é lido por ninguém.",  # english-only: the gate must name what it detects
    "A razão é que o gate está quebrado.",  # english-only: the gate must name what it detects
    "Você deve rodar o comando três vezes.",  # english-only: the gate must name what it detects
    "O plano foi aceito, porém sem evidência.",  # english-only: the gate must name what it detects
])
def test_portuguese_prose_is_caught(line: str) -> None:
    """Sentences a maintainer would actually write."""
    assert find_markers(line), f"missed: {line}"


@pytest.mark.parametrize("line", [
    "The verdict is computed, never asserted.",
    "Run the command three times to reproduce.",
    "See docs/para-standards.md for the parameter list.",
    "curl https://example.com/api/v1/status",
    "def compose_goal_condition(mode: str) -> str:",
    "The de facto standard is UTF-8.",
    "# Deduplicate by (file, line) — the same finding twice is one finding.",
])
def test_english_prose_is_not_flagged(line: str) -> None:
    """Precision matters more than recall: this gate runs in every consumer.

    `para`, `com`, `de` and `mode` all appear here in legitimate English or
    inside paths and identifiers. A detector that flagged them would fire on
    clean files, and the first thing a team does with a noisy gate is turn it
    off.
    """
    assert find_markers(line) == [], f"false positive: {line}"


def test_an_exemption_needs_a_written_reason() -> None:
    """A line may stay in Portuguese only if it says why, on the line itself.

    A quoted error message, a proper name, a citation of what somebody actually
    wrote — these are legitimate, and the exemption marker keeps them legible as
    deliberate rather than as debt nobody noticed. An exemption with no reason
    is a silent opt-out, which is what the gate exists to prevent.
    """
    assert is_exempt("O plano não existe  # english-only: quoting the tool's own output")
    assert is_exempt("não  <!-- english-only: the consumer's verbatim finding -->")
    assert not is_exempt("O plano não existe  # english-only:")
    assert not is_exempt("O plano não existe  # TODO translate")  # english-only: the gate must name what it detects
    assert not is_exempt("O plano não existe")  # english-only: the gate must name what it detects


def test_scan_reports_line_numbers_and_the_words_found() -> None:
    """A finding a reader cannot locate is a finding they will not fix.

    Naming the line and the exact markers is the difference between "this file
    has Portuguese somewhere" and a fix that takes ten seconds.
    """
    text = "line one is fine\nesta linha não está em inglês\nand this one is fine\n"  # english-only: the gate must name what it detects
    findings = scan_text(text)
    assert len(findings) == 1
    line_no, markers = findings[0]
    assert line_no == 2
    assert "não" in markers  # english-only: the gate must name what it detects


def test_a_file_with_only_english_scans_clean() -> None:
    text = "# Purpose\n\nThis rule governs the intake cycle.\n\n- One item, one owner.\n"
    assert scan_text(text) == []


def test_a_portuguese_docstring_with_no_accent_is_detected() -> None:
    """The marker set missed the shape a docstring actually takes.

    `Classifica (e opcionalmente aplica) a delta em UM consumidor` sat in versioned source  # english-only: quoting the line that slipped through
    for weeks and the gate reported clean: no accent, and not one of its words was on the
    list. The marker set had accented function words and a few nouns, and a Portuguese
    sentence built from verbs slipped through every one of them.
    """
    from check_english_only import scan_text

    assert scan_text("    \"\"\"Classifica (e opcionalmente aplica) a delta em UM consumidor.\"\"\"")  # english-only: the fixture IS the Portuguese this gate must catch


@pytest.mark.parametrize("line", [
    "# apply the delta to one consumer",
    "# returns the validated entry",
    "# this writes a file and validates the result",
    "def classify(source: str) -> Action:",
    "# the present value, or the absent one",
])
def test_the_widened_markers_do_not_fire_on_english(line: str) -> None:
    """Words that exist in both languages decide nothing on their own.

    `apply`, `returns`, `present`: the old list carried their Portuguese cousins, and
    the scorer must not mistake the English spellings for them.
    """
    from check_english_only import scan_text

    assert not scan_text(line), f"false positive on: {line}"


# ── the detector scores; it does not look words up ──────────────────────────────


@pytest.mark.parametrize("line", [
    # The install.sh shape with words no list ever carried: no accent, no marker.
    "# --- lista de encaminhamento: publicada VAZIA -----------------",  # english-only: the fixture IS the Portuguese this gate must catch
    # docs/ADR/0025 carried this one, and the list could not see it either.
    "**Integração (Fleet Lander)**",  # english-only: the fixture IS the Portuguese this gate must catch
    # The line the old docstring admitted it missed, verbatim.
    "exigindo a spec Agent Skills; com o kit instalado",  # english-only: the fixture IS the Portuguese this gate must catch
    "# Poda durante a travessia: um filtro posterior desce em tudo",  # english-only: the fixture IS the Portuguese this gate must catch
    "Descrição",  # english-only: the fixture IS the Portuguese this gate must catch
    "- 9 testes novos (95 nas duas skills).",  # english-only: the fixture IS the Portuguese this gate must catch
])
def test_portuguese_no_list_names_is_still_caught(line: str) -> None:
    """Coverage the closed list could not give: none of these words was on it."""
    assert find_markers(line), f"missed: {line}"


@pytest.mark.parametrize("line", [
    "We met at a café in São Paulo before the release.",
    "Deploy to the São Paulo region first, then Rio de Janeiro.",
    "Offices: Rio de Janeiro, São Paulo",
    "Maintained by José Antônio and João.",
    "The façade pattern hides the subsystem; the naïve version leaked it.",
    "Attach your résumé, not a cliché.",
    "São Paulo",
    "café",
    "Use an em dash, not a hyphen.",
    "The de facto standard is UTF-8, and para-virtualisation is not the point.",
    "except ValueError as e:",
    "The lookup is O(n) at worst; Big O hides the constant.",
    '    "sort": "o", "go": "o",',
    "# TODO: a line with a TODO in it is still English",
])
def test_english_with_loanwords_and_names_is_not_flagged(line: str) -> None:
    """A loanword or a name is one word of evidence against a whole English sentence.

    The gate runs in every consumer, and a consumer's README names its city and its
    authors. A detector that read `São Paulo` as Portuguese prose would be turned off
    the first week, which is the failure the old list was built to avoid.
    """
    assert find_markers(line) == [], f"false positive: {line}"


# ── the allowlist: which paths may carry Portuguese at all ──────────────────────


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    """A git repository tracking exactly `files`."""
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    return tmp_path


_PT_COPY = "Seu pedido foi enviado com sucesso.\n"  # english-only: product copy is the thing the allowlist admits


def test_a_path_declared_in_the_allowlist_may_carry_portuguese(tmp_path: Path) -> None:
    from check_english_only import scan_repository

    root = _repo(tmp_path, {
        "rules/english-only-allowlist.txt":
            "web/locales/pt-BR/* | product copy: the storefront ships in Portuguese\n",
        "web/locales/pt-BR/checkout.txt": _PT_COPY,
        "src/checkout.py": "# " + _PT_COPY,
    })

    report = scan_repository(root)

    assert list(report) == ["src/checkout.py"]


def test_without_an_allowlist_every_path_must_be_english(tmp_path: Path) -> None:
    from check_english_only import scan_repository

    root = _repo(tmp_path, {"web/locales/pt-BR/checkout.txt": _PT_COPY})

    assert list(scan_repository(root)) == ["web/locales/pt-BR/checkout.txt"]


def test_an_allowlist_row_without_a_reason_is_refused(tmp_path: Path) -> None:
    """Same contract as the per-line marker: an opt-out that says nothing is refused.

    A bare glob would silently exempt a directory forever, and the next reader could
    not tell product copy from a lapse somebody hid.
    """
    from check_english_only import AllowlistError, scan_repository

    root = _repo(tmp_path, {
        "rules/english-only-allowlist.txt": "web/locales/pt-BR/*\n",
        "web/locales/pt-BR/checkout.txt": _PT_COPY,
    })

    with pytest.raises(AllowlistError, match="english-only-allowlist.txt:1"):
        scan_repository(root)


def test_a_malformed_allowlist_exits_unchecked_rather_than_clean(tmp_path: Path) -> None:
    from check_english_only import main

    _repo(tmp_path, {
        "rules/english-only-allowlist.txt": "web/* |   \n",
        "README.md": "English.\n",
    })

    assert main(["--root", str(tmp_path)]) == 2

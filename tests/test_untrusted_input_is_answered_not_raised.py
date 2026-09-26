"""Two entry points turned malformed input into a traceback.

* `board_server._authorised` passed a raw Cookie value to `secrets.compare_digest`.
  With two `str` arguments that function requires both to be ASCII-only and raises
  `TypeError` otherwise — so a request carrying `board_token=café` raised INSIDE
  `do_GET`, and the handler thread logged a traceback and dropped the connection
  instead of answering 401. The header is unvalidated input from the network, which is
  the one place a raise is never the right answer.
* `propose_rules.main` read flag values with `args[args.index(flag) + 1]` and then
  dispatched on `{"go": ..., "typescript": ...}[language]`. `--language` with nothing
  after it raised IndexError; `--language rust` raised KeyError. Both reached the
  operator as a traceback, from a function that already prints a usage line.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "skills" / "backlog-review" / "scripts"))
sys.path.insert(0, str(_ROOT / "skills" / "arch-check" / "scripts"))

import board_server  # noqa: E402 — post-bootstrap import


class _Headers:
    def __init__(self, cookie: str) -> None:
        self._cookie = cookie

    def get(self, name: str) -> str | None:
        return self._cookie if name == "Cookie" else None


class _Request:
    """The two attributes `_authorised` reads, and nothing else."""

    def __init__(self, cookie: str) -> None:
        self.headers = _Headers(cookie)


def _authorised(cookie: str, token: str) -> bool:
    handler = board_server._handler(_ROOT, board_server._Hub(), token)
    return handler._authorised(_Request(cookie))


def test_a_non_ascii_cookie_is_refused_not_raised() -> None:
    assert _authorised("board_token=café", "the-real-token") is False


def test_the_right_token_is_still_accepted() -> None:
    assert _authorised("board_token=the-real-token", "the-real-token") is True


def test_a_wrong_token_is_refused() -> None:
    assert _authorised("board_token=something-else", "the-real-token") is False


def _propose(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_ROOT / "skills" / "arch-check" / "scripts" / "propose_rules.py"),
         *argv],
        capture_output=True, text=True, timeout=180, check=False)


def test_a_flag_with_no_value_prints_usage() -> None:
    done = _propose(str(_ROOT), "--language")

    assert "Traceback" not in done.stderr, done.stderr
    assert done.returncode == 2
    assert "usage" in done.stderr.lower()


def test_an_unsupported_language_says_which_are_supported() -> None:
    done = _propose(str(_ROOT), "--language", "rust")

    assert "Traceback" not in done.stderr, done.stderr
    assert done.returncode == 2
    assert "go" in done.stderr and "typescript" in done.stderr

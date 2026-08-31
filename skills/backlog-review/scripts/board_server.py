#!/usr/bin/env python3
"""A live board of the cycle: every item, the phase it sits in, and what holds it.

    python3 skills/backlog-review/scripts/board_server.py [project-path] [--port 8765]

Serves a single page at http://127.0.0.1:8765 that re-renders whenever `BACKLOG.md` or
`records/cycle-events.jsonl` changes on disk. No build step, no dependencies beyond the
standard library, and nothing to install — the same constraint the rest of this kit
works under, for the same reason: a tool that needs a toolchain gets used once.

## How "live" works, and what it costs

The server polls the mtime of the two source files twice a second and pushes a
Server-Sent Event when either moves. Polling rather than inotify because it is
portable, needs no dependency, and half a second is far below the rate at which a
human edits a registry or a cycle finishes a phase.

SSE rather than WebSockets because the traffic is one-directional: the board observes,
it never commands. A board that could advance an item would be a second writer racing
`backlog_status.py`, which is exactly the shape this ecosystem removed when it made
one writer own the status line.

## Bound to localhost by default, and never widened by accident

`BACKLOG.md` carries unreleased plans, kill reasons and sponsor decisions. The server
binds 127.0.0.1 unless told otherwise, because the failure mode of guessing wrong is
publishing someone's roadmap to their network.

Widening it takes two explicit flags, and the second is enforced rather than advised:

    --host 0.0.0.0 --token "$(openssl rand -hex 24)"

A non-loopback host with no token is REFUSED at startup. That is deliberate
fail-closed design — the machine this was first exposed on had `ufw` inactive and
five ports already open to the internet, so "I will add auth later" would have meant
serving an unreleased roadmap to anyone who scanned the host.

The token is checked against a cookie; a first visit may carry `?t=<token>` and the
server exchanges it for the cookie and redirects, so the secret leaves the URL bar
after one request instead of living in browser history and every access log line.
Comparison is `compare_digest` — a plain `==` leaks the token's prefix to anyone
willing to time the responses.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board_state import build_state, item_detail  # noqa: E402

POLL_SECONDS = 0.5
WATCHED = ("BACKLOG.md", "records/cycle-events.jsonl", ".claude/records/cycle-events.jsonl")

#: Set by `main()` from the flags, and read by every `build_state` call. Module-level
#: because the handler and the watcher both need them and neither owns the other.
_LEAD_LOG: Path | None = None
_LEAD_MARKER: Path | None = None


def _state(root: Path) -> dict:
    return build_state(root, _LEAD_LOG, _LEAD_MARKER)

#: How long a granted browser stays granted. Long, because the alternative measured
#: worse: a session cookie made the board look dead on the next browser start.
_COOKIE_MAX_AGE = 30 * 24 * 3600

#: What an unauthorised visitor gets. A page, not a line of text: the old plain-text
#: reply rendered as one sentence on a blank page and was read as the server being
#: down. It states that the board is running and what is missing.
#:
#: It never prints the token. A page that handed out the secret it is checking would
#: be an authentication that authenticates nobody.
_UNAUTHORISED_PAGE = b"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cycle Board \xe2\x80\x94 token required</title>
<style>
 :root { color-scheme: light dark; }
 body { margin:0; min-height:100vh; display:flex; align-items:center;
        justify-content:center; background:#f6f7f6; color:#1a1f1c;
        font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }
 @media (prefers-color-scheme: dark) { body { background:#101512; color:#e6ebe7; } }
 main { max-width:32rem; padding:2rem; }
 h1 { font-size:1.1rem; margin:0 0 .75rem; }
 p { margin:0 0 .75rem; }
 code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.9em; }
 .q { opacity:.7; font-size:.9em; }
</style></head><body><main>
<h1>The board is running \xe2\x80\x94 this browser is not signed in.</h1>
<p>The server is up and serving; what is missing is the access token. Open the board
   once through the full link, which ends in <code>?t=&lt;token&gt;</code>. It sets a
   cookie, drops the token from the address bar, and the plain address works from
   then on.</p>
<p class="q">The link is printed by the command that started the board. This page
   does not repeat the token \xe2\x80\x94 it is the thing being checked.</p>
</main></body></html>
"""

_PAGE = (Path(__file__).resolve().parent / "board.html")


class _Hub:
    """Fan-out of change notifications to every connected board."""

    def __init__(self) -> None:
        self._clients: set[queue.Queue] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=8)
        with self._lock:
            self._clients.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._clients.discard(q)

    def publish(self, payload: str) -> None:
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(payload)
            except queue.Full:
                # A board that stopped reading is a board that went away. Dropping the
                # update beats blocking the watcher for every other viewer.
                pass


def _fingerprint(root: Path) -> tuple:
    out = []
    # The lead's log and the session marker are absolute and live outside the project,
    # so they are appended rather than resolved against the root. Without them a
    # decision reached the board only when something else happened to change.
    extra = [p for p in (_LEAD_LOG, _LEAD_MARKER) if p is not None]
    for rel in list(WATCHED) + extra:
        p = root / rel if isinstance(rel, str) else rel
        try:
            st = p.stat()
            out.append((str(rel), st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((str(rel), 0, 0))
    return tuple(out)


def _watch(root: Path, hub: _Hub, stop: threading.Event) -> None:
    last = _fingerprint(root)
    while not stop.wait(POLL_SECONDS):
        current = _fingerprint(root)
        if current != last:
            last = current
            hub.publish(json.dumps(_state(root), ensure_ascii=False))


def _handler(root: Path, hub: _Hub, token: str | None):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:  # noqa: D102 - quiet by default
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        # ── authentication ────────────────────────────────────────────────
        def _authorised(self) -> bool:
            """True when no token is configured, or the request carries it."""
            if not token:
                return True
            cookie = self.headers.get("Cookie") or ""
            for part in cookie.split(";"):
                name, _, value = part.strip().partition("=")
                if name == "board_token" and secrets.compare_digest(value, token):
                    return True
            return False

        def _grant(self) -> bool:
            """Exchange a `?t=` query for the cookie, then redirect without it.

            The redirect matters: it takes the secret out of the address bar, out of
            browser history, and out of every later line in an access log.
            """
            path, _, query = self.path.partition("?")
            supplied = ""
            for pair in query.split("&"):
                key, _, value = pair.partition("=")
                if key == "t":
                    supplied = value
            if not supplied or not token or not secrets.compare_digest(supplied, token):
                return False
            self.send_response(302)
            self.send_header("Location", path or "/")
            # Max-Age, because without it this is a SESSION cookie: it dies when the
            # browser closes, and the next visit to the bare address answers 401.
            # Measured on 2026-08-31 — the operator reported the board as down while
            # the process was up, serving, and streaming. A dashboard that has to be
            # re-authorised every time the browser restarts is a dashboard nobody
            # keeps open. The cookie carries no more authority than the link that
            # granted it, and stays HttpOnly and SameSite=Strict.
            self.send_header(
                "Set-Cookie",
                f"board_token={token}; Path=/; Max-Age={_COOKIE_MAX_AGE}; "
                "HttpOnly; SameSite=Strict",
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's contract
            if not self._authorised():
                if self._grant():
                    return
                self._send(401, _UNAUTHORISED_PAGE, "text/html; charset=utf-8")
                return
            self.path = self.path.partition("?")[0] or "/"
            if self.path in ("/", "/index.html"):
                try:
                    body = _PAGE.read_bytes()
                except OSError as exc:
                    self._send(500, f"board.html unreadable: {exc}".encode(), "text/plain")
                    return
                self._send(200, body, "text/html; charset=utf-8")
            elif self.path == "/api/state":
                body = json.dumps(_state(root), ensure_ascii=False).encode()
                self._send(200, body, "application/json; charset=utf-8")
            elif self.path.startswith("/api/item/"):
                # On demand, never in the board payload: this registry holds 167 items,
                # and reading every plan and progress file to render a column of cards
                # would spend the page budget on work nobody asked to see.
                item = self.path[len("/api/item/"):].strip("/").upper()
                if not re.fullmatch(r"B-\d{3,}", item):
                    self._send(400, b"expected /api/item/B-NNN\n", "text/plain")
                    return
                body = json.dumps(item_detail(root, item), ensure_ascii=False).encode()
                self._send(200, body, "application/json; charset=utf-8")
            elif self.path == "/api/stream":
                self._stream()
            else:
                self._send(404, b"not found", "text/plain")

        def _stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = hub.subscribe()
            try:
                # The first frame is the current state, so a board that connects late
                # is not blank until something happens to change.
                self._frame(json.dumps(_state(root), ensure_ascii=False))
                while True:
                    try:
                        self._frame(q.get(timeout=15))
                    except queue.Empty:
                        # A comment frame keeps proxies and browsers from closing an
                        # idle stream, which on a quiet registry is most of the time.
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                hub.unsubscribe(q)

        def _frame(self, payload: str) -> None:
            self.wfile.write(b"data: " + payload.encode() + b"\n\n")
            self.wfile.flush()

    return Handler


def serve(root: Path, port: int, host: str = "127.0.0.1", token: str | None = None) -> int:
    hub = _Hub()
    stop = threading.Event()
    watcher = threading.Thread(target=_watch, args=(root, hub, stop), daemon=True)
    watcher.start()

    server = ThreadingHTTPServer((host, port), _handler(root, hub, token))
    state = _state(root)
    # `flush`, because stdout is block-buffered whenever it is not a terminal: the
    # first thing anyone does is redirect this to a log and then look for the URL,
    # and without the flush the log stays empty until the process exits.
    print(f"board: {root}", flush=True)
    print(f"  {len(state.get('items', []))} item(s) · "
          f"stream {'present' if state.get('has_stream') else 'absent (positions derived from status)'}",
          flush=True)
    shown = host if host not in ("0.0.0.0", "::") else "<this-host>"
    suffix = f"/?t={token}" if token else "/"
    print(f"  http://{shown}:{port}{suffix}  — Ctrl-C to stop", flush=True)
    if token:
        print("  token required; the link above sets a cookie and drops the token "
              "from the URL", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        stop.set()
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a live board of the cycle.")
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address; anything but loopback requires --token")
    parser.add_argument("--token", default=os.environ.get("BOARD_TOKEN", ""),
                        help="shared secret; also read from BOARD_TOKEN")
    parser.add_argument("--lead-log", type=Path, default=None,
                        help="the supervisor's decision log, rendered on the board")
    parser.add_argument("--lead-marker", type=Path, default=None,
                        help="file whose mtime says when the executing session last moved")
    args = parser.parse_args()

    global _LEAD_LOG, _LEAD_MARKER
    _LEAD_LOG = args.lead_log
    _LEAD_MARKER = args.lead_marker

    root = args.project.resolve()
    if not (root / "BACKLOG.md").is_file():
        print(f"FATAL: no BACKLOG.md under {root}", file=sys.stderr)
        return 1

    # Fail closed. A registry of unreleased plans reachable by anyone who scans the
    # host is not a thing to leave to a later flag.
    loopback = args.host in ("127.0.0.1", "::1", "localhost")
    if not loopback and not args.token:
        print("FATAL: --host " + args.host + " would serve BACKLOG.md beyond this "
              "machine. Pass --token (or set BOARD_TOKEN); generate one with:\n"
              "  openssl rand -hex 24", file=sys.stderr)
        return 1

    return serve(root, args.port, args.host, args.token or None)


if __name__ == "__main__":
    raise SystemExit(main())

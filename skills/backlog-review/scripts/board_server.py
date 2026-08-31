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

## Bound to localhost, deliberately

`BACKLOG.md` carries unreleased plans, kill reasons and sponsor decisions. The server
binds 127.0.0.1 and refuses another address, because the failure mode of guessing
wrong here is publishing someone's roadmap to their network.
"""
from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board_state import build_state  # noqa: E402

POLL_SECONDS = 0.5
WATCHED = ("BACKLOG.md", "records/cycle-events.jsonl", ".claude/records/cycle-events.jsonl")

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
    for rel in WATCHED:
        p = root / rel
        try:
            st = p.stat()
            out.append((rel, st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((rel, 0, 0))
    return tuple(out)


def _watch(root: Path, hub: _Hub, stop: threading.Event) -> None:
    last = _fingerprint(root)
    while not stop.wait(POLL_SECONDS):
        current = _fingerprint(root)
        if current != last:
            last = current
            hub.publish(json.dumps(build_state(root), ensure_ascii=False))


def _handler(root: Path, hub: _Hub):
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

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's contract
            if self.path in ("/", "/index.html"):
                try:
                    body = _PAGE.read_bytes()
                except OSError as exc:
                    self._send(500, f"board.html unreadable: {exc}".encode(), "text/plain")
                    return
                self._send(200, body, "text/html; charset=utf-8")
            elif self.path == "/api/state":
                body = json.dumps(build_state(root), ensure_ascii=False).encode()
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
                self._frame(json.dumps(build_state(root), ensure_ascii=False))
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


def serve(root: Path, port: int) -> int:
    hub = _Hub()
    stop = threading.Event()
    watcher = threading.Thread(target=_watch, args=(root, hub, stop), daemon=True)
    watcher.start()

    server = ThreadingHTTPServer(("127.0.0.1", port), _handler(root, hub))
    state = build_state(root)
    print(f"board: {root}")
    print(f"  {len(state.get('items', []))} item(s) · "
          f"stream {'present' if state.get('has_stream') else 'absent (positions derived from status)'}")
    print(f"  http://127.0.0.1:{port}  — Ctrl-C to stop")
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
    args = parser.parse_args()

    root = args.project.resolve()
    if not (root / "BACKLOG.md").is_file():
        print(f"FATAL: no BACKLOG.md under {root}", file=sys.stderr)
        return 1
    return serve(root, args.port)


if __name__ == "__main__":
    raise SystemExit(main())

"""Flask web frontend for ART — ASCII Dungeon Escape.

Runs the curses game inside a PTY and streams terminal I/O over WebSocket
to an xterm.js browser terminal.  The game itself is unchanged.

Usage:
    .venv/bin/python web.py [--port 5000] [--start-bonus]

Then open http://localhost:5000 in a browser.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import threading

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = "arthack-web"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Global game session — one PTY process shared across all browser tabs.
_lock = threading.Lock()
_master_fd: int | None = None
_proc: subprocess.Popen | None = None
_reader_running = False
_start_bonus = False  # set by CLI arg


# ---------------------------------------------------------------------------
# PTY helpers
# ---------------------------------------------------------------------------

def _set_winsize(fd: int, rows: int, cols: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def _read_loop() -> None:
    """Background thread: read PTY output and broadcast to all connected clients."""
    global _master_fd
    while True:
        if _master_fd is None:
            socketio.sleep(0.05)
            continue
        try:
            ready, _, _ = select.select([_master_fd], [], [], 0.02)
            if ready:
                chunk = os.read(_master_fd, 4096)
                socketio.emit("output", {"data": chunk.decode("utf-8", errors="replace")},
                              namespace="/game")
        except OSError:
            # PTY closed — game exited
            with _lock:
                _master_fd = None
            socketio.emit("game_over", {}, namespace="/game")
            socketio.sleep(1)


def _start_session(rows: int = 40, cols: int = 160) -> None:
    """Start the game process inside a PTY (no-op if already running)."""
    global _master_fd, _proc, _reader_running
    with _lock:
        if _proc and _proc.poll() is None:
            return  # session already live
        master_fd, slave_fd = pty.openpty()
        _set_winsize(master_fd, rows, cols)
        cmd = [sys.executable, os.path.join(BASE_DIR, "main.py")]
        if _start_bonus:
            cmd.append("--start-bonus")
        _proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            cwd=BASE_DIR,
        )
        os.close(slave_fd)
        _master_fd = master_fd
        if not _reader_running:
            _reader_running = True
            socketio.start_background_task(_read_loop)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/restart", methods=["POST"])
def restart():
    """Kill the current session so the next connection spawns a fresh game."""
    global _proc, _master_fd
    with _lock:
        if _proc:
            try:
                _proc.terminate()
                _proc.wait(timeout=2)
            except Exception:
                pass
            _proc = None
        if _master_fd is not None:
            try:
                os.close(_master_fd)
            except OSError:
                pass
            _master_fd = None
    return ("", 204)


# ---------------------------------------------------------------------------
# WebSocket events
# ---------------------------------------------------------------------------

def _sync_winsize(rows: int, cols: int) -> None:
    """Update PTY winsize and notify the game process (always safe to call)."""
    with _lock:
        if _master_fd is None:
            return
        try:
            _set_winsize(_master_fd, rows, cols)
        except OSError:
            return
        if _proc and _proc.poll() is None:
            try:
                os.kill(_proc.pid, signal.SIGWINCH)
            except ProcessLookupError:
                pass


@socketio.on("connect", namespace="/game")
def on_connect():
    rows = request.args.get("rows", 40, type=int)
    cols = request.args.get("cols", 200, type=int)
    _start_session(rows, cols)
    # Always sync in case the session was already running at different dimensions.
    _sync_winsize(rows, cols)


@socketio.on("input", namespace="/game")
def on_input(data):
    if _master_fd is not None:
        try:
            os.write(_master_fd, data["data"].encode("utf-8"))
        except OSError:
            pass


@socketio.on("resize", namespace="/game")
def on_resize(data):
    _sync_winsize(int(data["rows"]), int(data["cols"]))


@socketio.on("ping_check", namespace="/game")
def on_ping():
    emit("pong_check")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="ART web frontend")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--start-bonus", action="store_true",
                   help="start every new game session with the debug kit")
    return p.parse_args(argv)


def main():
    global _start_bonus
    args = _parse_args()
    _start_bonus = args.start_bonus
    print(f"ART web frontend → http://localhost:{args.port}")
    socketio.run(app, host=args.host, port=args.port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()

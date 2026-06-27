#!/usr/bin/env bash
# Launch ART in this project's virtualenv. Run from a terminal on XFCE4/X11.
set -euo pipefail
cd "$(dirname "$0")"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
exec "$PY" main.py "$@"

#!/usr/bin/env bash
# Start the ART web frontend and open a browser tab.
set -e
cd "$(dirname "$0")"

PORT="${PORT:-5000}"
WERKZEUG_RUN_MAIN=true

echo "Starting ART web frontend on http://localhost:$PORT"
WERKZEUG_SERVER_FD="" \
  .venv/bin/python web.py --port "$PORT" "$@"

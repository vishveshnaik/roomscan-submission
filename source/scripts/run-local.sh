#!/bin/sh
# Portable convenience launcher. Set ROOMSCAN_PYTHON to choose an interpreter.
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"
if [ -n "${ROOMSCAN_PYTHON:-}" ]; then
  exec "$ROOMSCAN_PYTHON" -m roomscan "$@"
elif [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m roomscan "$@"
else
  exec python3 -m roomscan "$@"
fi

#!/bin/sh
# Regenerate the original ceiling-coupled implementation from its real Git commit.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
INPUT=${1:?Usage: scripts/fix-loop.sh /absolute/path/to/raw-capture}
case "$INPUT" in
  /*) ;;
  *) INPUT="$(pwd)/$INPUT" ;;
esac
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
cd "$ROOT"
git archive 503a331 | tar -x -C "$TEMP_DIR"
PYTHON_BIN=${ROOMSCAN_PYTHON:-python3}
case "$PYTHON_BIN" in
  /*) ;;
  */*) PYTHON_BIN="$ROOT/$PYTHON_BIN" ;;
  *) PYTHON_BIN=$(command -v "$PYTHON_BIN") ;;
esac
(cd "$TEMP_DIR" && PYTHONPATH="$ROOT/.deps${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" -m roomscan run "$INPUT" --out "$ROOT/output/fix-before" --no-drift)
"$ROOT/scripts/run-local.sh" run "$INPUT" --out "$ROOT/output/fix-after" --no-drift
"$PYTHON_BIN" "$ROOT/scripts/compare-runs.py" "$ROOT/output/fix-before/result.json" "$ROOT/output/fix-after/result.json" "$ROOT/output/fix-diff.json"

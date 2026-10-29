#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN. Install Python or set PYTHON_BIN." >&2
  exit 127
fi

if ps -eo command | grep -q "[G]KK_Main_fixed_labor.a"; then
  echo "A fixed-labor model run is already active. Wait for it or inspect the log." >&2
  exit 1
fi

mkdir -p "$PACKAGE_DIR/logs" "$PACKAGE_DIR/results"
LOG="$PACKAGE_DIR/logs/optimizer_$(date +%Y%m%d_%H%M).log"

echo "Fixed-labor joint optimization will run in the foreground."
echo "Progress log: $LOG"
echo "Completed candidates are cached in: $PACKAGE_DIR/results"

cd "$ROOT"
THREADS="${THREADS:-9}" "$PYTHON_BIN" \
  "$PACKAGE_DIR/optimize_joint_taxes_fixed_labor.py" "$@" 2>&1 | tee "$LOG"

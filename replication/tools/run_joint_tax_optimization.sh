#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN. Install Python or set PYTHON_BIN." >&2
  exit 127
fi

if ps -eo command | grep -q "[C]ompiled_Files_Baseline/GKK_Main.a"; then
  echo "A model run is already active. Wait for it to finish before starting the joint search." >&2
  exit 1
fi

mkdir -p automation_logs
LOG="automation_logs/joint_tax_$(date +%Y%m%d_%H%M).log"

echo "Joint tax optimization will run in the foreground."
echo "Progress log: $LOG"
echo "Completed candidates are cached and reused if this command is restarted."

THREADS="${THREADS:-9}" "$PYTHON_BIN" tools/optimize_joint_taxes.py "$@" 2>&1 | tee "$LOG"

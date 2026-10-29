#!/usr/bin/env bash
# Start the optimal-wealth-tax (OWT) grid search, detached, with logging.
#
#   bash tools/start_owt.sh
#
# Refuses to start if an optw run is already going, because two concurrent runs
# write to the same Opt_Tax_W files and interleave their output.

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

if ps -eo command | grep -q "[r]un_mac.sh optw"; then
  echo "An optw run is ALREADY RUNNING - not starting another."
  echo "Check it with:  bash tools/status.sh"
  echo "Stop it with :  pkill -f run_mac.sh"
  exit 1
fi

mkdir -p automation_logs
LOG="automation_logs/owt_$(date +%Y%m%d_%H%M).log"

THREADS="${THREADS:-9}" nohup bash tools/run_mac.sh optw > "$LOG" 2>&1 < /dev/null &
disown

echo "OWT started.  log: $LOG"
echo "Takes several hours. Safe to close this terminal."
echo "Check progress with:  bash tools/status.sh"

#!/usr/bin/env bash
# Start the optimal capital income tax (OKIT) grid search, detached, with logging.
#
#   bash tools/start_okit.sh                 # tau_k grid -20% .. -5%, step 1
#   KMIN=-25 KMAX=5 bash tools/start_okit.sh # custom range, in percent
#   KSTEP=2 bash tools/start_okit.sh         # coarser grid, fewer points
#
# The paper's OKIT is a capital income SUBSIDY of -13.6% (Table VIII), so the grid
# must span negative tau_k. The default -20..-5 brackets it with room either side.
#
# Refuses to start if another optimal-tax run is going, because concurrent runs
# write to the same result files and interleave their output.

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

if ps -eo command | grep -qE "[r]un_mac.sh (optk|optw)"; then
  echo "An optimal-tax run is ALREADY RUNNING - not starting another."
  echo "Check it with:  bash tools/status.sh"
  echo "Stop it with :  pkill -f run_mac.sh"
  exit 1
fi

KMIN="${KMIN:--20}"
KMAX="${KMAX:--05}"
KSTEP="${KSTEP:-1}"

# Rewrite the OKIT grid in place, targeting the trailing markers so the OWT grid
# (which uses the same variable names a few lines below) is never touched.
perl -pi -e "s/^(\s*tau_grid_min\s*=\s*)\S+(\s*! OKIT_GRID_MIN)/\${1}$KMIN\${2}/"   GKK_Main.f90
perl -pi -e "s/^(\s*tau_grid_max\s*=\s*)\S+(\s*! OKIT_GRID_MAX)/\${1}$KMAX\${2}/"   GKK_Main.f90
perl -pi -e "s/^(\s*tau_grid_step\s*=\s*)\S+(\s*! OKIT_GRID_STEP)/\${1}$KSTEP\${2}/" GKK_Main.f90

echo "OKIT grid set to tau_k = $KMIN% .. $KMAX%, step $KSTEP:"
grep -n "OKIT_GRID_" GKK_Main.f90

npts=$(( (KMAX - KMIN) / KSTEP + 1 ))
echo "  $npts grid points; each needs several full equilibria - budget hours."

mkdir -p automation_logs
LOG="automation_logs/okit_$(date +%Y%m%d_%H%M).log"

THREADS="${THREADS:-9}" nohup bash tools/run_mac.sh optk > "$LOG" 2>&1 < /dev/null &
disown

echo
echo "OKIT started.  log: $LOG"
echo "Safe to close this terminal."
echo "Check progress with:  bash tools/status.sh"

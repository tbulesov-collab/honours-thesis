#!/usr/bin/env bash
# Reproduce the revenue-neutral (RN) tax reform results of GKKOC (2022, QJE),
# Tables V, VI and VII.
#
#   bash tools/reproduce_rn_reform.sh              # full run, benchmark + reform
#   bash tools/reproduce_rn_reform.sh --tables     # tables only, reuse existing output
#   bash tools/reproduce_rn_reform.sh --skip-bench # reform only, reuse Bench_Files
#
#   THREADS=9 bash tools/reproduce_rn_reform.sh
#
# The benchmark must be solved before the reform: 'tax-reform' mode sets
# compute_bench=.false. and reads the benchmark from <model>/Bench_Files.
#
# WARNING: the reform stage takes many hours. It solves a full stationary
# equilibrium for every wealth-tax rate in the bracketing and bisection search
# over tau_a (GKK_Main.f90:627-696).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${MODEL_DIR:-Revision/Model_2.1_Local}"
# nz=9 in parameters.f90, and the code calls omp_set_num_threads(nz), so more
# than 9 threads has no effect on the equilibrium solvers.
THREADS="${THREADS:-9}"
PYTHON_BIN="${PYTHON:-$(command -v python3)}"

RUN_BENCH=1
RUN_REFORM=1

for arg in "$@"; do
  case "$arg" in
    --tables)     RUN_BENCH=0; RUN_REFORM=0 ;;
    --skip-bench) RUN_BENCH=0 ;;
    -h|--help)    sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *)            echo "unknown option: $arg" >&2; exit 64 ;;
  esac
done

cd "$ROOT"

step() { printf '\n=== [%s] %s ===\n' "$(date +%H:%M:%S)" "$1"; }

if (( RUN_BENCH )); then
  step "Stage 1/3  benchmark economy (tau_k = 25%, tau_a = 0)"
  THREADS="$THREADS" bash tools/run_mac.sh bench-recompute
fi

if (( RUN_REFORM )); then
  step "Stage 2/3  RN tax reform (tau_k = 0, solve for revenue-neutral tau_a)"
  THREADS="$THREADS" bash tools/run_mac.sh tax-reform
fi

step "Stage 3/3  building Tables V, VI, VII"
"$PYTHON_BIN" tools/rn_reform_tables.py --model-dir "$MODEL_DIR"

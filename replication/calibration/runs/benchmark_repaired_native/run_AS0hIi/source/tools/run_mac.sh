#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN="$ROOT/GKK_Main.f90"
THREADS="${THREADS:-4}"
PYTHON_BIN="${PYTHON:-/opt/anaconda3/bin/python3}"

usage() {
  cat <<'USAGE'
Usage:
  THREADS=4 bash tools/run_mac.sh <mode>

Modes:
  bench-recompute  Solve benchmark from scratch and write Bench_Files
  bench-read       Read existing benchmark files
  bench-sim        Read benchmark files and run benchmark simulations
  calibration-build Configure benchmark recomputation and compile without running
  tax-reform       Run wealth-tax reform experiment
  optw             Run optimal wealth-tax grid
  optk             Run optimal capital-tax grid
  joint-build      Configure and compile one joint-tax candidate evaluator
  joint-eval       Evaluate one revenue-neutral joint-tax candidate
  build            Compile Fortran executable without running it
  python           Run Python tables/figures pipeline
  all              Run bench-recompute, tax-reform, optw, optk, then python

Environment:
  THREADS          OpenMP threads for Fortran runs, default 4
  PYTHON           Python executable for the paper pipeline
USAGE
}

set_bool() {
  local name="$1"
  local value="$2"
  perl -0pi -e "s/^([ \\t]*${name}[ \\t]*=[ \\t]*)\\.(?:true|false)\\./\${1}.${value}./mi" "$MAIN"
}

set_real() {
  local name="$1"
  local value="$2"
  perl -0pi -e "s/^([ \\t]*${name}[ \\t]*=[ \\t]*)[-0-9.]+_dp/\${1}${value}_dp/mi" "$MAIN"
}

configure_common_off() {
  set_bool Benchmark_Only false
  set_bool Tax_Reform false
  set_bool Tax_Reform_tktw false
  set_bool Opt_Tax false
  set_bool Opt_Threshold false
  set_bool Transition_Tax_Reform false
  set_bool Transition_OT false
  set_bool Simul_Switch false
  set_bool compute_exp false
  set_bool compute_exp_pf false
  set_bool compute_exp_prices false
}

configure_mode() {
  local mode="$1"
  configure_common_off

  case "$mode" in
    bench-recompute)
      set_bool Benchmark_Only true
      set_bool compute_bench true
      ;;
    bench-read)
      set_bool Benchmark_Only true
      set_bool compute_bench false
      ;;
    bench-sim)
      set_bool Benchmark_Only true
      set_bool compute_bench false
      set_bool Simul_Switch true
      ;;
    tax-reform)
      set_bool Tax_Reform true
      set_bool compute_bench false
      set_bool compute_exp true
      # Table V is a FLAT wealth tax. A nonzero factor exempts wealth below
      # Threshold_Factor*Ebar_bench and solves a different experiment.
      set_real Threshold_Factor 0.00
      ;;
    optw)
      set_bool Opt_Tax true
      set_bool compute_bench false
      set_bool Opt_Tax_KW false
      ;;
    optk)
      set_bool Opt_Tax true
      set_bool compute_bench false
      set_bool Opt_Tax_KW true
      ;;
    joint-eval)
      set_bool Tax_Reform_tktw true
      set_bool budget_flag true
      set_bool compute_bench false
      ;;
    *)
      echo "Unknown Fortran mode: $mode" >&2
      usage
      exit 64
      ;;
  esac
}

run_fortran() {
  if ! command -v gfortran >/dev/null 2>&1; then
    echo "gfortran was not found. Install it with: brew install gcc" >&2
    exit 127
  fi

  cd "$ROOT"
  echo "[mac-run] OMP_NUM_THREADS=$THREADS make GKK_Main"
  OMP_NUM_THREADS="$THREADS" make GKK_Main
}

build_fortran() {
  if ! command -v gfortran >/dev/null 2>&1; then
    echo "gfortran was not found. Install it with: brew install gcc" >&2
    exit 127
  fi

  cd "$ROOT"
  mkdir -p Compiled_Files_Baseline

  local folder="./Compiled_Files_Baseline"
  local main_objects=(
    "$folder/NRTYPE.o"
    "$folder/NRUTIL.o"
    "$folder/Toolbox.o"
    "$folder/parameters.o"
    "$folder/global.o"
    "$folder/programfunctions.o"
    "$folder/Simulation_Module.o"
    "$folder/GKK_Stats.o"
  )
  local opt_objects=(
    "$folder/Opt_Tax_Parameters.o"
    "$folder/Opt_Tax_Functions.o"
  )

  # Apple Silicon has a baseline FMA instruction and gfortran defaults to
  # -ffp-contract=fast, so a*b+c is fused and rounded once. The authors built on
  # x86-64 (UMN PBS cluster), where the SSE2 baseline has no FMA and no contraction
  # happens. Contraction is not symmetric roundoff: it feeds the grid-bracketing
  # step, where tklo is an integer truncation, so a 1-ulp shift moves an agent onto
  # a different asset grid point. Keep it off to match the reference build.
  fp="-ffp-contract=off"

  echo "[mac-run] compiling Fortran objects"
  gfortran -O3 $fp -J"$folder" -c NRTYPE.F90 -o "$folder/NRTYPE.o"
  gfortran -O3 $fp -J"$folder" -c NRUTIL.F90 -o "$folder/NRUTIL.o"
  gfortran -O3 $fp -J"$folder" -c Toolbox.f90 -o "$folder/Toolbox.o"
  gfortran -O3 $fp -J"$folder" -c parameters.f90 -o "$folder/parameters.o"
  gfortran -O3 $fp -J"$folder" -c global.f90 -o "$folder/global.o"
  gfortran -fopenmp -O3 $fp -fbounds-check -J"$folder" -c programfunctions.f90 -o "$folder/programfunctions.o"
  gfortran -fopenmp -O3 $fp -fbounds-check -J"$folder" -c Simulation_Module.f90 -o "$folder/Simulation_Module.o"
  gfortran -fopenmp -O3 $fp -fbounds-check -J"$folder" -c GKK_Stats.f90 -o "$folder/GKK_Stats.o"
  gfortran -O3 $fp -J"$folder" -c Opt_Tax_Parameters.f90 -o "$folder/Opt_Tax_Parameters.o"
  gfortran -O3 $fp -J"$folder" -c Opt_Tax_Functions.f90 -o "$folder/Opt_Tax_Functions.o"

  echo "[mac-run] linking $folder/GKK_Main.a"
  gfortran -fopenmp -fbounds-check -O3 $fp -I"$folder" GKK_Main.f90 "${main_objects[@]}" "${opt_objects[@]}" -o "$folder/GKK_Main.a"
  echo "[mac-run] build complete: $folder/GKK_Main.a"
}

run_python() {
  cd "$ROOT"

  if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="$(command -v python3 || true)"
  fi

  if [[ -z "${PYTHON_BIN:-}" ]]; then
    echo "python3 was not found." >&2
    exit 127
  fi

  mkdir -p "$ROOT/.cache/matplotlib" "$ROOT/.cache/fontconfig"
  export MPLCONFIGDIR="${MPLCONFIGDIR:-$ROOT/.cache/matplotlib}"
  export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$ROOT/.cache}"

  echo "[mac-run] $PYTHON_BIN paper_python/run_pipeline.py"
  "$PYTHON_BIN" paper_python/run_pipeline.py
}

main() {
  local mode="${1:-help}"

  case "$mode" in
    help|-h|--help)
      usage
      ;;
    python)
      run_python
      ;;
    build)
      build_fortran
      ;;
    calibration-build)
      configure_mode bench-recompute
      build_fortran
      ;;
    joint-build)
      configure_mode joint-eval
      build_fortran
      ;;
    all)
      configure_mode bench-recompute
      run_fortran
      configure_mode tax-reform
      run_fortran
      configure_mode optw
      run_fortran
      configure_mode optk
      run_fortran
      run_python
      ;;
    bench-recompute|bench-read|bench-sim|tax-reform|optw|optk|joint-eval)
      configure_mode "$mode"
      run_fortran
      ;;
    *)
      echo "Unknown mode: $mode" >&2
      usage
      exit 64
      ;;
  esac
}

main "$@"

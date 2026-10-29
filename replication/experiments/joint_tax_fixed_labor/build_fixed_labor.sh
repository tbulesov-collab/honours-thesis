#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
BUILD="$PACKAGE_DIR/build"
FP="-ffp-contract=off"

if ! command -v gfortran >/dev/null 2>&1; then
  echo "gfortran was not found. Install it with: brew install gcc" >&2
  exit 127
fi

mkdir -p "$BUILD"
echo "[fixed-labor-build] compiling isolated Fortran objects"

gfortran -O3 $FP -J"$BUILD" -c "$ROOT/NRTYPE.F90" -o "$BUILD/NRTYPE.o"
gfortran -O3 $FP -J"$BUILD" -c "$ROOT/NRUTIL.F90" -o "$BUILD/NRUTIL.o"
gfortran -O3 $FP -J"$BUILD" -c "$ROOT/Toolbox.f90" -o "$BUILD/Toolbox.o"
gfortran -O3 $FP -J"$BUILD" -c "$ROOT/parameters.f90" -o "$BUILD/parameters.o"
gfortran -O3 $FP -J"$BUILD" -c "$ROOT/global.f90" -o "$BUILD/global.o"
gfortran -fopenmp -O3 $FP -fbounds-check -J"$BUILD" -c "$ROOT/programfunctions.f90" -o "$BUILD/programfunctions.o"
gfortran -fopenmp -O3 $FP -fbounds-check -J"$BUILD" -c "$ROOT/Simulation_Module.f90" -o "$BUILD/Simulation_Module.o"
gfortran -fopenmp -O3 $FP -fbounds-check -J"$BUILD" -c "$ROOT/GKK_Stats.f90" -o "$BUILD/GKK_Stats.o"
gfortran -O3 $FP -J"$BUILD" -c "$ROOT/Opt_Tax_Parameters.f90" -o "$BUILD/Opt_Tax_Parameters.o"
gfortran -O3 $FP -J"$BUILD" -c "$ROOT/Opt_Tax_Functions.f90" -o "$BUILD/Opt_Tax_Functions.o"

echo "[fixed-labor-build] linking isolated executable"
gfortran -fopenmp -fbounds-check -O3 $FP -I"$BUILD" \
  "$PACKAGE_DIR/GKK_Main_fixed_labor.f90" \
  "$BUILD/NRTYPE.o" "$BUILD/NRUTIL.o" "$BUILD/Toolbox.o" \
  "$BUILD/parameters.o" "$BUILD/global.o" "$BUILD/programfunctions.o" \
  "$BUILD/Simulation_Module.o" "$BUILD/GKK_Stats.o" \
  "$BUILD/Opt_Tax_Parameters.o" "$BUILD/Opt_Tax_Functions.o" \
  -o "$BUILD/GKK_Main_fixed_labor.a"

# Some macOS/Homebrew linker combinations leave executables outside the main
# build directory unsigned. macOS then kills them immediately with SIGKILL.
# Apply the same ad-hoc signature carried by the working main executable.
if command -v codesign >/dev/null 2>&1; then
  codesign --force --sign - "$BUILD/GKK_Main_fixed_labor.a"
fi

echo "[fixed-labor-build] complete: $BUILD/GKK_Main_fixed_labor.a"

#!/usr/bin/env python3
"""Build benchmark and evaluator copies with higher markups, mu = 0.8 (GKKOC E.10 iii).

mu is a compile-time constant in parameters.f90 (REAL(DP), PARAMETER :: mu=0.90_DP), so
the check needs its own build.  This copy sets mu = 0.80 and also carries the validated
bounded interest-rate search of make_rbracket.py (start at the current R, search
[-0.1, 0.5]), which reproduced every previously converged result exactly.  The live
sources are not modified.

    variants/mu08/build/bench.a   benchmark solver
    variants/mu08/build/eval.a    policy evaluator

The directory layout (variants/<arm>/build/bench.a) lets partC7.py reuse the thesis
calibration procedure in experiments/model_spec_sensitivity_2022/recalibrate.py.

    python3 experiments/robustness_gkkoc_2022/make_mu08.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "model_spec_sensitivity_2022"))
sys.path.insert(0, str(HERE))

from make_rbracket import NEW as RB_NEW, OLD as RB_OLD          # noqa: E402
from make_variants import SOURCES, bench_main, run, sha         # noqa: E402

PATCHES = {"parameters.f90": [("mu=0.90_DP", "mu=0.80_DP", 1)],
           "programfunctions.f90": [(RB_OLD, RB_NEW, 3)]}
BASE = HERE / "variants" / "mu08"


def main() -> int:
    src, out = BASE / "src", BASE / "build"
    if BASE.exists():
        shutil.rmtree(BASE)
    (out / "mod").mkdir(parents=True)
    src.mkdir(parents=True)
    for name in SOURCES:
        shutil.copy2(ROOT / name, src / name)
    for name, reps in PATCHES.items():
        text = (src / name).read_text()
        for old, new, count in reps:
            if text.count(old) != count:
                raise SystemExit(f"expected {count} of {old[:50]!r} in {name}, found {text.count(old)}")
            text = text.replace(old, new)
        (src / name).write_text(text)
    (src / "GKK_Main_bench.f90").write_text(bench_main((src / "GKK_Main.f90").read_text()))

    plain = ["NRTYPE.F90", "NRUTIL.F90", "Toolbox.f90", "parameters.f90", "global.f90",
             "Opt_Tax_Parameters.f90"]
    omp = ["programfunctions.f90", "Simulation_Module.f90", "GKK_Stats.f90"]
    objects = []
    for name in plain + omp + ["Opt_Tax_Functions.f90"]:
        obj = f"../build/{Path(name).stem}.o"
        flags = (["-fopenmp", "-O3", "-fbounds-check", "-ffp-contract=off"] if name in omp
                 else ["-O3"])
        run(["gfortran", *flags, "-J../build/mod", "-c", name, "-o", obj], src)
        objects.append(obj)
    for main, exe in [("GKK_Main.f90", "eval.a"), ("GKK_Main_bench.f90", "bench.a")]:
        run(["gfortran", "-fopenmp", "-fbounds-check", "-ffp-contract=off", "-O3",
             "-I../build/mod", main, *objects, "-o", f"../build/{exe}"], src)
    srcs = {p.name: sha(p) for p in sorted(src.iterdir()) if p.suffix.lower() == ".f90"}
    changed = sorted(n for n in SOURCES if srcs[n] != sha(ROOT / n))
    if changed != sorted(PATCHES):
        raise SystemExit(f"unexpected source differences: {changed}")
    (BASE / "provenance.json").write_text(json.dumps({
        "patches": {f: [{"old": o, "new": n, "count": c} for o, n, c in r] for f, r in PATCHES.items()},
        "sources_sha256": srcs,
        "live_sources_sha256": {n: sha(ROOT / n) for n in SOURCES},
        "executables_sha256": {e: sha(out / e) for e in ("bench.a", "eval.a")}}, indent=2) + "\n")
    print(f"built {out}/bench.a and eval.a; changed {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build benchmark and evaluator copies with the bounded interest-rate search.

The pure-rents benchmark does not converge with the inherited solver for any ability
spread tried (0.001, 0.01, 0.02, 0.04): the steady-state interest-rate step

    brent_value = brent(-0.1_DP,0.01_DP,10.0_DP,Agg_Debt, brent_tol,R)

always restarts at R = 0.01 and, with nearly identical firms, alternates between
R = -0.032 and R = 0.052 every iteration.  This copy uses the bounded search of
make_rbracket.py (start at the current R, search [-0.1, 0.5]) in both executables:

    variant_purerents/build/bench.a   benchmark solver (Benchmark_Only, as in
                                      make_variants.bench_main)
    variant_purerents/build/eval.a    policy evaluator

The OKIT follow-up showed the bounded search reproduces converged policy results
exactly; partC.py --probe ... --build rb also re-solves the thesis benchmark with this
bench.a and requires it to match the fresh thesis benchmark.  The live sources are not
modified; only programfunctions.f90 differs (3 replacements).

    python3 experiments/robustness_gkkoc_2022/make_purerents.py
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

from make_rbracket import NEW, OLD                           # noqa: E402
from make_variants import SOURCES, bench_main, run, sha      # noqa: E402

BASE = HERE / "variant_purerents"


def main() -> int:
    src, out = BASE / "src", BASE / "build"
    if BASE.exists():
        shutil.rmtree(BASE)
    (out / "mod").mkdir(parents=True)
    src.mkdir(parents=True)
    for name in SOURCES:
        shutil.copy2(ROOT / name, src / name)
    pf = src / "programfunctions.f90"
    text = pf.read_text()
    if text.count(OLD) != 3:
        raise SystemExit(f"expected 3 interest-rate solves, found {text.count(OLD)}")
    pf.write_text(text.replace(OLD, NEW))
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
    changed = [n for n in SOURCES if srcs[n] != sha(ROOT / n)]
    if changed != ["programfunctions.f90"]:
        raise SystemExit(f"unexpected source differences: {changed}")
    (BASE / "provenance.json").write_text(json.dumps({
        "patch": {"file": "programfunctions.f90", "old": OLD, "new": NEW, "count": 3},
        "sources_sha256": srcs,
        "live_sources_sha256": {n: sha(ROOT / n) for n in SOURCES},
        "executables_sha256": {e: sha(out / e) for e in ("bench.a", "eval.a")}}, indent=2) + "\n")
    print(f"built {out}/bench.a and eval.a; only programfunctions.f90 differs (3 replacements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

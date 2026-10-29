#!/usr/bin/env python3
"""Build a copy of the evaluator with a bounded interest-rate search.

Under the looser-constraint calibration (theta_max 9.66) every OKIT evaluation stopped
with "Non-finite equilibrium aggregates": once the budget loop changed the labour tax,
the steady-state interest-rate step

    brent_value = brent(-0.1_DP,0.01_DP,10.0_DP,Agg_Debt, brent_tol,R)

(a minimisation of squared excess capital demand over [-0.1, 10], always started at
0.01) jumped from R = 0.04 to R = 3.83, after which wages and output were zero.  This
copy searches [-0.1, 0.5] instead, starting from the current R:

    brent_value = brent(-0.1_DP,min(max(R,-0.09_DP),0.49_DP),0.5_DP,Agg_Debt, brent_tol,R)

in all three steady-state solvers (FIND_DBN_EQ and its two variants).  Equilibria with
R inside (-0.1, 0.5) are unaffected; tier1.py re-evaluates converged points with this
build to check that.  The live sources are not modified: the patched copy and its
executable live under experiments/robustness_gkkoc_2022/variant_rbracket/.

    python3 experiments/robustness_gkkoc_2022/make_rbracket.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "model_spec_sensitivity_2022"))

from make_variants import SOURCES, run, sha       # noqa: E402

OLD = "brent(-0.1_DP,0.01_DP,10.0_DP,Agg_Debt, brent_tol,R)"
NEW = "brent(-0.1_DP,min(max(R,-0.09_DP),0.49_DP),0.5_DP,Agg_Debt, brent_tol,R)"
BASE = HERE / "variant_rbracket"


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
    run(["gfortran", "-fopenmp", "-fbounds-check", "-ffp-contract=off", "-O3",
         "-I../build/mod", "GKK_Main.f90", *objects, "-o", "../build/eval.a"], src)
    provenance = {"patch": {"old": OLD, "new": NEW, "count": 3},
                  "sources_sha256": {p.name: sha(p) for p in sorted(src.iterdir())
                                     if p.suffix.lower() == ".f90"},
                  "live_sources_sha256": {n: sha(ROOT / n) for n in SOURCES},
                  "eval_sha256": sha(out / "eval.a")}
    changed = [n for n in SOURCES if provenance["sources_sha256"][n] != provenance["live_sources_sha256"][n]]
    if changed != ["programfunctions.f90"]:
        raise SystemExit(f"unexpected source differences: {changed}")
    (BASE / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"built {out / 'eval.a'}; only programfunctions.f90 differs (3 replacements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

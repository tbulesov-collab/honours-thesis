#!/usr/bin/env python3
"""Build benchmark and evaluator copies with a constant borrowing limit (GKKOC E.10 ii).

The thesis model's collateral limit rises linearly with ability,
theta(z_i) = 1 + (theta_max - 1)(i - 1)/(nz - 1).  GKKOC's robustness check (ii) makes
it independent of ability, theta(z) = theta.  This copy changes the GKK_THETA_MAX block
of GKK_Main.f90 so the environment value sets one constant limit for every ability:

    theta(zi) = theta_max_override

It also carries the bounded interest-rate search of make_rbracket.py (start at the
current R, search [-0.1, 0.5]), which reproduced every previously converged result
exactly (OKIT follow-up checkpoints; pure-rents consistency 6.4e-11) and prevents the
interest-rate jump that stopped the capital-income-subsidy points under looser credit.
The live sources are not modified.

    variant_constant_theta/build/bench.a   benchmark solver
    variant_constant_theta/build/eval.a    policy evaluator

    python3 experiments/robustness_gkkoc_2022/make_constant_theta.py
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

THETA_OLD = ("\t\t\t\ttheta(zi) = 1.0_dp + (theta_max_override-1.0_dp)/(nz-1) &\n"
             "\t\t\t\t\t* (real(zi,dp)-1.0_dp)")
THETA_NEW = "\t\t\t\ttheta(zi) = theta_max_override   ! constant limit (robustness_gkkoc_2022 C6)"
PATCHES = {"GKK_Main.f90": [(THETA_OLD, THETA_NEW, 1)],
           "programfunctions.f90": [(RB_OLD, RB_NEW, 3)]}
BASE = HERE / "variant_constant_theta"


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

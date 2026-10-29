#!/usr/bin/env python3
"""Build the evaluator copies used by part B (subsidies beyond -50%).

The joint evaluator rejects capital-income taxes below -50% with an input check in
GKK_Main.f90 (no model calculation depends on that value):

    if ((env_status.ne.0).or.(tauK.lt.-0.50_dp).or.(tauK.gt.0.50_dp)) &

Two copies are built under experiments/robustness_gkkoc_2022/variant_partb/:

  guard     the check relaxed to -0.95; nothing else changed
  guard_rb  the same plus the bounded interest-rate search of make_rbracket.py, used only
            as a fallback for points that fail with "guard"

The live sources are not modified.  The script asserts the exact replacements and that
no other file differs, and writes provenance.json.

    python3 experiments/robustness_gkkoc_2022/make_partb.py
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

from make_rbracket import NEW as RB_NEW, OLD as RB_OLD     # noqa: E402
from make_variants import SOURCES, run, sha               # noqa: E402

GUARD_OLD = "(tauK.lt.-0.50_dp).or.(tauK.gt.0.50_dp)"
GUARD_NEW = "(tauK.lt.-0.95_dp).or.(tauK.gt.0.50_dp)"
BASE = HERE / "variant_partb"
BUILDS = {"guard": {"GKK_Main.f90": [(GUARD_OLD, GUARD_NEW, 1)]},
          "guard_rb": {"GKK_Main.f90": [(GUARD_OLD, GUARD_NEW, 1)],
                       "programfunctions.f90": [(RB_OLD, RB_NEW, 3)]}}


def build(name: str, patches: dict) -> dict:
    src, out = BASE / name / "src", BASE / name / "build"
    (out / "mod").mkdir(parents=True)
    src.mkdir(parents=True)
    for f in SOURCES:
        shutil.copy2(ROOT / f, src / f)
    for f, reps in patches.items():
        text = (src / f).read_text()
        for old, new, count in reps:
            if text.count(old) != count:
                raise SystemExit(f"{name}: expected {count} of {old!r} in {f}, found {text.count(old)}")
            text = text.replace(old, new)
        (src / f).write_text(text)
    plain = ["NRTYPE.F90", "NRUTIL.F90", "Toolbox.f90", "parameters.f90", "global.f90",
             "Opt_Tax_Parameters.f90"]
    omp = ["programfunctions.f90", "Simulation_Module.f90", "GKK_Stats.f90"]
    objects = []
    for f in plain + omp + ["Opt_Tax_Functions.f90"]:
        obj = f"../build/{Path(f).stem}.o"
        flags = (["-fopenmp", "-O3", "-fbounds-check", "-ffp-contract=off"] if f in omp else ["-O3"])
        run(["gfortran", *flags, "-J../build/mod", "-c", f, "-o", obj], src)
        objects.append(obj)
    run(["gfortran", "-fopenmp", "-fbounds-check", "-ffp-contract=off", "-O3",
         "-I../build/mod", "GKK_Main.f90", *objects, "-o", "../build/eval.a"], src)
    srcs = {p.name: sha(p) for p in sorted(src.iterdir()) if p.suffix.lower() == ".f90"}
    changed = sorted(f for f in SOURCES if srcs[f] != sha(ROOT / f))
    if changed != sorted(patches):
        raise SystemExit(f"{name}: unexpected source differences {changed}")
    print(f"built {name}: changed {changed}", flush=True)
    return {"patches": {f: [{"old": o, "new": n, "count": c} for o, n, c in r] for f, r in patches.items()},
            "sources_sha256": srcs, "eval_sha256": sha(out / "eval.a")}


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)
    provenance = {"live_sources_sha256": {f: sha(ROOT / f) for f in SOURCES}}
    for name, patches in BUILDS.items():
        provenance[name] = build(name, patches)
    (BASE / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

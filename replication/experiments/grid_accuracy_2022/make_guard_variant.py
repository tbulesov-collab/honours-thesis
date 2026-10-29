#!/usr/bin/env python3
"""Build subsidy-guard evaluators for the asset-grid check of the extended policies.

The joint evaluator rejects capital-income taxes below -50% with an input check in
GKK_Main.f90 (no model calculation depends on that value):

    if ((env_status.ne.0).or.(tauK.lt.-0.50_dp).or.(tauK.gt.0.50_dp)) &

The reported 80% and 95% subsidy results used experiments/robustness_gkkoc_2022/
variant_partb/guard, where only this check is relaxed to -0.95 (make_partb.py). This
script applies the same single replacement to the grid builds made by make_grid_variant.py:

    variants/na<N>/src  ->  variants/na<N>_guard/build/eval.a     (N = 201, 301, 401)

Only eval.a is built; the benchmarks of run_grid_check.py are reused unchanged. The source
copy is checked against variants/na<N>/provenance.json, the replacement must occur exactly
once, and no other file may differ. For N = 201 the new eval.a is compared byte for byte
with variant_partb/guard, which confirms the build reproduces the evaluator behind the
reported extended results.

    python3 experiments/grid_accuracy_2022/make_guard_variant.py --dry-run
    python3 experiments/grid_accuracy_2022/make_guard_variant.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "experiments" / "model_spec_sensitivity_2022"),
                str(ROOT / "experiments" / "robustness_gkkoc_2022")]

from make_partb import GUARD_NEW, GUARD_OLD                    # noqa: E402
from make_variants import SOURCES, run, sha                    # noqa: E402

PARTB_GUARD = ROOT / "experiments" / "robustness_gkkoc_2022" / "variant_partb"
GRIDS = (201, 301, 401)


def source_record(na: int) -> dict:
    """The grid build's sources, checked against its provenance."""
    base = HERE / "variants" / f"na{na}"
    prov_file = base / "provenance.json"
    if not prov_file.exists():
        raise SystemExit(f"{base.relative_to(ROOT)} not built; run make_grid_variant.py --na {na}")
    prov = json.loads(prov_file.read_text())
    for name in SOURCES:
        if sha(base / "src" / name) != prov["sources_sha256"][name]:
            raise SystemExit(f"{base.relative_to(ROOT)}/src/{name} differs from its recorded build; stop")
    count = (base / "src" / "GKK_Main.f90").read_text().count(GUARD_OLD)
    if count != 1:
        raise SystemExit(f"expected one {GUARD_OLD!r} in na{na}/src/GKK_Main.f90, found {count}")
    return prov


def build(na: int, prov: dict) -> dict:
    origin = HERE / "variants" / f"na{na}" / "src"
    base = HERE / "variants" / f"na{na}_guard"
    src, out = base / "src", base / "build"
    if base.exists():
        shutil.rmtree(base)
    (out / "mod").mkdir(parents=True)
    src.mkdir(parents=True)
    for name in SOURCES:
        shutil.copy2(origin / name, src / name)
    main = src / "GKK_Main.f90"
    main.write_text(main.read_text().replace(GUARD_OLD, GUARD_NEW))

    # Compiler commands identical to make_grid_variant.build() and make_partb.build().
    plain = ["NRTYPE.F90", "NRUTIL.F90", "Toolbox.f90", "parameters.f90", "global.f90",
             "Opt_Tax_Parameters.f90"]
    omp = ["programfunctions.f90", "Simulation_Module.f90", "GKK_Stats.f90"]
    objects = []
    for name in plain + omp + ["Opt_Tax_Functions.f90"]:
        obj = f"../build/{Path(name).stem}.o"
        flags = (["-fopenmp", "-O3", "-fbounds-check", "-ffp-contract=off"] if name in omp else ["-O3"])
        run(["gfortran", *flags, "-J../build/mod", "-c", name, "-o", obj], src)
        objects.append(obj)
    run(["gfortran", "-fopenmp", "-fbounds-check", "-ffp-contract=off", "-O3",
         "-I../build/mod", "GKK_Main.f90", *objects, "-o", "../build/eval.a"], src)

    sources = {name: sha(src / name) for name in SOURCES}
    changed = sorted(n for n in SOURCES if sources[n] != prov["sources_sha256"][n])
    if changed != ["GKK_Main.f90"]:
        raise SystemExit(f"na{na}_guard: unexpected source differences {changed}")
    record = {"na": na, "fine_na": prov["fine_na"], "copied_from": str(origin.relative_to(ROOT)),
              "patch": {"file": "GKK_Main.f90", "old": GUARD_OLD, "new": GUARD_NEW, "count": 1},
              "files_changed_vs_grid_build": changed, "sources_sha256": sources,
              "executables_sha256": {"eval.a": sha(out / "eval.a")}}
    if na == 201:
        partb = json.loads((PARTB_GUARD / "provenance.json").read_text())["guard"]["eval_sha256"]
        record["identical_to_partb_guard"] = record["executables_sha256"]["eval.a"] == partb
    (base / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--na", default=",".join(map(str, GRIDS)), help="subset of 201,301,401")
    ap.add_argument("--dry-run", action="store_true", help="check sources and the patch; compile nothing")
    args = ap.parse_args()
    grids = [int(x) for x in args.na.split(",") if x.strip()]
    if any(g not in GRIDS for g in grids):
        ap.error(f"--na must be a subset of {GRIDS}")
    provs = {na: source_record(na) for na in grids}
    for na in grids:
        print(f"{'would build' if args.dry_run else 'building'} variants/na{na}_guard/build/eval.a "
              f"from variants/na{na}/src (na={provs[na]['na']}, fine_na={provs[na]['fine_na']})", flush=True)
    if args.dry_run:
        print("dry run: grid sources match their recorded builds and the check occurs once; "
              "nothing was written or compiled.")
        return 0
    for na in grids:
        record = build(na, provs[na])
        note = ""
        if "identical_to_partb_guard" in record:
            note = ("; eval.a byte-identical to variant_partb/guard" if record["identical_to_partb_guard"]
                    else "; eval.a differs from variant_partb/guard: check before relying on the comparison")
        print(f"built variants/na{na}_guard (changed: {record['files_changed_vs_grid_build']}){note}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

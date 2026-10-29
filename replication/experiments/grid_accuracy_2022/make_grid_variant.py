#!/usr/bin/env python3
"""Build copies of the control model with a different asset grid (thesis Appendix A.3).

na and fine_na are compile-time constants in parameters.f90

    INTEGER(I4B), PARAMETER  :: na=201, fine_na=801

so a finer grid needs its own build.  The sources are copied from the control variant of
model_spec_sensitivity_2022 (variants/control/src), the build behind the freshly solved
standard-grid results reported in thesis Section 7.3.  They are first checked against
that build's provenance; only the grid line of parameters.f90 is changed, and the
compiler commands are those of make_variants.py.  fine_na keeps the original relation
fine_na = 4*(na-1)+1 unless --fine-na is given.

    variants/na301/build/bench.a   benchmark solver   (na=301, fine_na=1201)
    variants/na301/build/eval.a    policy evaluator
    variants/na201/build/...       reference rebuild of the standard grid (default); its
                                   executables are compared byte for byte with the control
                                   build to confirm that the toolchain reproduces it

Nothing is solved here.  The live sources and the control variant are never modified.

    python3 experiments/grid_accuracy_2022/make_grid_variant.py --dry-run
    python3 experiments/grid_accuracy_2022/make_grid_variant.py
    python3 experiments/grid_accuracy_2022/make_grid_variant.py --na 401 --no-reference
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SENS = ROOT / "experiments" / "model_spec_sensitivity_2022"
sys.path.insert(0, str(SENS))

from make_variants import SOURCES, bench_main, run, sha        # noqa: E402

CONTROL = SENS / "variants" / "control"
PROVENANCE = SENS / "variants" / "provenance.json"
GRID_LINE = "na=201, fine_na=801"
STANDARD_NA = 201


def fine_for(na: int) -> int:
    return 4 * (na - 1) + 1


def control_provenance() -> dict:
    """Check that the control sources are those of its recorded build."""
    prov = json.loads(PROVENANCE.read_text())["control"]
    for name in SOURCES + ["GKK_Main_bench.f90"]:
        path = CONTROL / "src" / name
        if not path.exists() or sha(path) != prov["sources_sha256"][name]:
            raise SystemExit(f"control source {name} differs from its recorded build; stop")
    for exe in ("bench.a", "eval.a"):
        if sha(CONTROL / "build" / exe) != prov["executables_sha256"][exe]:
            raise SystemExit(f"control executable {exe} differs from its recorded build; stop")
    live_changed = [n for n in SOURCES if sha(ROOT / n) != prov["sources_sha256"][n]]
    if live_changed:
        print(f"note: live sources changed since the control build: {live_changed}. "
              "The grid builds still copy the control sources, so the comparison stays "
              "like for like with the reported control results.")
    text = (CONTROL / "src" / "parameters.f90").read_text()
    if text.count(GRID_LINE) != 1:
        raise SystemExit(f"expected exactly one {GRID_LINE!r} in the control parameters.f90")
    return prov


def build(na: int, fine_na: int, prov: dict) -> dict:
    base = HERE / "variants" / f"na{na}"
    src, out = base / "src", base / "build"
    if base.exists():
        shutil.rmtree(base)
    (out / "mod").mkdir(parents=True)
    src.mkdir(parents=True)
    for name in SOURCES:
        shutil.copy2(CONTROL / "src" / name, src / name)
    params = src / "parameters.f90"
    text = params.read_text()
    params.write_text(text.replace(GRID_LINE, f"na={na}, fine_na={fine_na}"))
    (src / "GKK_Main_bench.f90").write_text(bench_main((src / "GKK_Main.f90").read_text()))

    # Compiler commands identical to make_variants.build().
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

    sources = {p.name: sha(p) for p in sorted(src.iterdir()) if p.suffix.lower() == ".f90"}
    changed = sorted(n for n, h in sources.items() if h != prov["sources_sha256"][n])
    expected = [] if na == STANDARD_NA and fine_na == fine_for(STANDARD_NA) else ["parameters.f90"]
    if changed != expected:
        raise SystemExit(f"unexpected source differences from the control build: {changed}")
    executables = {e: sha(out / e) for e in ("bench.a", "eval.a")}
    record = {"na": na, "fine_na": fine_na, "copied_from": str(CONTROL.relative_to(ROOT) / "src"),
              "patch": {"file": "parameters.f90", "old": GRID_LINE,
                        "new": f"na={na}, fine_na={fine_na}"},
              "files_changed_vs_control": changed, "sources_sha256": sources,
              "executables_sha256": executables}
    if not expected:
        record["identical_to_control_build"] = {
            e: executables[e] == prov["executables_sha256"][e] for e in executables}
    (base / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--na", type=int, default=301, help="asset-grid nodes for the check (default 301)")
    ap.add_argument("--fine-na", type=int, default=None,
                    help="fine-grid nodes (default 4*(na-1)+1, the original relation)")
    ap.add_argument("--no-reference", action="store_true",
                    help="skip the na=201 reference rebuild")
    ap.add_argument("--dry-run", action="store_true",
                    help="check the control sources and the patch; write and compile nothing")
    args = ap.parse_args()
    fine_na = args.fine_na if args.fine_na is not None else fine_for(args.na)
    if args.na < 2 or fine_na < args.na:
        ap.error("need na >= 2 and fine_na >= na")
    prov = control_provenance()
    grids = [(args.na, fine_na)]
    if not args.no_reference and (args.na, fine_na) != (STANDARD_NA, fine_for(STANDARD_NA)):
        grids.insert(0, (STANDARD_NA, fine_for(STANDARD_NA)))
    for na, fn in grids:
        target = HERE / "variants" / f"na{na}"
        print(f"{'would build' if args.dry_run else 'building'} {target.relative_to(ROOT)} "
              f"(na={na}, fine_na={fn}) from {CONTROL.relative_to(ROOT)}/src", flush=True)
    if args.dry_run:
        print("dry run: control sources and executables match their recorded build; "
              f"the grid line occurs once; nothing was written or compiled.")
        return 0
    for na, fn in grids:
        record = build(na, fn, prov)
        note = ""
        if "identical_to_control_build" in record:
            same = record["identical_to_control_build"]
            note = ("; executables byte-identical to the control build" if all(same.values())
                    else f"; executables differ from the control build ({same}) although sources, "
                         "flags and compiler match: check before relying on the comparison")
        print(f"built variants/na{na} (changed vs control: {record['files_changed_vs_control']}){note}",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

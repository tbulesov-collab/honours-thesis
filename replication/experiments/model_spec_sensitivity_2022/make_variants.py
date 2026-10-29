#!/usr/bin/env python3
"""Build four model variants that differ only in how two published-model features
are implemented, so their effect on the benchmark and headline policies can be measured.

    control       live sources, unchanged
    productivity  below-median ability types start at base productivity z (GKKOC eq. 3)
    timing        expectations at the last working age keep the earnings shock that
                  fixes the pension, y_R(kappa, e_{R-1}), as the distribution already does
    both          both corrections

The live sources in the repository root are never modified.  Each variant gets its own
copy under variants/<name>/src, and two executables under variants/<name>/build:
bench.a (solves the benchmark from scratch) and eval.a (the joint-policy evaluator used by
tools/policy_evaluation.py).  Every patch asserts the exact number of replacements.

    python3 experiments/model_spec_sensitivity_2022/make_variants.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ["NRTYPE.F90", "NRUTIL.F90", "Toolbox.f90", "parameters.f90", "global.f90",
           "programfunctions.f90", "Simulation_Module.f90", "GKK_Stats.f90",
           "Opt_Tax_Parameters.f90", "Opt_Tax_Functions.f90", "GKK_Main.f90"]
VARIANTS = {"control": (), "productivity": ("productivity",), "timing": ("timing",),
            "both": ("productivity", "timing")}

PR_E_NEXT = """
!========================================================================================
! Pr_e_Next: distribution of next period's earnings shock given age and current shock.
! The stationary distribution (FIND_DBN_EQ) redraws e only between working ages
! 1..RetAge-1 and keeps it from the last working age on, because the pension depends on
! the shock at that age, y_R(kappa, e_{R-1}) (GKKOC, Section 3).  Expectations over e'
! must use the same timing.  [model_spec_sensitivity_2022 timing correction]

FUNCTION Pr_e_Next(age_in,e_in) RESULT(prob)
	IMPLICIT NONE
	integer, intent(in) :: age_in, e_in
	real(dp)            :: prob(ne)
	if (age_in.lt.RetAge-1) then
		prob = pr_e(e_in,:)
	else
		prob       = 0.0_dp
		prob(e_in) = 1.0_dp
	endif
END FUNCTION Pr_e_Next

"""

# Routine name -> (old text, new text, expected count) for the timing correction.
TIMING_SITES = {
    "FOC_WH": ("pr_e(e_in,:)", "Pr_e_Next(age_in,e_in)", 4),
    "FOC_WH_Transition": ("pr_e(e_in,:)", "Pr_e_Next(age_in,e_in)", 4),
    "FOC_H_NSU": ("pr_e(e_in,:)", "Pr_e_Next(age_in,e_in)", 1),
    "FOC_H_NSU_Transition": ("pr_e(e_in,:)", "Pr_e_Next(age_in,e_in)", 1),
    "EGM_Working_Period": ("pr_e(ei,:)", "Pr_e_Next(age,ei)", 4),
    "EGM_Working_Period_Transition": ("pr_e(ei,:)", "Pr_e_Next(age,ei)", 4),
    "COMPUTE_VALUE_FUNCTION_LINEAR": ("pr_e(ei,:)", "Pr_e_Next(age,ei)", 2),
    "Firm_Value": ("pr_e(ei,:)", "Pr_e_Next(age,ei)", 1),
}

PRODUCTIVITY_OLD = """				xz_grid(1,:)   = exp(log(zgrid)*xgrid(1))
				xz_grid(2,1:4) = xz_grid(1,1:4); xz_grid(2,5:) = exp(log(zgrid(5:))*xgrid(2));"""
PRODUCTIVITY_NEW = """				! GKKOC eq. (3): only above-median types (z > z_median = 1, nodes 5:nz) start in
				! the fast lane with productivity z**x_hi; the others start at base level z.
				! [model_spec_sensitivity_2022 productivity correction]
				if (abs(zgrid(4)-1.0_dp).gt.1.0e-12_dp .or. zgrid(5).le.1.0_dp) &
					& error stop 'Median ability node is not zgrid(4)=1'
				xz_grid(1,1:4) = zgrid(1:4); xz_grid(1,5:) = exp(log(zgrid(5:))*xgrid(1))
				xz_grid(2,:)   = exp(log(zgrid)*xgrid(2))"""


def routine_span(text: str, name: str) -> tuple[int, int]:
    """Start and end offsets of a FUNCTION/SUBROUTINE named exactly `name`."""
    start = re.search(rf"^[ \t]*(FUNCTION|Function|SUBROUTINE|Subroutine)[ \t]+{name}[ \t]*\(",
                      text, re.M)
    if not start:
        raise SystemExit(f"routine {name} not found")
    end = re.search(rf"^[ \t]*END[ \t]*(FUNCTION|Function|SUBROUTINE|Subroutine)[ \t]+{name}\b",
                    text[start.end():], re.M | re.I)
    if not end:
        raise SystemExit(f"end of routine {name} not found")
    return start.start(), start.end() + end.end()


def patch_timing(text: str) -> str:
    for name, (old, new, expected) in TIMING_SITES.items():
        a, b = routine_span(text, name)
        body = text[a:b]
        found = body.count(old)
        if found != expected:
            raise SystemExit(f"{name}: expected {expected} x {old}, found {found}")
        text = text[:a] + body.replace(old, new) + text[b:]
    anchor = "Subroutine Asset_Grid_Threshold(Y_a_threshold_in,agrid_t,na_t)"
    if text.count(anchor) != 1:
        raise SystemExit("insertion point for Pr_e_Next not found")
    return text.replace(anchor, PR_E_NEXT.lstrip("\n") + anchor)


def patch_productivity(text: str) -> str:
    if text.count(PRODUCTIVITY_OLD) != 1:
        raise SystemExit("productivity lines not found exactly once")
    return text.replace(PRODUCTIVITY_OLD, PRODUCTIVITY_NEW)


def set_switch(text: str, name: str, value: bool) -> str:
    """Set the first assignment of a logical switch, as tools/run_mac.sh set_bool does."""
    pattern = re.compile(rf"^([ \t]*{name}[ \t]*=[ \t]*)\.(true|false)\.", re.M | re.I)
    if not pattern.search(text):
        raise SystemExit(f"switch {name} not found")
    return pattern.sub(lambda m: m.group(1) + (".true." if value else ".false."), text, count=1)


def bench_main(text: str) -> str:
    """Mirror tools/run_mac.sh configure_mode bench-recompute."""
    for name in ["Benchmark_Only", "Tax_Reform", "Tax_Reform_tktw", "Opt_Tax", "Opt_Threshold",
                 "Transition_Tax_Reform", "Transition_OT", "Simul_Switch", "compute_exp",
                 "compute_exp_pf", "compute_exp_prices"]:
        text = set_switch(text, name, False)
    text = set_switch(text, "Benchmark_Only", True)
    return set_switch(text, "compute_bench", True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], cwd: Path) -> None:
    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"failed in {cwd}: {' '.join(cmd)}\n{done.stdout[-3000:]}{done.stderr[-3000:]}")


def build(variant: str, patches: tuple[str, ...]) -> dict:
    base = HERE / "variants" / variant
    src, out = base / "src", base / "build"
    if base.exists():
        shutil.rmtree(base)
    (out / "mod").mkdir(parents=True)
    src.mkdir(parents=True)
    for name in SOURCES:
        shutil.copy2(ROOT / name, src / name)
    pf = src / "programfunctions.f90"
    text = pf.read_text()
    if "productivity" in patches:
        text = patch_productivity(text)
    if "timing" in patches:
        text = patch_timing(text)
    pf.write_text(text)
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
    return {"patches": list(patches),
            "sources_sha256": {p.name: sha(p) for p in sorted(src.iterdir()) if p.suffix.lower() == ".f90"},
            "executables_sha256": {e: sha(out / e) for e in ["bench.a", "eval.a"]},
            "live_sources_sha256": {n: sha(ROOT / n) for n in SOURCES}}


def main() -> int:
    provenance = {}
    for variant, patches in VARIANTS.items():
        print(f"building {variant} {patches}", flush=True)
        provenance[variant] = build(variant, patches)
    control = provenance["control"]["sources_sha256"]
    for variant, info in provenance.items():
        changed = sorted(k for k, v in info["sources_sha256"].items()
                         if k != "GKK_Main_bench.f90" and v != control[k])
        info["files_changed_vs_control"] = changed
        print(f"  {variant}: files changed vs control = {changed}")
    if any(provenance["control"]["sources_sha256"][n] != provenance["control"]["live_sources_sha256"][n]
           for n in SOURCES):
        raise SystemExit("control sources differ from the live sources")
    (HERE / "variants" / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

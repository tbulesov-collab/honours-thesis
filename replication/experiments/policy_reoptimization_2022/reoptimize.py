#!/usr/bin/env python3
"""Re-optimise the reported policies under the re-calibrated parameters.

The re-calibration sensitivity (experiments/model_spec_sensitivity_2022/recalibrate.py)
evaluated the reported policies at their reported rates.  Under the re-calibrated
parameters the three-tax candidate (estate tax ~0, capital-income subsidy at its -30%
bound) overtook the estate-fixed candidates (estate tax 40%, subsidy ~-50%).  Neither
reported search could reach the region between them: the three-tax search stopped at
a -30% subsidy and the nested search held the estate tax at 40%.  The estate-tax sweep
at the optimal wealth tax (calibration/runs/estate_tax_grid_2022) raises newborn CE2
by about 1 point per 10 points of estate tax removed, so that region is the most
promising one to examine.

    phase 1  grids, run --max-parallel at a time:
             recal  tau_bq = 40%  tau_w {3,5,7}% x tau_k {0,-10,...,-50}%   (the reported
                                   grid, re-calibrated)
             recal  tau_bq = 0    same 18 points
             thesis tau_bq = 0    same 18 points, reported calibration and saved benchmark
                                  (its tau_bq = 40% grid is calibration/runs/
                                  subsidy_cap_grid_2022)
             recal  separate-optimum sweeps: OWT tau_w {2, 2.5, 3.5, 4}% (tau_k 0) and OKIT
                                  tau_k {-22, -18, -10, -6}% (tau_w 0), tau_bq 40%; the
                                  reported rates come from recal_results.json
             Grid points are ordered by subsidy size, largest first, so early results
             cover the promising region.
    phase 2  one wide search under the re-calibrated parameters, all three taxes free:
             tau_w [0, 8%], tau_k [-50%, 25%] (-50% is the executable's guard),
             tau_bq [0, 80%].  The algorithm of tools/optimize_joint_taxes.py (anchors,
             differential evolution with 2 generations and population 4, then bounded
             Powell with at most 45 evaluations) and its objective; the global stage
             evaluates --max-parallel candidates at once (updating="deferred").  It
             starts from the best phase-1 point.

"recal" is the re-calibrated original code (the control arm of recalibrate.py): its
benchmark, parameters and executable (variants/control/build/eval.a, built from the
live sources).  "thesis" uses the same executable with the reported calibration and
the saved benchmark (business_financing_2022/rn_reform), so it is directly comparable
with the reported grid.  Outputs go only under experiments/policy_reoptimization_2022/.
Re-running resumes from the evaluator cache.

    python3 experiments/policy_reoptimization_2022/reoptimize.py --check-only
    python3 experiments/policy_reoptimization_2022/reoptimize.py
    python3 experiments/policy_reoptimization_2022/reoptimize.py --summary-only
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SENS = ROOT / "experiments" / "model_spec_sensitivity_2022"
sys.path[:0] = [str(ROOT / "tools"), str(SENS)]

import optimize_joint_taxes as ojt                                  # noqa: E402
import recalibrate as rc                                            # noqa: E402
from policy_evaluation import PolicyEvaluator, atomic_json          # noqa: E402
from run_sensitivity import JOINT                                   # noqa: E402
from scipy.optimize import differential_evolution, minimize         # noqa: E402

EXE = SENS / "variants" / "control" / "build" / "eval.a"
RECAL_FIN = SENS / "recal" / "control" / "financing.json"
RECAL_RESULTS = SENS / "recal_results.json"
THESIS_BENCH = ROOT / "calibration" / "runs" / "business_financing_2022" / "rn_reform"
THESIS_GRID = ROOT / "calibration" / "runs" / "subsidy_cap_grid_2022" / "all_results.csv"
HEADLINE = ROOT / "calibration" / "runs" / "headline_revalidation_2022" / "validated_headline.json"
RUNS = HERE / "runs"
LOCK = RUNS / "driver.lock"
OTHER_LOCKS = [SENS / "recal" / "driver.lock", SENS / "runs" / "driver.lock"]

WIDE = ((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0))      # evaluator bounds for fixed-rate points
LABOR_BOUNDS = (0.0, 0.60)
BUDGET_TOLERANCE = 1.0e-4
TAU_W = (0.03, 0.05, 0.07)
TAU_K = (0.0, -0.10, -0.20, -0.30, -0.40, -0.50)
OWT_W = (0.020, 0.025, 0.035, 0.040)
OKIT_K = (-0.22, -0.18, -0.10, -0.06)
SEARCH_BOUNDS = ((0.0, 0.08), (-0.50, 0.25), (0.0, 0.80))
OWT, OKIT = (0.030618034, 0.0, 0.40), (0.0, -0.13618034, 0.40)
# Edge sweep: phase 1 put the best grid point at the -50% subsidy guard with no estate
# tax, so the remaining choice is the wealth tax along that edge (the executable
# accepts tau_w up to 20%).
EDGE_W = (0.06, 0.075, 0.08, 0.09, 0.10)
EDGE_K, EDGE_BQ = -0.50, 0.0
NOISE_PP = 0.15


def jobs() -> list[tuple[str, str, tuple[float, float, float]]]:
    """(calibration, group, rates), promising region first."""
    grid = [(cal, group, (w, k, bq))
            for k in sorted(TAU_K)                   # -50% first
            for cal, group, bq in (("thesis", "grid_bq0", 0.0), ("recal", "grid_bq0", 0.0),
                                   ("recal", "grid_bq40", 0.40))
            for w in sorted(TAU_W, reverse=True)]
    separate = ([("recal", "owt", (w, 0.0, 0.40)) for w in OWT_W]
                + [("recal", "okit", (0.0, k, 0.40)) for k in OKIT_K])
    return grid + separate


def edge_jobs() -> list[tuple[str, str, tuple[float, float, float]]]:
    return [(cal, "edge", (w, EDGE_K, EDGE_BQ)) for w in EDGE_W for cal in ("thesis", "recal")]


def recal_env() -> dict[str, str]:
    return rc.param_env(json.loads(RECAL_FIN.read_text())["parameters"])


def recal_benchmark() -> Path:
    return ROOT / json.loads(RECAL_FIN.read_text())["benchmark"]


class SearchEvaluator(PolicyEvaluator):
    objective = ojt.Evaluator.objective          # -CE2, penalised if infeasible


def make_evaluators(threads: int) -> dict[str, PolicyEvaluator]:
    common = dict(root=ROOT, executable=EXE, threads=threads, labor_bounds=LABOR_BOUNDS,
                  budget_tolerance=BUDGET_TOLERANCE, fixed_labor=False)
    return {"recal": PolicyEvaluator(benchmark=recal_benchmark(), run_root=RUNS / "recal",
                                     bounds=WIDE, calibration_env=recal_env(), **common),
            "thesis": PolicyEvaluator(benchmark=THESIS_BENCH, run_root=RUNS / "thesis",
                                      bounds=WIDE, calibration_env=None, **common)}


# ------------------------------------------------------------------ phase 1: grids

def phase_grid(evaluators: dict, max_parallel: int, todo=None,
               out: str = "grid_points.json") -> None:
    todo = jobs() if todo is None else todo

    def run(job):
        cal, group, rates = job
        try:
            r = evaluators[cal].evaluate_rates(rates)
            return job, {"status": "ok", **r}
        except Exception as exc:                  # one failure must not stop the batch
            return job, {"status": "failed", "error": str(exc)}

    print(f"{out}: {len(todo)} points, {max_parallel} at a time", flush=True)
    records = []
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        for (cal, group, rates), r in pool.map(run, todo):
            records.append({"calibration": cal, "group": group, "rates": list(rates), **r})
            print(f"[{cal} {group}] w={rates[0]:.3f} k={rates[1]:+.3f} bq={rates[2]:.2f}: "
                  + (f"CE2 {r['ce2_newborn']:.3f}" if r["status"] == "ok" else f"FAILED {r['error']}"),
                  flush=True)
    for ev in evaluators.values():
        ev.write_index()
    atomic_json(RUNS / out, records)


# ----------------------------------------------------------------- phase 2: search

def phase_search(threads: int, max_parallel: int, seed: int) -> None:
    grid = [r for r in json.loads((RUNS / "grid_points.json").read_text())
            if r["calibration"] == "recal" and r["status"] == "ok"
            and r["group"].startswith("grid") and r.get("feasible")]
    if not grid:
        raise SystemExit("no feasible re-calibrated grid point; run phase 1 first")
    grid.sort(key=lambda r: -r["ce2_newborn"])
    ev = SearchEvaluator(root=ROOT, executable=EXE, benchmark=recal_benchmark(),
                         run_root=RUNS / "recal_search", threads=threads, bounds=SEARCH_BOUNDS,
                         labor_bounds=LABOR_BOUNDS, budget_tolerance=BUDGET_TOLERANCE,
                         fixed_labor=False, calibration_env=recal_env())

    def inside(rates) -> bool:
        return all(lo <= x <= hi for x, (lo, hi) in zip(rates, SEARCH_BOUNDS))

    start = tuple(grid[0]["rates"])
    anchors = [start, *(tuple(r["rates"]) for r in grid[1:3]), *JOINT.values(), OWT, OKIT]
    anchors = [a for i, a in enumerate(anchors) if inside(a) and a not in anchors[:i]]
    print(f"phase 2: {len(anchors)} anchors, start {start}", flush=True)
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        list(pool.map(lambda a: ev.objective(ojt.rates_to_scaled(a, SEARCH_BOUNDS)), anchors))
        print("\n[stage 1] differential evolution", flush=True)
        glob = differential_evolution(
            ev.objective, bounds=[(0.0, 1.0)] * 3, maxiter=2, popsize=4, seed=seed,
            polish=False, workers=pool.map, updating="deferred", disp=True,
            x0=np.clip(ojt.rates_to_scaled(start, SEARCH_BOUNDS), 0.0, 1.0))
    print("\n[stage 2] bounded Powell refinement", flush=True)
    local = minimize(ev.objective, x0=np.clip(glob.x, 0.0, 1.0), method="Powell",
                     bounds=[(0.0, 1.0)] * 3,
                     options={"xtol": 0.01, "ftol": 1.0e-4, "maxfev": 45, "disp": True})
    valid = [r for r in ev.results if ev.is_feasible(r)]
    if not valid:
        raise SystemExit("no feasible candidate in the search")
    best = max(valid, key=lambda r: float(r["ce2_newborn"]))
    flags = {}
    for name, (lo, hi) in zip(("tau_w", "tau_k", "tau_bq"), SEARCH_BOUNDS):
        if float(best[name]) - lo <= 0.01 * (hi - lo):
            flags[name] = "lower"
        elif hi - float(best[name]) <= 0.01 * (hi - lo):
            flags[name] = "upper"
    atomic_json(RUNS / "search_best.json", {
        "context_id": ev.context_id, "bounds": SEARCH_BOUNDS, "start": start,
        "anchors": anchors, "evaluations": len(ev.results),
        "optimizer_status": {"global_message": str(glob.message),
                             "local_success": bool(local.success),
                             "local_message": str(local.message), "boundary_flags": flags},
        "best": best})
    ev.write_index()
    print(f"search best: w={best['tau_w']:.4f} k={best['tau_k']:+.4f} bq={best['tau_bq']:.4f} "
          f"CE2 {best['ce2_newborn']:.3f}  bounds hit: {flags or 'none'}", flush=True)


# ------------------------------------------------------------------------ summary

def summarise() -> None:
    lines = ["# Policy re-optimisation under the re-calibrated parameters", "",
             "Newborn CE2 (%).  recal: re-calibrated original code, own benchmark.  thesis: "
             "reported calibration, saved benchmark (as in the reported tables).", ""]
    pts = json.loads((RUNS / "grid_points.json").read_text()) if (RUNS / "grid_points.json").exists() else []
    ok = [p for p in pts if p["status"] == "ok"]
    thesis40 = []
    if THESIS_GRID.exists():
        for r in csv.DictReader(THESIS_GRID.open()):
            thesis40.append({"calibration": "thesis", "group": "grid_bq40", "status": "ok",
                             "rates": [float(r["tau_w"]), float(r["tau_k"]), float(r["tau_bq"])],
                             "ce2_newborn": float(r["ce2_newborn"]), "feasible": True})
    best = {}
    for cal, group, title in (("thesis", "grid_bq40", "Reported calibration, estate tax 40% (reported grid)"),
                              ("thesis", "grid_bq0", "Reported calibration, estate tax 0"),
                              ("recal", "grid_bq40", "Re-calibrated, estate tax 40%"),
                              ("recal", "grid_bq0", "Re-calibrated, estate tax 0")):
        cell = {(round(p["rates"][0], 4), round(p["rates"][1], 4)): p
                for p in (thesis40 if (cal, group) == ("thesis", "grid_bq40") else ok)
                if p["calibration"] == cal and p["group"] == group}
        if not cell:
            continue
        top = max(cell.values(), key=lambda p: p["ce2_newborn"])
        best[(cal, group)] = top
        lines += [f"## {title}", "", "| tau_w \\ tau_k | " + " | ".join(f"{100*k:+.0f}%" for k in TAU_K) + " |",
                  "|---|" + "---:|" * len(TAU_K)]
        for w in TAU_W:
            row = []
            for k in TAU_K:
                p = cell.get((round(w, 4), round(k, 4)))
                v = "—" if p is None else f"{p['ce2_newborn']:.2f}" + ("" if p.get("feasible", True) else "*")
                row.append(f"**{v}**" if p is top else v)
            lines.append(f"| {100*w:.0f}% | " + " | ".join(row) + " |")
        lines += [""]
    lines += ["`*` misses the revenue tolerance.  Bold: highest in the table.", ""]
    for cal in ("thesis", "recal"):
        a, b = best.get((cal, "grid_bq0")), best.get((cal, "grid_bq40"))
        if a and b:
            lines.append(f"- {cal}: best at estate tax 0 minus best at 40% = "
                         f"{a['ce2_newborn'] - b['ce2_newborn']:+.2f} pp")
    if RECAL_RESULTS.exists():
        rep = json.loads(RECAL_RESULTS.read_text())["arms"]["control"]["policies"]
        sep = {g: [p for p in ok if p["calibration"] == "recal" and p["group"] == g] for g in ("owt", "okit")}
        for g, rates in (("owt", OWT), ("okit", OKIT)):
            if g in rep:
                sep[g].append({"rates": list(rates), "ce2_newborn": rep[g]["ce2_newborn"]})
        if sep["owt"] and sep["okit"]:
            bo = max(sep["owt"], key=lambda p: p["ce2_newborn"])
            bk = max(sep["okit"], key=lambda p: p["ce2_newborn"])
            lines += ["", "## Separate optima, re-calibrated (tau_bq 40%)", "",
                      "| Wealth tax | " + " | ".join(f"{100*p['rates'][0]:.2f}%" for p in sorted(sep['owt'], key=lambda p: p['rates'][0])) + " |",
                      "|---|" + "---:|" * len(sep["owt"]),
                      "| CE2 | " + " | ".join(f"{p['ce2_newborn']:.2f}" for p in sorted(sep['owt'], key=lambda p: p['rates'][0])) + " |", "",
                      "| Capital-income tax | " + " | ".join(f"{100*p['rates'][1]:+.1f}%" for p in sorted(sep['okit'], key=lambda p: p['rates'][1])) + " |",
                      "|---|" + "---:|" * len(sep["okit"]),
                      "| CE2 | " + " | ".join(f"{p['ce2_newborn']:.2f}" for p in sorted(sep['okit'], key=lambda p: p['rates'][1])) + " |", "",
                      f"Best OWT {bo['ce2_newborn']:.2f} at {100*bo['rates'][0]:.2f}%; best OKIT "
                      f"{bk['ce2_newborn']:.2f} at {100*bk['rates'][1]:+.1f}%; gap "
                      f"{bo['ce2_newborn'] - bk['ce2_newborn']:.2f} pp (fixed-rate gap in recal_results: "
                      f"{rep['owt']['ce2_newborn'] - rep['okit']['ce2_newborn']:.2f})."]
    edge = (json.loads((RUNS / "edge_points.json").read_text())
            if (RUNS / "edge_points.json").exists() else [])
    if edge:
        prof = {}
        for p in ok + [e for e in edge if e["status"] == "ok"]:
            if p["group"] in ("grid_bq0", "edge") and abs(p["rates"][1] - EDGE_K) < 1e-12 \
                    and abs(p["rates"][2] - EDGE_BQ) < 1e-12:
                prof.setdefault(p["calibration"], {})[round(p["rates"][0], 4)] = p
        ws = sorted({w for d in prof.values() for w in d})
        lines += ["", f"## Wealth tax along the edge (tau_k {100*EDGE_K:+.0f}%, estate tax 0)", "",
                  "| Calibration | " + " | ".join(f"{100*w:.1f}%" for w in ws) + " |",
                  "|---|" + "---:|" * len(ws)]
        notes = []
        for cal in ("thesis", "recal"):
            d = prof.get(cal, {})
            top = max(d.values(), key=lambda p: p["ce2_newborn"]) if d else None
            cells = []
            for w in ws:
                p = d.get(w)
                v = "—" if p is None else f"{p['ce2_newborn']:.2f}" + ("" if p.get("feasible", True) else "*")
                cells.append(f"**{v}**" if p is not None and p is top else v)
            lines.append(f"| {cal} | " + " | ".join(cells) + " |")
            if top:
                notes.append(f"- {cal}: best wealth tax on the edge {100*top['rates'][0]:.1f}%, "
                             f"CE2 {top['ce2_newborn']:.3f}, population CE2 {top['ce2_population']:.3f}, "
                             f"labour tax {100*top['tau_l']:.2f}%, output {top['output_growth']:+.2f}%, "
                             f"top 1% {100*top['top1_wealth_share']:.2f}%")
        lines += ["", *notes]
    if (RUNS / "search_best.json").exists():
        s = json.loads((RUNS / "search_best.json").read_text())
        b = s["best"]
        lines += ["", "## Wide three-tax search (re-calibrated)", "",
                  f"Best of {s['evaluations']} evaluations: tau_w {100*b['tau_w']:.3f}%, tau_k "
                  f"{100*b['tau_k']:+.3f}%, tau_bq {100*b['tau_bq']:.3f}%, labour tax "
                  f"{100*b['tau_l']:.2f}%, newborn CE2 {b['ce2_newborn']:.3f}% "
                  f"(population {b['ce2_population']:.3f}%, output {b['output_growth']:+.2f}%, "
                  f"top 1% {100*b['top1_wealth_share']:.2f}%).  Bounds hit: "
                  f"{s['optimizer_status']['boundary_flags'] or 'none'}."]
    (HERE / "results.md").write_text("\n".join(lines) + "\n")
    atomic_json(HERE / "results.json", {"grid_points": pts, "best_by_grid":
                                        {f"{c}:{g}": v for (c, g), v in best.items()}})
    print("\n".join(lines))


# --------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", choices=["grid", "edge", "search", "all"], default="all",
                        help="all = grid then search; edge = wealth-tax sweep on the "
                             "-50%%/estate-0 edge, both calibrations")
    parser.add_argument("--max-parallel", type=int, default=2,
                        help="evaluations at once; 2 was the most efficient on this Mac")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--dbn-max-iter", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=2022)
    parser.add_argument("--check-only", action="store_true", help="print the plan; solve nothing")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise()
        return 0
    rc.check_builds(["control"])
    for path in (RECAL_FIN, RECAL_RESULTS, HEADLINE, THESIS_BENCH / "output.txt"):
        if not path.exists():
            raise SystemExit(f"missing input: {path}")
    plan = jobs()
    if args.check_only:
        for cal, group, r in plan:
            print(f"{cal:6s} {group:9s} w={r[0]:.4f} k={r[1]:+.4f} bq={r[2]:.2f}")
        print(f"\n{len(plan)} grid evaluations, then a wide search (~85 evaluations) "
              f"with bounds {SEARCH_BOUNDS}.  Recal benchmark: {recal_benchmark()}.  "
              "Check only: nothing was run.")
        return 0
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)   # the evaluator inherits GKK_*
    RUNS.mkdir(parents=True, exist_ok=True)
    for lock in (LOCK, *OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                os.kill(pid, 0)
                raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass                                  # stale lock from a stopped run
    LOCK.write_text(str(os.getpid()))
    try:
        if args.phase in ("grid", "all"):
            phase_grid(make_evaluators(args.threads), args.max_parallel)
            summarise()
        if args.phase == "edge":
            phase_grid(make_evaluators(args.threads), args.max_parallel, edge_jobs(),
                       "edge_points.json")
            summarise()
        if args.phase in ("search", "all"):
            phase_search(args.threads, args.max_parallel, args.seed)
            summarise()
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

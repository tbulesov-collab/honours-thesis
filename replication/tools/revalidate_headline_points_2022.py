#!/usr/bin/env python3
"""Re-solve the paper's headline policy points under the validated evaluator.

Why this exists.  Every Section 5 result (the joint searches and the subsidy-cap
grid, 333 solves in total) and the fixed-labour search were produced before
tools/policy_evaluation.py gained its convergence checks.  Those solves stopped
once the distribution change fell below 1e-7 and never verified the aggregate
residual.  The same policy therefore scores differently depending on which code
computed it; the headline OWT policy gives newborn CE2 of 8.4431 in the Section 5
evaluator, 8.4913 in the validated evaluator, and 8.5089 in the optimal-tax
routine used for Section 4.

This script re-solves only the rows the paper reports, so that every welfare
number in Tables VII-IX comes from one numerical standard: equilibrium residual
below 1e-7, aggregate residual below 1e-6, iteration count within the cap, tax
rates and benchmark revenue verified.

Points re-solved (financing calibration, benchmark business_financing_2022/rn_reform):

    s5_1  three taxes, labour tax adjusts    (Table VIII row 1)
    s5_2  three taxes, labour tax fixed      (Table VIII row 2; fixed-labour build)
    s5_3  wealth-capital, estate tax fixed   (Table VIII row 3)
    s5_4  best subsidy-cap grid point        (Section 5.4, Figure 1, Table IX)

Points reused, not re-solved: OWT and OKIT at the financing calibration were
already solved under the validated evaluator by tools/theta_max_robustness_2022.py.
They are read from calibration/runs/theta_max_robustness_2022/financing/.

SAFETY.  Nothing under an existing run tree is written to.  Output goes to
calibration/runs/headline_revalidation_2022/.  Each point's outcome is stored in
its own file, so the comparison table always reflects every completed point, not
just the ones solved in the latest invocation.

Usage:

    python3 tools/revalidate_headline_points_2022.py --check-only
    python3 tools/revalidate_headline_points_2022.py --threads 4
    python3 tools/revalidate_headline_points_2022.py --points s5_2      # one point

Re-running is safe; completed points are reused from the evaluator cache.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from policy_evaluation import PolicyEvaluator, atomic_json  # noqa: E402

BENCHMARK = ROOT / "calibration" / "runs" / "business_financing_2022" / "rn_reform"
EXECUTABLES = {
    False: ROOT / "Compiled_Files_Baseline" / "GKK_Main.a",
    True: ROOT / "experiments" / "joint_tax_fixed_labor" / "build" / "GKK_Main_fixed_labor.a",
}
OUT_ROOT = ROOT / "calibration" / "runs" / "headline_revalidation_2022"
THETA_FINANCING = ROOT / "calibration" / "runs" / "theta_max_robustness_2022" / "financing"

# Exact rates copied from each search's best.json / all_results.csv, with the
# unvalidated CE2 each one reported, so the change can be measured.
POINTS = {
    "s5_1": dict(label="Three taxes, labour residual (Table VIII)",
                 rates=(0.04909963880661732, -0.30, 0.0011395892219886016),
                 fixed_labor=False, old_ce2=19.427850849218053,
                 source="calibration/runs/joint_tax_2022/best.json"),
    "s5_2": dict(label="Three taxes, labour fixed (Table VIII)",
                 rates=(0.02607740355301102, -0.2796540429279936, 8.988849991218075e-18),
                 fixed_labor=True, old_ce2=16.839959321793053,
                 source="experiments/joint_tax_fixed_labor/results/best.json"),
    "s5_3": dict(label="Wealth-capital, estate fixed (Table VIII)",
                 rates=(0.07129528494896156, -0.4982312866513432, 0.4000000000084517),
                 fixed_labor=False, old_ce2=19.813667619988507,
                 source="calibration/runs/joint_wealth_capital_2022/best.json"),
    "s5_4": dict(label="Best subsidy-cap grid point (Section 5.4)",
                 rates=(0.07, -0.5, 0.4),
                 fixed_labor=False, old_ce2=19.849731874361698,
                 source="calibration/runs/subsidy_cap_grid_2022/all_results.csv"),
}

# Already validated; reused. Old values are what the paper currently reports.
REUSED = {
    "owt": dict(label="Optimal wealth tax (Table VII)", rates=(0.030618034, 0.0, 0.40),
                old_ce2=8.5089144308119415,
                old_source="Opt_Tax routine, business_financing_2022/rn_reform/Opt_Tax_W"),
    "okit": dict(label="Optimal capital-income tax (Table VII)", rates=(0.0, -0.13618034, 0.40),
                 old_ce2=5.0535141199330447,
                 old_source="Opt_Tax routine, business_financing_2022/rn_reform/Opt_Tax_K"),
}

# Wide enough never to bind: fixed points are evaluated, not searched.
BOUNDS = ((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0))
LABOR_BOUNDS = (0.0, 0.60)


def preflight(names: list[str]) -> None:
    if not (BENCHMARK / "output.txt").exists():
        raise SystemExit(f"benchmark missing: {BENCHMARK}")
    for flag in sorted({POINTS[n]["fixed_labor"] for n in names}):
        exe = EXECUTABLES[flag]
        if not exe.exists():
            raise SystemExit(f"executable missing: {exe}")
    for name, rates in ((n, POINTS[n]["rates"]) for n in names):
        if not -0.50 <= rates[1] <= 0.50:
            raise SystemExit(f"{name}: tau_k={rates[1]} is outside the executable's "
                             "[-0.50, 0.50] guard and cannot be solved")


def reused_result(rates) -> dict | None:
    for f in glob.glob(str(THETA_FINANCING / "v2_*" / "*" / "result.json")):
        r = json.loads(Path(f).read_text())
        if (r.get("status") == "ok"
                and all(math.isclose(a, b, rel_tol=0, abs_tol=1e-12)
                        for a, b in zip((r["tau_w"], r["tau_k"], r["tau_bq"]), rates))):
            return r
    return None


def make_evaluator(fixed_labor: bool, threads: int, budget_tolerance: float) -> PolicyEvaluator:
    return PolicyEvaluator(
        root=ROOT,
        executable=EXECUTABLES[fixed_labor],
        benchmark=BENCHMARK,
        run_root=OUT_ROOT / ("fixed_labour" if fixed_labor else "labour_residual"),
        threads=threads,
        bounds=BOUNDS,
        labor_bounds=LABOR_BOUNDS,
        budget_tolerance=budget_tolerance,
        fixed_labor=fixed_labor,
        calibration_env=None,  # financing calibration, exactly as the original drivers
    )


def solve_points(names: list[str], threads: int, budget_tolerance: float) -> None:
    (OUT_ROOT / "points").mkdir(parents=True, exist_ok=True)
    evaluators: dict[bool, PolicyEvaluator] = {}
    for name in names:
        spec = POINTS[name]
        flag = spec["fixed_labor"]
        if flag not in evaluators:
            evaluators[flag] = make_evaluator(flag, threads, budget_tolerance)
            print(f"versioned results ({'fixed' if flag else 'residual'} labour): "
                  f"{evaluators[flag].run_root}", flush=True)
        ev = evaluators[flag]
        print(f"\n[{name}] {spec['label']}", flush=True)
        print(f"  tau_w={spec['rates'][0]:.9f} tau_k={spec['rates'][1]:+.9f} "
              f"tau_bq={spec['rates'][2]:.9f}", flush=True)
        record = {"point": name, **{k: v for k, v in spec.items() if k != "rates"},
                  "rates": list(spec["rates"])}
        try:
            result = ev.evaluate_rates(spec["rates"])
        except Exception as exc:  # one failure must not stop the batch
            record.update(status="failed", error=str(exc))
            print(f"  FAILED: {exc}", flush=True)
        else:
            record.update(status="ok", result=result, feasible=bool(ev.is_feasible(result)))
            print(f"  CE2 {spec['old_ce2']:.4f} -> {result['ce2_newborn']:.4f} "
                  f"({result['ce2_newborn'] - spec['old_ce2']:+.4f})  "
                  f"revenue gap {result['revenue_relative_gap']:.2e}  "
                  f"feasible={record['feasible']}", flush=True)
        atomic_json(OUT_ROOT / "points" / f"{name}.json", record)
    for ev in evaluators.values():
        ev.write_index()


def write_comparison(budget_tolerance: float) -> None:
    rows = []
    for name, spec in REUSED.items():
        r = reused_result(spec["rates"])
        rows.append((name, spec["label"], spec["old_ce2"],
                     r["ce2_newborn"] if r else None, r, True if r else None,
                     "reused from theta_max_robustness_2022" if r else "NOT FOUND"))
    for name, spec in POINTS.items():
        f = OUT_ROOT / "points" / f"{name}.json"
        if not f.exists():
            rows.append((name, spec["label"], spec["old_ce2"], None, None, None, "not yet solved"))
            continue
        rec = json.loads(f.read_text())
        if rec["status"] != "ok":
            rows.append((name, spec["label"], spec["old_ce2"], None, None, None,
                         f"FAILED: {rec['error'][:60]}"))
            continue
        r = rec["result"]
        rows.append((name, spec["label"], spec["old_ce2"], r["ce2_newborn"], r,
                     rec["feasible"], "solved"))

    lines = ["# Headline points under the validated evaluator", "",
             "Every validated value satisfies: equilibrium residual < 1e-7, aggregate "
             "residual < 1e-6, iteration count within the cap, tax rates and "
             "benchmark revenue verified.", "",
             "| Point | Reported CE2 | Validated CE2 | Change | Labour tax | "
             "Revenue gap | Feasible | Status |",
             "|---|---:|---:|---:|---:|---:|---|---|"]
    out = {"standard": {"equilibrium_residual_below": 1e-7, "aggregate_residual_below": 1e-6,
                        "budget_tolerance": budget_tolerance}, "points": {}}
    for name, label, old, new, r, feas, status in rows:
        if new is None:
            lines.append(f"| {label} | {old:.4f} | — | — | — | — | — | {status} |")
            out["points"][name] = {"label": label, "reported_ce2": old, "status": status}
            continue
        lines.append(f"| {label} | {old:.4f} | {new:.4f} | {new - old:+.4f} | "
                     f"{r['tau_l']:.4f} | {r['revenue_relative_gap']:.2e} | "
                     f"{'yes' if feas else '**NO**'} | {status} |")
        out["points"][name] = {
            "label": label, "reported_ce2": old, "status": status, "feasible": feas,
            **{k: r[k] for k in ("tau_w", "tau_k", "tau_bq", "tau_l", "ce2_newborn",
                                 "ce2_population", "ce1_newborn", "output_growth",
                                 "consumption_growth", "top1_wealth_share",
                                 "revenue_relative_gap", "equilibrium_residual",
                                 "aggregate_residual", "result_directory")
               if k in r}}

    done = [n for n, *_ in rows if out["points"][n].get("ce2_newborn") is not None]
    if done:
        worst = max(abs(out["points"][n]["ce2_newborn"] - out["points"][n]["reported_ce2"])
                    for n in done)
        lines += ["", f"Largest change in newborn CE2 across completed points: "
                      f"{worst:.4f} percentage points."]
    infeasible = [n for n in done if out["points"][n].get("feasible") is False]
    if infeasible:
        lines += ["", "**Not revenue-feasible under the validated solve:** "
                  + ", ".join(infeasible)
                  + f". The revenue gap exceeds {budget_tolerance:g}; the paper must not "
                    "report these as feasible optima without qualification."]
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "comparison.md").write_text("\n".join(lines) + "\n")
    atomic_json(OUT_ROOT / "validated_headline.json", out)
    print(f"\nwrote {OUT_ROOT / 'comparison.md'}")
    print(f"wrote {OUT_ROOT / 'validated_headline.json'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--budget-tolerance", type=float, default=1.0e-4,
                        help="matches the original search drivers (default 1e-4)")
    parser.add_argument("--dbn-max-iter", type=int, default=2000,
                        help="equilibrium iteration cap (default 2000; the evaluator's own "
                             "default of 700 was too low for a capital-income subsidy)")
    parser.add_argument("--points", default=",".join(POINTS),
                        help="comma-separated subset of: " + ",".join(POINTS))
    parser.add_argument("--check-only", action="store_true",
                        help="verify inputs, print the plan, solve nothing")
    parser.add_argument("--table-only", action="store_true",
                        help="rebuild comparison.md from completed points; solve nothing")
    args = parser.parse_args()
    if args.threads < 1 or not 0 < args.budget_tolerance < 1 or args.dbn_max_iter < 1:
        parser.error("invalid threads, budget tolerance or iteration cap")
    names = [p.strip() for p in args.points.split(",") if p.strip()]
    unknown = [n for n in names if n not in POINTS]
    if unknown:
        parser.error(f"unknown point(s): {', '.join(unknown)}")

    if args.table_only:
        write_comparison(args.budget_tolerance)
        return 0

    preflight(names)
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)  # honoured via setdefault

    print(f"benchmark: {BENCHMARK.relative_to(ROOT)}")
    print(f"iteration cap: {args.dbn_max_iter}   budget tolerance: {args.budget_tolerance:g}")
    for name in names:
        s = POINTS[name]
        print(f"  {name}: {s['label']}")
        print(f"        rates {s['rates']}  fixed_labour={s['fixed_labor']}  "
              f"reported CE2 {s['old_ce2']:.4f}")
        print(f"        from {s['source']}")
    for name, s in REUSED.items():
        found = reused_result(s["rates"])
        print(f"  {name}: {s['label']}  -> "
              + (f"reused, validated CE2 {found['ce2_newborn']:.4f}" if found
                 else "NOT FOUND in theta_max_robustness_2022/financing"))

    if args.check_only:
        print(f"\nCheck only: no model was run. {len(names)} solve(s) planned.")
        print("No existing run tree is written to.")
        return 0

    solve_points(names, args.threads, args.budget_tolerance)
    write_comparison(args.budget_tolerance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Jointly optimize wealth, capital-income, and estate taxes.

Each policy evaluation loads the SCF-plus-financing benchmark, solves the labor
tax required to hold government revenue fixed, and records newborn CE2 welfare.
Evaluations are cached on disk, so rerunning this command resumes the search.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import differential_evolution, minimize
from policy_evaluation import PolicyEvaluator, atomic_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = ROOT / "calibration" / "runs" / "business_financing_2022" / "rn_reform"
DEFAULT_RUN_ROOT = ROOT / "calibration" / "runs" / "joint_tax_2022"
EXECUTABLE = ROOT / "Compiled_Files_Baseline" / "GKK_Main.a"

# Bounds are policy rates in decimal units.
DEFAULT_BOUNDS = (
    (0.00, 0.06),   # flat annual wealth tax
    (-0.30, 0.25),  # capital-income tax; negative values are subsidies
    (0.00, 0.80),   # estate tax
)


def read_kv(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in path.read_text(errors="replace").splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            values[fields[0]] = float(fields[-1].replace("D", "E"))
        except ValueError:
            continue
    return values


def scaled_to_rates(u: np.ndarray, bounds: tuple[tuple[float, float], ...]) -> tuple[float, float, float]:
    rates = [lo + float(x) * (hi - lo) for x, (lo, hi) in zip(u, bounds)]
    return rates[0], rates[1], rates[2]


def rates_to_scaled(rates: tuple[float, float, float], bounds: tuple[tuple[float, float], ...]) -> np.ndarray:
    return np.array([(x - lo) / (hi - lo) for x, (lo, hi) in zip(rates, bounds)], dtype=float)


class Evaluator(PolicyEvaluator):
    def __init__(self, benchmark, run_root, threads, bounds, labor_bounds, budget_tolerance):
        super().__init__(root=ROOT, executable=EXECUTABLE, benchmark=benchmark, run_root=run_root,
                         threads=threads, bounds=bounds, labor_bounds=labor_bounds,
                         budget_tolerance=budget_tolerance, fixed_labor=False)

    def objective(self, u: np.ndarray) -> float:
        rates = scaled_to_rates(np.clip(u, 0.0, 1.0), self.bounds)
        try:
            result = self.evaluate_rates(rates)
        except Exception as exc:
            print(f"             FAILED: {exc}", flush=True)
            return 1.0e6

        objective = -float(result["ce2_newborn"])
        tau_l = float(result["tau_l"])
        lo_l, hi_l = self.labor_bounds
        if tau_l < lo_l:
            objective += 1.0e4 * (lo_l - tau_l) ** 2
        if tau_l > hi_l:
            objective += 1.0e4 * (tau_l - hi_l) ** 2
        revenue_gap = float(result["revenue_relative_gap"])
        if not self.is_feasible(result):
            return 1.0e6 + revenue_gap
        return objective


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--threads", type=int, default=int(os.environ.get("THREADS", "9")))
    parser.add_argument("--global-generations", type=int, default=2)
    parser.add_argument("--population", type=int, default=4)
    parser.add_argument("--local-max-evals", type=int, default=45)
    parser.add_argument("--seed", type=int, default=2022)
    parser.add_argument("--budget-tolerance", type=float, default=1.0e-4)
    parser.add_argument("--tau-w-min", type=float, default=DEFAULT_BOUNDS[0][0])
    parser.add_argument("--tau-w-max", type=float, default=DEFAULT_BOUNDS[0][1])
    parser.add_argument("--tau-k-min", type=float, default=DEFAULT_BOUNDS[1][0])
    parser.add_argument("--tau-k-max", type=float, default=DEFAULT_BOUNDS[1][1])
    parser.add_argument("--tau-bq-min", type=float, default=DEFAULT_BOUNDS[2][0])
    parser.add_argument("--tau-bq-max", type=float, default=DEFAULT_BOUNDS[2][1])
    parser.add_argument("--tau-l-min", type=float, default=0.0)
    parser.add_argument("--tau-l-max", type=float, default=0.60)
    parser.add_argument("--initial-tau-w", type=float)
    parser.add_argument("--initial-tau-k", type=float)
    parser.add_argument("--initial-tau-bq", type=float)
    parser.add_argument("--skip-build", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    benchmark = args.benchmark if args.benchmark.is_absolute() else ROOT / args.benchmark
    run_root = args.run_root if args.run_root.is_absolute() else ROOT / args.run_root
    if not (benchmark / "Bench_Files").is_dir() or not (benchmark / "output.txt").is_file():
        raise SystemExit(f"matching benchmark is incomplete: {benchmark}")

    if not args.skip_build:
        subprocess.run(
            ["bash", "tools/run_mac.sh", "joint-build"],
            cwd=ROOT,
            env={**os.environ, "THREADS": str(args.threads)},
            check=True,
        )
    if not EXECUTABLE.is_file():
        raise SystemExit(f"joint evaluator is missing: {EXECUTABLE}")

    bounds = (
        (args.tau_w_min, args.tau_w_max),
        (args.tau_k_min, args.tau_k_max),
        (args.tau_bq_min, args.tau_bq_max),
    )
    for name, (lo, hi) in zip(("tau_w", "tau_k", "tau_bq"), bounds):
        if not lo < hi:
            raise SystemExit(f"invalid {name} bounds: minimum must be below maximum")
    if not args.tau_l_min < args.tau_l_max:
        raise SystemExit("invalid tau_l bounds: minimum must be below maximum")
    evaluator = Evaluator(
        benchmark=benchmark,
        run_root=run_root,
        threads=args.threads,
        bounds=bounds,
        labor_bounds=(args.tau_l_min, args.tau_l_max),
        budget_tolerance=args.budget_tolerance,
    )

    run_root = evaluator.run_root
    print(f"Versioned results: {run_root}", flush=True)

    # Record economically meaningful anchors before the global search. The OWT
    # and OKIT rates are not mechanically combined: each is a conditional
    # one-dimensional optimum, while the global stage explores their interaction.
    standard_anchors = [
        (0.030618034, 0.0, 0.40),
        (0.0, -0.13618034, 0.40),
        (0.0, 0.25, 0.40),
    ]
    supplied_initial = (args.initial_tau_w, args.initial_tau_k, args.initial_tau_bq)
    if any(value is not None for value in supplied_initial):
        if not all(value is not None for value in supplied_initial):
            raise SystemExit("supply all three --initial-tau-* values together")
        initial_rates = tuple(float(value) for value in supplied_initial)
    else:
        previous_best = (0.04909963880661732, -0.30, 0.0011395892219886016)
        initial_rates = previous_best

    def inside(rates: tuple[float, float, float]) -> bool:
        return all(lo <= value <= hi for value, (lo, hi) in zip(rates, bounds))

    if not inside(initial_rates):
        raise SystemExit(f"initial tax vector lies outside the requested bounds: {initial_rates}")
    anchor_rates = [initial_rates, *[rates for rates in standard_anchors if inside(rates)]]
    for rates in anchor_rates:
        evaluator.objective(rates_to_scaled(rates, bounds))
    initial_u = np.clip(rates_to_scaled(initial_rates, bounds), 0.0, 1.0)

    print("\n[stage 1] coarse global differential-evolution search", flush=True)
    global_result = differential_evolution(
        evaluator.objective,
        bounds=[(0.0, 1.0)] * 3,
        maxiter=args.global_generations,
        popsize=args.population,
        seed=args.seed,
        polish=False,
        workers=1,
        updating="immediate",
        disp=True,
        x0=initial_u,
    )

    print("\n[stage 2] bounded Powell refinement", flush=True)
    local_result = minimize(
        evaluator.objective,
        x0=np.clip(global_result.x, 0.0, 1.0),
        method="Powell",
        bounds=[(0.0, 1.0)] * 3,
        options={"xtol": 0.01, "ftol": 1.0e-4, "maxfev": args.local_max_evals, "disp": True},
    )

    valid = [
        row for row in evaluator.results
        if evaluator.is_feasible(row)
    ]
    if not valid:
        raise SystemExit("no feasible revenue-neutral candidate completed")
    best = max(valid, key=lambda row: float(row["ce2_newborn"]))
    boundary_tolerance = 0.01
    boundary_flags: dict[str, str] = {}
    for name, value, (lo, hi) in zip(
        ("tau_w", "tau_k", "tau_bq"),
        (float(best["tau_w"]), float(best["tau_k"]), float(best["tau_bq"])),
        bounds,
    ):
        width = hi - lo
        if value - lo <= boundary_tolerance * width:
            boundary_flags[name] = "lower"
        elif hi - value <= boundary_tolerance * width:
            boundary_flags[name] = "upper"
    summary = {
        "context_id": evaluator.context_id,
        "budget_tolerance": evaluator.budget_tolerance,
        "objective": "maximize newborn CE2 welfare",
        "budget_rule": "labor tax adjusts to match benchmark government revenue",
        "benchmark": str(benchmark.relative_to(ROOT)),
        "bounds": {
            "tau_w": bounds[0], "tau_k": bounds[1], "tau_bq": bounds[2],
            "tau_l": (args.tau_l_min, args.tau_l_max),
        },
        "optimizer_status": {
            "global_success": bool(global_result.success),
            "global_message": str(global_result.message),
            "local_success": bool(local_result.success),
            "local_message": str(local_result.message),
            "boundary_flags": boundary_flags,
        },
        "calibration_environment": evaluator.calibration_env,
        "best": best,
    }
    atomic_json(run_root / "best.json", summary)
    evaluator.write_index()

    print("\n================ JOINT REVENUE-NEUTRAL OPTIMUM ================")
    print(f"Wealth tax             {100*float(best['tau_w']):9.4f}%")
    print(f"Capital-income tax     {100*float(best['tau_k']):9.4f}%")
    print(f"Estate tax             {100*float(best['tau_bq']):9.4f}%")
    print(f"Balancing labor tax    {100*float(best['tau_l']):9.4f}%")
    print(f"Newborn CE2 welfare    {float(best['ce2_newborn']):9.4f}%")
    print(f"Revenue gap            {float(best['revenue_gap']):+12.5e}")
    print(f"Summary                {(run_root / 'best.json').relative_to(ROOT)}")
    if boundary_flags:
        print(f"BOUNDARY WARNING       {boundary_flags}")
        print("Extend the flagged bound before calling this an unconstrained optimum.")
    print("================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())

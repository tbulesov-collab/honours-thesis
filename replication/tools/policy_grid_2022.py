#!/usr/bin/env python3
"""One-dimensional policy grids under the validated evaluator.

Two presets, both at the financing calibration (benchmark
business_financing_2022/rn_reform), revenue-neutral through the labour tax:

  estate   Estate-tax sweep at the optimal wealth tax.
           tau_w = 3.0618%, tau_k = 0, tau_bq in {0, 10, 20, 30, 40, 50, 60}%.
           Question: does the estate tax matter alongside a wealth tax?  The
           only existing evidence comes from the joint-search corner, where the
           estate tax falls to zero together with an extreme capital subsidy.

  okit     Capital-income tax grid around the OKIT optimum.
           tau_w = 0, tau_bq = 40%, tau_k in {-22, -21, ..., -13}%.
           Question: is the +/-0.15 pp zigzag in the optimal-tax routine's grid
           numerical?  Each point is shown beside that routine's value at the
           same rate.  If the validated curve is smooth, the zigzag was
           numerical and the optimum becomes identifiable.

Every solve must pass the validated checks (equilibrium residual < 1e-7,
aggregate residual < 1e-6, rates and benchmark revenue verified).  A point
already solved under the validated evaluator elsewhere is reused, not re-solved.

SAFETY.  Writes only to calibration/runs/<preset output>/.  One failed point
does not stop the batch.  The table is always built from every saved point.

Usage:
    python3 tools/policy_grid_2022.py --grid estate --check-only
    python3 tools/policy_grid_2022.py --grid estate --threads 4
    python3 tools/policy_grid_2022.py --grid okit --values -0.16,-0.15,-0.14   # quick diagnostic
    python3 tools/policy_grid_2022.py --grid okit --table-only
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
EXECUTABLE = ROOT / "Compiled_Files_Baseline" / "GKK_Main.a"
OPT_TAX_K_GRID = BENCHMARK / "Opt_Tax_K" / "Stats_by_tau_k_2.txt"
# Validated results elsewhere that may be reused when rates match exactly.
REUSE_GLOBS = [
    "calibration/runs/theta_max_robustness_2022/financing/v2_*/*/result.json",
    "calibration/runs/headline_revalidation_2022/labour_residual/v2_*/*/result.json",
]
INDEX = {"tau_w": 0, "tau_k": 1, "tau_bq": 2}
GRIDS = {
    "estate": dict(
        title="Estate-tax sweep at the optimal wealth tax",
        vary="tau_bq", fixed={"tau_w": 0.030618034, "tau_k": 0.0},
        values=[0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60],
        out="estate_tax_grid_2022"),
    "okit": dict(
        title="Capital-income tax grid around the OKIT optimum",
        vary="tau_k", fixed={"tau_w": 0.0, "tau_bq": 0.40},
        values=[round(-0.22 + 0.01 * i, 2) for i in range(10)],   # -0.22 ... -0.13
        out="okit_fine_grid_2022"),
}
NOISE_PP = 0.15  # welfare differences below this are within numerical error (paper, Section 3)
BOUNDS = ((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0))
LABOR_BOUNDS = (0.0, 0.60)


def rates_for(spec: dict, value: float) -> tuple[float, float, float]:
    r = [0.0, 0.0, 0.0]
    for name, v in spec["fixed"].items():
        r[INDEX[name]] = v
    r[INDEX[spec["vary"]]] = value
    return tuple(r)


def point_name(spec: dict, value: float) -> str:
    return f"{spec['vary']}_{value:+.4f}"


def same_rates(r: dict, rates) -> bool:
    return all(math.isclose(a, b, rel_tol=0, abs_tol=1e-12)
               for a, b in zip((r["tau_w"], r["tau_k"], r["tau_bq"]), rates))


def reusable(rates) -> dict | None:
    for pattern in REUSE_GLOBS:
        for f in glob.glob(str(ROOT / pattern)):
            r = json.loads(Path(f).read_text())
            if r.get("status") == "ok" and same_rates(r, rates):
                return r
    return None


def old_routine_ce2() -> dict[float, float]:
    """CE2 by tau_k from the optimal-tax routine's grid (unvalidated), for comparison."""
    out: dict[float, float] = {}
    if not OPT_TAX_K_GRID.exists():
        return out
    for line in OPT_TAX_K_GRID.read_text().splitlines():
        f = line.split()
        try:
            out[round(float(f[0]), 2)] = float(f[-2])
        except (ValueError, IndexError):
            continue
    return out


def solve(spec: dict, values: list[float], threads: int, budget_tolerance: float) -> None:
    out = ROOT / "calibration" / "runs" / spec["out"]
    (out / "points").mkdir(parents=True, exist_ok=True)
    evaluator = None
    for value in values:
        rates = rates_for(spec, value)
        name = point_name(spec, value)
        print(f"\n[{name}] tau_w={rates[0]:.6f} tau_k={rates[1]:+.4f} tau_bq={rates[2]:.4f}",
              flush=True)
        record = {"point": name, "value": value, "rates": list(rates)}
        prior = reusable(rates)
        if prior is not None:
            record.update(status="ok", result=prior, source="reused validated result")
            print(f"  reused: CE2 {prior['ce2_newborn']:.4f}", flush=True)
            atomic_json(out / "points" / f"{name}.json", record)
            continue
        if evaluator is None:
            evaluator = PolicyEvaluator(
                root=ROOT, executable=EXECUTABLE, benchmark=BENCHMARK,
                run_root=out, threads=threads, bounds=BOUNDS,
                labor_bounds=LABOR_BOUNDS, budget_tolerance=budget_tolerance,
                fixed_labor=False, calibration_env=None)
            print(f"versioned results: {evaluator.run_root}", flush=True)
        try:
            result = evaluator.evaluate_rates(rates)
        except Exception as exc:  # one failure must not stop the batch
            record.update(status="failed", error=str(exc))
            print(f"  FAILED: {exc}", flush=True)
        else:
            record.update(status="ok", result=result, source="solved",
                          feasible=bool(evaluator.is_feasible(result)))
            print(f"  CE2 {result['ce2_newborn']:.4f}  tau_l {result['tau_l']:.4f}  "
                  f"revenue gap {result['revenue_relative_gap']:.2e}", flush=True)
        atomic_json(out / "points" / f"{name}.json", record)
    if evaluator is not None:
        evaluator.write_index()


def write_table(grid: str, spec: dict) -> None:
    out = ROOT / "calibration" / "runs" / spec["out"]
    records = [json.loads(f.read_text()) for f in sorted((out / "points").glob("*.json"))]
    records.sort(key=lambda r: r["value"])
    ok = [r for r in records if r["status"] == "ok"]
    label = {"tau_bq": "Estate tax", "tau_k": "Capital-income tax"}[spec["vary"]]
    old = old_routine_ce2() if grid == "okit" else {}

    head = f"| {label} | CE2 newborn | "
    head += "Old routine CE2 | " if old else ""
    head += "CE1 newborn | CE2 population | Labour tax | Output | Top 1% | Source |"
    lines = [f"# {spec['title']}", "",
             "Financing calibration; labour tax balances revenue; validated evaluator.", "",
             head, "|" + "---:|" * (head.count("|") - 1)]
    for r in records:
        v = f"{100 * r['value']:+.0f}%" if spec["vary"] == "tau_k" else f"{100 * r['value']:.0f}%"
        if r["status"] != "ok":
            lines.append(f"| {v} | FAILED: {r['error'][:50]} |")
            continue
        x = r["result"]
        row = f"| {v} | {x['ce2_newborn']:.4f} | "
        if old:
            o = old.get(round(r["value"], 2))
            row += f"{o:.4f} | " if o is not None else "— | "
        row += (f"{x['ce1_newborn']:.4f} | {x['ce2_population']:.4f} | "
                f"{100 * x['tau_l']:.2f}% | {x['output_growth']:+.2f}% | "
                f"{100 * x['top1_wealth_share']:.2f}% | {r.get('source', '')} |")
        lines.append(row)

    summary = {"grid": grid, "title": spec["title"], "vary": spec["vary"],
               "fixed": spec["fixed"], "noise_pp": NOISE_PP, "points": records}
    if len(ok) >= 2:
        ce2 = [r["result"]["ce2_newborn"] for r in ok]
        best = max(range(len(ok)), key=lambda i: ce2[i])
        ties = [ok[i]["value"] for i in range(len(ok)) if ce2[best] - ce2[i] < NOISE_PP]
        lines += ["", f"Highest CE2: {ce2[best]:.4f} at {spec['vary']} = {ok[best]['value']:+.2f}.",
                  f"Within {NOISE_PP} pp of the maximum (numerically tied): "
                  + ", ".join(f"{t:+.2f}" for t in ties) + "."]
        summary.update(best_value=ok[best]["value"], best_ce2=ce2[best], tied_values=ties)
        diffs = [b - a for a, b in zip(ce2, ce2[1:])]
        turns = sum(1 for a, b in zip(diffs, diffs[1:]) if a * b < 0)
        lines += [f"Direction changes along the grid: {turns}; largest adjacent step: "
                  f"{max(abs(d) for d in diffs):.4f} pp."]
        summary.update(direction_changes=turns, max_adjacent_step=max(abs(d) for d in diffs))
        if old:
            o = [old.get(round(r["value"], 2)) for r in ok]
            if all(v is not None for v in o):
                od = [b - a for a, b in zip(o, o[1:])]
                oturns = sum(1 for a, b in zip(od, od[1:]) if a * b < 0)
                lines += [f"Same points in the old routine: {oturns} direction changes; "
                          f"largest adjacent step {max(abs(d) for d in od):.4f} pp."]
                summary.update(old_direction_changes=oturns)
                if turns < oturns:
                    lines += ["", "**The validated curve is smoother than the old routine's: "
                              "the zigzag is at least partly numerical.**"]
                elif turns == oturns and turns > 0:
                    lines += ["", "**The zigzag persists under the validated evaluator: it is not "
                              "an artefact of the old routine's convergence.**"]
    (out / "comparison.md").write_text("\n".join(lines) + "\n")
    atomic_json(out / "grid_results.json", summary)
    print(f"\nwrote {out / 'comparison.md'}\nwrote {out / 'grid_results.json'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--grid", choices=sorted(GRIDS), required=True)
    parser.add_argument("--values", help="comma-separated subset of grid values, e.g. -0.16,-0.15")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--budget-tolerance", type=float, default=1.0e-4)
    parser.add_argument("--dbn-max-iter", type=int, default=2000,
                        help="equilibrium iteration cap (default 2000; 700 failed for a subsidy)")
    parser.add_argument("--check-only", action="store_true", help="print the plan; solve nothing")
    parser.add_argument("--table-only", action="store_true",
                        help="rebuild the table from saved points; solve nothing")
    args = parser.parse_args()
    spec = GRIDS[args.grid]
    if args.threads < 1 or not 0 < args.budget_tolerance < 1 or args.dbn_max_iter < 1:
        parser.error("invalid threads, budget tolerance or iteration cap")

    values = spec["values"]
    if args.values:
        values = [round(float(v), 4) for v in args.values.split(",") if v.strip()]
    if spec["vary"] == "tau_k" and any(not -0.50 <= v <= 0.50 for v in values):
        parser.error("tau_k must lie within the executable's [-0.50, 0.50] guard")

    if args.table_only:
        write_table(args.grid, spec)
        return 0
    if not (BENCHMARK / "output.txt").exists() or not EXECUTABLE.exists():
        raise SystemExit("benchmark or executable missing")
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)  # honoured via setdefault

    print(f"{spec['title']}\nfixed: {spec['fixed']}\niteration cap: {args.dbn_max_iter}")
    to_solve = 0
    for v in values:
        prior = reusable(rates_for(spec, v))
        print(f"  {point_name(spec, v)}  "
              + (f"reuse validated CE2 {prior['ce2_newborn']:.4f}" if prior else "solve"))
        to_solve += prior is None
    if args.check_only:
        print(f"\nCheck only: no model was run. {to_solve} solve(s) planned, "
              f"{len(values) - to_solve} reused.")
        return 0
    solve(spec, values, args.threads, args.budget_tolerance)
    write_table(args.grid, spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

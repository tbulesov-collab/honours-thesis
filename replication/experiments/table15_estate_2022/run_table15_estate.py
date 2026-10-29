#!/usr/bin/env python3
"""Fill the estate-tax cells of thesis Table 15 (tab:ch7_robustness_summary).

Newborn CE2 at a 7% wealth tax and -50% capital-income tax, with the estate tax at 40%
and at 0, in three variants:

    theta_2800  theta_max = 2.800 (published value), SCF parameters fixed, its own
                benchmark calibration/runs/scf_2022/3f5118dda04e. Never solved before.
    theta_2952  theta_max = 2.952 (reported calibration), saved benchmark rn_reform.
                The thesis row 19.86 -> 23.54; here it is the matched check.
    recal_alt   recalibration under the alternative productivity convention
                (model_spec_sensitivity_2022/recal/productivity). Estate 40 (17.05) is
                saved; estate 0 was never solved.

Each evaluator copies an existing one exactly, so a point already solved in the same
context is reused instead of re-solved:

    theta_2952  the "thesis" evaluator of policy_reoptimization_2022/reoptimize.py
                (control eval.a, reported calibration, 4 threads, DBN max iter 2000).
                Reuses 19.865 (three_tax_2022/runs/estate) and 23.539
                (policy_reoptimization_2022/runs/thesis).
    theta_2800  the same evaluator with the published theta_max and benchmark, as in
                tools/theta_max_robustness_2022.py (benchmark theta grid is checked).
    recal_alt   the policy evaluator of model_spec_sensitivity_2022/recalibrate.py for
                the productivity arm (its eval.a, 3 threads, DBN max iter 2000).
                Reuses 17.05 from recal/productivity/policies.

A point is reused only if context, key and output digest match (PolicyEvaluator._cached),
i.e. executable, sources, benchmark and settings are unchanged; otherwise it is solved.
Saved folders are read, never written to.

Expected: 3 new solves (theta_2800 pair, recal_alt estate 0), 2 at a time, about 2 hours;
up to 6 if a context has changed. Separate-policy gaps are read from saved results
(theta_max_robustness_2022/comparison.json, recal/productivity/policies). Outputs only
under experiments/table15_estate_2022/; summary in results.md/.json. Re-running resumes.

    python3 experiments/table15_estate_2022/run_table15_estate.py --check-only
    python3 experiments/table15_estate_2022/run_table15_estate.py
    python3 experiments/table15_estate_2022/run_table15_estate.py --summary-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SENS = ROOT / "experiments" / "model_spec_sensitivity_2022"
sys.path[:0] = [str(ROOT / "tools"), str(SENS)]

import recalibrate as rc                                            # noqa: E402
import theta_max_robustness_2022 as tm                              # noqa: E402
from policy_evaluation import PolicyEvaluator, atomic_json          # noqa: E402

RUNS = HERE / "runs"
LOCK = RUNS / "driver.lock"
OTHER_LOCKS = [ROOT / "experiments/robustness_gkkoc_2022/runs/driver.lock",
               ROOT / "experiments/policy_reoptimization_2022/runs/driver.lock",
               ROOT / "experiments/three_tax_2022/runs/driver.lock",
               SENS / "recal" / "driver.lock", SENS / "runs" / "driver.lock"]
EXE = SENS / "variants" / "control" / "build" / "eval.a"
ALT_EXE = SENS / "variants" / "productivity" / "build" / "eval.a"
ALT_FIN = SENS / "recal" / "productivity" / "financing.json"
ALT_POLICIES = SENS / "recal" / "productivity" / "policies"

WIDE = ((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0))      # evaluator bounds for fixed-rate points
LABOR_BOUNDS = (0.0, 0.60)
BUDGET_TOLERANCE = 1.0e-4
OWT, OKIT = (0.030618034, 0.0, 0.40), (0.0, -0.13618034, 0.40)
RATES = {"bq40": (0.07, -0.50, 0.40), "bq0": (0.07, -0.50, 0.0)}

VARIANTS = ["theta_2800", "recal_alt", "theta_2952"]   # new solves first
LABELS = {"theta_2800": "Financial constraints, θ_max = 2.800",
          "theta_2952": "Financial constraints, θ_max = 2.952",
          "recal_alt": "Recalibration, alternative productivity convention"}
THREADS = {"theta_2800": 4, "theta_2952": 4, "recal_alt": 3}   # part of each context
REUSE = {"theta_2800": [],
         "theta_2952": [ROOT / "experiments/three_tax_2022/runs/estate",
                        ROOT / "experiments/policy_reoptimization_2022/runs/thesis"],
         "recal_alt": [ALT_POLICIES]}
# Values already reported; a reused or re-solved point must match them.
EXPECTED = {("theta_2952", "bq40"): 19.864961, ("theta_2952", "bq0"): 23.538518,
            ("recal_alt", "bq40"): 17.050529}
CHECK_TOL = 0.01                                    # pp of newborn CE2
TABLE_RANGES = {"gap": (1.37, 3.44), "gain": (2.82, 3.75)}   # Table 15 as of 2026-10-19


def check_inputs() -> None:
    for path in (EXE, ALT_EXE, ALT_FIN, tm.SCF_BEST, tm.FINANCING_BEST,
                 tm.BENCHMARKS["published"] / "output.txt", tm.BENCHMARKS["financing"] / "output.txt"):
        if not path.exists():
            raise SystemExit(f"missing input: {path}")
    thetas = tm.theta_max_values()
    for arm in ("published", "financing"):
        found = tm.benchmark_theta_max(tm.BENCHMARKS[arm])
        if abs(found - thetas[arm]) > 1e-8:
            raise SystemExit(f"benchmark {tm.BENCHMARKS[arm]} was solved at theta_max={found:.10f}, "
                             f"not {thetas[arm]:.10f}")


def make_evaluator(variant: str) -> PolicyEvaluator:
    common = dict(root=ROOT, run_root=RUNS / variant, threads=THREADS[variant], bounds=WIDE,
                  labor_bounds=LABOR_BOUNDS, budget_tolerance=BUDGET_TOLERANCE, fixed_labor=False)
    if variant == "theta_2952":
        return PolicyEvaluator(executable=EXE, benchmark=tm.BENCHMARKS["financing"],
                               calibration_env=None, **common)
    if variant == "theta_2800":
        env = tm.calibration_env(tm.scf_parameters(), tm.PUBLISHED_THETA_MAX)
        return PolicyEvaluator(executable=EXE, benchmark=tm.BENCHMARKS["published"],
                               calibration_env=env, **common)
    fin = json.loads(ALT_FIN.read_text())
    return PolicyEvaluator(executable=ALT_EXE, benchmark=ROOT / fin["benchmark"],
                           calibration_env=rc.param_env(fin["parameters"]), **common)


def find_cached(ev: PolicyEvaluator, rates, roots) -> tuple[dict, Path] | None:
    """A validated result of this exact context and rates in one of the given run roots."""
    key = ev.candidate_key(rates)
    for root in roots:
        for path in sorted((root / ("v2_" + ev.context_id[:12])).glob(key + "_*/result.json")):
            result = ev._cached(path, rates)
            if result is not None:
                return result, path.parent
    return None


def load_points() -> dict:
    path = RUNS / "points.json"
    return json.loads(path.read_text()) if path.exists() else {}


def separate_gaps() -> dict:
    """(wealth-tax CE2, capital-income-policy CE2) per variant, from saved runs."""
    gaps = {}
    comp = json.loads((tm.OUT_ROOT / "comparison.json").read_text())
    by = {(r["arm"], r["anchor"]): r["ce2_newborn"] for r in comp["results"] if r.get("status") == "ok"}
    for variant, arm in (("theta_2800", "published"), ("theta_2952", "financing")):
        if (arm, "owt") in by and (arm, "okit") in by:
            gaps[variant] = (by[(arm, "owt")], by[(arm, "okit")])
    alt = {}
    for path in ALT_POLICIES.glob("v2_*/*/result.json"):
        r = json.loads(path.read_text())
        for name, rates in (("owt", OWT), ("okit", OKIT)):
            if r.get("status") == "ok" and all(abs(a - b) < 1e-12 for a, b in
                                               zip((r["tau_w"], r["tau_k"], r["tau_bq"]), rates)):
                alt[name] = r["ce2_newborn"]
    if len(alt) == 2:
        gaps["recal_alt"] = (alt["owt"], alt["okit"])
    return gaps


def summarise() -> None:
    points, gaps, rows = load_points(), separate_gaps(), {}
    lines = ["# Table 15 estate-tax cells (7% wealth tax, -50% capital-income tax)", "",
             "| Comparison | Separate-policy gap (pp) | Newborn CE2 (%) estate 40% → 0% | Estate-removal gain (pp) |",
             "|---|---:|---:|---:|"]
    for v in ["theta_2800", "theta_2952", "recal_alt"]:
        g = gaps.get(v)
        a, b = points.get(f"{v}_bq40", {}), points.get(f"{v}_bq0", {})
        ok = a.get("status") == "ok" and b.get("status") == "ok"
        rows[v] = {"label": LABELS[v], "owt_ce2": g[0] if g else None, "okit_ce2": g[1] if g else None,
                   "separate_gap": g[0] - g[1] if g else None,
                   "ce2_bq40": a.get("ce2_newborn"), "ce2_bq0": b.get("ce2_newborn"),
                   "estate_removal_gain": b["ce2_newborn"] - a["ce2_newborn"] if ok else None}
        lines.append(f"| {LABELS[v]} | " + (f"{g[0] - g[1]:.2f}" if g else "—") + " | "
                     + (f"{a['ce2_newborn']:.2f} → {b['ce2_newborn']:.2f} | "
                        f"{b['ce2_newborn'] - a['ce2_newborn']:+.2f} |" if ok else "— | — |"))
    lines += ["", "Gains are computed before rounding. Each estate-tax pair uses one benchmark; "
              "benchmarks differ across rows.", "", "## Points", ""]
    for name, r in points.items():
        if r.get("status") == "ok":
            lines.append(f"- {name}: newborn CE2 {r['ce2_newborn']:.4f}, population {r['ce2_population']:.4f}, "
                         f"labour tax {100 * r['tau_l']:.2f}%, top 1% {100 * r['top1_wealth_share']:.2f}%, "
                         f"revenue gap {100 * r['revenue_relative_gap']:.4f}%, residual "
                         f"{r['equilibrium_residual']:.1e}, feasible {r['feasible']} ({r['source']})")
        else:
            lines.append(f"- {name}: FAILED ({r.get('error', '')})")
    lines += ["", "## Checks", ""]
    for (v, case), want in EXPECTED.items():
        r = points.get(f"{v}_{case}", {})
        if r.get("status") == "ok":
            ok = abs(r["ce2_newborn"] - want) <= CHECK_TOL
            lines.append(f"- {v} {case}: {r['ce2_newborn']:.4f} vs {want:.4f} → {'passed' if ok else 'NOT passed'}")
        else:
            lines.append(f"- {v} {case}: not available")
    for what, field in (("gap", "separate_gap"), ("gain", "estate_removal_gain")):
        lo, hi = TABLE_RANGES[what]
        for v, row in rows.items():
            x = row[field]
            if x is not None and not lo - 0.005 <= x <= hi + 0.005:
                lines.append(f"- {v}: {what} {x:.2f} lies outside the Table 15 range {lo:.2f}–{hi:.2f}")
    (HERE / "results.md").write_text("\n".join(lines) + "\n")
    atomic_json(HERE / "results.json", {"rows": rows, "points": points})
    print("\n".join(lines))


def plan(evaluators: dict) -> tuple[dict, list]:
    """Reusable points, and the (name, evaluator, rates) jobs still to solve."""
    points, todo = load_points(), []
    for v, ev in evaluators.items():
        for case, rates in RATES.items():
            name = f"{v}_{case}"
            found = find_cached(ev, rates, [RUNS / v, *REUSE[v]])
            if found:
                result, folder = found
                points[name] = {**result, "source": str(folder.relative_to(ROOT))}
                print(f"  {name:16s} reuse  CE2_NB={result['ce2_newborn']:.6f}  "
                      f"({folder.relative_to(ROOT)})", flush=True)
            else:
                todo.append((name, ev, rates))
                print(f"  {name:16s} solve  (context {ev.context_id[:12]})", flush=True)
    return points, todo


def run(points: dict, todo: list, max_parallel: int) -> None:
    def one(job):
        name, ev, rates = job
        try:
            return name, {**ev.evaluate_rates(rates), "source": str(ev.run_root.relative_to(ROOT))}
        except Exception as exc:                  # one failure must not stop the others
            return name, {"status": "failed", "error": str(exc),
                          "tau_w": rates[0], "tau_k": rates[1], "tau_bq": rates[2]}

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        for future in as_completed([pool.submit(one, job) for job in todo]):
            name, r = future.result()
            points[name] = r
            atomic_json(RUNS / "points.json", points)
            print(f"[points.json] {name}: " + (f"CE2 {r['ce2_newborn']:.3f}  tau_l {100 * r['tau_l']:.2f}%"
                  if r["status"] == "ok" else f"FAILED ({r['error']})"), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-parallel", type=int, default=2)
    ap.add_argument("--dbn-max-iter", type=int, default=2000,
                    help="part of the context: 2000 matches the saved points")
    ap.add_argument("--variants", default=",".join(VARIANTS), help="comma-separated subset of "
                    + ",".join(VARIANTS))
    ap.add_argument("--check-only", action="store_true",
                    help="build the evaluators (each runs its 15-second interface check) and "
                         "report what would be reused or solved; solve nothing")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()
    if args.summary_only:
        summarise()
        return 0
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    if not variants or any(v not in VARIANTS for v in variants):
        ap.error(f"--variants must be a subset of {','.join(VARIANTS)}")
    if args.max_parallel < 1 or args.dbn_max_iter < 1:
        ap.error("--max-parallel and --dbn-max-iter must be positive")
    check_inputs()
    RUNS.mkdir(parents=True, exist_ok=True)
    for lock in (LOCK, *OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                if pid > 0:
                    os.kill(pid, 0)
                    raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass                                             # stale lock from a stopped run
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)    # the evaluators inherit GKK_*
    if args.check_only:
        points, todo = plan({v: make_evaluator(v) for v in variants})
        print(f"{len(todo)} solve(s), {args.max_parallel} at a time. Check only: nothing was solved "
              "or recorded.")
        return 0
    LOCK.write_text(str(os.getpid()))
    try:
        points, todo = plan({v: make_evaluator(v) for v in variants})
        atomic_json(RUNS / "points.json", points)
        print(f"{len(todo)} solve(s), {args.max_parallel} at a time", flush=True)
        run(points, todo, args.max_parallel)
        summarise()
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

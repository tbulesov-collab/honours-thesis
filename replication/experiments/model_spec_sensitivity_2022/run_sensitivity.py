#!/usr/bin/env python3
"""Solve each variant's benchmark, then evaluate the headline policies against it.

Build the variants first with make_variants.py.  Then:

    phase 1  benchmark solves (variants/<v>/build/bench.a), all variants in parallel
    phase 2  policy evaluations with tools/policy_evaluation.PolicyEvaluator, the same
             validated evaluator as the headline results, --max-parallel at a time
    phase 3  results.json and results.md

Every variant uses the financing calibration (the same environment the headline runs
used) and is compared with its *own* benchmark, which is solved from scratch with the
current convergence checks.  The control variant therefore also shows how much of the
reported welfare is the ~0.1-point offset of the saved benchmark.

Re-running resumes: a benchmark with done.json and complete solver state is reused, and solved policies come from
the evaluator cache.  Outputs go only under experiments/model_spec_sensitivity_2022/runs/.

    python3 experiments/model_spec_sensitivity_2022/run_sensitivity.py
    python3 experiments/model_spec_sensitivity_2022/run_sensitivity.py --summary-only
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from benchmark_cache import complete_benchmark  # noqa: E402
from policy_evaluation import PolicyEvaluator, atomic_json, read_kv  # noqa: E402

VARIANTS = ["control", "productivity", "timing", "both"]
POLICIES = {"owt": (0.030618034, 0.0, 0.40), "okit": (0.0, -0.13618034, 0.40)}
ANCHOR = {"benchmark_anchor": (0.0, 0.25, 0.40)}     # evaluated for the control only
# Joint-policy headline points (validated_headline.json), evaluated only on request with
# --policies; names match that file so the saved-benchmark values can be shown alongside.
JOINT = {"s5_1": (0.04909963880661732, -0.30, 0.0011395892219886016),
         "s5_3": (0.07129528494896156, -0.4982312866513432, 0.4000000000084517),
         "s5_4": (0.07, -0.5, 0.4)}


def policy_set(variant: str, only: list[str] | None) -> dict:
    """Default: OWT and OKIT (+ anchor for control); with --policies, exactly those named."""
    if only is None:
        return POLICIES | (ANCHOR if variant == "control" else {})
    pool = POLICIES | JOINT | (ANCHOR if variant == "control" else {})
    return {name: rates for name, rates in pool.items() if name in only}
BOUNDS = ((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0))
LABOR_BOUNDS = (0.0, 0.60)
BUDGET_TOLERANCE = 1.0e-4
SOLVER = {"GKK_DBN_TOL": "1e-7", "GKK_AGG_TOL": "1e-6", "GKK_DBN_MAX_ITER": "700",
          "GKK_BUDGET_MAX_ITER": "100"}
SAVED_BENCHMARK = ROOT / "calibration/runs/business_financing_2022/rn_reform"
HEADLINE = ROOT / "calibration/runs/headline_revalidation_2022/validated_headline.json"
LOCK = HERE / "runs" / "driver.lock"


def calibration_env() -> dict[str, str]:
    """Identical to PolicyEvaluator's default (financing calibration)."""
    scf = json.loads((ROOT / "calibration/runs/scf_2022/best.json").read_text())["parameters"]
    fin = json.loads((ROOT / "calibration/runs/business_financing_2022/best.json").read_text())
    return {"GKK_RHO_Z": "0.1",
            "GKK_SIGMA_Z_EPS": format(scf["sigma_z_eps"], ".17g"),
            "GKK_X_HI": format(scf["x_hi"], ".17g"),
            "GKK_P1_X": format(scf["p1_x"], ".17g"),
            "GKK_P2_X": format(scf["p2_x"], ".17g"),
            "GKK_THETA_MAX": format(fin["theta_max"], ".17g")}


def bench_dir(variant: str) -> Path:
    return HERE / "runs" / variant / "benchmark"


def solve_benchmark(variant: str, threads: int) -> dict:
    folder = bench_dir(variant)
    done = folder / "done.json"
    if done.exists() and complete_benchmark(folder):
        print(f"[{variant}] benchmark already solved", flush=True)
        return json.loads(done.read_text())
    exe = HERE / "variants" / variant / "build" / "bench.a"
    if not exe.exists():
        raise SystemExit(f"{exe} missing; run make_variants.py first")
    if folder.exists():                       # partial output from an interrupted solve
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GKK_", "OMP_"))}
    env.update(calibration_env())
    env.update(SOLVER)
    env.update({"OMP_NUM_THREADS": str(threads), "OMP_DYNAMIC": "FALSE", "OMP_NESTED": "FALSE",
                "GKK_RESULT_FOLDER": str(folder.relative_to(ROOT)) + "/"})
    print(f"[{variant}] solving benchmark ({threads} threads)", flush=True)
    start = time.monotonic()
    with (folder / "run.log").open("w") as log:
        code = subprocess.run([str(exe)], cwd=ROOT, env=env, stdout=log,
                              stderr=subprocess.STDOUT).returncode
    elapsed = time.monotonic() - start
    output = read_kv(folder / "output.txt") if (folder / "output.txt").exists() else {}
    if code or output.get("Statistics_Schema") != 3 or not complete_benchmark(folder):
        raise RuntimeError(f"[{variant}] benchmark failed (exit {code}); see {folder / 'run.log'}")
    record = {"variant": variant, "elapsed_minutes": elapsed / 60,
              "environment": {k: env[k] for k in sorted(env) if k.startswith(("GKK_", "OMP_"))}}
    atomic_json(done, record)
    print(f"[{variant}] benchmark solved in {elapsed / 60:.1f} min", flush=True)
    return record


def evaluate_all(variants: list[str], threads: int, max_parallel: int,
                 only: list[str] | None = None) -> dict:
    evaluators, jobs = {}, []
    for v in variants:
        evaluators[v] = PolicyEvaluator(
            root=ROOT, executable=HERE / "variants" / v / "build" / "eval.a",
            benchmark=bench_dir(v), run_root=HERE / "runs" / v / "policies",
            threads=threads, bounds=BOUNDS, labor_bounds=LABOR_BOUNDS,
            budget_tolerance=BUDGET_TOLERANCE, fixed_labor=False, calibration_env=None)
        if evaluators[v].calibration_env != calibration_env():
            raise SystemExit("evaluator calibration differs from the benchmark calibration")
        jobs += [(v, name, rates) for name, rates in policy_set(v, only).items()]

    def run(job):
        v, name, rates = job
        try:
            result = evaluators[v].evaluate_rates(rates)
            return v, name, {"status": "ok", **result}
        except Exception as exc:              # one failure must not stop the others
            return v, name, {"status": "failed", "error": str(exc)}

    # Each solver holds roughly 3 GB, so memory, not cores, limits parallel jobs.
    print(f"evaluating {len(jobs)} policies, {max_parallel} at a time ({threads} threads each)",
          flush=True)
    results: dict = {}
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        for v, name, result in pool.map(run, jobs):
            results.setdefault(v, {})[name] = result
            print(f"[{v}] {name}: {result.get('status')} "
                  f"CE2_NB={result.get('ce2_newborn', float('nan')):.4f}", flush=True)
    return results


def benchmark_moments(folder: Path) -> dict:
    out = read_kv(folder / "output.txt")
    ent = read_kv(folder / "Entrepreneur_10_50.txt")
    return {"entrepreneur_population_share": ent["Profits/Before_Tax_Income>50%"] / 100,
            "entrepreneur_wealth_share": ent["Entreprenur_50_A_Share"] / 100,
            "entrepreneurs_in_top1_share": ent["Top_01_Entrepreneur_50"] / 100,
            **{k: out[k] for k in ["Wealth_Top_1%", "Wealth_Top_0.1%", "Debt_Output",
                                   "Wealth_Output", "KBAR", "YBAR", "CBAR", "GBAR", "R", "wage"]}}


def cached_policies(variant: str) -> dict:
    """Validated results from the evaluator cache, keyed by policy name."""
    found = {}
    wanted = POLICIES | JOINT | (ANCHOR if variant == "control" else {})
    for path in (HERE / "runs" / variant / "policies").glob("v2_*/*/result.json"):
        r = json.loads(path.read_text())
        for name, rates in wanted.items():
            if r.get("status") == "ok" and all(abs(a - b) < 1e-12 for a, b in
                                               zip((r["tau_w"], r["tau_k"], r["tau_bq"]), rates)):
                manifest = json.loads((path.parents[1] / "manifest.json").read_text())
                r["dbn_max_iter"] = int(manifest["environment"]["GKK_DBN_MAX_ITER"])
                found[name] = r
    return found


def summarise() -> None:
    headline = json.loads(HEADLINE.read_text())["points"]
    table = {"saved_benchmark": {"benchmark": benchmark_moments(SAVED_BENCHMARK),
                                 "policies": {n: headline[n] for n in POLICIES | JOINT}}}
    for v in VARIANTS:
        if (bench_dir(v) / "done.json").exists():
            table[v] = {"benchmark": benchmark_moments(bench_dir(v)), "policies": cached_policies(v)}
    fields = ["ce2_newborn", "ce2_population", "tau_l", "output_growth", "top1_wealth_share"]
    lines = ["# Model-specification sensitivity (financing calibration, parameters fixed)", "",
             "Each variant is compared with its own benchmark solved from scratch.  "
             "`saved_benchmark` is the published headline (saved benchmark).", "",
             "## Benchmark moments", "",
             "| Variant | Ent. pop. | Ent. wealth | Ent. in top 1% | Top 1% | Top 0.1% | Debt/Y | K | Y |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for v, t in table.items():
        b = t["benchmark"]
        lines.append(f"| {v} | {100*b['entrepreneur_population_share']:.2f}% | "
                     f"{100*b['entrepreneur_wealth_share']:.2f}% | {100*b['entrepreneurs_in_top1_share']:.2f}% | "
                     f"{100*b['Wealth_Top_1%']:.2f}% | {100*b['Wealth_Top_0.1%']:.2f}% | "
                     f"{b['Debt_Output']:.4f} | {b['KBAR']:.4f} | {b['YBAR']:.4f} |")
    lines += ["", "## Policies (relative to each variant's own benchmark)", "",
              "| Variant | Policy | Newborn CE2 | Population CE2 | Labour tax | Output | Top 1% | Max iter |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for v, t in table.items():
        for name, r in sorted(t["policies"].items()):
            lines.append(f"| {v} | {name} | {r['ce2_newborn']:.3f}% | {r['ce2_population']:.3f}% | "
                         f"{100*r['tau_l']:.2f}% | {r['output_growth']:+.2f}% | {100*r['top1_wealth_share']:.2f}% | "
                         f"{r.get('dbn_max_iter', 700)} |")
    if "control" in table:
        lines += ["", "## Effects relative to the control (newborn CE2, percentage points)", ""]
        for v in [x for x in VARIANTS if x != "control" and x in table]:
            for name in POLICIES | JOINT:
                a, b = table["control"]["policies"].get(name), table[v]["policies"].get(name)
                if a and b:
                    lines.append(f"- {v}, {name}: {b['ce2_newborn'] - a['ce2_newborn']:+.3f}")
    atomic_json(HERE / "results.json", {"fields": fields, "table": table})
    (HERE / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", nargs="+", default=VARIANTS, choices=VARIANTS)
    parser.add_argument("--threads-bench", type=int, default=4)
    parser.add_argument("--threads-policy", type=int, default=4)
    parser.add_argument("--max-parallel", type=int, default=4,
                        help="policy evaluations run at once (each needs about 3 GB)")
    parser.add_argument("--policies", nargs="+", choices=list(POLICIES) + list(ANCHOR) + list(JOINT),
                        help="evaluate only these policies (benchmarks must already be solved)")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise()
        return 0
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        pid = int(LOCK.read_text().strip() or 0)
        try:
            os.kill(pid, 0)
            raise SystemExit(f"another driver (pid {pid}) is running; stop it first")
        except ProcessLookupError:
            pass                                  # stale lock from a stopped run
    LOCK.write_text(str(os.getpid()))
    try:
        def attempt(v):
            try:
                solve_benchmark(v, args.threads_bench)
                return v, None
            except Exception as exc:              # keep the other variants going
                return v, str(exc)

        with ThreadPoolExecutor(max_workers=len(args.variants)) as pool:
            outcome = list(pool.map(attempt, args.variants))
        failed = {v: err for v, err in outcome if err}
        for v, err in failed.items():
            print(f"[{v}] BENCHMARK FAILED: {err}", flush=True)
        solved = [v for v, err in outcome if not err]
        if solved:
            evaluate_all(solved, args.threads_policy, args.max_parallel, args.policies)
        summarise()
        if failed:
            return 1
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

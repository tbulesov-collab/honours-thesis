#!/usr/bin/env python3
"""Tier-1 robustness checks from GKKOC Section 7 / Appendix E.5, with the thesis model.

  ontop   GKKOC Table E.10 (vi)-(ix): a wealth tax added ON TOP of the existing system
          (capital-income tax 25%, estate tax 40%), at 2% and at the thesis's optimal
          3.062%.  Two uses of the new revenue:
            wasted     labour tax fixed at the benchmark (fixed-labour evaluator); the
                       revenue surplus buys nothing that enters utility
            rebated    labour tax lowered to keep revenue at the benchmark
          Thesis calibration and saved benchmark, as in the reported tables.
  looser  GKKOC Table E.10 (i): looser borrowing constraints.  theta_max is re-fitted so
          that debt/output is 2.5 instead of 1.5629, with every other parameter at the
          thesis calibration (GKKOC likewise re-fit only the constraint).  Then:
            OWT sweep   tau_w {1.5, 2, 2.5, 3.062, 3.5}%   (tau_k 0, tau_b 40%)
            OKIT sweep  tau_k {-5, -10, -13.618, -20}%     (tau_w 0, tau_b 40%)
            joint       7%/-50%/40% (reported best grid point), 7%/-50%/0 and 6%/-50%/0
          The baseline comparison is the freshly solved thesis benchmark
          (model_spec_sensitivity_2022/runs/control/benchmark), for which OWT, OKIT and
          7%/-50%/40% already exist; 7%/-50%/0 is evaluated against it here.

Schedule: the theta_max fit (sequential solves) and the five fixed-rate points (ontop
plus the baseline corner) run side by side, then the 12 looser-constraint policies
run --max-parallel at a time.  Executables: variants/control/build/{bench,eval}.a
(live sources, checked against provenance.json) and the fixed-labour build, which was
used for the validated headline.  GKK_DBN_MAX_ITER=2000.  Outputs only under
experiments/robustness_gkkoc_2022/runs/.  Re-running resumes from the caches.

    python3 experiments/robustness_gkkoc_2022/tier1.py --check-only
    python3 experiments/robustness_gkkoc_2022/tier1.py
    python3 experiments/robustness_gkkoc_2022/tier1.py --summary-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SENS = ROOT / "experiments" / "model_spec_sensitivity_2022"
sys.path[:0] = [str(ROOT / "tools"), str(SENS)]

import recalibrate as rc                                        # noqa: E402
from policy_evaluation import PolicyEvaluator, atomic_json, read_kv  # noqa: E402

RUNS = HERE / "runs"
LOCK = RUNS / "driver.lock"
OTHER_LOCKS = [SENS / "recal" / "driver.lock", SENS / "runs" / "driver.lock",
               ROOT / "experiments" / "policy_reoptimization_2022" / "runs" / "driver.lock"]
EVAL = SENS / "variants" / "control" / "build" / "eval.a"
FIXED_EVAL = ROOT / "experiments" / "joint_tax_fixed_labor" / "build" / "GKK_Main_fixed_labor.a"
SAVED_BENCH = ROOT / "calibration" / "runs" / "business_financing_2022" / "rn_reform"
FRESH_BENCH = SENS / "runs" / "control" / "benchmark"
SCF_BEST = ROOT / "calibration" / "runs" / "scf_2022" / "best.json"
FIN_BEST = ROOT / "calibration" / "runs" / "business_financing_2022" / "best.json"
FIXED_RESULTS = SENS / "results.json"

WIDE = ((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0))
LABOR_BOUNDS = (0.0, 0.60)
BUDGET_TOLERANCE = 1.0e-4
OWT_RATE = 0.030618034
ONTOP = {"ontop_2": (0.02, 0.25, 0.40), "ontop_owt": (OWT_RATE, 0.25, 0.40)}
BASELINE_CORNER = (0.07, -0.50, 0.0)
DEBT_TARGET, DEBT_TOL, FIT_MAX_ITER = 2.5, 0.01, 8
# Follow-up (--part rbracket): the OKIT points failed under the looser constraints when
# the inherited interest-rate search jumped to R = 3.83.  make_rbracket.py builds a copy
# whose search is bounded to [-0.1, 0.5] and starts at the current R.  Two points that
# converged with the original build are re-evaluated as a consistency check.
RB_DIR = HERE / "variant_rbracket"
RB_EVAL = RB_DIR / "build" / "eval.a"
RB_JOBS = ([(f"okit_{k:g}", (0.0, k, 0.40)) for k in (-0.05, -0.10, -0.13618034, -0.20)]
           + [("check_owt_0.025", (0.025, 0.0, 0.40)), ("check_joint_6_50_0", (0.06, -0.50, 0.0))])
RB_CHECK_TOL = 0.01      # pp of newborn CE2
LOOSER = ([(f"owt_{w:g}", (w, 0.0, 0.40)) for w in (0.015, 0.02, 0.025, OWT_RATE, 0.035)]
          + [(f"okit_{k:g}", (0.0, k, 0.40)) for k in (-0.05, -0.10, -0.13618034, -0.20)]
          + [("joint_7_50_40", (0.07, -0.50, 0.40)), ("joint_7_50_0", (0.07, -0.50, 0.0)),
             ("joint_6_50_0", (0.06, -0.50, 0.0))])


def thesis_params() -> dict[str, float]:
    return {k: float(v) for k, v in json.loads(SCF_BEST.read_text())["parameters"].items()}


def evaluator(benchmark: Path, run_root: Path, threads: int, *, fixed=False, env=None, exe=None):
    return PolicyEvaluator(root=ROOT, executable=exe or (FIXED_EVAL if fixed else EVAL),
                           benchmark=benchmark, run_root=run_root, threads=threads,
                           bounds=WIDE, labor_bounds=LABOR_BOUNDS,
                           budget_tolerance=BUDGET_TOLERANCE, fixed_labor=fixed,
                           calibration_env=env)


def run_jobs(jobs: list, max_parallel: int, out: str) -> None:
    """jobs: (name, evaluator, rates).  Results go to runs/<out> as they finish."""
    path = RUNS / out
    records = json.loads(path.read_text()) if path.exists() else {}

    def run(job):
        name, ev, rates = job
        try:
            r = ev.evaluate_rates(rates)
            rec = {"status": "ok", **r, "benchmark": str(ev.benchmark)}
        except Exception as exc:                      # one failure must not stop the rest
            rec = {"status": "failed", "error": str(exc), "rates": list(rates)}
        print(f"[{out}] {name}: " + (f"CE2 {rec['ce2_newborn']:.3f}  tau_l {100*rec['tau_l']:.2f}%"
                                     if rec["status"] == "ok" else f"FAILED {rec['error']}"), flush=True)
        return name, rec

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        for name, rec in pool.map(run, jobs):
            records[name] = rec
            atomic_json(path, records)


# --------------------------------------------------- looser constraints: theta fit

def fit_theta(threads: int) -> dict:
    """Regula falsi (Illinois) on debt/output in theta_max; low end = thesis benchmark."""
    rc.RECAL = RUNS / "looser"                       # solves go to runs/looser/control/solves
    params = thesis_params()
    theta0 = float(json.loads(FIN_BEST.read_text())["theta_max"])
    d0 = read_kv(FRESH_BENCH / "output.txt")["Debt_Output"]
    path = [{"theta_max": theta0, "debt_output": d0, "source": "fresh thesis benchmark"}]

    def at(theta: float) -> tuple[float, Path]:
        m, folder = rc.solve("control", {**params, "theta_max": theta}, threads)
        path.append({"theta_max": theta, "debt_output": m["debt_output"],
                     "folder": str(folder.relative_to(ROOT))})
        print(f"[theta fit] theta_max={theta:.4f} debt/output={m['debt_output']:.4f}", flush=True)
        return m["debt_output"], folder

    lo, d_lo, f_lo = theta0, d0, FRESH_BENCH
    hi = 8.0
    d_hi, f_hi = at(hi)
    while d_hi < DEBT_TARGET:                         # expand until bracketed
        if hi >= 40:
            raise RuntimeError(f"debt/output {d_hi:.3f} still below {DEBT_TARGET} at theta {hi}")
        lo, d_lo, f_lo = hi, d_hi, f_hi
        hi = hi * 1.6
        d_hi, f_hi = at(hi)
    best = min([(abs(d_lo - DEBT_TARGET), lo, d_lo, f_lo), (abs(d_hi - DEBT_TARGET), hi, d_hi, f_hi)])
    side = 0
    for _ in range(FIT_MAX_ITER):
        if best[0] <= DEBT_TOL:
            break
        g_lo, g_hi = d_lo - DEBT_TARGET, d_hi - DEBT_TARGET
        mid = (lo * g_hi - hi * g_lo) / (g_hi - g_lo)
        mid = min(hi - 1e-3, max(lo + 1e-3, mid))
        d_mid, f_mid = at(mid)
        best = min(best, (abs(d_mid - DEBT_TARGET), mid, d_mid, f_mid))
        if d_mid < DEBT_TARGET:
            lo, d_lo, f_lo = mid, d_mid, f_mid
            if side == -1:
                d_hi = DEBT_TARGET + (d_hi - DEBT_TARGET) / 2     # Illinois step
            side = -1
        else:
            hi, d_hi, f_hi = mid, d_mid, f_mid
            if side == 1:
                d_lo = DEBT_TARGET + (d_lo - DEBT_TARGET) / 2
            side = 1
    gap, theta, debt, folder = best
    if folder == FRESH_BENCH:
        raise RuntimeError("theta fit did not move from the thesis benchmark")
    out = {"theta_max": theta, "debt_output": debt, "target": DEBT_TARGET, "gap": debt - DEBT_TARGET,
           "within_tolerance": gap <= DEBT_TOL, "parameters": {**params, "theta_max": theta},
           "benchmark": str(Path(folder).relative_to(ROOT)), "path": path}
    atomic_json(RUNS / "looser_theta.json", out)
    print(f"[theta fit] done: theta_max={theta:.4f}, debt/output={debt:.4f} (target {DEBT_TARGET})",
          flush=True)
    return out


# --------------------------------------------------------------------------- summary

def policy_extra(rec: dict, bench: Path) -> dict:
    o = read_kv(ROOT / rec["result_directory"] / "output_exp.txt")
    b, s = read_kv(bench / "output.txt"), read_kv(bench / "TFP_Star.txt")
    alpha = 0.40
    return {"K": 100 * (o["KBAR"] / b["KBAR"] - 1), "TFP": 100 * (o["TFP_Q"] / b["TFP_Q"] - 1),
            "misalloc": 1 - (o["TFP_Q"] / s["TFP_Star"]) ** alpha,
            "misalloc_bench": 1 - (b["TFP_Q"] / s["TFP_Star"]) ** alpha}


def summarise() -> None:
    lines = ["# GKKOC Tier-1 robustness checks with the thesis model", ""]
    load = lambda n: json.loads((RUNS / n).read_text()) if (RUNS / n).exists() else {}  # noqa: E731
    side, looser = load("side.json"), load("looser_policies.json")
    theta = load("looser_theta.json")

    lines += ["## Wealth tax on top of the existing system (GKKOC Table E.10 vi-ix)", "",
              "Thesis calibration, saved benchmark; capital-income tax stays 25%, estate tax 40%.  "
              "*Wasted*: labour tax fixed, surplus revenue not used for anything valued.  "
              "*Rebated*: labour tax lowered to keep revenue at the benchmark.", "",
              "| Wealth tax | Revenue use | Labour tax | Newborn CE2 | Population CE2 | CE1 | Output | "
              "Consumption | K | TFP | GKKOC CE2 |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    gk = {("ontop_2", "wasted"): "−9.9", ("ontop_2", "rebated"): "0.0",
          ("ontop_owt", "wasted"): "−14.2", ("ontop_owt", "rebated"): "−1.0"}
    for name in ONTOP:
        for use in ("wasted", "rebated"):
            r = side.get(f"{name}_{use}")
            if not r or r["status"] != "ok":
                lines.append(f"| {100*ONTOP[name][0]:.2f}% | {use} | {'FAILED' if r else 'pending'} |")
                continue
            x = policy_extra(r, SAVED_BENCH)
            lines.append(f"| {100*r['tau_w']:.2f}% | {use} | {100*r['tau_l']:.2f}% | {r['ce2_newborn']:.2f} | "
                         f"{r['ce2_population']:.2f} | {r['ce1_newborn']:.2f} | {r['output_growth']:+.2f}% | "
                         f"{r['consumption_growth']:+.2f}% | {x['K']:+.2f}% | {x['TFP']:+.2f}% | "
                         f"{gk[(name, use)]} |")
    lines += ["", "GKKOC's on-top experiments use 2% and their 3.03% optimum.", ""]

    lines += ["## Looser borrowing constraints (GKKOC Table E.10 i)", ""]
    if theta:
        p = theta["path"]
        lines += [f"theta_max re-fitted to debt/output {theta['debt_output']:.3f} (target "
                  f"{DEBT_TARGET}): theta_max = {theta['theta_max']:.3f} (thesis "
                  f"{p[0]['theta_max']:.3f}, debt/output {p[0]['debt_output']:.3f}).  Fit path: "
                  + ", ".join(f"{q['theta_max']:.2f}→{q['debt_output']:.3f}" for q in p) + ".", ""]
        bench = ROOT / theta["benchmark"]
        bo, fo = read_kv(bench / "output.txt"), read_kv(FRESH_BENCH / "output.txt")
        s_new, s_old = read_kv(bench / "TFP_Star.txt"), read_kv(FRESH_BENCH / "TFP_Star.txt")
        lines += ["| Benchmark | Debt/output | Top 1% | Top 0.1% | Misallocation |", "|---|---:|---:|---:|---:|",
                  f"| thesis (θ {p[0]['theta_max']:.3f}) | {fo['Debt_Output']:.3f} | {100*fo['Wealth_Top_1%']:.2f}% | "
                  f"{100*fo['Wealth_Top_0.1%']:.2f}% | {1-(fo['TFP_Q']/s_old['TFP_Star'])**0.4:.3f} |",
                  f"| looser (θ {theta['theta_max']:.3f}) | {bo['Debt_Output']:.3f} | {100*bo['Wealth_Top_1%']:.2f}% | "
                  f"{100*bo['Wealth_Top_0.1%']:.2f}% | {1-(bo['TFP_Q']/s_new['TFP_Star'])**0.4:.3f} |", ""]
    fixed = json.loads(FIXED_RESULTS.read_text())["table"]["control"]["policies"] if FIXED_RESULTS.exists() else {}
    base = {f"owt_{OWT_RATE:g}": fixed.get("owt"), f"okit_{-0.13618034:g}": fixed.get("okit"),
            "joint_7_50_40": fixed.get("s5_4"), "joint_7_50_0": side.get("baseline_7_50_0")}
    lines += ["| Policy | τ_w | τ_k | τ_b | Baseline CE2 | Looser CE2 | Looser labour tax | Looser output | "
              "Misallocation (bench → policy) |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, rates in LOOSER:
        r = looser.get(name)
        b = base.get(name)
        bcell = f"{b['ce2_newborn']:.2f}" if b and b.get("status", "ok") == "ok" else "—"
        if not r or r["status"] != "ok":
            lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.1f}% | {100*rates[2]:.0f}% | "
                         f"{bcell} | {'FAILED' if r else 'pending'} | | | |")
            continue
        x = policy_extra(r, ROOT / theta["benchmark"])
        lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.1f}% | {100*rates[2]:.0f}% | {bcell} | "
                     f"{r['ce2_newborn']:.2f} | {100*r['tau_l']:.2f}% | {r['output_growth']:+.2f}% | "
                     f"{x['misalloc_bench']:.3f} → {x['misalloc']:.3f} |")
    ok = {n: r for n, r in looser.items() if r.get("status") == "ok"}
    owt = [r for n, r in ok.items() if n.startswith("owt_")]
    okit = [r for n, r in ok.items() if n.startswith("okit_")]
    if owt and okit:
        bw, bk = max(owt, key=lambda r: r["ce2_newborn"]), max(okit, key=lambda r: r["ce2_newborn"])
        lines += ["", f"Looser constraints: best wealth tax {100*bw['tau_w']:.2f}% (CE2 {bw['ce2_newborn']:.2f}); "
                  f"best capital-income tax {100*bk['tau_k']:+.1f}% (CE2 {bk['ce2_newborn']:.2f}); "
                  f"wealth-tax advantage {bw['ce2_newborn'] - bk['ce2_newborn']:.2f} pp.  "
                  "GKKOC (debt/GDP 2.5): optimal wealth tax 2.34%, CE2 4.2."]
    rb = load("looser_rbracket.json")
    if rb:
        lines += ["", "## Looser constraints, bounded interest-rate search (OKIT follow-up)", "",
                  "Same benchmark, calibration and policies; evaluator built by make_rbracket.py "
                  "(interest-rate search on [-0.1, 0.5] from the current R instead of [-0.1, 10] "
                  "from 0.01).", "",
                  "| Policy | τ_w | τ_k | τ_b | CE2 | Labour tax | Output | Misallocation (bench → policy) | "
                  "Original build |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        orig_name = {"check_owt_0.025": "owt_0.025", "check_joint_6_50_0": "joint_6_50_0"}
        checks_ok = True
        for name, rates in RB_JOBS:
            r = rb.get(name)
            o = looser.get(orig_name.get(name, name), {})
            ocell = f"{o['ce2_newborn']:.3f}" if o.get("status") == "ok" else "failed"
            if not r or r["status"] != "ok":
                lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.1f}% | {100*rates[2]:.0f}% | "
                             f"{'FAILED' if r else 'pending'} | | | | {ocell} |")
                checks_ok &= not name.startswith("check_")
                continue
            x = policy_extra(r, ROOT / theta["benchmark"])
            lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.1f}% | {100*rates[2]:.0f}% | "
                         f"{r['ce2_newborn']:.3f} | {100*r['tau_l']:.2f}% | {r['output_growth']:+.2f}% | "
                         f"{x['misalloc_bench']:.3f} → {x['misalloc']:.3f} | {ocell} |")
            if name.startswith("check_"):
                checks_ok &= o.get("status") == "ok" and abs(r["ce2_newborn"] - o["ce2_newborn"]) <= RB_CHECK_TOL
        lines += ["", f"Consistency check (re-evaluated points within {RB_CHECK_TOL} pp of the original "
                  f"build): **{'passed' if checks_ok else 'NOT passed'}**."]
        okit_rb = [rb[n] for n, _ in RB_JOBS if n.startswith("okit_") and rb.get(n, {}).get("status") == "ok"]
        if okit_rb and owt and checks_ok:
            bk = max(okit_rb, key=lambda r: r["ce2_newborn"])
            bw = max(owt, key=lambda r: r["ce2_newborn"])
            lines.append(f"Looser constraints: best OKIT {100*bk['tau_k']:+.1f}% (CE2 {bk['ce2_newborn']:.2f}) "
                         f"against best OWT {100*bw['tau_w']:.2f}% (CE2 {bw['ce2_newborn']:.2f}): wealth-tax "
                         f"advantage {bw['ce2_newborn'] - bk['ce2_newborn']:.2f} pp (baseline 3.44).")
    (HERE / "tier1_results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ----------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--part", choices=["all", "rbracket"], default="all",
                        help="rbracket = OKIT follow-up with the bounded interest-rate build")
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--dbn-max-iter", type=int, default=2000)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise()
        return 0
    rc.check_builds(["control"])
    for p in (FIXED_EVAL, SAVED_BENCH / "output.txt", FRESH_BENCH / "done.json", SCF_BEST, FIN_BEST,
              FIXED_RESULTS):
        if not p.exists():
            raise SystemExit(f"missing input: {p}")
    if args.part == "rbracket":
        theta_file = RUNS / "looser_theta.json"
        prov_file = RB_DIR / "provenance.json"
        if not theta_file.exists():
            raise SystemExit("looser_theta.json missing: run the main part first")
        if not RB_EVAL.exists() or not prov_file.exists():
            raise SystemExit("bounded build missing: run make_rbracket.py first")
        prov = json.loads(prov_file.read_text())
        if rc.sha(RB_EVAL) != prov["eval_sha256"] or any(
                rc.sha(ROOT / n) != h for n, h in prov["live_sources_sha256"].items()):
            raise SystemExit("sources or bounded build changed since make_rbracket.py; rebuild")
        theta = json.loads(theta_file.read_text())
        if args.check_only:
            for name, rates in RB_JOBS:
                print(f"  {name:20s} {rates}")
            print(f"benchmark {theta['benchmark']}; executable {RB_EVAL.relative_to(ROOT)}.  "
                  "Check only: nothing was run.")
            return 0
    if args.check_only:
        print("side (theta fit runs alongside):")
        for name, rates in ONTOP.items():
            print(f"  {name}_wasted / {name}_rebated  {rates}")
        print(f"  baseline_7_50_0  {BASELINE_CORNER}  against {FRESH_BENCH.relative_to(ROOT)}")
        print(f"theta fit: thesis params {thesis_params()}, start theta "
              f"{json.loads(FIN_BEST.read_text())['theta_max']:.4f} (debt/output "
              f"{read_kv(FRESH_BENCH / 'output.txt')['Debt_Output']:.4f}) -> target {DEBT_TARGET}")
        print("looser policies:")
        for name, rates in LOOSER:
            print(f"  {name:16s} {rates}")
        print("Check only: nothing was run.")
        return 0
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["RECAL_DBN_MAX_ITER"] = str(args.dbn_max_iter)   # rc.solve
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)     # evaluators (inherit GKK_*)
    RUNS.mkdir(parents=True, exist_ok=True)
    for lock in (LOCK, *OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                os.kill(pid, 0)
                raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass
    LOCK.write_text(str(os.getpid()))
    if args.part == "rbracket":
        try:
            rb_ev = evaluator(ROOT / theta["benchmark"], RUNS / "looser_rbracket", args.threads,
                              env=rc.param_env(theta["parameters"]), exe=RB_EVAL)
            run_jobs([(n, rb_ev, r) for n, r in RB_JOBS], args.max_parallel, "looser_rbracket.json")
            summarise()
        finally:
            LOCK.unlink(missing_ok=True)
        return 0
    try:
        rebated = evaluator(SAVED_BENCH, RUNS / "ontop_rebated", args.threads)
        wasted = evaluator(SAVED_BENCH, RUNS / "ontop_wasted", args.threads, fixed=True)
        fresh = evaluator(FRESH_BENCH, RUNS / "baseline", args.threads)
        side = ([(f"{n}_wasted", wasted, r) for n, r in ONTOP.items()]
                + [(f"{n}_rebated", rebated, r) for n, r in ONTOP.items()]
                + [("baseline_7_50_0", fresh, BASELINE_CORNER)])
        with ThreadPoolExecutor(max_workers=2) as pool:      # theta fit || fixed-rate points
            fit = pool.submit(fit_theta, args.threads)
            side_done = pool.submit(run_jobs, side, 1, "side.json")
            side_done.result()
            theta = fit.result()
        summarise()
        looser_ev = evaluator(ROOT / theta["benchmark"], RUNS / "looser_policies", args.threads,
                              env=rc.param_env(theta["parameters"]))
        run_jobs([(n, looser_ev, r) for n, r in LOOSER], args.max_parallel, "looser_policies.json")
        summarise()
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

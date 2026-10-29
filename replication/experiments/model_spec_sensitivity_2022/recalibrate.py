#!/usr/bin/env python3
"""Re-calibrate the original and the productivity-corrected code, then evaluate the
reported policies (option A of the implementation sensitivity).

run_sensitivity.py holds every parameter at the thesis calibration.  Here each arm
repeats the thesis's two calibration steps with its own executable
(variants/<arm>/build/bench.a) and then evaluates the reported policies at their
reported rates:

    stage 1  SCF step: the procedure of tools/recalibrate_scf.py (one ridge-regularised
             Gauss-Newton step from the published vector, half-step fallback; same
             targets, steps, bounds and ridge, imported from that script).  Moments use
             the repaired percentile statistic (Statistics_Schema 3), as the live script
             does.
    stage 2  financing step: the procedure of tools/recalibrate_financing_2022.py
             (bracket theta_max from 2.8 and 3.1, then secant steps, tolerance 0.001,
             at most 6 steps).
    stage 3  OWT, OKIT, s5_1, s5_3, s5_4 at the reported rates with the validated
             evaluator (variants/<arm>/build/eval.a).  The benchmark is the chosen
             stage-2 solve: same executable and tolerances as run_sensitivity.py's
             benchmark solves.

Why a control arm: the thesis calibration ran before the percentile repair, so its SCF
step targeted the old top-1% statistic.  Re-running the procedure therefore moves the
original code as well, and the productivity effect is productivity minus control.

Outputs go only under experiments/model_spec_sensitivity_2022/recal/.  Re-running
resumes: finished solves (result.json) and evaluated policies (evaluator cache) are
reused.  Nothing in calibration/runs/ is read-modified-written.

    python3 experiments/model_spec_sensitivity_2022/recalibrate.py
    python3 experiments/model_spec_sensitivity_2022/recalibrate.py --summary-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import recalibrate_scf as scf                                   # noqa: E402
from recalibrate_financing_2022 import (PUBLISHED_THETA_MAX,     # noqa: E402
                                        financing_target)
from benchmark_cache import complete_benchmark  # noqa: E402
from policy_evaluation import PolicyEvaluator, atomic_json, read_kv  # noqa: E402
from run_sensitivity import (BOUNDS, BUDGET_TOLERANCE, HEADLINE,  # noqa: E402
                             JOINT, LABOR_BOUNDS, POLICIES)

ARMS = ["control", "productivity"]
RECAL = HERE / "recal"
LOCK = RECAL / "driver.lock"
CACHE = "recal-v1"
RIDGE = 0.10                    # recalibrate_scf.py default, used for the thesis step
FIN_TOLERANCE, FIN_MAX_ITER = 0.001, 6   # recalibrate_financing_2022.py defaults
THESIS_SCF = ROOT / "calibration/runs/scf_2022/best.json"
THESIS_FIN = ROOT / "calibration/runs/business_financing_2022/best.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_builds(arms: list[str]) -> None:
    """The variant executables must be built from the current live sources."""
    provenance = json.loads((HERE / "variants/provenance.json").read_text())
    for arm in arms:
        record = provenance[arm]
        for name, digest in record["live_sources_sha256"].items():
            if sha(ROOT / name) != digest:
                raise SystemExit(f"{name} changed since the variants were built; "
                                 "rerun make_variants.py first")
        for exe, digest in record["executables_sha256"].items():
            if sha(HERE / "variants" / arm / "build" / exe) != digest:
                raise SystemExit(f"variants/{arm}/build/{exe} does not match provenance.json")


# --------------------------------------------------------------------------- solves

def solver_env() -> dict[str, str]:
    return {"GKK_DBN_TOL": "1e-7", "GKK_AGG_TOL": "1e-6",
            "GKK_DBN_MAX_ITER": os.environ["RECAL_DBN_MAX_ITER"], "GKK_BUDGET_MAX_ITER": "100"}


def param_env(p: dict[str, float]) -> dict[str, str]:
    """One formatting for every solve and for the evaluator, so they match exactly."""
    return {"GKK_RHO_Z": "0.1",
            "GKK_SIGMA_Z_EPS": format(p["sigma_z_eps"], ".17g"),
            "GKK_X_HI": format(p["x_hi"], ".17g"),
            "GKK_P1_X": format(p["p1_x"], ".17g"),
            "GKK_P2_X": format(p["p2_x"], ".17g"),
            "GKK_THETA_MAX": format(p["theta_max"], ".17g")}


def moments(folder: Path) -> dict[str, float]:
    out = read_kv(folder / "output.txt")
    ent = read_kv(folder / "Entrepreneur_10_50.txt")
    return {"top1": out["Wealth_Top_1%"],
            "ent_top1": ent["Top_01_Entrepreneur_50"] / 100,
            "ent_wealth": ent["Entreprenur_50_A_Share"] / 100,
            "ent_pop": ent["Profits/Before_Tax_Income>50%"] / 100,
            "top01": out["Wealth_Top_0.1%"],
            "debt_output": out["Debt_Output"]}


def solve(arm: str, p: dict[str, float], threads: int) -> tuple[dict, Path]:
    """Solve one benchmark for this arm's executable; cached by parameters."""
    exe = HERE / "variants" / arm / "build" / "bench.a"
    env_p = param_env(p)
    key = json.dumps({"cache": CACHE, "exe": sha(exe), "params": env_p,
                      "solver": solver_env()}, sort_keys=True)
    folder = RECAL / arm / "solves" / hashlib.sha256(key.encode()).hexdigest()[:12]
    done = folder / "result.json"
    if done.exists() and complete_benchmark(folder):
        return json.loads(done.read_text())["moments"], folder
    if folder.exists():                          # partial output from an interrupted solve
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GKK_", "OMP_", "RECAL_"))}
    env.update(env_p)
    env.update(solver_env())
    env.update({"OMP_NUM_THREADS": str(threads), "OMP_DYNAMIC": "FALSE", "OMP_NESTED": "FALSE",
                "GKK_RESULT_FOLDER": str(folder.relative_to(ROOT)) + "/"})
    label = ", ".join(f"{k}={v:.6g}" for k, v in p.items())
    print(f"[{arm}] solving {folder.name}: {label}", flush=True)
    start = time.monotonic()
    with (folder / "run.log").open("w") as log:
        code = subprocess.run([str(exe)], cwd=ROOT, env=env, stdout=log,
                              stderr=subprocess.STDOUT).returncode
    elapsed = (time.monotonic() - start) / 60
    output = read_kv(folder / "output.txt") if (folder / "output.txt").exists() else {}
    if code or output.get("Statistics_Schema") != 3 or not complete_benchmark(folder):
        raise RuntimeError(f"[{arm}] solve failed (exit {code}); see {folder / 'run.log'}")
    m = moments(folder)
    atomic_json(done, {"arm": arm, "parameters": p, "moments": m, "elapsed_minutes": elapsed,
                       "environment": {k: env[k] for k in sorted(env)
                                       if k.startswith(("GKK_", "OMP_"))}})
    print(f"[{arm}] solved {folder.name} in {elapsed:.1f} min", flush=True)
    return m, folder


# ------------------------------------------------------------------ stage 1: SCF step

def vec(m: dict) -> np.ndarray:
    return np.array([m["top1"], m["ent_top1"], m["ent_wealth"]])


def as_params(x: np.ndarray, theta_max: float = PUBLISHED_THETA_MAX) -> dict[str, float]:
    return {**dict(zip(scf.NAMES, map(float, x))), "theta_max": theta_max}


def scf_step(arm: str, threads: int, jac_parallel: int, iterations: int) -> dict:
    target = scf.targets(scf.DEFAULT_TARGET_FILE)
    x = scf.BASELINE.copy()
    m, folder = solve(arm, as_params(x), threads)
    path = [{"step": "published vector", "objective": scf.objective(vec(m), target)}]
    for it in range(1, iterations + 1):
        trials = []
        for j in range(len(x)):
            t = x.copy()
            t[j] = min(scf.UPPER[j], x[j] + scf.STEPS[j])
            trials.append(t)
        with ThreadPoolExecutor(max_workers=jac_parallel) as pool:
            jac_m = list(pool.map(lambda t: solve(arm, as_params(t), threads)[0], trials))
        jac = np.column_stack([(vec(mt) - vec(m)) / (t[j] - x[j])
                               for j, (t, mt) in enumerate(zip(trials, jac_m))])
        scaled = jac * scf.BASELINE[np.newaxis, :]
        delta = np.linalg.solve(scaled.T @ scaled + RIDGE * np.eye(len(x)),
                                scaled.T @ (target - vec(m)))
        best_obj = scf.objective(vec(m), target)
        accepted = None
        for share in (1.0, 0.5):                 # full step, then the half-step fallback
            cand = np.clip(x + share * scf.BASELINE * delta, scf.LOWER, scf.UPPER)
            mc, fc = solve(arm, as_params(cand), threads)
            obj = scf.objective(vec(mc), target)
            path.append({"step": f"iteration {it}, {share:g} step", "objective": obj})
            if obj < best_obj:
                accepted = (cand, mc, fc)
                break
        if accepted is None:
            print(f"[{arm}] no improving SCF step; keeping the current vector", flush=True)
            break
        x, m, folder = accepted
    result = {"parameters": dict(zip(scf.NAMES, map(float, x))), "moments": m,
              "targets": target.tolist(), "objective": scf.objective(vec(m), target),
              "path": path, "run_directory": str(folder.relative_to(ROOT))}
    atomic_json(RECAL / arm / "scf.json", result)
    print(f"[{arm}] SCF step done: objective {result['objective']:.3f}", flush=True)
    return result


# ------------------------------------------------------------ stage 2: financing step

def financing_step(arm: str, scf_params: dict, threads: int) -> dict:
    target = financing_target()

    def at(theta: float):
        m, f = solve(arm, {**scf_params, "theta_max": theta}, threads)
        return m["debt_output"], f

    low, high = PUBLISHED_THETA_MAX, 3.1
    with ThreadPoolExecutor(max_workers=2) as pool:  # 2.8 is normally the cached SCF solve
        (m_low, f_low), (m_high, f_high) = pool.map(at, [low, high])
    while m_high < target and high < 6.0:
        low, m_low, f_low = high, m_high, f_high
        high = min(6.0, high + 0.6)
        m_high, f_high = at(high)
    if not m_low <= target <= m_high:
        raise RuntimeError(f"[{arm}] financing target {target:.6f} not bracketed "
                           f"({m_low:.6f}, {m_high:.6f})")
    best = min([(abs(m_low - target), low, m_low, f_low),
                (abs(m_high - target), high, m_high, f_high)])
    for it in range(1, FIN_MAX_ITER + 1):
        mid = low + (target - m_low) * (high - low) / (m_high - m_low)
        mid = min(high - 1e-6, max(low + 1e-6, mid))
        m_mid, f_mid = at(mid)
        best = min(best, (abs(m_mid - target), mid, m_mid, f_mid))
        print(f"[{arm}] financing {it}: theta_max={mid:.8f} gap={m_mid - target:+.8f}", flush=True)
        if abs(m_mid - target) <= FIN_TOLERANCE:
            break
        if m_mid < target:
            low, m_low, f_low = mid, m_mid, f_mid
        else:
            high, m_high, f_high = mid, m_mid, f_mid
    gap, theta, model, folder = best
    result = {"theta_max": theta, "debt_output": model, "target": target,
              "gap": model - target, "parameters": {**scf_params, "theta_max": theta},
              "moments": moments(folder), "benchmark": str(folder.relative_to(ROOT))}
    atomic_json(RECAL / arm / "financing.json", result)
    print(f"[{arm}] financing step done: theta_max={theta:.6f}, gap {model - target:+.2e}",
          flush=True)
    return result


def calibrate(arm: str, args) -> dict:
    s = scf_step(arm, args.threads_bench, args.jac_parallel, args.iterations)
    return financing_step(arm, s["parameters"], args.threads_bench)


# ---------------------------------------------------------------- stage 3: policies

def evaluate(arms: list[str], threads: int, max_parallel: int) -> None:
    evaluators, jobs = {}, []
    for arm in arms:
        fin = json.loads((RECAL / arm / "financing.json").read_text())
        evaluators[arm] = PolicyEvaluator(
            root=ROOT, executable=HERE / "variants" / arm / "build" / "eval.a",
            benchmark=ROOT / fin["benchmark"], run_root=RECAL / arm / "policies",
            threads=threads, bounds=BOUNDS, labor_bounds=LABOR_BOUNDS,
            budget_tolerance=BUDGET_TOLERANCE, fixed_labor=False,
            calibration_env=param_env(fin["parameters"]))
        jobs += [(arm, name, rates) for name, rates in (POLICIES | JOINT).items()]

    def run(job):
        arm, name, rates = job
        try:
            return arm, name, {"status": "ok", **evaluators[arm].evaluate_rates(rates)}
        except Exception as exc:                  # one failure must not stop the others
            return arm, name, {"status": "failed", "error": str(exc)}

    print(f"evaluating {len(jobs)} policies, {max_parallel} at a time ({threads} threads each)",
          flush=True)
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        for arm, name, r in pool.map(run, jobs):
            print(f"[{arm}] {name}: {r['status']} CE2_NB={r.get('ce2_newborn', float('nan')):.4f}"
                  + (f" ({r['error']})" if r["status"] == "failed" else ""), flush=True)


def cached_policies(arm: str) -> dict:
    found = {}
    for path in (RECAL / arm / "policies").glob("v2_*/*/result.json"):
        r = json.loads(path.read_text())
        for name, rates in (POLICIES | JOINT).items():
            if r.get("status") == "ok" and all(abs(a - b) < 1e-12 for a, b in
                                               zip((r["tau_w"], r["tau_k"], r["tau_bq"]), rates)):
                found[name] = r
    return found


# ------------------------------------------------------------------------- summary

def summarise() -> None:
    headline = json.loads(HEADLINE.read_text())["points"]
    fixed = json.loads((HERE / "results.json").read_text())["table"]
    thesis_scf = json.loads(THESIS_SCF.read_text())
    thesis_fin = json.loads(THESIS_FIN.read_text())
    target = scf.targets(scf.DEFAULT_TARGET_FILE)
    arms = {}
    for arm in ARMS:
        if (RECAL / arm / "financing.json").exists():
            arms[arm] = {"scf": json.loads((RECAL / arm / "scf.json").read_text()),
                         "financing": json.loads((RECAL / arm / "financing.json").read_text()),
                         "policies": cached_policies(arm)}
    names = list(POLICIES | JOINT)
    lines = ["# Re-calibration sensitivity (option A)", "",
             "Each arm repeats the thesis's SCF and financing calibration steps with its own "
             "code (repaired percentile statistic), then evaluates the reported policies at "
             "their reported rates against its own benchmark.", "",
             "## Calibrated parameters", "",
             "| Parameter | Thesis | " + " | ".join(f"Re-calibrated {a}" for a in arms) + " |",
             "|---|---:|" + "---:|" * len(arms)]
    thesis_params = {**thesis_scf["parameters"], "theta_max": thesis_fin["theta_max"]}
    for k in [*scf.NAMES, "theta_max"]:
        lines.append(f"| {k} | {thesis_params[k]:.6f} | "
                     + " | ".join(f"{a['financing']['parameters'][k]:.6f}" for a in arms.values())
                     + " |")
    lines += ["", "## Benchmark moments (financing-step benchmark; repaired statistic)", "",
              "| Moment | Target | Thesis calibration, original code | "
              + " | ".join(f"Re-calibrated {a}" for a in arms) + " |",
              "|---|---:|---:|" + "---:|" * len(arms)]
    tb = fixed["control"]["benchmark"]
    thesis_m = {"top1": tb["Wealth_Top_1%"], "ent_top1": tb["entrepreneurs_in_top1_share"],
                "ent_wealth": tb["entrepreneur_wealth_share"],
                "ent_pop": tb["entrepreneur_population_share"],
                "top01": tb["Wealth_Top_0.1%"], "debt_output": tb["Debt_Output"]}
    rows = [("Top 1% wealth share", "top1", target[0]),
            ("Entrepreneurs in top 1%", "ent_top1", target[1]),
            ("Entrepreneur wealth share", "ent_wealth", target[2]),
            ("Entrepreneur population", "ent_pop", None),
            ("Top 0.1% wealth share", "top01", None)]
    for label, key, t in rows:
        lines.append(f"| {label} | {'' if t is None else f'{100 * t:.2f}%'} | "
                     f"{100 * thesis_m[key]:.2f}% | "
                     + " | ".join(f"{100 * a['financing']['moments'][key]:.2f}%" for a in arms.values())
                     + " |")
    lines.append(f"| Debt/output | {financing_target():.4f} | {thesis_m['debt_output']:.4f} | "
                 + " | ".join(f"{a['financing']['debt_output']:.4f}" for a in arms.values()) + " |")
    lines.append("| SCF objective (at theta_max = 2.8) | 0 | "
                 f"{thesis_scf['objective']:.2f} (old statistic) | "
                 + " | ".join(f"{a['scf']['objective']:.2f}" for a in arms.values()) + " |")
    lines += ["", "## Newborn CE2 (%)", "",
              "| Policy | Thesis | Fixed params, control | Fixed params, productivity | "
              + " | ".join(f"Re-calibrated {a}" for a in arms) + " | Productivity effect, re-calibrated |",
              "|---|---:|---:|---:|" + "---:|" * len(arms) + "---:|"]
    for n in names:
        fc = fixed.get("control", {}).get("policies", {}).get(n)
        fp = fixed.get("productivity", {}).get("policies", {}).get(n)
        rec = [a["policies"].get(n) for a in arms.values()]
        eff = (f"{rec[1]['ce2_newborn'] - rec[0]['ce2_newborn']:+.3f}"
               if len(rec) == 2 and all(rec) else "")
        cell = lambda r: f"{r['ce2_newborn']:.3f}" if r else "—"   # noqa: E731
        lines.append(f"| {n} | {headline[n]['ce2_newborn']:.3f} | {cell(fc)} | {cell(fp)} | "
                     + " | ".join(cell(r) for r in rec) + f" | {eff} |")
    lines += ["", "OWT − OKIT gap (newborn CE2): "
              + ", ".join(f"{a}: {p['owt']['ce2_newborn'] - p['okit']['ce2_newborn']:.2f}"
                          for a, p in ((a, v["policies"]) for a, v in arms.items())
                          if "owt" in p and "okit" in p)]
    lines += ["", "## Policy details (re-calibrated)", "",
              "| Arm | Policy | Newborn CE2 | Population CE2 | Labour tax | Output | Top 1% | "
              "Agg. residual | Revenue gap |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for arm, a in arms.items():
        for n in names:
            r = a["policies"].get(n)
            if r:
                lines.append(f"| {arm} | {n} | {r['ce2_newborn']:.3f}% | {r['ce2_population']:.3f}% | "
                             f"{100 * r['tau_l']:.2f}% | {r['output_growth']:+.2f}% | "
                             f"{100 * r['top1_wealth_share']:.2f}% | {r['aggregate_residual']:.2e} | "
                             f"{r['revenue_relative_gap']:.1e} |")
    atomic_json(HERE / "recal_results.json", {"arms": arms, "thesis_parameters": thesis_params})
    (HERE / "recal_results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ---------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arms", nargs="+", default=ARMS, choices=ARMS)
    parser.add_argument("--threads-bench", type=int, default=4)
    parser.add_argument("--jac-parallel", type=int, default=2,
                        help="Jacobian solves at once per arm (each needs about 3 GB)")
    parser.add_argument("--iterations", type=int, default=1,
                        help="SCF ridge iterations (the thesis calibration used 1)")
    parser.add_argument("--threads-policy", type=int, default=3)
    parser.add_argument("--max-parallel", type=int, default=6,
                        help="policy evaluations at once (each needs about 2-3 GB)")
    parser.add_argument("--dbn-max-iter", type=int, default=2000)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise()
        return 0
    check_builds(args.arms)
    # One solver environment for every solve and for the evaluator (which inherits GKK_*).
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["RECAL_DBN_MAX_ITER"] = str(args.dbn_max_iter)
    os.environ.update(solver_env())
    RECAL.mkdir(parents=True, exist_ok=True)
    for lock in (LOCK, HERE / "runs" / "driver.lock"):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                os.kill(pid, 0)
                raise SystemExit(f"another driver (pid {pid}, {lock.name}) is running; stop it first")
            except ProcessLookupError:
                pass                                  # stale lock from a stopped run
    LOCK.write_text(str(os.getpid()))
    try:
        def attempt(arm):
            try:
                calibrate(arm, args)
                return arm, None
            except Exception as exc:                  # keep the other arm going
                return arm, str(exc)

        with ThreadPoolExecutor(max_workers=len(args.arms)) as pool:
            outcome = list(pool.map(attempt, args.arms))
        failed = {arm: err for arm, err in outcome if err}
        for arm, err in failed.items():
            print(f"[{arm}] CALIBRATION FAILED: {err}", flush=True)
        ready = [arm for arm, err in outcome if not err]
        if ready:
            evaluate(ready, args.threads_policy, args.max_parallel)
        summarise()
        return 1 if failed else 0
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())

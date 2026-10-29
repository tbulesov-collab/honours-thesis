#!/usr/bin/env python3
"""Policy rankings along the calibration's unidentified parameter direction (thesis Section 7.2.2).

The SCF calibration step fits four entrepreneurial parameters (sigma_z_eps, x_hi, p1_x,
p2_x) to three moments (top-1% wealth share, entrepreneurs in the top 1%, entrepreneur
wealth share). Its finite-difference Jacobian, saved in recal/control/solves, therefore
has a direction along which the three moments do not change to first order.

This driver moves the thesis parameters a step each way along that direction (proportional
changes, the largest component equal to --step), re-fits theta_max to the financing target
with the secant procedure of the financing step, and evaluates the thesis policies at their
reported rates against each side's own benchmark. The centre is the fixed-parameter control
of run_sensitivity.py (thesis parameters, fresh benchmark), so all three columns use the same
code, solver tolerances and evaluator settings. The summary reports each side's moments and
whether the rankings hold:

  * wealth tax beats the capital-income subsidy;
  * both 7%/-50% joint policies beat both separate policies;
  * removing the 40% estate tax at 7%/-50% raises newborn CE2;
  * the ordering of the three joint candidates (shown, not tested).

Outputs go only under experiments/model_spec_sensitivity_2022/flat/. Re-running resumes:
finished solves (result.json) and evaluated policies (evaluator cache) are reused. --plan
computes the direction and the two parameter vectors and runs no executable.

    python3 experiments/model_spec_sensitivity_2022/flat_direction.py --plan
    nohup caffeinate -i python3 experiments/model_spec_sensitivity_2022/flat_direction.py \\
        > experiments/model_spec_sensitivity_2022/flat_run.log 2>&1 &
    python3 experiments/model_spec_sensitivity_2022/flat_direction.py --summary-only
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
sys.path[:0] = [str(ROOT / "tools"), str(HERE), str(ROOT / "experiments" / "grid_accuracy_2022")]

import recalibrate as rc                                        # noqa: E402
import recalibrate_scf as scf                                   # noqa: E402
from recalibrate_financing_2022 import PUBLISHED_THETA_MAX, financing_target  # noqa: E402
from benchmark_cache import complete_benchmark                 # noqa: E402
from policy_evaluation import PolicyEvaluator, atomic_json, read_kv  # noqa: E402
from run_sensitivity import BOUNDS, BUDGET_TOLERANCE, JOINT, LABOR_BOUNDS, POLICIES  # noqa: E402

FLAT = HERE / "flat"
LOCK = FLAT / "driver.lock"
OTHER_LOCKS = [rc.LOCK, HERE / "runs" / "driver.lock",
               ROOT / "experiments" / "grid_accuracy_2022" / "runs" / "driver.lock"]
CACHE = "flat-v1"
SIDES = {"minus": -1.0, "plus": 1.0}
EXTRA = {"joint_bq0": (0.07, -0.50, 0.0)}          # 7%/-50% without estate tax
EVALUATED = POLICIES | JOINT | EXTRA
EXE = HERE / "variants" / "control" / "build"
FIN_TOLERANCE, FIN_MAX_ITER = rc.FIN_TOLERANCE, rc.FIN_MAX_ITER
LABELS = {"owt": "Separate wealth tax (3.06%)", "okit": "Separate subsidy (−13.62%)",
          "s5_1": "Three-tax candidate (4.91%, −30%, ≈0.1%)", "s5_3": "7.13%, −49.82%, 40%",
          "s5_4": "7%, −50%, 40% estate tax", "joint_bq0": "7%, −50%, no estate tax"}


# ---------------------------------------------------------------- the flat direction

def jacobian_direction() -> dict:
    """Null direction of the saved SCF-step Jacobian (control arm, proportional changes)."""
    solves = []
    for path in (rc.RECAL / "control" / "solves").glob("*/result.json"):
        r = json.loads(path.read_text())
        solves.append((np.array([r["parameters"][k] for k in scf.NAMES]),
                       r["parameters"]["theta_max"], np.array(rc.vec(r["moments"]))))
    base = [s for s in solves if np.allclose(s[0], scf.BASELINE) and abs(s[1] - PUBLISHED_THETA_MAX) < 1e-9]
    if len(base) != 1:
        raise SystemExit("saved Jacobian base solve not found in recal/control/solves")
    x0, m0 = base[0][0], base[0][2]
    cols = []
    for j in range(len(scf.NAMES)):
        trial = x0.copy()
        trial[j] = min(scf.UPPER[j], x0[j] + scf.STEPS[j])
        hit = [s for s in solves if np.allclose(s[0], trial) and abs(s[1] - PUBLISHED_THETA_MAX) < 1e-9]
        if len(hit) != 1:
            raise SystemExit(f"saved Jacobian solve for {scf.NAMES[j]} not found")
        cols.append((hit[0][2] - m0) / (trial[j] - x0[j]))
    scaled = np.column_stack(cols) * x0[np.newaxis, :]      # response to proportional changes
    _, sv, vt = np.linalg.svd(scaled)
    v = vt[-1] / np.abs(vt[-1]).max()
    if v[scf.NAMES.index("x_hi")] < 0:
        v = -v
    return {"names": list(scf.NAMES), "direction": v.tolist(), "singular_values": sv.tolist(),
            "scaled_jacobian": scaled.tolist(), "first_order_moment_change": (scaled @ v).tolist()}


def thesis_parameters() -> dict:
    p = json.loads(rc.THESIS_SCF.read_text())["parameters"]
    return {**{k: float(p[k]) for k in scf.NAMES},
            "theta_max": float(json.loads(rc.THESIS_FIN.read_text())["theta_max"])}


def side_parameters(step: float) -> dict:
    d, centre = jacobian_direction(), thesis_parameters()
    out = {}
    for side, sign in SIDES.items():
        p = {k: centre[k] * (1.0 + sign * step * d["direction"][i]) for i, k in enumerate(scf.NAMES)}
        for i, k in enumerate(scf.NAMES):
            if not scf.LOWER[i] <= p[k] <= scf.UPPER[i]:
                raise SystemExit(f"{side}: {k}={p[k]:.6g} outside the calibration bounds")
        out[side] = p
    return out


# --------------------------------------------------------------------------- solves

def solve(side: str, p: dict, threads: int) -> tuple[dict, Path]:
    """One benchmark with the control build; cached by parameters (as recalibrate.solve)."""
    exe = EXE / "bench.a"
    env_p = rc.param_env(p)
    key = json.dumps({"cache": CACHE, "exe": rc.sha(exe), "params": env_p,
                      "solver": rc.solver_env()}, sort_keys=True)
    folder = FLAT / side / "solves" / hashlib.sha256(key.encode()).hexdigest()[:12]
    done = folder / "result.json"
    if done.exists() and complete_benchmark(folder):
        return json.loads(done.read_text())["moments"], folder
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GKK_", "OMP_", "RECAL_"))}
    env.update(env_p)
    env.update(rc.solver_env())
    env.update({"OMP_NUM_THREADS": str(threads), "OMP_DYNAMIC": "FALSE", "OMP_NESTED": "FALSE",
                "GKK_RESULT_FOLDER": str(folder.relative_to(ROOT)) + "/"})
    print(f"[{side}] solving {folder.name}: " + ", ".join(f"{k}={v:.6g}" for k, v in p.items()), flush=True)
    start = time.monotonic()
    with (folder / "run.log").open("w") as log:
        code = subprocess.run([str(exe)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    elapsed = (time.monotonic() - start) / 60
    output = read_kv(folder / "output.txt") if (folder / "output.txt").exists() else {}
    if code or output.get("Statistics_Schema") != 3 or not complete_benchmark(folder):
        raise RuntimeError(f"[{side}] solve failed (exit {code}); see {folder / 'run.log'}")
    m = rc.moments(folder)
    atomic_json(done, {"side": side, "parameters": p, "moments": m, "elapsed_minutes": elapsed,
                       "environment": {k: env[k] for k in sorted(env) if k.startswith(("GKK_", "OMP_"))}})
    print(f"[{side}] solved {folder.name} in {elapsed:.1f} min (debt/output {m['debt_output']:.4f})", flush=True)
    return m, folder


def financing(side: str, scf_params: dict, theta0: float, threads: int) -> dict:
    """Secant on theta_max to the financing target, starting from the thesis value."""
    target = financing_target()

    def at(theta: float):
        m, f = solve(side, {**scf_params, "theta_max": theta}, threads)
        return theta, m["debt_output"], f

    with ThreadPoolExecutor(max_workers=2) as pool:
        (a, ma, fa), (b, mb, fb) = pool.map(at, [theta0, theta0 + 0.15])
    best = min([(abs(ma - target), a, ma, fa), (abs(mb - target), b, mb, fb)])
    for it in range(1, FIN_MAX_ITER + 1):
        if best[0] <= FIN_TOLERANCE or mb == ma:
            break
        c = b + (target - mb) * (b - a) / (mb - ma)
        c = min(6.0, max(1.0, c))
        c, mc, fc = at(c)
        best = min(best, (abs(mc - target), c, mc, fc))
        print(f"[{side}] financing {it}: theta_max={c:.8f} gap={mc - target:+.8f}", flush=True)
        a, ma, b, mb = b, mb, c, mc
    gap, theta, model, folder = best
    result = {"theta_max": theta, "debt_output": model, "target": target, "gap": model - target,
              "parameters": {**scf_params, "theta_max": theta}, "moments": rc.moments(folder),
              "benchmark": str(folder.relative_to(ROOT))}
    atomic_json(FLAT / side / "financing.json", result)
    print(f"[{side}] financing step done: theta_max={theta:.6f}, gap {model - target:+.2e}", flush=True)
    return result


# ------------------------------------------------------------------------ policies

def evaluate(sides: list[str], names: list[str], threads: int, max_parallel: int) -> None:
    evaluators, jobs = {}, []
    for side in sides:
        fin = json.loads((FLAT / side / "financing.json").read_text())
        evaluators[side] = PolicyEvaluator(
            root=ROOT, executable=EXE / "eval.a", benchmark=ROOT / fin["benchmark"],
            run_root=FLAT / side / "policies", threads=threads, bounds=BOUNDS,
            labor_bounds=LABOR_BOUNDS, budget_tolerance=BUDGET_TOLERANCE, fixed_labor=False,
            calibration_env=rc.param_env(fin["parameters"]))
        jobs += [(side, n, EVALUATED[n]) for n in names]

    def run(job):
        side, name, rates = job
        try:
            return side, name, {"status": "ok", **evaluators[side].evaluate_rates(rates)}
        except Exception as exc:                  # one failure must not stop the others
            return side, name, {"status": "failed", "error": str(exc)}

    print(f"evaluating {len(jobs)} policies, {max_parallel} at a time ({threads} threads each)", flush=True)
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        for side, name, r in pool.map(run, jobs):
            print(f"[{side}] {name}: {r['status']} CE2_NB={r.get('ce2_newborn', float('nan')):.4f}"
                  + (f" ({r['error']})" if r["status"] == "failed" else ""), flush=True)


def cached_policies(side: str) -> dict:
    found = {}
    for path in (FLAT / side / "policies").glob("v2_*/*/result.json"):
        r = json.loads(path.read_text())
        for name, rates in EVALUATED.items():
            if r.get("status") == "ok" and all(abs(a - b) < 1e-12 for a, b in
                                               zip((r["tau_w"], r["tau_k"], r["tau_bq"]), rates)):
                found[name] = r
    return found


def centre_results() -> tuple[dict, dict]:
    """Fixed-parameter control: thesis parameters, fresh benchmark (run_sensitivity.py)."""
    import run_grid_check as rgc                  # finds the control's 7%/-50%/0 result
    table = json.loads((HERE / "results.json").read_text())["table"]["control"]
    ce2 = {n: r["ce2_newborn"] for n, r in table["policies"].items() if n in EVALUATED}
    bq0 = rgc.control_results().get("joint_bq0")
    if bq0:
        ce2["joint_bq0"] = bq0["ce2_newborn"]
    b = table["benchmark"]
    moments = {"top1": b["Wealth_Top_1%"], "ent_top1": b["entrepreneurs_in_top1_share"],
               "ent_wealth": b["entrepreneur_wealth_share"], "ent_pop": b["entrepreneur_population_share"],
               "top01": b["Wealth_Top_0.1%"], "debt_output": b["Debt_Output"]}
    return ce2, moments


# ------------------------------------------------------------------------- summary

def checks_for(ce2: dict) -> dict:
    need = ["owt", "okit", "s5_4", "joint_bq0"]
    if not all(n in ce2 for n in need):
        return {}
    joint = [n for n in ("s5_1", "s5_3", "s5_4") if n in ce2]
    return {"wealth_tax_lead_pp": ce2["owt"] - ce2["okit"],
            "wealth_tax_beats_subsidy": ce2["owt"] > ce2["okit"],
            "joint_beats_separate": min(ce2["s5_4"], ce2["joint_bq0"]) > max(ce2["owt"], ce2["okit"]),
            "estate_removal_gain_pp": ce2["joint_bq0"] - ce2["s5_4"],
            "estate_removal_raises_welfare": ce2["joint_bq0"] > ce2["s5_4"],
            "joint_order": sorted(joint, key=lambda n: -ce2[n])}


def summarise(step: float) -> None:
    d = jacobian_direction()
    centre_ce2, centre_m = centre_results()
    cols = {"minus": {}, "centre": {"ce2": centre_ce2, "moments": centre_m,
                                    "parameters": thesis_parameters()}, "plus": {}}
    for side in SIDES:
        if (FLAT / side / "financing.json").exists():
            fin = json.loads((FLAT / side / "financing.json").read_text())
            cols[side] = {"ce2": {n: r["ce2_newborn"] for n, r in cached_policies(side).items()},
                          "moments": fin["moments"], "parameters": fin["parameters"]}
    order = ["minus", "centre", "plus"]
    target = scf.targets(scf.DEFAULT_TARGET_FILE)
    lines = ["# Policy rankings along the unidentified calibration direction", "",
             "Direction (proportional changes, largest = 1): "
             + ", ".join(f"{k} {v:+.3f}" for k, v in zip(d["names"], d["direction"]))
             + f". Step ±{step:g}. Singular values of the scaled Jacobian: "
             + ", ".join(f"{s:.4f}" for s in d["singular_values"]) + ".", "",
             "Centre: thesis parameters with a fresh benchmark (run_sensitivity.py control). "
             "Each side re-fits theta_max to the financing target and uses its own benchmark.", "",
             "## Parameters", "", "| Parameter | minus | centre | plus |", "|---|---:|---:|---:|"]
    for k in [*scf.NAMES, "theta_max"]:
        lines.append(f"| {k} | " + " | ".join(f"{cols[c]['parameters'][k]:.6f}" if cols[c].get("parameters")
                                              else "—" for c in order) + " |")
    lines += ["", "## Benchmark moments", "", "| Moment | Target | minus | centre | plus |",
              "|---|---:|---:|---:|---:|"]
    for label, key, t in [("Top 1% wealth share", "top1", target[0]),
                          ("Entrepreneurs in top 1%", "ent_top1", target[1]),
                          ("Entrepreneur wealth share", "ent_wealth", target[2]),
                          ("Entrepreneur population", "ent_pop", None),
                          ("Top 0.1% wealth share", "top01", None),
                          ("Debt/output", "debt_output", None)]:
        fmt = (lambda v: f"{v:.4f}") if key == "debt_output" else (lambda v: f"{100 * v:.2f}%")
        lines.append(f"| {label} | " + ("" if t is None else f"{100 * t:.2f}%") + " | "
                     + " | ".join(fmt(cols[c]["moments"][key]) if cols[c].get("moments") else "—"
                                  for c in order) + " |")
    lines += ["", "## Newborn CE2 (%)", "", "| Policy | minus | centre | plus |", "|---|---:|---:|---:|"]
    for n in EVALUATED:
        lines.append(f"| {LABELS[n]} | " + " | ".join(
            f"{cols[c]['ce2'][n]:.3f}" if n in cols[c].get("ce2", {}) else "—" for c in order) + " |")
    checks = {c: checks_for(cols[c].get("ce2", {})) for c in order}
    lines += ["", "## Rankings", ""]
    for c in order:
        k = checks[c]
        lines.append(f"- {c}: " + ("not all policies solved yet" if not k else
                     f"wealth-tax lead {k['wealth_tax_lead_pp']:+.2f} pp "
                     f"({'holds' if k['wealth_tax_beats_subsidy'] else 'FAILS'}); joint beats separate: "
                     f"{'yes' if k['joint_beats_separate'] else 'NO'}; estate-removal gain "
                     f"{k['estate_removal_gain_pp']:+.2f} pp; joint order {' > '.join(k['joint_order'])}"))
    atomic_json(FLAT / "results.json", {"direction": d, "step": step, "columns": cols, "checks": checks})
    (FLAT / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


# ---------------------------------------------------------------------------- main

def check_locks() -> None:
    for lock in (LOCK, *OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                if pid > 0:
                    os.kill(pid, 0)
                    raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass                                  # stale lock from a stopped run


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", type=float, default=0.10,
                    help="largest proportional parameter change on each side (default 0.10)")
    ap.add_argument("--sides", default="minus,plus")
    ap.add_argument("--policies", default=",".join(EVALUATED), help="subset of " + ",".join(EVALUATED))
    ap.add_argument("--threads-bench", type=int, default=4)
    ap.add_argument("--threads-policy", type=int, default=3)
    ap.add_argument("--max-parallel", type=int, default=6,
                    help="policy evaluations at once (each needs about 2-3 GB)")
    ap.add_argument("--dbn-max-iter", type=int, default=2000)
    ap.add_argument("--plan", action="store_true", help="show the direction and parameters; run nothing")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()
    sides = [s.strip() for s in args.sides.split(",") if s.strip()]
    names = [n.strip() for n in args.policies.split(",") if n.strip()]
    if any(s not in SIDES for s in sides) or any(n not in EVALUATED for n in names):
        ap.error(f"--sides must be a subset of {list(SIDES)} and --policies of {list(EVALUATED)}")
    if not 0 < args.step < 0.5:
        ap.error("--step must be between 0 and 0.5")
    os.environ["RECAL_DBN_MAX_ITER"] = str(args.dbn_max_iter)      # rc.solver_env reads it
    if args.summary_only:
        summarise(args.step)
        return 0
    if args.plan:
        d, params, centre = jacobian_direction(), side_parameters(args.step), thesis_parameters()
        print("singular values:", ", ".join(f"{s:.4f}" for s in d["singular_values"]))
        print("direction:", ", ".join(f"{k} {v:+.3f}" for k, v in zip(d["names"], d["direction"])))
        print("first-order moment change along it:", [f"{x:.2e}" for x in d["first_order_moment_change"]])
        for k in scf.NAMES:
            print(f"  {k:12s} minus {params['minus'][k]:.6f}   centre {centre[k]:.6f}   plus {params['plus'][k]:.6f}")
        print(f"theta_max starts at the thesis value {centre['theta_max']:.6f} and is re-fitted on each side")
        print(f"sides {sides}; policies {names}; plan only: no executable was run")
        return 0

    rc.check_builds(["control"])
    check_locks()
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ.update(rc.solver_env())                               # the evaluator inherits GKK_*
    FLAT.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(str(os.getpid()))
    try:
        params, theta0 = side_parameters(args.step), thesis_parameters()["theta_max"]

        def attempt(side):
            try:
                financing(side, params[side], theta0, args.threads_bench)
                return side, None
            except Exception as exc:              # keep the other side going
                return side, str(exc)

        with ThreadPoolExecutor(max_workers=len(sides)) as pool:
            outcome = list(pool.map(attempt, sides))
        for side, err in outcome:
            if err:
                print(f"[{side}] CALIBRATION FAILED: {err}", flush=True)
        ready = [s for s, err in outcome if not err]
        if ready:
            evaluate(ready, names, args.threads_policy, args.max_parallel)
        summarise(args.step)
        return 1 if len(ready) < len(sides) else 0
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())

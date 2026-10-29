#!/usr/bin/env python3
"""C6: constant borrowing limit (GKKOC Table E.10 column ii).

The thesis model lets the collateral limit rise with ability (theta from 1 to 2.952).
GKKOC's check (ii) makes it the same for everyone and re-fits it; their optimal wealth
tax is 3.66% with newborn CE2 11.2 (higher than baseline: the ability-dependent limit
is the conservative choice).

  1. Fit the constant limit so that debt/output equals the thesis financing target
     (1.5629), every other parameter at the thesis calibration.  Regula falsi
     (Illinois) from a parallel first pair, tolerance 0.002, at most 8 solves.  Each
     solved benchmark is checked to have nine equal theta values.
  2. Evaluate against the fitted benchmark, labour tax balancing revenue:
        OWT sweep   tau_w {2.5, 3.062, 3.5, 4, 4.5}%   (tau_k 0, tau_b 40%)
        OKIT sweep  tau_k {-5, -10, -13.618, -20}%     (tau_w 0, tau_b 40%)
        joint       7%/-50%/40% and 7%/-50%/0
     compared with the same policies in the thesis model (fresh benchmark).

Executables: variant_constant_theta (make_constant_theta.py; constant limit plus the
validated bounded interest-rate search).  ~2-3 h fit + 11 evaluations 2 at a time
(~6 h).  Outputs only under experiments/robustness_gkkoc_2022/runs/; summary in
c6_results.md.  Resumable.

    python3 experiments/robustness_gkkoc_2022/partC6.py --check-only
    python3 experiments/robustness_gkkoc_2022/partC6.py
    python3 experiments/robustness_gkkoc_2022/partC6.py --summary-only
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tier1 as t1                                          # noqa: E402
from benchmark_cache import complete_benchmark  # noqa: E402
from tier1 import ROOT, RUNS, rc, read_kv                   # noqa: E402

BASE = HERE / "variant_constant_theta"
BENCH_EXE, EVAL_EXE = BASE / "build" / "bench.a", BASE / "build" / "eval.a"
TOL, MAX_SOLVES, FIRST_PAIR, GROW = 0.002, 8, (2.4, 3.2), 1.5
POLICIES = ([(f"owt_{w:g}", (w, 0.0, 0.40)) for w in (0.025, t1.OWT_RATE, 0.035, 0.04, 0.045)]
            + [(f"okit_{k:g}", (0.0, k, 0.40)) for k in (-0.05, -0.10, -0.13618034, -0.20)]
            + [("joint_7_50_40", (0.07, -0.50, 0.40)), ("joint_7_50_0", (0.07, -0.50, 0.0))])
THESIS_REF = {f"owt_{t1.OWT_RATE:g}": 8.391, f"okit_{-0.13618034:g}": 4.951,
              "joint_7_50_40": 19.766, "joint_7_50_0": 23.440}     # fresh thesis benchmark


def check_build() -> None:
    prov_file = BASE / "provenance.json"
    if not prov_file.exists() or not (BENCH_EXE.exists() and EVAL_EXE.exists()):
        raise SystemExit("constant-limit build missing: run make_constant_theta.py first")
    prov = json.loads(prov_file.read_text())
    if any(rc.sha(ROOT / n) != h for n, h in prov["live_sources_sha256"].items()):
        raise SystemExit("live sources changed since make_constant_theta.py; rebuild")
    for e in (BENCH_EXE, EVAL_EXE):
        if rc.sha(e) != prov["executables_sha256"][e.name]:
            raise SystemExit(f"{e.name} changed since make_constant_theta.py; rebuild")


def thetas(folder: Path) -> list[float]:
    line = next(l for l in (folder / "output.txt").read_text().splitlines() if l.split()[:1] == ["Theta"])
    return [float(v) for v in line.split()[1:10]]


def solve(theta: float, threads: int) -> tuple[dict, Path]:
    """Benchmark with the constant limit theta; cached by parameters."""
    p = {**t1.thesis_params(), "theta_max": theta}
    env_p = rc.param_env(p)
    key = json.dumps({"cache": rc.CACHE, "exe": rc.sha(BENCH_EXE), "params": env_p,
                      "solver": rc.solver_env()}, sort_keys=True)
    folder = RUNS / "c6" / "solves" / hashlib.sha256(key.encode()).hexdigest()[:12]
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
    print(f"[C6] solving {folder.name}: constant theta {theta:.4f}", flush=True)
    start = time.monotonic()
    with (folder / "run.log").open("w") as log:
        code = subprocess.run([str(BENCH_EXE)], cwd=ROOT, env=env, stdout=log,
                              stderr=subprocess.STDOUT).returncode
    output = read_kv(folder / "output.txt") if (folder / "output.txt").exists() else {}
    if code or output.get("Statistics_Schema") != 3 or not complete_benchmark(folder):
        raise RuntimeError(f"[C6] solve failed (exit {code}); see {folder / 'run.log'}")
    th = thetas(folder)
    if max(abs(v - theta) for v in th) > 1e-9:
        raise RuntimeError(f"[C6] borrowing limit is not constant: {th}")
    m = rc.moments(folder)
    t1.atomic_json(done, {"parameters": p, "moments": m, "theta": th,
                          "elapsed_minutes": (time.monotonic() - start) / 60})
    print(f"[C6] theta {theta:.4f}: debt/output {m['debt_output']:.4f} "
          f"({(time.monotonic() - start) / 60:.1f} min)", flush=True)
    return m, folder


def fit(threads: int) -> dict:
    target = rc.financing_target()
    path = []

    def at(theta):
        m, f = solve(theta, threads)
        path.append({"theta": theta, "debt_output": m["debt_output"], "folder": str(f.relative_to(ROOT))})
        return m["debt_output"], f

    with ThreadPoolExecutor(max_workers=2) as pool:
        (d_lo, f_lo), (d_hi, f_hi) = pool.map(at, FIRST_PAIR)
    lo, hi = FIRST_PAIR
    while d_hi < target:                                   # both below: move up
        lo, d_lo, f_lo = hi, d_hi, f_hi
        hi *= GROW
        d_hi, f_hi = at(hi)
        if hi > 20:
            raise RuntimeError("debt/output target not reached by theta 20")
    while d_lo > target:                                   # both above: move down
        hi, d_hi, f_hi = lo, d_lo, f_lo
        lo = max(1.0, lo / GROW)
        d_lo, f_lo = at(lo)
        if lo == 1.0 and d_lo > target:
            raise RuntimeError("debt/output above target even at theta 1")
    best = min([(abs(d_lo - target), lo, d_lo, f_lo), (abs(d_hi - target), hi, d_hi, f_hi)])
    side = 0
    while best[0] > TOL and len(path) < MAX_SOLVES:
        g_lo, g_hi = d_lo - target, d_hi - target
        mid = min(hi - 1e-3, max(lo + 1e-3, (lo * g_hi - hi * g_lo) / (g_hi - g_lo)))
        d_mid, f_mid = at(mid)
        best = min(best, (abs(d_mid - target), mid, d_mid, f_mid))
        if d_mid < target:
            lo, d_lo, f_lo = mid, d_mid, f_mid
            if side == -1:
                d_hi = target + (d_hi - target) / 2
            side = -1
        else:
            hi, d_hi, f_hi = mid, d_mid, f_mid
            if side == 1:
                d_lo = target + (d_lo - target) / 2
            side = 1
    gap, theta, debt, folder = best
    out = {"theta": theta, "debt_output": debt, "target": target, "gap": debt - target,
           "within_tolerance": gap <= TOL, "parameters": {**t1.thesis_params(), "theta_max": theta},
           "benchmark": str(folder.relative_to(ROOT)), "path": path}
    t1.atomic_json(RUNS / "c6_theta.json", out)
    print(f"[C6] fit done: constant theta {theta:.4f}, debt/output {debt:.4f} (target {target:.4f})", flush=True)
    if gap > TOL:
        raise SystemExit(f"debt/output gap {gap:.4f} exceeds tolerance after {len(path)} solves")
    return out


def misallocation(folder: Path) -> float:
    o, s = read_kv(folder / "output.txt"), read_kv(folder / "TFP_Star.txt")
    return 1 - (o["TFP_Q"] / s["TFP_Star"]) ** 0.4


def summarise() -> None:
    load = lambda n: json.loads((RUNS / n).read_text()) if (RUNS / n).exists() else {}  # noqa: E731
    fit_, pol = load("c6_theta.json"), load("c6_policies.json")
    lines = ["# C6: constant borrowing limit (GKKOC Table E.10 ii)", ""]
    if fit_:
        b, f = ROOT / fit_["benchmark"], t1.FRESH_BENCH
        bo, fo = read_kv(b / "output.txt"), read_kv(f / "output.txt")
        lines += [f"Constant limit fitted to debt/output {fit_['debt_output']:.4f} (target {fit_['target']:.4f}): "
                  f"θ = {fit_['theta']:.4f} for every ability (thesis: rising from 1 to 2.952).  Fit path: "
                  + ", ".join(f"{q['theta']:.3f}→{q['debt_output']:.3f}" for q in fit_["path"]) + ".", "",
                  "| Benchmark | Debt/output | Top 1% | Top 0.1% | Misallocation | Interest rate |",
                  "|---|---:|---:|---:|---:|---:|",
                  f"| thesis (rising limit) | {fo['Debt_Output']:.3f} | {100*fo['Wealth_Top_1%']:.2f}% | "
                  f"{100*fo['Wealth_Top_0.1%']:.2f}% | {misallocation(f):.3f} | {fo['R']:.2f}% |",
                  f"| constant limit | {bo['Debt_Output']:.3f} | {100*bo['Wealth_Top_1%']:.2f}% | "
                  f"{100*bo['Wealth_Top_0.1%']:.2f}% | {misallocation(b):.3f} | {bo['R']:.2f}% |", ""]
    lines += ["| Policy | τ_w | τ_k | τ_b | Newborn CE2 | Population CE2 | Labour tax | Output | Thesis model CE2 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, rates in POLICIES:
        r, ref = pol.get(name), THESIS_REF.get(name)
        refc = f"{ref:.2f}" if ref else "—"
        if not r or r.get("status") != "ok":
            lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.1f}% | {100*rates[2]:.0f}% | "
                         f"{'FAILED' if r else 'pending'} | | | | {refc} |")
            continue
        lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.1f}% | {100*rates[2]:.0f}% | "
                     f"{r['ce2_newborn']:.2f} | {r['ce2_population']:.2f} | {100*r['tau_l']:.2f}% | "
                     f"{r['output_growth']:+.2f}% | {refc} |")
    ok = {n: r for n, r in pol.items() if r.get("status") == "ok"}
    owt = [r for n, r in ok.items() if n.startswith("owt_")]
    okit = [r for n, r in ok.items() if n.startswith("okit_")]
    if owt and okit:
        bw, bk = max(owt, key=lambda r: r["ce2_newborn"]), max(okit, key=lambda r: r["ce2_newborn"])
        lines += ["", f"Best wealth tax {100*bw['tau_w']:.2f}% (CE2 {bw['ce2_newborn']:.2f}); best capital-income "
                  f"tax {100*bk['tau_k']:+.1f}% (CE2 {bk['ce2_newborn']:.2f}); wealth-tax advantage "
                  f"{bw['ce2_newborn'] - bk['ce2_newborn']:.2f} pp (thesis 3.44).  GKKOC (ii): optimal wealth "
                  "tax 3.66%, CE2 11.2."]
        for side, best, edge in (("wealth", bw, (min, max)), ("capital-income", bk, (min, max))):
            key = "tau_w" if side == "wealth" else "tau_k"
            vals = [r[key] for r in (owt if side == "wealth" else okit)]
            if best[key] in (min(vals), max(vals)):
                lines.append(f"The best {side} tax is at the edge of the tested range ({100*best[key]:+.2f}%).")
    (HERE / "c6_results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--dbn-max-iter", type=int, default=2000)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise()
        return 0
    check_build()
    if args.check_only:
        print(f"fit: constant theta, first pair {FIRST_PAIR}, target debt/output "
              f"{rc.financing_target():.4f}, thesis parameters {t1.thesis_params()}")
        print("policies:")
        for name, rates in POLICIES:
            print(f"  {name:16s} {rates}")
        print(f"Executables: {BENCH_EXE.relative_to(ROOT)}, eval.a.  Check only: nothing was run.")
        return 0
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["RECAL_DBN_MAX_ITER"] = str(args.dbn_max_iter)
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)
    RUNS.mkdir(parents=True, exist_ok=True)
    for lock in (t1.LOCK, *t1.OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                os.kill(pid, 0)
                raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass
    t1.LOCK.write_text(str(os.getpid()))
    try:
        f = fit(args.threads)
        ev = t1.evaluator(ROOT / f["benchmark"], RUNS / "c6_policies", args.threads,
                          env=rc.param_env(f["parameters"]), exe=EVAL_EXE)
        t1.run_jobs([(n, ev, r) for n, r in POLICIES], args.max_parallel, "c6_policies.json")
        summarise()
    finally:
        t1.LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

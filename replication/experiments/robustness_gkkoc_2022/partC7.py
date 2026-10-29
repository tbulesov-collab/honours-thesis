#!/usr/bin/env python3
"""C7: higher markups, mu = 0.8 instead of 0.9 (GKKOC Table E.10 column iii).

GKKOC re-calibrate with mu = 0.8 (the model matches the targets nearly as well) and
find an optimal wealth tax of 2.45% with newborn CE2 7.6.  Here the thesis's own
calibration procedure is repeated with the mu = 0.8 build (make_mu08.py):

  1. SCF step: experiments/model_spec_sensitivity_2022/recalibrate.py scf_step,
     unchanged (one ridge step from the published vector, half-step fallback,
     repaired percentile statistics).
  2. Borrowing limit: theta_max fitted so debt/output equals the 2022 target (1.5629).
     recalibrate.py's financing_step only searches upwards from 2.8 and stops at 6;
     with mu = 0.8 firms want less capital, so this script brackets in both
     directions (x1.5 expansion, Illinois regula falsi, tolerance 0.001 as in the
     thesis step, at most 8 solves).
  3. Policies, labour tax balancing revenue:
        OWT sweep   tau_w {1.5, 2, 2.5, 3.062, 3.5}%   (tau_k 0, tau_b 40%)
        OKIT sweep  tau_k {-5, -10, -13.618, -20}%     (tau_w 0, tau_b 40%)
        joint       7%/-50%/40% and 7%/-50%/0

The comparison that isolates mu is the re-calibrated mu = 0.9 control arm, which ran
exactly the same procedure (recal_results.json and the re-optimisation grids); thesis
values are shown as well.  ~2.5-3 h SCF step + ~1-2 h theta + ~6 h policies.  Outputs
only under experiments/robustness_gkkoc_2022/runs/c7*; summary in c7_results.md.
Resumable (cached solves and evaluations).

    python3 experiments/robustness_gkkoc_2022/partC7.py --check-only
    python3 experiments/robustness_gkkoc_2022/partC7.py
    python3 experiments/robustness_gkkoc_2022/partC7.py --summary-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tier1 as t1                                          # noqa: E402
from tier1 import ROOT, RUNS, rc, read_kv                   # noqa: E402

ARM = "mu08"
BASE = HERE / "variants" / ARM
BENCH_EXE, EVAL_EXE = BASE / "build" / "bench.a", BASE / "build" / "eval.a"
C7 = RUNS / "c7"
TOL, MAX_SOLVES, FIRST_PAIR, GROW = 0.001, 8, (2.8, 3.1), 1.5
POLICIES = ([(f"owt_{w:g}", (w, 0.0, 0.40)) for w in (0.015, 0.02, 0.025, t1.OWT_RATE, 0.035)]
            + [(f"okit_{k:g}", (0.0, k, 0.40)) for k in (-0.05, -0.10, -0.13618034, -0.20,
                                                           -0.25, -0.30)]   # -25/-30 added 2026-10-05:
            # OKIT welfare was still rising at -20% (slopes 0.082, 0.062, 0.042 per pp)
            + [("joint_7_50_40", (0.07, -0.50, 0.40)), ("joint_7_50_0", (0.07, -0.50, 0.0))])
THESIS_REF = {f"owt_{t1.OWT_RATE:g}": 8.391, f"okit_{-0.13618034:g}": 4.951,
              "joint_7_50_40": 19.766, "joint_7_50_0": 23.440}     # fresh thesis benchmark
SENS = ROOT / "experiments" / "model_spec_sensitivity_2022"
REOPT = ROOT / "experiments" / "policy_reoptimization_2022" / "runs"


def use_c7_paths() -> None:
    """Point recalibrate.py's solver at the mu = 0.8 build and the c7 output folder."""
    rc.HERE = HERE                    # exe = HERE / variants / mu08 / build / bench.a
    rc.RECAL = C7                     # outputs under runs/c7/mu08/


def check_build() -> None:
    prov_file = BASE / "provenance.json"
    if not prov_file.exists() or not (BENCH_EXE.exists() and EVAL_EXE.exists()):
        raise SystemExit("mu = 0.8 build missing: run make_mu08.py first")
    prov = json.loads(prov_file.read_text())
    if any(rc.sha(ROOT / n) != h for n, h in prov["live_sources_sha256"].items()):
        raise SystemExit("live sources changed since make_mu08.py; rebuild")
    for e in (BENCH_EXE, EVAL_EXE):
        if rc.sha(e) != prov["executables_sha256"][e.name]:
            raise SystemExit(f"{e.name} changed since make_mu08.py; rebuild")


def fit_theta(scf_params: dict, threads: int) -> dict:
    target = rc.financing_target()
    path = []

    def at(theta):
        m, f = rc.solve(ARM, {**scf_params, "theta_max": theta}, threads)
        path.append({"theta_max": theta, "debt_output": m["debt_output"]})
        print(f"[C7] theta_max {theta:.4f}: debt/output {m['debt_output']:.4f}", flush=True)
        return m["debt_output"], f

    with ThreadPoolExecutor(max_workers=2) as pool:       # 2.8 is normally the cached SCF solve
        (d_lo, f_lo), (d_hi, f_hi) = pool.map(at, FIRST_PAIR)
    lo, hi = FIRST_PAIR
    while d_hi < target:
        if hi > 40:
            raise SystemExit("debt/output target not reached by theta_max 40")
        lo, d_lo, f_lo = hi, d_hi, f_hi
        hi *= GROW
        d_hi, f_hi = at(hi)
    while d_lo > target:
        if lo <= 1.0:
            raise SystemExit("debt/output above target even at theta_max 1")
        hi, d_hi, f_hi = lo, d_lo, f_lo
        lo = max(1.0, lo / GROW)
        d_lo, f_lo = at(lo)
    best = min([(abs(d_lo - target), lo, d_lo, f_lo), (abs(d_hi - target), hi, d_hi, f_hi)])
    side = 0
    while best[0] > TOL and len(path) < MAX_SOLVES:
        g_lo, g_hi = d_lo - target, d_hi - target
        mid = min(hi - 1e-4, max(lo + 1e-4, (lo * g_hi - hi * g_lo) / (g_hi - g_lo)))
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
    out = {"theta_max": theta, "debt_output": debt, "target": target, "gap": debt - target,
           "within_tolerance": gap <= TOL, "parameters": {**scf_params, "theta_max": theta},
           "moments": rc.moments(folder), "benchmark": str(folder.relative_to(ROOT)), "path": path}
    t1.atomic_json(C7 / ARM / "financing.json", out)
    print(f"[C7] theta fit done: theta_max {theta:.4f}, debt/output {debt:.4f} (target {target:.4f})", flush=True)
    if gap > TOL:
        raise SystemExit(f"debt/output gap {gap:.4f} exceeds tolerance after {len(path)} solves")
    return out


# --------------------------------------------------------------------------- summary

def misallocation(folder: Path) -> float:
    o, s = read_kv(folder / "output.txt"), read_kv(folder / "TFP_Star.txt")
    return 1 - (o["TFP_Q"] / s["TFP_Star"]) ** 0.4


def recal_ref(rates) -> float | None:
    """Same policy in the re-calibrated mu = 0.9 control arm (same procedure)."""
    rr = json.loads((SENS / "recal_results.json").read_text())["arms"]["control"]["policies"]
    pts = [p for p in rr.values() if p.get("status") == "ok"]
    gp = REOPT / "grid_points.json"
    if gp.exists():
        pts += [p for p in json.loads(gp.read_text()) if p["calibration"] == "recal" and p["status"] == "ok"]
    for p in pts:
        r = p.get("rates") or [p["tau_w"], p["tau_k"], p["tau_bq"]]
        if all(abs(a - b) < 1e-9 for a, b in zip(r, rates)):
            return p["ce2_newborn"]
    return None


def summarise() -> None:
    load = lambda f: json.loads(f.read_text()) if f.exists() else {}  # noqa: E731
    scf_ = load(C7 / ARM / "scf.json")
    fin = load(C7 / ARM / "financing.json")
    pol = load(RUNS / "c7_policies.json")
    rec = load(SENS / "recal" / "control" / "financing.json")
    rscf = load(SENS / "recal" / "control" / "scf.json")
    lines = ["# C7: higher markups, mu = 0.8 (GKKOC Table E.10 iii)", "",
             "Both columns repeat the thesis calibration procedure (one-step SCF fit from the published "
             "vector, repaired statistics; theta_max fitted to debt/output 1.5629).", ""]
    if fin and rec:
        lines += ["| | μ = 0.9 (re-calibrated control) | μ = 0.8 |", "|---|---:|---:|"]
        for k in ("sigma_z_eps", "x_hi", "p1_x", "p2_x", "theta_max"):
            lines.append(f"| {k} | {rec['parameters'][k]:.4f} | {fin['parameters'][k]:.4f} |")
        for label, key in (("Top 1%", "top1"), ("Entrepreneurs in top 1%", "ent_top1"),
                           ("Entrepreneur wealth share", "ent_wealth"), ("Top 0.1%", "top01")):
            lines.append(f"| {label} | {100*rec['moments'][key]:.2f}% | {100*fin['moments'][key]:.2f}% |")
        lines.append(f"| SCF-step objective | {rscf.get('objective', float('nan')):.1f} | "
                     f"{scf_.get('objective', float('nan')):.1f} |")
        lines.append(f"| Misallocation | {misallocation(ROOT / rec['benchmark']):.3f} | "
                     f"{misallocation(ROOT / fin['benchmark']):.3f} |")
        lines.append("")
    lines += ["| Policy | τ_w | τ_k | τ_b | μ = 0.8 CE2 | Labour tax | Output | μ = 0.9 re-cal CE2 | Thesis CE2 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, rates in POLICIES:
        r, ref, th = pol.get(name), recal_ref(rates), THESIS_REF.get(name)
        refc = f"{ref:.2f}" if ref is not None else "—"
        thc = f"{th:.2f}" if th else "—"
        if not r or r.get("status") != "ok":
            lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.1f}% | {100*rates[2]:.0f}% | "
                         f"{'FAILED' if r else 'pending'} | | | {refc} | {thc} |")
            continue
        lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.1f}% | {100*rates[2]:.0f}% | "
                     f"{r['ce2_newborn']:.2f} | {100*r['tau_l']:.2f}% | {r['output_growth']:+.2f}% | "
                     f"{refc} | {thc} |")
    ok = {n: r for n, r in pol.items() if r.get("status") == "ok"}
    owt = [r for n, r in ok.items() if n.startswith("owt_")]
    okit = [r for n, r in ok.items() if n.startswith("okit_")]
    if owt and okit:
        bw, bk = max(owt, key=lambda r: r["ce2_newborn"]), max(okit, key=lambda r: r["ce2_newborn"])
        lines += ["", f"μ = 0.8: best wealth tax {100*bw['tau_w']:.2f}% (CE2 {bw['ce2_newborn']:.2f}); best "
                  f"capital-income tax {100*bk['tau_k']:+.1f}% (CE2 {bk['ce2_newborn']:.2f}); wealth-tax "
                  f"advantage {bw['ce2_newborn'] - bk['ce2_newborn']:.2f} pp (μ = 0.9 re-calibrated: 3.00; "
                  "thesis 3.44).  GKKOC (iii): optimal wealth tax 2.45%, CE2 7.6."]
        for label, best, vals, key in (("wealth", bw, owt, "tau_w"), ("capital-income", bk, okit, "tau_k")):
            v = [r[key] for r in vals]
            if best[key] in (min(v), max(v)):
                lines.append(f"The best {label} tax is at the edge of the tested range ({100*best[key]:+.2f}%).")
    (HERE / "c7_results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--jac-parallel", type=int, default=2)
    parser.add_argument("--dbn-max-iter", type=int, default=2000)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise()
        return 0
    check_build()
    use_c7_paths()
    if args.check_only:
        print(f"SCF step: published vector {dict(zip(rc.scf.NAMES, rc.scf.BASELINE))}, theta_max 2.8, "
              f"targets {rc.scf.targets(rc.scf.DEFAULT_TARGET_FILE).round(4).tolist()}")
        print(f"theta fit: target debt/output {rc.financing_target():.4f}, first pair {FIRST_PAIR}")
        print(f"bench.a resolves to {(rc.HERE / 'variants' / ARM / 'build' / 'bench.a').relative_to(ROOT)}; "
              f"outputs to {(rc.RECAL / ARM).relative_to(ROOT)}")
        print("policies:")
        for name, rates in POLICIES:
            print(f"  {name:16s} {rates}")
        print("Check only: nothing was run.")
        return 0
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["RECAL_DBN_MAX_ITER"] = str(args.dbn_max_iter)
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)
    C7.mkdir(parents=True, exist_ok=True)
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
        s = rc.scf_step(ARM, args.threads, args.jac_parallel, 1)
        f = fit_theta(s["parameters"], args.threads)
        ev = t1.evaluator(ROOT / f["benchmark"], RUNS / "c7_policies", args.threads,
                          env=rc.param_env(f["parameters"]), exe=EVAL_EXE)
        t1.run_jobs([(n, ev, r) for n, r in POLICIES], args.max_parallel, "c7_policies.json")
        summarise()
    finally:
        t1.LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

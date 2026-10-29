#!/usr/bin/env python3
"""Part C5: the pure-rents model (GKKOC Table XII column 5).

GKKOC remove differences in entrepreneurial ability.  Every firm still earns monopoly
rents, but returns no longer differ by ability, so the wealth tax loses its
reallocation advantage: their optimal wealth tax is 1.40% and *lowers* welfare
(CE2 -1.4, CE1 -1.7) relative to the US benchmark with its 25% capital-income tax.

Here the same experiment uses the thesis model with no code change: the ability spread
GKK_SIGMA_Z_EPS is set to 0.001 (Tauchen grid, so every ability node is
1.000 +/- 0.3%), with every other parameter at the thesis calibration (GKKOC likewise
do not re-fit; their debt/GDP falls to 1.1).  Executables: the unchanged control build
(variants/control/build/{bench,eval}.a, checked against provenance.json).

  1. Solve the pure-rents benchmark.  The run stops if misallocation,
     1 - (TFP/TFP*)^0.4, is not close to zero (< 0.01): ability differences must be
     gone.
  2. Evaluate against it, labour tax balancing revenue:
        OWT sweep    tau_w {0.5, 1, 1.5, 2, 3.062}%   (tau_k 0, tau_b 40%)
        capital tax  tau_k {0, 35}%                   (tau_w 0, tau_b 40%; the
                                                       benchmark is 25%)
        joint        7%/-50%/40% and 7%/-50%/0
     Each is compared with the same policy in the thesis model.

Convergence: at sigma 0.001 the benchmark did not converge (the equilibrium loop
alternated between two states, R = -0.032 and 0.053, for 2000 iterations: with almost
identical firms, capital demand switches abruptly with R).  The spread is therefore a
setting: --probe solves benchmarks for several small spreads in parallel and reports
convergence and remaining misallocation; the policies are then run with --sigma at the
smallest spread that converges (misallocation must stay below --max-misalloc).

    python3 experiments/robustness_gkkoc_2022/partC.py --probe 0.01 0.02 0.04
    python3 experiments/robustness_gkkoc_2022/partC.py --sigma 0.01

Update: the probe at 0.01/0.02/0.04 showed the same alternation for every spread, so the
cause is the interest-rate step, not the spread.  --build rb uses the bounded search
(make_purerents.py: benchmark and evaluator copies, only programfunctions.f90 differs).
With --build rb the probe also re-solves the thesis benchmark and requires it to match
the fresh thesis benchmark (consistency check).

    python3 experiments/robustness_gkkoc_2022/partC.py --build rb --probe 0.001 0.01
    python3 experiments/robustness_gkkoc_2022/partC.py --build rb --sigma 0.001

~1 benchmark solve + 9 evaluations, 2 at a time: ~5 h.  Outputs only under
experiments/robustness_gkkoc_2022/runs/; summary in partC_results.md.  Resumable.

    python3 experiments/robustness_gkkoc_2022/partC.py --check-only
    python3 experiments/robustness_gkkoc_2022/partC.py
    python3 experiments/robustness_gkkoc_2022/partC.py --summary-only
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tier1 as t1                                          # noqa: E402
from benchmark_cache import complete_benchmark  # noqa: E402
from tier1 import ROOT, RUNS, rc, read_kv                   # noqa: E402

RB_DIR = HERE / "variant_purerents"
EXES = {"control": (rc.HERE / "variants" / "control" / "build" / "bench.a",
                    rc.HERE / "variants" / "control" / "build" / "eval.a"),
        "rb": (RB_DIR / "build" / "bench.a", RB_DIR / "build" / "eval.a")}
CHECK_KEYS, CHECK_REL = ("KBAR", "YBAR", "Debt_Output", "Wealth_Top_1%"), 1e-4
SIGMA = 0.01             # default spread; see --probe
MISALLOC_MAX = 0.02      # thesis model 0.151, GKKOC pure rents 0.004
# TFP* is the maximum of Q/K given the same capital (GKK_Stats.f90 ~3001).  TFP above it
# (negative misallocation) means firms use more capital than households own, i.e. the
# capital market does not clear; such a benchmark is not a valid equilibrium.  The
# sigma 0.001 bounded-search benchmark gave TFP/TFP* = 1.055 (2026-10-04).
MISALLOC_MIN = -0.001
POLICIES = ([(f"owt_{w:g}", (w, 0.0, 0.40)) for w in (0.005, 0.01, 0.015, 0.02, t1.OWT_RATE)]
            + [("tauk_0", (0.0, 0.0, 0.40)), ("tauk_35", (0.0, 0.35, 0.40)),
               ("joint_7_50_40", (0.07, -0.50, 0.40)), ("joint_7_50_0", (0.07, -0.50, 0.0))])
# Same policies in the thesis model (fresh thesis benchmark), where already evaluated.
THESIS_REF = {f"owt_{t1.OWT_RATE:g}": ("model_spec_sensitivity_2022 control", 8.391),
              "joint_7_50_40": ("model_spec_sensitivity_2022 control", 19.766),
              "joint_7_50_0": ("robustness baseline", 23.440)}


def tag(sigma: float, build: str = "control") -> str:
    return f"s{sigma:g}" + ("" if build == "control" else f"_{build}")


def check_rb_build() -> None:
    prov_file = RB_DIR / "provenance.json"
    if not prov_file.exists() or not all(e.exists() for e in EXES["rb"]):
        raise SystemExit("bounded build missing: run make_purerents.py first")
    prov = json.loads(prov_file.read_text())
    if any(rc.sha(ROOT / n) != h for n, h in prov["live_sources_sha256"].items()):
        raise SystemExit("live sources changed since make_purerents.py; rebuild")
    for e in EXES["rb"]:
        if rc.sha(e) != prov["executables_sha256"][e.name]:
            raise SystemExit(f"{e.name} changed since make_purerents.py; rebuild")


def solve_rb(p: dict, threads: int) -> tuple[dict, Path]:
    """rc.solve with the bounded-search benchmark executable; cached by parameters."""
    exe = EXES["rb"][0]
    env_p = rc.param_env(p)
    key = json.dumps({"cache": rc.CACHE, "exe": rc.sha(exe), "params": env_p,
                      "solver": rc.solver_env()}, sort_keys=True)
    folder = RUNS / "purerents_rb" / "solves" / hashlib.sha256(key.encode()).hexdigest()[:12]
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
    print(f"[rb] solving {folder.name}: sigma_z_eps={p['sigma_z_eps']:g}", flush=True)
    start = time.monotonic()
    with (folder / "run.log").open("w") as log:
        code = subprocess.run([str(exe)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    output = read_kv(folder / "output.txt") if (folder / "output.txt").exists() else {}
    if code or output.get("Statistics_Schema") != 3 or not complete_benchmark(folder):
        raise RuntimeError(f"[rb] solve failed (exit {code}); see {folder / 'run.log'}")
    m = rc.moments(folder)
    t1.atomic_json(done, {"parameters": p, "moments": m, "elapsed_minutes": (time.monotonic() - start) / 60,
                          "environment": {k: env[k] for k in sorted(env) if k.startswith(("GKK_", "OMP_"))}})
    print(f"[rb] solved {folder.name} in {(time.monotonic() - start) / 60:.1f} min", flush=True)
    return m, folder


def rb_consistency(threads: int) -> dict:
    """The bounded benchmark solver must reproduce the fresh thesis benchmark."""
    p = {**t1.thesis_params(), "theta_max": float(json.loads(t1.FIN_BEST.read_text())["theta_max"])}
    _, folder = solve_rb(p, threads)
    new, ref = read_kv(folder / "output.txt"), read_kv(t1.FRESH_BENCH / "output.txt")
    diffs = {k: abs(new[k] / ref[k] - 1) for k in CHECK_KEYS}
    out = {"folder": str(folder.relative_to(ROOT)), "relative_differences": diffs,
           "passed": max(diffs.values()) <= CHECK_REL}
    t1.atomic_json(RUNS / "purerents_rb_consistency.json", out)
    print(f"[rb] consistency vs thesis benchmark: max relative difference "
          f"{max(diffs.values()):.2e} → {'passed' if out['passed'] else 'NOT passed'}", flush=True)
    return out


def params(sigma: float = SIGMA) -> dict[str, float]:
    return {**t1.thesis_params(), "sigma_z_eps": sigma,
            "theta_max": float(json.loads(t1.FIN_BEST.read_text())["theta_max"])}


def misallocation(folder: Path) -> float:
    o, s = read_kv(folder / "output.txt"), read_kv(folder / "TFP_Star.txt")
    return 1 - (o["TFP_Q"] / s["TFP_Star"]) ** 0.4


def solve_benchmark(threads: int, sigma: float = SIGMA, max_mis: float = MISALLOC_MAX,
                    build: str = "control") -> dict:
    rc.RECAL = RUNS / "purerents"                  # control solves go to runs/purerents/control/solves
    p = params(sigma)
    m, folder = rc.solve("control", p, threads) if build == "control" else solve_rb(p, threads)
    z = [float(v) for v in (folder / "zgrid").read_text().split()]
    mis = misallocation(folder)
    out = {"sigma": sigma, "build": build, "parameters": p, "benchmark": str(folder.relative_to(ROOT)),
           "moments": m, "misallocation": mis, "zgrid_min": min(z), "zgrid_max": max(z)}
    t1.atomic_json(RUNS / f"purerents_benchmark_{tag(sigma, build)}.json", out)
    print(f"[pure rents σ={sigma:g}] benchmark {folder.name}: misallocation {mis:.4f}, z in "
          f"[{min(z):.4f}, {max(z):.4f}], debt/output {m['debt_output']:.3f}", flush=True)
    if mis >= max_mis:
        raise SystemExit(f"misallocation {mis:.4f} is not ~0: ability differences were not removed")
    if mis < MISALLOC_MIN:
        raise SystemExit(f"TFP exceeds the efficient level (misallocation {mis:.4f}): capital demand "
                         "exceeds supply, so this benchmark is not a valid equilibrium")
    return out


def probe(sigmas: list[float], threads: int, build: str = "control") -> None:
    from concurrent.futures import ThreadPoolExecutor

    def one(sigma):
        if sigma == "check":
            try:
                return {"sigma": "check", **rb_consistency(threads)}
            except Exception as exc:
                return {"sigma": "check", "passed": False, "error": str(exc)[:200]}
        try:
            b = solve_benchmark(threads, sigma, max_mis=1.0, build=build)
        except (Exception, SystemExit) as exc:   # non-convergence or invalid equilibrium:
            return {"sigma": sigma, "converged": False, "error": str(exc)[:200]}   # report, do not use
        return {"sigma": sigma, "converged": True, "misallocation": b["misallocation"],
                "zgrid": [b["zgrid_min"], b["zgrid_max"]], "debt_output": b["moments"]["debt_output"]}

    jobs = list(sigmas) + (["check"] if build == "rb" else [])
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        res = list(pool.map(one, jobs))
    check = [r for r in res if r["sigma"] == "check"]
    res = [r for r in res if r["sigma"] != "check"]
    t1.atomic_json(RUNS / f"purerents_probe_{build}.json", {"spreads": res, "consistency": check})
    if check:
        c = check[0]
        print("\nConsistency (bounded solver re-solves the thesis benchmark): "
              + (f"max relative difference {max(c['relative_differences'].values()):.2e} → "
                 f"{'passed' if c['passed'] else 'NOT passed'}" if "relative_differences" in c
                 else f"FAILED ({c.get('error', '')[:80]})"))
    print("\nσ_z     converged  misallocation  z range            debt/output")
    for r in res:
        if r["converged"]:
            print(f"{r['sigma']:<7g} yes        {r['misallocation']:.4f}         "
                  f"[{r['zgrid'][0]:.3f}, {r['zgrid'][1]:.3f}]   {r['debt_output']:.3f}")
        else:
            print(f"{r['sigma']:<7g} NO         ({r['error'][:60]})")
    ok = [r for r in res if r["converged"] and MISALLOC_MIN <= r["misallocation"] < MISALLOC_MAX]
    for r in res:
        if r["converged"] and r["misallocation"] < MISALLOC_MIN:
            print(f"σ_z {r['sigma']:g}: TFP above the efficient level, capital market does not clear: "
                  "not a valid equilibrium")
    if ok:
        best = min(ok, key=lambda r: r["sigma"])
        if check and not check[0].get("passed"):
            print("\nThe bounded solver did not reproduce the thesis benchmark: do not use these results.")
            return
        nxt = f"partC.py{'' if build == 'control' else ' --build ' + build} --sigma {best['sigma']:g}"
        print(f"\nSmallest usable spread: σ_z = {best['sigma']:g} "
              f"(misallocation {best['misallocation']:.4f}; thesis 0.151, GKKOC 0.004).  Next: {nxt}")
    else:
        print(f"\nNo spread converged with misallocation < {MISALLOC_MAX}.")


def summarise(sigma: float = SIGMA, build: str = "control") -> None:
    load = lambda n: json.loads((RUNS / n).read_text()) if (RUNS / n).exists() else {}  # noqa: E731
    bench = load(f"purerents_benchmark_{tag(sigma, build)}.json")
    pol = load(f"purerents_policies_{tag(sigma, build)}.json")
    lines = ["# Part C5: pure-rents model (no differences in entrepreneurial ability)", ""]
    if bench:
        b, f = bench["moments"], read_kv(t1.FRESH_BENCH / "output.txt")
        lines += [f"Ability spread σ_z = {sigma:g} (z in [{bench['zgrid_min']:.4f}, {bench['zgrid_max']:.4f}]); "
                  "every other parameter at the thesis calibration; executables: "
                  + ("unchanged control build." if build == "control" else
                     "bounded interest-rate search (make_purerents.py), checked against the thesis "
                     "benchmark.") + "", "",
                  "| Benchmark | Debt/output | Top 1% | Top 0.1% | Entrepreneurs | Ent. wealth share | "
                  "Misallocation |", "|---|---:|---:|---:|---:|---:|---:|",
                  f"| thesis model | {f['Debt_Output']:.3f} | {100*f['Wealth_Top_1%']:.2f}% | "
                  f"{100*f['Wealth_Top_0.1%']:.2f}% | | | {misallocation(t1.FRESH_BENCH):.3f} |",
                  f"| pure rents | {b['debt_output']:.3f} | {100*b['top1']:.2f}% | {100*b['top01']:.2f}% | "
                  f"{100*b['ent_pop']:.2f}% | {100*b['ent_wealth']:.2f}% | {bench['misallocation']:.4f} |", "",
                  "GKKOC pure rents: debt/GDP 1.1, misallocation 0.004.", ""]
    lines += ["| Policy | τ_w | τ_k | τ_b | Newborn CE2 | CE1 | Population CE2 | Labour tax | Output | "
              "Thesis model CE2 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, rates in POLICIES:
        r = pol.get(name)
        ref = THESIS_REF.get(name)
        refc = f"{ref[1]:.2f}" if ref else "—"
        if not r or r.get("status") != "ok":
            lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.0f}% | {100*rates[2]:.0f}% | "
                         f"{'FAILED' if r else 'pending'} | | | | | {refc} |")
            continue
        lines.append(f"| {name} | {100*rates[0]:.2f}% | {100*rates[1]:+.0f}% | {100*rates[2]:.0f}% | "
                     f"{r['ce2_newborn']:.2f} | {r['ce1_newborn']:.2f} | {r['ce2_population']:.2f} | "
                     f"{100*r['tau_l']:.2f}% | {r['output_growth']:+.2f}% | {refc} |")
    owt = [r for n, r in pol.items() if n.startswith("owt_") and r.get("status") == "ok"]
    if owt:
        bw = max(owt, key=lambda r: r["ce2_newborn"])
        lines += ["", f"Best wealth tax in the pure-rents model: {100*bw['tau_w']:.2f}% with newborn CE2 "
                  f"{bw['ce2_newborn']:.2f} (thesis model: 3.06%, 8.39).  GKKOC pure rents: 1.40%, CE2 −1.4."]
    lines += ["", "All welfare changes are relative to the model's own benchmark with the US tax system "
              "(capital-income tax 25%, estate tax 40%)."]
    (HERE / f"partC_results_{tag(sigma, build)}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sigma", type=float, default=SIGMA, help="ability spread GKK_SIGMA_Z_EPS")
    parser.add_argument("--build", choices=sorted(EXES), default="control",
                        help="rb = bounded interest-rate search (make_purerents.py)")
    parser.add_argument("--probe", type=float, nargs="+",
                        help="solve only the benchmarks for these spreads (in parallel) and report")
    parser.add_argument("--max-misalloc", type=float, default=MISALLOC_MAX)
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--dbn-max-iter", type=int, default=2000)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise(args.sigma, args.build)
        return 0
    rc.check_builds(["control"])
    if args.build == "rb":
        check_rb_build()
    if args.check_only:
        if args.probe:
            print(f"probe: benchmarks only for σ_z in {args.probe}, in parallel")
        print(f"benchmark parameters: {params(args.sigma)}")
        print("policies:")
        for name, rates in POLICIES:
            print(f"  {name:14s} {rates}")
        print(f"Executables: {EXES[args.build][0].relative_to(ROOT)}, {EXES[args.build][1].name}"
              + ("  (+ consistency re-solve of the thesis benchmark)" if args.build == "rb" and args.probe else "")
              + ".  Check only: nothing was run.")
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
        if args.probe:
            probe(args.probe, args.threads, args.build)
            return 0
        if args.build == "rb":
            c = RUNS / "purerents_rb_consistency.json"
            if not c.exists() or not json.loads(c.read_text())["passed"]:
                raise SystemExit("run the rb probe first: its consistency check must pass")
        bench = solve_benchmark(args.threads, args.sigma, args.max_misalloc, args.build)
        ev = t1.evaluator(ROOT / bench["benchmark"], RUNS / f"purerents_{tag(args.sigma, args.build)}_policies",
                          args.threads, env=rc.param_env(bench["parameters"]), exe=EXES[args.build][1])
        t1.run_jobs([(n, ev, r) for n, r in POLICIES], args.max_parallel,
                    f"purerents_policies_{tag(args.sigma, args.build)}.json")
        summarise(args.sigma, args.build)
    finally:
        t1.LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

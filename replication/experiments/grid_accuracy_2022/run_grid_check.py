#!/usr/bin/env python3
"""Asset-grid accuracy check for the thesis (Appendix A.3).

Solve the benchmark and four headline policies on a finer asset grid and compare newborn
CE2 with the standard-grid (na=201) results of the control variant of
model_spec_sensitivity_2022, i.e. the freshly solved values reported in thesis Section 7.3.
The procedure is that of run_sensitivity.py for its control: financing calibration,
benchmark solved from scratch, the validated PolicyEvaluator, labour tax adjusting to the
spending requirement.  Only the grid differs (see make_grid_variant.py).

    policy      (tau_w, tau_k, tau_bq)        standard grid (control)
    owt         (0.030618034, 0, 0.40)        8.3912
    okit        (0, -0.13618034, 0.40)        4.9511
    joint_bq40  (0.07, -0.50, 0.40)           19.7663
    joint_bq0   (0.07, -0.50, 0.00)           23.4398

Pass test: every |fine - standard| < 0.15 pp of newborn CE2 (the thesis tie threshold),
and the three robust rankings hold on the fine grid: wealth tax > capital-income subsidy;
both joint policies > both separate policies; removing the estate tax raises newborn CE2.
Benchmark moments are compared too, to show whether the grid moves the calibration.

Build first with make_grid_variant.py.  Outputs only under experiments/grid_accuracy_2022/
(runs/na<NA>/, results_na<NA>.md/.json).  Re-running resumes: a benchmark with done.json and complete solver state
is reused and solved policies come from the evaluator cache.  --plan runs no executable.

    python3 experiments/grid_accuracy_2022/run_grid_check.py --plan
    nohup caffeinate -i python3 experiments/grid_accuracy_2022/run_grid_check.py \\
        > experiments/grid_accuracy_2022/run.log 2>&1 &
    python3 experiments/grid_accuracy_2022/run_grid_check.py --summary-only
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SENS = ROOT / "experiments" / "model_spec_sensitivity_2022"
sys.path[:0] = [str(ROOT / "tools"), str(SENS)]

import run_sensitivity as rs                                        # noqa: E402
from benchmark_cache import complete_benchmark  # noqa: E402
from policy_evaluation import PolicyEvaluator, atomic_json, read_kv  # noqa: E402

POLICIES = {"owt": (0.030618034, 0.0, 0.40), "okit": (0.0, -0.13618034, 0.40),
            "joint_bq40": (0.07, -0.50, 0.40), "joint_bq0": (0.07, -0.50, 0.0)}
ANCHOR = {"benchmark_anchor": (0.0, 0.25, 0.40)}       # optional: should re-solve to ~0
LABELS = {"owt": "Separate wealth tax (3.06%)", "okit": "Separate capital-income subsidy (−13.62%)",
          "joint_bq40": "7% wealth tax, −50% capital-income tax, 40% estate tax",
          "joint_bq0": "7% wealth tax, −50% capital-income tax, no estate tax",
          "benchmark_anchor": "Benchmark policy (should be ≈ 0)"}
CONTROL_BENCH = SENS / "runs" / "control" / "benchmark"
CONTROL_ROOTS = [SENS / "runs" / "control" / "policies",
                 ROOT / "experiments" / "robustness_gkkoc_2022" / "runs" / "baseline"]
# Values reported in Section 7.3; the control results found on disk must match them.
EXPECTED_CONTROL = {"owt": 8.3912, "okit": 4.9511, "joint_bq40": 19.7663, "joint_bq0": 23.4398}
TIE = 0.15                                              # pp of newborn CE2
LOCK = HERE / "runs" / "driver.lock"
OTHER_LOCKS = [ROOT / "experiments/table15_estate_2022/runs/driver.lock",
               ROOT / "experiments/robustness_gkkoc_2022/runs/driver.lock",
               ROOT / "experiments/policy_reoptimization_2022/runs/driver.lock",
               ROOT / "experiments/three_tax_2022/runs/driver.lock",
               SENS / "recal" / "driver.lock", SENS / "runs" / "driver.lock"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variant_dir(na: int) -> Path:
    return HERE / "variants" / f"na{na}"


def run_dir(na: int) -> Path:
    return HERE / "runs" / f"na{na}"


def variant_record(na: int) -> dict:
    """The build made by make_grid_variant.py, checked against its provenance."""
    base = variant_dir(na)
    prov_file = base / "provenance.json"
    if not prov_file.exists():
        raise SystemExit(f"{base.relative_to(ROOT)} not built; run make_grid_variant.py --na {na}")
    prov = json.loads(prov_file.read_text())
    if prov["na"] != na:
        raise SystemExit(f"{prov_file} records na={prov['na']}, not {na}")
    for exe, want in prov["executables_sha256"].items():
        if sha(base / "build" / exe) != want:
            raise SystemExit(f"{exe} in {base.relative_to(ROOT)} changed after its build; rebuild")
    return prov


def control_results() -> dict:
    """Standard-grid results solved against the control's own fresh benchmark."""
    found = {}
    bench = CONTROL_BENCH.resolve()
    relative_bench = CONTROL_BENCH.relative_to(ROOT)
    for root in CONTROL_ROOTS:
        for path in sorted(root.glob("v2_*/*/result.json")):
            try:
                r = json.loads(path.read_text())
                manifest = json.loads((path.parents[1] / "manifest.json").read_text())
            except (OSError, ValueError):
                continue
            recorded_bench = Path(manifest.get("benchmark", ""))
            # Released manifests retain their historical absolute path. Compare
            # its exact model-relative suffix without reading that old checkout.
            relocated = (recorded_bench == relative_bench or
                         (recorded_bench.is_absolute() and
                          recorded_bench.parts[-len(relative_bench.parts):] == relative_bench.parts))
            if r.get("status") != "ok" or not (relocated or recorded_bench.resolve() == bench):
                continue
            for name, rates in (POLICIES | ANCHOR).items():
                if all(abs(a - b) < 1e-12 for a, b in zip((r["tau_w"], r["tau_k"], r["tau_bq"]), rates)):
                    r["source"] = str(path.parent.relative_to(ROOT))
                    r["dbn_max_iter"] = int(manifest["environment"]["GKK_DBN_MAX_ITER"])
                    found.setdefault(name, r)
    return found


def solve_benchmark(na: int, threads: int, max_iter: int) -> dict:
    """As run_sensitivity.solve_benchmark, with this variant's bench.a."""
    folder = run_dir(na) / "benchmark"
    done = folder / "done.json"
    if done.exists() and complete_benchmark(folder):
        print(f"[na{na}] benchmark already solved", flush=True)
        return json.loads(done.read_text())
    exe = variant_dir(na) / "build" / "bench.a"
    if folder.exists():                              # partial output from an interrupted solve
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GKK_", "OMP_"))}
    env.update(rs.calibration_env())
    env.update({**rs.SOLVER, "GKK_DBN_MAX_ITER": str(max_iter)})
    env.update({"OMP_NUM_THREADS": str(threads), "OMP_DYNAMIC": "FALSE", "OMP_NESTED": "FALSE",
                "GKK_RESULT_FOLDER": str(folder.relative_to(ROOT)) + "/"})
    print(f"[na{na}] solving benchmark ({threads} threads, DBN max iter {max_iter})", flush=True)
    start = time.monotonic()
    with (folder / "run.log").open("w") as log:
        code = subprocess.run([str(exe)], cwd=ROOT, env=env, stdout=log,
                              stderr=subprocess.STDOUT).returncode
    elapsed = time.monotonic() - start
    output = read_kv(folder / "output.txt") if (folder / "output.txt").exists() else {}
    if code or output.get("Statistics_Schema") != 3 or not complete_benchmark(folder):
        raise RuntimeError(f"[na{na}] benchmark failed (exit {code}); see {folder / 'run.log'}")
    record = {"na": na, "elapsed_minutes": elapsed / 60, "bench_sha256": sha(exe),
              "environment": {k: env[k] for k in sorted(env) if k.startswith(("GKK_", "OMP_"))}}
    atomic_json(done, record)
    print(f"[na{na}] benchmark solved in {elapsed / 60:.1f} min", flush=True)
    return record


def load_points(na: int) -> dict:
    path = run_dir(na) / "points.json"
    return json.loads(path.read_text()) if path.exists() else {}


def evaluate(na: int, names: list[str], threads: int, max_parallel: int) -> dict:
    ev = PolicyEvaluator(root=ROOT, executable=variant_dir(na) / "build" / "eval.a",
                         benchmark=run_dir(na) / "benchmark", run_root=run_dir(na) / "policies",
                         threads=threads, bounds=rs.BOUNDS, labor_bounds=rs.LABOR_BOUNDS,
                         budget_tolerance=rs.BUDGET_TOLERANCE, fixed_labor=False, calibration_env=None)
    if ev.calibration_env != rs.calibration_env():
        raise SystemExit("evaluator calibration differs from the benchmark calibration")
    pool_rates = POLICIES | ANCHOR
    points = load_points(na)

    def one(name):
        try:
            return name, {**ev.evaluate_rates(pool_rates[name]), "source": str(ev.run_root.relative_to(ROOT))}
        except Exception as exc:                     # one failure must not stop the others
            rates = pool_rates[name]
            return name, {"status": "failed", "error": str(exc),
                          "tau_w": rates[0], "tau_k": rates[1], "tau_bq": rates[2]}

    print(f"[na{na}] evaluating {len(names)} policies, {max_parallel} at a time "
          f"({threads} threads each; context {ev.context_id[:12]})", flush=True)
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        for future in as_completed([pool.submit(one, n) for n in names]):
            name, r = future.result()
            points[name] = r
            atomic_json(run_dir(na) / "points.json", points)
            print(f"[na{na}] {name}: " + (f"CE2 {r['ce2_newborn']:.4f}  tau_l {100 * r['tau_l']:.2f}%"
                  if r["status"] == "ok" else f"FAILED ({r['error']})"), flush=True)
    return points


def summarise(na: int) -> None:
    points, control = load_points(na), control_results()
    fine_bench = run_dir(na) / "benchmark"
    prov = json.loads((variant_dir(na) / "provenance.json").read_text()) \
        if (variant_dir(na) / "provenance.json").exists() else {}
    lines = [f"# Asset-grid accuracy check: na = {na} vs the standard grid (na = 201)", "",
             f"Fine grid: na = {prov.get('na', na)}, fine_na = {prov.get('fine_na', '?')}. "
             "Both sides use the financing calibration, a benchmark solved from scratch on "
             "their own grid, and the same evaluator; only the grid differs.", "",
             "## Newborn CE2 (%)", "",
             "| Policy | Standard grid | Fine grid | Difference (pp) | Within 0.15 pp |",
             "|---|---:|---:|---:|:---:|"]
    rows, diffs = {}, {}
    for name in [n for n in (POLICIES | ANCHOR) if n in points or n in POLICIES]:
        c, f = control.get(name), points.get(name, {})
        ok_f = f.get("status") == "ok"
        d = f["ce2_newborn"] - c["ce2_newborn"] if (c and ok_f) else None
        if d is not None and name in POLICIES:
            diffs[name] = d
        rows[name] = {"label": LABELS[name], "standard": c["ce2_newborn"] if c else None,
                      "fine": f.get("ce2_newborn") if ok_f else None, "difference": d,
                      "standard_source": c.get("source") if c else None,
                      "fine_status": f.get("status", "not run"),
                      "fine_population_ce2": f.get("ce2_population"), "fine_tau_l": f.get("tau_l"),
                      "fine_top1": f.get("top1_wealth_share")}
        lines.append(f"| {LABELS[name]} | " + (f"{c['ce2_newborn']:.4f}" if c else "—") + " | "
                     + (f"{f['ce2_newborn']:.4f}" if ok_f else f.get("status", "not run")) + " | "
                     + (f"{d:+.4f}" if d is not None else "—") + " | "
                     + (("yes" if abs(d) < TIE else "NO") if d is not None and name in POLICIES else "—")
                     + " |")
    fine = {n: points[n]["ce2_newborn"] for n in POLICIES if points.get(n, {}).get("status") == "ok"}
    checks = {}
    if len(diffs) == len(POLICIES):
        checks["all_within_0.15pp"] = all(abs(d) < TIE for d in diffs.values())
        checks["max_abs_difference_pp"] = max(abs(d) for d in diffs.values())
    if len(fine) == len(POLICIES):
        checks["wealth_tax_beats_subsidy"] = fine["owt"] > fine["okit"]
        checks["joint_beats_separate"] = min(fine["joint_bq40"], fine["joint_bq0"]) > max(fine["owt"], fine["okit"])
        checks["estate_removal_raises_welfare"] = fine["joint_bq0"] > fine["joint_bq40"]
        checks["fine_grid_gaps_pp"] = {"owt_minus_okit": fine["owt"] - fine["okit"],
                                       "estate_removal_gain": fine["joint_bq0"] - fine["joint_bq40"]}
    lines += ["", "## Checks", ""]
    if not checks:
        lines.append("- not all four policies are solved yet")
    for k, v in checks.items():
        lines.append(f"- {k}: " + (f"{v:.4f}" if isinstance(v, float) else
                                   ", ".join(f"{a} {b:+.4f}" for a, b in v.items()) if isinstance(v, dict)
                                   else ("passed" if v else "NOT passed")))
    for name, want in EXPECTED_CONTROL.items():
        c = control.get(name)
        if not c:
            lines.append(f"- control {name}: not found on disk")
        elif abs(c["ce2_newborn"] - want) > 5e-4:
            lines.append(f"- control {name}: {c['ce2_newborn']:.4f} differs from the reported {want:.4f}")
    moments = {}
    if (fine_bench / "done.json").exists():
        moments = {"standard": rs.benchmark_moments(CONTROL_BENCH), "fine": rs.benchmark_moments(fine_bench)}
        lines += ["", "## Benchmark moments", "",
                  "| Grid | Ent. pop. | Ent. wealth | Ent. in top 1% | Top 1% | Top 0.1% | Debt/Y | K | Y |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for grid, b in moments.items():
            lines.append(f"| {grid} | {100*b['entrepreneur_population_share']:.2f}% | "
                         f"{100*b['entrepreneur_wealth_share']:.2f}% | {100*b['entrepreneurs_in_top1_share']:.2f}% | "
                         f"{100*b['Wealth_Top_1%']:.2f}% | {100*b['Wealth_Top_0.1%']:.2f}% | "
                         f"{b['Debt_Output']:.4f} | {b['KBAR']:.4f} | {b['YBAR']:.4f} |")
    (HERE / f"results_na{na}.md").write_text("\n".join(lines) + "\n")
    atomic_json(HERE / f"results_na{na}.json", {"na": na, "rows": rows, "checks": checks,
                                                "benchmark_moments": moments, "points": points})
    print("\n".join(lines))


def check_locks() -> None:
    for lock in (LOCK, *OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                if pid > 0:
                    os.kill(pid, 0)
                    raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass                                     # stale lock from a stopped run


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--na", type=int, default=301, help="grid built by make_grid_variant.py (default 301)")
    ap.add_argument("--threads-bench", type=int, default=4, help="as the control benchmark (4)")
    ap.add_argument("--threads-policy", type=int, default=4)
    ap.add_argument("--max-parallel", type=int, default=2,
                    help="policy solves at once; each needs roughly 4-5 GB at na=301")
    ap.add_argument("--dbn-max-iter", type=int, default=2000,
                    help="iteration cap; a converged solution does not depend on it")
    ap.add_argument("--policies", default=",".join(POLICIES),
                    help="comma-separated subset of " + ",".join(POLICIES | ANCHOR))
    ap.add_argument("--with-anchor", action="store_true",
                    help="also re-solve the benchmark policy (should give CE2 ≈ 0)")
    ap.add_argument("--plan", action="store_true",
                    help="show the build, the control values and the work to do; run no executable")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()
    names = [n.strip() for n in args.policies.split(",") if n.strip()]
    if args.with_anchor and "benchmark_anchor" not in names:
        names.append("benchmark_anchor")
    if not names or any(n not in POLICIES | ANCHOR for n in names):
        ap.error(f"--policies must be a subset of {','.join(POLICIES | ANCHOR)}")
    if min(args.threads_bench, args.threads_policy, args.max_parallel, args.dbn_max_iter) < 1:
        ap.error("threads, --max-parallel and --dbn-max-iter must be positive")
    if args.summary_only:
        summarise(args.na)
        return 0

    control = control_results()
    missing = [n for n in POLICIES if n not in control]
    if missing:
        raise SystemExit(f"standard-grid control results not found for {missing}")
    for n, want in EXPECTED_CONTROL.items():
        if abs(control[n]["ce2_newborn"] - want) > 5e-4:
            raise SystemExit(f"control {n} is {control[n]['ce2_newborn']:.4f}, not the reported {want:.4f}")
    if args.plan:
        built = ((variant_dir(args.na) / "provenance.json").exists() and
                 all((variant_dir(args.na) / "build" / exe).is_file()
                     for exe in ("bench.a", "eval.a")))
        print(f"variant na{args.na}: {'built' if built else 'NOT built yet (run make_grid_variant.py)'}")
        if built:
            prov = variant_record(args.na)
            print(f"  fine_na={prov['fine_na']}, changed vs control: {prov['files_changed_vs_control']}")
        bench_folder = run_dir(args.na) / "benchmark"
        bench_done = (bench_folder / "done.json").exists() and complete_benchmark(bench_folder)
        print(f"benchmark: {'solved (reused)' if bench_done else 'to solve'}")
        print("standard-grid values (control):")
        for n in POLICIES:
            print(f"  {n:11s} {control[n]['ce2_newborn']:.4f}  ({control[n]['source']})")
        done = {n for n, r in load_points(args.na).items() if r.get("status") == "ok"}
        print(f"requested policies: {names} ({args.max_parallel} at a time); "
              f"saved summary records: {sorted(done)}")
        print("Each requested policy is validated against the local executable and benchmark; "
              "a summary record alone does not skip its solve.")
        print("Plan only: no executable was run.")
        return 0

    variant_record(args.na)
    check_locks()
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)        # the evaluator inherits GKK_*
    LOCK.write_text(str(os.getpid()))
    try:
        solve_benchmark(args.na, args.threads_bench, args.dbn_max_iter)
        evaluate(args.na, names, args.threads_policy, args.max_parallel)
        summarise(args.na)
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Asset-grid check for the extended-subsidy policies (thesis Section 6.3, extended grid table).

Appendix A.3 checks four policies on 201, 301 and 401 asset-grid points. This driver
evaluates the three no-estate-tax extended-subsidy policies on the same three grids, each
against its own freshly solved benchmark, with the evaluator settings of run_grid_check.py:

    name      (tau_w, tau_k, tau_bq)
    w8_s80    (0.08, -0.80, 0.00)     8% wealth tax, 80% subsidy
    w9_s95    (0.09, -0.95, 0.00)     9% wealth tax, 95% subsidy (highest reported gain)
    w10_s95   (0.10, -0.95, 0.00)     10% wealth tax, 95% subsidy (reported as tied with w9_s95)

Benchmarks: 201 points uses the fresh control benchmark of model_spec_sensitivity_2022, the
same base as the 201 column of the thesis's three-grid table; 301 and 401 points use the
benchmarks solved by run_grid_check.py. No benchmark is solved here; all three must exist.

Evaluators: the standard builds reject capital-income taxes below -50%, so each grid uses
variants/na<N>_guard/build/eval.a from make_guard_variant.py. It is the grid build with
only that input check relaxed to -0.95, as in the build behind the reported extended
results (robustness_gkkoc_2022/variant_partb/guard). Build them first:

    python3 experiments/grid_accuracy_2022/make_guard_variant.py

The summary answers three questions:
  * how far each extended gain moves from 201 to 401 points, next to the largest move of
    the four policies in the existing check;
  * whether 9%/-95% and 10%/-95% stay within the 0.15-point tie threshold on every grid;
  * whether newborn CE2 still rises from 7%/-50% to 8%/-80% to the better 95% point.

Outputs go only under experiments/grid_accuracy_2022/: runs/na<N>/policies_extended/,
runs/na<N>/points_extended.json, results_extended.md and results_extended.json. The
existing points.json and results_na301/401 files are not touched. Re-running resumes from
the evaluator cache. --plan runs no executable.

    python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --plan
    nohup caffeinate -i python3 experiments/grid_accuracy_2022/run_extended_grid_check.py \\
        > experiments/grid_accuracy_2022/run_extended.log 2>&1 &
    python3 experiments/grid_accuracy_2022/run_extended_grid_check.py --summary-only
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import run_grid_check as rgc                                       # same folder; sets sys.path

GRIDS = (201, 301, 401)
EXTENDED = {"w8_s80": (0.08, -0.80, 0.0), "w9_s95": (0.09, -0.95, 0.0), "w10_s95": (0.10, -0.95, 0.0)}
LABELS = {"joint_bq0": "7% wealth tax, −50% capital-income tax (existing check)",
          "w8_s80": "8% wealth tax, −80% capital-income tax",
          "w9_s95": "9% wealth tax, −95% capital-income tax",
          "w10_s95": "10% wealth tax, −95% capital-income tax"}
# The most informative points first, so an interrupted night still answers the main question.
JOB_ORDER = [(na, name) for name in ("w9_s95", "w10_s95", "w8_s80") for na in GRIDS]
WRITE_LOCK = threading.Lock()
OUT = rgc.HERE                                                     # results_extended.md/.json


def guard_dir(na: int) -> Path:
    return rgc.HERE / "variants" / f"na{na}_guard"


def context(na: int) -> tuple[Path, Path, Path]:
    """Evaluator executable, benchmark folder and output base for one grid."""
    exe = guard_dir(na) / "build" / "eval.a"
    if na == 201:
        return exe, rgc.CONTROL_BENCH, rgc.HERE / "runs" / "na201"
    return exe, rgc.run_dir(na) / "benchmark", rgc.run_dir(na)


def guard_record(na: int) -> dict:
    """The guard build made by make_guard_variant.py, checked against its provenance."""
    prov_file = guard_dir(na) / "provenance.json"
    if not prov_file.exists():
        raise SystemExit(f"variants/na{na}_guard not built; run make_guard_variant.py")
    prov = json.loads(prov_file.read_text())
    if prov["na"] != na or prov["files_changed_vs_grid_build"] != ["GKK_Main.f90"]:
        raise SystemExit(f"{prov_file} does not describe a guard build of na={na}")
    if rgc.sha(guard_dir(na) / "build" / "eval.a") != prov["executables_sha256"]["eval.a"]:
        raise SystemExit(f"variants/na{na}_guard/build/eval.a changed after its build; rebuild")
    return prov


def benchmark_ready(na: int) -> bool:
    _, bench, _ = context(na)
    if not (bench / "output.txt").exists() or not rgc.complete_benchmark(bench):
        return False
    return na == 201 or (bench / "done.json").exists()


def points_file(na: int) -> Path:
    return context(na)[2] / "points_extended.json"


def load_points(na: int) -> dict:
    path = points_file(na)
    return json.loads(path.read_text()) if path.exists() else {}


def evaluator(na: int) -> rgc.PolicyEvaluator:
    exe, bench, base = context(na)
    guard_record(na)
    if na != 201:
        rgc.variant_record(na)                       # the build that solved this benchmark
    ev = rgc.PolicyEvaluator(root=rgc.ROOT, executable=exe, benchmark=bench,
                             run_root=base / "policies_extended", threads=ARGS.threads_policy,
                             bounds=rgc.rs.BOUNDS, labor_bounds=rgc.rs.LABOR_BOUNDS,
                             budget_tolerance=rgc.rs.BUDGET_TOLERANCE, fixed_labor=False,
                             calibration_env=None)
    if ev.calibration_env != rgc.rs.calibration_env():
        raise SystemExit(f"[na{na}] evaluator calibration differs from the benchmark calibration")
    return ev


def run_jobs(jobs: list[tuple[int, str]]) -> None:
    evaluators = {na: evaluator(na) for na in sorted({na for na, _ in jobs})}

    def one(job):
        na, name = job
        rates = EXTENDED[name]
        try:
            result = {**evaluators[na].evaluate_rates(rates),
                      "source": str(evaluators[na].run_root.relative_to(rgc.ROOT))}
        except Exception as exc:                     # one failure must not stop the others
            result = {"status": "failed", "error": str(exc),
                      "tau_w": rates[0], "tau_k": rates[1], "tau_bq": rates[2]}
        return na, name, result

    print(f"evaluating {len(jobs)} policy/grid pairs, {ARGS.max_parallel} at a time "
          f"({ARGS.threads_policy} threads each)", flush=True)
    with ThreadPoolExecutor(max_workers=ARGS.max_parallel) as pool:
        for future in as_completed([pool.submit(one, job) for job in jobs]):
            na, name, r = future.result()
            with WRITE_LOCK:
                points = load_points(na)
                points[name] = r
                points_file(na).parent.mkdir(parents=True, exist_ok=True)
                rgc.atomic_json(points_file(na), points)
            print(f"[na{na}] {name}: " + (f"CE2 {r['ce2_newborn']:.4f}  tau_l {100 * r['tau_l']:.2f}%  "
                  f"{r.get('elapsed_seconds', 0) / 3600:.2f} h" if r["status"] == "ok"
                  else f"FAILED ({r['error']})"), flush=True)


def reference_joint_bq0() -> dict:
    """The 7%/-50%/0 point from the existing check: control at 201, points.json at 301/401."""
    out = {}
    control = rgc.control_results().get("joint_bq0")
    if control:
        out[201] = control
    for na in GRIDS[1:]:
        r = rgc.load_points(na).get("joint_bq0")
        if r and r.get("status") == "ok":
            out[na] = r
    return out


def largest_baseline_move() -> float | None:
    """Largest |401 - 201| newborn-CE2 move among the four policies of the existing check."""
    control, fine = rgc.control_results(), rgc.load_points(401)
    moves = [abs(fine[n]["ce2_newborn"] - control[n]["ce2_newborn"]) for n in rgc.POLICIES
             if n in control and fine.get(n, {}).get("status") == "ok"]
    return max(moves) if len(moves) == len(rgc.POLICIES) else None


def summarise() -> None:
    ok = {na: {n: r for n, r in load_points(na).items() if r.get("status") == "ok"} for na in GRIDS}
    ref = reference_joint_bq0()
    ce2 = {"joint_bq0": {na: r["ce2_newborn"] for na, r in ref.items()}}
    for name in EXTENDED:
        ce2[name] = {na: ok[na][name]["ce2_newborn"] for na in GRIDS if name in ok[na]}

    lines = ["# Asset-grid check for the extended-subsidy policies", "",
             "Newborn CE2 (%) against each grid's own freshly solved benchmark (no estate tax). "
             "201 points: control build and benchmark of model_spec_sensitivity_2022. "
             "301/401 points: the builds and benchmarks of run_grid_check.py.", "",
             "| Policy | 201 | 301 | 401 | 401 − 201 (pp) |", "|---|---:|---:|---:|---:|"]
    moves = {}
    for name, values in ce2.items():
        move = values[401] - values[201] if 201 in values and 401 in values else None
        if move is not None:
            moves[name] = move
        cells = [f"{values[na]:.4f}" if na in values else "—" for na in GRIDS]
        lines.append(f"| {LABELS[name]} | " + " | ".join(cells) + " | "
                     + (f"{move:+.4f}" if move is not None else "—") + " |")

    checks = {"largest_move_of_four_existing_policies_pp": largest_baseline_move(),
              "move_201_to_401_pp": moves, "w9_minus_w10_pp": {}, "w9_w10_tied": {},
              "welfare_rises_with_subsidy": {}}
    for na in GRIDS:
        v = {n: ce2[n].get(na) for n in ce2}
        if v["w9_s95"] is not None and v["w10_s95"] is not None:
            d = v["w9_s95"] - v["w10_s95"]
            checks["w9_minus_w10_pp"][na] = d
            checks["w9_w10_tied"][na] = abs(d) < rgc.TIE
        if all(x is not None for x in v.values()):
            checks["welfare_rises_with_subsidy"][na] = (
                v["joint_bq0"] < v["w8_s80"] < max(v["w9_s95"], v["w10_s95"]))

    lines += ["", "## Checks", ""]
    big = checks["largest_move_of_four_existing_policies_pp"]
    lines.append("- Largest 201→401 move among the four existing policies: "
                 + (f"{big:.4f} pp" if big is not None else "not available"))
    for na in GRIDS:
        parts = []
        if na in checks["w9_minus_w10_pp"]:
            d = checks["w9_minus_w10_pp"][na]
            parts.append(f"9% minus 10% at −95%: {d:+.4f} pp ("
                         + ("tied" if checks["w9_w10_tied"][na] else "NOT tied") + ")")
        if na in checks["welfare_rises_with_subsidy"]:
            parts.append("welfare rises 7%/−50% → 8%/−80% → 95%: "
                         + ("yes" if checks["welfare_rises_with_subsidy"][na] else "NO"))
        lines.append(f"- {na} points: " + ("; ".join(parts) if parts else "not all points solved yet"))

    lines += ["", "## Extended points in detail", "",
              "| Grid | Policy | Population CE2 | Labour tax | Output | Top 1% | Agg. residual | Revenue gap | Hours |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for na in GRIDS:
        for name in EXTENDED:
            r = load_points(na).get(name)
            if not r:
                continue
            if r.get("status") != "ok":
                lines.append(f"| {na} | {name} | {r.get('status')}: {r.get('error', '')} | | | | | | |")
                continue
            lines.append(f"| {na} | {name} | {r['ce2_population']:.3f}% | {100 * r['tau_l']:.2f}% | "
                         f"{r['output_growth']:+.2f}% | {100 * r['top1_wealth_share']:.2f}% | "
                         f"{r['aggregate_residual']:.1e} | {r['revenue_relative_gap']:.1e} | "
                         f"{r.get('elapsed_seconds', 0) / 3600:.2f} |")

    (OUT / "results_extended.md").write_text("\n".join(lines) + "\n")
    rgc.atomic_json(OUT / "results_extended.json",
                    {"newborn_ce2": {n: {str(k): v for k, v in vals.items()} for n, vals in ce2.items()},
                     "checks": json.loads(json.dumps(checks, default=str)),
                     "points": {str(na): load_points(na) for na in GRIDS}})
    print("\n".join(lines))


def plan(jobs: list[tuple[int, str]]) -> None:
    for na in GRIDS:
        exe, bench, base = context(na)
        prov_file = guard_dir(na) / "provenance.json"
        built = exe.is_file() and prov_file.exists()
        same = json.loads(prov_file.read_text()).get("identical_to_partb_guard") if built else None
        print(f"na{na}: guard evaluator {'built' if built else 'NOT built (run make_guard_variant.py)'}"
              + ("" if same is None else f", identical to variant_partb/guard: {same}") + "; "
              f"benchmark {'ready' if benchmark_ready(na) else 'NOT ready'} ({bench.relative_to(rgc.ROOT)}); "
              f"saved points: {sorted(n for n, r in load_points(na).items() if r.get('status') == 'ok')}")
    print(f"jobs in order ({ARGS.max_parallel} at a time): " + ", ".join(f"{n}@{na}" for na, n in jobs))
    print("Each job is validated against the local executable and benchmark; a saved record alone "
          "does not skip its solve. Plan only: no executable was run.")


def main() -> int:
    global ARGS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grids", default=",".join(map(str, GRIDS)), help="subset of 201,301,401")
    ap.add_argument("--policies", default=",".join(EXTENDED), help="subset of " + ",".join(EXTENDED))
    ap.add_argument("--threads-policy", type=int, default=4)
    ap.add_argument("--max-parallel", type=int, default=2,
                    help="policy solves at once (two 401-point solves fit in 24 GB)")
    ap.add_argument("--dbn-max-iter", type=int, default=2000, help="as run_grid_check.py")
    ap.add_argument("--plan", action="store_true", help="show the work to do; run no executable")
    ap.add_argument("--summary-only", action="store_true")
    ARGS = ap.parse_args()
    grids = [int(g) for g in ARGS.grids.split(",") if g.strip()]
    names = [n.strip() for n in ARGS.policies.split(",") if n.strip()]
    if any(g not in GRIDS for g in grids) or any(n not in EXTENDED for n in names):
        ap.error(f"--grids must be a subset of {GRIDS} and --policies of {list(EXTENDED)}")
    if min(ARGS.threads_policy, ARGS.max_parallel, ARGS.dbn_max_iter) < 1:
        ap.error("--threads-policy, --max-parallel and --dbn-max-iter must be positive")
    jobs = [(na, n) for na, n in JOB_ORDER if na in grids and n in names]

    if ARGS.summary_only:
        summarise()
        return 0
    if ARGS.plan:
        plan(jobs)
        return 0
    not_ready = [na for na in grids if not benchmark_ready(na)]
    if not_ready:
        raise SystemExit(f"benchmark missing for grids {not_ready}; see --plan")
    for na in grids:
        guard_record(na)

    rgc.check_locks()
    rgc.LOCK.parent.mkdir(parents=True, exist_ok=True)
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["GKK_DBN_MAX_ITER"] = str(ARGS.dbn_max_iter)        # the evaluator inherits GKK_*
    rgc.LOCK.write_text(str(os.getpid()))
    try:
        run_jobs(jobs)
        summarise()
    finally:
        rgc.LOCK.unlink(missing_ok=True)
    return 0


ARGS: argparse.Namespace


if __name__ == "__main__":
    raise SystemExit(main())

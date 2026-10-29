#!/usr/bin/env python3
"""Part D: subsidies beyond -80%. Does newborn welfare peak before the input limit?

Part B (partB_results.md) found newborn CE2 still rising at a -80% capital-income tax with
no estate tax (28.30 at a 7% wealth tax, 28.71 at 8%). Part D extends the same exercise:

    tau_k = -80%           at tau_w {9, 10}%
    tau_k = -90%, -95%     at tau_w {8, 9, 10}%
    estate tax 0 throughout

Everything else is identical to Part B: thesis calibration, saved benchmark, labour tax as
the residual, and the guard-relaxed build variant_partb/guard (only the input check
moved, to -95%, the lowest rate it accepts). The evaluator writes to Part B's run folder
with the same settings, so its context and cache are shared: the 7%/-50%/0 consistency
check (23.539) is read from the cache. A point that fails is retried once with
variant_partb/guard_rb (bounded interest-rate search), which adds its own check.

Runs --max-parallel at a time (default 2), about 4-5 hours for 8 points. Outputs only
under experiments/robustness_gkkoc_2022/runs/; summary in partD_results.md. Re-running
resumes from the cache.

    python3 experiments/robustness_gkkoc_2022/partD.py --check-only
    python3 experiments/robustness_gkkoc_2022/partD.py
    python3 experiments/robustness_gkkoc_2022/partD.py --summary-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tier1 as t1                                                  # noqa: E402
from tier1 import RUNS                                              # noqa: E402
from partB import CHECK, CHECK_CE2, CHECK_TOL, EXE, REOPT, check_inputs  # noqa: E402

D = [(f"d_{round(100 * w)}_{round(-100 * k)}_0", (w, k, 0.0))
     for w, k in ((0.08, -0.90), (0.09, -0.90), (0.08, -0.95), (0.09, -0.95),
                  (0.10, -0.90), (0.10, -0.95), (0.09, -0.80), (0.10, -0.80))]
KS = [-0.50, -0.60, -0.70, -0.80, -0.90, -0.95]


def load(name: str) -> dict:
    path = RUNS / name
    return json.loads(path.read_text()) if path.exists() else {}


def surface() -> dict:
    """{(tau_w, tau_k): result} for estate tax 0 under the thesis calibration."""
    pts = {}
    for f in ("grid_points.json", "edge_points.json"):
        if (REOPT / f).exists():
            for p in json.loads((REOPT / f).read_text()):
                if (p["calibration"] == "thesis" and p.get("status") == "ok"
                        and abs(p["rates"][2]) < 1e-12 and abs(p["rates"][1] + 0.50) < 1e-9):
                    pts[(round(p["rates"][0], 4), -0.50)] = p
    for source in (load("partB_b3.json"), load("partD_all.json")):
        for name, r in source.items():
            if name.startswith("check_") or r.get("status") != "ok":
                continue
            key = (round(r["tau_w"], 4), round(r["tau_k"], 4))
            if name.endswith("_rb") and key in pts:
                continue                                 # keep the guard build when both exist
            pts[key] = r
    return pts


def summarise() -> None:
    pts = surface()
    ws = sorted({w for w, _ in pts if w >= 0.07})
    best = max(pts.values(), key=lambda p: p["ce2_newborn"]) if pts else None
    lines = ["# Part D: subsidies beyond -80% (thesis calibration, saved benchmark, estate tax 0)", "",
             "Newborn CE2 (%). The -50% column is from the re-optimisation grid and edge sweep; "
             "-60% to -80% at 7-8% from Part B; the rest from Part D (guard-relaxed build).", "",
             "| τ_w \\ τ_k | " + " | ".join(f"{100 * k:+.0f}%" for k in KS) + " |",
             "|---|" + "---:|" * len(KS)]
    for w in ws:
        cells = []
        for k in KS:
            p = pts.get((w, round(k, 4)))
            v = "—" if p is None else f"{p['ce2_newborn']:.2f}"
            cells.append(f"**{v}**" if p is not None and p is best else v)
        lines.append(f"| {100 * w:.1f}% | " + " | ".join(cells) + " |")
    lines.append("")
    if best:
        lines.append(f"Best tested: τ_w {100 * best['tau_w']:.1f}%, τ_k {100 * best['tau_k']:+.0f}%, estate 0: "
                     f"newborn CE2 {best['ce2_newborn']:.2f} (population {best['ce2_population']:.2f}, "
                     f"labour tax {100 * best['tau_l']:.2f}%, output {best['output_growth']:+.2f}%, "
                     f"top 1% {100 * best['top1_wealth_share']:.2f}%).")
        edge = abs(best["tau_k"] - KS[-1]) < 1e-9
        lines.append("The best tested point is at the -95% input limit: no interior peak is identified."
                     if edge else "The best tested point is inside the tested subsidy range: welfare peaks "
                     "before the -95% limit.")
        for w in ws:
            row = [(k, pts[(w, round(k, 4))]["ce2_newborn"]) for k in KS if (w, round(k, 4)) in pts]
            if len(row) >= 3:
                kbest = max(row, key=lambda x: x[1])[0]
                lines.append(f"- τ_w {100 * w:.0f}%: highest at τ_k {100 * kbest:+.0f}% "
                             + ("(edge of the tested range)" if kbest in (row[0][0], row[-1][0]) else "(interior)"))
    allr = {**load("partB_b3.json"), **load("partD_all.json")}
    for name, r in allr.items():
        if name.startswith("check_"):
            ok = r.get("status") == "ok" and abs(r["ce2_newborn"] - CHECK_CE2) <= CHECK_TOL
            lines.append(f"Consistency check {name}: " + (f"{r['ce2_newborn']:.3f} vs {CHECK_CE2} → "
                         f"{'passed' if ok else 'NOT passed'}" if r.get("status") == "ok" else "FAILED"))
    failed = [n for n, r in load("partD_all.json").items() if r.get("status") != "ok"]
    if failed:
        lines.append("Failed points (after any retry): " + ", ".join(failed))
    (HERE / "partD_results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--dbn-max-iter", type=int, default=2000)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.summary_only:
        summarise()
        return 0
    check_inputs(need_theta=False)
    if args.check_only:
        print("Part D (thesis calibration, saved benchmark, guard build, estate tax 0):")
        for name, rates in [CHECK, *D]:
            print(f"  {name:12s} tau_w {100 * rates[0]:.0f}%  tau_k {100 * rates[1]:+.0f}%")
        print(f"{len(D)} new solves, {args.max_parallel} at a time. Check only: nothing was run.")
        return 0
    for k in [k for k in os.environ if k.startswith(("GKK_", "OMP_"))]:
        del os.environ[k]
    os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)    # the evaluator inherits GKK_*
    for lock in (t1.LOCK, *t1.OTHER_LOCKS):
        if lock.exists():
            pid = int(lock.read_text().strip() or 0)
            try:
                os.kill(pid, 0)
                raise SystemExit(f"another driver (pid {pid}, {lock}) is running; stop it first")
            except ProcessLookupError:
                pass                                             # stale lock from a stopped run
    t1.LOCK.write_text(str(os.getpid()))
    try:
        guard = t1.evaluator(t1.SAVED_BENCH, RUNS / "partB_guard", args.threads, exe=EXE["guard"])
        t1.run_jobs([(n, guard, r) for n, r in [CHECK, *D]], args.max_parallel, "partD_all.json")
        allr = load("partD_all.json")
        failed = [(n, r) for n, r in D if allr.get(n, {}).get("status") != "ok"]
        if failed:
            guard_rb = t1.evaluator(t1.SAVED_BENCH, RUNS / "partB_guard_rb", args.threads, exe=EXE["guard_rb"])
            retry = [(n + "_rb", guard_rb, r) for n, r in failed] + [(CHECK[0] + "_rb", guard_rb, CHECK[1])]
            t1.run_jobs(retry, args.max_parallel, "partD_all.json")
        summarise()
    finally:
        t1.LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

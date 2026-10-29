#!/usr/bin/env python3
"""Robustness of the headline policy results to the financing recalibration.

Section 2.5 raises theta_max from the published 2.8 to 2.9521 to match the 2022
business-financing target, and notes that doing so weakens all three
entrepreneurship moments.  Section 5 never asks whether that change moves the
policy conclusions.  This script answers that question directly.

Two arms, identical in every respect except theta_max:

    published   theta_max = 2.8         (GKKOC value)
    financing   theta_max = 2.9521...   (2022 financing target)

Both hold the SCF active-manager entrepreneurial parameters fixed at
calibration/runs/scf_2022/best.json, and rho_z at 0.1.

Each arm evaluates the paper's own three headline anchors, taken verbatim from
tools/optimize_joint_taxes.py:

    (0.0,         0.25,        0.40)   US benchmark tax system
    (0.030618034, 0.0,         0.40)   optimal wealth tax (OWT)
    (0.0,        -0.13618034,  0.40)   optimal capital income tax (OKIT)

Every evaluation is revenue-neutral: the labour tax adjusts to reproduce
benchmark revenue, as everywhere else in the paper.

SAFETY.  This script never writes to calibration/runs/scf_2022/ or
calibration/runs/business_financing_2022/.  Results go to a new tree under
calibration/runs/theta_max_robustness_2022/.  Benchmarks are read only.

Usage:

    # verify inputs, print the plan, solve nothing
    python3 tools/theta_max_robustness_2022.py --check-only

    # run it (6 policy solves, roughly 1.5-2.5 hours)
    python3 tools/theta_max_robustness_2022.py --threads 4

Re-running is safe: PolicyEvaluator caches by candidate, so completed points are
reused rather than re-solved.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from policy_evaluation import PolicyEvaluator, atomic_json  # noqa: E402

EXECUTABLE = ROOT / "Compiled_Files_Baseline" / "GKK_Main.a"
SCF_BEST = ROOT / "calibration" / "runs" / "scf_2022" / "best.json"
FINANCING_BEST = ROOT / "calibration" / "runs" / "business_financing_2022" / "best.json"
OUT_ROOT = ROOT / "calibration" / "runs" / "theta_max_robustness_2022"

# Benchmark economies. Both already exist; neither is written to.
BENCHMARKS = {
    "published": ROOT / "calibration" / "runs" / "scf_2022" / "3f5118dda04e",
    "financing": ROOT / "calibration" / "runs" / "business_financing_2022" / "rn_reform",
}

PUBLISHED_THETA_MAX = 2.8

# Verbatim from tools/optimize_joint_taxes.py standard_anchors.
ANCHORS = [
    ("benchmark", (0.0, 0.25, 0.40)),
    ("owt", (0.030618034, 0.0, 0.40)),
    ("okit", (0.0, -0.13618034, 0.40)),
]

# Wide enough never to bind: this script evaluates fixed points, it does not search.
BOUNDS = ((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0))
LABOR_BOUNDS = (0.0, 0.60)


def scf_parameters() -> dict[str, float]:
    payload = json.loads(SCF_BEST.read_text())
    return {name: float(value) for name, value in payload["parameters"].items()}


def theta_max_values() -> dict[str, float]:
    financing = json.loads(FINANCING_BEST.read_text())
    return {
        "published": PUBLISHED_THETA_MAX,
        "financing": float(financing["theta_max"]),
    }


def calibration_env(parameters: dict[str, float], theta_max: float) -> dict[str, str]:
    """Exactly the environment PolicyEvaluator would build, with theta_max overridden."""
    return {
        "GKK_RHO_Z": "0.1",
        "GKK_SIGMA_Z_EPS": format(parameters["sigma_z_eps"], ".17g"),
        "GKK_X_HI": format(parameters["x_hi"], ".17g"),
        "GKK_P1_X": format(parameters["p1_x"], ".17g"),
        "GKK_P2_X": format(parameters["p2_x"], ".17g"),
        "GKK_THETA_MAX": format(theta_max, ".17g"),
    }


def benchmark_theta_max(folder: Path) -> float:
    """Read the top of the Theta grid actually used by a completed benchmark."""
    for line in (folder / "output.txt").read_text(errors="replace").splitlines():
        fields = line.split()
        if fields[:1] == ["Theta"] and len(fields) >= 10:
            return float(fields[9])
    raise ValueError(f"no Theta grid line in {folder / 'output.txt'}")


def preflight(thetas: dict[str, float]) -> None:
    if not EXECUTABLE.exists():
        raise SystemExit(f"executable not found: {EXECUTABLE}\nBuild it before running.")
    for path in (SCF_BEST, FINANCING_BEST):
        if not path.exists():
            raise SystemExit(f"calibration file missing: {path}")
    for arm, folder in BENCHMARKS.items():
        out = folder / "output.txt"
        if not out.exists():
            raise SystemExit(f"benchmark missing for arm '{arm}': {out}")
        found = benchmark_theta_max(folder)
        if not math.isclose(found, thetas[arm], rel_tol=0, abs_tol=1e-8):
            raise SystemExit(
                f"benchmark for arm '{arm}' was solved at theta_max={found:.10f}, "
                f"but this arm requires {thetas[arm]:.10f}.\n"
                f"  {folder}\n"
                "Refusing to run: the revenue target and welfare normalisation "
                "would come from the wrong economy."
            )


def run_arm(arm: str, theta_max: float, parameters: dict[str, float],
            threads: int, budget_tolerance: float, check_only: bool,
            anchors: list) -> list[dict]:
    benchmark = BENCHMARKS[arm]
    print(f"\n=== arm '{arm}': theta_max = {theta_max:.10f} ===", flush=True)
    print(f"benchmark: {benchmark.relative_to(ROOT)}", flush=True)
    if check_only:
        for name, rates in anchors:
            print(f"  would evaluate {name:<10} tau_w={rates[0]:+.9f} "
                  f"tau_k={rates[1]:+.9f} tau_bq={rates[2]:.2f}", flush=True)
        return []

    evaluator = PolicyEvaluator(
        root=ROOT,
        executable=EXECUTABLE,
        benchmark=benchmark,
        run_root=OUT_ROOT / arm,
        threads=threads,
        bounds=BOUNDS,
        labor_bounds=LABOR_BOUNDS,
        budget_tolerance=budget_tolerance,
        fixed_labor=False,
        calibration_env=calibration_env(parameters, theta_max),
    )
    print(f"versioned results: {evaluator.run_root}", flush=True)

    rows = []
    for name, rates in anchors:
        print(f"  {name} ...", flush=True)
        # A single non-convergent anchor must not destroy the whole experiment,
        # including arms that have not started yet. Record it and continue.
        try:
            result = evaluator.evaluate_rates(rates)
        except Exception as exc:
            print(f"    FAILED: {exc}", flush=True)
            rows.append({"status": "failed", "anchor": name, "arm": arm,
                         "theta_max": theta_max, "error": str(exc),
                         "tau_w": rates[0], "tau_k": rates[1], "tau_bq": rates[2]})
            continue
        result["anchor"] = name
        result["arm"] = arm
        result["theta_max"] = theta_max
        rows.append(result)
        print(f"    CE2_newborn={result['ce2_newborn']:+.4f}  "
              f"tau_l={result['tau_l']:.4f}  "
              f"top1={result['top1_wealth_share']:.4f}  "
              f"dY={result['output_growth']:+.2f}%", flush=True)
    evaluator.write_index()
    return rows


def _find_key(obj, key):
    """Return the first value stored under `key` anywhere in a nested manifest."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        obj = list(obj.values())
    if isinstance(obj, list):
        for item in obj:
            found = _find_key(item, key)
            if found is not None:
                return found
    return None


def collect_results(thetas: dict[str, float]) -> list[dict]:
    """Every completed solve on disk, across all run contexts.

    Tabulating only the current invocation let a partial re-run (e.g. OKIT
    alone at a higher iteration cap) replace the full comparison with a subset.
    Results are matched to anchors by their tax rates; if one anchor was solved
    in several contexts, the most recent result wins.
    """
    found: dict[tuple[str, str], dict] = {}
    files = sorted(OUT_ROOT.glob("*/v2_*/*/result.json"), key=lambda p: p.stat().st_mtime)
    for f in files:
        arm = f.relative_to(OUT_ROOT).parts[0]
        if arm not in BENCHMARKS:
            continue
        r = json.loads(f.read_text())
        if r.get("status") != "ok":
            continue
        for name, rates in ANCHORS:
            if all(math.isclose(a, b, rel_tol=0, abs_tol=1e-12)
                   for a, b in zip((r["tau_w"], r["tau_k"], r["tau_bq"]), rates)):
                manifest = json.loads((f.parents[1] / "manifest.json").read_text())
                cap = _find_key(manifest, "GKK_DBN_MAX_ITER")
                found[(arm, name)] = {**r, "anchor": name, "arm": arm,
                                      "theta_max": thetas[arm],
                                      "dbn_max_iter": int(cap) if cap is not None else None}
    return list(found.values())


def write_comparison(rows: list[dict], thetas: dict[str, float]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    by = {(r["arm"], r["anchor"]): r for r in rows}
    atomic_json(OUT_ROOT / "comparison.json", {
        "question": "Do the headline policy results survive the 2.5 financing "
                    "recalibration of theta_max?",
        "arms": thetas,
        "anchors": {name: list(rates) for name, rates in ANCHORS},
        "note": "Entrepreneurial parameters and rho_z are identical across arms; "
                "only theta_max differs. Every point is revenue-neutral via the "
                "labour tax.",
        "results": rows,
    })

    lines = ["# theta_max robustness of the headline policy results", "",
             f"Published arm: theta_max = {thetas['published']:.10f}",
             f"Financing arm: theta_max = {thetas['financing']:.10f}", "",
             "Entrepreneurial parameters identical across arms; only theta_max differs.",
             "All points revenue-neutral via the labour tax.", "",
             "| Anchor | Metric | Published | Financing | Difference |",
             "|---|---|---:|---:|---:|"]
    metrics = [("ce2_newborn", "CE2 newborn (%)"), ("ce1_newborn", "CE1 newborn (%)"),
               ("tau_l", "Labour tax"), ("top1_wealth_share", "Top 1% wealth share"),
               ("output_growth", "Output change (%)"),
               ("consumption_growth", "Consumption change (%)")]
    for name, _ in ANCHORS:
        a, b = by.get(("published", name)), by.get(("financing", name))
        if not (a and b):
            continue
        for key, label in metrics:
            lines.append(f"| {name} | {label} | {a[key]:.4f} | {b[key]:.4f} "
                         f"| {b[key]-a[key]:+.4f} |")

    caps = sorted({(r["anchor"], r.get("dbn_max_iter")) for r in rows},
                  key=lambda x: [n for n, _ in ANCHORS].index(x[0]))
    if caps:
        lines += ["", "Equilibrium iteration cap per anchor: "
                  + ", ".join(f"{a} {c}" for a, c in caps)
                  + ".  Every result passed the validated convergence checks; the cap "
                    "only matters when a solve reaches it."]

    owt_a, owt_b = by.get(("published", "owt")), by.get(("financing", "owt"))
    okit_a, okit_b = by.get(("published", "okit")), by.get(("financing", "okit"))
    if owt_a and okit_a and owt_b and okit_b:
        ga = owt_a["ce2_newborn"] - okit_a["ce2_newborn"]
        gb = owt_b["ce2_newborn"] - okit_b["ce2_newborn"]
        lines += ["", "## Welfare ranking (OWT minus OKIT, CE2 newborn)", "",
                  f"- Published arm: {ga:+.4f}",
                  f"- Financing arm: {gb:+.4f}",
                  f"- Change: {gb-ga:+.4f}", "",
                  f"The ranking **{'is preserved' if ga*gb > 0 else 'REVERSES'}** "
                  "between the two arms."]
    (OUT_ROOT / "comparison.md").write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT_ROOT / 'comparison.json'}")
    print(f"wrote {OUT_ROOT / 'comparison.md'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--budget-tolerance", type=float, default=1.0e-4,
                        help="matches tools/optimize_joint_taxes.py (default 1e-4)")
    parser.add_argument("--check-only", action="store_true",
                        help="verify inputs and print the plan; solve nothing")
    parser.add_argument("--table-only", action="store_true",
                        help="rebuild comparison.md/json from every completed solve; solve nothing")
    parser.add_argument("--arm", choices=["published", "financing"],
                        help="run a single arm instead of both")
    parser.add_argument("--anchors", default=",".join(n for n, _ in ANCHORS),
                        help="comma-separated subset of: "
                             + ",".join(n for n, _ in ANCHORS))
    parser.add_argument("--dbn-max-iter", type=int,
                        help="raise the equilibrium iteration cap (evaluator default 700). "
                             "NOTE: this changes the run fingerprint, so previously "
                             "completed solves are NOT reused.")
    args = parser.parse_args()
    if args.threads < 1 or not (0 < args.budget_tolerance < 1):
        parser.error("threads must be positive and budget tolerance must lie in (0, 1)")

    known = {name: rates for name, rates in ANCHORS}
    chosen = [a.strip() for a in args.anchors.split(",") if a.strip()]
    unknown = [a for a in chosen if a not in known]
    if unknown:
        parser.error(f"unknown anchor(s): {', '.join(unknown)}")
    anchors = [(name, known[name]) for name in chosen]

    if args.dbn_max_iter is not None:
        if args.dbn_max_iter < 1:
            parser.error("--dbn-max-iter must be positive")
        # PolicyEvaluator uses setdefault, so an inherited value is honoured.
        os.environ["GKK_DBN_MAX_ITER"] = str(args.dbn_max_iter)
        print(f"equilibrium iteration cap raised to {args.dbn_max_iter} "
              "(new run fingerprint; cached solves will not be reused)")

    thetas = theta_max_values()
    if args.table_only:
        write_comparison(collect_results(thetas), thetas)
        return 0
    parameters = scf_parameters()
    preflight(thetas)

    print("SCF active-manager parameters (identical in both arms):")
    for name, value in parameters.items():
        print(f"  {name:<14} {value:.17g}")
    print(f"\ntheta_max published = {thetas['published']:.10f}")
    print(f"theta_max financing = {thetas['financing']:.10f}")
    print(f"difference          = {thetas['financing']-thetas['published']:+.10f}")

    arms = [args.arm] if args.arm else ["published", "financing"]
    if args.check_only:
        for arm in arms:
            run_arm(arm, thetas[arm], parameters, args.threads,
                    args.budget_tolerance, check_only=True, anchors=anchors)
        print(f"\nCheck only: no model was run. {len(arms)*len(anchors)} policy "
              "solves would be required (cached points are reused).")
        print("Neither scf_2022/ nor business_financing_2022/ is ever written to.")
        return 0

    rows: list[dict] = []
    for arm in arms:
        rows += run_arm(arm, thetas[arm], parameters, args.threads,
                        args.budget_tolerance, check_only=False, anchors=anchors)
    failed = [r for r in rows if r.get("status") == "failed"]
    # Always tabulate everything on disk, not only this invocation's solves.
    write_comparison(collect_results(thetas), thetas)
    if failed:
        print(f"\n{len(failed)} solve(s) did not converge:")
        for r in failed:
            print(f"  {r['arm']}/{r['anchor']}: {r['error']}")
        print("Retry just those with a higher cap, e.g.:")
        print(f"  --anchors {','.join(sorted({r['anchor'] for r in failed}))} "
              "--dbn-max-iter 2000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

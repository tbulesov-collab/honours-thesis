#!/usr/bin/env python3
"""Welfare gains and misallocation across validated policy evaluations.

GKKOC (Section 7, last paragraph) report a correlation of 0.92 between the welfare
gain and the change in misallocation, (TFP* - TFP)/TFP*, across their robustness
economies.  This script computes the counterpart from saved results only (no model
run).

The default sample is the 118 evaluations reported in the thesis (Section 7.4.1).
misallocation_link_sample.json lists each one as a model-relative result.json and the
benchmark folder it is compared with, so every copy of the model reproduces that
sample.  --rescan instead uses every result.json in a validated evaluator context
(v2_*/manifest.json) under calibration/runs/ and experiments/, each compared with the
benchmark named in its manifest.  Evaluations saved after the thesis sample was fixed
enter the rescanned sample, so --rescan writes only to a separate --out folder.

TFP* depends only on the ability distribution and technology, which policies do not
change, so it is taken from the benchmark's TFP_Star.txt; the policy's TFP is its
TFP_Q.  Both are in units of quality-adjusted capital (Q/K).  GKKOC's Hsieh-Klenow
measure is in output units, Y = A Q^alpha L^(1-alpha), so misallocation here is
1 - (TFP_Q/TFP*)^alpha with alpha = 0.40 (parameters.f90); for the saved benchmark
this gives 0.150, against GKKOC's 0.16.  A policy point evaluated in several contexts
against the same benchmark is counted once: the thesis sample kept the most recent
evaluation, and --rescan keeps the last one in path order.

    python3 experiments/robustness_gkkoc_2022/misallocation_link.py
    python3 experiments/robustness_gkkoc_2022/misallocation_link.py --rescan --out DIR
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SAMPLE = HERE / "misallocation_link_sample.json"
ALPHA = 0.40
ANCHORS = (("calibration", "runs"), ("experiments",))


def model_path(value: str) -> Path:
    """Resolve a recorded run path inside this copy of the model.

    Manifests record the original machine's absolute benchmark path; its calibration/runs or
    experiments suffix identifies the released location.  An old absolute path is
    never read directly, even if it exists on this computer.
    """
    path = Path(value)
    if path.is_absolute():
        parts = path.parts
        starts = [i for i in range(len(parts)) for a in ANCHORS if parts[i:i + len(a)] == a]
        if not starts:
            raise ValueError(f"Cannot relocate run path: {value}")
        path = Path(*parts[max(starts):])
    root = ROOT.resolve()
    folder = (root / path).resolve()
    if not folder.is_relative_to(root):
        raise ValueError(f"Run path leaves this copy of the model: {value}")
    return folder


def read_kv(path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in path.read_text(errors="replace").splitlines():
        f = line.split()
        if len(f) >= 2:
            try:
                out[f[0]] = float(f[-1].replace("D", "E"))
            except ValueError:
                pass
    return out


def benchmark_stats(folder: Path) -> dict | None:
    out, star = folder / "output.txt", folder / "TFP_Star.txt"
    if not out.exists() or not star.exists():
        return None
    o, s = read_kv(out), read_kv(star)
    if "TFP_Q" not in o or "TFP_Star" not in s:
        return None
    return {"tfp": o["TFP_Q"], "tfp_star": s["TFP_Star"], "K": o["KBAR"], "Y": o["YBAR"]}


def label(bench: Path) -> str:
    rel = bench.relative_to(ROOT.resolve()).as_posix()
    if rel.endswith("business_financing_2022/rn_reform"):
        return "thesis (saved benchmark)"
    if "/recal/control/" in rel:
        return "re-calibrated, original code"
    if "/recal/productivity/" in rel:
        return "re-calibrated, productivity fix"
    if rel.startswith("calibration/runs/scf_2022/"):
        return "thesis params, theta_max 2.8"
    if "model_spec_sensitivity_2022/runs/" in rel:
        return "thesis params, " + rel.split("runs/")[1].split("/")[0] + " code"
    return rel


def evaluation(result: Path, bench: Path) -> dict | None:
    """Compare one saved evaluation with its benchmark; None if either is incomplete."""
    b = benchmark_stats(bench)
    if b is None:
        return None
    r = json.loads(result.read_text())
    if r.get("status") != "ok" or not r.get("feasible"):
        return None
    o = model_path(r["result_directory"]) / "output_exp.txt"
    if not o.exists():
        return None
    v = read_kv(o)
    if "TFP_Q" not in v:
        return None
    row = {"benchmark": label(bench), "tau_w": r["tau_w"], "tau_k": r["tau_k"],
           "tau_bq": r["tau_bq"], "ce2_newborn": r["ce2_newborn"],
           "ce2_population": r["ce2_population"], "output": r["output_growth"],
           "tfp_change": 100 * (v["TFP_Q"] / b["tfp"] - 1),
           "capital_change": 100 * (v["KBAR"] / b["K"] - 1),
           "misalloc_bench": 1 - (b["tfp"] / b["tfp_star"]) ** ALPHA,
           "misalloc_policy": 1 - (v["TFP_Q"] / b["tfp_star"]) ** ALPHA,
           "source": result.relative_to(ROOT.resolve()).as_posix()}
    row["misalloc_change"] = 100 * (row["misalloc_policy"] - row["misalloc_bench"])
    return row


def collect_sample() -> list[dict]:
    """The evaluations reported in the thesis, in their saved order."""
    rows = []
    for item in json.loads(SAMPLE.read_text())["evaluations"]:
        row = evaluation(model_path(item["result"]), model_path(item["benchmark"]))
        if row is None:
            raise SystemExit(f"Reported evaluation is missing or incomplete: {item['result']}")
        rows.append(row)
    return rows


def collect_all() -> list[dict]:
    """Every validated, revenue-matched evaluation in this copy of the model."""
    rows: dict[tuple, dict] = {}
    manifests = sorted(ROOT.glob("calibration/runs/**/v2_*/manifest.json")) + \
        sorted(ROOT.glob("experiments/**/v2_*/manifest.json"))
    for manifest in manifests:
        m = json.loads(manifest.read_text())
        if m.get("fixed_labor"):
            continue                       # revenue not matched: not a comparable policy
        bench = model_path(m["benchmark"])
        for res in sorted(manifest.parent.glob("*/result.json")):
            row = evaluation(res, bench)
            if row is not None:
                key = (str(bench), round(row["tau_w"], 6), round(row["tau_k"], 6),
                       round(row["tau_bq"], 6))
                rows[key] = row            # a later evaluation replaces an earlier one
    return [r for r in rows.values() if abs(r["tau_w"]) + abs(r["tau_k"] - 0.25) > 1e-9
            or abs(r["tau_bq"] - 0.40) > 1e-9]          # drop the benchmark policy itself


def corr(x, y) -> float:
    return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rescan", action="store_true",
                    help="use every validated evaluation in this copy, not the thesis sample")
    ap.add_argument("--out", type=Path, default=HERE,
                    help="folder for misallocation_link.md/.json (default: next to this script)")
    args = ap.parse_args()
    out = args.out.resolve()
    if args.rescan and out == HERE:
        ap.error("--rescan changes the sample; pass --out to keep the thesis results")
    rows = collect_all() if args.rescan else collect_sample()
    sample = ("every validated evaluation in this copy (--rescan)" if args.rescan
              else f"the {len(rows)} evaluations reported in the thesis ({SAMPLE.name})")

    groups = {"all": rows}
    for r in rows:
        groups.setdefault(r["benchmark"], []).append(r)
    groups["estate tax 40%"] = [r for r in rows if abs(r["tau_bq"] - 0.40) < 1e-6]
    groups["estate tax zero or near-zero"] = [r for r in rows if r["tau_bq"] < 0.005]
    groups["separate taxes, estate tax 40%"] = [r for r in rows if (r["tau_w"] == 0 or r["tau_k"] == 0)
                                                and abs(r["tau_bq"] - 0.40) < 1e-6]
    groups["joint packages (wealth tax and subsidy)"] = [r for r in rows if r["tau_w"] > 0 and r["tau_k"] < 0]

    lines = ["# Welfare gain and misallocation across validated policies", "",
             f"Sample: {sample}.  "
             "Misallocation = 1 - (TFP/TFP*)^alpha (GKKOC's output-based measure; alpha = 0.4), "
             "TFP* from each benchmark.  Change in misallocation is in percentage points "
             "(negative = less misallocation).  Correlations are Pearson, across policies.  "
             "Fixed-labour (revenue-unmatched) evaluations are excluded. "
             "The zero or near-zero estate-tax group uses rates below 0.5%.", "",
             "| Group | Policies | corr(CE2, -Δmisallocation) | corr(CE2, ΔK) | "
             "corr(CE2, Δoutput) | Benchmark misallocation |",
             "|---|---:|---:|---:|---:|---:|"]
    summary = {}
    for name, g in groups.items():
        if len(g) < 3:
            continue
        ce = [r["ce2_newborn"] for r in g]
        c_m = corr(ce, [-r["misalloc_change"] for r in g])
        c_k = corr(ce, [r["capital_change"] for r in g])
        c_y = corr(ce, [r["output"] for r in g])
        mb = sorted({round(r["misalloc_bench"], 3) for r in g})
        lines.append(f"| {name} | {len(g)} | {c_m:.2f} | {c_k:.2f} | {c_y:.2f} | "
                     + ", ".join(f"{x:.3f}" for x in mb) + " |")
        summary[name] = {"n": len(g), "corr_ce2_misalloc_reduction": c_m,
                         "corr_ce2_capital": c_k, "corr_ce2_output": c_y}

    # Within each benchmark, does misallocation explain welfare beyond capital deepening?
    lines += ["", "## Regression of newborn CE2 on the two channels, by benchmark", "",
              "| Benchmark | Policies | β(-Δmisallocation, pp) | β(ΔK, %) | R² |",
              "|---|---:|---:|---:|---:|"]
    for name, g in groups.items():
        if name == "all" or name.startswith(("estate", "separate", "joint")) or len(g) < 6:
            continue
        X = np.column_stack([np.ones(len(g)), [-r["misalloc_change"] for r in g],
                             [r["capital_change"] for r in g]])
        y = np.array([r["ce2_newborn"] for r in g])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        r2 = 1 - np.sum((y - X @ beta) ** 2) / np.sum((y - y.mean()) ** 2)
        lines.append(f"| {name} | {len(g)} | {beta[1]:.2f} | {beta[2]:.2f} | {r2:.2f} |")
        summary[name]["regression"] = {"misalloc_reduction": beta[1], "capital": beta[2], "r2": r2}

    lines += ["", "## Selected policies", "",
              "| Benchmark | τ_w | τ_k | τ_b | CE2 | ΔTFP % | Misallocation (bench → policy) | ΔK % |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    picks = [(0.030618034, 0.0, 0.40), (0.0, -0.13618034, 0.40), (0.07, -0.5, 0.40), (0.07, -0.5, 0.0)]
    for r in sorted(rows, key=lambda r: (r["benchmark"], r["tau_bq"], r["tau_w"])):
        if any(abs(r["tau_w"] - a) < 1e-6 and abs(r["tau_k"] - b) < 1e-6 and abs(r["tau_bq"] - c) < 1e-6
               for a, b, c in picks):
            lines.append(f"| {r['benchmark']} | {100*r['tau_w']:.2f}% | {100*r['tau_k']:+.1f}% | "
                         f"{100*r['tau_bq']:.0f}% | {r['ce2_newborn']:.2f} | {r['tfp_change']:+.2f} | "
                         f"{r['misalloc_bench']:.3f} → {r['misalloc_policy']:.3f} | {r['capital_change']:+.2f} |")
    out.mkdir(parents=True, exist_ok=True)
    (out / "misallocation_link.md").write_text("\n".join(lines) + "\n")
    (out / "misallocation_link.json").write_text(json.dumps(
        {"summary": summary, "policies": rows}, indent=1, default=float) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

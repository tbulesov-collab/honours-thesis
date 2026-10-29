#!/usr/bin/env python3
"""Marginal returns and binding collateral constraints under the thesis policies.

Reads saved model reports only; no equilibrium is solved. For the reference benchmark and
the seven policies behind the separate and joint tables (thesis Sections 6.2-6.3) it
collects:

  * the interest rate r and its after-tax value (output.txt / output_exp.txt: R, R_AT);
  * wealth-weighted percentiles of the before-tax marginal return on wealth
    (Mg_Return_W_Pct_*.txt) and the matching after-tax values (1 - tau_k) m - tau_w;
  * the share of households whose collateral constraint binds, by ability and
    productivity state (Constrained_firms_stats*.txt; population-weighted);
  * wealth-weighted mean pre-tax and after-tax returns by ability (Asset_Stats_*.txt).

The saved "After_Tax" rows of Mg_Return_*_Pct files are not used: GKK_Stats.f90 writes
them as m(1 - tau_k) in the benchmark and m - tau_w otherwise, so they omit the
capital-income subsidy when both taxes are active.

Output: results.json and results.md next to this script (or under --out).

    python3 experiments/marginal_returns_2022/extract_marginal_returns.py

For newly solved runs, copy run_map.example.json and replace its model-relative
run folders. Policy IDs and tax rates remain fixed; every run must use the same
benchmark. No source-code edits are needed:

    python3 experiments/marginal_returns_2022/extract_marginal_returns.py \
        --run-map /path/to/my_runs.json --out /path/to/new_summary
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# Run folders as pinned in replication/validation/policy_table_inputs/index.json, plus the
# separate subsidy from calibration/runs/headline_revalidation_2022/validated_headline.json.
POLICIES = {
    "separate_wealth": ((0.030618034, 0.0, 0.40),
        "calibration/runs/theta_max_robustness_2022/financing/v2_bf8c109fc300/15d6fe146f961036_c0817307"),
    "separate_subsidy": ((0.0, -0.13618034, 0.40),
        "calibration/runs/theta_max_robustness_2022/financing/v2_4c477e22cbc6/72530e11b66db37a_5c8dd35c"),
    "joint_estate_40": ((0.07, -0.50, 0.40),
        "experiments/three_tax_2022/runs/estate/v2_fecede9519f7/0f17cb8e58562d19_8148a55d"),
    "joint_estate_zero": ((0.07, -0.50, 0.0),
        "experiments/policy_reoptimization_2022/runs/thesis/v2_fecede9519f7/54b48c5df64e6d40_35be0941"),
    "joint_subsidy_80": ((0.08, -0.80, 0.0),
        "experiments/robustness_gkkoc_2022/runs/partB_guard/v2_606ecb7a15de/d897e64637565c79_0d5d0f96"),
    "joint_subsidy_95": ((0.09, -0.95, 0.0),
        "experiments/robustness_gkkoc_2022/runs/partB_guard/v2_606ecb7a15de/b29768ab5f73dab8_daaff08f"),
    "joint_subsidy_95_w10": ((0.10, -0.95, 0.0),
        "experiments/robustness_gkkoc_2022/runs/partB_guard/v2_606ecb7a15de/2099fc18711dc078_1edd2ec7"),
}
BENCH_RATES = (0.0, 0.25, 0.40)
PCTS = ("p10", "p50", "p90", "p95", "p99")
NZ = 9


def run_folders(run_map: Path | None) -> dict[str, Path]:
    """Resolve a complete policy-to-run map within this model copy."""
    if run_map is None:
        paths = {name: rel for name, (_, rel) in POLICIES.items()}
    else:
        paths = json.loads(run_map.read_text())
        if not isinstance(paths, dict) or set(paths) != set(POLICIES):
            raise ValueError("run map must contain exactly these policy IDs: "
                             + ", ".join(POLICIES))
    folders = {}
    for name in POLICIES:
        value = paths[name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}: run folder must be a nonempty relative path")
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"{name}: run folder must stay inside the model directory")
        folder = (ROOT / relative).resolve()
        if not folder.is_relative_to(ROOT):
            raise ValueError(f"{name}: run folder resolves outside the model directory")
        if not folder.is_dir():
            raise ValueError(f"{name}: run folder does not exist: {relative}")
        folders[name] = folder
    return folders


def kv(path: Path, key: str) -> float:
    for line in path.read_text().splitlines():
        parts = line.split()
        if parts and parts[0] == key:
            return float(parts[-1])
    raise KeyError(f"{key} not in {path}")


def marginal_pct(path: Path) -> list[float]:
    for line in path.read_text().splitlines():
        parts = line.split()
        if parts and parts[0] == "Before_Tax":
            return [float(x) for x in parts[1:6]]
    raise KeyError(f"Before_Tax row not in {path}")


def constrained(path: Path) -> dict:
    by_z, total = {}, None
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit():
            by_z[int(parts[0])] = {"all_states": float(parts[1]), "fast_lane": float(parts[2]),
                                   "normal": float(parts[3])}
        elif parts and parts[0] == "Total":
            total = float(parts[1])
    if sorted(by_z) != list(range(1, NZ + 1)) or total is None:
        raise ValueError(f"unexpected layout in {path}")
    return {"by_ability": by_z, "total": total}


def mean_returns(path: Path) -> dict:
    """Wealth-weighted mean returns by ability, pre-tax and after-tax (in %)."""
    pre, post = {}, {}
    for line in path.read_text().splitlines():
        m = re.match(r"\s*Mean_Return_z\s+(\d+)(_AT)?\s+(\S+)", line)
        if m:
            (post if m.group(2) else pre)[int(m.group(1))] = 100 * float(m.group(3))
    if sorted(pre) != list(range(1, NZ + 1)) or sorted(post) != list(range(1, NZ + 1)):
        raise ValueError(f"unexpected layout in {path}")
    return {"pre_tax": pre, "after_tax": post}


def after_tax(m: float, rates) -> float:
    tau_w, tau_k, _ = rates
    return (1.0 - tau_k) * m - 100.0 * tau_w


def summarise_run(folder: Path, rates, experiment: bool) -> dict:
    if experiment:
        f = folder / "Joint_Tax"
        out, mg, con, ast = (f / "output_exp.txt", f / "Mg_Return_W_Pct_Exp.txt",
                             f / "Constrained_firms_stats_exp.txt", f / "Asset_Stats_exp.txt")
    else:
        out, mg, con, ast = (folder / "output.txt", folder / "Mg_Return_W_Pct_Bench.txt",
                             folder / "Constrained_firms_stats.txt", folder / "Asset_Stats_bench.txt")
    r, r_at = kv(out, "R"), kv(out, "R_AT")
    before = marginal_pct(mg)
    after = [after_tax(m, rates) for m in before]
    # Consistency: the lowest marginal return is r, and its after-tax value must match R_AT.
    if abs(before[0] - r) > 0.01 or abs(after[0] - r_at) > 0.01:
        raise ValueError(f"{folder}: p10 marginal return {before[0]:.4f}/{after[0]:.4f} "
                         f"does not match r {r:.4f}/{r_at:.4f}")
    return {"rates": list(rates), "r": r, "r_after_tax": r_at,
            "marginal_return_wealth_weighted": {"before_tax": dict(zip(PCTS, before)),
                                                "after_tax": dict(zip(PCTS, after))},
            "constrained_share_pct": constrained(con), "mean_return_by_ability_pct": mean_returns(ast),
            "sources": [str(p.relative_to(ROOT)) for p in (out, mg, con, ast)]}


def max_difference(a, b) -> float:
    """Largest absolute difference between matching numbers of two nested records."""
    if isinstance(a, dict):
        return max((max_difference(a[k], b[k]) for k in a), default=0.0)
    if isinstance(a, list):
        return max((max_difference(x, y) for x, y in zip(a, b)), default=0.0)
    return abs(a - b)


def check_rates(folder: Path, rates) -> None:
    rec = json.loads((folder / "result.json").read_text())
    got = (rec["tau_w"], rec["tau_k"], rec["tau_bq"])
    if rec.get("status") != "ok" or any(abs(a - b) > 1e-9 for a, b in zip(got, rates)):
        raise ValueError(f"{folder}: result.json has {got} ({rec.get('status')}), expected {rates}")


def write_md(res: dict, path: Path) -> None:
    names = ["benchmark", *POLICIES]
    lines = ["# Marginal returns and binding collateral constraints", "",
             "Saved reports only. Returns in %; marginal-return percentiles are wealth-weighted.",
             "After-tax marginal return = (1 − τk) × before-tax − τw.", "",
             "| Run | τw | τk | τb | r | r after tax | p50 after tax | p90 after tax | p99 after tax | "
             "Constrained, all households |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for n in names:
        x = res[n]
        a = x["marginal_return_wealth_weighted"]["after_tax"]
        tw, tk, tb = x["rates"]
        lines.append(f"| {n} | {100*tw:.2f}% | {100*tk:.2f}% | {100*tb:.0f}% | {x['r']:.2f} | "
                     f"{x['r_after_tax']:.2f} | {a['p50']:.2f} | {a['p90']:.2f} | {a['p99']:.2f} | "
                     f"{x['constrained_share_pct']['total']:.1f}% |")
    for state in ("fast_lane", "normal"):
        lines += ["", f"## Share constrained by ability, {state.replace('_', ' ')} state (%)", "",
                  "| Run | " + " | ".join(f"z{z}" for z in range(1, NZ + 1)) + " |",
                  "|---|" + "---:|" * NZ]
        for n in names:
            c = res[n]["constrained_share_pct"]["by_ability"]
            lines.append(f"| {n} | " + " | ".join(f"{c[z][state]:.0f}" for z in range(1, NZ + 1)) + " |")
    lines += ["", "## Wealth-weighted mean return by ability, after tax (%)", "",
              "| Run | " + " | ".join(f"z{z}" for z in range(1, NZ + 1)) + " |", "|---|" + "---:|" * NZ]
    for n in names:
        m = res[n]["mean_return_by_ability_pct"]["after_tax"]
        lines.append(f"| {n} | " + " | ".join(f"{m[z]:.2f}" for z in range(1, NZ + 1)) + " |")
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE, help="folder for results.json/results.md")
    ap.add_argument("--run-map", type=Path,
                    help="JSON mapping all seven policy IDs to model-relative run folders")
    args = ap.parse_args()
    try:
        folders = run_folders(args.run_map)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    res, bench = {}, None
    for name, (rates, _) in POLICIES.items():
        folder = folders[name]
        check_rates(folder, rates)
        res[name] = summarise_run(folder, rates, experiment=True)
        b = summarise_run(folder, BENCH_RATES, experiment=False)   # each run's own benchmark report
        b.pop("sources")
        if bench is None:
            bench = b
        elif max_difference(b, bench) > 1e-6:
            raise ValueError(f"{name}: benchmark report differs from the first policy's")
    res = {"benchmark": {**bench, "sources": ["benchmark reports beside each policy's Joint_Tax folder"]}, **res}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    write_md(res, args.out / "results.md")
    print((args.out / "results.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

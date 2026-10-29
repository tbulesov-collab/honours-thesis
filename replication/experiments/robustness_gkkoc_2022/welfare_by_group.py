#!/usr/bin/env python3
"""Who gains and who loses: welfare by age group and ability for the main policies.

Reads files the evaluator already wrote for each policy (no model run):

  CE_by_AgeGroup_z.txt  7 age groups x 9 ability nodes
  CE_by_age.txt         81 model ages
  CE_NEWBORN.txt        first line: newborn average
  frac_pos_welfare.txt  % of the benchmark population with a gain

The measure (GKK_Stats.f90, ~3220-3300) is the consumption-equivalent change of a
household that, in a given state (age, wealth, ability, labour type, shock, lane), is
moved from the benchmark into the new steady state, averaged with the *benchmark*
distribution within each group.  It compares steady states: it is not the welfare of
households alive during a transition.  The code's per-group "share with a gain" file
(frac_pos_welfare_by_agegroup_z.txt) divides a benchmark-weighted numerator by a
new-steady-state-weighted denominator, so it is not used here.

With a zero estate tax the code's formula is 0/0 at the terminal age (100) for the top
ability node, which makes that age, and the code's 75+/z9 group cell, NaN.  The group
cells are therefore rebuilt here from CE_by_age_z.txt with the benchmark's population
weights (size_by_age_z.txt), skipping only NaN ages; elsewhere the rebuilt cells must
match the code's CE_by_AgeGroup_z.txt (checked).

Model age a corresponds to age 19 + a (entry at 20, retirement at 64, MaxAge 81 = 100).
Ability nodes are ordered from lowest (z1) to highest (z9); nodes 1-4 lie below the
median.

    python3 experiments/robustness_gkkoc_2022/welfare_by_group.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SAVED = "calibration/runs/business_financing_2022/rn_reform"
RECAL = "experiments/model_spec_sensitivity_2022/recal/control/solves/6063645eb5a8"
AGE_GROUPS = ["20–24", "25–34", "35–44", "45–54", "55–64", "65–74", "75+"]
AGE_LIMIT = [0, 5, 15, 25, 35, 45, 55, 81]     # GKK_Stats.f90 age_limit
POLICIES = [   # (key, label, rates, benchmark)
    ("owt", "Optimal wealth tax (3.06%)", (0.030618034, 0.0, 0.40), SAVED),
    ("okit", "Optimal capital-income subsidy (−13.6%)", (0.0, -0.13618034, 0.40), SAVED),
    ("s5_1", "Three taxes, labour residual (4.91% / −30% / 0.1%)",
     (0.04909963880661732, -0.30, 0.0011395892219886016), SAVED),
    ("s5_4", "Best reported grid point (7% / −50% / 40%)", (0.07, -0.50, 0.40), SAVED),
    ("corner", "Best package found (7% / −50% / estate 0)", (0.07, -0.50, 0.0), SAVED),
    ("recal_owt", "Re-calibrated: wealth tax 3.06%", (0.030618034, 0.0, 0.40), RECAL),
    ("recal_edge", "Re-calibrated: best package (6% / −50% / estate 0)", (0.06, -0.50, 0.0), RECAL),
]


def find(rates, bench: str) -> dict | None:
    """Most recent feasible validated evaluation of these rates against this benchmark."""
    best = None
    for m in glob.glob(str(ROOT / "calibration/runs/**/v2_*/manifest.json"), recursive=True) + \
            glob.glob(str(ROOT / "experiments/**/v2_*/manifest.json"), recursive=True):
        man = json.loads(Path(m).read_text())
        if man.get("fixed_labor") or not man["benchmark"].endswith(bench):
            continue
        for r in glob.glob(str(Path(m).parent / "*/result.json")):
            x = json.loads(Path(r).read_text())
            if x.get("status") != "ok" or not x.get("feasible"):
                continue
            if all(abs(a - b) < 1e-9 for a, b in zip((x["tau_w"], x["tau_k"], x["tau_bq"]), rates)):
                d = ROOT / x["result_directory"]
                if (d / "CE_by_AgeGroup_z.txt").exists():
                    t = Path(r).stat().st_mtime
                    if best is None or t > best[0]:
                        best = (t, x, d)
    return None if best is None else {"result": best[1], "dir": best[2]}


def numbers(path: Path) -> np.ndarray:
    return np.array([[float(v) for v in line.split()] for line in path.read_text().splitlines() if line.strip()])


def main() -> int:
    out, lines = {}, ["# Who gains and who loses: welfare by age group and ability", "",
                      "Consumption-equivalent welfare change (%) of moving a household, in its benchmark "
                      "state, into the new steady state; averaged within each group with the benchmark "
                      "distribution.  Steady-state comparison, not a transition.  Ability z1 (lowest) to "
                      "z9 (highest); z1–z4 are below the median.", ""]
    summary = ["| Policy | Newborn CE2 | Newborn (this measure) | Share of population gaining | "
               "Largest loss (group) | Largest gain (group) |",
               "|---|---:|---:|---:|---|---|"]
    for key, label, rates, bench in POLICIES:
        hit = find(rates, bench)
        if hit is None:
            summary.append(f"| {label} | — | missing | | | |")
            continue
        d, r = hit["dir"], hit["result"]
        saved = numbers(d / "CE_by_AgeGroup_z.txt")             # 7 x 9, code's own
        by_age_z = numbers(d / "CE_by_age_z.txt")               # 81 x 9
        w = numbers(ROOT / bench / "size_by_age_z.txt")         # 81 x 9, benchmark
        ok = ~np.isnan(by_age_z)
        grid = np.array([[np.sum((w * np.where(ok, by_age_z, 0))[a:b, z]) / np.sum((w * ok)[a:b, z])
                          for z in range(9)] for a, b in zip(AGE_LIMIT[:-1], AGE_LIMIT[1:])])
        good = ~np.isnan(saved)
        if np.abs(grid[good] - saved[good]).max() > 0.05:
            raise SystemExit(f"{key}: rebuilt group cells differ from CE_by_AgeGroup_z.txt")
        nan_ages = sorted({int(a) + 20 for a, _ in np.argwhere(~ok)})
        by_age = np.sum(w * np.where(ok, by_age_z, 0), axis=1) / np.sum(w * ok, axis=1)
        pop_losing = float(np.sum(w * ok * (by_age_z < 0)) / np.sum(w * ok))
        newborn = float(numbers(d / "CE_NEWBORN.txt")[0, 0])
        share = float(numbers(d / "frac_pos_welfare.txt")[0, 0])
        lo, hi = np.unravel_index(grid.argmin(), grid.shape), np.unravel_index(grid.argmax(), grid.shape)
        out[key] = {"label": label, "rates": list(rates), "benchmark": bench,
                    "result_directory": str(d.relative_to(ROOT)), "ce2_newborn": r["ce2_newborn"],
                    "newborn_ce": newborn, "share_gaining": share, "nan_ages_excluded": nan_ages,
                    "pop_share_in_losing_age_z_cells": pop_losing,
                    "by_agegroup_z": grid.tolist(), "by_age": by_age.tolist()}
        summary.append(f"| {label} | {r['ce2_newborn']:.2f} | {newborn:.2f} | {share:.1f}% | "
                       f"{grid[lo]:.1f} (age {AGE_GROUPS[lo[0]]}, z{lo[1]+1}) | "
                       f"{grid[hi]:.1f} (age {AGE_GROUPS[hi[0]]}, z{hi[1]+1}) |")
        lines += [f"## {label}", "", "| Age \\ ability | " + " | ".join(f"z{i}" for i in range(1, 10)) + " |",
                  "|---|" + "---:|" * 9]
        for g, row in zip(AGE_GROUPS, grid):
            lines.append(f"| {g} | " + " | ".join(f"{v:.1f}" for v in row) + " |")
        lines.append("")
    lines = lines[:4] + ["## Summary", "", *summary, "",
                         "Shares use the benchmark distribution.  With estate tax 0, age 100 (top "
                         "ability) is excluded: the code's formula is 0/0 there.", ""] + lines[4:]
    (HERE / "welfare_by_group.md").write_text("\n".join(lines) + "\n")
    (HERE / "welfare_by_group.json").write_text(json.dumps(out, indent=1) + "\n")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib unavailable; tables written, figures skipped")
    else:
        keys = [k for k in ("owt", "okit", "s5_4", "corner") if k in out]
        lim = max(abs(np.array(out[k]["by_agegroup_z"])).max() for k in keys)
        fig, axes = plt.subplots(1, len(keys), figsize=(4.2 * len(keys), 4), sharey=True,
                                 constrained_layout=True)
        for ax, k in zip(np.atleast_1d(axes), keys):
            im = ax.imshow(np.array(out[k]["by_agegroup_z"]), cmap="RdBu", vmin=-lim, vmax=lim, aspect="auto")
            ax.set_title(out[k]["label"], fontsize=9)
            ax.set_xticks(range(9), [f"z{i}" for i in range(1, 10)], fontsize=8)
            ax.set_yticks(range(7), AGE_GROUPS, fontsize=8)
            ax.set_xlabel("Ability (low → high)", fontsize=8)
        np.atleast_1d(axes)[0].set_ylabel("Age group", fontsize=8)
        fig.colorbar(im, ax=axes, shrink=0.85, label="Welfare change (%)")
        fig.savefig(HERE / "welfare_by_group.png", dpi=200)

        fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
        for k in ("owt", "okit", "s5_4", "corner"):
            if k in out:
                ax.plot(np.arange(len(out[k]["by_age"])) + 20, out[k]["by_age"], label=out[k]["label"])
        ax.axhline(0, color="grey", lw=0.8)
        ax.axvline(64, color="grey", lw=0.8, ls=":")
        ax.set_xlabel("Age")
        ax.set_ylabel("Welfare change (%)")
        ax.legend(fontsize=7)
        fig.savefig(HERE / "welfare_by_age.png", dpi=200)
    print("\n".join(lines[:4 + len(summary) + 6]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

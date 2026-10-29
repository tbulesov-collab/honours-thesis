#!/usr/bin/env python3
"""Render the thesis's two-panel estate-tax comparison from released results.

No model execution. --check-data reads and checks inputs without creating files.
The manuscript's inline PGFPlots representation is not needed by this script.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_data():
    rep = ROOT / "replication"
    with (rep / "calibration/runs/estate_tax_grid_2022/grid_results.json").open() as fh:
        separate = [x["result"] for x in json.load(fh)["points"]]
    with (rep / "experiments/three_tax_2022/results.json").open() as fh:
        joint = json.load(fh)["estate_series"]
    separate.sort(key=lambda x: x["tau_bq"])
    joint.sort(key=lambda x: x["tau_bq"])
    if len(separate) != 7 or len(joint) != 5:
        raise ValueError("Expected seven separate-tax and five joint-tax estate points")
    for name, rows, expected in [("separate", separate, (12.21, 6.08, 48.28, 42.35)),
                                 ("joint", joint, (23.54, 19.86, 60.15, 56.71))]:
        for row in rows:
            if not row["feasible"]:
                raise ValueError(f"Infeasible {name} point")
        values = (rows[0]["ce2_newborn"], rows[-1]["ce2_newborn"],
                  100*rows[0]["top1_wealth_share"], 100*rows[-1]["top1_wealth_share"])
        if [round(x, 2) for x in values] != list(expected):
            raise ValueError(f"{name}: endpoint values differ from the thesis")
    return {"separate": separate, "joint": joint}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-data", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "output/figures")
    args = parser.parse_args()
    data = load_data()
    if args.check_data:
        print("PASS: two estate-comparison series (7 and 5 points); no model run or figure write.")
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.3), layout="constrained")
    for name, color, marker, label in [("separate", "#2a78d6", "o", "Wealth tax 3.06%, capital-income tax 0"),
                                       ("joint", "#eb6834", "s", "Wealth tax 7%, capital-income tax −50%")]:
        rows = data[name]
        xs = [100*r["tau_bq"] for r in rows]
        axes[0].plot(xs, [r["ce2_newborn"] for r in rows], color=color, marker=marker,
                     markersize=3.5, linewidth=1.2, label=label)
        axes[1].plot(xs, [100*r["top1_wealth_share"] for r in rows], color=color,
                     marker=marker, markersize=3.5, linewidth=1.2)
    for ax in axes:
        ax.set_xlabel("Estate tax (%)")
        ax.set_xticks(range(0, 61, 10))
        ax.grid(axis="y", color="#e1e0d9", linewidth=.6)
        ax.set_axisbelow(True)
    axes[0].set_title("(a) Newborn welfare")
    axes[0].set_ylabel("Newborn CE2 (%)")
    axes[1].set_title("(b) Wealth concentration")
    axes[1].set_ylabel("Top 1% wealth share (%)")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center",
               frameon=False, fontsize=8)
    args.out.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(args.out / f"fig_estate_comparison.{suffix}", dpi=180)
    plt.close(fig)
    print(f"Wrote estate comparison to {args.out}; saved results only.")


if __name__ == "__main__":
    main()

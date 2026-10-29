#!/usr/bin/env python3
"""Who does the estate tax help?  Group incidence and alternative welfare measures.

Reads evaluator output that is already saved in the active model tree; it never runs
the model.  For every policy it uses the files the evaluator wrote:

  CE_by_age_z.txt       81 ages x 9 ability nodes, consumption-equivalent change (%)
  CE_by_AgeGroup_z.txt  the code's own 7 x 9 group cells (used only as a check)
  frac_pos_welfare.txt  % of the benchmark population (all household states) with CE >= 0
  size_by_age_z.txt     benchmark population weights (from the benchmark folder)

Group cells are rebuilt from CE_by_age_z.txt with the benchmark weights, skipping NaN
ages (with a zero estate tax the code's formula is 0/0 at age 100 for the top ability
node), exactly as experiments/robustness_gkkoc_2022/welfare_by_group.py does.  Where
the code's own cell is defined, the rebuilt cell must match it to 0.05.

Differences between two policies are differences between their consumption-equivalent
changes relative to the same benchmark (percentage points).  They show where removing
the estate tax raises or lowers measured welfare; they are not themselves a
consumption-equivalent of moving between the two policies.

Policies
  sweep            wealth tax 3.062%, capital-income tax 0, estate tax 0%..60% (saved benchmark)
  joint (reported) 7% wealth tax, -50% capital-income tax, estate tax 40% and 0
  recal pairs      the 18 matched estate-40 / estate-0 grid points, recalibrated parameters

    python3 output/figures/estate_incidence.py --check-data   # compute and print; writes nothing
    python3 output/figures/estate_incidence.py                # writes the files below

Writes to output/figures/: estate_incidence.json, estate_incidence.md,
estate_incidence_table.tex and fig_estate_incidence.pdf/.png.
"""
import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

SAVED = "calibration/runs/business_financing_2022/rn_reform"
RECAL = "experiments/model_spec_sensitivity_2022/recal/control/solves/6063645eb5a8"
AGE_LABELS = ["20-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
AGE_LIMIT = [0, 5, 15, 25, 35, 45, 55, 81]  # GKK_Stats.f90 age_limit
LOW = list(range(4))  # ability nodes 1-4 lie below the median
TOP = [8]  # highest ability node

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
NEUTRAL = "#f0efec"
DIV_BLUE = ["#b7d3f6", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
DIV_RED = ["#f4c2be", "#ea9a93", "#d75853", "#9e3432", "#621b1a"]


# --------------------------------------------------------------------------- loading
def thesis_root(start):
    for p in [start, *start.parents]:
        if (p / "replication" / "calibration").is_dir():
            return p
    sys.exit("Could not find the thesis workspace root. Use --model-root.")


def num(path):
    with open(path, encoding="utf8") as fh:
        return np.array([[float(v) for v in line.split()] for line in fh if line.strip()])


def rebuild(ce, w):
    ok = ~np.isnan(ce)
    cew = np.where(ok, ce, 0.0)
    grid = np.full((7, 9), np.nan)
    for g, (a, b) in enumerate(zip(AGE_LIMIT[:-1], AGE_LIMIT[1:])):
        top, bottom = (w[a:b] * cew[a:b]).sum(axis=0), (w[a:b] * ok[a:b]).sum(axis=0)
        grid[g] = np.where(bottom > 0, top / np.where(bottom > 0, bottom, 1.0), np.nan)
    return grid


def wmean(ce, w, cols):
    ok = ~np.isnan(ce[:, cols])
    return float((w[:, cols] * np.where(ok, ce[:, cols], 0.0)).sum() / (w[:, cols] * ok).sum())


def measures(model, result, w):
    d = model / result["result_directory"]
    ce = num(d / "CE_by_age_z.txt")
    grid = rebuild(ce, w)
    code = num(d / "CE_by_AgeGroup_z.txt")
    good = ~np.isnan(code)
    gap = float(np.abs(grid[good] - code[good]).max())
    assert gap <= 0.05, f"{d}: rebuilt group cells differ from the code's by {gap:.3f}"
    lo = np.unravel_index(np.nanargmin(grid), grid.shape)
    return {
        "tau_w": result["tau_w"], "tau_k": result["tau_k"], "tau_bq": result["tau_bq"],
        "ce2_newborn": result["ce2_newborn"], "ce2_population": result["ce2_population"],
        "top1_wealth_share": 100 * result["top1_wealth_share"],
        "share_nonneg": float(num(d / "frac_pos_welfare.txt")[0, 0]),
        "worst": {"value": float(grid[lo]), "age": AGE_LABELS[lo[0]], "ability": int(lo[1]) + 1},
        "low_ability_mean": wmean(ce, w, LOW), "top_ability_mean": wmean(ce, w, TOP),
        "grid": grid.tolist(), "_ce": ce, "result_directory": result["result_directory"],
    }


def incidence(m40, m0, w):
    ok = ~np.isnan(m40["_ce"]) & ~np.isnan(m0["_ce"])
    helped = float((w * ok * (m0["_ce"] > m40["_ce"])).sum() / (w * ok).sum())
    diff = np.array(m0["grid"]) - np.array(m40["grid"])
    lo, hi = np.unravel_index(np.nanargmin(diff), diff.shape), np.unravel_index(np.nanargmax(diff), diff.shape)
    return {"newborn_pp": m0["ce2_newborn"] - m40["ce2_newborn"],
            "population_pp": m0["ce2_population"] - m40["ce2_population"],
            "share_nonneg_pp": m0["share_nonneg"] - m40["share_nonneg"],
            "low_ability_pp": m0["low_ability_mean"] - m40["low_ability_mean"],
            "top_ability_pp": m0["top_ability_mean"] - m40["top_ability_mean"],
            "top1_pp": m0["top1_wealth_share"] - m40["top1_wealth_share"],
            "helped_mass": 100 * helped, "diff_grid": diff.tolist(),
            "most_hurt": {"value": float(diff[lo]), "age": AGE_LABELS[lo[0]], "ability": int(lo[1]) + 1},
            "most_helped": {"value": float(diff[hi]), "age": AGE_LABELS[hi[0]], "ability": int(hi[1]) + 1}}


def load(model):
    wS, wR = num(model / SAVED / "size_by_age_z.txt"), num(model / RECAL / "size_by_age_z.txt")
    d = {"sweep": []}
    for f in sorted(glob.glob(str(model / "calibration/runs/estate_tax_grid_2022/points/tau_bq_*.json"))):
        with open(f, encoding="utf8") as fh:
            d["sweep"].append(measures(model, json.load(fh)["result"], wS))
    d["sweep"].sort(key=lambda m: m["tau_bq"])
    by_bq = {round(m["tau_bq"], 4): m for m in d["sweep"]}
    d["sweep_incidence"] = incidence(by_bq[0.4], by_bq[0.0], wS)

    with open(model / "calibration/runs/headline_revalidation_2022/validated_headline.json", encoding="utf8") as fh:
        s54 = json.load(fh)["points"]["s5_4"]
    with open(model / "experiments/policy_reoptimization_2022/runs/grid_points.json", encoding="utf8") as fh:
        grid = [p for p in json.load(fh) if p.get("status") == "ok"]
    corner = next(p for p in grid if p["calibration"] == "thesis" and p["group"] == "grid_bq0"
                  and abs(p["tau_w"] - 0.07) < 1e-9 and abs(p["tau_k"] + 0.5) < 1e-9)
    d["joint40"], d["joint0"] = measures(model, s54, wS), measures(model, corner, wS)
    d["joint_incidence"] = incidence(d["joint40"], d["joint0"], wS)

    key = lambda p: (round(p["tau_w"], 4), round(p["tau_k"], 4))
    r40 = {key(p): p for p in grid if p["calibration"] == "recal" and p["group"] == "grid_bq40"}
    r0 = {key(p): p for p in grid if p["calibration"] == "recal" and p["group"] == "grid_bq0"}
    d["recal_pairs"] = []
    for k in sorted(set(r40) & set(r0)):
        a, b = measures(model, r40[k], wR), measures(model, r0[k], wR)
        inc = incidence(a, b, wR)
        d["recal_pairs"].append({"tau_w": k[0], "tau_k": k[1], "share_nonneg_40": a["share_nonneg"],
                                 "share_nonneg_0": b["share_nonneg"],
                                 **{x: inc[x] for x in ("newborn_pp", "population_pp", "share_nonneg_pp",
                                                        "low_ability_pp", "top_ability_pp", "helped_mass")}})
    return d


def check(d):
    def near(a, b, tol, what):
        assert abs(a - b) <= tol, f"{what}: {a} vs expected {b}"
    s = {round(m["tau_bq"], 4): m for m in d["sweep"]}
    assert len(d["sweep"]) == 7, "estate sweep should have 7 points"
    near(s[0.0]["ce2_newborn"], 12.213, 0.002, "sweep, estate 0")
    near(s[0.4]["ce2_newborn"], 8.4913, 0.001, "sweep, estate 40")
    near(s[0.6]["ce2_newborn"], 6.076, 0.002, "sweep, estate 60")
    near(s[0.4]["share_nonneg"], 60.4747, 0.01, "share non-negative at the wealth-tax candidate")
    near(d["joint40"]["ce2_newborn"], 19.865, 0.001, "joint package, estate 40")
    near(d["joint0"]["ce2_newborn"], 23.5385, 0.001, "joint package, estate 0")
    near(d["joint0"]["share_nonneg"], 67.117, 0.01, "share non-negative, best package")
    assert len(d["recal_pairs"]) == 18, "there should be 18 recalibrated pairs"
    gains = [p["newborn_pp"] for p in d["recal_pairs"]]
    assert 3.1 < min(gains) and max(gains) < 4.2, f"recalibrated estate gains outside 3.2-4.1: {min(gains)}, {max(gains)}"
    print("All checks passed (values match the thesis and welfare_by_group.json).")


# --------------------------------------------------------------------------- reporting
def summary(d):
    out = ["Estate sweep at the wealth-tax candidate (3.062%, capital-income tax 0)",
           "estate  newborn  population  share>=0  worst-off group      low-ability  top-ability  top1%"]
    for m in d["sweep"]:
        w = m["worst"]
        out.append(f"{100*m['tau_bq']:5.0f}%  {m['ce2_newborn']:7.2f}  {m['ce2_population']:10.2f}  "
                   f"{m['share_nonneg']:8.1f}  {w['value']:6.1f} ({w['age']}, z{w['ability']})  "
                   f"{m['low_ability_mean']:11.2f}  {m['top_ability_mean']:11.2f}  {m['top1_wealth_share']:5.1f}")
    for lab, m in (("joint 7%/-50%, estate 40", d["joint40"]), ("joint 7%/-50%, estate 0 ", d["joint0"])):
        w = m["worst"]
        out.append(f"{lab}: newborn {m['ce2_newborn']:.2f}, population {m['ce2_population']:.2f}, "
                   f"share>=0 {m['share_nonneg']:.1f}, worst {w['value']:.1f} ({w['age']}, z{w['ability']}), "
                   f"low-ability {m['low_ability_mean']:.2f}, top-ability {m['top_ability_mean']:.2f}, top1 {m['top1_wealth_share']:.1f}")
    for lab, inc in (("Removing the estate tax at the wealth-tax candidate", d["sweep_incidence"]),
                     ("Removing the estate tax at the joint package", d["joint_incidence"])):
        out.append(f"{lab}: newborn {inc['newborn_pp']:+.2f} pp, population {inc['population_pp']:+.2f} pp, "
                   f"share>=0 {inc['share_nonneg_pp']:+.1f} pp, low-ability {inc['low_ability_pp']:+.2f} pp, "
                   f"top-ability {inc['top_ability_pp']:+.2f} pp, top1 {inc['top1_pp']:+.1f} pp, "
                   f"benchmark mass in age-ability cells helped {inc['helped_mass']:.1f}%, "
                   f"most hurt {inc['most_hurt']['value']:+.1f} ({inc['most_hurt']['age']}, z{inc['most_hurt']['ability']}), "
                   f"most helped {inc['most_helped']['value']:+.1f} ({inc['most_helped']['age']}, z{inc['most_helped']['ability']})")
    rp = d["recal_pairs"]
    rng = lambda k: (min(p[k] for p in rp), max(p[k] for p in rp))
    out.append("Recalibrated 18 pairs (estate 0 minus estate 40): " + ", ".join(
        f"{k} {a:+.2f}..{b:+.2f}" for k, (a, b) in ((k, rng(k)) for k in
        ("newborn_pp", "population_pp", "share_nonneg_pp", "low_ability_pp", "top_ability_pp", "helped_mass"))))
    return "\n".join(out)


def latex_table(d):
    def worst(m):
        w = m["worst"]
        return f"${w['value']:.1f}$ ({w['age'].replace('-', '--')}, {w['ability']})"

    def row(label, m):
        return (f"{label} & ${m['ce2_newborn']:.2f}$ & ${m['ce2_population']:.2f}$ & ${m['share_nonneg']:.1f}$ & "
                f"{worst(m)} & ${m['low_ability_mean']:.2f}$ & ${m['top_ability_mean']:.2f}$ \\\\")

    rows = [row(f"${100*m['tau_bq']:.0f}\\%$", m) for m in d["sweep"]]
    lines = [
        "% Generated by output/figures/estate_incidence.py from saved evaluator output. Do not edit numbers by hand.",
        "\\begin{table}[htbp]", "\\centering",
        "\\caption{Estate Taxation under Alternative Welfare Measures}", "\\label{tab:estate_measures}",
        "\\footnotesize", "\\setlength{\\tabcolsep}{3pt}",
        "\\begin{tabular}{lrrrlrr}", "\\toprule",
        "Estate tax & Newborn CE2 & Population CE2 & Share $\\ge 0$ & Worst-off group & Abilities 1--4 & Ability 9 \\\\",
        "\\midrule",
        "\\multicolumn{7}{l}{\\textit{Wealth tax $3.062\\%$, no capital-income tax}} \\\\", *rows, "\\midrule",
        "\\multicolumn{7}{l}{\\textit{Wealth tax $7\\%$, capital-income tax $-50\\%$}} \\\\",
        row("$40\\%$", d["joint40"]), row("$0\\%$", d["joint0"]),
        "\\bottomrule", "\\end{tabular}", "\\par\\vspace{0.3em}",
        "{\\footnotesize \\textit{Notes:} All entries are stationary consumption-equivalent changes (\\%) relative to the "
        "saved benchmark, except the share column. Share $\\ge 0$ is the percentage of all households, weighted by the "
        "benchmark distribution, whose welfare change is zero or positive. Worst-off group gives the lowest age--ability "
        "cell average with its age group and ability group (1 = lowest). Abilities 1--4 and Ability 9 are "
        "benchmark-weighted averages over all ages for the below-median and the highest ability groups. The labour tax "
        "adjusts to the revenue requirement in every row.\\par}",
        "\\end{table}"]
    return "\n".join(lines) + "\n"


def figure(d, out, png):
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, Normalize
    mpl.rcParams.update({
        "font.family": "serif", "font.serif": ["cmr10", "DejaVu Serif"], "mathtext.fontset": "cm",
        "axes.formatter.use_mathtext": True, "axes.unicode_minus": False, "font.size": 8.5,
        "text.color": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK2,
        "pdf.fonttype": 42, "figure.facecolor": "white", "savefig.facecolor": "white"})
    cmap = LinearSegmentedColormap.from_list("div_blue_red", DIV_RED[::-1] + [NEUTRAL] + DIV_BLUE, N=256)
    panels = [(d["sweep_incidence"], "(a) Wealth tax 3.06%, no capital-income tax"),
              (d["joint_incidence"], r"(b) Wealth tax 7%, capital-income tax $-50\%$")]
    vmax = float(np.ceil(max(np.nanmax(np.abs(p["diff_grid"])) for p, _ in panels) / 2.0) * 2.0)
    norm = Normalize(-vmax, vmax)
    fig, axes = plt.subplots(1, 2, figsize=(6.1, 3.3))
    fig.subplots_adjust(left=0.08, right=0.995, top=0.82, bottom=0.27, wspace=0.07)
    for i, (ax, (inc, title)) in enumerate(zip(axes, panels)):
        z = np.array(inc["diff_grid"], dtype=float)
        ax.imshow(z, cmap=cmap, norm=norm, aspect="auto", interpolation="nearest")
        ax.set_xticks(range(9))
        ax.set_xticklabels([str(k) for k in range(1, 10)], fontsize=7)
        ax.set_yticks(range(7))
        ax.set_yticklabels(AGE_LABELS if i == 0 else [], fontsize=7)
        ax.set_xticks([k - 0.5 for k in range(10)], minor=True)
        ax.set_yticks([k - 0.5 for k in range(8)], minor=True)
        ax.grid(which="minor", color="white", lw=1.2)
        ax.tick_params(which="both", length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        for r in range(7):
            for c in range(9):
                v = z[r, c]
                if np.isnan(v):
                    ax.text(c, r, "n/a", ha="center", va="center", fontsize=5.5, color=MUTED)
                    continue
                rgb = cmap(norm(v))[:3]
                lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
                txt = "0.0" if abs(v) < 0.05 else rf"${v:.1f}$"
                ax.text(c, r, txt, ha="center", va="center", fontsize=6, color="white" if lum < 0.40 else INK)
        ax.set_title(f"{title}\nnewborn {inc['newborn_pp']:+.1f} pp; share with gains {inc['share_nonneg_pp']:+.1f} pp",
                     loc="left", fontsize=7.5, linespacing=1.25)
        ax.set_xlabel("Ability group (1 = lowest)", fontsize=7.5)
    axes[0].set_ylabel("Age group", fontsize=7.5)
    cax = fig.add_axes([0.25, 0.11, 0.5, 0.02])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    ticks = [-vmax, -vmax / 2, 0, vmax / 2, vmax]
    cb.set_ticks(ticks)
    cb.set_ticklabels([rf"${t:g}$" if t < 0 else f"{t:g}" for t in ticks])
    cb.ax.tick_params(length=2, width=0.6, labelsize=7)
    cb.outline.set_visible(False)
    cb.set_label("Change from removing the 40% estate tax (pp): blue = better without it, red = worse",
                 fontsize=7.5, labelpad=3)
    fig.savefig(out / "fig_estate_incidence.pdf")
    if png:
        fig.savefig(out / "fig_estate_incidence.png", dpi=200)


def strip(x):
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if not k.startswith("_")}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-root", type=Path, help="active model tree (default: the workspace's Wealth Tax - Replica)")
    ap.add_argument("--check-data", action="store_true", help="compute, check and print; write nothing")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()
    root = thesis_root(Path(__file__).resolve().parent)
    model = (args.model_root or root / "Guvenen Wealth Tax Paper Code copy" / "Wealth Tax - Replica").resolve()
    d = load(model)
    check(d)
    text = summary(d)
    print(text)
    if args.check_data:
        return
    out = root / "output" / "figures"
    (out / "estate_incidence.json").write_text(json.dumps(strip(d), indent=1) + "\n", encoding="utf8")
    (out / "estate_incidence.md").write_text("# Estate-tax incidence and alternative welfare measures\n\n```\n"
                                             + text + "\n```\n", encoding="utf8")
    (out / "estate_incidence_table.tex").write_text(latex_table(d), encoding="utf8")
    figure(d, out, not args.no_png)
    print(f"Wrote estate_incidence.json/.md, estate_incidence_table.tex and fig_estate_incidence.pdf to {out}")


if __name__ == "__main__":
    main()

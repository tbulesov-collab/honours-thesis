#!/usr/bin/env python3
"""Thesis figures drawn from the saved result files.

Reads only saved JSON/CSV under replication/ and writes PDF (vector) and PNG
(preview) files to output/figures/ (or --out). It never runs the model. Panel (b)
of the welfare surface needs Part D (partD_all.json) in the snapshot; --partd
points to another copy.

    python3 scripts/thesis_figures/make_thesis_figures.py --check-data   # load + assert, no plots
    python3 scripts/thesis_figures/make_thesis_figures.py                # all four figures
    python3 scripts/thesis_figures/make_thesis_figures.py --only surface,estate

Figures
  fig_welfare_surface  newborn welfare against the capital-income subsidy, by wealth tax
  fig_flat_regions     the flat capital-income-tax plateau and the wealth-tax hump
  fig_estate_sweep     estate-tax sweep at the wealth-tax candidate
  fig_group_welfare    who gains and loses, by age group and entrepreneurial ability

Colour: categorical slots 1-2 and the ordinal blue ramp validated with the dataviz
validator on a white surface (no FAIL; aqua contrast WARN avoided by not using it).
The diverging heat map pairs the blue ramp with a red arm matched to it in OKLCH
lightness and hue 25 degrees, around the neutral #f0efec.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, TINT = "#e1e0d9", "#c3c2b7", "#f4f3f0"
BLUE, ORANGE = "#2a78d6", "#eb6834"
ORDINAL_BLUE = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]  # steps 250/350/450/550/700 (--ordinal passes; 6 steps cannot)
NEUTRAL = "#f0efec"
DIV_BLUE = ["#b7d3f6", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # steps 150/250/400/550/700
DIV_RED = ["#f4c2be", "#ea9a93", "#d75853", "#9e3432", "#621b1a"]  # same OKLCH L and C, hue 25 degrees
AGE_LABELS = ["20-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]


# --------------------------------------------------------------------------- data
def find_root(start):
    for p in [start, *start.parents]:
        if (p / "replication" / "calibration").is_dir():
            return p
    sys.exit("Could not find the workspace root (a folder containing replication/calibration). Use --root.")


def jload(rep, rel):
    with open(rep / rel, encoding="utf8") as fh:
        return json.load(fh)


def by_wealth_tax(points):
    """[(tau_w, tau_k, ce2)] -> {tau_w in %: [(subsidy in %, ce2)]}, first value wins on duplicates."""
    seen, out = set(), {}
    for tw, tk, ce in points:
        key = (round(tw * 100, 3), round(-tk * 100, 3))
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(key[0], []).append((key[1], ce))
    return {k: sorted(v) for k, v in out.items()}


def load_data(root, partd_file=None):
    rep = root / "replication"
    ok = lambda p: p.get("status") == "ok"
    d = {}

    with open(rep / "calibration/runs/subsidy_cap_grid_2022/all_results.csv", encoding="utf8") as fh:
        rows = list(csv.DictReader(fh))
    d["surface40"] = by_wealth_tax(
        [(float(r["tau_w"]), float(r["tau_k"]), float(r["ce2_newborn"]))
         for r in rows if abs(float(r["tau_bq"]) - 0.4) < 1e-9])

    grid = jload(rep, "experiments/policy_reoptimization_2022/runs/grid_points.json")
    edge = jload(rep, "experiments/policy_reoptimization_2022/runs/edge_points.json")
    b3 = jload(rep, "experiments/robustness_gkkoc_2022/runs/partB_b3.json")
    pick = lambda pts, cal, grp: [(p["tau_w"], p["tau_k"], p["ce2_newborn"])
                                  for p in pts if p["calibration"] == cal and p["group"] == grp and ok(p)]
    partd_file = partd_file or rep / "experiments/robustness_gkkoc_2022/runs/partD_all.json"
    if not partd_file.exists():
        sys.exit(f"Part D results not found: {partd_file}\nPass --partd with the path to partD_all.json.")
    with open(partd_file, encoding="utf8") as fh:
        partd = json.load(fh)
    ext = [(v["tau_w"], v["tau_k"], v["ce2_newborn"]) for v in [*b3.values(), *partd.values()]
           if ok(v) and abs(v["tau_bq"]) < 1e-9]
    d["surface0"] = by_wealth_tax(pick(grid, "thesis", "grid_bq0") + pick(edge, "thesis", "edge") + ext)
    # wealth-tax slices beyond the original limit (Parts B and D), estate 0: {subsidy %: [(tau_w %, ce2)]}
    d["hump_relaxed"] = {s: sorted((tw, ce) for tw, pts in d["surface0"].items() for x, ce in pts if x == s)
                         for s in (80.0, 95.0)}

    # wealth-tax hump along tau_k = -50%, estate 0, both calibrations
    d["hump"] = {}
    for cal in ("thesis", "recal"):
        pts = [p for p in pick(grid, cal, "grid_bq0") if abs(p[1] + 0.5) < 1e-9] + pick(edge, cal, "edge")
        seen, series = set(), []
        for tw, _, ce in pts:
            if round(tw, 6) in seen:
                continue
            seen.add(round(tw, 6))
            series.append((tw * 100, ce))
        d["hump"][cal] = sorted(series)

    fine = jload(rep, "calibration/runs/okit_fine_grid_2022/grid_results.json")
    d["okit"] = sorted((-p["value"] * 100, p["result"]["ce2_newborn"]) for p in fine["points"] if ok(p))
    d["okit_noise"] = fine["noise_pp"]
    head = jload(rep, "calibration/runs/headline_revalidation_2022/validated_headline.json")["points"]["okit"]
    d["okit_reported"] = (-head["tau_k"] * 100, head["ce2_newborn"])

    est = []
    for f in sorted((rep / "calibration/runs/estate_tax_grid_2022/points").glob("tau_bq_*.json")):
        r = json.load(open(f, encoding="utf8"))["result"]
        est.append((r["tau_bq"] * 100, r["ce2_newborn"], r["ce2_population"], r["top1_wealth_share"] * 100))
    d["estate"] = sorted(est)

    grp = jload(rep, "experiments/robustness_gkkoc_2022/welfare_by_group.json")
    d["groups"] = {k: grp[k] for k in ("owt", "okit", "corner")}
    return d


def check_data(d):
    def near(a, b, tol, what):
        assert abs(a - b) <= tol, f"{what}: {a} vs expected {b}"
        print(f"  ok  {what}: {a:.4f}")

    print("Data checks against the figures quoted in the thesis")
    assert sum(len(v) for v in d["surface40"].values()) == 18, "estate-40 grid should have 18 points"
    near(dict(d["surface40"][7.0])[50.0], 19.8497, 0.02, "estate-40 grid, 7% / -50%")
    near(dict(d["surface0"][7.0])[50.0], 23.5385, 0.01, "estate-0, 7% / -50%")
    near(dict(d["surface0"][8.0])[80.0], 28.713, 0.01, "estate-0 extended, 8% / -80%")
    near(dict(d["surface0"][8.0])[95.0], 30.704, 0.01, "estate-0 extended, 8% / -95%")
    near(dict(d["surface0"][9.0])[95.0], 31.007, 0.01, "estate-0 extended, 9% / -95% (best tested)")
    near(max(c for _, c in d["hump"]["thesis"]), 23.5385, 0.01, "reported hump maximum")
    near(max(c for _, c in d["hump"]["recal"]), 20.73, 0.01, "recalibrated hump maximum")
    assert len(d["hump"]["thesis"]) == 8 and len(d["hump"]["recal"]) == 8, "hump series should have 8 points each"
    assert [tw for tw, _ in d["hump_relaxed"][80.0]] == [7.0, 8.0, 9.0, 10.0], "-80% slice should have 7-10%"
    assert [tw for tw, _ in d["hump_relaxed"][95.0]] == [8.0, 9.0, 10.0], "-95% slice should have 8-10%"
    near(max(c for _, c in d["hump_relaxed"][80.0]), 28.714, 0.01, "-80% slice maximum (9%)")
    assert len(d["okit"]) == 10, "fine grid should have 10 points"
    near(max(c for _, c in d["okit"]), 5.0622, 0.001, "fine-grid maximum")
    near(d["okit_reported"][1], 5.0525, 0.001, "reported OKIT (-13.618%)")
    assert len(d["estate"]) == 7, "estate sweep should have 7 points"
    near(dict((x, c) for x, c, _, _ in d["estate"])[40.0], 8.4913, 0.001, "estate sweep at 40%")
    ces = [c for _, c, _, _ in d["estate"]]
    assert all(a > b for a, b in zip(ces, ces[1:])), "estate sweep should fall monotonically"
    for k, share in (("owt", 60.5), ("okit", 98.3), ("corner", 67.1)):
        g = d["groups"][k]
        assert len(g["by_agegroup_z"]) == 7 and all(len(r) == 9 for r in g["by_agegroup_z"]), f"{k}: heat map should be 7 x 9"
        near(g["share_gaining"], share, 0.1, f"share gaining, {k}")
    print("All data checks passed.")


# --------------------------------------------------------------------------- plotting helpers
def setup():
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    mpl.rcParams.update({
        "font.family": "serif", "font.serif": ["cmr10", "DejaVu Serif"], "mathtext.fontset": "cm",
        "axes.formatter.use_mathtext": True, "axes.unicode_minus": False, "font.size": 8.5,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlesize": 8.5, "axes.titlecolor": INK,
        "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
        "axes.facecolor": "white", "savefig.facecolor": "white", "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    return plt


def tidy(ax, ygrid=True):
    ax.set_axisbelow(True)
    if ygrid:
        ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.tick_params(length=2.5, width=0.7)


def spread(ys, gap):
    """Nudge label heights apart (keeps order), then recentre the group on its original mean."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for a, b in zip(order, order[1:]):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    shift = (sum(out) - sum(ys)) / len(ys)
    return [y - shift for y in out]


def end_labels(ax, items, gap, dx=5):
    """items: [(text, x, y, colour)] -> direct labels at the right end of each line."""
    ys = spread([y for _, _, y, _ in items], gap)
    for (text, x, _, col), y in zip(items, ys):
        ax.annotate(text, xy=(x, y), xytext=(dx, 0), textcoords="offset points",
                    va="center", ha="left", fontsize=8, color=INK)


def save(fig, out, name, png):
    fig.savefig(out / f"{name}.pdf")
    if png:
        fig.savefig(out / f"{name}.png", dpi=200)
    print(f"  wrote {name}.pdf" + (" and .png" if png else ""))


# --------------------------------------------------------------------------- figures
def fig_surface(d, plt, out, png):
    from matplotlib.lines import Line2D
    fig, axes = plt.subplots(1, 2, figsize=(6.1, 3.2), gridspec_kw={"width_ratios": [64, 104]})  # one x-scale
    fig.subplots_adjust(left=0.085, right=0.975, top=0.80, bottom=0.17, wspace=0.22)
    tws = [3, 5, 7, 8, 9]          # 10% left out: a sixth ordinal step is not distinguishable (see notes)
    colour, marker = dict(zip(tws, ORDINAL_BLUE)), dict(zip(tws, ["o", "s", "^", "D", "v"]))
    panels = [(axes[0], "surface40", "(a) Estate tax 40%", 64, (0, 22), 10),
              (axes[1], "surface0", "(b) No estate tax", 104, (0, 34), 10)]
    for ax, key, title, xmax, ylim, step in panels:
        ax.set_xlim(0, xmax)
        ax.set_ylim(*ylim)
        tidy(ax)
        if key == "surface0":
            ax.axvspan(50, 95, facecolor=TINT, lw=0, zorder=0)
            for x in (50, 95):
                ax.axvline(x, color=MUTED, lw=0.8, ls=(0, (3, 2)), zorder=1)
            ax.text(48.8, 1.0, "original\nlimit", ha="right", va="bottom", fontsize=7, color=INK2)
            ax.text(51.2, 1.0, "limit relaxed", ha="left", va="bottom", fontsize=7, color=INK2)
            ax.text(96.2, 1.0, "95%\nlimit", ha="left", va="bottom", fontsize=7, color=INK2)
        last = max(x for tw in tws for x, _ in d[key].get(float(tw), []))
        ends = []
        for tw in tws:
            pts = d[key].get(float(tw))
            if not pts:
                continue
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color=colour[tw], marker=marker[tw], ms=6, mec="white", mew=1.0, lw=1.5, zorder=3)
            if key == "surface40" or xs[-1] == last:   # in (b), lines ending inside the cluster rely on the legend
                ends.append((f"{tw}%", xs[-1], ys[-1], colour[tw]))
        end_labels(ax, ends, gap=0.065 * (ylim[1] - ylim[0]))
        if key == "surface0":
            x, y = max((p for tw in tws for p in d[key].get(float(tw), [])), key=lambda p: p[1])
            ax.annotate(f"{y:.2f}", xy=(x, y), xytext=(-6, 14), textcoords="offset points",
                        ha="right", fontsize=7.5, color=INK2)
        ax.set_title(title, loc="left")
        ax.set_xticks(range(0, min(int(xmax), 100), step))
        ax.set_xlabel(r"Capital-income subsidy, $-\tau_k$ (%)")
    axes[0].set_ylabel("Newborn welfare gain, CE2 (%)")
    handles = [Line2D([], [], color=colour[t], marker=marker[t], ms=6, mec="white", mew=1.0, lw=1.5) for t in tws]
    fig.legend(handles, [rf"$\tau_w$ = {t}%" for t in tws], loc="upper center", bbox_to_anchor=(0.5, 1.0),
               ncol=len(tws), frameon=False, handlelength=2.0, columnspacing=1.4, fontsize=8.5)
    save(fig, out, "fig_welfare_surface", png)


def fig_flat(d, plt, out, png):
    from matplotlib.lines import Line2D
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(6.1, 3.0))
    fig.subplots_adjust(left=0.085, right=0.985, top=0.83, bottom=0.18, wspace=0.42)

    # (a) capital-income-tax plateau
    xs, ys = zip(*d["okit"])
    best, noise = max(ys), d["okit_noise"]
    a.set_ylim(best - 0.24, best + 0.05)
    a.set_xlim(12.5, 22.5)
    tidy(a)
    a.axhspan(best - noise, best, facecolor=BLUE, alpha=0.12, lw=0, zorder=0)
    a.plot(xs, ys, color=BLUE, marker="o", ms=6, mec="white", mew=1.0, lw=1.5, zorder=3)
    rx, ry = d["okit_reported"]
    a.plot([rx], [ry], marker="D", ms=6.5, mfc="white", mec=INK, mew=1.2, ls="none", zorder=4)
    a.annotate("reported rate\n" + r"$-13.618\%$", xy=(rx, ry), xytext=(15.4, best - 0.185), fontsize=7.5,
               color=INK2, ha="left", va="center", arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7))
    a.text(22.3, best - noise + 0.008, f"band: within {noise:.2f} pp\nof the maximum", ha="right", va="bottom",
           fontsize=7, color=INK2)
    a.set_title("(a) Capital-income tax,\nno wealth tax", loc="left")
    a.set_xlabel(r"Capital-income subsidy, $-\tau_k$ (%)")
    a.set_ylabel("Newborn welfare gain, CE2 (%)")

    # (b) wealth-tax hump along the -50% subsidy edge
    b.set_xlim(2, 10.8)
    b.set_ylim(15, 25)
    tidy(b)
    for cal, col, mk in (("thesis", BLUE, "o"), ("recal", ORANGE, "s")):
        xs, ys = zip(*d["hump"][cal])
        top = max(ys)
        b.plot(xs, ys, color=col, lw=1.5, zorder=2)
        for x, y in zip(xs, ys):
            tied = top - y <= noise
            b.plot([x], [y], marker=mk, ms=6, mfc=col if tied else "white", mec=col,
                   mew=1.0 if tied else 1.2, zorder=3)
    b.set_title(r"(b) $\tau_k=-50\%$," + "\nno estate tax", loc="left")
    b.set_xlabel(r"Wealth tax, $\tau_w$ (%)")
    b.set_xticks([3, 4, 5, 6, 7, 8, 9, 10])
    handles = [Line2D([], [], color=BLUE, marker="o", ms=6, lw=1.5), Line2D([], [], color=ORANGE, marker="s", ms=6, lw=1.5)]
    b.legend(handles, ["Reported", "Recalibrated"], loc="lower right", frameon=False, fontsize=7.5,
             handlelength=1.6)

    # (c) the same comparison at larger subsidies (reported calibration, guard-relaxed points)
    c.set_xlim(6.5, 10.5)
    c.set_ylim(28, 31.3)
    tidy(c)
    handles = []
    for s, col, mk in ((80.0, "#3987e5", "o"), (95.0, "#0d366b", "^")):   # blue steps 400/700 (--ordinal passes)
        xs, ys = zip(*d["hump_relaxed"][s])
        top = max(ys)
        c.plot(xs, ys, color=col, lw=1.5, zorder=2)
        for x, y in zip(xs, ys):
            tied = top - y <= noise
            c.plot([x], [y], marker=mk, ms=6, mfc=col if tied else "white", mec=col,
                   mew=1.0 if tied else 1.2, zorder=3)
        handles.append(Line2D([], [], color=col, marker=mk, ms=6, lw=1.5))
    c.legend(handles, [r"$\tau_k=-80\%$", r"$\tau_k=-95\%$"], loc="center", frameon=False, fontsize=7.5,
             handlelength=1.6)
    c.set_title("(c) Larger subsidies,\nno estate tax", loc="left")
    c.set_xlabel(r"Wealth tax, $\tau_w$ (%)")
    c.set_xticks([7, 8, 9, 10])
    save(fig, out, "fig_flat_regions", png)


def fig_estate(d, plt, out, png):
    from matplotlib.lines import Line2D
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.1, 2.8))
    fig.subplots_adjust(left=0.085, right=0.975, top=0.88, bottom=0.19, wspace=0.30)
    xs = [e[0] for e in d["estate"]]
    for ax in (a, b):
        tidy(ax)
        ax.set_xlim(-2, 72)
        ax.set_xticks(range(0, 61, 10))
        ax.axvline(40, color=MUTED, lw=0.8, ls=(0, (3, 2)), zorder=1)
        ax.set_xlabel(r"Estate tax, $\tau_b$ (%)")
    a.set_ylim(0, 14)
    a.plot(xs, [e[1] for e in d["estate"]], color=BLUE, marker="o", ms=6, mec="white", mew=1.0, lw=1.5, zorder=3)
    a.plot(xs, [e[2] for e in d["estate"]], color=ORANGE, marker="s", ms=6, mec="white", mew=1.0, lw=1.5, zorder=3)
    end_labels(a, [("Newborn", xs[-1], d["estate"][-1][1], BLUE), ("Population", xs[-1], d["estate"][-1][2], ORANGE)],
               gap=0.07 * 14)
    a.text(39, 0.5, "benchmark", rotation=90, ha="right", va="bottom", fontsize=7, color=INK2)
    a.set_title("(a) Welfare gain, CE2 (%)", loc="left")
    a.legend([Line2D([], [], color=BLUE, marker="o", ms=6, lw=1.5), Line2D([], [], color=ORANGE, marker="s", ms=6, lw=1.5)],
             ["Newborn", "Population"], loc="upper right", frameon=False, fontsize=7.5, handlelength=1.6)
    top1 = [e[3] for e in d["estate"]]
    b.set_ylim(40, 50)
    b.plot(xs, top1, color=BLUE, marker="o", ms=6, mec="white", mew=1.0, lw=1.5, zorder=3)
    for x, y, dy in ((xs[0], top1[0], 7), (xs[-1], top1[-1], -12)):
        b.annotate(f"{y:.1f}", xy=(x, y), xytext=(0, dy), textcoords="offset points", ha="center", fontsize=7.5, color=INK2)
    b.set_title("(b) Top 1% wealth share (%)", loc="left")
    save(fig, out, "fig_estate_sweep", png)


def fig_groups(d, plt, out, png):
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap, Normalize
    cmap = LinearSegmentedColormap.from_list("div_blue_red", DIV_RED[::-1] + [NEUTRAL] + DIV_BLUE, N=256)
    vmax = 40.0
    norm = Normalize(-vmax, vmax)
    fig, axes = plt.subplots(1, 3, figsize=(6.1, 3.6))
    fig.subplots_adjust(left=0.075, right=0.995, top=0.80, bottom=0.27, wspace=0.07)
    titles = {"owt": "(a) Wealth tax 3.06%", "okit": r"(b) Capital-income tax $-13.6\%$",
              "corner": r"(c) 7% wealth tax, $-50\%$ capital," + "\n" + "no estate tax"}
    for i, (ax, key) in enumerate(zip(axes, ("owt", "okit", "corner"))):
        g = d["groups"][key]
        z = np.array(g["by_agegroup_z"], dtype=float)
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
        for r in range(z.shape[0]):
            for c in range(z.shape[1]):
                v = z[r, c]
                if np.isnan(v):
                    ax.text(c, r, "n/a", ha="center", va="center", fontsize=5.5, color=MUTED)
                    continue
                rgb = cmap(norm(v))[:3]
                lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
                n = int(round(v))
                ax.text(c, r, "0" if n == 0 else rf"${n}$", ha="center", va="center", fontsize=6.3,
                        color="white" if lum < 0.40 else INK)
        ax.set_title(titles[key] + "\n" + f"newborn {g['ce2_newborn']:.1f}%; {g['share_gaining']:.0f}% with\nnon-negative welfare changes",
                     loc="left", fontsize=7.5, linespacing=1.25)
        ax.set_xlabel("Ability group (1 = lowest)", fontsize=7.5)
    axes[0].set_ylabel("Age group", fontsize=7.5)
    cax = fig.add_axes([0.25, 0.115, 0.5, 0.02])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    cb.set_ticks([-40, -20, 0, 20, 40])
    cb.set_ticklabels([r"$-40$", r"$-20$", "0", "20", "40"])
    cb.ax.tick_params(length=2, width=0.6, labelsize=7)
    cb.outline.set_visible(False)
    cb.set_label("Consumption-equivalent change (%), blue = gain, red = loss", fontsize=7.5, labelpad=3)
    save(fig, out, "fig_group_welfare", png)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, help="workspace root (default: found by searching upwards)")
    ap.add_argument("--check-data", action="store_true", help="load the saved results and run the assertions only")
    ap.add_argument("--only", default="surface,flat,estate,groups", help="comma-separated subset of figures")
    ap.add_argument("--no-png", action="store_true", help="write PDFs only")
    ap.add_argument("--out", type=Path, help="output folder (default: output/figures)")
    ap.add_argument("--partd", type=Path, help="Part D results file (default: the replication snapshot's copy)")
    args = ap.parse_args()

    root = (args.root or find_root(Path(__file__).resolve().parent)).resolve()
    d = load_data(root, args.partd)
    check_data(d)
    if args.check_data:
        return
    out = args.out or root / "output" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    plt = setup()
    todo = {"surface": fig_surface, "flat": fig_flat, "estate": fig_estate, "groups": fig_groups}
    for name in [s.strip() for s in args.only.split(",") if s.strip()]:
        todo[name](d, plt, out, not args.no_png)
    print(f"Done. Files are in {out}")


if __name__ == "__main__":
    main()

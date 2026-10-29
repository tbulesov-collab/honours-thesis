from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _safe_read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_vector(path: Path) -> np.ndarray:
    if not path.exists():
        return np.array([])
    arr = np.loadtxt(path)
    return np.asarray(arr).reshape(-1)


def _ecdf(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    xs = np.sort(x)
    n = xs.size
    if n == 0:
        return np.array([]), np.array([])
    ys = np.arange(1, n + 1) / n
    return xs, ys


def _read_vermeulen(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Columns in file: rank, type, wealth, weight
    if not path.exists():
        return np.array([]), np.array([]), np.array([])
    raw = np.loadtxt(path)
    if raw.ndim != 2 or raw.shape[1] < 4:
        return np.array([]), np.array([]), np.array([])
    t = raw[:, 1]
    wealth = raw[:, 2]
    weight = raw[:, 3]
    df = pd.DataFrame({"type": t, "wealth": wealth, "weight": weight})
    g = df.groupby("wealth", as_index=False).agg({"weight": "sum", "type": "first"})
    g = g[g["wealth"] > 0].copy()
    g["wealth"] = 1.3572 * g["wealth"]
    return g["wealth"].to_numpy(), g["weight"].to_numpy(), g["type"].to_numpy()


def _regression_line(logw: np.ndarray, logccdf: np.ndarray) -> tuple[float, float]:
    if logw.size < 2:
        return np.nan, np.nan
    slope, intercept = np.polyfit(logw, logccdf, 1)
    return intercept, slope


def _read_stats_grid(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, delim_whitespace=True)
    except Exception:
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()


def _resolve_stats_w_path(model_dir: Path) -> Path | None:
    candidates = [
        model_dir / "Opt_Tax_W" / "Stats_by_tau_w.txt",
        model_dir / "Opt_Tax_W" / "Wide_Grid" / "Stats_by_tau_w.txt",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _resolve_stats_k_path(model_dir: Path) -> Path | None:
    candidates = [
        model_dir / "Opt_Tax_K" / "Stats_by_tau_k_2.txt",
        model_dir / "Opt_Tax_K" / "Stats_by_tau_k.txt",
        model_dir / "Opt_Tax_K" / "Wide_Grid" / "Stats_by_tau_k.txt",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_col(df: pd.DataFrame, preferred: list[str]) -> str | None:
    for c in preferred:
        if c in df.columns:
            return c
    low = {c.lower(): c for c in df.columns}
    for p in preferred:
        if p.lower() in low:
            return low[p.lower()]
    for c in df.columns:
        lc = c.lower()
        for p in preferred:
            if p.lower() in lc:
                return c
    return None


def figure_macro_change_bar(table_v_path: Path, out_png: Path) -> bool:
    df = _safe_read_table(table_v_path)
    if df.empty or "pct_change" not in df.columns:
        return False

    plot_df = df[df["variable"].isin(["YBAR", "KBAR", "QBAR", "CBAR", "wage", "R"])].copy()
    if plot_df.empty:
        return False

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 5))
    plt.bar(plot_df["variable"], plot_df["pct_change"])
    plt.axhline(0.0, color="black", linewidth=1.0)
    plt.ylabel("Percent change (Tax Reform vs Benchmark)")
    plt.title("Macro Changes Under Tax Reform")
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()
    return True


def figure_1a_pareto_baseline(model_dir: Path, out_dir: Path) -> list[Path]:
    out: list[Path] = []
    panel_path = model_dir / "Simul" / "panel_Pareto"
    ver_path = Path("Figures_._Tables") / "Vermeulen_Data" / "USA_IM1.dat"
    wealth = _read_vector(panel_path)
    wv, wgt, _t = _read_vermeulen(ver_path)
    if wealth.size == 0 or wv.size == 0:
        return out

    wealth = np.sort(wealth)
    wmins = [1_000_000.0, float(np.percentile(wealth, 98)), float(np.percentile(wealth, 99))]
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    for wmin in wmins:
        wb = wealth[wealth >= wmin]
        if wb.size < 50:
            continue
        xb, fb = _ecdf(wb)
        xb = np.log(xb[1:])
        yb = np.log(1.0 - fb[:-1])

        mask = wv > wmin
        xv = np.log(wv[mask])
        if xv.size < 50:
            continue
        yv = np.log(np.cumsum(wgt[mask][::-1])[::-1] / np.sum(wgt[mask]))

        ib, sb = _regression_line(xb, yb)
        iv, sv = _regression_line(xv, yv)
        xx = np.linspace(min(xv.min(), xb.min()), max(xv.max(), xb.max()), 100)

        plt.figure(figsize=(8, 5))
        plt.scatter(xv, yv, s=10, alpha=0.4, label="US Data")
        plt.plot(xx, iv + sv * xx, linewidth=2.0, label="US Regression")
        plt.scatter(xb, yb, s=10, alpha=0.4, label="Benchmark Model")
        plt.plot(xx, ib + sb * xx, linewidth=2.0, label="Model Regression")
        plt.xlabel("log(Wealth)")
        plt.ylabel("log(CCDF)")
        plt.title(f"Pareto Tail Above ${wmin:,.0f}")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        p = fig_dir / f"figure_1a_pareto_{int(round(wmin))}.png"
        plt.savefig(p, dpi=160)
        plt.close()
        out.append(p)
    return out


def figure_2_optimal_welfare(model_dir: Path, out_png: Path) -> bool:
    w_path = _resolve_stats_w_path(model_dir)
    k_path = _resolve_stats_k_path(model_dir)
    if w_path is None or k_path is None:
        return False
    w = _read_stats_grid(w_path)
    k = _read_stats_grid(k_path)
    if w.empty or k.empty:
        return False
    xw = _find_col(w, ["GBAR_K/Tax_Rev_bench", "GBAR_K_Tax_Rev_bench"])
    yw = _find_col(w, ["Av_Util_NB"])
    xk = _find_col(k, ["GBAR_K/Tax_Rev_bench", "GBAR_K_Tax_Rev_bench"])
    yk = _find_col(k, ["Av_Util_NB"])
    if not all([xw, yw, xk, yk]):
        return False

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 5))
    plt.plot(k[xk], k[yk], linewidth=2.2, label="Capital income tax economy")
    plt.plot(w[xw], w[yw], linewidth=2.2, label="Wealth tax economy")
    plt.axhline(0.0, color="black", linestyle="--", linewidth=1.0)
    plt.xlabel("Tax Revenue from K / Total Tax Revenue")
    plt.ylabel("Average Welfare Change (Newborn)")
    plt.title("Figure 2: Welfare Gains from Optimal Taxation")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()
    return True


def figure_3_k_q(model_dir: Path, out_png: Path) -> bool:
    w_path = _resolve_stats_w_path(model_dir)
    k_path = _resolve_stats_k_path(model_dir)
    if w_path is None or k_path is None:
        return False
    w = _read_stats_grid(w_path)
    k = _read_stats_grid(k_path)
    if w.empty or k.empty:
        return False

    xw = _find_col(w, ["GBAR_K/Tax_Rev_bench", "GBAR_K_Tax_Rev_bench"])
    xk = _find_col(k, ["GBAR_K/Tax_Rev_bench", "GBAR_K_Tax_Rev_bench"])
    kw = _find_col(w, ["KBAR"])
    qw = _find_col(w, ["QBAR"])
    kk = _find_col(k, ["KBAR"])
    qk = _find_col(k, ["QBAR"])
    tw = _find_col(w, ["tauW_at", "tauW"])
    tk = _find_col(k, ["tauK"])
    if not all([xw, xk, kw, qw, kk, qk, tw, tk]):
        return False

    i0w = int(np.argmin(np.abs(w[tw].to_numpy())))
    i0k = int(np.argmin(np.abs(k[tk].to_numpy())))
    wk = 100.0 * (w[kw] / float(w[kw].iloc[i0w]) - 1.0)
    wq = 100.0 * (w[qw] / float(w[qw].iloc[i0w]) - 1.0)
    kkc = 100.0 * (k[kk] / float(k[kk].iloc[i0k]) - 1.0)
    kqc = 100.0 * (k[qk] / float(k[qk].iloc[i0k]) - 1.0)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 5))
    plt.plot(k[xk], kkc, linewidth=2.0, label="OCIT: K")
    plt.plot(k[xk], kqc, "--", linewidth=2.0, label="OCIT: Q")
    plt.plot(w[xw], wk, linewidth=2.0, label="OWT: K")
    plt.plot(w[xw], wq, "--", linewidth=2.0, label="OWT: Q")
    plt.axhline(0.0, color="gray", linestyle="--", linewidth=1.0)
    plt.axvline(0.0, color="gray", linestyle="--", linewidth=1.0)
    plt.xlabel("Tax Revenue from K / Total Tax Revenue")
    plt.ylabel("% Deviation from zero-tax benchmark")
    plt.title("Figure 3: K and Q vs Revenue Share from Capital Tax")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()
    return True


def figure_c1_pareto_mu80(out_png: Path) -> bool:
    candidates = [
        Path("Revision") / "Model_2.1_mu80" / "Simul" / "panel_Pareto",
        Path("Model_2.1_mu80") / "Simul" / "panel_Pareto",
    ]
    panel_path = next((p for p in candidates if p.exists()), None)
    ver_path = Path("Figures_._Tables") / "Vermeulen_Data" / "USA_IM1.dat"
    if panel_path is None or not ver_path.exists():
        return False
    wealth = _read_vector(panel_path)
    wv, wgt, _ = _read_vermeulen(ver_path)
    if wealth.size == 0 or wv.size == 0:
        return False
    wmin = 1_000_000.0
    wb = wealth[wealth >= wmin]
    xv = np.log(wv[wv > wmin])
    yv = np.log(np.cumsum(wgt[wv > wmin][::-1])[::-1] / np.sum(wgt[wv > wmin]))
    xb, fb = _ecdf(wb)
    xb = np.log(xb[1:])
    yb = np.log(1.0 - fb[:-1])
    ib, sb = _regression_line(xb, yb)
    iv, sv = _regression_line(xv, yv)
    xx = np.linspace(min(xv.min(), xb.min()), max(xv.max(), xb.max()), 100)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 5))
    plt.scatter(xv, yv, s=10, alpha=0.4, label="US Data")
    plt.plot(xx, iv + sv * xx, linewidth=2.0, label="US Regression")
    plt.scatter(xb, yb, s=10, alpha=0.4, label="mu=0.8 Model")
    plt.plot(xx, ib + sb * xx, linewidth=2.0, label="Model Regression")
    plt.xlabel("log(Wealth)")
    plt.ylabel("log(CCDF)")
    plt.title("Figure C.1: Pareto Tail (mu=0.8)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()
    return True


def figure_c4_income_vs_k_tax_share(model_dir: Path, out_png: Path) -> bool:
    w_path = _resolve_stats_w_path(model_dir)
    k_path = _resolve_stats_k_path(model_dir)
    if w_path is None or k_path is None:
        return False
    w = _read_stats_grid(w_path)
    k = _read_stats_grid(k_path)
    if w.empty or k.empty:
        return False
    xw = _find_col(w, ["GBAR_K/Tax_Rev_bench", "GBAR_K_Tax_Rev_bench"])
    xk = _find_col(k, ["GBAR_K/Tax_Rev_bench", "GBAR_K_Tax_Rev_bench"])
    # After-tax labor income: psi * wage * NBAR
    psiw = _find_col(w, ["psi"])
    psik = _find_col(k, ["psi"])
    wagew = _find_col(w, ["wage"])
    wagek = _find_col(k, ["wage"])
    nbarw = _find_col(w, ["NBAR"])
    nbark = _find_col(k, ["NBAR"])
    # After-tax capital income
    cw_col = _find_col(w, ["Tot_Cap_Inc"])
    ck_col = _find_col(k, ["Tot_Cap_Inc"])
    tauw = _find_col(w, ["tauW_at", "tauW"])
    tauk = _find_col(k, ["tauK"])
    kbarw = _find_col(w, ["KBAR"])
    if not all([xw, xk, psiw, psik, wagew, wagek, nbarw, nbark, cw_col, ck_col, tauw, tauk, kbarw]):
        return False

    w_labor = w[psiw].to_numpy() * w[wagew].to_numpy() * w[nbarw].to_numpy()
    k_labor = k[psik].to_numpy() * k[wagek].to_numpy() * k[nbark].to_numpy()
    w_cap = w[cw_col].to_numpy() - w[tauw].to_numpy() * w[kbarw].to_numpy()
    k_cap = (1.0 - k[tauk].to_numpy()) * k[ck_col].to_numpy()

    i0w = int(np.argmin(np.abs(w[tauw].to_numpy())))
    i0k = int(np.argmin(np.abs(k[tauk].to_numpy())))
    w_labor_pct = 100.0 * (w_labor / w_labor[i0w] - 1.0)
    k_labor_pct = 100.0 * (k_labor / k_labor[i0k] - 1.0)
    w_cap_pct = 100.0 * (w_cap / w_cap[i0w] - 1.0)
    k_cap_pct = 100.0 * (k_cap / k_cap[i0k] - 1.0)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    _, ax1 = plt.subplots(figsize=(9, 5))
    ax2 = ax1.twinx()
    ax1.plot(k[xk], k_labor_pct, color="tab:red", linewidth=2.0, label="Labor income, tau_k")
    ax1.plot(w[xw], w_labor_pct, color="gray", linewidth=2.0, label="Labor income, tau_a")
    ax2.plot(k[xk], k_cap_pct, color="tab:red", linestyle="-.", linewidth=2.0, label="Capital income, tau_k")
    ax2.plot(w[xw], w_cap_pct, color="gray", linestyle="--", linewidth=2.0, label="Capital income, tau_a")
    ax1.set_xlabel("Tax Revenue from K / Total Tax Revenue")
    ax1.set_ylabel("% Deviation of After-Tax Labor Income")
    ax2.set_ylabel("% Deviation of After-Tax Capital Income")
    ax1.set_ylim(-20, 20)
    ax2.set_ylim(-40, 40)
    ax1.grid(True, alpha=0.3)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="lower center", fontsize=10)
    plt.title("Figure C.4: After-Tax Labor and Capital Income")
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()
    return True


def figure_c3a_igm_rank_rank(out_png: Path) -> bool:
    fagereng_path = Path("Figures_._Tables") / "Fagereng_Figure" / "Fagereng_IGM_data.csv"
    if not fagereng_path.exists():
        return False
    try:
        df = pd.read_csv(fagereng_path)
    except Exception:
        return False
    xcol = _find_col(df, ["pct_father"])
    ycol = _find_col(df, ["av_pct_child"])
    if xcol is None or ycol is None:
        return False
    x = df[xcol].to_numpy(dtype=float)
    y = df[ycol].to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    xx = np.linspace(0.0, 100.0, 3)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(6, 6))
    plt.scatter(x, y, s=18, linewidths=1.5, edgecolors="#0072bd", facecolors="#ade9ff", label="Norway (Fagereng et al.)")
    plt.plot(xx, intercept + slope * xx, "k--", linewidth=1.5)
    plt.xlabel("Father's Wealth Percentile")
    plt.ylabel("Offspring's Average Wealth Percentile")
    plt.title("Figure C.3.A: Intergenerational Wealth Rank")
    plt.xlim(0, 101)
    plt.ylim(25, 95)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()
    return True


def write_available_figures(run_dir: Path) -> list[Path]:
    written: list[Path] = []
    fig_dir = run_dir / "figures"
    ok = figure_macro_change_bar(
        table_v_path=run_dir / "tables" / "table_v_macro_changes_tax_reform.csv",
        out_png=fig_dir / "figure_macro_changes_tax_reform.png",
    )
    if ok:
        written.append(fig_dir / "figure_macro_changes_tax_reform.png")
    return written


def figure_entrepreneur_by_age(model_dir: Path, out_png: Path) -> bool:
    p_b = model_dir / "Entrepreneur_by_age.txt"
    p_r = model_dir / "Tax_Reform" / "Entrepreneur_by_age.txt"
    if not p_b.exists() or not p_r.exists():
        return False

    def load_col(path: Path) -> tuple[np.ndarray, np.ndarray]:
        # Skip first three header lines, then read numeric rows.
        data = pd.read_csv(path, delim_whitespace=True, skiprows=3, header=None)
        # cols: age, >10, >25, >50, >90, ...
        age = data.iloc[:, 0].to_numpy()
        frac50 = data.iloc[:, 3].to_numpy()
        return age, frac50

    age_b, y_b = load_col(p_b)
    age_r, y_r = load_col(p_r)
    if age_b.size == 0 or age_r.size == 0:
        return False

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 5))
    plt.plot(age_b, y_b, label="Benchmark")
    plt.plot(age_r, y_r, label="Tax Reform")
    plt.xlabel("Age")
    plt.ylabel("Entrepreneurs (%), Pr/Income > 50%")
    plt.title("Entrepreneur Share Over Life Cycle")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()
    return True


def write_extra_figures(model_dir: Path, out_dir: Path) -> list[Path]:
    written: list[Path] = []
    fig_dir = out_dir / "figures"
    ok = figure_entrepreneur_by_age(
        model_dir=model_dir,
        out_png=fig_dir / "figure_c2_entrepreneur_by_age_benchmark_vs_reform.png",
    )
    if ok:
        written.append(fig_dir / "figure_c2_entrepreneur_by_age_benchmark_vs_reform.png")

    for p in figure_1a_pareto_baseline(model_dir=model_dir, out_dir=out_dir):
        written.append(p)

    if figure_2_optimal_welfare(model_dir=model_dir, out_png=fig_dir / "figure_2_optimal_welfare.png"):
        written.append(fig_dir / "figure_2_optimal_welfare.png")

    if figure_3_k_q(model_dir=model_dir, out_png=fig_dir / "figure_3_k_q.png"):
        written.append(fig_dir / "figure_3_k_q.png")

    if figure_c1_pareto_mu80(out_png=fig_dir / "figure_c1_pareto_mu80.png"):
        written.append(fig_dir / "figure_c1_pareto_mu80.png")

    if figure_c3a_igm_rank_rank(out_png=fig_dir / "figure_c3a_igm_rank_rank.png"):
        written.append(fig_dir / "figure_c3a_igm_rank_rank.png")

    if figure_c4_income_vs_k_tax_share(model_dir=model_dir, out_png=fig_dir / "figure_c4_income_vs_k_tax_share.png"):
        written.append(fig_dir / "figure_c4_income_vs_k_tax_share.png")
    return written

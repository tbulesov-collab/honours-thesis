#!/usr/bin/env python3
"""Compare a run's benchmark and RN-reform output against the published paper.

Prints Table III calibration moments and Table V macro changes side by side with
GKKOC (2022, QJE), and optionally against a previous run for a before/after view.

    python3 tools/compare_to_paper.py
    python3 tools/compare_to_paper.py --prev Revision/Model_2.1_Local/Run_History/Run_preFidelityFix_20260808_1448

Stdlib only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_output(path: Path) -> dict[str, list[float]]:
    """Parse a GKK output.txt into {label: [values]}; later lines win."""
    out: dict[str, list[float]] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        tok = raw.split()
        if len(tok) < 2:
            continue
        try:
            out[tok[0]] = [float(t.replace("D", "E").replace("d", "e")) for t in tok[1:]]
        except ValueError:
            continue
    return out


def s(d: dict[str, list[float]], key: str) -> float:
    v = d.get(key)
    return v[0] if v else float("nan")


# Table III, "Benchmark" column. Targeted unless marked untargeted.
TABLE_III = [
    ("Std dev log earnings",   "STD_Labor_Earnings", 0.80,  1.0),
    ("Capital-output ratio",   "Wealth_Output",      3.00,  1.0),
    ("Average labor hours",    "Av.Hours",           0.40,  1.0),
    ("Bequest/wealth",         "Total_Bequest_Wealth", 0.012, 1.0),
    ("Top 1% wealth share",    "Wealth_Top_1%",      0.36,  1.0),
    ("Top 0.1% share (untgt)", "Wealth_Top_0.1%",    0.23,  1.0),
    ("Debt+ext funds/GDP",     "Debt_Output",        1.50,  1.0),
    ("Std dev of returns",     "Std_Return",         0.084, 1.0),
]

# Table V, RN reform. (label, output.txt key, "pct" or "diff", paper value)
TABLE_V = [
    ("K",           "KBAR",   "pct",  16.4),
    ("Q",           "QBAR",   "pct",  22.6),
    ("TFP_Q",       "TFP_Q",  "pct",   5.3),
    ("L",           "NBAR",   "pct",   1.2),
    ("Y",           "YBAR",   "pct",   9.2),
    ("C",           "CBAR",   "pct",   9.5),
    ("w",           "wage",   "pct",   8.0),
    ("w (net)",     "wage_AT","pct",   8.0),
    ("dr (pp)",     "R",      "diff",  0.21),
    ("dr net (pp)", "R_AT",   "diff", -0.36),
]

PAPER_TAU_A = 1.19357  # authors' unrounded value, GKK_Main.f90:822 (paper prints 1.19)


def tau_a(reform: dict) -> float:
    return 100.0 * s(reform, "Wealth_Tax_Above")


def report(model_dir: Path, label: str, prev_dir: Path | None) -> None:
    bench = parse_output(model_dir / "output.txt")
    reform = parse_output(model_dir / "Tax_Reform" / "output_exp.txt")
    if not bench or not reform:
        raise SystemExit(f"error: missing output.txt / Tax_Reform/output_exp.txt under {model_dir}")

    pb = parse_output(prev_dir / "output.txt") if prev_dir else {}
    pr = parse_output(prev_dir / "Tax_Reform" / "output_exp.txt") if prev_dir else {}
    has_prev = bool(pb and pr)
    pcol = f"{'prev':>10}" if has_prev else ""

    print(f"\n=== {label} ===")
    print(f"\nTable III - benchmark calibration moments")
    print(f"  {'moment':<24}{'model':>10}{pcol}{'paper':>10}{'diff':>10}")
    for name, key, paper, scale in TABLE_III:
        v = s(bench, key) * scale
        pv = f"{s(pb, key)*scale:>10.4f}" if has_prev else ""
        print(f"  {name:<24}{v:>10.4f}{pv}{paper:>10.4f}{v - paper:>+10.4f}")

    print(f"\nTable V - RN reform, change from benchmark")
    t = tau_a(reform)
    pt = f"{tau_a(pr):>10.3f}" if has_prev else ""
    print(f"  {'variable':<24}{'model':>10}{pcol}{'paper':>10}{'diff':>10}")
    print(f"  {'tau_a (%)':<24}{t:>10.3f}{pt}{PAPER_TAU_A:>10.3f}{t - PAPER_TAU_A:>+10.3f}")
    for name, key, how, paper in TABLE_V:
        b, e = s(bench, key), s(reform, key)
        v = 100.0 * (e / b - 1.0) if how == "pct" else e - b
        if has_prev:
            b2, e2 = s(pb, key), s(pr, key)
            v2 = 100.0 * (e2 / b2 - 1.0) if how == "pct" else e2 - b2
            pv = f"{v2:>10.3f}"
        else:
            pv = ""
        print(f"  {name:<24}{v:>10.3f}{pv}{paper:>10.3f}{v - paper:>+10.3f}")

    # Revenue neutrality is the condition tau_a is solving; report the residual.
    gb, ge = s(bench, "GBAR"), s(reform, "GBAR")
    print(f"\n  revenue neutrality: GBAR_exp/GBAR_bench - 1 = {ge/gb - 1:+.3e}  (tolerance 1e-5)")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model-dir", default="Revision/Model_2.1_Local")
    ap.add_argument("--prev", default=None, help="a Run_History folder to compare against")
    a = ap.parse_args()
    prev = (ROOT / a.prev).resolve() if a.prev else None
    report((ROOT / a.model_dir).resolve(), "current run", prev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

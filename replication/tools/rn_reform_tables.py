#!/usr/bin/env python3
"""Rebuild the revenue-neutral (RN) tax reform tables of GKKOC (2022, QJE).

Reads the raw Fortran output of a benchmark run and a Tax_Reform run and
reproduces Tables V, VI and VII, each shown next to the published values.

    python3 tools/rn_reform_tables.py
    python3 tools/rn_reform_tables.py --model-dir Revision/Model_2.1_Local

Inputs (written by GKK_Main.a):
    <model-dir>/output.txt                    benchmark aggregates
    <model-dir>/Tax_Reform/output_exp.txt     reform aggregates + welfare
    <model-dir>/Tax_Reform/draft_group_CE.txt CE1 by age group x z-percentile

Stdlib only, so it runs under any Python 3.9+ without the paper_python env.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------- parsing


def _as_float(tok: str) -> float:
    """Parse a Fortran real, accepting D/d exponents (1.17D-02)."""
    return float(tok.replace("D", "E").replace("d", "e"))


def parse_output(path: Path) -> dict[str, list[float]]:
    """Parse a GKK output.txt into {label: [values]}.

    Lines look like ' KBAR   4.0517233981232517' or
    ' BQ/Inc_for_90th_pct   4.066  4.331  5.531'. A line qualifies when every
    token after the first parses as a real; headers and text flags are skipped.
    Later occurrences win, matching how the Fortran code overwrites a section.
    """
    out: dict[str, list[float]] = {}
    if not path.exists():
        return out

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        tok = raw.split()
        if len(tok) < 2:
            continue
        try:
            out[tok[0]] = [_as_float(t) for t in tok[1:]]
        except ValueError:
            continue
    return out


def scalar(d: dict[str, list[float]], key: str) -> float:
    v = d.get(key)
    if not v:
        raise KeyError(key)
    return v[0]


def read_matrix(path: Path) -> list[list[float]]:
    if not path.exists():
        return []
    rows = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        tok = raw.split()
        if tok:
            rows.append([_as_float(t) for t in tok])
    return rows


# ---------------------------------------------------------------- tables

# Published values, GKKOC (2022, QJE). Used only for the side-by-side column.
PAPER_V = {
    "tau_a (%)": 1.19,
    "K": 16.4,
    "Q": 22.6,
    "TFP_Q": 5.3,
    "L": 1.2,
    "Y": 9.2,
    "C": 9.5,
    "w": 8.0,
    "w (net)": 8.0,
    "dr (pp)": 0.21,
    "dr net (pp)": -0.36,
}
PAPER_VI = {"CE1": 6.8, "CE2": 7.2, "% with welfare gain": 67.5}
PAPER_VII = [
    [6.7, 6.3, 6.8, 8.5, 11.5, 13.4],
    [6.3, 5.5, 5.5, 6.5, 8.5, 9.7],
    [4.9, 3.8, 3.3, 3.3, 3.1, 2.8],
    [2.2, 1.5, 1.1, 0.9, 0.4, -0.2],
    [-0.2, -0.3, -0.4, -0.4, -0.7, -1.0],
]
AGE_GROUPS = ["20 (newborn)", "21-34", "35-49", "50-64", "65+"]
Z_BINS = ["0-40", "40-80", "80-90", "90-99", "99-99.9", "99.9+"]


def pct_change(bench: float, exp: float) -> float:
    return 100.0 * (exp / bench - 1.0)


def build_table_v(bench, reform) -> list[dict]:
    """Table V: change in macro variables from the US benchmark.

    Quantities are percent changes; interest rates are percentage-POINT
    changes, because R/R_AT are already stored in percent by the Fortran code.
    """
    rows = [
        # label,          key,        transform
        ("K", "KBAR", "pct"),
        ("Q", "QBAR", "pct"),
        ("TFP_Q", "TFP_Q", "pct"),
        ("L", "NBAR", "pct"),
        ("Y", "YBAR", "pct"),
        ("C", "CBAR", "pct"),
        ("w", "wage", "pct"),
        ("w (net)", "wage_AT", "pct"),
        ("dr (pp)", "R", "diff"),
        ("dr net (pp)", "R_AT", "diff"),
    ]

    out = [{
        "variable": "tau_a (%)",
        "benchmark": 0.0,
        "reform": 100.0 * scalar(reform, "Wealth_Tax_Above"),
        "change": 100.0 * scalar(reform, "Wealth_Tax_Above"),
        "paper": PAPER_V["tau_a (%)"],
    }]

    for label, key, how in rows:
        b, e = scalar(bench, key), scalar(reform, key)
        change = pct_change(b, e) if how == "pct" else e - b
        out.append({
            "variable": label,
            "benchmark": b,
            "reform": e,
            "change": change,
            "paper": PAPER_V[label],
        })

    # K/Y is reported as a level in the paper (3 -> 3.2), not a change.
    b, e = scalar(bench, "Wealth_Output"), scalar(reform, "Wealth_Output")
    out.append({"variable": "K/Y (level)", "benchmark": b, "reform": e,
                "change": e - b, "paper": float("nan")})
    return out


def build_table_vi(reform) -> list[dict]:
    keys = {
        "CE1": "CE1_NB(exp)",
        "CE2": "CE2_NB(exp)",
        "% with welfare gain": "Frac_pos_welfare(bench)",
    }
    return [{"metric": lbl, "model": scalar(reform, k), "paper": PAPER_VI[lbl]}
            for lbl, k in keys.items()]


def build_table_vii(model_dir: Path) -> list[dict]:
    """CE1 by age group x entrepreneurial ability.

    draft_group_CE.txt has 8 columns; the last two split the top 0.1% and are
    not reported in the paper, so only the first six are kept.
    """
    mat = read_matrix(model_dir / "Tax_Reform" / "draft_group_CE.txt")
    out = []
    for i, age in enumerate(AGE_GROUPS):
        if i >= len(mat):
            break
        for j, zbin in enumerate(Z_BINS):
            if j >= len(mat[i]):
                break
            out.append({"age_group": age, "z_bin": zbin,
                        "model": mat[i][j], "paper": PAPER_VII[i][j]})
    return out


# ---------------------------------------------------------------- output


def _fmt(x: float) -> str:
    return "  n/a" if x != x else f"{x:7.2f}"


def print_tables(t5, t6, t7) -> None:
    print("\nTable V - Tax Reform: change in macro variables (RN reform)")
    print(f"  {'variable':<14}{'benchmark':>12}{'reform':>12}{'change':>10}{'paper':>10}{'diff':>9}")
    for r in t5:
        diff = r["change"] - r["paper"]
        print(f"  {r['variable']:<14}{r['benchmark']:>12.4f}{r['reform']:>12.4f}"
              f"{_fmt(r['change']):>10}{_fmt(r['paper']):>10}{_fmt(diff):>9}")

    print("\nTable VI - Average welfare gain from the RN reform (%)")
    print(f"  {'metric':<24}{'model':>10}{'paper':>10}{'diff':>9}")
    for r in t6:
        print(f"  {r['metric']:<24}{r['model']:>10.2f}{r['paper']:>10.2f}"
              f"{r['model'] - r['paper']:>9.2f}")

    if t7:
        print("\nTable VII - CE1 by age group and entrepreneurial ability (model / paper)")
        print(f"  {'age group':<14}" + "".join(f"{z:>16}" for z in Z_BINS))
        for age in AGE_GROUPS:
            cells = [r for r in t7 if r["age_group"] == age]
            if not cells:
                continue
            line = "".join(f"{c['model']:>9.1f} /{c['paper']:>6.1f}" for c in cells)
            print(f"  {age:<14}{line}")
    print()


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-dir", default="Revision/Model_2.1_Local",
                    help="folder holding output.txt and Tax_Reform/ (default: %(default)s)")
    ap.add_argument("--out", default=None,
                    help="directory for CSV output (default: <model-dir>/_Tables_RN)")
    args = ap.parse_args()

    model_dir = (root / args.model_dir).resolve()
    out_dir = Path(args.out).resolve() if args.out else model_dir / "_Tables_RN"

    bench_path = model_dir / "output.txt"
    reform_path = model_dir / "Tax_Reform" / "output_exp.txt"
    for p in (bench_path, reform_path):
        if not p.exists():
            print(f"error: missing {p}\n"
                  f"       run 'bash tools/reproduce_rn_reform.sh' first.", file=sys.stderr)
            return 1

    bench = parse_output(bench_path)
    reform = parse_output(reform_path)

    try:
        t5 = build_table_v(bench, reform)
        t6 = build_table_vi(reform)
    except KeyError as exc:
        print(f"error: key {exc} not found - the run may not have finished.", file=sys.stderr)
        return 1
    t7 = build_table_vii(model_dir)

    print_tables(t5, t6, t7)
    write_csv(t5, out_dir / "table_v_macro_changes_RN.csv")
    write_csv(t6, out_dir / "table_vi_welfare_RN.csv")
    write_csv(t7, out_dir / "table_vii_welfare_by_group_RN.csv")
    print(f"CSV written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

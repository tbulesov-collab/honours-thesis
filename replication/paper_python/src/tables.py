from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .io_utils import parse_key_value_file, parse_named_numeric_rows, read_numeric_matrix, save_table


def build_table_iii_moments(model_dir: Path) -> pd.DataFrame:
    bench = parse_key_value_file(model_dir / "output.txt")
    rows = [
        "Debt_Output",
        "Wealth_Output",
        "Wealth_Top_1%",
        "Wealth_Top_10%",
        "STD_Labor_Earnings",
        "Mean_Return",
        "Capital_Tax/Total_Tax",
    ]
    data = [{"moment": r, "benchmark_model": bench.get(r, np.nan)} for r in rows]
    return pd.DataFrame(data)


def build_table_v_macro_changes(model_dir: Path) -> pd.DataFrame:
    bench = parse_key_value_file(model_dir / "output.txt")
    reform = parse_key_value_file(model_dir / "Tax_Reform" / "output_exp.txt")
    rows = ["GBAR", "KBAR", "QBAR", "NBAR", "EBAR", "YBAR", "CBAR", "wage", "R"]
    out = []
    for r in rows:
        b = bench.get(r, np.nan)
        e = reform.get(r, np.nan)
        pct = np.nan
        if np.isfinite(b) and b != 0 and np.isfinite(e):
            pct = 100.0 * (e / b - 1.0)
        out.append({"variable": r, "benchmark": b, "tax_reform": e, "pct_change": pct})
    return pd.DataFrame(out)


def build_table_vi_welfare(model_dir: Path) -> pd.DataFrame:
    reform = parse_key_value_file(model_dir / "Tax_Reform" / "output_exp.txt")
    keys = [
        "CE1_Pop(exp)",
        "CE1_NB(exp)",
        "CE2_Pop(exp)",
        "CE2_NB(exp)",
        "Frac_pos_welfare(bench)",
    ]
    return pd.DataFrame({"metric": keys, "value": [reform.get(k, np.nan) for k in keys]})


def build_table_vii_group_welfare(model_dir: Path) -> pd.DataFrame:
    mat = read_numeric_matrix(model_dir / "Tax_Reform" / "draft_group_CE.txt")
    if mat.size == 0:
        return pd.DataFrame(columns=["row", "col", "value"])
    rows, cols = mat.shape
    records = []
    for i in range(rows):
        for j in range(cols):
            records.append({"row": i + 1, "col": j + 1, "value": float(mat[i, j])})
    return pd.DataFrame(records)


def build_table_iv_return_distribution(model_dir: Path) -> pd.DataFrame:
    # Available output in current run: Tax_Reform/Simul/Asset_Return_Panel/Return_Stats_exp.txt
    p = model_dir / "Tax_Reform" / "Simul" / "Asset_Return_Panel" / "Return_Stats_exp.txt"
    rows = parse_named_numeric_rows(p)
    if rows.empty:
        return pd.DataFrame(columns=["stat"])
    # Prefer 25-75 row to align with MATLAB comment.
    target = rows[rows["name"] == "Returns_2575"]
    if target.empty:
        target = rows.head(1)
    return target.rename(columns={"name": "stat"})


def build_table_x_decomposition(model_dir: Path) -> pd.DataFrame:
    p = model_dir / "Tax_Reform" / "CE_Decomposition.txt"
    rows = parse_named_numeric_rows(p)
    if rows.empty:
        return pd.DataFrame(columns=["component"])
    return rows.rename(columns={"name": "component"})


def build_table_b3_welfare_distribution(model_dir: Path) -> pd.DataFrame:
    ce = read_numeric_matrix(model_dir / "Tax_Reform" / "draft_group_CE.txt")
    pos = read_numeric_matrix(model_dir / "Tax_Reform" / "draft_group_fpos_welfare.txt")
    records: list[dict[str, float]] = []
    if ce.size > 0:
        for i in range(ce.shape[0]):
            for j in range(ce.shape[1]):
                records.append({"metric": 1.0, "row": i + 1.0, "col": j + 1.0, "value": float(ce[i, j])})
    if pos.size > 0:
        for i in range(pos.shape[0]):
            for j in range(pos.shape[1]):
                records.append({"metric": 2.0, "row": i + 1.0, "col": j + 1.0, "value": float(pos[i, j])})
    return pd.DataFrame(records, columns=["metric", "row", "col", "value"])


def write_all_tables(model_dir: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    t3 = build_table_iii_moments(model_dir)
    p = out_dir / "table_iii_moments_model.csv"
    save_table(t3, p, out_dir / "table_iii_moments_model.xlsx")
    written.append(p)

    t5 = build_table_v_macro_changes(model_dir)
    p = out_dir / "table_v_macro_changes_tax_reform.csv"
    save_table(t5, p, out_dir / "table_v_macro_changes_tax_reform.xlsx")
    written.append(p)

    t6 = build_table_vi_welfare(model_dir)
    p = out_dir / "table_vi_welfare_tax_reform.csv"
    save_table(t6, p, out_dir / "table_vi_welfare_tax_reform.xlsx")
    written.append(p)

    t7 = build_table_vii_group_welfare(model_dir)
    p = out_dir / "table_vii_welfare_by_group.csv"
    save_table(t7, p, out_dir / "table_vii_welfare_by_group.xlsx")
    written.append(p)

    t4 = build_table_iv_return_distribution(model_dir)
    p = out_dir / "table_iv_return_distribution.csv"
    save_table(t4, p, out_dir / "table_iv_return_distribution.xlsx")
    written.append(p)

    tx = build_table_x_decomposition(model_dir)
    p = out_dir / "table_x_decomposition.csv"
    save_table(tx, p, out_dir / "table_x_decomposition.xlsx")
    written.append(p)

    tb3 = build_table_b3_welfare_distribution(model_dir)
    p = out_dir / "table_b3_welfare_distribution.csv"
    save_table(tb3, p, out_dir / "table_b3_welfare_distribution.xlsx")
    written.append(p)

    return written

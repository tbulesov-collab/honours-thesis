#!/usr/bin/env python3
"""Build 2022 SCF entrepreneur moments under alternative definitions.

Inputs are the official Federal Reserve 2022 summary CSV and full Stata file.
The script merges the five implicates by (YY1, Y1), uses the supplied WGT
(X42001/5), and writes a compact definition bridge for calibration sensitivity.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:
    raise SystemExit(
        "pandas and numpy are required; run with python3"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "calibration" / "scf_2022_definition_bridge.csv"

SUMMARY_COLUMNS = [
    "Y1",
    "YY1",
    "WGT",
    "INCOME",
    "WAGEINC",
    "BUSSEFARMINC",
    "INTDIVINC",
    "SSRETINC",
    "NETWORTH",
    "NWPCTLECAT",
]


def weighted_share(indicator: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(weights * indicator) / np.sum(weights))


def build(summary_csv: Path, full_dta: Path) -> list[dict[str, object]]:
    summary = pd.read_csv(summary_csv, usecols=SUMMARY_COLUMNS)
    raw = pd.read_stata(
        full_dta,
        columns=["y1", "yy1", "x3104"],
        convert_categoricals=False,
    ).rename(columns=str.upper)
    data = summary.merge(raw, on=["Y1", "YY1"], validate="one_to_one")
    if len(data) != 22_975 or data["YY1"].nunique() != 4_595:
        raise ValueError("unexpected 2022 SCF public-file dimensions")

    weights = data["WGT"].to_numpy(float)
    wealth = data["NETWORTH"].to_numpy(float)
    top1 = data["NWPCTLECAT"].to_numpy() == 12
    business = data["BUSSEFARMINC"].to_numpy(float)
    model_flow_income = (
        data["BUSSEFARMINC"]
        + data["WAGEINC"]
        + data["INTDIVINC"]
        + data["SSRETINC"]
    ).to_numpy(float)

    active_manager = data["X3104"].to_numpy() == 1
    model_flow_majority = (model_flow_income > 0) & (
        business > 0.5 * model_flow_income
    )
    total_income = data["INCOME"].to_numpy(float)
    total_income_majority = (total_income > 0) & (business > 0.5 * total_income)

    definitions = [
        (
            "active_manager_paper_proxy",
            active_manager,
            "X3104=1; paper-continuity proxy for active business owners",
        ),
        (
            "business_majority_model_flow",
            model_flow_majority,
            "BUSSEFARMINC > 50% of BUSSEFARMINC+WAGEINC+INTDIVINC+SSRETINC",
        ),
        (
            "active_manager_and_business_majority",
            active_manager & model_flow_majority,
            "X3104=1 and business income is a majority of model-comparable flows",
        ),
        (
            "business_majority_total_scf_income",
            total_income_majority,
            "BUSSEFARMINC > 50% of Federal Reserve INCOME",
        ),
    ]

    rows: list[dict[str, object]] = []
    total_wealth = np.sum(weights * wealth)
    top1_weight = weights * top1
    for name, indicator, description in definitions:
        rows.append(
            {
                "definition_id": name,
                "population_share": weighted_share(indicator, weights),
                "wealth_share": float(
                    np.sum(weights * wealth * indicator) / total_wealth
                ),
                "entrepreneur_share_top1": weighted_share(indicator, top1_weight),
                "unweighted_implicate_records": int(np.sum(indicator)),
                "definition": description,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-csv", type=Path, required=True)
    parser.add_argument("--full-dta", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = build(args.summary_csv, args.full_dta)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {args.output}")
    for row in rows:
        print(
            f"{row['definition_id']:<39} "
            f"population={row['population_share']:.4%} "
            f"wealth={row['wealth_share']:.4%} "
            f"top1={row['entrepreneur_share_top1']:.4%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

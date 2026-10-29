#!/usr/bin/env python3
"""Compute 2022 SCF entrepreneur-moment standard errors.

Imputation variance is the sample variance across the five implicates.
Sampling variance is the sample variance across the 999 Federal Reserve
bootstrap estimates on implicate 1. The combined variance is
1.2 * imputation_variance + sampling_variance, following the SCF codebook.
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
DEFAULT_OUTPUT = ROOT / "calibration" / "scf_2022_standard_errors.csv"
SUMMARY_COLUMNS = ["Y1", "YY1", "WGT", "NETWORTH", "NWPCTLECAT"]


def ratios(data: pd.DataFrame, weights: np.ndarray) -> np.ndarray:
    active = (data["X3104"].to_numpy() == 1).astype(float)
    wealth = data["NETWORTH"].to_numpy(float)
    top1 = (data["NWPCTLECAT"].to_numpy() == 12).astype(float)
    return np.array(
        [
            np.sum(weights * active) / np.sum(weights),
            np.sum(weights * wealth * active) / np.sum(weights * wealth),
            np.sum(weights * top1 * active) / np.sum(weights * top1),
        ]
    )


def compute(summary_csv: Path, full_dta: Path, replicate_dta: Path) -> list[dict]:
    summary = pd.read_csv(summary_csv, usecols=SUMMARY_COLUMNS)
    raw = pd.read_stata(
        full_dta,
        columns=["y1", "yy1", "x3104"],
        convert_categoricals=False,
    ).rename(columns=str.upper)
    data = summary.merge(raw, on=["Y1", "YY1"], validate="one_to_one")
    data["IMPLICATE"] = data["Y1"] - 10 * data["YY1"]
    if len(data) != 22_975 or sorted(data["IMPLICATE"].unique()) != [1, 2, 3, 4, 5]:
        raise ValueError("unexpected 2022 SCF implicate structure")

    implicate_estimates = np.vstack(
        [
            ratios(group, group["WGT"].to_numpy(float))
            for _, group in data.groupby("IMPLICATE", sort=True)
        ]
    )
    # Report the same pooled five-implicate point estimate used in the
    # versioned calibration targets. The implicate-specific estimates below
    # are used only to estimate imputation variance.
    estimates = ratios(data, data["WGT"].to_numpy(float))
    imputation_variance = implicate_estimates.var(axis=0, ddof=1)

    first = data.loc[data["IMPLICATE"] == 1].copy()
    replicate = pd.read_stata(replicate_dta, convert_categoricals=False).rename(
        columns=str.upper
    )
    first = first.merge(replicate, on=["Y1", "YY1"], validate="one_to_one")
    if len(first) != 4_595:
        raise ValueError("replicate weights did not match the first implicate")

    weight_columns = [f"WT1B{i}" for i in range(1, 1000)]
    multiplicity_columns = [f"MM{i}" for i in range(1, 1000)]
    replicate_weights = np.nan_to_num(
        first[weight_columns].to_numpy(float), nan=0.0
    ) * np.nan_to_num(first[multiplicity_columns].to_numpy(float), nan=0.0)

    active = (first["X3104"].to_numpy() == 1).astype(float)
    wealth = first["NETWORTH"].to_numpy(float)
    top1 = (first["NWPCTLECAT"].to_numpy() == 12).astype(float)
    replicate_estimates = np.vstack(
        [
            (active @ replicate_weights) / replicate_weights.sum(axis=0),
            ((wealth * active) @ replicate_weights)
            / (wealth @ replicate_weights),
            ((top1 * active) @ replicate_weights) / (top1 @ replicate_weights),
        ]
    ).T
    sampling_variance = replicate_estimates.var(axis=0, ddof=1)
    combined_se = np.sqrt(1.2 * imputation_variance + sampling_variance)

    ids = [
        "entrepreneur_population_share",
        "entrepreneur_wealth_share",
        "entrepreneur_share_top1",
    ]
    labels = [
        "Population share of entrepreneurs",
        "Wealth share of entrepreneurs",
        "Population share of entrepreneurs in top 1%",
    ]
    rows = []
    for index, (moment_id, label) in enumerate(zip(ids, labels)):
        rows.append(
            {
                "moment_id": moment_id,
                "label": label,
                "estimate": estimates[index],
                "imputation_se": np.sqrt(imputation_variance[index]),
                "sampling_se": np.sqrt(sampling_variance[index]),
                "combined_se": combined_se[index],
                "ci95_lower": estimates[index] - 1.96 * combined_se[index],
                "ci95_upper": estimates[index] + 1.96 * combined_se[index],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-csv", type=Path, required=True)
    parser.add_argument("--full-dta", type=Path, required=True)
    parser.add_argument("--replicate-dta", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = compute(args.summary_csv, args.full_dta, args.replicate_dta)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {args.output}")
    print(f"{'Moment':48} {'Estimate':>10} {'SE':>10} {'95% CI':>23}")
    print("-" * 94)
    for row in rows:
        print(
            f"{row['label'][:48]:48} "
            f"{row['estimate']:10.2%} {row['combined_se']:10.2%} "
            f"[{row['ci95_lower']:.2%}, {row['ci95_upper']:.2%}]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

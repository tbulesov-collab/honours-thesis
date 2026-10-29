#!/usr/bin/env python3
"""Rebuild the seven audited 2022 SCF definitions from bundled public archives.

Run from any directory: python3 scripts/rebuild_scf_audit.py --check
The released reference CSV is read only. No model runs or network access occur.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "scf2022"
REFERENCE = ROOT / "replication/calibration/scf_2022_definition_moments_audited.csv"
MOMENTS = (
    "entrepreneur_population_share", "entrepreneur_wealth_share",
    "entrepreneur_share_top1", "wealth_top1_share",
)
FIELDS = ("definition_id", *MOMENTS, "definition")
SUMMARY_COLUMNS = [
    "Y1", "YY1", "WGT", "NETWORTH", "INCOME", "WAGEINC",
    "BUSSEFARMINC", "INTDIVINC", "SSRETINC", "PENACCTWD",
]
RAW_INCOME = ["X5702", "X5704", "X5706", "X5708", "X5710", "X5714", "X5722"]
# Federal Reserve bulletin.macro.txt, YEAR=2022, CPILAG=4315/3992.
# These are the frozen extract's 2021-income-to-2022-dollar units. Retain the
# exact ratio: recovering it from rounded CSV wages changes strict >50% ties.
INCOME_SCALE = 4315 / 3992
DEFINITIONS = {
    "active_manager_paper_proxy":
        "X3104 == 1; current active private-business management by someone in the family",
    "business_majority_model_flow":
        "D > 0 and BUSSEFARMINC > 0.5*D; D=BUSSEFARMINC+WAGEINC+INTDIVINC+SSRETINC",
    "active_manager_and_business_majority":
        "X3104 == 1 AND business_majority_model_flow",
    "business_majority_total_scf_income":
        "INCOME > 0 and BUSSEFARMINC > 0.5*INCOME",
    "sole_prop_farm_only_diagnostic":
        "D > 0 and CPI*X5704 > 0.5*D; removes mixed X5714 from numerator only, including legitimate other-business income",
    "business_majority_without_pension_withdrawals":
        "D-PENACCTWD > 0 and BUSSEFARMINC > 0.5*(D-PENACCTWD)",
    "business_majority_minus1_as_zero":
        "Broad flow proxy with documented raw -1 (nothing) income codes set to zero; other negative income retained",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_archives(directory: Path) -> dict:
    manifest = json.loads((directory / "MANIFEST.json").read_text())
    for name, record in manifest["files"].items():
        if Path(name).name != name:
            raise ValueError(f"Invalid archive name in manifest: {name}")
        path = directory / name
        if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise ValueError(f"Archive differs from the frozen input: {path}")
    return manifest


def load_data(directory: Path) -> tuple[pd.DataFrame, float]:
    with ZipFile(directory / "scfp2022excel.zip") as archive:
        with archive.open("SCFP2022.csv") as stream:
            summary = pd.read_csv(stream, usecols=SUMMARY_COLUMNS)
    with ZipFile(directory / "scf2022s.zip") as archive:
        raw = pd.read_stata(
            io.BytesIO(archive.read("p22i6.dta")),
            columns=["y1", "yy1", "x3104", "x42001", *[s.lower() for s in RAW_INCOME]],
            convert_categoricals=False,
        ).rename(columns=str.upper)
    data = summary.merge(raw, on=["Y1", "YY1"], how="outer",
                         validate="one_to_one", indicator=True)
    if (len(data) != 22975 or data.YY1.nunique() != 4595
            or not (data["_merge"] == "both").all()):
        raise ValueError("The expected 4,595-family SCF merge was not obtained")
    data["implicate"] = data.Y1 - 10 * data.YY1
    if (sorted(data.implicate.unique()) != [1, 2, 3, 4, 5]
            or not (data.groupby("YY1").implicate.nunique() == 5).all()):
        raise ValueError("Expected all five implicates for every family")
    required = list(dict.fromkeys([*SUMMARY_COLUMNS, "X3104", "X42001", *RAW_INCOME]))
    if not np.isfinite(data[required].to_numpy()).all():
        raise ValueError("Non-finite values in an input used by the audit")
    if not (data.WGT > 0).all() or not np.allclose(data.WGT, data.X42001 / 5,
                                                rtol=1e-7, atol=1e-6):
        raise ValueError("Unexpected survey weights")

    # Validate the frozen income units before using raw X5704 or recoding the
    # documented -1 values in the two diagnostic definitions. The published
    # summary components themselves remain the inputs to the main definitions.
    income_scale = INCOME_SCALE
    counterparts = {
        "WAGEINC": income_scale * data.X5702,
        "BUSSEFARMINC": income_scale * (data.X5704 + data.X5714),
        "INTDIVINC": income_scale * (data.X5706 + data.X5708 + data.X5710),
        "SSRETINC": income_scale * data.X5722 + data.PENACCTWD,
    }
    for name, values in counterparts.items():
        # The official CSV rounds some dollar values; this check permits that
        # serialization precision, not a change to the classification rule.
        if not np.allclose(data[name], values, rtol=1e-8, atol=1e-5):
            raise ValueError(f"Raw income reconstruction does not match {name}")
    return data, income_scale


def classifications(data: pd.DataFrame, income_scale: float) -> pd.DataFrame:
    business = data.BUSSEFARMINC
    denominator = business + data.WAGEINC + data.INTDIVINC + data.SSRETINC
    active = data.X3104 == 1
    majority = (denominator > 0) & (business > 0.5 * denominator)
    without_withdrawals = denominator - data.PENACCTWD
    # Only exactly -1 is changed. In particular, retain genuine negative
    # income and the public-file negative-income value -9.
    # Apply only the recoding increment to the supplied summary values. A full
    # reconstruction from raw components would also change CSV rounding at
    # exactly-half-income boundaries, which was not part of the saved audit.
    corrected_business = business + income_scale * (data[["X5704", "X5714"]] == -1).sum(axis=1)
    corrected_denominator = denominator + income_scale * (data[RAW_INCOME] == -1).sum(axis=1)
    return pd.DataFrame({
        "active_manager_paper_proxy": active,
        "business_majority_model_flow": majority,
        "active_manager_and_business_majority": active & majority,
        "business_majority_total_scf_income": (data.INCOME > 0) & (business > 0.5 * data.INCOME),
        "sole_prop_farm_only_diagnostic": (denominator > 0) & (income_scale * data.X5704 > 0.5 * denominator),
        "business_majority_without_pension_withdrawals": (without_withdrawals > 0) & (business > 0.5 * without_withdrawals),
        "business_majority_minus1_as_zero": (corrected_denominator > 0) & (corrected_business > 0.5 * corrected_denominator),
    }, index=data.index)


def calculate(data: pd.DataFrame, indicators: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    estimates = []
    for implicate, group in data.groupby("implicate", sort=True):
        w = group.WGT.to_numpy(float)
        wealth = group.NETWORTH.to_numpy(float)
        total_wealth = float(w @ wealth)
        if total_wealth <= 0:
            raise ValueError("Non-positive aggregate wealth")
        # Aggregate equal wealth before assigning the fractional upper-tail
        # weight. Each observation tied at the cutoff gets the same fraction.
        weighted = pd.DataFrame({"NETWORTH": wealth, "weight": w}, index=group.index)
        for name in DEFINITIONS:
            weighted[name] = w * indicators.loc[group.index, name].to_numpy()
        bins = weighted.groupby("NETWORTH").sum().sort_index(ascending=False)
        mass = bins.weight.to_numpy(float)
        used = np.clip(0.01 * mass.sum() - (np.cumsum(mass) - mass), 0, mass)
        if not np.isclose(used.sum(), 0.01 * mass.sum(), rtol=1e-10):
            raise ValueError("Top-one-percent population mass check failed")
        wealth_top1 = float(used @ bins.index.to_numpy(float) / total_wealth)
        for name in DEFINITIONS:
            indicator = indicators.loc[group.index, name].to_numpy()
            estimates.append({
                "implicate": int(implicate), "definition_id": name,
                "entrepreneur_population_share": float(w @ indicator / w.sum()),
                "entrepreneur_wealth_share": float((w * indicator) @ wealth / total_wealth),
                "entrepreneur_share_top1": float(used @ (bins[name].to_numpy(float) / mass) / used.sum()),
                "wealth_top1_share": wealth_top1,
            })
    rows = []
    for name, description in DEFINITIONS.items():
        subset = [row for row in estimates if row["definition_id"] == name]
        rows.append({"definition_id": name,
                     **{key: float(np.mean([r[key] for r in subset])) for key in MOMENTS},
                     "definition": description})
    return rows, estimates


def compare(rows: list[dict], reference: Path, tolerance: float) -> dict:
    with reference.open(newline="") as stream:
        expected = list(csv.DictReader(stream))
    if [r["definition_id"] for r in rows] != [r["definition_id"] for r in expected]:
        raise ValueError("Reference definition names/order differ")
    differences = []
    exact = 0
    for actual, saved in zip(rows, expected):
        if actual["definition"] != saved["definition"]:
            raise ValueError(f"Definition text differs: {actual['definition_id']}")
        for key in MOMENTS:
            target = float(saved[key])
            gap = abs(actual[key] - target)
            exact += actual[key] == target
            differences.append({"definition_id": actual["definition_id"], "moment": key,
                                "recomputed": actual[key], "reference": target,
                                "absolute_difference": gap})
    maximum = max(row["absolute_difference"] for row in differences)
    return {"ok": maximum <= tolerance, "numeric_cells": len(differences),
            "exact_float_matches": exact, "absolute_tolerance": tolerance,
            "maximum_absolute_difference": maximum, "comparisons": differences}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--check", action="store_true", help="compare all 28 cells with the released audited CSV")
    parser.add_argument("--tolerance", type=float, default=1e-12, help="absolute tolerance in fraction units")
    parser.add_argument("--output", type=Path, help="write rebuilt CSV to a new path")
    parser.add_argument("--report", type=Path, help="write input hashes, per-implicate estimates and comparison JSON")
    args = parser.parse_args()
    if not np.isfinite(args.tolerance) or args.tolerance < 0:
        parser.error("tolerance must be finite and non-negative")
    for target in (args.output, args.report):
        if target is not None and (target.resolve() == args.reference.resolve() or target.exists()):
            parser.error(f"Refusing to overwrite an existing file: {target}")
    manifest = verify_archives(args.data_dir)
    data, income_scale = load_data(args.data_dir)
    rows, estimates = calculate(data, classifications(data, income_scale))
    comparison = compare(rows, args.reference, args.tolerance) if args.check else None
    report = {"schema": 1, "model_executed": False,
              "input_archive_sha256": {n: r["sha256"] for n, r in manifest["files"].items()},
              "families": int(data.YY1.nunique()), "records": len(data), "implicates": 5,
              "income_scale_2021_to_2022": income_scale,
              "income_scale_definition": "4315/3992; Federal Reserve 2022 CPILAG",
              "reference_sha256": sha256(args.reference) if args.check else None,
              "comparison": comparison, "estimates": rows, "implicate_estimates": estimates}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    for row in rows:
        print(f"{row['definition_id']}: " + ", ".join(f"{k}={row[k]:.12g}" for k in MOMENTS))
    if comparison:
        print(json.dumps({k: v for k, v in comparison.items() if k != "comparisons"}, indent=2))
        return 0 if comparison["ok"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

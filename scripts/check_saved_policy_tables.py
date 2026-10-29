#!/usr/bin/env python3
"""Reproduce saved numerical table evidence without importing or running the model.

The index pins repository-relative reports, result records and context manifests.
Historical absolute paths in those manifests are provenance strings only: this
checker normalises their benchmark suffixes and never opens external files or
the omitted equilibrium arrays. Default execution is read-only; --write exports
the checked JSON and --show-table prints the numerical rows as Markdown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "replication/validation/policy_table_inputs/index.json"
DEFAULT_OUTPUT = ROOT / "replication/validation/saved_comparison.json"
TABLE_IDS = ("separate_wealth", "joint_estate_40", "joint_estate_zero",
             "joint_subsidy_80", "joint_subsidy_95")
ALL_IDS = (*TABLE_IDS, "joint_subsidy_95_tie")
TOLERANCES = {"equilibrium_residual": 1e-7, "aggregate_residual": 1e-6,
              "revenue_relative_gap": 1e-4}
RAW_MATCHES = {
    "tau_w": ("Wealth_Tax_Above", 1), "tau_k": ("Tau_K", 1),
    "tau_bq": ("Tau_BQ", 1), "tau_l": ("Average_Labor_Tax", 1),
    "psi": ("Psi", 1), "ce2_newborn": ("CE2_NB(exp)", 1),
    "ce2_population": ("CE2_Pop(exp)", 1), "revenue": ("GBAR", 1),
    "top1_wealth_share": ("Wealth_Top_1%", 1),
    "equilibrium_residual": ("Equilibrium_Residual", 1),
    "aggregate_residual": ("Aggregate_Residual", 1),
    "revenue_relative_gap": ("Revenue_Relative_Gap", 1),
}
GROWTH_KEYS = (("Capital change", "KBAR"),
               ("Intermediate TFP change", "TFP_Q"),
               ("Effective labour change", "NBAR"),
               ("Output change", "YBAR"), ("Consumption change", "CBAR"))
BASE_KEYS = {"GBAR", "KBAR", "QBAR", "NBAR", "YBAR", "CBAR", "TFP_Q"}
POLICY_KEYS = BASE_KEYS | {v[0] for v in RAW_MATCHES.values()} | {
    "Av.Hours", "Capital_Tax/_GDP", "Labor_Tax/GDP", "Estate_Tax/GDP",
    "Statistics_Schema", "Evaluation_Schema", "Equilibrium_Converged",
    "Budget_Tolerance",
}


class ValidationError(ValueError):
    """A saved input or its numerical reconciliation failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def close(actual: float, expected: float, label: str, tolerance: float = 1e-10) -> None:
    require(math.isfinite(actual) and math.isfinite(expected), f"Non-finite {label}")
    require(math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance),
            f"{label}: {actual!r} != {expected!r}")


def relative_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in name,
            f"Unsafe repository-relative path: {name}")
    return path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_pinned(spec: dict) -> bytes:
    name = spec["path"]
    path = ROOT / relative_path(name)
    require(path.is_file() and not path.is_symlink(), f"Missing regular input: {name}")
    require(path.resolve().is_relative_to(ROOT), f"Input escapes repository: {name}")
    data = path.read_bytes()
    require(digest(data) == spec["sha256"], f"Hash mismatch: {name}")
    return data


def parse_report(data: bytes, required: set[str], label: str) -> dict[str, float]:
    values = {}
    for line in data.decode("utf-8").splitlines():
        fields = line.split()
        if fields and fields[0] in required:
            require(len(fields) == 2, f"Malformed {fields[0]} in {label}")
            require(fields[0] not in values, f"Duplicate {fields[0]} in {label}")
            value = float(fields[1].replace("D", "E").replace("d", "e"))
            require(math.isfinite(value), f"Non-finite {fields[0]} in {label}")
            values[fields[0]] = value
    require(required <= values.keys(), f"Missing fields in {label}: {sorted(required - values.keys())}")
    # Unused legacy fields, including NaN population CE1, are outside this check.
    return values


def benchmark_hashes(context: dict, benchmark_path: str) -> dict[str, str]:
    """Extract only portable suffixes; do not dereference historical path prefixes."""
    recorded = context.get("benchmark", "").replace("\\", "/").rstrip("/")
    require(recorded == benchmark_path or recorded.endswith("/" + benchmark_path),
            "Context uses a different benchmark")
    marker = benchmark_path + "/"
    hashes = {}
    for name, sha in context["files"].items():
        if marker in name:
            suffix = name.split(marker, 1)[1]
            relative_path(suffix)
            require(suffix not in hashes, f"Duplicate benchmark entry: {suffix}")
            hashes[suffix] = sha
    require("output.txt" in hashes and "Bench_Files/DBN" in hashes,
            "Context omits benchmark report or distribution provenance")
    return hashes


def check_production(raw: dict[str, float], alpha: float, label: str) -> None:
    require(all(raw[k] > 0 for k in ("KBAR", "QBAR", "NBAR", "YBAR", "CBAR")),
            f"Non-positive aggregate in {label}")
    close(raw["TFP_Q"], raw["QBAR"] / raw["KBAR"], f"{label}: Q/K")
    close(raw["YBAR"], raw["QBAR"] ** alpha * raw["NBAR"] ** (1 - alpha),
          f"{label}: production identity")


def build_comparison(index_path: Path) -> dict:
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    require(index["schema_version"] == 1, "Unsupported input-index schema")
    require(index["table_policy_ids"] == list(TABLE_IDS), "Wrong table policy order")
    require(tuple(p["id"] for p in index["policies"]) == ALL_IDS,
            "Expected five table policies and one auxiliary tie policy")
    alpha = index["alpha"]
    close(alpha, 0.4, "Production exponent")
    close(index["reporting_tie_pp"], 0.15, "Reporting tie convention")
    benchmark = index["benchmark"]
    benchmark_path = str(relative_path(benchmark["source_directory"]))
    base = parse_report(read_pinned(benchmark["output"]), BASE_KEYS, "benchmark")
    check_production(base, alpha, "benchmark")
    require(base["GBAR"] > 0, "Benchmark spending requirement must be positive")

    contexts = {}
    common_hashes = None
    for key, spec in index["contexts"].items():
        context = json.loads(read_pinned(spec))
        require(context["schema"] == 2 and context["fixed_labor"] is False,
                f"{key}: expected residual-labour context")
        close(context["budget_tolerance"], TOLERANCES["revenue_relative_gap"],
              f"{key}: budget tolerance")
        hashes = benchmark_hashes(context, benchmark_path)
        require(hashes["output.txt"] == benchmark["output"]["sha256"],
                f"{key}: benchmark-report hash differs")
        if common_hashes is None:
            common_hashes = hashes
        require(hashes == common_hashes, f"{key}: benchmark-state hashes differ")
        contexts[key] = context

    records = []
    raws = {}
    for policy in index["policies"]:
        policy_id = policy["id"]
        record = json.loads(read_pinned(policy["record"]))
        context_id = policy["context_id"]
        require(record["context_id"] == context_id and context_id in contexts,
                f"{policy_id}: wrong context")
        require(record["status"] == "ok" and record["feasible"] is True
                and record["equilibrium_converged"] is True and record["schema"] == 2,
                f"{policy_id}: saved result is not an accepted equilibrium")
        if "benchmark" in record:
            reference = record["benchmark"].replace("\\", "/").rstrip("/")
            require(reference == benchmark_path or reference.endswith("/" + benchmark_path),
                    f"{policy_id}: wrong result benchmark")
        require(record["output_sha256"] == policy["output"]["sha256"],
                f"{policy_id}: record/report hash differs")
        require(policy["output"]["path"] == "replication/" + record["result_directory"] + "/output_exp.txt",
                f"{policy_id}: report path differs from result provenance")
        raw = parse_report(read_pinned(policy["output"]), POLICY_KEYS, policy_id)
        check_production(raw, alpha, policy_id)
        for field, (raw_key, multiplier) in RAW_MATCHES.items():
            close(record[field], multiplier * raw[raw_key], f"{policy_id}: {field}")
        for field, limit in TOLERANCES.items():
            require(0 <= record[field] <= limit, f"{policy_id}: exceeds {field} tolerance")
        for field, value in zip(("tau_w", "tau_k", "tau_bq"), policy["rates"]):
            close(record[field], value, f"{policy_id}: expected {field}")
        context = contexts[context_id]
        for field, bounds in zip(("tau_w", "tau_k", "tau_bq"), context["bounds"]):
            require(bounds[0] <= record[field] <= bounds[1], f"{policy_id}: {field} outside bounds")
        require(context["labor_bounds"][0] <= record["tau_l"] <= context["labor_bounds"][1],
                f"{policy_id}: labour tax outside bounds")
        close(record["tau_l"] + record["psi"], 1, f"{policy_id}: labour-tax complement")
        close(raw["Statistics_Schema"], 3, f"{policy_id}: statistics schema")
        close(raw["Evaluation_Schema"], 2, f"{policy_id}: evaluation schema")
        close(raw["Equilibrium_Converged"], 1, f"{policy_id}: raw convergence flag")
        close(raw["Budget_Tolerance"], 1e-4, f"{policy_id}: raw budget tolerance")
        gap = abs(record["revenue"] - base["GBAR"])
        close(record["revenue_gap"], gap, f"{policy_id}: absolute fiscal gap")
        close(record["revenue_relative_gap"], gap / base["GBAR"],
              f"{policy_id}: relative fiscal gap")
        for field, raw_key in (("output_growth", "YBAR"), ("consumption_growth", "CBAR")):
            close(record[field], 100 * (raw[raw_key] / base[raw_key] - 1), f"{policy_id}: {field}")
        # Export finite numerical fields and portable provenance, not historical paths.
        numerical = {k: v for k, v in record.items() if isinstance(v, (bool, int, float))}
        records.append({"id": policy_id, "name": policy["name"], "status": record["status"],
                        "context_id": context_id, "key": record["key"],
                        "source_record": policy["record"], "source_output": policy["output"],
                        "record": numerical, "raw": raw})
        raws[policy_id] = raw

    table_records = records[:len(TABLE_IDS)]
    cells = []

    def row(label: str, values: list[float], digits: int = 2, percent: bool = True) -> None:
        cells.append({"label": label, "raw_values": values, "digits": digits, "percent": percent,
                      "display_values": [f"{v:.{digits}f}" for v in values]})

    for label, field, digits in (("Wealth tax", "tau_w", 2),
                                 ("Capital-income tax", "tau_k", 2),
                                 ("Estate tax", "tau_bq", 0),
                                 ("Labour tax", "tau_l", 2)):
        row(label, [100 * r["record"][field] for r in table_records], digits)
    for label, key in GROWTH_KEYS:
        row(label, [100 * (raws[p][key] / base[key] - 1) for p in TABLE_IDS])
    row("Average hours", [raws[p]["Av.Hours"] for p in TABLE_IDS], percent=False)
    for label, key in (("Net lifetime capital tax / GDP", "Capital_Tax/_GDP"),
                       ("Labour tax / GDP", "Labor_Tax/GDP"),
                       ("Estate tax / GDP", "Estate_Tax/GDP")):
        row(label, [100 * raws[p][key] for p in TABLE_IDS])
    for label, field in (("Newborn CE2", "ce2_newborn"), ("Population CE2", "ce2_population")):
        row(label, [r["record"][field] for r in table_records])
    row("Top 1% wealth share", [100 * raws[p]["Wealth_Top_1%"] for p in TABLE_IDS])
    require({r["label"]: r["display_values"] for r in cells} == index["reported_rows"],
            "Computed rows differ from the current reported table")

    separate, joint = raws[TABLE_IDS[0]], raws[TABLE_IDS[1]]
    contributions = {
        "capital": 100 * alpha * math.log(joint["KBAR"] / separate["KBAR"]),
        "intermediate_productivity": 100 * alpha * math.log(joint["TFP_Q"] / separate["TFP_Q"]),
        "effective_labour": 100 * (1 - alpha) * math.log(joint["NBAR"] / separate["NBAR"]),
    }
    total = 100 * math.log(joint["YBAR"] / separate["YBAR"])
    close(sum(contributions.values()), total, "Output log decomposition")
    displayed_decomposition = {k: f"{v:.2f}" for k, v in contributions.items()}
    displayed_decomposition["total"] = f"{total:.2f}"
    require(displayed_decomposition == index["reported_output_decomposition"],
            "Output decomposition differs from the current reported values")
    estate_gain = raws["joint_estate_zero"]["CE2_NB(exp)"] - raws["joint_estate_40"]["CE2_NB(exp)"]
    close(estate_gain, index["expected_estate_removal_gain_pp"], "Matched estate-removal gain")
    tie_gap = raws["joint_subsidy_95"]["CE2_NB(exp)"] - raws["joint_subsidy_95_tie"]["CE2_NB(exp)"]
    close(tie_gap, index["expected_subsidy_95_gap_pp"], "95% subsidy tie gap")
    require(0 < tie_gap < index["reporting_tie_pp"], "95% subsidy policies are not tied")
    require(f"{estate_gain:.2f}" == "3.67" and f"{tie_gap:.3f}" == "0.061",
            "Key welfare differences no longer reproduce the reported values")
    return {
        "schema_version": 2,
        "scope": "Arithmetic reproduction of the current five-column stationary joint-policy table, "
                 "output accounting, matched estate removal and the 95% subsidy tie. No model execution; "
                 "no certification of Euler/Bellman, asset-grid/tail or transition accuracy.",
        "inputs_index_sha256": digest(index_bytes),
        "benchmark_source": benchmark["output"]["path"],
        "benchmark_sha256": benchmark["output"]["sha256"],
        "benchmark_state_fingerprint": digest(json.dumps(common_hashes, sort_keys=True).encode()),
        "columns": [{"id": r["id"], "name": r["name"]} for r in table_records],
        "records": table_records, "auxiliary_records": records[len(TABLE_IDS):],
        "table_cells": cells, "output_log_contributions": contributions,
        "output_log_difference": total,
        "output_log_shares_percent": {k: 100 * v / total for k, v in contributions.items()},
        "welfare_checks": {"estate_removal_gain_pp": estate_gain,
                           "subsidy_95_gap_pp": tie_gap,
                           "reporting_tie_pp": index["reporting_tie_pp"], "subsidy_95_tied": True},
    }


def markdown_table(comparison: dict) -> str:
    lines = ["| Outcome | " + " | ".join(c["name"] for c in comparison["columns"]) + " |",
             "|---|" + "---:|" * len(comparison["columns"])]
    for cell in comparison["table_cells"]:
        suffix = "%" if cell["percent"] else ""
        lines.append("| " + cell["label"] + " | "
                     + " | ".join(v + suffix for v in cell["display_values"]) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX,
                        help="Input index; its data paths remain relative to this repository")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Comparison JSON to check, or intentionally refresh with --write")
    parser.add_argument("--write", action="store_true", help="Export the checked comparison JSON")
    parser.add_argument("--show-table", action="store_true", help="Print the checked numerical rows")
    args = parser.parse_args()
    try:
        comparison = build_comparison(args.index)
        if args.write:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(comparison, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        else:
            require(args.output.is_file(), "Comparison JSON missing; generate it with --write")
            require(json.loads(args.output.read_text()) == comparison,
                    "Comparison JSON differs; inspect the inputs before refreshing with --write")
        if args.show_table:
            print(markdown_table(comparison))
        print("PASS: 5 table columns, 16 rows, 6 feasible saved policies; output identity, "
              "estate gain and subsidy tie verified. No model run.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

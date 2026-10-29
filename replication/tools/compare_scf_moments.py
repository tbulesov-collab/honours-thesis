#!/usr/bin/env python3
"""Compare benchmark model moments with the versioned 2022 SCF moments."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = ROOT / "calibration" / "scf_2022_moments.csv"
DEFAULT_SUMMARY = ROOT / "calibration" / "runs" / "scf_2022" / "best.json"
FALLBACK_RESULTS = ROOT / "Revision" / "Model_2.1_Local"


def read_key_values(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = raw_line.split()
        if len(fields) < 2:
            continue
        try:
            values[fields[0]] = float(fields[-1])
        except ValueError:
            continue
    return values


def fmt(value: float) -> str:
    return "--" if math.isnan(value) else f"{100.0 * value:8.2f}%"


def fmt_gap(value: float) -> str:
    return "--" if math.isnan(value) else f"{100.0 * value:+7.2f} pp"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument(
        "--results",
        type=Path,
        help="model output directory (default: corrected run recorded in best.json)",
    )
    args = parser.parse_args()

    if args.results is None:
        if DEFAULT_SUMMARY.exists():
            summary = json.loads(DEFAULT_SUMMARY.read_text())
            args.results = Path(summary["run_directory"])
        else:
            args.results = FALLBACK_RESULTS
            print(
                "WARNING: corrected benchmark summary not found; using archived "
                "pre-correction results."
            )

    with args.targets.open(newline="", encoding="utf-8") as stream:
        moments = list(csv.DictReader(stream))

    cache: dict[Path, dict[str, float]] = {}
    print(f"2022 SCF moments: {args.targets}")
    print(f"Model results:    {args.results}")
    print()
    print(f"{'Moment':48} {'Role':12} {'Original':>10} {'SCF 2022':>10} {'Model':>10} {'Gap':>11}")
    print("-" * 108)

    for moment in moments:
        data_value = float(moment["scf_2022_value"])
        original = float(moment["original_value"])
        model_value = math.nan
        model_file = moment["model_file"].strip()
        model_key = moment["model_key"].strip()
        if model_file and model_key:
            path = args.results / model_file
            if path not in cache:
                cache[path] = read_key_values(path)
            raw_value = cache[path].get(model_key, math.nan)
            model_value = raw_value * float(moment["model_scale"])
        gap = model_value - data_value if not math.isnan(model_value) else math.nan
        print(
            f"{moment['label'][:48]:48} {moment['role']:12} "
            f"{fmt(original):>10} {fmt(data_value):>10} "
            f"{fmt(model_value):>10} {fmt_gap(gap):>11}"
        )

    print("\nGap is model minus 2022 SCF, in percentage points.")
    print("Only rows marked 'target' replace SCF-derived calibration targets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

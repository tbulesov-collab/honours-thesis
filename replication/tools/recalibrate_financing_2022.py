#!/usr/bin/env python3
"""Recalibrate the borrowing constraint to the updated 2022 financing target.

The SCF entrepreneurial-process parameters are held at their staged 2022 values.
Only the maximum of the model's linearly increasing theta schedule is searched.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path

from benchmark_cache import BENCHMARK_STATE_FILES, complete_benchmark


ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "Compiled_Files_Baseline" / "GKK_Main.a"
TARGET_FILE = ROOT / "calibration" / "business_financing_2022.csv"
SCF_BEST = ROOT / "calibration" / "runs" / "scf_2022" / "best.json"
RUN_ROOT = ROOT / "calibration" / "runs" / "business_financing_2022"
CACHE_VERSION = "business-financing-fractional-percentiles-v2"
PUBLISHED_THETA_MAX = 2.8


def portable_run_directory(value: str, *, root: Path | None = None) -> Path:
    """Resolve released provenance paths inside this copy of the model.

    Some best.json files record the original machine's absolute path. Its calibration/runs
    suffix identifies the released location; never read another checkout merely
    because that old absolute path happens to exist on this computer.
    """
    path = Path(value)
    parts = path.parts
    if path.is_absolute():
        starts = [i for i in range(len(parts) - 1)
                  if parts[i:i + 2] == ("calibration", "runs")]
        if not starts:
            raise ValueError(f"Cannot relocate calibration run path: {value}")
        path = Path(*parts[starts[-1]:])
    model_root = ROOT if root is None else Path(root)
    folder = (model_root / path).resolve()
    folder.relative_to(model_root.resolve())
    return folder


def read_key_value(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    for raw in path.read_text(errors="replace").splitlines():
        fields = raw.strip().split()
        if len(fields) < 2:
            continue
        try:
            values[fields[0]] = float(fields[-1])
        except ValueError:
            pass
    return values


def financing_target() -> float:
    with TARGET_FILE.open(newline="", encoding="utf-8") as stream:
        rows = {row["component"]: row for row in csv.DictReader(stream)}
    return float(rows["business_financing_to_GDP"]["value"])


def scf_parameters() -> dict[str, float]:
    payload = json.loads(SCF_BEST.read_text())
    return {name: float(value) for name, value in payload["parameters"].items()}


def run_id(theta_max: float, parameters: dict[str, float]) -> str:
    payload = json.dumps(
        {"cache": CACHE_VERSION, "theta_max": theta_max, "scf": parameters},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def evaluate(
    theta_max: float, parameters: dict[str, float], threads: int
) -> tuple[float, Path]:
    if not 1.0 <= theta_max <= 6.0:
        raise ValueError("theta_max must lie between 1 and 6")

    # Reuse the SCF benchmark only when its parameters, theta and statistics
    # match. Old benchmarks must not bypass the percentile-cache version bump.
    if abs(theta_max - PUBLISHED_THETA_MAX) < 1e-12:
        scf_payload = json.loads(SCF_BEST.read_text())
        scf_folder = portable_run_directory(scf_payload["run_directory"])
        output_file = scf_folder / "output.txt"
        output = read_key_value(output_file) if output_file.exists() else {}
        theta_line = next((line for line in (output_file.read_text().splitlines() if output_file.exists() else [])
                           if line.split()[:1] == ["Theta"]), "")
        theta_values = theta_line.split()[1:10]
        if (complete_benchmark(scf_folder)
                and output.get("Statistics_Schema") == 3
                and scf_payload.get("parameters") == parameters
                and len(theta_values) == 9
                and abs(float(theta_values[-1]) - theta_max) < 1e-12):
            return output["Debt_Output"], scf_folder

    folder = RUN_ROOT / run_id(theta_max, parameters)
    result_file = folder / "result.json"
    if result_file.exists() and complete_benchmark(folder):
        result = json.loads(result_file.read_text())
        output = read_key_value(folder / "output.txt")
        if output.get("Statistics_Schema") != 3:
            raise ValueError("Cached benchmark uses old percentile statistics; recompute it")
        return output["Debt_Output"], folder

    folder.mkdir(parents=True, exist_ok=True)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("GKK_", "OMP_"))}
    env.update(
        {
            "OMP_NUM_THREADS": str(threads),
            "OMP_DYNAMIC": "FALSE",
            "OMP_NESTED": "FALSE",
            "GKK_RHO_Z": "0.1",
            "GKK_SIGMA_Z_EPS": f"{parameters['sigma_z_eps']:.16g}",
            "GKK_X_HI": f"{parameters['x_hi']:.16g}",
            "GKK_P1_X": f"{parameters['p1_x']:.16g}",
            "GKK_P2_X": f"{parameters['p2_x']:.16g}",
            "GKK_THETA_MAX": f"{theta_max:.16g}",
            "GKK_RESULT_FOLDER": str(folder.relative_to(ROOT)),
        }
    )
    with (folder / "run.log").open("w") as log:
        completed = subprocess.run(
            [str(EXE)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
        )
    if completed.returncode:
        raise RuntimeError(f"model failed; inspect {folder / 'run.log'}")

    output = read_key_value(folder / "output.txt")
    if output.get("Statistics_Schema") != 3:
        raise ValueError("Benchmark uses old percentile statistics; rebuild and recompute it")
    if not complete_benchmark(folder):
        raise ValueError("Benchmark state is incomplete; inspect the solver output")
    debt_output = output["Debt_Output"]
    result_file.write_text(
        json.dumps(
            {
                "cache_version": CACHE_VERSION,
                "theta_max": theta_max,
                "debt_output": debt_output,
                "scf_parameters": parameters,
            },
            indent=2,
        )
        + "\n"
    )
    return debt_output, folder


def build() -> None:
    subprocess.run(
        ["bash", "tools/run_mac.sh", "calibration-build"], cwd=ROOT, check=True
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--tolerance", type=float, default=0.001)
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--overwrite-best", action="store_true",
                        help="replace the existing best.json, which backs the paper")
    parser.add_argument(
        "--evaluate", type=float, metavar="THETA_MAX", help="evaluate one value only"
    )
    args = parser.parse_args()
    if args.threads < 1 or args.tolerance <= 0 or args.max_iterations < 1:
        parser.error("threads and max-iterations must be positive; tolerance must exceed zero")
    if not args.skip_build:
        build()
    if not EXE.exists():
        raise SystemExit(f"executable not found: {EXE}")

    target = financing_target()
    parameters = scf_parameters()
    if args.evaluate is not None:
        model, folder = evaluate(args.evaluate, parameters, args.threads)
        print(f"theta_max={args.evaluate:.8f} model={model:.8f} target={target:.8f}")
        print(f"gap={model-target:+.8f}; outputs={folder}")
        return 0

    low, high = PUBLISHED_THETA_MAX, 3.1
    model_low, folder_low = evaluate(low, parameters, args.threads)
    model_high, folder_high = evaluate(high, parameters, args.threads)
    while model_high < target and high < 6.0:
        low, model_low, folder_low = high, model_high, folder_high
        high = min(6.0, high + 0.6)
        model_high, folder_high = evaluate(high, parameters, args.threads)
    if not model_low <= target <= model_high:
        raise RuntimeError(
            f"target {target:.6f} is not bracketed by model values "
            f"{model_low:.6f} and {model_high:.6f}"
        )

    best = min(
        [(abs(model_low - target), low, model_low, folder_low),
         (abs(model_high - target), high, model_high, folder_high)]
    )
    for iteration in range(1, args.max_iterations + 1):
        middle = low + (target - model_low) * (high - low) / (model_high - model_low)
        middle = min(high - 1e-6, max(low + 1e-6, middle))
        model_middle, folder_middle = evaluate(middle, parameters, args.threads)
        candidate = (abs(model_middle - target), middle, model_middle, folder_middle)
        best = min(best, candidate)
        print(
            f"iteration {iteration}: theta_max={middle:.8f} "
            f"model={model_middle:.8f} gap={model_middle-target:+.8f}"
        )
        if candidate[0] <= args.tolerance:
            break
        if model_middle < target:
            low, model_low, folder_low = middle, model_middle, folder_middle
        else:
            high, model_high, folder_high = middle, model_middle, folder_middle

    gap, theta_max, model, folder = best
    output = read_key_value(folder / "output.txt")
    entrepreneurs = read_key_value(folder / "Entrepreneur_10_50.txt")
    summary = {
        "cache_version": CACHE_VERSION,
        "target_file": str(TARGET_FILE.relative_to(ROOT)),
        "target": target,
        "theta_max": theta_max,
        "published_theta_max": PUBLISHED_THETA_MAX,
        "model_debt_output": model,
        "gap": model - target,
        "scf_parameters": parameters,
        "benchmark_moments": {
            "wealth_output": output["Wealth_Output"],
            "top_1_wealth_share": output["Wealth_Top_1%"],
            "top_0_1_wealth_share": output["Wealth_Top_0.1%"],
            "entrepreneur_population_share": entrepreneurs[
                "Profits/Before_Tax_Income>50%"
            ]
            / 100.0,
            "entrepreneurs_in_top_1_share": entrepreneurs[
                "Top_01_Entrepreneur_50"
            ]
            / 100.0,
            "entrepreneur_wealth_share": entrepreneurs[
                "Entreprenur_50_A_Share"
            ]
            / 100.0,
        },
        "run_directory": str(folder.relative_to(ROOT)),
    }
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    # best.json backs Section 2.5 and every policy run (PolicyEvaluator reads it).
    # Never replace it silently: write a candidate unless --overwrite-best is given.
    best_file = RUN_ROOT / "best.json"
    if best_file.exists() and not args.overwrite_best:
        best_file = RUN_ROOT / "best.candidate.json"
        print(f"\n{RUN_ROOT / 'best.json'} already exists and backs the paper; "
              f"wrote {best_file.name} instead.  Re-run with --overwrite-best to "
              "replace the canonical calibration deliberately.")
    best_file.write_text(json.dumps(summary, indent=2) + "\n")
    print("\nBest financing calibration")
    print(f"  theta_max:        {theta_max:.8f} (published {PUBLISHED_THETA_MAX:.8f})")
    print(f"  debt/output:      {model:.8f}")
    print(f"  2022 target:      {target:.8f}")
    print(f"  gap:              {model-target:+.8f}")
    print(f"  outputs:          {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

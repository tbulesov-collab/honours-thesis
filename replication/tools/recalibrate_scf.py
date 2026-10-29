#!/usr/bin/env python3
"""Locally recalibrate entrepreneurial parameters to the 2022 SCF targets.

The paper jointly calibrates the entrepreneurial process. This staged driver keeps
rho_z fixed at its directly targeted value (0.1), preserves the paper's top-1% wealth
target, and updates the two SCF entrepreneurship targets. Four remaining process
parameters are adjusted by a regularized Gauss-Newton step, so the underidentified
local update is the smallest proportional departure from the published calibration.
Every model evaluation has its own output directory and is cached.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path

from benchmark_cache import complete_benchmark

try:
    import numpy as np
except ImportError as exc:
    raise SystemExit(
        "numpy is required; run this with python3"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "Compiled_Files_Baseline" / "GKK_Main.a"
RUN_ROOT = ROOT / "calibration" / "runs" / "scf_2022"
DEFAULT_TARGET_FILE = ROOT / "calibration" / "scf_2022_moments.csv"
CACHE_VERSION = "entrepreneur-fractional-percentiles-v3"

NAMES = ("sigma_z_eps", "x_hi", "p1_x", "p2_x")
BASELINE = np.array([0.277, 1.50, 0.05, 0.03], dtype=float)
STEPS = np.array([0.015, 0.10, 0.005, 0.003], dtype=float)
LOWER = np.array([0.05, 1.05, 0.005, 0.005], dtype=float)
UPPER = np.array([0.60, 3.00, 0.20, 0.15], dtype=float)


def parse_key_value(path: Path) -> dict[str, float]:
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


def targets(target_file: Path) -> np.ndarray:
    with target_file.open(newline="") as stream:
        rows = {row["moment_id"]: row for row in csv.DictReader(stream)}
    return np.array(
        [
            0.36,  # Preserve the paper's Vermeulen top-1% calibration target.
            float(rows["entrepreneur_share_top1"]["scf_2022_value"]),
            float(rows["entrepreneur_wealth_share"]["scf_2022_value"]),
        ]
    )


def candidate_id(params: np.ndarray) -> str:
    payload = CACHE_VERSION + ":" + ",".join(f"{x:.10g}" for x in params)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def read_moments(folder: Path) -> np.ndarray:
    output = parse_key_value(folder / "output.txt")
    if output.get("Statistics_Schema") != 3:
        raise ValueError("Benchmark uses old percentile statistics; rebuild and recompute it")
    entrepreneurs = parse_key_value(folder / "Entrepreneur_10_50.txt")
    return np.array(
        [
            output["Wealth_Top_1%"],
            entrepreneurs["Top_01_Entrepreneur_50"] / 100.0,
            entrepreneurs["Entreprenur_50_A_Share"] / 100.0,
        ]
    )


def evaluate(params: np.ndarray, threads: int) -> tuple[np.ndarray, Path]:
    if np.any(params < LOWER) or np.any(params > UPPER):
        raise ValueError("candidate lies outside parameter bounds")
    run_dir = RUN_ROOT / candidate_id(params)
    result_file = run_dir / "result.json"
    if result_file.exists() and complete_benchmark(run_dir):
        payload = json.loads(result_file.read_text())
        return read_moments(run_dir), run_dir

    run_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "OMP_NUM_THREADS": str(threads),
            "GKK_RHO_Z": "0.1",
            "GKK_SIGMA_Z_EPS": f"{params[0]:.16g}",
            "GKK_X_HI": f"{params[1]:.16g}",
            "GKK_P1_X": f"{params[2]:.16g}",
            "GKK_P2_X": f"{params[3]:.16g}",
            "GKK_RESULT_FOLDER": str(run_dir.relative_to(ROOT)),
        }
    )
    with (run_dir / "run.log").open("w") as log:
        completed = subprocess.run(
            [str(EXE)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
        )
    if completed.returncode:
        raise RuntimeError(f"model failed; inspect {run_dir / 'run.log'}")

    if not complete_benchmark(run_dir):
        raise ValueError("Benchmark state is incomplete; inspect the solver output")
    moments = read_moments(run_dir)
    result_file.write_text(
        json.dumps(
            {
                "cache_version": CACHE_VERSION,
                "parameters": dict(zip(NAMES, params.tolist())),
                "moments": moments.tolist(),
            },
            indent=2,
        )
        + "\n"
    )
    return moments, run_dir


def objective(moments: np.ndarray, target: np.ndarray) -> float:
    """Return the equally weighted sum of squared percentage-point errors."""
    return float(np.sum(((moments - target) * 100.0) ** 2))


def build() -> None:
    subprocess.run(
        ["bash", "tools/run_mac.sh", "calibration-build"], cwd=ROOT, check=True
    )


def report(params: np.ndarray, moments: np.ndarray, target: np.ndarray, folder: Path) -> None:
    print("\nParameters")
    for name, value, base in zip(NAMES, params, BASELINE):
        print(f"  {name:<14} {value:10.6f}  (published {base:.6f})")
    print("\nMoments")
    labels = (
        "Top 1% wealth share",
        "Entrepreneurs in top 1%",
        "Entrepreneur wealth share",
    )
    for label, model, data in zip(labels, moments, target):
        gap = (model - data) * 100.0
        print(f"  {label:<30} model={model:8.4%} target={data:8.4%} gap={gap:+7.3f} pp")
    print(f"\nObjective: {objective(moments, target):.6f}")
    print(f"Outputs:   {folder}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--ridge", type=float, default=0.10)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument(
        "--targets",
        type=Path,
        default=DEFAULT_TARGET_FILE,
        help="SCF moment CSV (default: paper-continuity active-manager targets)",
    )
    parser.add_argument(
        "--evaluate",
        nargs=4,
        type=float,
        metavar=NAMES,
        help="evaluate one candidate instead of running the local search",
    )
    args = parser.parse_args()
    if args.threads < 1 or args.iterations < 0 or args.ridge < 0:
        parser.error("threads must be positive; iterations and ridge must be nonnegative")
    if not args.skip_build:
        build()
    if not EXE.exists():
        raise SystemExit(f"executable not found: {EXE}")

    target_file = args.targets.resolve()
    target = targets(target_file)
    params = np.array(args.evaluate if args.evaluate else BASELINE, dtype=float)
    moments, folder = evaluate(params, args.threads)
    report(params, moments, target, folder)
    if args.evaluate:
        return 0

    for iteration in range(1, args.iterations + 1):
        print(f"\nSensitivity iteration {iteration}/{args.iterations}")
        jacobian = np.empty((len(target), len(params)))
        for column in range(len(params)):
            trial = params.copy()
            trial[column] = min(UPPER[column], params[column] + STEPS[column])
            trial_moments, trial_folder = evaluate(trial, args.threads)
            jacobian[:, column] = (
                (trial_moments - moments) / (trial[column] - params[column])
            )
            print(f"  evaluated +{NAMES[column]} in {trial_folder.name}")

        # Scale changes by published values. The ridge term selects a stable,
        # minimum-change solution because three moments identify four inputs here.
        scaled_jacobian = jacobian * BASELINE[np.newaxis, :]
        error = target - moments
        system = (
            scaled_jacobian.T @ scaled_jacobian
            + args.ridge * np.eye(len(params))
        )
        scaled_delta = np.linalg.solve(system, scaled_jacobian.T @ error)
        candidate = np.clip(params + BASELINE * scaled_delta, LOWER, UPPER)

        candidate_moments, candidate_folder = evaluate(candidate, args.threads)
        if objective(candidate_moments, target) >= objective(moments, target):
            candidate = np.clip(
                params + 0.5 * BASELINE * scaled_delta, LOWER, UPPER
            )
            candidate_moments, candidate_folder = evaluate(candidate, args.threads)
        if objective(candidate_moments, target) >= objective(moments, target):
            print("No improving local step found; stopping.")
            break
        params, moments, folder = candidate, candidate_moments, candidate_folder
        report(params, moments, target, folder)

    summary_name = (
        "best.json"
        if target_file == DEFAULT_TARGET_FILE.resolve()
        else f"best.{target_file.stem}.json"
    )
    summary = RUN_ROOT / summary_name
    summary.parent.mkdir(parents=True, exist_ok=True)
    current = {
        "cache_version": CACHE_VERSION,
        "target_file": str(target_file),
        "parameters": dict(zip(NAMES, params.tolist())),
        "moments": moments.tolist(),
        "targets": target.tolist(),
        "objective": objective(moments, target),
        "run_directory": str(folder),
    }
    previous = json.loads(summary.read_text()) if summary.exists() else None
    if previous is not None and (
        previous.get("cache_version") != CACHE_VERSION
        or previous.get("target_file") != str(target_file)
    ):
        previous = None
    if previous is None or current["objective"] < previous["objective"]:
        summary.write_text(json.dumps(current, indent=2) + "\n")
        print(f"\nBest staged calibration saved to {summary}")
    else:
        print(
            f"\nExisting best retained ({previous['objective']:.6f} < "
            f"{current['objective']:.6f}): {summary}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

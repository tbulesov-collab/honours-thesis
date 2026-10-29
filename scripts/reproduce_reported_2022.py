#!/usr/bin/env python3
"""Build and rerun the reported 2022 parameters in an isolated numerical workspace.

The default stage prints a plan and writes nothing. --stage build compiles the
frozen, unchanged control model without executing it. --stage benchmark solves a
cold benchmark; --stage policies evaluates selected fixed policies against that
benchmark. --stage all performs those stages in sequence. Those stages do not
change released sources, calibrations, summaries, historical runs or the grid.
The separate --stage install-legacy copies a verified fresh benchmark into the
path expected by legacy drivers, backing up the old folder. Use a disposable
working copy for that stage and subsequent legacy experiments.

--profile theta2800 holds the same saved SCF parameters and frozen control
sources, with theta_max=2.8. It builds/solves/installs only that benchmark; it
does not compare its policies with the reported financing-profile references.

This is the core benchmark/four-policy reproduction, not a claim that calibration
searches, every robustness variant, extended grids, or transitions were rerun.
Results use a freshly solved benchmark; the historical headline normalization
differs by about 0.10 CE2 percentage points. The reference values below are the
released fresh-control comparisons, not the historical headline levels.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
MODEL_DEFAULT = ROOT / "replication"
SOURCES = ["NRTYPE.F90", "NRUTIL.F90", "Toolbox.f90", "parameters.f90", "global.f90",
           "programfunctions.f90", "Simulation_Module.f90", "GKK_Stats.f90",
           "Opt_Tax_Parameters.f90", "Opt_Tax_Functions.f90", "GKK_Main.f90",
           "GKK_Main_bench.f90"]
PLAIN = ["NRTYPE.F90", "NRUTIL.F90", "Toolbox.f90", "parameters.f90", "global.f90",
         "Opt_Tax_Parameters.f90"]
OMP = ["programfunctions.f90", "Simulation_Module.f90", "GKK_Stats.f90"]
STATES = ["DBN", "value", "bq_value", "cons", "hours", "aprime", "Income_AT",
          "v_pr", "v_pr_nb", "GBAR", "YBAR", "R", "P", "wage", "QBAR", "NBAR",
          "EBAR", "psi", "tauK", "tauW_bt", "tauW_at", "tauPL", "SSC_Payments",
          "K_P", "K_C", "L_P", "L_C", "YBAR_P", "YBAR_C"]
POLICIES = {"owt": (0.030618034, 0.0, 0.4), "okit": (0.0, -0.13618034, 0.4),
            "joint_bq40": (0.07, -0.5, 0.4), "joint_bq0": (0.07, -0.5, 0.0),
            "anchor": (0.0, 0.25, 0.4)}
DEFAULT_POLICIES = ["owt", "okit", "joint_bq40", "joint_bq0"]
FRESH_REFERENCE = {"owt": 8.3912, "okit": 4.9511, "joint_bq40": 19.7663,
                   "joint_bq0": 23.4398, "anchor": 0.0}
SOLVER = {"GKK_DBN_TOL": "1e-7", "GKK_AGG_TOL": "1e-6",
          "GKK_DBN_MAX_ITER": "2000", "GKK_BUDGET_MAX_ITER": "100"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def clean_environment() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith(("GKK_", "OMP_"))}


def calibration(model: Path, profile: str = "reported") -> tuple[dict, dict]:
    if profile not in ("reported", "theta2800"):
        raise ValueError(f"Unknown benchmark profile: {profile}")
    files = {"scf": model / "calibration/runs/scf_2022/best.json",
             "financing": model / "calibration/runs/business_financing_2022/best.json"}
    scf, fin = (json.loads(files[key].read_text()) for key in ("scf", "financing"))
    p = scf["parameters"]
    if any(not math.isclose(float(p[k]), float(fin["scf_parameters"][k]),
                            rel_tol=0, abs_tol=1e-14) for k in p):
        raise ValueError("SCF and financing records use different entrepreneurial parameters")
    env = {"GKK_RHO_Z": "0.1", "GKK_SIGMA_Z_EPS": format(p["sigma_z_eps"], ".17g"),
           "GKK_X_HI": format(p["x_hi"], ".17g"), "GKK_P1_X": format(p["p1_x"], ".17g"),
           "GKK_P2_X": format(p["p2_x"], ".17g"),
           "GKK_THETA_MAX": format(2.8 if profile == "theta2800" else fin["theta_max"], ".17g")}
    return env, {str(p.relative_to(model)): sha(p) for p in files.values()}


def frozen_sources(model: Path) -> tuple[Path, dict]:
    base = model / "experiments/model_spec_sensitivity_2022/variants"
    src = base / "control/src"
    provenance = json.loads((base / "provenance.json").read_text())["control"]
    hashes = {}
    for name in SOURCES:
        hashes[name] = sha(src / name)
        if hashes[name] != provenance["sources_sha256"][name]:
            raise ValueError(f"Frozen control source differs from provenance: {name}")
    return src, hashes


@contextmanager
def locked(work: Path):
    lock = work / "runner.lock"
    try:
        with lock.open("x") as stream:
            stream.write(str(os.getpid()) + "\n")
    except FileExistsError:
        raise RuntimeError(f"Another or interrupted run owns {lock}; inspect it before resuming")
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def build(model: Path, work: Path, source: Path, hashes: dict) -> dict:
    compiler = shutil.which("gfortran")
    if compiler is None:
        raise RuntimeError("GNU Fortran with OpenMP is required; gfortran was not found")
    version = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
    expected = {"source_sha256": hashes, "compiler": compiler, "compiler_version": version,
                "compiler_sha256": sha(Path(compiler).resolve()),
                "flags": "Frozen control build: -O3; OpenMP sources and links also use "
                         "-fopenmp -fbounds-check -ffp-contract=off"}
    record = work / "build.json"
    out, src = work / "build", work / "src"
    if record.exists():
        old = json.loads(record.read_text())
        if old["inputs"] != expected:
            raise RuntimeError("Build inputs changed; choose a new --run-id")
        for name, digest in old["executable_sha256"].items():
            if sha(out / name) != digest:
                raise RuntimeError(f"Built executable changed: {name}; choose a new --run-id")
        print("Reusing verified local build", flush=True)
        return old
    if out.exists() or src.exists():
        raise RuntimeError("Incomplete build exists; retain it and choose a new --run-id")
    (out / "mod").mkdir(parents=True)
    src.mkdir()
    for name in SOURCES:
        shutil.copy2(source / name, src / name)
    commands, objects = [], []
    for name in PLAIN + OMP + ["Opt_Tax_Functions.f90"]:
        obj = out / (Path(name).stem + ".o")
        flags = ["-fopenmp", "-O3", "-fbounds-check", "-ffp-contract=off"] if name in OMP else ["-O3"]
        commands.append([compiler, *flags, "-J" + str(out / "mod"), "-c", name, "-o", str(obj)])
        objects.append(str(obj))
    for main, exe in [("GKK_Main.f90", "eval.a"), ("GKK_Main_bench.f90", "bench.a")]:
        commands.append([compiler, "-fopenmp", "-fbounds-check", "-ffp-contract=off", "-O3",
                         "-I" + str(out / "mod"), main, *objects, "-o", str(out / exe)])
    with (work / "build.log").open("w") as log:
        for command in commands:
            print("Compiling " + Path(command[-1]).name, flush=True)
            log.write(json.dumps(command) + "\n"); log.flush()
            subprocess.run(command, cwd=src, env=clean_environment(), stdout=log,
                           stderr=subprocess.STDOUT, check=True)
    result = {"inputs": expected, "commands": commands,
              "executable_sha256": {n: sha(out / n) for n in ("bench.a", "eval.a")}}
    write_json(record, result)
    return result


def verified_benchmark(folder: Path, inputs: dict) -> dict | None:
    done = folder / "done.json"
    if not done.exists():
        return None
    old = json.loads(done.read_text())
    if old["inputs"] != inputs:
        raise RuntimeError("Benchmark inputs changed; choose a new --run-id")
    for name in ["output.txt", *["Bench_Files/" + x for x in STATES]]:
        if sha(folder / name) != old["files_sha256"].get(name):
            raise RuntimeError(f"Benchmark cache changed or is incomplete: {name}")
    return old


def benchmark(model: Path, work: Path, build_info: dict, env: dict, calibration_hashes: dict,
              profile: str = "reported") -> dict:
    from policy_evaluation import read_kv
    folder = work / "benchmark"
    model_env = {**env, "GKK_RESULT_FOLDER": str(folder.relative_to(model)) + "/"}
    inputs = {"profile": profile, "environment": model_env, "calibration_sha256": calibration_hashes,
              "executable_sha256": build_info["executable_sha256"]["bench.a"]}
    old = verified_benchmark(folder, inputs)
    if old is not None:
        print("Reusing verified benchmark arrays from this run", flush=True)
        return old
    if folder.exists():
        raise RuntimeError("Incomplete benchmark exists; retain it and choose a new --run-id")
    folder.mkdir()
    start = time.monotonic()
    print("Solving fresh benchmark; progress is in " + str(folder / "run.log"), flush=True)
    with (folder / "run.log").open("w") as log:
        subprocess.run([str(work / "build/bench.a")], cwd=model,
                       env={**clean_environment(), **model_env}, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    values = read_kv(folder / "output.txt")
    if values.get("Statistics_Schema") != 3 or any(
            not math.isfinite(values.get(k, float("nan"))) or values[k] <= 0
            for k in ("GBAR", "YBAR", "CBAR", "KBAR")):
        raise RuntimeError("Benchmark output is incomplete or invalid")
    files = ["output.txt", *["Bench_Files/" + x for x in STATES]]
    if any(not (folder / n).is_file() or (folder / n).stat().st_size == 0 for n in files):
        raise RuntimeError("Benchmark did not create the complete solver state")
    result = {"inputs": inputs, "elapsed_seconds": time.monotonic() - start,
              "files_sha256": {n: sha(folder / n) for n in files}, "aggregates": values}
    write_json(folder / "done.json", result)
    return result


def policies(model: Path, work: Path, build_info: dict, env: dict, calibration_hashes: dict,
             names: list[str], threads: int, profile: str = "reported") -> dict:
    if profile != "reported":
        raise ValueError("Policy reference comparisons require --profile reported")
    from policy_evaluation import PolicyEvaluator
    folder = work / "benchmark"
    inputs = {"profile": profile,
              "environment": {**env, "GKK_RESULT_FOLDER": str(folder.relative_to(model)) + "/"},
              "calibration_sha256": calibration_hashes,
              "executable_sha256": build_info["executable_sha256"]["bench.a"]}
    if verified_benchmark(folder, inputs) is None:
        raise RuntimeError("Run --stage benchmark first; saved summaries are not a benchmark cache")
    old_environment = os.environ.copy()
    try:
        os.environ.clear(); os.environ.update(clean_environment_from(old_environment)); os.environ.update(env)
        evaluator = PolicyEvaluator(root=model, executable=work / "build/eval.a", benchmark=folder,
            run_root=work / "policies", threads=threads,
            bounds=((-1., 1.), (-1., 1.), (0., 1.)), labor_bounds=(0., .6),
            budget_tolerance=1e-4, fixed_labor=False,
            calibration_env={k: v for k, v in env.items() if k in calibration(model)[0]})
        results = {}
        for name in names:
            print("Evaluating " + name, flush=True)
            result = evaluator.evaluate_rates(POLICIES[name])
            results[name] = {**result, "fresh_control_reference_ce2": FRESH_REFERENCE[name],
                "difference_pp": result["ce2_newborn"] - FRESH_REFERENCE[name],
                "within_reporting_threshold": abs(result["ce2_newborn"] - FRESH_REFERENCE[name]) < .15}
            write_json(work / "policy_results.json", results)
        return results
    finally:
        os.environ.clear(); os.environ.update(old_environment)


def clean_environment_from(environment: dict) -> dict:
    return {k: v for k, v in environment.items() if not k.startswith(("GKK_", "OMP_"))}


def legacy_benchmark_target(model: Path, profile: str = "reported") -> Path:
    if profile == "reported":
        return model / "calibration/runs/business_financing_2022/rn_reform"
    if profile == "theta2800":
        from recalibrate_financing_2022 import portable_run_directory
        scf = json.loads((model / "calibration/runs/scf_2022/best.json").read_text())
        return portable_run_directory(scf["run_directory"], root=model)
    raise ValueError(f"Unknown benchmark profile: {profile}")


def install_legacy_benchmark(model: Path, work: Path, build_info: dict, env: dict,
                             calibration_hashes: dict, profile: str = "reported") -> dict:
    """Install a consistent output/state pair; retain the original run intact."""
    source = work / "benchmark"
    inputs = {"profile": profile,
              "environment": {**env, "GKK_RESULT_FOLDER": str(source.relative_to(model)) + "/"},
              "calibration_sha256": calibration_hashes,
              "executable_sha256": build_info["executable_sha256"]["bench.a"]}
    record = verified_benchmark(source, inputs)
    if record is None:
        raise RuntimeError("Run --stage benchmark before installing the legacy benchmark")
    target = legacy_benchmark_target(model, profile)
    marker = target / "fresh_benchmark_installation.json"
    if marker.exists():
        old = json.loads(marker.read_text())
        if old.get("files_sha256") == record["files_sha256"] and all(
                (target / n).is_file() and sha(target / n) == h
                for n, h in record["files_sha256"].items()):
            print("Legacy benchmark already matches the verified fresh state", flush=True)
            return old
        raise RuntimeError("Legacy benchmark was changed after installation; use a new working copy")
    token = uuid.uuid4().hex
    staged = target.with_name(target.name + ".installing-" + token)
    backup = target.with_name(target.name + ".before-fresh-" + token)
    installation = {"profile": profile, "source": str(source.relative_to(model)),
                    "backup": str(backup.relative_to(model)) if target.exists() else None,
                    "normalisation": ("Fresh reported-parameter benchmark; historical headline CE2 "
                                      "differs by approximately 0.10 percentage points"
                                      if profile == "reported" else
                                      "Fresh theta_max=2.8 benchmark at the saved SCF parameters; "
                                      "historical benchmark normalization is not assumed exact"),
                    "inputs": inputs, "files_sha256": record["files_sha256"]}
    target.parent.mkdir(parents=True, exist_ok=True)
    # Stage and verify the whole benchmark, including auxiliary grids/statistics,
    # before renaming anything. Never mix old output.txt with fresh arrays.
    shutil.copytree(source, staged)
    for name, digest in record["files_sha256"].items():
        if sha(staged / name) != digest:
            raise RuntimeError(f"Staged benchmark copy failed verification: {name}")
    write_json(staged / marker.name, installation)
    if target.exists():
        target.rename(backup)
    try:
        staged.rename(target)
    except OSError:
        if backup.exists() and not target.exists():
            backup.rename(target)
        raise
    print("Installed fresh benchmark: " + str(target), flush=True)
    if installation["backup"]:
        print("Original evidence retained at: " + str(backup), flush=True)
    return installation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-root", type=Path, default=MODEL_DEFAULT)
    parser.add_argument("--profile", choices=["reported", "theta2800"], default="reported")
    parser.add_argument("--run-id", help="Default: reported_2022 or theta2800_2022; use a new identifier if inputs change")
    parser.add_argument("--stage", choices=["plan", "build", "benchmark", "policies", "all", "install-legacy"], default="plan")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--policies", nargs="+", choices=list(POLICIES), default=DEFAULT_POLICIES)
    args = parser.parse_args()
    if args.profile == "theta2800" and args.stage in ("policies", "all"):
        parser.error("theta2800 supports plan, build, benchmark and install-legacy only; "
                     "the policy references require --profile reported")
    if args.run_id is None:
        args.run_id = "reported_2022" if args.profile == "reported" else "theta2800_2022"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.run_id) or args.threads < 1:
        parser.error("run-id must be 1–40 letters/digits/_/- and threads must be positive")
    model = args.model_root.resolve()
    source, hashes = frozen_sources(model)
    cal_env, cal_hashes = calibration(model, args.profile)
    env = {**cal_env, **SOLVER, "OMP_NUM_THREADS": str(args.threads),
           "OMP_DYNAMIC": "FALSE", "OMP_NESTED": "FALSE"}
    work = model / "runtime/reproduction" / args.run_id
    plan = {"stage": args.stage, "profile": args.profile,
            "model_root": str(model), "workspace": str(work),
            "source": str(source.relative_to(model)), "calibration_environment": cal_env,
            "solver_environment": {**SOLVER, "OMP_NUM_THREADS": str(args.threads)},
            "policies": {n: POLICIES[n] for n in args.policies} if args.profile == "reported" else {},
            "scope": ("Fresh reported-parameter benchmark and selected fixed policies; no calibration search"
                      if args.profile == "reported" else
                      "Fresh theta_max=2.8 benchmark only, holding the saved SCF parameters fixed"),
            "expected_resources": "About 3 GB RAM per sequential solver, several GB disk per benchmark; "
                                  "historically about 30 minutes benchmark plus 50–155 minutes per policy",
            "reference": ("Fresh control results; historical headline CE2 has an approximately 0.10-point offset"
                          if args.profile == "reported" else
                          "No reported financing-profile policy references apply to theta2800")}
    print(json.dumps(plan, indent=2), flush=True)
    if args.stage == "plan":
        return 0
    sys.path.insert(0, str(model / "tools"))
    work.mkdir(parents=True, exist_ok=True)
    with locked(work):
        if args.stage == "install-legacy" and not (work / "build.json").is_file():
            raise RuntimeError("Run --stage benchmark first; install-legacy does not compile or solve")
        info = build(model, work, source, hashes)
        write_json(work / "run_plan.json", plan)
        if args.stage == "install-legacy":
            install_legacy_benchmark(model, work, info, env, cal_hashes, args.profile)
        if args.stage in ("benchmark", "all"):
            benchmark(model, work, info, env, cal_hashes, args.profile)
        if args.stage in ("policies", "all"):
            results = policies(model, work, info, env, cal_hashes, args.policies, args.threads, args.profile)
            print(json.dumps({n: {k: r[k] for k in ("ce2_newborn", "difference_pp",
                  "within_reporting_threshold", "feasible")} for n, r in results.items()}, indent=2))
            if not all(r["feasible"] and r["within_reporting_threshold"] for r in results.values()):
                print("A selected result differs from the released fresh-control comparison; inspect outputs.", file=sys.stderr)
                return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Check the released files and syntax without importing or executing model code."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "replication"
REQUIRED = (
    "GKK_Main.f90", "parameters.f90", "programfunctions.f90",
    "tools/run_mac.sh", "requirements.txt",
    "tools/benchmark_cache.py",
    "calibration/runs/scf_2022/best.json",
    "calibration/runs/business_financing_2022/best.json",
    "calibration/runs/headline_revalidation_2022/validated_headline.json",
    "tools/optimize_joint_taxes.py", "tools/policy_grid_2022.py",
    "experiments/joint_tax_fixed_labor/README.md",
    "experiments/model_spec_sensitivity_2022/results.json",
    "experiments/model_spec_sensitivity_2022/recal_results.json",
    "experiments/policy_reoptimization_2022/results.json",
    "experiments/policy_reoptimization_2022/runs/grid_points.json",
    "experiments/policy_reoptimization_2022/runs/edge_points.json",
    "experiments/robustness_gkkoc_2022/misallocation_link.json",
    "experiments/robustness_gkkoc_2022/runs/side.json",
    "experiments/robustness_gkkoc_2022/runs/looser_policies.json",
    "experiments/robustness_gkkoc_2022/runs/looser_rbracket.json",
    "experiments/robustness_gkkoc_2022/runs/partB_all.json",
    "experiments/robustness_gkkoc_2022/partD.py",
    "experiments/robustness_gkkoc_2022/partD_results.md",
    "experiments/robustness_gkkoc_2022/runs/partD_all.json",
    "experiments/robustness_gkkoc_2022/runs/c6_theta.json",
    "experiments/robustness_gkkoc_2022/runs/c6_policies.json",
    "experiments/robustness_gkkoc_2022/c6_results.md",
    "experiments/robustness_gkkoc_2022/runs/c7/mu08/scf.json",
    "experiments/robustness_gkkoc_2022/runs/c7/mu08/financing.json",
    "experiments/robustness_gkkoc_2022/runs/c7_policies.json",
    "experiments/robustness_gkkoc_2022/c7_results.md",
    "experiments/table15_estate_2022/run_table15_estate.py",
    "experiments/table15_estate_2022/results.json",
    "experiments/table15_estate_2022/results.md",
    "experiments/table15_estate_2022/runs/points.json",
    "validation/saved_comparison.json", "validation/incidence_checks.json",
    "validation/policy_table_inputs/index.json",
    "experiments/grid_accuracy_2022/README.md",
    "experiments/grid_accuracy_2022/make_grid_variant.py",
    "experiments/grid_accuracy_2022/run_grid_check.py",
    "experiments/grid_accuracy_2022/results_na301.json",
    "experiments/grid_accuracy_2022/results_na401.json",
    "experiments/grid_accuracy_2022/make_guard_variant.py",
    "experiments/grid_accuracy_2022/run_extended_grid_check.py",
    "experiments/grid_accuracy_2022/results_extended.json",
    "experiments/marginal_returns_2022/extract_marginal_returns.py",
    "experiments/marginal_returns_2022/results.json",
    "experiments/marginal_returns_2022/run_map.example.json",
    "experiments/model_spec_sensitivity_2022/flat_direction.py",
    "experiments/model_spec_sensitivity_2022/flat/results.json",
)


def main():
    manifest = json.loads((SNAPSHOT / "SNAPSHOT_MANIFEST.json").read_text())
    records = {**manifest["files"], **manifest.get("managed_files", {})}
    errors = []
    counts = {"hashed_files": 0, "python_files": 0, "shell_files": 0, "json_files": 0}
    for name, record in records.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"Unsafe manifest path: {name}")
            continue
        path = SNAPSHOT / relative
        if not path.is_file() or path.is_symlink():
            errors.append(f"Missing file or symlink: {name}")
            continue
        data = path.read_bytes()
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            errors.append(f"Hash/size mismatch: {name}")
        counts["hashed_files"] += 1
        try:
            if path.suffix == ".py":
                compile(data, str(path), "exec")  # Syntax only; no imports or execution.
                counts["python_files"] += 1
            elif path.suffix == ".json":
                json.loads(data)
                counts["json_files"] += 1
            elif path.suffix == ".sh":
                result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
                if result.returncode:
                    errors.append(f"Shell syntax: {name}: {result.stderr.strip()}")
                counts["shell_files"] += 1
        except (SyntaxError, ValueError, UnicodeError) as exc:
            errors.append(f"Syntax/data error: {name}: {exc}")
    for name in REQUIRED:
        if name not in records:
            errors.append(f"Required evidence/source absent from manifest: {name}")
    for path in (ROOT / "scripts").glob("*.py"):
        try:
            compile(path.read_bytes(), str(path), "exec")
            counts["python_files"] += 1
        except SyntaxError as exc:
            errors.append(f"Package-script syntax: {path.name}: {exc}")
    if not (ROOT / "scripts/check_saved_policy_tables.py").is_file():
        errors.append("Saved-policy table checker is missing")
    # The public SCF archives are distributed separately from the model snapshot.
    # Verify archive hashes and decompression integrity without extracting files.
    scf_manifest_path = ROOT / "data/scf2022/MANIFEST.json"
    if not scf_manifest_path.is_file():
        errors.append("Public SCF archive manifest is missing")
    else:
        scf_manifest = json.loads(scf_manifest_path.read_text())
        counts["scf_archives"] = 0
        for name, record in scf_manifest["files"].items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"Unsafe SCF archive path: {name}")
                continue
            path = scf_manifest_path.parent / relative
            if not path.is_file() or path.is_symlink():
                errors.append(f"Missing SCF archive: {name}")
                continue
            data = path.read_bytes()
            if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
                errors.append(f"SCF archive hash/size mismatch: {name}")
            try:
                with zipfile.ZipFile(path) as archive:
                    bad_member = archive.testzip()
                    if bad_member:
                        errors.append(f"Corrupt SCF archive member: {name}/{bad_member}")
            except zipfile.BadZipFile:
                errors.append(f"Invalid SCF archive: {name}")
            counts["scf_archives"] += 1
        if counts["scf_archives"] != 3:
            errors.append("Expected summary, full-data and replicate-weight SCF archives")
    for name in ("scripts/rebuild_scf_audit.py", "scripts/check_thesis_results.py",
                 "scripts/reproduce_reported_2022.py", "scripts/test_reproduction_portability.py",
                 "scripts/test_marginal_run_map.py",
                 "THESIS_RESULT_MAP.md", "THESIS_RESULT_MAP.json"):
        if not (ROOT / name).is_file():
            errors.append(f"Required reproduction entry point missing: {name}")
    report = {"ok": not errors, **counts, "errors": errors,
              "scope": "File integrity and syntax only; no model execution or numerical reproduction."}
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

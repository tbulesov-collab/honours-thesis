#!/usr/bin/env python3
"""No-solver regression tests for relocation and compact benchmark-cache handling.

All writes use temporary directories. Every attempted legacy solver invocation
is intercepted; no compiler or model process is launched. Pass --model-root to
test an exported snapshot in another location.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SolverIntercepted(Exception):
    """Raised instead of launching a numerical subprocess."""


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)

    def make_benchmark(self, folder, *, complete=True):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "output.txt").write_text("Statistics_Schema 3\nDebt_Output 1.5\n")
        if complete:
            (folder / "Bench_Files").mkdir()
            for name in cache.BENCHMARK_STATE_FILES:
                (folder / "Bench_Files" / name).write_text("1\n")

    def wrapper_fixture(self, relative):
        """Run only a copied shell wrapper with fake Python and process listing."""
        root = self.root / "relocated model with spaces"
        wrapper = root / relative
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(model / relative, wrapper)
        bin_dir = self.root / "fake executables"
        bin_dir.mkdir(exist_ok=True)
        interpreter = bin_dir / "python3"
        interpreter.write_text('#!/bin/sh\nprintf "%s\\n" "$THREADS" "$PWD" "$@" > "$WRAPPER_CAPTURE"\nexit "$WRAPPER_STATUS"\n')
        interpreter.chmod(0o755)
        process_list = bin_dir / "ps"
        process_list.write_text("#!/bin/sh\nexit 0\n")
        process_list.chmod(0o755)
        capture = self.root / "wrapper-arguments.txt"
        capture.unlink(missing_ok=True)
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                   WRAPPER_CAPTURE=str(capture), WRAPPER_STATUS="0")
        env.pop("PYTHON_BIN", None)
        env.pop("THREADS", None)
        return root, wrapper, interpreter, capture, env

    def test_optimizer_wrappers_use_path_python_and_preserve_arguments(self):
        for relative in ("tools/run_joint_tax_optimization.sh",
                         "experiments/joint_tax_fixed_labor/run_fixed_labor_optimizer.sh"):
            with self.subTest(wrapper=relative):
                root, wrapper, _, capture, env = self.wrapper_fixture(relative)
                result = subprocess.run(["bash", str(wrapper), "--tag", "value with spaces"],
                                        cwd=self.root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                observed = capture.read_text().splitlines()
                self.assertEqual(observed[:2], ["9", str(root)])
                self.assertTrue(observed[2].endswith(".py"))
                self.assertEqual(observed[3:], ["--tag", "value with spaces"])

    def test_optimizer_wrappers_respect_override_threads_and_failure_status(self):
        for relative in ("tools/run_joint_tax_optimization.sh",
                         "experiments/joint_tax_fixed_labor/run_fixed_labor_optimizer.sh"):
            with self.subTest(wrapper=relative):
                _, wrapper, interpreter, capture, env = self.wrapper_fixture(relative)
                env.update(PYTHON_BIN=str(interpreter), THREADS="2", WRAPPER_STATUS="23")
                result = subprocess.run(["bash", str(wrapper), "--tag", "another value"],
                                        cwd=self.root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 23, result.stderr)
                observed = capture.read_text().splitlines()
                self.assertEqual(observed[0], "2")
                self.assertEqual(observed[-2:], ["--tag", "another value"])

    def test_optimizer_wrappers_report_missing_interpreter(self):
        for relative in ("tools/run_joint_tax_optimization.sh",
                         "experiments/joint_tax_fixed_labor/run_fixed_labor_optimizer.sh"):
            with self.subTest(wrapper=relative):
                _, wrapper, _, capture, env = self.wrapper_fixture(relative)
                env["PYTHON_BIN"] = str(self.root / "no such python")
                result = subprocess.run(["bash", str(wrapper)], cwd=self.root, env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 127)
                self.assertIn("Python interpreter not found", result.stderr)
                self.assertFalse(capture.exists())

    def test_historical_absolute_path_resolves_inside_current_copy(self):
        old_root = self.root / "old-author-checkout"
        suffix = Path("calibration/runs/scf_2022/example")
        (old_root / suffix).mkdir(parents=True)
        with patch.object(fin, "ROOT", self.root / "relocated"):
            self.assertEqual(fin.portable_run_directory(str(old_root / suffix)),
                             self.root / "relocated" / suffix)
            self.assertEqual(fin.portable_run_directory(str(suffix)),
                             self.root / "relocated" / suffix)

    def test_misallocation_paths_relocate_inside_current_copy(self):
        old_root = self.root / "old-author-checkout"
        suffixes = ("calibration/runs/business_financing_2022/rn_reform",
                    "experiments/model_spec_sensitivity_2022/recal/control/solves/example")
        for suffix in suffixes:
            (old_root / suffix).mkdir(parents=True)
        with patch.object(misalloc, "ROOT", self.root / "relocated"):
            for suffix in suffixes:
                with self.subTest(suffix=suffix):
                    self.assertEqual(misalloc.model_path(str(old_root / suffix)),
                                     self.root / "relocated" / suffix)
                    self.assertEqual(misalloc.model_path(suffix), self.root / "relocated" / suffix)
            for value in ("/unrelated/author/path", "../outside", "experiments/../../outside"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    misalloc.model_path(value)

    def test_misallocation_reported_sample_is_pinned(self):
        sample = json.loads(misalloc.SAMPLE.read_text())["evaluations"]
        self.assertEqual(len(sample), 118)
        for item in sample:
            for value in (item["result"], item["benchmark"]):
                self.assertFalse(Path(value).is_absolute() or ".." in Path(value).parts, value)
        saved = json.loads((misalloc.HERE / "misallocation_link.json").read_text())
        self.assertEqual(misalloc.collect_sample(), saved["policies"])

    def test_misallocation_rescan_cannot_overwrite_thesis_results(self):
        with patch.object(sys, "argv", ["misallocation_link.py", "--rescan"]), \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            misalloc.main()
        self.assertEqual(stopped.exception.code, 2)

    def test_unknown_absolute_and_escaping_paths_are_rejected(self):
        with patch.object(fin, "ROOT", self.root):
            for value in ("/unrelated/author/path", "../outside"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    fin.portable_run_directory(value)

    def test_compact_missing_empty_and_complete_state(self):
        folder = self.root / "benchmark"
        self.make_benchmark(folder, complete=False)
        (folder / "done.json").write_text("{}")
        self.assertFalse(cache.complete_benchmark(folder))
        self.make_benchmark(folder)
        self.assertTrue(cache.complete_benchmark(folder))
        missing = folder / "Bench_Files" / "DBN"
        missing.write_text("")
        self.assertFalse(cache.complete_benchmark(folder))
        missing.unlink()
        self.assertFalse(cache.complete_benchmark(folder))

    def test_sensitivity_done_without_arrays_enters_solver_branch(self):
        here = self.root / "sensitivity"
        folder = here / "runs/control/benchmark"
        self.make_benchmark(folder, complete=False)
        (folder / "done.json").write_text('{"compact": true}')
        exe = here / "variants/control/build/bench.a"
        exe.parent.mkdir(parents=True)
        exe.write_text("not executable")
        with patch.object(sens, "ROOT", self.root), patch.object(sens, "HERE", here), \
                patch.object(sens, "calibration_env", return_value={}), \
                patch.object(sens.subprocess, "run", side_effect=SolverIntercepted) as run:
            with self.assertRaises(SolverIntercepted):
                sens.solve_benchmark("control", 1)
            run.assert_called_once()

    def test_sensitivity_complete_state_is_reused(self):
        here = self.root / "sensitivity"
        folder = here / "runs/control/benchmark"
        self.make_benchmark(folder)
        (folder / "done.json").write_text('{"reused": true}')
        with patch.object(sens, "HERE", here), patch.object(sens.subprocess, "run") as run:
            self.assertEqual(sens.solve_benchmark("control", 1), {"reused": True})
            run.assert_not_called()

    def test_grid_done_without_arrays_enters_solver_branch(self):
        here = self.root / "grid"
        folder = here / "runs/na301/benchmark"
        self.make_benchmark(folder, complete=False)
        (folder / "done.json").write_text('{"compact": true}')
        with patch.object(grid, "ROOT", self.root), patch.object(grid, "HERE", here), \
                patch.object(grid.rs, "calibration_env", return_value={}), \
                patch.object(grid.subprocess, "run", side_effect=SolverIntercepted) as run:
            with self.assertRaises(SolverIntercepted):
                grid.solve_benchmark(301, 1, 2000)
            run.assert_called_once()

    def test_grid_complete_state_is_reused(self):
        here = self.root / "grid"
        folder = here / "runs/na301/benchmark"
        self.make_benchmark(folder)
        (folder / "done.json").write_text('{"reused": true}')
        with patch.object(grid, "HERE", here), patch.object(grid.subprocess, "run") as run:
            self.assertEqual(grid.solve_benchmark(301, 1, 2000), {"reused": True})
            run.assert_not_called()

    def test_financing_compact_result_enters_solver_branch(self):
        parameters = {"sigma_z_eps": .277, "x_hi": 1.5, "p1_x": .05, "p2_x": .03}
        run_root = self.root / "financing"
        folder = run_root / fin.run_id(3.1, parameters)
        self.make_benchmark(folder, complete=False)
        (folder / "result.json").write_text("{}")
        with patch.object(fin, "ROOT", self.root), patch.object(fin, "RUN_ROOT", run_root), \
                patch.object(fin.subprocess, "run", side_effect=SolverIntercepted) as run:
            with self.assertRaises(SolverIntercepted):
                fin.evaluate(3.1, parameters, 1)
            run.assert_called_once()

    def test_grid_reads_relocated_saved_control_manifest(self):
        root = self.root / "policies"
        point = root / "v2_test/point"
        point.mkdir(parents=True)
        suffix = Path("experiments/model_spec_sensitivity_2022/runs/control/benchmark")
        (point.parent / "manifest.json").write_text(json.dumps({
            "benchmark": str(Path("/old/author/model") / suffix),
            "environment": {"GKK_DBN_MAX_ITER": "700"}}))
        (point / "result.json").write_text(json.dumps({"status": "ok", "tau_w": .030618034,
            "tau_k": 0., "tau_bq": .4, "ce2_newborn": 8.3912}))
        with patch.object(grid, "ROOT", self.root), \
                patch.object(grid, "CONTROL_BENCH", self.root / suffix), \
                patch.object(grid, "CONTROL_ROOTS", [root]):
            self.assertEqual(grid.control_results()["owt"]["ce2_newborn"], 8.3912)

    def make_runner_benchmark(self, profile="reported"):
        work = self.root / "runtime/reproduction/test"
        folder = work / "benchmark"
        self.make_benchmark(folder)
        info, env, cal = {"executable_sha256": {"bench.a": "test"}}, {}, {}
        inputs = {"profile": profile,
                  "environment": {"GKK_RESULT_FOLDER": str(folder.relative_to(self.root)) + "/"},
                  "calibration_sha256": cal, "executable_sha256": "test"}
        files = ["output.txt", *["Bench_Files/" + n for n in runner.STATES]]
        record = {"inputs": inputs, "files_sha256": {n: runner.sha(folder / n) for n in files}}
        (folder / "done.json").write_text(json.dumps(record))
        return work, info, env, cal

    def test_legacy_install_keeps_old_evidence_and_consistent_state(self):
        work, info, env, cal = self.make_runner_benchmark()
        target = self.root / "calibration/runs/business_financing_2022/rn_reform"
        target.mkdir(parents=True)
        (target / "output.txt").write_text("historical evidence\n")
        record = runner.install_legacy_benchmark(self.root, work, info, env, cal)
        self.assertEqual((self.root / record["backup"] / "output.txt").read_text(),
                         "historical evidence\n")
        self.assertEqual((target / "output.txt").read_bytes(),
                         (work / "benchmark/output.txt").read_bytes())
        self.assertTrue(cache.complete_benchmark(target))
        self.assertEqual(runner.install_legacy_benchmark(self.root, work, info, env, cal), record)

    def test_legacy_install_rejects_changed_source_before_touching_target(self):
        work, info, env, cal = self.make_runner_benchmark()
        (work / "benchmark/Bench_Files/DBN").write_text("altered")
        with self.assertRaises(RuntimeError):
            runner.install_legacy_benchmark(self.root, work, info, env, cal)
        self.assertFalse((self.root / "calibration/runs/business_financing_2022/rn_reform").exists())

    def test_runner_rejects_inherited_model_and_openmp_overrides(self):
        self.assertEqual(runner.clean_environment_from({"PATH": "bin", "GKK_THETA_MAX": "99",
            "GKK_DBN_TOL": "1", "OMP_NUM_THREADS": "99"}), {"PATH": "bin"})

    def test_theta_profile_preserves_scf_parameters_and_separates_default_workspace(self):
        reported, _ = runner.calibration(model, "reported")
        theta, _ = runner.calibration(model, "theta2800")
        self.assertEqual(float(theta["GKK_THETA_MAX"]), 2.8)
        self.assertEqual({k: v for k, v in theta.items() if k != "GKK_THETA_MAX"},
                         {k: v for k, v in reported.items() if k != "GKK_THETA_MAX"})
        plans = {}
        for profile in ("reported", "theta2800"):
            output = io.StringIO()
            with patch.object(sys, "argv", ["runner", "--model-root", str(model),
                    "--profile", profile, "--stage", "plan"]), redirect_stdout(output), \
                    patch.object(runner, "build") as build:
                self.assertEqual(runner.main(), 0)
                build.assert_not_called()
            plans[profile] = json.loads(output.getvalue())
            self.assertEqual(plans[profile]["profile"], profile)
        self.assertNotEqual(plans["reported"]["workspace"], plans["theta2800"]["workspace"])
        self.assertEqual(plans["theta2800"]["policies"], {})

    def test_theta_profile_installs_scf_target_and_rejects_reported_policy_comparison(self):
        work, info, env, cal = self.make_runner_benchmark("theta2800")
        suffix = Path("calibration/runs/scf_2022/3f5118dda04e")
        scf_best = self.root / "calibration/runs/scf_2022/best.json"
        scf_best.parent.mkdir(parents=True)
        scf_best.write_text(json.dumps({"run_directory": str(Path("/old/author/model") / suffix)}))
        record = runner.install_legacy_benchmark(self.root, work, info, env, cal, "theta2800")
        self.assertTrue(cache.complete_benchmark(self.root / suffix))
        self.assertEqual(record["profile"], "theta2800")
        self.assertEqual(record["inputs"]["profile"], "theta2800")
        self.assertFalse((self.root / "calibration/runs/business_financing_2022/rn_reform").exists())
        with self.assertRaises(ValueError):
            runner.policies(self.root, work, info, env, cal, ["owt"], 1, "theta2800")
        for stage in ("policies", "all"):
            with patch.object(sys, "argv", ["runner", "--profile", "theta2800", "--stage", stage]), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                runner.main()
            self.assertEqual(stopped.exception.code, 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, default=REPO / "replication")
    args = parser.parse_args()
    model = args.model_root.resolve()
    sys.path[:0] = [str(model / "tools"), str(model / "experiments/model_spec_sensitivity_2022")]
    cache = load("portable_cache", model / "tools/benchmark_cache.py")
    fin = load("portable_financing", model / "tools/recalibrate_financing_2022.py")
    sens = load("portable_sensitivity", model / "experiments/model_spec_sensitivity_2022/run_sensitivity.py")
    grid = load("portable_grid", model / "experiments/grid_accuracy_2022/run_grid_check.py")
    misalloc = load("portable_misallocation", model / "experiments/robustness_gkkoc_2022/misallocation_link.py")
    runner = load("portable_runner", REPO / "scripts/reproduce_reported_2022.py")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PortabilityTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)

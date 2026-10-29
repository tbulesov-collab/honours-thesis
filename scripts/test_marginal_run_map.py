#!/usr/bin/env python3
"""Check marginal-return extraction and fresh-run mappings without model solves.

Reads only the bundled compact reports. Outputs and altered fixtures stay in
temporary directories. Use --model-root to test a relocated snapshot or the
canonical model tree; no model executable or compiler is launched.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
REPORTS = (
    "result.json", "output.txt", "Mg_Return_W_Pct_Bench.txt",
    "Constrained_firms_stats.txt", "Asset_Stats_bench.txt",
    "Joint_Tax/output_exp.txt", "Joint_Tax/Mg_Return_W_Pct_Exp.txt",
    "Joint_Tax/Constrained_firms_stats_exp.txt", "Joint_Tax/Asset_Stats_exp.txt",
)


class MarginalRunMapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="marginal-run-map-")
        self.addCleanup(temporary.cleanup)
        self.temp = Path(temporary.name).resolve()
        self.mapping = {name: rel for name, (_, rel) in extractor.POLICIES.items()}
        self.expected = json.loads((extractor.HERE / "results.json").read_text())

    def extract(self, mapping=None, *, root=None, output="output"):
        target = self.temp / output
        argv = ["extract_marginal_returns.py", "--out", str(target)]
        if mapping is not None:
            map_file = self.temp / "run-map.json"
            map_file.write_text(json.dumps(mapping))
            argv += ["--run-map", str(map_file)]
        with patch.object(sys, "argv", argv), \
                patch.object(extractor, "ROOT", root or model), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(extractor.main(), 0)
        return json.loads((target / "results.json").read_text())

    def assert_map_rejected(self, mapping, *, root=None):
        with self.assertRaises(SystemExit) as stopped:
            self.extract(mapping, root=root)
        self.assertEqual(stopped.exception.code, 2)
        self.assertFalse((self.temp / "output").exists())

    def copy_runs(self):
        """Copy only extraction inputs into new, deliberately different paths."""
        root = self.temp / "relocated-model"
        root.mkdir()
        mapping = {name: f"new-runs/{name}" for name in self.mapping}
        for name, old in self.mapping.items():
            for report in REPORTS:
                target = root / mapping[name] / report
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(model / old / report, target)
        return root, mapping

    def test_default_matches_bundled_results(self):
        self.assertEqual(self.extract(), self.expected)

    def test_explicit_mapping_matches_default_results(self):
        self.assertEqual(self.extract(self.mapping), self.expected)

    def test_new_run_folders_preserve_statistics_and_record_new_sources(self):
        root, mapping = self.copy_runs()
        actual = self.extract(mapping, root=root)
        self.assertEqual(actual.keys(), self.expected.keys())
        for name in actual:
            self.assertEqual({k:v for k,v in actual[name].items() if k != "sources"},
                             {k:v for k,v in self.expected[name].items() if k != "sources"})
            if name != "benchmark":
                self.assertTrue(all(p.startswith(mapping[name] + "/")
                                    for p in actual[name]["sources"]))

    def test_missing_policy_is_rejected(self):
        mapping = dict(self.mapping)
        mapping.pop("separate_wealth")
        self.assert_map_rejected(mapping)

    def test_unknown_policy_is_rejected(self):
        self.assert_map_rejected({**self.mapping, "extra_policy": "unused"})

    def test_nonstring_folder_is_rejected(self):
        self.assert_map_rejected({**self.mapping, "separate_wealth": 3})

    def test_missing_folder_is_rejected(self):
        self.assert_map_rejected({**self.mapping, "separate_wealth": "missing-run"})

    def test_parent_traversal_is_rejected(self):
        self.assert_map_rejected({**self.mapping, "separate_wealth": "../outside"})

    def test_absolute_folder_is_rejected(self):
        self.assert_map_rejected({**self.mapping,
                                 "separate_wealth": str(model / self.mapping["separate_wealth"])})

    def test_symlink_escape_is_rejected(self):
        root = self.temp / "model"
        root.mkdir()
        try:
            (root / "escape").symlink_to(self.temp, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Cannot create symlink on this platform: {exc}")
        map_file = self.temp / "run-map.json"
        map_file.write_text(json.dumps({**self.mapping, "separate_wealth": "escape"}))
        with patch.object(extractor, "ROOT", root), self.assertRaisesRegex(ValueError, "outside"):
            extractor.run_folders(map_file)

    def test_wrong_policy_rates_are_rejected_before_output(self):
        mapping = {**self.mapping, "separate_wealth": self.mapping["separate_subsidy"]}
        with self.assertRaisesRegex(ValueError, "expected"):
            self.extract(mapping)
        self.assertFalse((self.temp / "output").exists())

    def test_mixed_benchmarks_are_rejected_before_output(self):
        root, mapping = self.copy_runs()
        report = root / mapping["separate_subsidy"] / "Asset_Stats_bench.txt"
        text, count = re.subn(r"(Mean_Return_z\s+1_AT\s+)(\S+)",
                             lambda m: m[1] + str(float(m[2]) + .001),
                             report.read_text(), count=1)
        self.assertEqual(count, 1)
        report.write_text(text)
        with self.assertRaisesRegex(ValueError, "benchmark report differs"):
            self.extract(mapping, root=root)
        self.assertFalse((self.temp / "output").exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, default=REPO / "replication")
    args = parser.parse_args()
    model = args.model_root.resolve()
    module_path = model / "experiments/marginal_returns_2022/extract_marginal_returns.py"
    spec = importlib.util.spec_from_file_location("tested_marginal_extractor", module_path)
    extractor = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(extractor)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MarginalRunMapTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)

"""Regression checks for policy validation and cache provenance (no economic solves)."""
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from policy_evaluation import PolicyEvaluator, atomic_json

FAKE = '''#!/usr/bin/env python3
import os, pathlib, sys
if os.environ.get('GKK_EVALUATOR_CHECK'):
    print('GKK_POLICY_EVALUATOR_V2 FIXED_LABOR_CAPABLE')
    raise SystemExit(0)
e = os.environ
case = e.get('GKK_TEST_CASE', '')
root = pathlib.Path(e['GKK_RESULT_FOLDER'])
fixed = e.get('GKK_JOINT_FIXED_LABOR') == '1'
folder = root / ('Joint_Tax_Fixed_Labor' if fixed else 'Joint_Tax')
folder.mkdir(parents=True)
if case == 'crash':
    raise SystemExit(3)
gap = float(e.get('GKK_TEST_GAP', '0'))
values = {
'Evaluation_Schema': 2, 'Equilibrium_Converged': 1,
'Equilibrium_Residual': 1e-10, 'Aggregate_Residual': 1e-9,
'Equilibrium_Iterations': 10, 'Budget_Tolerance': float(e['GKK_JOINT_BUDGET_TOL']),
'Revenue_Relative_Gap': abs(gap), 'GBAR': 2 * (1 + gap), 'YBAR': 11, 'CBAR': 6,
'Wealth_Tax_Above': float(e['GKK_JOINT_TAUW']), 'Tau_K': float(e['GKK_JOINT_TAUK']),
'Tau_BQ': float(e['GKK_JOINT_TAUBQ']), 'Psi': .776, 'Wealth_Top_1%': .4,
'CE2_NB(exp)': 8, 'CE2_Pop(exp)': 4, 'CE1_NB(exp)': 7,
}
if case == 'nan': values['CE2_NB(exp)'] = float('nan')
if case == 'unconverged': values['Equilibrium_Converged'] = 0
if case == 'residual': values['Aggregate_Residual'] = .1
if case == 'wrong_tax': values['Tau_K'] = .123
if case == 'wrong_labor': values['Psi'] = .9
if case == 'old': del values['Evaluation_Schema']
if case == 'wrong_tol': values['Budget_Tolerance'] = .1
(folder / 'output_exp.txt').write_text('\\n'.join(f'{k} {v}' for k, v in values.items()))
'''


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bench = self.root / 'bench'
        (self.bench / 'Bench_Files').mkdir(parents=True)
        (self.bench / 'output.txt').write_text('GBAR 2\nYBAR 10\nCBAR 5\nAverage_Labor_Tax .224\n')
        (self.bench / 'Bench_Files/state').write_text('benchmark')
        self.exe = self.root / 'model.a'
        self.exe.write_text(FAKE)
        self.exe.chmod(0o755)
        (self.root / 'model.f90').write_text('! model version 1\n')
        self.environment = patch.dict(os.environ, {}, clear=False)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for key in list(os.environ):
            if key.startswith(('GKK_', 'OMP_')):
                del os.environ[key]

    def evaluator(self, **kwargs):
        defaults = dict(root=self.root, executable=self.exe, benchmark=self.bench,
                        run_root=self.root/'runs', threads=1, bounds=((0,.1),(-.5,.25),(0,.8)),
                        labor_bounds=(0,.6), budget_tolerance=1e-4, calibration_env={'GKK_RHO_Z': '.1'})
        defaults.update(kwargs)
        return PolicyEvaluator(**defaults)

    def test_success_cache_and_raw_summary_validation(self):
        ev = self.evaluator()
        first = ev.evaluate_rates((.03,-.1,.4))
        self.assertTrue(ev.is_feasible(first))
        second = ev.evaluate_rates((.03,-.1,.4))
        self.assertEqual(first['result_directory'], second['result_directory'])
        self.assertEqual(ev.eval_count, 1)
        path = self.root/first['result_directory']
        summary = json.loads((path.parent/'result.json').read_text())
        summary['ce2_newborn'] = 999
        atomic_json(path.parent/'result.json', summary)
        self.assertEqual(ev.evaluate_rates((.03,-.1,.4))['ce2_newborn'], 8)

    def test_raw_output_tampering_is_not_reused(self):
        ev = self.evaluator()
        first = ev.evaluate_rates((.03,0,.4))
        (self.root/first['result_directory']/'output_exp.txt').write_text('stale')
        second = ev.evaluate_rates((.03,0,.4))
        self.assertNotEqual(first['result_directory'], second['result_directory'])
        self.assertEqual(ev.eval_count, 2)

    def test_full_precision_rates_have_distinct_keys(self):
        ev = self.evaluator()
        self.assertNotEqual(ev.candidate_key((.03,0,.4)), ev.candidate_key((.03000000001,0,.4)))
        for bad in [float('nan'), float('inf')]:
            with self.assertRaises(ValueError): ev.candidate_key((bad,0,.4))

    def test_context_changes_for_all_model_inputs(self):
        first = self.evaluator().context_id
        cases = [dict(budget_tolerance=1e-5), dict(threads=2),
                 dict(calibration_env={'GKK_RHO_Z': '.2'}), dict(fixed_labor=True),
                 dict(labor_bounds=(0,.5))]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs): self.assertNotEqual(first, self.evaluator(**kwargs).context_id)
        for path in [self.exe, self.bench/'Bench_Files/state', self.root/'model.f90']:
            previous = self.evaluator().context_id
            path.write_text(path.read_text()+'\n# changed\n')
            self.assertNotEqual(previous, self.evaluator().context_id)
        os.environ['GKK_DBN_TOL'] = '1e-8'
        self.assertNotEqual(first, self.evaluator().context_id)

    def test_changed_input_during_search_stops_evaluation(self):
        ev = self.evaluator()
        (self.bench/'Bench_Files/state').write_text('changed')
        with self.assertRaisesRegex(RuntimeError, 'inputs changed'): ev.evaluate_rates((.03,0,.4))

    def test_legacy_results_are_preserved_and_ignored(self):
        old = self.root/'runs'
        old.mkdir()
        (old/'best.json').write_text('{"legacy":true}')
        ev = self.evaluator()
        self.assertNotEqual(old, ev.run_root)
        ev.evaluate_rates((.03,0,.4))
        self.assertEqual((old/'best.json').read_text(), '{"legacy":true}')

    def test_failures_and_nonfinite_output_never_become_results(self):
        for case in ['crash','nan','unconverged','residual','wrong_tax','old','wrong_tol']:
            with self.subTest(case=case):
                os.environ['GKK_TEST_CASE'] = case
                ev = self.evaluator()
                with self.assertRaises(RuntimeError): ev.evaluate_rates((.03,0,.4))
                self.assertEqual(list(ev.run_root.glob('*/result.json')), [])
                self.assertEqual(len(list(ev.run_root.glob('*/failure.json'))), 1)

    def test_strict_revenue_tolerance(self):
        os.environ['GKK_TEST_GAP'] = '.0002'  # used to pass the five-times filter
        ev = self.evaluator()
        with self.assertRaisesRegex(RuntimeError, 'revenue tolerance'): ev.evaluate_rates((.03,0,.4))

    def test_fixed_labor_can_explore_but_not_select_infeasible_points(self):
        os.environ['GKK_TEST_GAP'] = '.0002'
        ev = self.evaluator(fixed_labor=True)
        row = ev.evaluate_rates((.03,0,.4))
        self.assertFalse(row['feasible'])
        self.assertFalse(ev.is_feasible(row))
        row['revenue_relative_gap'] = 0  # forged summary cannot bypass recomputation
        self.assertFalse(ev.is_feasible(row))

    def test_configured_labor_bounds_are_used(self):
        ev = self.evaluator(labor_bounds=(0,.2), fixed_labor=True)
        row = ev.evaluate_rates((.03,0,.4))
        self.assertFalse(ev.is_feasible(row))

    def test_fixed_labor_tax_change_rejected(self):
        os.environ['GKK_TEST_CASE'] = 'wrong_labor'
        ev = self.evaluator(fixed_labor=True)
        with self.assertRaisesRegex(RuntimeError, 'labour tax'): ev.evaluate_rates((.03,0,.4))

    def test_inherited_candidate_controls_are_overridden(self):
        os.environ.update(GKK_JOINT_TAUK='.8', GKK_RESULT_FOLDER='wrong', GKK_JOINT_FIXED_LABOR='1')
        ev = self.evaluator()
        row = ev.evaluate_rates((.03,-.1,.4))
        self.assertEqual(row['tau_k'], -.1)
        self.assertTrue(row['result_directory'].endswith('/Joint_Tax'))

    def test_force_uses_fresh_attempt(self):
        ev = self.evaluator()
        first = ev.evaluate_rates((.03,0,.4))
        second = ev.evaluate_rates((.03,0,.4), force=True)
        self.assertNotEqual(first['result_directory'], second['result_directory'])
        self.assertEqual(ev.eval_count, 2)

    def test_bad_budget_tolerance_rejected(self):
        for value in [0,-1,float('nan'),float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError): self.evaluator(budget_tolerance=value)


if __name__ == '__main__':
    unittest.main()
